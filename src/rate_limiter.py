"""
分布式 Rate Limiter 核心实现
使用 Redis 和滑动窗口算法
"""
import asyncio
import time
from typing import Dict, Tuple, Optional
import redis.asyncio as redis
from datetime import datetime, timedelta
import json
import tiktoken
from src.config import Config
from src.models import ChatCompletionRequest, RateLimitInfo


class RateLimiter:
    """分布式速率限制器"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.config = Config()
        self.window_size = self.config.SLIDING_WINDOW_SIZE_SECONDS
        self.segments = self.config.WINDOW_SEGMENTS
        self.segment_size = self.window_size // self.segments
        
        # 初始化 tokenizer（用于计算 token 数量）
        try:
            self.encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        except:
            self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def _get_current_segment(self) -> int:
        """获取当前时间所在的段"""
        current_time = int(time.time())
        return current_time // self.segment_size
    
    def _get_window_segments(self) -> Tuple[int, int]:
        """获取滑动窗口的起始和结束段"""
        current_segment = self._get_current_segment()
        start_segment = current_segment - self.segments + 1
        return start_segment, current_segment
    
    def _get_redis_keys(self, api_key: str) -> Dict[str, str]:
        """获取 Redis 键名"""
        return {
            "rpm": f"rate_limit:rpm:{api_key}",
            "input_tpm": f"rate_limit:input_tpm:{api_key}",
            "output_tpm": f"rate_limit:output_tpm:{api_key}"
        }
    
    async def _increment_counter(self, key: str, segment: int, value: int = 1) -> None:
        """增加计数器"""
        field = str(segment)
        pipe = self.redis.pipeline()
        pipe.hincrby(key, field, value)
        pipe.expire(key, self.window_size * 2)  # 设置过期时间为窗口大小的两倍
        await pipe.execute()
    
    async def _get_window_sum(self, key: str) -> int:
        """获取滑动窗口内的总和"""
        start_segment, end_segment = self._get_window_segments()
        
        # 获取所有段的值
        segments_to_check = [str(i) for i in range(start_segment, end_segment + 1)]
        values = await self.redis.hmget(key, segments_to_check)
        
        # 计算总和
        total = sum(int(v) if v else 0 for v in values)
        return total
    
    async def _clean_old_segments(self, key: str) -> None:
        """清理过期的段"""
        start_segment, _ = self._get_window_segments()
        
        # 获取所有字段
        all_fields = await self.redis.hkeys(key)
        if not all_fields:
            return
        
        # 找出需要删除的字段
        fields_to_delete = []
        for field in all_fields:
            try:
                segment = int(field)
                if segment < start_segment:
                    fields_to_delete.append(field)
            except ValueError:
                continue
        
        # 删除过期字段
        if fields_to_delete:
            await self.redis.hdel(key, *fields_to_delete)
    
    def count_tokens(self, text: str) -> int:
        """计算文本的 token 数量"""
        return len(self.encoding.encode(text))
    
    def estimate_request_tokens(self, request: ChatCompletionRequest) -> int:
        """估算请求的 token 数量"""
        total_tokens = 0
        for message in request.messages:
            # 角色和内容的 token
            total_tokens += self.count_tokens(message.role)
            total_tokens += self.count_tokens(message.content)
            # 消息格式的额外 token
            total_tokens += 4  # 每条消息的格式开销
        
        total_tokens += 2  # 对话的开始和结束标记
        return total_tokens
    
    async def check_rate_limit(self, api_key: str, request: ChatCompletionRequest) -> Tuple[bool, Optional[RateLimitInfo]]:
        """
        检查速率限制
        返回: (是否允许请求, 速率限制信息)
        """
        # 获取 API Key 的限制
        limits = self.config.get_api_key_limits(api_key)
        
        # 获取 Redis 键
        keys = self._get_redis_keys(api_key)
        
        # 估算请求的 token 数量
        input_tokens = self.estimate_request_tokens(request)
        
        # 估算输出 token（使用 max_tokens 或默认值）
        output_tokens = request.max_tokens if request.max_tokens else 1000
        
        # 获取当前使用量
        current_rpm = await self._get_window_sum(keys["rpm"])
        current_input_tpm = await self._get_window_sum(keys["input_tpm"])
        current_output_tpm = await self._get_window_sum(keys["output_tpm"])
        
        # 创建速率限制信息
        window_start, window_end = self._get_window_segments()
        rate_limit_info = RateLimitInfo(
            api_key=api_key,
            input_tpm_used=current_input_tpm,
            output_tpm_used=current_output_tpm,
            rpm_used=current_rpm,
            input_tpm_limit=limits["input_tpm"],
            output_tpm_limit=limits["output_tpm"],
            rpm_limit=limits["rpm"],
            window_start=datetime.fromtimestamp(window_start * self.segment_size),
            window_end=datetime.fromtimestamp((window_end + 1) * self.segment_size)
        )
        
        # 检查是否超限
        if current_rpm + 1 > limits["rpm"]:
            return False, rate_limit_info
        
        if current_input_tpm + input_tokens > limits["input_tpm"]:
            return False, rate_limit_info
        
        if current_output_tpm + output_tokens > limits["output_tpm"]:
            return False, rate_limit_info
        
        return True, rate_limit_info
    
    async def record_usage(self, api_key: str, input_tokens: int, output_tokens: int) -> None:
        """记录使用量"""
        current_segment = self._get_current_segment()
        keys = self._get_redis_keys(api_key)
        
        # 使用管道批量执行
        pipe = self.redis.pipeline()
        
        # 增加计数
        pipe.hincrby(keys["rpm"], str(current_segment), 1)
        pipe.hincrby(keys["input_tpm"], str(current_segment), input_tokens)
        pipe.hincrby(keys["output_tpm"], str(current_segment), output_tokens)
        
        # 设置过期时间
        expire_time = self.window_size * 2
        pipe.expire(keys["rpm"], expire_time)
        pipe.expire(keys["input_tpm"], expire_time)
        pipe.expire(keys["output_tpm"], expire_time)
        
        await pipe.execute()
        
        # 异步清理旧数据（不阻塞主流程）
        asyncio.create_task(self._clean_old_segments(keys["rpm"]))
        asyncio.create_task(self._clean_old_segments(keys["input_tpm"]))
        asyncio.create_task(self._clean_old_segments(keys["output_tpm"]))
    
    async def get_rate_limit_headers(self, api_key: str, rate_limit_info: RateLimitInfo) -> Dict[str, str]:
        """生成速率限制响应头"""
        reset_time = rate_limit_info.window_end
        
        headers = {
            "X-RateLimit-Limit-Requests": str(rate_limit_info.rpm_limit),
            "X-RateLimit-Limit-Tokens-Input": str(rate_limit_info.input_tpm_limit),
            "X-RateLimit-Limit-Tokens-Output": str(rate_limit_info.output_tpm_limit),
            "X-RateLimit-Remaining-Requests": str(max(0, rate_limit_info.rpm_limit - rate_limit_info.rpm_used)),
            "X-RateLimit-Remaining-Tokens-Input": str(max(0, rate_limit_info.input_tpm_limit - rate_limit_info.input_tpm_used)),
            "X-RateLimit-Remaining-Tokens-Output": str(max(0, rate_limit_info.output_tpm_limit - rate_limit_info.output_tpm_used)),
            "X-RateLimit-Reset-Requests": reset_time.isoformat(),
            "X-RateLimit-Reset-Tokens": reset_time.isoformat(),
            "Retry-After": str(int((reset_time - datetime.now()).total_seconds()))
        }
        
        return headers 
"""
FastAPI 服务器实现
处理 OpenAI 格式的 API 请求并应用速率限制
"""
import asyncio
import random
import time
import sys
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse
import redis.asyncio as redis
import uvicorn

from src.config import Config
from src.models import (
    ChatCompletionRequest, 
    ChatCompletionResponse,
    ChatMessage,
    Choice,
    Usage,
    ErrorResponse
)
from src.rate_limiter import RateLimiter


class RateLimiterServer:
    """Rate Limiter 服务器"""
    
    def __init__(self, port: int = 8000):
        self.app = FastAPI(title="LLM API Rate Limiter")
        self.config = Config()
        self.port = port
        self.redis_client = None
        self.rate_limiter = None
        
        # 设置路由
        self._setup_routes()
    
    async def startup(self):
        """启动事件"""
        # 连接 Redis
        self.redis_client = await redis.from_url(
            f"redis://{self.config.REDIS_HOST}:{self.config.REDIS_PORT}/{self.config.REDIS_DB}",
            password=self.config.REDIS_PASSWORD,
            decode_responses=True
        )
        
        # 测试 Redis 连接
        try:
            await self.redis_client.ping()
            print(f"[OK] Connected to Redis {self.config.REDIS_HOST}:{self.config.REDIS_PORT}")
        except Exception as e:
            print(f"[ERROR] Cannot connect to Redis: {e}")
            sys.exit(1)
        
        # 创建 Rate Limiter
        self.rate_limiter = RateLimiter(self.redis_client)
        print(f"[INFO] Rate Limiter server started on port {self.port}")
    
    async def shutdown(self):
        """关闭事件"""
        if self.redis_client:
            await self.redis_client.close()
        print("[INFO] Rate Limiter server stopped")
    
    def _setup_routes(self):
        """设置路由"""
        self.app.add_event_handler("startup", self.startup)
        self.app.add_event_handler("shutdown", self.shutdown)
        
        @self.app.get("/health")
        async def health_check():
            """健康检查"""
            return {"status": "healthy", "service": "rate-limiter", "port": self.port}
        
        @self.app.post("/v1/chat/completions")
        async def chat_completions(
            request: ChatCompletionRequest,
            authorization: Optional[str] = Header(None)
        ):
            """处理聊天补全请求"""
            # 提取 API Key
            if not authorization or not authorization.startswith("Bearer "):
                raise HTTPException(
                    status_code=401,
                    detail={"error": {"message": "Invalid authorization header", "type": "invalid_request_error"}}
                )
            
            api_key = authorization.replace("Bearer ", "")
            
            # 检查 API Key 是否有效
            if api_key not in self.config.API_KEY_LIMITS:
                raise HTTPException(
                    status_code=401,
                    detail={"error": {"message": "Invalid API key", "type": "invalid_request_error"}}
                )
            
            # 检查速率限制
            allowed, rate_limit_info = await self.rate_limiter.check_rate_limit(api_key, request)
            
            # 生成响应头
            headers = await self.rate_limiter.get_rate_limit_headers(api_key, rate_limit_info)
            
            if not allowed:
                # 返回 429 错误
                return JSONResponse(
                    status_code=429,
                    headers=headers,
                    content={
                        "error": {
                            "message": "Rate limit exceeded",
                            "type": "rate_limit_exceeded",
                            "param": None,
                            "code": "rate_limit_exceeded"
                        }
                    }
                )
            
            # 生成 mock 响应
            mock_response = await self._generate_mock_response(request)
            
            # 记录使用量
            await self.rate_limiter.record_usage(
                api_key,
                mock_response.usage.prompt_tokens,
                mock_response.usage.completion_tokens
            )
            
            # 返回响应
            return JSONResponse(
                status_code=200,
                headers=headers,
                content=mock_response.model_dump()
            )
    
    async def _generate_mock_response(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """生成 mock OpenAI API 响应"""
        # 模拟处理延迟
        delay = random.uniform(
            self.config.MOCK_RESPONSE_DELAY_MIN,
            self.config.MOCK_RESPONSE_DELAY_MAX
        )
        await asyncio.sleep(delay)
        
        # 计算 token 数量
        prompt_tokens = self.rate_limiter.estimate_request_tokens(request)
        
        # 生成 mock 响应内容
        mock_content = self._generate_mock_content(request)
        completion_tokens = self.rate_limiter.count_tokens(mock_content)
        
        # 创建响应
        response = ChatCompletionResponse(
            model=request.model,
            choices=[
                Choice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=mock_content
                    ),
                    finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens
            ),
            system_fingerprint="fp_mock"
        )
        
        return response
    
    def _generate_mock_content(self, request: ChatCompletionRequest) -> str:
        """生成 mock 响应内容"""
        # 简单的 mock 响应生成
        templates = [
            "This is a mock response. Your request has been successfully processed.",
            "I understand your request. This is a system-generated test response.",
            "Processing complete. This is a mock response from the Rate Limiter system.",
            f"Message received. Currently using model: {request.model}.",
            "This is an auto-generated response for testing rate limiting functionality."
        ]
        
        # 随机选择一个模板
        base_content = random.choice(templates)
        
        # 如果设置了 max_tokens，生成相应长度的内容
        if request.max_tokens and request.max_tokens > 50:
            additional_content = " This is additional content to fill the response." * (request.max_tokens // 20)
            base_content += additional_content
        
        return base_content
    
    def run(self):
        """运行服务器"""
        uvicorn.run(
            self.app,
            host=self.config.SERVER_HOST,
            port=self.port,
            log_level="info"
        )


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="LLM API Rate Limiter Server")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    args = parser.parse_args()
    
    server = RateLimiterServer(port=args.port)
    server.run()


if __name__ == "__main__":
    main() 
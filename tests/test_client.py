"""
测试客户端 - 模拟生成 OpenAI API 请求
"""
import asyncio
import random
import time
import json
from typing import List, Dict, Any
from datetime import datetime
import httpx
from dataclasses import dataclass, field
import argparse
import statistics


@dataclass
class RequestStats:
    """请求统计信息"""
    total_requests: int = 0
    successful_requests: int = 0
    rate_limited_requests: int = 0
    failed_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    response_times: List[float] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    
    def get_summary(self) -> Dict[str, Any]:
        """获取统计摘要"""
        elapsed_time = time.time() - self.start_time
        
        return {
            "duration_seconds": elapsed_time,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "rate_limited_requests": self.rate_limited_requests,
            "failed_requests": self.failed_requests,
            "requests_per_second": self.total_requests / elapsed_time if elapsed_time > 0 else 0,
            "success_rate": self.successful_requests / self.total_requests if self.total_requests > 0 else 0,
            "rate_limit_rate": self.rate_limited_requests / self.total_requests if self.total_requests > 0 else 0,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "avg_response_time": statistics.mean(self.response_times) if self.response_times else 0,
            "p50_response_time": statistics.median(self.response_times) if self.response_times else 0,
            "p95_response_time": statistics.quantiles(self.response_times, n=20)[18] if len(self.response_times) > 20 else 0,
            "p99_response_time": statistics.quantiles(self.response_times, n=100)[98] if len(self.response_times) > 100 else 0,
        }


class TestClient:
    """OpenAI API 测试客户端"""
    
    def __init__(self, server_urls: List[str], api_keys: List[str]):
        self.server_urls = server_urls
        self.api_keys = api_keys
        self.stats = RequestStats()
        
        # 预定义的消息模板
        self.message_templates = [
            "告诉我关于人工智能的有趣事实。",
            "如何学习编程？给我一些建议。",
            "解释一下什么是机器学习。",
            "写一个关于未来科技的短故事。",
            "Python 和 JavaScript 有什么区别？",
            "如何提高工作效率？",
            "解释一下区块链技术。",
            "给我推荐一些好书。",
            "如何保持身心健康？",
            "介绍一下云计算的概念。"
        ]
        
        self.models = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"]
    
    def generate_request(self) -> Dict[str, Any]:
        """生成随机的 OpenAI API 请求"""
        messages = []
        
        # 随机生成 1-3 条消息
        num_messages = random.randint(1, 3)
        for i in range(num_messages):
            role = "user" if i % 2 == 0 else "assistant"
            content = random.choice(self.message_templates)
            
            # 随机增加消息长度
            if random.random() < 0.3:
                content += " " + " ".join(["这是额外的内容。"] * random.randint(5, 20))
            
            messages.append({
                "role": role,
                "content": content
            })
        
        # 确保最后一条消息是用户消息
        if messages[-1]["role"] != "user":
            messages.append({
                "role": "user",
                "content": random.choice(self.message_templates)
            })
        
        request = {
            "model": random.choice(self.models),
            "messages": messages,
            "temperature": random.uniform(0.5, 1.0),
            "max_tokens": random.choice([None, 100, 500, 1000, 2000])
        }
        
        return request
    
    async def send_request(self, client: httpx.AsyncClient, request_data: Dict[str, Any]) -> None:
        """发送单个请求"""
        # 随机选择服务器和 API Key
        server_url = random.choice(self.server_urls)
        api_key = random.choice(self.api_keys)
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        start_time = time.time()
        
        try:
            response = await client.post(
                f"{server_url}/v1/chat/completions",
                json=request_data,
                headers=headers,
                timeout=30.0
            )
            
            response_time = time.time() - start_time
            self.stats.response_times.append(response_time)
            self.stats.total_requests += 1
            
            if response.status_code == 200:
                self.stats.successful_requests += 1
                data = response.json()
                if "usage" in data:
                    self.stats.total_input_tokens += data["usage"]["prompt_tokens"]
                    self.stats.total_output_tokens += data["usage"]["completion_tokens"]
                
                print(f"✅ 成功 | API Key: {api_key} | 响应时间: {response_time:.2f}s")
            
            elif response.status_code == 429:
                self.stats.rate_limited_requests += 1
                print(f"⚠️  限流 | API Key: {api_key} | {response.headers.get('X-RateLimit-Limit-Requests', 'N/A')} RPM")
            
            else:
                self.stats.failed_requests += 1
                print(f"❌ 失败 | API Key: {api_key} | 状态码: {response.status_code}")
        
        except Exception as e:
            self.stats.failed_requests += 1
            self.stats.total_requests += 1
            print(f"❌ 错误 | API Key: {api_key} | 错误: {str(e)}")
    
    async def run_concurrent_requests(self, num_requests: int, concurrency: int) -> None:
        """并发运行多个请求"""
        print(f"\n🚀 开始测试: {num_requests} 个请求，并发数: {concurrency}")
        print(f"📡 服务器: {self.server_urls}")
        print(f"🔑 API Keys: {self.api_keys}\n")
        
        async with httpx.AsyncClient() as client:
            semaphore = asyncio.Semaphore(concurrency)
            
            async def send_with_limit():
                async with semaphore:
                    request_data = self.generate_request()
                    await self.send_request(client, request_data)
            
            # 创建所有任务
            tasks = [send_with_limit() for _ in range(num_requests)]
            
            # 并发执行
            await asyncio.gather(*tasks)
    
    def print_stats(self) -> None:
        """打印统计信息"""
        summary = self.stats.get_summary()
        
        print("\n" + "="*60)
        print("📊 测试统计报告")
        print("="*60)
        
        print(f"\n⏱️  测试时长: {summary['duration_seconds']:.2f} 秒")
        print(f"📨 总请求数: {summary['total_requests']}")
        print(f"✅ 成功请求: {summary['successful_requests']} ({summary['success_rate']:.1%})")
        print(f"⚠️  限流请求: {summary['rate_limited_requests']} ({summary['rate_limit_rate']:.1%})")
        print(f"❌ 失败请求: {summary['failed_requests']}")
        
        print(f"\n🚄 吞吐量: {summary['requests_per_second']:.2f} 请求/秒")
        print(f"🔤 总输入 Token: {summary['total_input_tokens']:,}")
        print(f"📤 总输出 Token: {summary['total_output_tokens']:,}")
        
        if summary['avg_response_time'] > 0:
            print(f"\n⏱️  响应时间统计:")
            print(f"   • 平均: {summary['avg_response_time']:.3f} 秒")
            print(f"   • P50: {summary['p50_response_time']:.3f} 秒")
            print(f"   • P95: {summary['p95_response_time']:.3f} 秒")
            print(f"   • P99: {summary['p99_response_time']:.3f} 秒")
        
        print("="*60)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="LLM API Rate Limiter 测试客户端")
    parser.add_argument("--servers", nargs="+", default=["http://localhost:8000", "http://localhost:8001", "http://localhost:8002"],
                       help="Rate Limiter 服务器 URL 列表")
    parser.add_argument("--api-keys", nargs="+", default=["test-key-1", "test-key-2", "test-key-3"],
                       help="API Key 列表")
    parser.add_argument("--requests", type=int, default=100, help="总请求数")
    parser.add_argument("--concurrency", type=int, default=10, help="并发数")
    parser.add_argument("--duration", type=int, help="测试持续时间（秒），如果设置则忽略 --requests")
    
    args = parser.parse_args()
    
    # 创建测试客户端
    client = TestClient(args.servers, args.api_keys)
    
    if args.duration:
        # 基于时间的测试
        print(f"⏰ 运行 {args.duration} 秒的负载测试...")
        start_time = time.time()
        request_count = 0
        
        while time.time() - start_time < args.duration:
            await client.run_concurrent_requests(args.concurrency, args.concurrency)
            request_count += args.concurrency
        
        print(f"\n📊 在 {args.duration} 秒内发送了 {request_count} 个请求")
    else:
        # 基于请求数的测试
        await client.run_concurrent_requests(args.requests, args.concurrency)
    
    # 打印统计信息
    client.print_stats()


if __name__ == "__main__":
    asyncio.run(main()) 
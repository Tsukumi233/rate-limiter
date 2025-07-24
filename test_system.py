#!/usr/bin/env python
"""
系统测试脚本
用于验证 Rate Limiter 系统是否正常工作
"""
import subprocess
import time
import requests
import sys


def check_redis():
    """检查 Redis 是否运行"""
    print("🔍 检查 Redis 连接...")
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("✅ Redis 连接正常")
        return True
    except Exception as e:
        print(f"❌ Redis 连接失败: {e}")
        print("请确保 Redis 服务正在运行")
        return False


def start_server(port=8000):
    """启动单个服务器"""
    print(f"\n🚀 启动 Rate Limiter 服务器 (端口 {port})...")
    process = subprocess.Popen(
        [sys.executable, "-m", "src.server", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(3)  # 等待服务器启动
    return process


def test_health_check(port=8000):
    """测试健康检查端点"""
    print(f"\n🏥 测试健康检查端点...")
    try:
        response = requests.get(f"http://localhost:{port}/health")
        if response.status_code == 200:
            print(f"✅ 健康检查通过: {response.json()}")
            return True
        else:
            print(f"❌ 健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 无法连接到服务器: {e}")
        return False


def test_api_request(port=8000):
    """测试 API 请求"""
    print(f"\n📡 测试 API 请求...")
    headers = {
        "Authorization": "Bearer test-key-1",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "user", "content": "Hello!"}
        ]
    }
    
    try:
        response = requests.post(
            f"http://localhost:{port}/v1/chat/completions",
            json=data,
            headers=headers
        )
        
        if response.status_code == 200:
            print("✅ API 请求成功")
            print(f"   响应 ID: {response.json()['id']}")
            return True
        elif response.status_code == 429:
            print("⚠️  收到限流响应 (429)")
            print(f"   限流信息: {response.headers.get('X-RateLimit-Limit-Requests')} RPM")
            return True
        else:
            print(f"❌ API 请求失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("🧪 Rate Limiter 系统测试")
    print("=" * 60)
    
    # 检查 Redis
    if not check_redis():
        print("\n❌ 测试失败：Redis 未运行")
        return
    
    # 启动服务器
    process = start_server(8888)
    
    try:
        # 测试健康检查
        if not test_health_check(8888):
            print("\n❌ 测试失败：服务器未正常启动")
            return
        
        # 测试 API 请求
        if not test_api_request(8888):
            print("\n❌ 测试失败：API 请求失败")
            return
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过！系统运行正常。")
        print("=" * 60)
        
    finally:
        # 停止服务器
        print("\n🛑 停止测试服务器...")
        process.terminate()
        process.wait()
        print("✅ 测试完成")


if __name__ == "__main__":
    main() 
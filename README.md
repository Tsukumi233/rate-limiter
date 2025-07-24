# 分布式 LLM API Rate Limiter

一个可扩展的分布式速率限制器，用于控制 LLM API 请求。支持基于 Token 和请求数的多维度限流，采用滑动窗口算法实现。

## 功能特点

- **分布式架构**：支持多节点部署，使用 Redis 作为共享存储
- **多维度限流**：支持输入 Token、输出 Token 和请求数三个维度的限流
- **滑动窗口算法**：使用分段滑动窗口算法，实现精确的速率限制
- **OpenAI API 兼容**：完全兼容 OpenAI API 格式
- **高性能**：异步处理，支持高并发请求
- **易于扩展**：可动态添加节点，水平扩展

## 系统架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client 1  │     │   Client 2  │     │   Client N  │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┴───────────────────┘
                           │
       ┌───────────────────┴───────────────────┐
       │                                       │
┌──────▼──────┐     ┌──────▼──────┐     ┌──────▼──────┐
│Rate Limiter │     │Rate Limiter │     │Rate Limiter │
│   Node 1    │     │   Node 2    │     │   Node N    │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┴───────────────────┘
                           │
                    ┌──────▼──────┐
                    │    Redis    │
                    │   Cluster   │
                    └─────────────┘
```

## 安装

### 1. 克隆项目

```bash
git clone <repository-url>
cd rate-limiter
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 安装 Redis

- Windows: 下载并运行 Redis for Windows
- Linux/Mac: 
  ```bash
  # Mac
  brew install redis
  brew services start redis
  
  # Linux
  sudo apt-get install redis-server
  sudo systemctl start redis
  ```

## 使用方法

### 1. 启动 Redis

确保 Redis 服务正在运行：

```bash
redis-cli ping
# 应该返回 PONG
```

### 2. 启动 Rate Limiter 集群

使用多节点启动脚本：

```bash
python start_multi_nodes.py
```

这将在端口 8000, 8001, 8002 启动三个 Rate Limiter 节点。

或者手动启动单个节点：

```bash
python -m src.server --port 8000
```

### 3. 运行测试客户端

```bash
# 基本测试
python tests/test_client.py --requests 100 --concurrency 10

# 指定服务器和 API Keys
python tests/test_client.py \
  --servers http://localhost:8000 http://localhost:8001 \
  --api-keys test-key-1 test-key-2 \
  --requests 200 \
  --concurrency 20

# 基于时间的压力测试
python tests/test_client.py --duration 60 --concurrency 50
```

## API 使用

### 请求格式

```http
POST /v1/chat/completions
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json

{
  "model": "gpt-3.5-turbo",
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "max_tokens": 100
}
```

### 响应格式（成功）

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "gpt-3.5-turbo",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "Hello! How can I help you?"
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 8,
    "total_tokens": 18
  }
}
```

### 响应格式（限流）

```json
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit-Requests: 20
X-RateLimit-Remaining-Requests: 0
Retry-After: 45

{
  "error": {
    "message": "Rate limit exceeded",
    "type": "rate_limit_exceeded",
    "code": "rate_limit_exceeded"
  }
}
```

## 配置

### API Key 配置

在 `src/config.py` 中配置 API Key 和限制：

```python
API_KEY_LIMITS = {
    "test-key-1": {
        "input_tpm": 10000,   # 每分钟输入 Token 限制
        "output_tpm": 10000,  # 每分钟输出 Token 限制
        "rpm": 20             # 每分钟请求数限制
    }
}
```

### 环境变量

创建 `.env` 文件：

```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

SERVER_HOST=0.0.0.0
SERVER_PORT=8000
```

## 性能调优

1. **Redis 优化**：
   - 使用 Redis 集群提高吞吐量
   - 启用 Redis 持久化避免数据丢失
   - 调整 Redis 内存策略

2. **节点扩展**：
   - 增加 Rate Limiter 节点数量
   - 使用负载均衡器分发请求
   - 监控节点健康状态

3. **参数调整**：
   - 调整滑动窗口分段数
   - 优化 Token 计算缓存
   - 设置合理的超时时间

## 监控和维护

- 使用 `/health` 端点检查节点健康状态
- 监控 Redis 内存使用和性能
- 定期清理过期的限流数据
- 记录和分析限流日志

## License

MIT License 
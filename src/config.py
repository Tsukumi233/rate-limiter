"""
Rate Limiter 配置文件
"""
import os
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

class Config:
    """系统配置类"""
    
    # Redis 配置
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
    
    # Rate Limiter 配置
    SLIDING_WINDOW_SIZE_SECONDS = 60  # 滑动窗口大小（秒）
    WINDOW_SEGMENTS = 12  # 窗口分段数（每5秒一个段）
    
    # API 默认限制
    DEFAULT_RATE_LIMITS = {
        "input_tpm": 100000,  # 输入 token 每分钟限制
        "output_tpm": 100000,  # 输出 token 每分钟限制
        "rpm": 100  # 每分钟请求数限制
    }
    
    # API Key 配置（实际应用中应该从数据库读取）
    API_KEY_LIMITS: Dict[str, Dict[str, int]] = {
        "test-key-1": {"input_tpm": 1000, "output_tpm": 1000, "rpm": 10000},
        "test-key-2": {"input_tpm": 10000, "output_tpm": 10000, "rpm": 2000},
        "test-key-3": {"input_tpm": 10000, "output_tpm": 10000, "rpm": 5000}
    }
    
    # 服务器配置
    SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT = int(os.getenv("SERVER_PORT", 8000))
    
    # Mock 响应配置
    MOCK_RESPONSE_DELAY_MIN = 0.1  # 最小响应延迟（秒）
    MOCK_RESPONSE_DELAY_MAX = 0.5  # 最大响应延迟（秒）
    
    @classmethod
    def get_api_key_limits(cls, api_key: str) -> Dict[str, int]:
        """获取 API Key 的限制配置"""
        return cls.API_KEY_LIMITS.get(api_key, cls.DEFAULT_RATE_LIMITS) 
"""
数据模型定义（OpenAI API 格式）
"""
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
import time
import uuid


class ChatMessage(BaseModel):
    """聊天消息模型"""
    role: str
    content: str
    name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    """聊天补全请求模型"""
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = 0
    frequency_penalty: Optional[float] = 0
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None


class Usage(BaseModel):
    """Token 使用情况"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class Choice(BaseModel):
    """响应选项"""
    index: int
    message: ChatMessage
    finish_reason: str


class ChatCompletionResponse(BaseModel):
    """聊天补全响应模型"""
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:8]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[Choice]
    usage: Usage
    system_fingerprint: Optional[str] = None


class ErrorResponse(BaseModel):
    """错误响应模型"""
    error: Dict[str, Any]


class RateLimitInfo(BaseModel):
    """速率限制信息"""
    api_key: str
    input_tpm_used: int
    output_tpm_used: int
    rpm_used: int
    input_tpm_limit: int
    output_tpm_limit: int
    rpm_limit: int
    window_start: datetime
    window_end: datetime


class RateLimitHeaders(BaseModel):
    """速率限制响应头"""
    x_ratelimit_limit_requests: int
    x_ratelimit_limit_tokens_input: int
    x_ratelimit_limit_tokens_output: int
    x_ratelimit_remaining_requests: int
    x_ratelimit_remaining_tokens_input: int
    x_ratelimit_remaining_tokens_output: int
    x_ratelimit_reset_requests: str
    x_ratelimit_reset_tokens: str 
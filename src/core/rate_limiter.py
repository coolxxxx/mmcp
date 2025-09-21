#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
请求限速器组件
实现全局请求频率控制，防止触发服务器限制
"""

import time
import threading
from typing import Optional, Callable, Dict, Any
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class RateLimitConfig:
    """速率限制配置"""
    max_requests_per_second: float = 2.0  # 每秒最大请求数
    burst_capacity: int = 5  # 突发请求容量
    enabled: bool = True  # 是否启用限速
    fast_mode: bool = False  # 快速模式，完全绕过速率限制

class RateLimiter:
    """请求限速器"""
    
    def __init__(self, config: RateLimitConfig):
        """
        初始化限速器
        
        Args:
            config: 速率限制配置
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 令牌桶算法参数
        self.tokens = config.burst_capacity  # 当前令牌数量
        self.last_refill_time = time.time()  # 上次补充令牌的时间
        self.lock = threading.Lock()  # 线程锁
        
    def _refill_tokens(self) -> None:
        """补充令牌"""
        now = time.time()
        elapsed = now - self.last_refill_time
        
        if elapsed > 0:
            # 计算应该补充的令牌数量
            new_tokens = elapsed * self.config.max_requests_per_second
            self.tokens = min(self.config.burst_capacity, self.tokens + new_tokens)
            self.last_refill_time = now
    
    def acquire(self, tokens: int = 1) -> bool:
        """
        获取令牌
        
        Args:
            tokens: 需要的令牌数量
            
        Returns:
            是否成功获取令牌
        """
        if not self.config.enabled:
            return True
            
        with self.lock:
            self._refill_tokens()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    def wait(self, tokens: int = 1) -> None:
        """
        等待直到获取足够的令牌
        
        Args:
            tokens: 需要的令牌数量
        """
        if not self.config.enabled:
            return
            
        while True:
            with self.lock:
                self._refill_tokens()
                
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return
            
            # 计算需要等待的时间
            deficit = tokens - self.tokens
            wait_time = deficit / self.config.max_requests_per_second
            
            # 添加一点缓冲时间
            wait_time = max(0.1, wait_time + 0.05)
            
            self.logger.debug(f"速率限制: 需要等待 {wait_time:.2f} 秒")
            time.sleep(wait_time)
    
    def get_wait_time(self, tokens: int = 1) -> float:
        """
        获取需要等待的时间（秒）
        
        Args:
            tokens: 需要的令牌数量
            
        Returns:
            需要等待的时间（秒）
        """
        if not self.config.enabled:
            return 0.0
            
        with self.lock:
            self._refill_tokens()
            
            if self.tokens >= tokens:
                return 0.0
                
            deficit = tokens - self.tokens
            return deficit / self.config.max_requests_per_second
    
    def set_rate(self, max_requests_per_second: float, burst_capacity: Optional[int] = None) -> None:
        """
        动态设置速率限制
        
        Args:
            max_requests_per_second: 每秒最大请求数
            burst_capacity: 突发请求容量（可选）
        """
        with self.lock:
            self.config.max_requests_per_second = max_requests_per_second
            if burst_capacity is not None:
                self.config.burst_capacity = burst_capacity
            self._refill_tokens()
    
    def enable(self) -> None:
        """启用速率限制"""
        with self.lock:
            self.config.enabled = True
            self._refill_tokens()
    
    def disable(self) -> None:
        """禁用速率限制"""
        with self.lock:
            self.config.enabled = False
    
    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        with self.lock:
            self._refill_tokens()
            return {
                'enabled': self.config.enabled,
                'max_requests_per_second': self.config.max_requests_per_second,
                'burst_capacity': self.config.burst_capacity,
                'current_tokens': self.tokens,
                'available_tokens': self.tokens,
                'wait_time_for_one': self.get_wait_time(1)
            }


class RateLimitedSession:
    """带速率限制的请求会话"""
    
    def __init__(self, session, rate_limiter: RateLimiter):
        """
        初始化带限速的会话
        
        Args:
            session: 原始的requests.Session对象
            rate_limiter: 速率限制器实例
        """
        self.session = session
        self.rate_limiter = rate_limiter
        self.logger = logging.getLogger(__name__)
    
    def __getattr__(self, name):
        """代理所有其他属性和方法到原始session"""
        return getattr(self.session, name)
    
    def request(self, method, url, **kwargs):
        """发送带速率限制的请求"""
        if not self.rate_limiter.config.fast_mode:
            self.rate_limiter.wait()
        return self.session.request(method, url, **kwargs)
    
    def get(self, url, **kwargs):
        """发送GET请求"""
        self.rate_limiter.wait()
        return self.session.get(url, **kwargs)
    
    def post(self, url, **kwargs):
        """发送POST请求"""
        self.rate_limiter.wait()
        return self.session.post(url, **kwargs)
    
    def head(self, url, **kwargs):
        """发送HEAD请求"""
        self.rate_limiter.wait()
        return self.session.head(url, **kwargs)
    
    def put(self, url, **kwargs):
        """发送PUT请求"""
        self.rate_limiter.wait()
        return self.session.put(url, **kwargs)
    
    def delete(self, url, **kwargs):
        """发送DELETE请求"""
        self.rate_limiter.wait()
        return self.session.delete(url, **kwargs)
    
    def patch(self, url, **kwargs):
        """发送PATCH请求"""
        self.rate_limiter.wait()
        return self.session.patch(url, **kwargs)


# 全局速率限制器实例
_global_rate_limiter: Optional[RateLimiter] = None

def get_global_rate_limiter() -> RateLimiter:
    """获取全局速率限制器"""
    global _global_rate_limiter
    if _global_rate_limiter is None:
        config = RateLimitConfig(
            max_requests_per_second=10.0,  # 更宽松的默认限制
            burst_capacity=20,
            enabled=True,
            fast_mode=False
        )
        _global_rate_limiter = RateLimiter(config)
    return _global_rate_limiter

def set_global_rate_limit(max_requests_per_second: float, burst_capacity: Optional[int] = None) -> None:
    """设置全局速率限制"""
    limiter = get_global_rate_limiter()
    limiter.set_rate(max_requests_per_second, burst_capacity)

def enable_global_rate_limit() -> None:
    """启用全局速率限制"""
    limiter = get_global_rate_limiter()
    limiter.enable()

def disable_global_rate_limit() -> None:
    """禁用全局速率限制"""
    limiter = get_global_rate_limiter()
    limiter.disable()

def get_global_rate_limit_status() -> Dict[str, Any]:
    """获取全局速率限制状态"""
    limiter = get_global_rate_limiter()
    return limiter.get_status()
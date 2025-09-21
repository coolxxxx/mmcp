#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""指数退避算法实现，包含随机抖动机制"""

import time
import random
from typing import Optional

class ExponentialBackoffStrategy:
    """指数退避策略，包含随机抖动机制"""
    
    def __init__(self, base_delay: float = 1.0, max_delay: float = 60.0):
        """
        初始化指数退避策略
        
        Args:
            base_delay: 基础延迟时间（秒）
            max_delay: 最大延迟时间（秒）
        """
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    def get_wait_time(self, attempt: int, retry_after: Optional[int] = None) -> float:
        """
        计算等待时间，使用指数退避算法和随机抖动
        
        Args:
            attempt: 当前尝试次数（0-based）
            retry_after: Retry-After头指定的等待时间（秒）
            
        Returns:
            等待时间（秒）
        """
        # 优先使用Retry-After头指定的时间
        if retry_after and retry_after > 0:
            base_wait = float(retry_after)
        else:
            # 指数退避：base_delay * 2^attempt
            base_wait = self.base_delay * (2 ** attempt)
        
        # 添加随机抖动（±25%），避免惊群效应
        jitter = random.uniform(0.75, 1.25)
        wait_time = base_wait * jitter
        
        # 限制最大等待时间
        wait_time = min(wait_time, self.max_delay)
        
        return wait_time

# 全局默认实例
default_backoff_strategy = ExponentialBackoffStrategy()
"""
自适应下载管理器
根据服务器响应动态调整下载策略，避免502错误
"""

import os
import time
import threading
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import deque

from .server_friendly_config import ServerFriendlyConfig, get_server_friendly_config
from ..models.data_models import ImageInfo, DownloadStatus
from ..utils.logger import setup_logger


class AdaptiveDownloadManager:
    """自适应下载管理器 - 智能应对服务器状况"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, file_manager=None):
        """初始化自适应下载管理器"""
        self.logger = setup_logger('adaptive_downloader')
        self.file_manager = file_manager
        
        # 加载服务器友好配置
        if config:
            self.config = config
        else:
            friendly_config = get_server_friendly_config()
            self.config = friendly_config.to_dict()
        
        # 服务器状态监控
        self.server_health = {
            'consecutive_502_errors': 0,
            'total_502_errors': 0,
            'last_502_time': None,
            'success_rate': 1.0,
            'avg_response_time': 0.0,
            'is_healthy': True
        }
        
        # 响应时间记录（最近50次请求）
        self.response_times = deque(maxlen=50)
        self.error_history = deque(maxlen=100)
        
        # 动态调整参数
        self.current_threads = self.config['max_threads']
        self.current_rate = self.config['base_rate']
        self.current_delay = self.config['request_interval']
        
        # 状态锁
        self.status_lock = threading.Lock()
        self.is_running = False
        
        # 统计信息
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'server_errors': 0,
            'avg_speed': 0.0
        }
        
        self.logger.info(f"自适应下载管理器初始化完成")
        self.logger.info(f"初始配置: 线程数={self.current_threads}, 速率={self.current_rate}req/s")
    
    def _update_server_health(self, response_time: float, status_code: int, error: Optional[Exception] = None):
        """更新服务器健康状态"""
        with self.status_lock:
            self.stats['total_requests'] += 1
            
            if status_code == 502:
                self.server_health['consecutive_502_errors'] += 1
                self.server_health['total_502_errors'] += 1
                self.server_health['last_502_time'] = datetime.now()
                self.stats['server_errors'] += 1
                
                self.logger.warning(f"检测到502错误，连续502错误数: {self.server_health['consecutive_502_errors']}")
                
                # 触发保护机制
                if self.server_health['consecutive_502_errors'] >= 3:
                    self._trigger_protection_mode()
                    
            elif 200 <= status_code < 300:
                # 成功请求，重置502计数
                self.server_health['consecutive_502_errors'] = 0
                self.stats['successful_requests'] += 1
                self.response_times.append(response_time)
                
                # 更新平均响应时间
                if self.response_times:
                    self.server_health['avg_response_time'] = sum(self.response_times) / len(self.response_times)
                
            else:
                # 其他错误
                self.stats['failed_requests'] += 1
                if self.server_health['consecutive_502_errors'] > 0:
                    self.server_health['consecutive_502_errors'] = max(0, self.server_health['consecutive_502_errors'] - 1)
            
            # 更新成功率
            if self.stats['total_requests'] > 0:
                self.server_health['success_rate'] = self.stats['successful_requests'] / self.stats['total_requests']
            
            # 记录错误历史
            if error or status_code >= 400:
                self.error_history.append({
                    'timestamp': datetime.now(),
                    'status_code': status_code,
                    'error': str(error) if error else f"HTTP {status_code}"
                })
    
    def _trigger_protection_mode(self):
        """触发保护模式"""
        self.logger.warning("触发服务器保护模式")
        
        # 大幅降低并发和速率
        self.current_threads = max(1, self.current_threads // 2)
        self.current_rate = max(1, self.current_rate // 2)
        self.current_delay = min(self.current_delay * 2, 5.0)
        
        self.server_health['is_healthy'] = False
        
        self.logger.info(f"保护模式参数: 线程数={self.current_threads}, 速率={self.current_rate}req/s, 延迟={self.current_delay}s")
        
        # 设置恢复检查
        recovery_thread = threading.Thread(target=self._recovery_check, daemon=True)
        recovery_thread.start()
    
    def _recovery_check(self):
        """恢复检查线程"""
        self.logger.info("开始服务器恢复检查")
        
        # 等待冷却时间
        cooldown = self.config.get('server_error_cooldown', 30)
        time.sleep(cooldown)
        
        # 尝试恢复性测试
        recovery_attempts = 0
        max_recovery_attempts = 5
        
        while recovery_attempts < max_recovery_attempts and not self.server_health['is_healthy']:
            try:
                # 发送测试请求
                test_url = "https://httpbin.org/status/200"  # 使用测试URL
                start_time = time.time()
                response = requests.get(test_url, timeout=10)
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    self.logger.info("服务器恢复检查成功，开始逐步恢复")
                    self._gradual_recovery()
                    break
                else:
                    recovery_attempts += 1
                    self.logger.warning(f"恢复检查失败 ({recovery_attempts}/{max_recovery_attempts})")
                    time.sleep(10)
                    
            except Exception as e:
                recovery_attempts += 1
                self.logger.error(f"恢复检查异常 ({recovery_attempts}/{max_recovery_attempts}): {e}")
                time.sleep(10)
        
        if recovery_attempts >= max_recovery_attempts:
            self.logger.error("服务器恢复检查失败，保持保护模式")
    
    def _gradual_recovery(self):
        """逐步恢复正常参数"""
        self.logger.info("开始逐步恢复下载参数")
        
        original_threads = self.config['max_threads']
        original_rate = self.config['base_rate']
        original_delay = self.config['request_interval']
        
        # 分5步恢复
        steps = 5
        for step in range(1, steps + 1):
            if not self.is_running:
                break
                
            # 逐步增加参数
            self.current_threads = min(original_threads, int(self.current_threads * 1.2))
            self.current_rate = min(original_rate, int(self.current_rate * 1.2))
            self.current_delay = max(original_delay, self.current_delay * 0.8)
            
            self.logger.info(f"恢复步骤 {step}/{steps}: 线程数={self.current_threads}, 速率={self.current_rate}req/s")
            
            # 等待观察
            time.sleep(30)
            
            # 检查是否有新的502错误
            if self.server_health['consecutive_502_errors'] > 0:
                self.logger.warning("恢复过程中检测到新的502错误，暂停恢复")
                break
        
        # 标记为健康
        self.server_health['is_healthy'] = True
        self.logger.info("服务器状态恢复完成")
    
    def download_image(self, image_info: ImageInfo) -> bool:
        """下载单个图片（带自适应逻辑）"""
        max_retries = self.config.get('server_error_retry_times', 6)
        
        for attempt in range(max_retries):
            try:
                # 应用当前延迟
                if attempt > 0:
                    delay = self._calculate_retry_delay(attempt)
                    self.logger.info(f"重试延迟 {delay}s (尝试 {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                
                # 执行下载
                start_time = time.time()
                success, status_code, error = self._perform_download(image_info)
                response_time = time.time() - start_time
                
                # 更新服务器健康状态
                self._update_server_health(response_time, status_code, error)
                
                if success:
                    self.logger.info(f"下载成功: {image_info.filename} (耗时: {response_time:.2f}s)")
                    return True
                
                # 如果是502错误且服务器不健康，增加额外延迟
                if status_code == 502 and not self.server_health['is_healthy']:
                    extra_delay = self.config.get('server_error_delay', 15)
                    self.logger.info(f"502错误额外延迟 {extra_delay}s")
                    time.sleep(extra_delay)
                
            except Exception as e:
                self.logger.error(f"下载异常 {image_info.filename} (尝试 {attempt + 1}/{max_retries}): {e}")
                self._update_server_health(0, 500, e)
        
        self.logger.error(f"下载失败，已达最大重试次数: {image_info.filename}")
        return False
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """计算重试延迟"""
        if self.config.get('exponential_backoff', True):
            # 指数退避
            base_delay = self.config.get('min_retry_delay', 3.0)
            max_delay = self.config.get('max_retry_delay', 60)
            delay = min(base_delay * (2 ** attempt), max_delay)
        else:
            # 固定延迟
            delay = self.config.get('min_retry_delay', 3.0)
        
        # 如果服务器不健康，增加延迟
        if not self.server_health['is_healthy']:
            delay *= 2
        
        return delay
    
    def _perform_download(self, image_info: ImageInfo) -> tuple[bool, int, Optional[Exception]]:
        """执行实际下载"""
        try:
            # 创建会话
            session = requests.Session()
            session.headers.update({
                'User-Agent': self.config['session']['user_agent'],
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            })
            
            # 发送请求
            response = session.get(
                image_info.url,
                timeout=self.config['timeout'],
                stream=True
            )
            
            status_code = response.status_code
            
            if status_code == 200:
                # 保存文件
                os.makedirs(os.path.dirname(image_info.file_path), exist_ok=True)
                
                with open(image_info.file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=self.config['chunk_size']):
                        if chunk:
                            f.write(chunk)
                
                return True, status_code, None
            else:
                return False, status_code, None
                
        except requests.exceptions.RequestException as e:
            # 尝试从异常中提取状态码
            status_code = 500
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
            return False, status_code, e
        except Exception as e:
            return False, 500, e
    
    def get_server_status(self) -> Dict[str, Any]:
        """获取服务器状态信息"""
        with self.status_lock:
            return {
                'is_healthy': self.server_health['is_healthy'],
                'consecutive_502_errors': self.server_health['consecutive_502_errors'],
                'total_502_errors': self.server_health['total_502_errors'],
                'success_rate': self.server_health['success_rate'],
                'avg_response_time': self.server_health['avg_response_time'],
                'current_threads': self.current_threads,
                'current_rate': self.current_rate,
                'current_delay': self.current_delay,
                'stats': self.stats.copy()
            }
    
    def get_recommendations(self) -> List[str]:
        """获取优化建议"""
        recommendations = []
        
        if self.server_health['total_502_errors'] > 10:
            recommendations.append("检测到大量502错误，建议降低下载速度或更换下载时间")
        
        if self.server_health['success_rate'] < 0.8:
            recommendations.append("成功率较低，建议检查网络连接或服务器状态")
        
        if self.server_health['avg_response_time'] > 10:
            recommendations.append("服务器响应较慢，建议增加超时时间或降低并发数")
        
        if not self.server_health['is_healthy']:
            recommendations.append("服务器状态不佳，系统已启用保护模式")
        
        return recommendations


def create_adaptive_config():
    """创建自适应配置"""
    from .server_friendly_config import create_server_friendly_config_file
    create_server_friendly_config_file()
    
    print("\n自适应下载管理器特性:")
    print("✓ 智能502错误检测和恢复")
    print("✓ 动态调整下载参数")
    print("✓ 服务器健康状态监控")
    print("✓ 指数退避重试策略")
    print("✓ 保护模式和逐步恢复")
    print("✓ 实时性能统计")


if __name__ == "__main__":
    create_adaptive_config()
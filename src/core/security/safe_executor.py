"""
安全执行器
提供安全的系统调用和文件操作
"""

import os
import subprocess
import tempfile
import shutil
from typing import Dict, List, Any, Optional, Union, Callable
from pathlib import Path
from dataclasses import dataclass
from contextlib import contextmanager
import logging
import signal
import threading
import time

from ..exceptions import SecurityError, TimeoutError as AppTimeoutError


@dataclass
class ExecutionContext:
    """执行上下文"""
    working_directory: Optional[str] = None
    environment_vars: Optional[Dict[str, str]] = None
    timeout_seconds: Optional[int] = None
    allowed_commands: Optional[List[str]] = None
    blocked_commands: Optional[List[str]] = None
    max_memory_mb: Optional[int] = None
    user_id: Optional[str] = None


class SafeExecutor:
    """安全执行器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._init_security_settings()
    
    def _init_security_settings(self):
        """初始化安全设置"""
        # 默认阻止的危险命令
        self.default_blocked_commands = [
            'rm', 'del', 'rmdir', 'rd',
            'format', 'fdisk', 'mkfs',
            'dd', 'shred', 'wipe',
            'chmod', 'chown', 'chgrp',
            'sudo', 'su', 'runas',
            'nc', 'netcat', 'telnet',
            'wget', 'curl', 'ftp',
            'python', 'python3', 'perl', 'ruby', 'php',
            'powershell', 'cmd', 'bash', 'sh',
            'reg', 'regedit', 'sc', 'net',
            'taskkill', 'kill', 'killall'
        ]
        
        # 默认允许的安全命令
        self.default_allowed_commands = [
            'echo', 'cat', 'type', 'dir', 'ls',
            'find', 'grep', 'head', 'tail',
            'sort', 'uniq', 'wc', 'cut',
            'explorer', 'open', 'xdg-open'
        ]
    
    def execute_command(self, command: Union[str, List[str]], 
                       context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """
        安全执行命令
        
        Args:
            command: 要执行的命令
            context: 执行上下文
            
        Returns:
            执行结果
        """
        if context is None:
            context = ExecutionContext()
        
        try:
            # 验证命令安全性
            self._validate_command(command, context)
            
            # 准备执行环境
            env = self._prepare_environment(context)
            cwd = context.working_directory or os.getcwd()
            timeout = context.timeout_seconds or 30
            
            # 执行命令
            if isinstance(command, str):
                cmd_list = command.split()
            else:
                cmd_list = command
            
            start_time = time.time()
            
            try:
                result = subprocess.run(
                    cmd_list,
                    cwd=cwd,
                    env=env,
                    timeout=timeout,
                    capture_output=True,
                    text=True,
                    shell=False  # 永远不使用shell
                )
                
                execution_time = time.time() - start_time
                
                return {
                    'success': True,
                    'return_code': result.returncode,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'execution_time': execution_time,
                    'command': ' '.join(cmd_list) if isinstance(cmd_list, list) else cmd_list
                }
                
            except subprocess.TimeoutExpired:
                raise AppTimeoutError(f"命令执行超时 ({timeout}秒): {command}")
            except subprocess.CalledProcessError as e:
                return {
                    'success': False,
                    'return_code': e.returncode,
                    'stdout': e.stdout or '',
                    'stderr': e.stderr or '',
                    'execution_time': time.time() - start_time,
                    'command': ' '.join(cmd_list) if isinstance(cmd_list, list) else cmd_list,
                    'error': str(e)
                }
                
        except Exception as e:
            self.logger.error(f"命令执行失败: {e}")
            raise SecurityError(f"命令执行失败: {e}")
    
    def _validate_command(self, command: Union[str, List[str]], 
                         context: ExecutionContext):
        """验证命令安全性"""
        if isinstance(command, str):
            cmd_parts = command.split()
        else:
            cmd_parts = command
        
        if not cmd_parts:
            raise SecurityError("命令不能为空")
        
        base_command = cmd_parts[0].lower()
        
        # 检查阻止的命令
        blocked_commands = context.blocked_commands or self.default_blocked_commands
        if base_command in blocked_commands:
            raise SecurityError(f"命令被阻止: {base_command}")
        
        # 检查允许的命令（如果指定了允许列表）
        if context.allowed_commands:
            if base_command not in context.allowed_commands:
                raise SecurityError(f"命令不在允许列表中: {base_command}")
        
        # 检查危险模式
        full_command = ' '.join(cmd_parts) if isinstance(cmd_parts, list) else command
        dangerous_patterns = [
            r';\s*rm\s',
            r';\s*del\s',
            r'\|\s*rm\s',
            r'&&\s*rm\s',
            r'`.*`',
            r'\$\(.*\)',
            r'>\s*/dev/',
            r'>\s*CON',
            r'>\s*NUL'
        ]
        
        import re
        for pattern in dangerous_patterns:
            if re.search(pattern, full_command, re.IGNORECASE):
                raise SecurityError(f"命令包含危险模式: {pattern}")
    
    def _prepare_environment(self, context: ExecutionContext) -> Dict[str, str]:
        """准备执行环境"""
        env = os.environ.copy()
        
        # 移除潜在危险的环境变量
        dangerous_vars = [
            'LD_PRELOAD', 'LD_LIBRARY_PATH',
            'PYTHONPATH', 'PATH'  # 可能需要根据需求调整
        ]
        
        for var in dangerous_vars:
            env.pop(var, None)
        
        # 添加自定义环境变量
        if context.environment_vars:
            for key, value in context.environment_vars.items():
                # 验证环境变量安全性
                if self._is_safe_env_var(key, value):
                    env[key] = value
                else:
                    self.logger.warning(f"跳过不安全的环境变量: {key}")
        
        return env
    
    def _is_safe_env_var(self, key: str, value: str) -> bool:
        """检查环境变量是否安全"""
        # 检查键名
        if not key.replace('_', '').replace('-', '').isalnum():
            return False
        
        # 检查值中的危险模式
        dangerous_patterns = [
            r';\s*rm\s',
            r'`.*`',
            r'\$\(.*\)',
            r'\.\./',
            r'/etc/',
            r'/proc/',
            r'C:\\Windows\\'
        ]
        
        import re
        for pattern in dangerous_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return False
        
        return True
    
    @contextmanager
    def safe_file_operation(self, file_path: str, mode: str = 'r', 
                           encoding: str = 'utf-8'):
        """
        安全文件操作上下文管理器
        
        Args:
            file_path: 文件路径
            mode: 打开模式
            encoding: 编码
        """
        # 验证文件路径安全性
        self._validate_file_path(file_path, mode)
        
        file_handle = None
        try:
            file_handle = open(file_path, mode, encoding=encoding)
            yield file_handle
        except Exception as e:
            self.logger.error(f"文件操作失败: {e}")
            raise SecurityError(f"文件操作失败: {e}")
        finally:
            if file_handle:
                file_handle.close()
    
    def _validate_file_path(self, file_path: str, mode: str):
        """验证文件路径安全性"""
        from .input_validator import validate_file_path, ValidationLevel
        
        result = validate_file_path(file_path, ValidationLevel.STRICT)
        if not result['valid']:
            raise SecurityError(f"文件路径不安全: {', '.join(result['errors'])}")
        
        # 检查写入权限
        if 'w' in mode or 'a' in mode:
            # 确保不是系统关键文件
            system_files = [
                '/etc/passwd', '/etc/shadow', '/etc/hosts',
                'C:\\Windows\\System32\\drivers\\etc\\hosts',
                'C:\\Windows\\System32\\config\\SAM'
            ]
            
            normalized_path = os.path.normpath(file_path)
            for sys_file in system_files:
                if normalized_path.lower() == sys_file.lower():
                    raise SecurityError(f"不允许修改系统文件: {file_path}")
    
    def safe_network_request(self, url: str, method: str = 'GET', 
                           headers: Optional[Dict[str, str]] = None,
                           data: Optional[Any] = None,
                           timeout: int = 30) -> Dict[str, Any]:
        """
        安全网络请求
        
        Args:
            url: 请求URL
            method: HTTP方法
            headers: 请求头
            data: 请求数据
            timeout: 超时时间
            
        Returns:
            请求结果
        """
        try:
            # 验证URL安全性
            from .input_validator import validate_url, ValidationLevel
            
            result = validate_url(url, ValidationLevel.STRICT)
            if not result['valid']:
                raise SecurityError(f"URL不安全: {', '.join(result['errors'])}")
            
            import requests
            
            # 安全的请求配置
            session = requests.Session()
            
            # 设置安全头
            safe_headers = {
                'User-Agent': 'SafeExecutor/1.0',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'close'  # 避免连接重用
            }
            
            if headers:
                # 验证自定义头的安全性
                for key, value in headers.items():
                    if self._is_safe_header(key, value):
                        safe_headers[key] = value
                    else:
                        self.logger.warning(f"跳过不安全的请求头: {key}")
            
            # 执行请求
            response = session.request(
                method=method.upper(),
                url=url,
                headers=safe_headers,
                data=data,
                timeout=timeout,
                verify=True,  # 始终验证SSL证书
                allow_redirects=False  # 不自动跟随重定向
            )
            
            return {
                'success': True,
                'status_code': response.status_code,
                'headers': dict(response.headers),
                'content': response.content,
                'text': response.text,
                'url': response.url
            }
            
        except requests.exceptions.Timeout:
            raise AppTimeoutError(f"网络请求超时: {url}")
        except requests.exceptions.RequestException as e:
            raise SecurityError(f"网络请求失败: {e}")
        except Exception as e:
            self.logger.error(f"网络请求执行失败: {e}")
            raise SecurityError(f"网络请求执行失败: {e}")
    
    def _is_safe_header(self, key: str, value: str) -> bool:
        """检查请求头是否安全"""
        # 危险的请求头
        dangerous_headers = [
            'authorization', 'cookie', 'x-forwarded-for',
            'x-real-ip', 'x-originating-ip'
        ]
        
        if key.lower() in dangerous_headers:
            return False
        
        # 检查值中的危险模式
        dangerous_patterns = [
            r'<script',
            r'javascript:',
            r'vbscript:',
            r'data:',
            r'eval\(',
            r'exec\('
        ]
        
        import re
        for pattern in dangerous_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return False
        
        return True
    
    def create_secure_temp_dir(self, prefix: str = 'safe_exec_') -> str:
        """创建安全的临时目录"""
        try:
            temp_dir = tempfile.mkdtemp(prefix=prefix)
            
            # 设置安全权限 (仅所有者可访问)
            os.chmod(temp_dir, 0o700)
            
            self.logger.info(f"创建安全临时目录: {temp_dir}")
            return temp_dir
            
        except Exception as e:
            raise SecurityError(f"创建临时目录失败: {e}")
    
    def cleanup_temp_dir(self, temp_dir: str):
        """清理临时目录"""
        try:
            if os.path.exists(temp_dir) and os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir)
                self.logger.info(f"清理临时目录: {temp_dir}")
        except Exception as e:
            self.logger.warning(f"清理临时目录失败: {e}")


# 便捷函数
def safe_subprocess_call(command: Union[str, List[str]], 
                        timeout: int = 30,
                        allowed_commands: Optional[List[str]] = None) -> Dict[str, Any]:
    """安全子进程调用的便捷函数"""
    executor = SafeExecutor()
    context = ExecutionContext(
        timeout_seconds=timeout,
        allowed_commands=allowed_commands
    )
    return executor.execute_command(command, context)


def safe_file_operation(file_path: str, mode: str = 'r', encoding: str = 'utf-8'):
    """安全文件操作的便捷函数"""
    executor = SafeExecutor()
    return executor.safe_file_operation(file_path, mode, encoding)


def safe_network_request(url: str, method: str = 'GET', 
                        headers: Optional[Dict[str, str]] = None,
                        timeout: int = 30) -> Dict[str, Any]:
    """安全网络请求的便捷函数"""
    executor = SafeExecutor()
    return executor.safe_network_request(url, method, headers, timeout=timeout)
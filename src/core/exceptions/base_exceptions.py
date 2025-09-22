"""
基础异常类定义
定义应用程序中使用的所有自定义异常类
"""

from typing import Dict, Any, Optional, List
import traceback
import time


class BaseApplicationException(Exception):
    """应用程序基础异常类"""
    
    def __init__(self, message: str, error_code: str = None, 
                 details: Dict[str, Any] = None, cause: Exception = None):
        """
        初始化基础异常
        
        Args:
            message: 错误消息
            error_code: 错误代码
            details: 错误详细信息
            cause: 原始异常
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.cause = cause
        self.timestamp = time.time()
        self.traceback_info = traceback.format_exc() if cause else None
        
        # 如果有原始异常，链接它
        if cause:
            self.__cause__ = cause
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'error_type': self.__class__.__name__,
            'error_code': self.error_code,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp,
            'traceback': self.traceback_info,
            'cause': str(self.cause) if self.cause else None
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        base_msg = f"[{self.error_code}] {self.message}"
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            base_msg += f" ({details_str})"
        return base_msg


class ValidationError(BaseApplicationException):
    """数据验证错误"""
    
    def __init__(self, message: str, field: str = None, value: Any = None, 
                 validation_rules: List[str] = None, **kwargs):
        """
        初始化验证错误
        
        Args:
            message: 错误消息
            field: 验证失败的字段
            value: 验证失败的值
            validation_rules: 违反的验证规则
        """
        details = kwargs.get('details', {})
        if field:
            details['field'] = field
        if value is not None:
            details['value'] = str(value)
        if validation_rules:
            details['validation_rules'] = validation_rules
        
        super().__init__(message, 'VALIDATION_ERROR', details, kwargs.get('cause'))


class ConfigurationError(BaseApplicationException):
    """配置错误"""
    
    def __init__(self, message: str, config_key: str = None, 
                 config_file: str = None, **kwargs):
        """
        初始化配置错误
        
        Args:
            message: 错误消息
            config_key: 配置键
            config_file: 配置文件路径
        """
        details = kwargs.get('details', {})
        if config_key:
            details['config_key'] = config_key
        if config_file:
            details['config_file'] = config_file
        
        super().__init__(message, 'CONFIG_ERROR', details, kwargs.get('cause'))


class ResourceError(BaseApplicationException):
    """资源错误"""
    
    def __init__(self, message: str, resource_type: str = None, 
                 resource_id: str = None, **kwargs):
        """
        初始化资源错误
        
        Args:
            message: 错误消息
            resource_type: 资源类型
            resource_id: 资源ID
        """
        details = kwargs.get('details', {})
        if resource_type:
            details['resource_type'] = resource_type
        if resource_id:
            details['resource_id'] = resource_id
        
        super().__init__(message, 'RESOURCE_ERROR', details, kwargs.get('cause'))


class NetworkError(BaseApplicationException):
    """网络错误"""
    
    def __init__(self, message: str, url: str = None, status_code: int = None,
                 response_body: str = None, **kwargs):
        """
        初始化网络错误
        
        Args:
            message: 错误消息
            url: 请求URL
            status_code: HTTP状态码
            response_body: 响应体
        """
        details = kwargs.get('details', {})
        if url:
            details['url'] = url
        if status_code:
            details['status_code'] = status_code
        if response_body:
            details['response_body'] = response_body[:1000]  # 限制长度
        
        super().__init__(message, 'NETWORK_ERROR', details, kwargs.get('cause'))


class FileSystemError(BaseApplicationException):
    """文件系统错误"""
    
    def __init__(self, message: str, file_path: str = None, 
                 operation: str = None, **kwargs):
        """
        初始化文件系统错误
        
        Args:
            message: 错误消息
            file_path: 文件路径
            operation: 操作类型
        """
        details = kwargs.get('details', {})
        if file_path:
            details['file_path'] = file_path
        if operation:
            details['operation'] = operation
        
        super().__init__(message, 'FILESYSTEM_ERROR', details, kwargs.get('cause'))


class ParsingError(BaseApplicationException):
    """解析错误"""
    
    def __init__(self, message: str, content_type: str = None, 
                 parser_type: str = None, line_number: int = None, **kwargs):
        """
        初始化解析错误
        
        Args:
            message: 错误消息
            content_type: 内容类型
            parser_type: 解析器类型
            line_number: 错误行号
        """
        details = kwargs.get('details', {})
        if content_type:
            details['content_type'] = content_type
        if parser_type:
            details['parser_type'] = parser_type
        if line_number:
            details['line_number'] = line_number
        
        super().__init__(message, 'PARSING_ERROR', details, kwargs.get('cause'))


class AuthenticationError(BaseApplicationException):
    """认证错误"""
    
    def __init__(self, message: str, auth_method: str = None, 
                 user_id: str = None, **kwargs):
        """
        初始化认证错误
        
        Args:
            message: 错误消息
            auth_method: 认证方法
            user_id: 用户ID
        """
        details = kwargs.get('details', {})
        if auth_method:
            details['auth_method'] = auth_method
        if user_id:
            details['user_id'] = user_id
        
        super().__init__(message, 'AUTH_ERROR', details, kwargs.get('cause'))


class PermissionError(BaseApplicationException):
    """权限错误"""
    
    def __init__(self, message: str, required_permission: str = None, 
                 user_id: str = None, resource: str = None, **kwargs):
        """
        初始化权限错误
        
        Args:
            message: 错误消息
            required_permission: 需要的权限
            user_id: 用户ID
            resource: 资源
        """
        details = kwargs.get('details', {})
        if required_permission:
            details['required_permission'] = required_permission
        if user_id:
            details['user_id'] = user_id
        if resource:
            details['resource'] = resource
        
        super().__init__(message, 'PERMISSION_ERROR', details, kwargs.get('cause'))


class TimeoutError(BaseApplicationException):
    """超时错误"""
    
    def __init__(self, message: str, timeout_duration: float = None, 
                 operation: str = None, **kwargs):
        """
        初始化超时错误
        
        Args:
            message: 错误消息
            timeout_duration: 超时时长
            operation: 操作类型
        """
        details = kwargs.get('details', {})
        if timeout_duration:
            details['timeout_duration'] = timeout_duration
        if operation:
            details['operation'] = operation
        
        super().__init__(message, 'TIMEOUT_ERROR', details, kwargs.get('cause'))


class ConcurrencyError(BaseApplicationException):
    """并发错误"""
    
    def __init__(self, message: str, thread_id: str = None, 
                 lock_name: str = None, **kwargs):
        """
        初始化并发错误
        
        Args:
            message: 错误消息
            thread_id: 线程ID
            lock_name: 锁名称
        """
        details = kwargs.get('details', {})
        if thread_id:
            details['thread_id'] = thread_id
        if lock_name:
            details['lock_name'] = lock_name
        
        super().__init__(message, 'CONCURRENCY_ERROR', details, kwargs.get('cause'))


class DataIntegrityError(BaseApplicationException):
    """数据完整性错误"""
    
    def __init__(self, message: str, data_type: str = None, 
                 expected_checksum: str = None, actual_checksum: str = None, **kwargs):
        """
        初始化数据完整性错误
        
        Args:
            message: 错误消息
            data_type: 数据类型
            expected_checksum: 期望的校验和
            actual_checksum: 实际的校验和
        """
        details = kwargs.get('details', {})
        if data_type:
            details['data_type'] = data_type
        if expected_checksum:
            details['expected_checksum'] = expected_checksum
        if actual_checksum:
            details['actual_checksum'] = actual_checksum
        
        super().__init__(message, 'DATA_INTEGRITY_ERROR', details, kwargs.get('cause'))


class SecurityError(BaseApplicationException):
    """安全错误"""
    
    def __init__(self, message: str, security_type: str = None, 
                 threat_level: str = None, **kwargs):
        """
        初始化安全错误
        
        Args:
            message: 错误消息
            security_type: 安全类型
            threat_level: 威胁级别
        """
        details = kwargs.get('details', {})
        if security_type:
            details['security_type'] = security_type
        if threat_level:
            details['threat_level'] = threat_level
        
        super().__init__(message, 'SECURITY_ERROR', details, kwargs.get('cause'))


# 异常映射字典，用于根据错误类型创建相应的异常
EXCEPTION_MAPPING = {
    'validation': ValidationError,
    'config': ConfigurationError,
    'resource': ResourceError,
    'network': NetworkError,
    'filesystem': FileSystemError,
    'parsing': ParsingError,
    'auth': AuthenticationError,
    'permission': PermissionError,
    'timeout': TimeoutError,
    'concurrency': ConcurrencyError,
    'data_integrity': DataIntegrityError,
    'security': SecurityError,
}


def create_exception(exception_type: str, message: str, **kwargs) -> BaseApplicationException:
    """
    根据异常类型创建相应的异常实例
    
    Args:
        exception_type: 异常类型
        message: 错误消息
        **kwargs: 其他参数
        
    Returns:
        异常实例
    """
    exception_class = EXCEPTION_MAPPING.get(exception_type, BaseApplicationException)
    return exception_class(message, **kwargs)
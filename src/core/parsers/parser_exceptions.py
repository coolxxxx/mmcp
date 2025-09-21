"""
解析器异常类定义
"""


class ParserError(Exception):
    """解析器基础异常类"""
    
    def __init__(self, message: str, error_code: str = None, context: dict = None):
        """
        初始化异常
        
        Args:
            message: 错误消息
            error_code: 错误代码
            context: 错误上下文信息
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "PARSER_ERROR"
        self.context = context or {}
    
    def __str__(self):
        return f"[{self.error_code}] {self.message}"


class NetworkError(ParserError):
    """网络相关错误"""
    
    def __init__(self, message: str, url: str = None, status_code: int = None):
        super().__init__(message, "NETWORK_ERROR")
        self.url = url
        self.status_code = status_code
        self.context = {
            "url": url,
            "status_code": status_code
        }


class ParseError(ParserError):
    """解析相关错误"""
    
    def __init__(self, message: str, parser_type: str = None, content_type: str = None):
        super().__init__(message, "PARSE_ERROR")
        self.parser_type = parser_type
        self.content_type = content_type
        self.context = {
            "parser_type": parser_type,
            "content_type": content_type
        }


class FilterError(ParserError):
    """过滤相关错误"""
    
    def __init__(self, message: str, filter_type: str = None, filter_params: dict = None):
        super().__init__(message, "FILTER_ERROR")
        self.filter_type = filter_type
        self.filter_params = filter_params or {}
        self.context = {
            "filter_type": filter_type,
            "filter_params": filter_params
        }


class ValidationError(ParserError):
    """验证相关错误"""
    
    def __init__(self, message: str, field: str = None, value: any = None):
        super().__init__(message, "VALIDATION_ERROR")
        self.field = field
        self.value = value
        self.context = {
            "field": field,
            "value": str(value) if value is not None else None
        }


class ConfigurationError(ParserError):
    """配置相关错误"""
    
    def __init__(self, message: str, config_key: str = None, config_value: any = None):
        super().__init__(message, "CONFIG_ERROR")
        self.config_key = config_key
        self.config_value = config_value
        self.context = {
            "config_key": config_key,
            "config_value": str(config_value) if config_value is not None else None
        }


class TimeoutError(ParserError):
    """超时错误"""
    
    def __init__(self, message: str, timeout_seconds: float = None, operation: str = None):
        super().__init__(message, "TIMEOUT_ERROR")
        self.timeout_seconds = timeout_seconds
        self.operation = operation
        self.context = {
            "timeout_seconds": timeout_seconds,
            "operation": operation
        }


class ResourceError(ParserError):
    """资源相关错误"""
    
    def __init__(self, message: str, resource_type: str = None, resource_id: str = None):
        super().__init__(message, "RESOURCE_ERROR")
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.context = {
            "resource_type": resource_type,
            "resource_id": resource_id
        }
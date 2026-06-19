"""
统一异常处理模块
提供完整的异常定义、处理和管理功能
"""

# 导入基础异常类
try:
    from .base_exceptions import (
        BaseApplicationException,
        ValidationError,
        ConfigurationError,
        ResourceError,
        NetworkError,
        FileSystemError,
        ParsingError,
        AuthenticationError,
        PermissionError as AppPermissionError,
        TimeoutError,
        TimeoutError as AppTimeoutError,
        ConcurrencyError,
        DataIntegrityError,
        SecurityError,
        create_exception
    )
    _base_exceptions_available = True
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"基础异常类导入失败: {e}")
    _base_exceptions_available = False

# 导入错误处理器
try:
    from .error_handler import (
        ErrorHandler,
        ErrorContext,
        ErrorSeverity,
        RetryPolicy,
        get_global_error_handler,
        handle_error,
        execute_with_retry
    )
    _error_handler_available = True
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"错误处理器导入失败: {e}")
    _error_handler_available = False

# 导入错误报告器
try:
    from .error_reporter import (
        ErrorReporter,
        ErrorReport,
        ReportLevel,
        get_global_error_reporter,
        report_error
    )
    _error_reporter_available = True
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"错误报告器导入失败: {e}")
    _error_reporter_available = False

# 导入装饰器
try:
    from .decorators import (
        handle_exceptions,
        retry_on_failure,
        log_exceptions,
        validate_input,
        timeout_handler,
        robust_operation
    )
    _decorators_available = True
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"装饰器导入失败: {e}")
    _decorators_available = False

# 构建导出列表
__all__ = []

if _base_exceptions_available:
    __all__.extend([
        'BaseApplicationException',
        'ValidationError',
        'ConfigurationError',
        'ResourceError',
        'NetworkError',
        'FileSystemError',
        'ParsingError',
        'AuthenticationError',
        'AppPermissionError',
        'TimeoutError',
        'AppTimeoutError',
        'ConcurrencyError',
        'DataIntegrityError',
        'SecurityError',
        'create_exception'
    ])

if _error_handler_available:
    __all__.extend([
        'ErrorHandler',
        'ErrorContext',
        'ErrorSeverity',
        'RetryPolicy',
        'get_global_error_handler',
        'handle_error',
        'execute_with_retry'
    ])

if _error_reporter_available:
    __all__.extend([
        'ErrorReporter',
        'ErrorReport',
        'ReportLevel',
        'get_global_error_reporter',
        'report_error'
    ])

if _decorators_available:
    __all__.extend([
        'handle_exceptions',
        'retry_on_failure',
        'log_exceptions',
        'validate_input',
        'timeout_handler',
        'robust_operation'
    ])

# 记录可用模块
available_modules = []
if _base_exceptions_available:
    available_modules.append('base_exceptions')
if _error_handler_available:
    available_modules.append('error_handler')
if _error_reporter_available:
    available_modules.append('error_reporter')
if _decorators_available:
    available_modules.append('decorators')

import logging
logger = logging.getLogger(__name__)
logger.info(f"异常处理模块加载完成: {len(available_modules)}/4 个模块可用 ({', '.join(available_modules)})")

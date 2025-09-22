"""
安全模块
提供输入验证、安全检查和防护功能
"""

# 导入输入验证组件
try:
    from .input_validator import (
        InputValidator,
        ValidationRule,
        URLValidator,
        FilePathValidator,
        ImageValidator,
        ValidationLevel,
        validate_url,
        validate_file_path,
        validate_image_url,
        sanitize_filename,
        sanitize_url
    )
    _input_validator_available = True
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"输入验证器导入失败: {e}")
    _input_validator_available = False

# 导入安全检查组件
try:
    from .security_checker import (
        SecurityChecker,
        SecurityLevel,
        SecurityReport,
        SecurityIssue,
        check_url_security,
        check_file_security,
        scan_for_vulnerabilities
    )
    _security_checker_available = True
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"安全检查器导入失败: {e}")
    _security_checker_available = False

# 导入安全执行组件
try:
    from .safe_executor import (
        SafeExecutor,
        ExecutionContext,
        safe_subprocess_call,
        safe_file_operation,
        safe_network_request
    )
    _safe_executor_available = True
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"安全执行器导入失败: {e}")
    _safe_executor_available = False

# 导入加密工具组件
try:
    from .crypto_utils import (
        CryptoUtils,
        hash_string,
        generate_secure_token,
        encrypt_sensitive_data,
        decrypt_sensitive_data
    )
    _crypto_utils_available = True
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"加密工具导入失败: {e}")
    _crypto_utils_available = False

# 构建导出列表
__all__ = []

if _input_validator_available:
    __all__.extend([
        'InputValidator',
        'ValidationRule', 
        'URLValidator',
        'FilePathValidator',
        'ImageValidator',
        'ValidationLevel',
        'validate_url',
        'validate_file_path',
        'validate_image_url',
        'sanitize_filename',
        'sanitize_url'
    ])

if _security_checker_available:
    __all__.extend([
        'SecurityChecker',
        'SecurityLevel',
        'SecurityReport',
        'SecurityIssue',
        'check_url_security',
        'check_file_security',
        'scan_for_vulnerabilities'
    ])

if _safe_executor_available:
    __all__.extend([
        'SafeExecutor',
        'ExecutionContext',
        'safe_subprocess_call',
        'safe_file_operation',
        'safe_network_request'
    ])

if _crypto_utils_available:
    __all__.extend([
        'CryptoUtils',
        'hash_string',
        'generate_secure_token',
        'encrypt_sensitive_data',
        'decrypt_sensitive_data'
    ])

# 记录可用模块
available_modules = []
if _input_validator_available:
    available_modules.append('input_validator')
if _security_checker_available:
    available_modules.append('security_checker')
if _safe_executor_available:
    available_modules.append('safe_executor')
if _crypto_utils_available:
    available_modules.append('crypto_utils')

import logging
logger = logging.getLogger(__name__)
logger.info(f"安全模块加载完成: {len(available_modules)}/4 个模块可用 ({', '.join(available_modules)})")
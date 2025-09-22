"""
输入验证器
提供全面的输入验证和清理功能
"""

import re
import os
import urllib.parse
from typing import Dict, List, Any, Optional, Union, Callable, Pattern
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import logging

from ..exceptions import ValidationError


class ValidationLevel(Enum):
    """验证级别"""
    BASIC = "basic"
    STRICT = "strict"
    PARANOID = "paranoid"


@dataclass
class ValidationRule:
    """验证规则"""
    name: str
    validator: Callable[[Any], bool]
    error_message: str
    level: ValidationLevel = ValidationLevel.BASIC
    sanitizer: Optional[Callable[[Any], Any]] = None


class InputValidator:
    """输入验证器"""
    
    def __init__(self, level: ValidationLevel = ValidationLevel.STRICT):
        self.level = level
        self.logger = logging.getLogger(__name__)
        self._init_rules()
    
    def _init_rules(self):
        """初始化验证规则"""
        self.rules: Dict[str, List[ValidationRule]] = {
            'url': self._get_url_rules(),
            'file_path': self._get_file_path_rules(),
            'filename': self._get_filename_rules(),
            'image_url': self._get_image_url_rules(),
            'user_input': self._get_user_input_rules()
        }
    
    def _get_url_rules(self) -> List[ValidationRule]:
        """获取URL验证规则"""
        rules = [
            ValidationRule(
                name="protocol_check",
                validator=lambda url: isinstance(url, str) and url.startswith(('http://', 'https://')),
                error_message="URL必须以http://或https://开头"
            ),
            ValidationRule(
                name="length_check",
                validator=lambda url: len(url) <= 2048,
                error_message="URL长度不能超过2048字符"
            ),
            ValidationRule(
                name="format_check",
                validator=self._is_valid_url_format,
                error_message="URL格式无效"
            )
        ]
        
        if self.level in [ValidationLevel.STRICT, ValidationLevel.PARANOID]:
            rules.extend([
                ValidationRule(
                    name="domain_check",
                    validator=self._is_safe_domain,
                    error_message="域名不在允许列表中",
                    level=ValidationLevel.STRICT
                ),
                ValidationRule(
                    name="malicious_check",
                    validator=self._check_malicious_patterns,
                    error_message="URL包含可疑模式",
                    level=ValidationLevel.STRICT
                )
            ])
        
        if self.level == ValidationLevel.PARANOID:
            rules.append(
                ValidationRule(
                    name="ip_check",
                    validator=lambda url: not self._contains_ip_address(url),
                    error_message="不允许直接使用IP地址",
                    level=ValidationLevel.PARANOID
                )
            )
        
        return rules
    
    def _get_file_path_rules(self) -> List[ValidationRule]:
        """获取文件路径验证规则"""
        rules = [
            ValidationRule(
                name="path_traversal_check",
                validator=lambda path: not self._has_path_traversal(path),
                error_message="路径包含目录遍历攻击"
            ),
            ValidationRule(
                name="length_check",
                validator=lambda path: len(path) <= 260,  # Windows路径限制
                error_message="路径长度超过限制"
            ),
            ValidationRule(
                name="invalid_chars_check",
                validator=self._has_valid_path_chars,
                error_message="路径包含无效字符"
            )
        ]
        
        if self.level in [ValidationLevel.STRICT, ValidationLevel.PARANOID]:
            rules.extend([
                ValidationRule(
                    name="system_path_check",
                    validator=lambda path: not self._is_system_path(path),
                    error_message="不允许访问系统路径",
                    level=ValidationLevel.STRICT
                ),
                ValidationRule(
                    name="executable_check",
                    validator=lambda path: not self._is_executable_path(path),
                    error_message="不允许访问可执行文件路径",
                    level=ValidationLevel.STRICT
                )
            ])
        
        return rules
    
    def _get_filename_rules(self) -> List[ValidationRule]:
        """获取文件名验证规则"""
        rules = [
            ValidationRule(
                name="length_check",
                validator=lambda name: 1 <= len(name) <= 255,
                error_message="文件名长度必须在1-255字符之间"
            ),
            ValidationRule(
                name="invalid_chars_check",
                validator=self._has_valid_filename_chars,
                error_message="文件名包含无效字符"
            ),
            ValidationRule(
                name="reserved_names_check",
                validator=lambda name: not self._is_reserved_filename(name),
                error_message="文件名是系统保留名称"
            )
        ]
        
        if self.level in [ValidationLevel.STRICT, ValidationLevel.PARANOID]:
            rules.append(
                ValidationRule(
                    name="extension_check",
                    validator=self._has_safe_extension,
                    error_message="文件扩展名不安全",
                    level=ValidationLevel.STRICT
                )
            )
        
        return rules
    
    def _get_image_url_rules(self) -> List[ValidationRule]:
        """获取图片URL验证规则"""
        url_rules = self._get_url_rules()
        image_rules = [
            ValidationRule(
                name="image_extension_check",
                validator=self._has_image_extension,
                error_message="URL不是有效的图片格式"
            ),
            ValidationRule(
                name="size_limit_check",
                validator=lambda url: self._check_url_size_limit(url),
                error_message="图片URL可能指向过大的文件"
            )
        ]
        
        return url_rules + image_rules
    
    def _get_user_input_rules(self) -> List[ValidationRule]:
        """获取用户输入验证规则"""
        rules = [
            ValidationRule(
                name="xss_check",
                validator=lambda text: not self._contains_xss_patterns(text),
                error_message="输入包含XSS攻击模式"
            ),
            ValidationRule(
                name="sql_injection_check",
                validator=lambda text: not self._contains_sql_injection(text),
                error_message="输入包含SQL注入模式"
            ),
            ValidationRule(
                name="command_injection_check",
                validator=lambda text: not self._contains_command_injection(text),
                error_message="输入包含命令注入模式"
            )
        ]
        
        return rules
    
    def validate(self, value: Any, rule_type: str, **kwargs) -> Dict[str, Any]:
        """
        验证输入值
        
        Args:
            value: 要验证的值
            rule_type: 验证规则类型
            **kwargs: 额外参数
            
        Returns:
            验证结果字典
        """
        result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'sanitized_value': value
        }
        
        if rule_type not in self.rules:
            result['valid'] = False
            result['errors'].append(f"未知的验证规则类型: {rule_type}")
            return result
        
        rules = self.rules[rule_type]
        
        for rule in rules:
            # 检查规则级别
            if rule.level.value not in [self.level.value] and rule.level != ValidationLevel.BASIC:
                if self.level == ValidationLevel.BASIC and rule.level != ValidationLevel.BASIC:
                    continue
                elif self.level == ValidationLevel.STRICT and rule.level == ValidationLevel.PARANOID:
                    continue
            
            try:
                if not rule.validator(value):
                    result['valid'] = False
                    result['errors'].append(rule.error_message)
                    self.logger.warning(f"验证失败 [{rule.name}]: {rule.error_message}")
                
                # 应用清理器
                if rule.sanitizer and result['valid']:
                    result['sanitized_value'] = rule.sanitizer(result['sanitized_value'])
                    
            except Exception as e:
                result['valid'] = False
                result['errors'].append(f"验证规则 {rule.name} 执行失败: {str(e)}")
                self.logger.error(f"验证规则执行失败: {e}")
        
        return result
    
    def _is_valid_url_format(self, url: str) -> bool:
        """检查URL格式是否有效"""
        try:
            parsed = urllib.parse.urlparse(url)
            return all([parsed.scheme, parsed.netloc])
        except Exception:
            return False
    
    def _is_safe_domain(self, url: str) -> bool:
        """检查域名是否安全"""
        try:
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc.lower()
            
            # 允许的域名模式
            safe_patterns = [
                r'.*\.xiuren\..*',
                r'.*\.tuigirl\..*',
                r'.*\.legbaby\..*',
                r'.*\.huayang\..*',
                r'.*\.youwu\..*',
                r'.*\.missleg\..*',
                r'.*\.mistar\..*',
                r'.*\.aiyouwu\..*',
                # 常见的图片托管服务
                r'.*\.imgur\.com',
                r'.*\.flickr\.com',
                r'.*\.photobucket\.com'
            ]
            
            return any(re.match(pattern, domain) for pattern in safe_patterns)
            
        except Exception:
            return False
    
    def _check_malicious_patterns(self, url: str) -> bool:
        """检查恶意模式"""
        malicious_patterns = [
            r'javascript:',
            r'data:',
            r'vbscript:',
            r'file:',
            r'ftp:',
            r'<script',
            r'</script>',
            r'eval\(',
            r'exec\(',
            r'system\(',
            r'shell_exec\(',
            r'passthru\(',
            r'\.\./',
            r'%2e%2e%2f',
            r'%252e%252e%252f'
        ]
        
        url_lower = url.lower()
        return not any(re.search(pattern, url_lower) for pattern in malicious_patterns)
    
    def _contains_ip_address(self, url: str) -> bool:
        """检查URL是否包含IP地址"""
        try:
            parsed = urllib.parse.urlparse(url)
            host = parsed.netloc.split(':')[0]  # 移除端口号
            
            # IPv4 模式
            ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
            if re.match(ipv4_pattern, host):
                return True
            
            # IPv6 模式 (简化检查)
            if ':' in host and '[' in host:
                return True
                
            return False
            
        except Exception:
            return False
    
    def _has_path_traversal(self, path: str) -> bool:
        """检查路径遍历攻击"""
        dangerous_patterns = [
            '../',
            '..\\',
            '%2e%2e%2f',
            '%2e%2e%5c',
            '..%2f',
            '..%5c',
            '%252e%252e%252f',
            '%252e%252e%255c'
        ]
        
        path_lower = path.lower()
        return any(pattern in path_lower for pattern in dangerous_patterns)
    
    def _has_valid_path_chars(self, path: str) -> bool:
        """检查路径字符是否有效"""
        # Windows无效字符
        invalid_chars = ['<', '>', ':', '"', '|', '?', '*']
        
        # 控制字符 (0-31)
        for char in path:
            if ord(char) < 32:
                return False
            if char in invalid_chars:
                return False
        
        return True
    
    def _is_system_path(self, path: str) -> bool:
        """检查是否为系统路径"""
        system_paths = [
            '/etc/',
            '/proc/',
            '/sys/',
            '/dev/',
            '/boot/',
            'C:\\Windows\\',
            'C:\\System32\\',
            'C:\\Program Files\\',
            '/usr/bin/',
            '/usr/sbin/',
            '/bin/',
            '/sbin/'
        ]
        
        path_normalized = os.path.normpath(path).replace('\\', '/')
        return any(path_normalized.startswith(sys_path.replace('\\', '/')) 
                  for sys_path in system_paths)
    
    def _is_executable_path(self, path: str) -> bool:
        """检查是否为可执行文件路径"""
        executable_extensions = [
            '.exe', '.bat', '.cmd', '.com', '.scr', '.pif',
            '.sh', '.bash', '.zsh', '.fish',
            '.py', '.pl', '.rb', '.php', '.js'
        ]
        
        path_lower = path.lower()
        return any(path_lower.endswith(ext) for ext in executable_extensions)
    
    def _has_valid_filename_chars(self, filename: str) -> bool:
        """检查文件名字符是否有效"""
        # Windows文件名无效字符
        invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        
        for char in filename:
            if ord(char) < 32 or char in invalid_chars:
                return False
        
        return True
    
    def _is_reserved_filename(self, filename: str) -> bool:
        """检查是否为保留文件名"""
        reserved_names = [
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        ]
        
        name_upper = filename.upper().split('.')[0]  # 移除扩展名
        return name_upper in reserved_names
    
    def _has_safe_extension(self, filename: str) -> bool:
        """检查文件扩展名是否安全"""
        safe_extensions = [
            '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.svg',
            '.txt', '.log', '.json', '.xml', '.csv',
            '.zip', '.rar', '.7z', '.tar', '.gz'
        ]
        
        dangerous_extensions = [
            '.exe', '.bat', '.cmd', '.com', '.scr', '.pif', '.msi',
            '.sh', '.bash', '.zsh', '.fish',
            '.py', '.pl', '.rb', '.php', '.js', '.vbs', '.ps1'
        ]
        
        filename_lower = filename.lower()
        
        # 检查危险扩展名
        if any(filename_lower.endswith(ext) for ext in dangerous_extensions):
            return False
        
        # 如果是严格模式，只允许安全扩展名
        if self.level in [ValidationLevel.STRICT, ValidationLevel.PARANOID]:
            return any(filename_lower.endswith(ext) for ext in safe_extensions)
        
        return True
    
    def _has_image_extension(self, url: str) -> bool:
        """检查是否为图片扩展名"""
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.svg']
        
        try:
            parsed = urllib.parse.urlparse(url)
            path = parsed.path.lower()
            return any(path.endswith(ext) for ext in image_extensions)
        except Exception:
            return False
    
    def _check_url_size_limit(self, url: str) -> bool:
        """检查URL大小限制（简化检查）"""
        # 这里可以实现HEAD请求检查文件大小
        # 为了简化，暂时返回True
        return True
    
    def _contains_xss_patterns(self, text: str) -> bool:
        """检查XSS攻击模式"""
        xss_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'vbscript:',
            r'onload\s*=',
            r'onerror\s*=',
            r'onclick\s*=',
            r'onmouseover\s*=',
            r'<iframe[^>]*>',
            r'<object[^>]*>',
            r'<embed[^>]*>',
            r'<link[^>]*>',
            r'<meta[^>]*>'
        ]
        
        text_lower = text.lower()
        return any(re.search(pattern, text_lower) for pattern in xss_patterns)
    
    def _contains_sql_injection(self, text: str) -> bool:
        """检查SQL注入模式"""
        sql_patterns = [
            r'union\s+select',
            r'drop\s+table',
            r'delete\s+from',
            r'insert\s+into',
            r'update\s+.*\s+set',
            r'exec\s*\(',
            r'execute\s*\(',
            r'sp_executesql',
            r'xp_cmdshell',
            r';\s*--',
            r';\s*/\*',
            r'\'\s*or\s*\'',
            r'\'\s*and\s*\'',
            r'1\s*=\s*1',
            r'1\s*=\s*0'
        ]
        
        text_lower = text.lower()
        return any(re.search(pattern, text_lower) for pattern in sql_patterns)
    
    def _contains_command_injection(self, text: str) -> bool:
        """检查命令注入模式"""
        command_patterns = [
            r';\s*rm\s',
            r';\s*del\s',
            r';\s*cat\s',
            r';\s*type\s',
            r';\s*ls\s',
            r';\s*dir\s',
            r';\s*wget\s',
            r';\s*curl\s',
            r';\s*nc\s',
            r';\s*netcat\s',
            r'\|\s*nc\s',
            r'\|\s*netcat\s',
            r'`.*`',
            r'\$\(.*\)',
            r'&&\s*rm\s',
            r'\|\|\s*rm\s'
        ]
        
        return any(re.search(pattern, text) for pattern in command_patterns)


class URLValidator(InputValidator):
    """URL专用验证器"""
    
    def __init__(self, level: ValidationLevel = ValidationLevel.STRICT):
        super().__init__(level)
    
    def validate_url(self, url: str) -> Dict[str, Any]:
        """验证URL"""
        return self.validate(url, 'url')


class FilePathValidator(InputValidator):
    """文件路径专用验证器"""
    
    def __init__(self, level: ValidationLevel = ValidationLevel.STRICT):
        super().__init__(level)
    
    def validate_path(self, path: str) -> Dict[str, Any]:
        """验证文件路径"""
        return self.validate(path, 'file_path')
    
    def validate_filename(self, filename: str) -> Dict[str, Any]:
        """验证文件名"""
        return self.validate(filename, 'filename')


class ImageValidator(InputValidator):
    """图片专用验证器"""
    
    def __init__(self, level: ValidationLevel = ValidationLevel.STRICT):
        super().__init__(level)
    
    def validate_image_url(self, url: str) -> Dict[str, Any]:
        """验证图片URL"""
        return self.validate(url, 'image_url')


# 便捷函数
def validate_url(url: str, level: ValidationLevel = ValidationLevel.STRICT) -> Dict[str, Any]:
    """验证URL的便捷函数"""
    validator = URLValidator(level)
    return validator.validate_url(url)


def validate_file_path(path: str, level: ValidationLevel = ValidationLevel.STRICT) -> Dict[str, Any]:
    """验证文件路径的便捷函数"""
    validator = FilePathValidator(level)
    return validator.validate_path(path)


def validate_image_url(url: str, level: ValidationLevel = ValidationLevel.STRICT) -> Dict[str, Any]:
    """验证图片URL的便捷函数"""
    validator = ImageValidator(level)
    return validator.validate_image_url(url)


def sanitize_filename(filename: str) -> str:
    """清理文件名"""
    # 移除或替换无效字符
    invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    sanitized = filename
    
    for char in invalid_chars:
        sanitized = sanitized.replace(char, '_')
    
    # 移除控制字符
    sanitized = ''.join(char for char in sanitized if ord(char) >= 32)
    
    # 限制长度
    if len(sanitized) > 255:
        name, ext = os.path.splitext(sanitized)
        max_name_len = 255 - len(ext)
        sanitized = name[:max_name_len] + ext
    
    # 处理保留名称
    reserved_names = [
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    ]
    
    name_upper = sanitized.upper().split('.')[0]
    if name_upper in reserved_names:
        sanitized = f"_{sanitized}"
    
    return sanitized


def sanitize_url(url: str) -> str:
    """清理URL"""
    try:
        # 解析URL
        parsed = urllib.parse.urlparse(url)
        
        # 重新构建URL，确保编码正确
        sanitized = urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            urllib.parse.quote(parsed.path, safe='/'),
            parsed.params,
            urllib.parse.quote_plus(parsed.query, safe='&='),
            urllib.parse.quote(parsed.fragment, safe='')
        ))
        
        return sanitized
        
    except Exception:
        return url
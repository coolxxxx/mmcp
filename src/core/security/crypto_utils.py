"""
加密工具
提供安全的加密、解密和哈希功能
"""

import hashlib
import secrets
import base64
import os
from typing import Dict, Any, Optional, Union, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

from ..exceptions import SecurityError


class CryptoUtils:
    """加密工具类"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    @staticmethod
    def hash_string(data: str, algorithm: str = 'sha256', salt: Optional[str] = None) -> str:
        """
        哈希字符串
        
        Args:
            data: 要哈希的数据
            algorithm: 哈希算法 (sha256, sha512, blake2b)
            salt: 盐值
            
        Returns:
            哈希值的十六进制字符串
        """
        try:
            # 添加盐值
            if salt:
                data = data + salt
            
            data_bytes = data.encode('utf-8')
            
            if algorithm == 'sha256':
                hash_obj = hashlib.sha256(data_bytes)
            elif algorithm == 'sha512':
                hash_obj = hashlib.sha512(data_bytes)
            elif algorithm == 'blake2b':
                hash_obj = hashlib.blake2b(data_bytes)
            else:
                raise ValueError(f"不支持的哈希算法: {algorithm}")
            
            return hash_obj.hexdigest()
            
        except Exception as e:
            raise SecurityError(f"哈希计算失败: {e}")
    
    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """
        生成安全令牌
        
        Args:
            length: 令牌长度
            
        Returns:
            安全令牌
        """
        try:
            return secrets.token_urlsafe(length)
        except Exception as e:
            raise SecurityError(f"令牌生成失败: {e}")
    
    @staticmethod
    def generate_salt(length: int = 16) -> str:
        """
        生成随机盐值
        
        Args:
            length: 盐值长度
            
        Returns:
            盐值
        """
        try:
            return secrets.token_hex(length)
        except Exception as e:
            raise SecurityError(f"盐值生成失败: {e}")
    
    @staticmethod
    def derive_key_from_password(password: str, salt: bytes) -> bytes:
        """
        从密码派生密钥
        
        Args:
            password: 密码
            salt: 盐值
            
        Returns:
            派生的密钥
        """
        try:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,  # 推荐的迭代次数
            )
            return kdf.derive(password.encode('utf-8'))
        except Exception as e:
            raise SecurityError(f"密钥派生失败: {e}")
    
    @staticmethod
    def encrypt_data(data: Union[str, bytes], key: bytes) -> str:
        """
        加密数据
        
        Args:
            data: 要加密的数据
            key: 加密密钥
            
        Returns:
            Base64编码的加密数据
        """
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            fernet = Fernet(base64.urlsafe_b64encode(key))
            encrypted_data = fernet.encrypt(data)
            return base64.urlsafe_b64encode(encrypted_data).decode('utf-8')
            
        except Exception as e:
            raise SecurityError(f"数据加密失败: {e}")
    
    @staticmethod
    def decrypt_data(encrypted_data: str, key: bytes) -> bytes:
        """
        解密数据
        
        Args:
            encrypted_data: Base64编码的加密数据
            key: 解密密钥
            
        Returns:
            解密后的数据
        """
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            fernet = Fernet(base64.urlsafe_b64encode(key))
            return fernet.decrypt(encrypted_bytes)
            
        except Exception as e:
            raise SecurityError(f"数据解密失败: {e}")
    
    @staticmethod
    def encrypt_sensitive_data(data: str, password: str) -> Dict[str, str]:
        """
        加密敏感数据（包含盐值）
        
        Args:
            data: 要加密的敏感数据
            password: 密码
            
        Returns:
            包含加密数据和盐值的字典
        """
        try:
            # 生成随机盐值
            salt = os.urandom(16)
            
            # 从密码派生密钥
            key = CryptoUtils.derive_key_from_password(password, salt)
            
            # 加密数据
            encrypted_data = CryptoUtils.encrypt_data(data, key)
            
            return {
                'encrypted_data': encrypted_data,
                'salt': base64.urlsafe_b64encode(salt).decode('utf-8')
            }
            
        except Exception as e:
            raise SecurityError(f"敏感数据加密失败: {e}")
    
    @staticmethod
    def decrypt_sensitive_data(encrypted_info: Dict[str, str], password: str) -> str:
        """
        解密敏感数据
        
        Args:
            encrypted_info: 包含加密数据和盐值的字典
            password: 密码
            
        Returns:
            解密后的数据
        """
        try:
            # 解码盐值
            salt = base64.urlsafe_b64decode(encrypted_info['salt'].encode('utf-8'))
            
            # 从密码派生密钥
            key = CryptoUtils.derive_key_from_password(password, salt)
            
            # 解密数据
            decrypted_bytes = CryptoUtils.decrypt_data(encrypted_info['encrypted_data'], key)
            return decrypted_bytes.decode('utf-8')
            
        except Exception as e:
            raise SecurityError(f"敏感数据解密失败: {e}")
    
    @staticmethod
    def verify_password_hash(password: str, hashed_password: str, salt: str) -> bool:
        """
        验证密码哈希
        
        Args:
            password: 原始密码
            hashed_password: 哈希后的密码
            salt: 盐值
            
        Returns:
            验证结果
        """
        try:
            computed_hash = CryptoUtils.hash_string(password, 'sha256', salt)
            return secrets.compare_digest(computed_hash, hashed_password)
        except Exception as e:
            raise SecurityError(f"密码验证失败: {e}")
    
    @staticmethod
    def secure_compare(a: str, b: str) -> bool:
        """
        安全字符串比较（防止时序攻击）
        
        Args:
            a: 字符串A
            b: 字符串B
            
        Returns:
            比较结果
        """
        return secrets.compare_digest(a, b)
    
    @staticmethod
    def generate_key_pair() -> Tuple[str, str]:
        """
        生成密钥对（简化版本，实际应用中应使用RSA等非对称加密）
        
        Returns:
            (公钥, 私钥) 元组
        """
        try:
            # 这里使用简化的密钥生成，实际应用中应使用RSA
            private_key = CryptoUtils.generate_secure_token(64)
            public_key = CryptoUtils.hash_string(private_key, 'sha256')
            
            return public_key, private_key
            
        except Exception as e:
            raise SecurityError(f"密钥对生成失败: {e}")


# 便捷函数
def hash_string(data: str, algorithm: str = 'sha256', salt: Optional[str] = None) -> str:
    """哈希字符串的便捷函数"""
    return CryptoUtils.hash_string(data, algorithm, salt)


def generate_secure_token(length: int = 32) -> str:
    """生成安全令牌的便捷函数"""
    return CryptoUtils.generate_secure_token(length)


def encrypt_sensitive_data(data: str, password: str) -> Dict[str, str]:
    """加密敏感数据的便捷函数"""
    return CryptoUtils.encrypt_sensitive_data(data, password)


def decrypt_sensitive_data(encrypted_info: Dict[str, str], password: str) -> str:
    """解密敏感数据的便捷函数"""
    return CryptoUtils.decrypt_sensitive_data(encrypted_info, password)
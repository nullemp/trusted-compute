from cryptography.fernet import Fernet
import os
import base64
import json
from typing import Dict, Any


class EncryptionService:
    """加密服务 - 使用AES-256加密结果"""

    def __init__(self):
        # 从环境变量获取密钥，或生成新密钥
        key = os.getenv("ENCRYPTION_KEY")
        if not key:
            # 生成密钥（仅用于演示，生产环境应该使用固定密钥）
            key = Fernet.generate_key()
        else:
            # 如果密钥是字符串，需要是Base64编码的
            if isinstance(key, str):
                try:
                    # 尝试解码Base64字符串
                    key = key.encode()
                except:
                    # 如果不是有效的Base64，生成新密钥
                    key = Fernet.generate_key()
        
        self.cipher = Fernet(key)

    def encrypt_result(self, data: Dict[str, Any]) -> str:
        """加密计算结果"""
        # 将数据转换为JSON字符串
        json_data = json.dumps(data, ensure_ascii=False)
        
        # 加密
        encrypted_data = self.cipher.encrypt(json_data.encode())
        
        # 返回Base64编码的密文
        return base64.b64encode(encrypted_data).decode()

    def decrypt_result(self, encrypted_data: str) -> Dict[str, Any]:
        """解密计算结果（用于验证，实际使用中可能不需要）"""
        # Base64解码
        encrypted_bytes = base64.b64decode(encrypted_data.encode())
        
        # 解密
        decrypted_data = self.cipher.decrypt(encrypted_bytes)
        
        # 解析JSON
        return json.loads(decrypted_data.decode())

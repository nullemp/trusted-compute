from cryptography.fernet import Fernet
import os
import base64
import json
from typing import Dict, Any


class EncryptionService:
    """Encryption service - AES-256 for result encryption"""

    def __init__(self):
        # Get key from env or generate
        key = os.getenv("ENCRYPTION_KEY")
        if not key:
            # Generate key (demo only; production should use fixed key)
            key = Fernet.generate_key()
        else:
            # If key is str, expect Base64
            if isinstance(key, str):
                try:
                    key = key.encode()
                except Exception:
                    key = Fernet.generate_key()
        
        self.cipher = Fernet(key)

    def encrypt_result(self, data: Dict[str, Any]) -> str:
        """Encrypt compute result"""
        json_data = json.dumps(data, ensure_ascii=False)
        encrypted_data = self.cipher.encrypt(json_data.encode())
        return base64.b64encode(encrypted_data).decode()

    def decrypt_result(self, encrypted_data: str) -> Dict[str, Any]:
        """Decrypt compute result (for verification)"""
        encrypted_bytes = base64.b64decode(encrypted_data.encode())
        decrypted_data = self.cipher.decrypt(encrypted_bytes)
        return json.loads(decrypted_data.decode())

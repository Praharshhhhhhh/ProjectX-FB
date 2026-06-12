import json
import os
import base64
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

CACHE_FILE = Path.home() / ".projectx" / "cache.enc"

class CacheService:
    def _get_key(self, password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    def save(self, data: dict, password: str):
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        salt = os.urandom(16)
        key = self._get_key(password, salt)
        f = Fernet(key)
        encrypted_data = f.encrypt(json.dumps(data).encode())
        
        with open(CACHE_FILE, "wb") as f_out:
            f_out.write(salt + encrypted_data)

    def load(self, password: str) -> dict | None:
        if not CACHE_FILE.exists():
            return None
        
        try:
            with open(CACHE_FILE, "rb") as f_in:
                content = f_in.read()
            
            if len(content) < 16:
                return None
                
            salt = content[:16]
            encrypted_data = content[16:]
            
            key = self._get_key(password, salt)
            f = Fernet(key)
            decrypted_data = f.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            print(f"Failed to load cache: {e}")
            return None

    def clear(self):
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()

cache_service = CacheService()

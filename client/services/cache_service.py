import json
import os
import base64
import time
import sqlite3
from pathlib import Path
from cryptography.fernet import Fernet
import keyring

CACHE_DB = Path.home() / ".projectx" / "cache.db"
KEYRING_SERVICE = "projectx_desktop"
KEYRING_USERNAME = "machine_key"

class CacheService:
    def __init__(self):
        self._f = None
        self._init_key()
        self._init_db()

    def _init_key(self):
        try:
            key_b64 = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
            if not key_b64:
                key = Fernet.generate_key()
                key_b64 = key.decode("utf-8")
                keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, key_b64)
            self._f = Fernet(key_b64.encode("utf-8"))
        except Exception as e:
            print("Failed to initialize keyring:", e)
            # Fallback for dev if keyring fails completely
            fallback = base64.urlsafe_b64encode(b"fallback_key_32_bytes_projectxxx")
            self._f = Fernet(fallback)

    def _init_db(self):
        CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(CACHE_DB) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS endpoint_cache (
                    endpoint TEXT PRIMARY KEY,
                    payload_encrypted BLOB,
                    cached_at INTEGER
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS offline_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT,
                    payload_encrypted BLOB,
                    created_at INTEGER
                )
            """)
            conn.commit()

    # --- Endpoint Cache ---
    def set_cache(self, endpoint: str, data: dict):
        try:
            enc = self._f.encrypt(json.dumps(data).encode("utf-8"))
            now = int(time.time())
            with sqlite3.connect(CACHE_DB) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO endpoint_cache (endpoint, payload_encrypted, cached_at) VALUES (?, ?, ?)",
                    (endpoint, enc, now)
                )
                conn.commit()
        except Exception as e:
            print("Failed to set cache:", e)

    def get_cache(self, endpoint: str) -> tuple[dict|None, int]:
        """Returns (data_dict, cached_at_timestamp)"""
        try:
            with sqlite3.connect(CACHE_DB) as conn:
                cursor = conn.execute("SELECT payload_encrypted, cached_at FROM endpoint_cache WHERE endpoint = ?", (endpoint,))
                row = cursor.fetchone()
                if row:
                    dec = self._f.decrypt(row[0])
                    return json.loads(dec.decode("utf-8")), row[1]
        except Exception as e:
            print("Failed to get cache:", e)
        return None, 0

    # --- Offline Action Queue ---
    def add_offline_action(self, action: str, payload: dict):
        try:
            enc = self._f.encrypt(json.dumps(payload).encode("utf-8"))
            now = int(time.time())
            with sqlite3.connect(CACHE_DB) as conn:
                conn.execute(
                    "INSERT INTO offline_actions (action, payload_encrypted, created_at) VALUES (?, ?, ?)",
                    (action, enc, now)
                )
                conn.commit()
        except Exception as e:
            print("Failed to add offline action:", e)

    def get_offline_actions(self) -> list[dict]:
        actions = []
        try:
            with sqlite3.connect(CACHE_DB) as conn:
                cursor = conn.execute("SELECT id, action, payload_encrypted, created_at FROM offline_actions ORDER BY id ASC")
                for row in cursor.fetchall():
                    dec = self._f.decrypt(row[2])
                    payload = json.loads(dec.decode("utf-8"))
                    actions.append({
                        "id": row[0],
                        "action": row[1],
                        "payload": payload,
                        "created_at": row[3]
                    })
        except Exception as e:
            print("Failed to get offline actions:", e)
        return actions

    def remove_offline_action(self, action_id: int):
        try:
            with sqlite3.connect(CACHE_DB) as conn:
                conn.execute("DELETE FROM offline_actions WHERE id = ?", (action_id,))
                conn.commit()
        except Exception as e:
            print("Failed to remove offline action:", e)

    def clear(self):
        if CACHE_DB.exists():
            CACHE_DB.unlink()

cache_service = CacheService()

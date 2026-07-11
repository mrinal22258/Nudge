import os
import secrets

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SECRET_FILE = os.path.join(PROJECT_ROOT, ".nudge_secret")

def get_or_create_server_secret() -> bytes:
    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE, "rb") as f:
            return f.read()
    key = secrets.token_bytes(32)
    with open(SECRET_FILE, "wb") as f:
        f.write(key)
    return key

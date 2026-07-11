import json
import os
import threading
import hmac
import hashlib
from typing import Dict, Any, List, Optional
from backend.secrets_store import get_or_create_server_secret

def _sign_entry(session_id: str, entry: Dict[str, Any]) -> str:
    secret = get_or_create_server_secret()
    payload = f"{session_id}|{entry['index']}|{entry['type']}|{entry['timestamp']}|{entry['content']}".encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()

DB_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "db.json"))

class LocalDB:
    def __init__(self):
        self.lock = threading.Lock()
        self._cache = None
        self._last_mtime = 0.0
        self._init_db()

    def _init_db(self):
        with self.lock:
            if not os.path.exists(DB_FILE):
                default_data = {
                    "candidates": {},
                    "job_targets": {},
                    "sessions": {},
                    "debriefs": {}
                }
                self._write_db(default_data)

    def _read_db(self) -> Dict[str, Any]:
        try:
            mtime = os.path.getmtime(DB_FILE)
        except OSError:
            mtime = 0.0
            
        if self._cache is not None and mtime <= self._last_mtime:
            return self._cache
            
        with open(DB_FILE, "r", encoding="utf-8") as f:
            self._cache = json.load(f)
            self._last_mtime = mtime
            return self._cache

    def _write_db(self, data: Dict[str, Any]):
        import tempfile
        db_dir = os.path.dirname(DB_FILE)
        fd, temp_path = tempfile.mkstemp(dir=db_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(temp_path, DB_FILE)
            self._cache = data
            try:
                self._last_mtime = os.path.getmtime(DB_FILE)
            except OSError:
                self._last_mtime = 0.0
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise e

    # Candidates CRUD
    def save_candidate(self, candidate_id: str, data: Dict[str, Any]):
        with self.lock:
            db = self._read_db()
            db["candidates"][candidate_id] = data
            self._write_db(db)

    def get_candidate(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            db = self._read_db()
            return db["candidates"].get(candidate_id)

    # JobTargets CRUD
    def save_job_target(self, target_id: str, data: Dict[str, Any]):
        with self.lock:
            db = self._read_db()
            db["job_targets"][target_id] = data
            self._write_db(db)

    def get_job_target(self, target_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            db = self._read_db()
            return db["job_targets"].get(target_id)

    def save_session(self, session_id: str, data: Dict[str, Any]):
        with self.lock:
            db = self._read_db()
            db["sessions"][session_id] = data
            self._write_db(db)

    def add_session_transcript_entry(self, session_id: str, entry_type: str, content: str) -> Optional[Dict[str, Any]]:
        from datetime import datetime
        with self.lock:
            db = self._read_db()
            sess = db["sessions"].get(session_id)
            if sess:
                if "transcript" not in sess:
                    sess["transcript"] = []
                entry = {
                    "index": len(sess["transcript"]),
                    "timestamp": datetime.now().isoformat(),
                    "type": entry_type,
                    "content": content
                }
                entry["signature"] = _sign_entry(session_id, entry)
                sess["transcript"].append(entry)
                self._write_db(db)
                return entry
            return None

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            db = self._read_db()
            return db["sessions"].get(session_id)

    def list_sessions(self) -> List[Dict[str, Any]]:
        with self.lock:
            db = self._read_db()
            return list(db["sessions"].values())

    # Debriefs CRUD
    def save_debrief(self, session_id: str, data: Dict[str, Any]):
        with self.lock:
            db = self._read_db()
            db["debriefs"][session_id] = data
            self._write_db(db)

    def get_debrief(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            db = self._read_db()
            return db["debriefs"].get(session_id)

db = LocalDB()

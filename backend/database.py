import json
import os
import threading
from typing import Dict, Any, List, Optional

DB_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "db.json"))

class LocalDB:
    def __init__(self):
        self.lock = threading.Lock()
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
                with open(DB_FILE, "w", encoding="utf-8") as f:
                    json.dump(default_data, f, indent=2)

    def _read_db(self) -> Dict[str, Any]:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_db(self, data: Dict[str, Any]):
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

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

    # Sessions CRUD
    def save_session(self, session_id: str, data: Dict[str, Any]):
        with self.lock:
            db = self._read_db()
            db["sessions"][session_id] = data
            self._write_db(db)

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

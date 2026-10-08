"""Thread-safe in-memory store for file metadata and measurement results."""

import threading
from typing import Any, Dict, Optional


class FileStore:
    """Thread-safe in-memory storage manager using a threading lock."""

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def save(self, file_id: str, record: Dict[str, Any]) -> None:
        """Save or update a file record thread-safely."""
        with self._lock:
            self._store[file_id] = record

    def get(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a file record by ID thread-safely."""
        with self._lock:
            return self._store.get(file_id)

    def clear(self) -> None:
        """Clear all stored records (useful between test runs)."""
        with self._lock:
            self._store.clear()


# Global shared instance
store = FileStore()

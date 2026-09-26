"""Trigger suppression tracking to prevent duplicate outreach and turn spam."""

from __future__ import annotations
import threading
from datetime import datetime
from typing import Dict, Optional
from pydantic import Field
from vera.models.base import VeraBaseModel


class SuppressionRecord(VeraBaseModel):
    """Record of an active suppression entry."""

    key: str = Field(..., min_length=1, description="Unique suppression deduplication key")
    trigger_id: str = Field(..., min_length=1, description="Trigger ID that created this suppression")
    suppressed_at: str = Field(..., description="ISO timestamp when suppression began")
    expires_at: Optional[str] = Field(default=None, description="ISO timestamp when suppression lifts")


class SuppressionStore:
    """Thread-safe store managing active frequency caps and deduplication keys."""

    def __init__(self):
        self._lock = threading.RLock()
        self._records: Dict[str, SuppressionRecord] = {}

    def is_suppressed(self, key: str, now_iso: Optional[str] = None) -> bool:
        """Checks if a suppression key is currently active."""
        with self._lock:
            record = self._records.get(key)
            if not record:
                return False

            if record.expires_at and now_iso:
                # If now_iso >= expires_at, suppression has expired
                if now_iso >= record.expires_at:
                    del self._records[key]
                    return False

            return True

    def record_suppression(
        self,
        key: str,
        trigger_id: str,
        suppressed_at: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> SuppressionRecord:
        """Marks a suppression key as actively handled."""
        with self._lock:
            ts = suppressed_at or (datetime.utcnow().isoformat() + "Z")
            record = SuppressionRecord(
                key=key,
                trigger_id=trigger_id,
                suppressed_at=ts,
                expires_at=expires_at,
            )
            self._records[key] = record
            return record

    def remove_suppression(self, key: str) -> bool:
        """Manually lifts a suppression key."""
        with self._lock:
            return self._records.pop(key, None) is not None

    def get_active_keys(self) -> list[str]:
        """Lists all active suppression keys."""
        with self._lock:
            return list(self._records.keys())

    def clear(self):
        """Clears all suppression entries."""
        with self._lock:
            self._records.clear()

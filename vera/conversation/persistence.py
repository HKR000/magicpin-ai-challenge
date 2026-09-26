"""Thread-safe persistence layer and repository for ConversationState management."""

from __future__ import annotations
import json
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from vera.models.conversation import ConversationState


class ConversationStore:
    """Thread-safe repository supporting in-memory and disk snapshot persistence."""

    def __init__(self, persistence_dir: Optional[str | Path] = None):
        self._lock = threading.RLock()
        self._conversations: Dict[str, ConversationState] = {}
        self.persistence_dir: Optional[Path] = (
            Path(persistence_dir) if persistence_dir else None
        )
        if self.persistence_dir:
            self.persistence_dir.mkdir(parents=True, exist_ok=True)

    def save(self, state: ConversationState) -> ConversationState:
        """Saves or updates a conversation state record thread-safely."""
        with self._lock:
            self._conversations[state.conversation_id] = state
            if self.persistence_dir:
                self._persist_to_file(state)
            return state

    def get(self, conversation_id: str) -> Optional[ConversationState]:
        """Retrieves a conversation state by its unique ID."""
        with self._lock:
            state = self._conversations.get(conversation_id)
            if not state and self.persistence_dir:
                state = self._load_from_file(conversation_id)
                if state:
                    self._conversations[conversation_id] = state
            return state

    def exists(self, conversation_id: str) -> bool:
        """Returns True if the conversation ID exists in storage."""
        with self._lock:
            if conversation_id in self._conversations:
                return True
            if self.persistence_dir:
                file_path = self.persistence_dir / f"{conversation_id}.json"
                return file_path.exists()
            return False

    def delete(self, conversation_id: str) -> bool:
        """Deletes a conversation from storage."""
        with self._lock:
            deleted = self._conversations.pop(conversation_id, None) is not None
            if self.persistence_dir:
                file_path = self.persistence_dir / f"{conversation_id}.json"
                if file_path.exists():
                    try:
                        file_path.unlink()
                        deleted = True
                    except OSError:
                        pass
            return deleted

    def list_all(self) -> List[ConversationState]:
        """Returns all stored conversation states."""
        with self._lock:
            return list(self._conversations.values())

    def list_active(self) -> List[ConversationState]:
        """Returns all non-terminal, active conversation states."""
        with self._lock:
            return [c for c in self._conversations.values() if getattr(c, "is_active", True)]

    def count(self) -> int:
        """Returns total count of conversations in memory."""
        with self._lock:
            return len(self._conversations)

    def clear(self):
        """Clears all conversations (used in teardown/tests)."""
        with self._lock:
            self._conversations.clear()
            if self.persistence_dir and self.persistence_dir.exists():
                for f in self.persistence_dir.glob("*.json"):
                    try:
                        f.unlink()
                    except OSError:
                        pass

    # -------------------------------------------------------------------------
    # Snapshot & File Serialization
    # -------------------------------------------------------------------------

    def _persist_to_file(self, state: ConversationState):
        """Writes single conversation state to JSON file."""
        if not self.persistence_dir:
            return
        target_path = self.persistence_dir / f"{state.conversation_id}.json"
        try:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(state.to_json(indent=2))
        except Exception:
            pass

    def _load_from_file(self, conversation_id: str) -> Optional[ConversationState]:
        """Reads single conversation state from JSON file."""
        if not self.persistence_dir:
            return None
        target_path = self.persistence_dir / f"{conversation_id}.json"
        if not target_path.exists():
            return None
        try:
            from vera.models.conversation import ConversationState
            with open(target_path, "r", encoding="utf-8") as f:
                return ConversationState.from_json(f.read())
        except Exception:
            return None

    def dump_snapshot(self) -> Dict[str, Any]:
        """Dumps all conversations to a serializable dictionary."""
        with self._lock:
            return {
                cid: c.model_dump()
                for cid, c in self._conversations.items()
            }

    def load_snapshot(self, snapshot: Dict[str, Any]):
        """Restores conversations from a dictionary snapshot."""
        from vera.models.conversation import ConversationState
        with self._lock:
            for cid, data in snapshot.items():
                self._conversations[cid] = ConversationState(**data)

    def save_snapshot_file(self, file_path: str | Path):
        """Exports all conversation states to a single JSON snapshot file."""
        with self._lock:
            p = Path(file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self.dump_snapshot(), f, indent=2)

    def load_snapshot_file(self, file_path: str | Path):
        """Imports conversation states from a JSON snapshot file."""
        with self._lock:
            p = Path(file_path)
            if not p.exists():
                raise FileNotFoundError(f"Snapshot file not found: {file_path}")
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.load_snapshot(data)

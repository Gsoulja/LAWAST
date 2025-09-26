"""
Session Manager - Manages multi-turn dialogue sessions with persistence
"""

import os
import json
import uuid
import logging
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path

from .context_tree import ContextTree

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    """State of a dialogue session"""
    session_id: str
    created_at: str
    last_activity: str
    turn_count: int = 0
    context_tree: Optional[ContextTree] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, str]] = field(default_factory=list)
    is_active: bool = True


class SessionManager:
    """Manages dialogue sessions with persistence and timeout"""

    def __init__(self,
                storage_path: str = "./sessions",
                timeout_minutes: int = 30,
                max_sessions: int = 100):
        """
        Initialize the session manager.

        Args:
            storage_path: Path to store session data
            timeout_minutes: Session timeout in minutes
            max_sessions: Maximum number of concurrent sessions
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.timeout_minutes = timeout_minutes
        self.max_sessions = max_sessions
        self.active_sessions: Dict[str, SessionState] = {}

        # Load existing sessions
        self._load_sessions()

    def create_session(self, metadata: Optional[Dict] = None) -> SessionState:
        """
        Create a new session.

        Args:
            metadata: Optional session metadata

        Returns:
            New SessionState object
        """
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        session = SessionState(
            session_id=session_id,
            created_at=now,
            last_activity=now,
            context_tree=ContextTree(),
            metadata=metadata or {}
        )

        self.active_sessions[session_id] = session
        self._save_session(session)

        # Clean up if too many sessions
        if len(self.active_sessions) > self.max_sessions:
            self._cleanup_old_sessions()

        logger.info(f"Created new session: {session_id}")
        return session

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """
        Get an existing session.

        Args:
            session_id: Session ID

        Returns:
            SessionState if found and active, None otherwise
        """
        # Check active sessions
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            if self._is_session_expired(session):
                self._expire_session(session_id)
                return None
            return session

        # Try to load from disk
        session = self._load_session(session_id)
        if session and not self._is_session_expired(session):
            self.active_sessions[session_id] = session
            return session

        return None

    def update_session(self,
                      session_id: str,
                      query: Optional[str] = None,
                      response: Optional[str] = None) -> bool:
        """
        Update a session with new interaction.

        Args:
            session_id: Session ID
            query: User query
            response: Agent response

        Returns:
            True if updated, False if session not found
        """
        session = self.get_session(session_id)
        if not session:
            return False

        # Update activity timestamp
        session.last_activity = datetime.now().isoformat()
        session.turn_count += 1

        # Add to history
        if query:
            session.history.append({"role": "user", "content": query})
        if response:
            session.history.append({"role": "assistant", "content": response})

        # Save to disk
        self._save_session(session)

        logger.debug(f"Updated session {session_id}, turn {session.turn_count}")
        return True

    def expire_session(self, session_id: str) -> bool:
        """
        Expire a session.

        Args:
            session_id: Session ID

        Returns:
            True if expired, False if not found
        """
        return self._expire_session(session_id)

    def _expire_session(self, session_id: str) -> bool:
        """
        Internal method to expire a session.

        Args:
            session_id: Session ID

        Returns:
            True if expired, False if not found
        """
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.is_active = False
            self._save_session(session)
            del self.active_sessions[session_id]
            logger.info(f"Expired session: {session_id}")
            return True
        return False

    def _is_session_expired(self, session: SessionState) -> bool:
        """
        Check if a session has expired.

        Args:
            session: SessionState object

        Returns:
            True if expired
        """
        if not session.is_active:
            return True

        last_activity = datetime.fromisoformat(session.last_activity)
        timeout = timedelta(minutes=self.timeout_minutes)
        return datetime.now() - last_activity > timeout

    def _cleanup_old_sessions(self) -> int:
        """
        Clean up old sessions.

        Returns:
            Number of sessions cleaned up
        """
        expired_ids = []
        for session_id, session in self.active_sessions.items():
            if self._is_session_expired(session):
                expired_ids.append(session_id)

        for session_id in expired_ids:
            self._expire_session(session_id)

        # Also check disk for very old sessions
        old_count = 0
        for session_file in self.storage_path.glob("*.json"):
            try:
                with open(session_file, 'r') as f:
                    data = json.load(f)
                last_activity = datetime.fromisoformat(data['last_activity'])
                if datetime.now() - last_activity > timedelta(days=7):
                    session_file.unlink()
                    old_count += 1
            except Exception as e:
                logger.error(f"Error cleaning up session file {session_file}: {e}")

        total_cleaned = len(expired_ids) + old_count
        if total_cleaned > 0:
            logger.info(f"Cleaned up {total_cleaned} sessions")

        return total_cleaned

    def _save_session(self, session: SessionState) -> None:
        """
        Save session to disk.

        Args:
            session: SessionState to save
        """
        session_file = self.storage_path / f"{session.session_id}.json"

        # Prepare data for serialization
        data = {
            'session_id': session.session_id,
            'created_at': session.created_at,
            'last_activity': session.last_activity,
            'turn_count': session.turn_count,
            'metadata': session.metadata,
            'history': session.history,
            'is_active': session.is_active,
            'context_tree': session.context_tree.to_json() if session.context_tree else None
        }

        try:
            with open(session_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved session {session.session_id} to disk")
        except Exception as e:
            logger.error(f"Failed to save session {session.session_id}: {e}")

    def _load_session(self, session_id: str) -> Optional[SessionState]:
        """
        Load session from disk.

        Args:
            session_id: Session ID

        Returns:
            SessionState if found, None otherwise
        """
        session_file = self.storage_path / f"{session_id}.json"

        if not session_file.exists():
            return None

        try:
            with open(session_file, 'r') as f:
                data = json.load(f)

            session = SessionState(
                session_id=data['session_id'],
                created_at=data['created_at'],
                last_activity=data['last_activity'],
                turn_count=data['turn_count'],
                metadata=data.get('metadata', {}),
                history=data.get('history', []),
                is_active=data.get('is_active', True)
            )

            # Reconstruct context tree
            if data.get('context_tree'):
                session.context_tree = ContextTree.from_json(data['context_tree'])

            logger.debug(f"Loaded session {session_id} from disk")
            return session

        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None

    def _load_sessions(self) -> None:
        """Load active sessions from disk on startup."""
        loaded_count = 0
        for session_file in self.storage_path.glob("*.json"):
            try:
                session_id = session_file.stem
                session = self._load_session(session_id)
                if session and session.is_active and not self._is_session_expired(session):
                    self.active_sessions[session_id] = session
                    loaded_count += 1
            except Exception as e:
                logger.error(f"Error loading session from {session_file}: {e}")

        if loaded_count > 0:
            logger.info(f"Loaded {loaded_count} active sessions from disk")

    def get_session_history(self, session_id: str) -> List[Dict[str, str]]:
        """
        Get the conversation history for a session.

        Args:
            session_id: Session ID

        Returns:
            List of conversation turns
        """
        session = self.get_session(session_id)
        if session:
            return session.history
        return []

    def get_session_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the extracted context for a session.

        Args:
            session_id: Session ID

        Returns:
            Context dictionary if session exists
        """
        session = self.get_session(session_id)
        if session and session.context_tree:
            return session.context_tree.get_summary()
        return None

    def list_active_sessions(self) -> List[Dict[str, Any]]:
        """
        List all active sessions.

        Returns:
            List of session summaries
        """
        sessions = []
        for session_id, session in self.active_sessions.items():
            if not self._is_session_expired(session):
                sessions.append({
                    'session_id': session_id,
                    'created_at': session.created_at,
                    'last_activity': session.last_activity,
                    'turn_count': session.turn_count,
                    'is_active': session.is_active
                })
        return sessions

    def clear_all_sessions(self) -> int:
        """
        Clear all sessions (for testing/reset).

        Returns:
            Number of sessions cleared
        """
        count = len(self.active_sessions)

        # Clear from memory
        self.active_sessions.clear()

        # Clear from disk
        for session_file in self.storage_path.glob("*.json"):
            try:
                session_file.unlink()
            except Exception as e:
                logger.error(f"Error deleting session file {session_file}: {e}")

        logger.info(f"Cleared {count} sessions")
        return count
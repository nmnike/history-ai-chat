# src/viewer/parsers/codex.py
"""Parser for OpenAI Codex CLI conversation history"""
import json
from pathlib import Path
from typing import Optional
from datetime import datetime
from .claude import Message, Session


class CodexParser:
    """Parse Codex CLI rollout JSONL files"""

    def __init__(self, sessions_path: str = None):
        import os
        self.sessions_path = Path(sessions_path or os.path.expanduser("~/.codex/sessions"))

    def parse_session(self, session_file: Path) -> list[Message]:
        """Parse a Codex rollout JSONL file"""
        messages = []

        with open(session_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                msg = self._parse_message(data, session_file)
                if msg:
                    messages.append(msg)

        return messages

    def _parse_message(self, data: dict, session_file: Path) -> Optional[Message]:
        """Parse a single message from Codex JSONL"""
        msg_type = data.get("type", "")

        if msg_type == "message":
            return self._parse_chat_message(data, session_file)
        elif msg_type == "function_call":
            return self._parse_tool_use(data, session_file)

        return None

    def _parse_chat_message(self, data: dict, session_file: Path) -> Optional[Message]:
        """Parse chat message"""
        role = data.get("role", "")
        content = data.get("content", "")

        if isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
            content = "\n".join(texts)

        return Message(
            role=role,
            content=str(content),
            uuid=data.get("id", ""),
            timestamp=self._parse_timestamp(data.get("timestamp")),
            session_id=session_file.stem,
            project_path=self._extract_project_from_path(session_file),
            message_type="text"
        )

    def _parse_tool_use(self, data: dict, session_file: Path) -> Optional[Message]:
        """Parse function/tool call"""
        return Message(
            role="assistant",
            content="",
            uuid=data.get("id", ""),
            timestamp=self._parse_timestamp(data.get("timestamp")),
            session_id=session_file.stem,
            project_path=self._extract_project_from_path(session_file),
            message_type="tool_use",
            tool_name=data.get("name", ""),
            tool_input=data.get("arguments", {})
        )

    def _parse_timestamp(self, ts) -> Optional[datetime]:
        """Parse timestamp"""
        if not ts:
            return None
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts)
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                pass
        return None

    def _extract_project_from_path(self, session_file: Path) -> str:
        """Extract project context from session file path"""
        # Session path: ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl
        parts = session_file.parts
        if len(parts) >= 4:
            return f"codex-{parts[-4]}-{parts[-3]}-{parts[-2]}"
        return "codex"

    def get_sessions(self) -> list[Session]:
        """Get all Codex sessions organized by date"""
        sessions = []

        if not self.sessions_path.exists():
            return sessions

        for session_file in self.sessions_path.glob("**/rollout-*.jsonl"):
            messages = self.parse_session(session_file)
            if messages:
                session = Session(
                    id=session_file.stem,
                    project_path=str(session_file.parent),
                    project_name=self._extract_project_from_path(session_file),
                    messages=messages,
                    first_message=messages[0].content[:100] if messages else None,
                    created_at=messages[0].timestamp if messages else None
                )
                sessions.append(session)

        return sorted(sessions, key=lambda x: x.created_at or datetime.min, reverse=True)
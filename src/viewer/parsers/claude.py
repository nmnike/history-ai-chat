# src/viewer/parsers/claude.py
"""Parser for Claude Code conversation history"""
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Message:
    """Represents a single message in a conversation"""
    role: str  # user, assistant
    content: str
    uuid: str
    timestamp: datetime
    session_id: str
    project_path: str
    message_type: str = "text"  # text, thinking, tool_use, tool_result
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    thinking_text: Optional[str] = None


@dataclass
class Session:
    """Represents a conversation session"""
    id: str
    project_path: str
    project_name: str
    messages: list[Message]
    first_message: Optional[str] = None
    created_at: Optional[datetime] = None


class ClaudeParser:
    """Parse Claude Code JSONL conversation files"""

    def __init__(self, projects_path: str = None):
        import os
        self.projects_path = Path(projects_path or os.path.expanduser("~/.claude/projects"))

    def parse_session(self, session_file: Path) -> list[Message]:
        """Parse a single session JSONL file"""
        messages = []

        with open(session_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                msg = self._parse_message(data)
                if msg:
                    messages.append(msg)

        return messages

    def _parse_message(self, data: dict) -> Optional[Message]:
        """Parse a single message from JSONL"""
        msg_type = data.get("type")

        if msg_type == "user":
            return self._parse_user_message(data)
        elif msg_type == "assistant":
            return self._parse_assistant_message(data)

        return None

    def _parse_user_message(self, data: dict) -> Optional[Message]:
        """Parse user message"""
        message = data.get("message", {})
        content = message.get("content", "")

        # Handle string or list content
        if isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        texts.append(block.get("text", ""))
                    elif block.get("type") == "tool_result":
                        # Extract actual tool result content
                        tool_content = block.get("content", "")
                        if tool_content:
                            texts.append(str(tool_content))
                        else:
                            texts.append(f"[Tool Result: {block.get('tool_use_id', 'unknown')}]")
                else:
                    texts.append(str(block))
            content = "\n".join(texts)

        return Message(
            role="user",
            content=str(content),
            uuid=data.get("uuid", ""),
            timestamp=self._parse_timestamp(data.get("timestamp")),
            session_id=data.get("sessionId", ""),
            project_path=data.get("cwd", ""),
            message_type="text"
        )

    def _parse_assistant_message(self, data: dict) -> Optional[Message]:
        """Parse assistant message with support for thinking and tool_use"""
        message = data.get("message", {})
        content_blocks = message.get("content", [])

        if not isinstance(content_blocks, list):
            return Message(
                role="assistant",
                content=str(content_blocks),
                uuid=data.get("uuid", ""),
                timestamp=self._parse_timestamp(data.get("timestamp")),
                session_id=data.get("sessionId", ""),
                project_path=data.get("cwd", ""),
                message_type="text"
            )

        # Extract text, thinking, and tool_use from content blocks
        text_parts = []
        thinking_text = None
        tool_name = None
        tool_input = None
        msg_type = "text"

        for block in content_blocks:
            block_type = block.get("type", "")

            if block_type == "text":
                text_parts.append(block.get("text", ""))
            elif block_type == "thinking":
                thinking_text = block.get("thinking", "")
                msg_type = "thinking"
            elif block_type == "tool_use":
                tool_name = block.get("name", "")
                tool_input = block.get("input", {})
                msg_type = "tool_use"

        return Message(
            role="assistant",
            content="\n".join(text_parts) if text_parts else "",
            uuid=data.get("uuid", ""),
            timestamp=self._parse_timestamp(data.get("timestamp")),
            session_id=data.get("sessionId", ""),
            project_path=data.get("cwd", ""),
            message_type=msg_type,
            tool_name=tool_name,
            tool_input=tool_input,
            thinking_text=thinking_text
        )

    def _parse_timestamp(self, ts) -> Optional[datetime]:
        """Parse timestamp from various formats"""
        if not ts:
            return None
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts / 1000)
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                pass
        return None

    def get_projects(self) -> list[dict]:
        """Get list of all projects"""
        projects = []

        if not self.projects_path.exists():
            return projects

        for project_dir in self.projects_path.iterdir():
            if not project_dir.is_dir():
                continue

            sessions = list(project_dir.glob("*.jsonl"))
            if sessions:
                project_name = project_dir.name.replace("-", "/").replace("_", " ")
                projects.append({
                    "id": project_dir.name,
                    "name": project_name,
                    "path": str(project_dir),
                    "session_count": len(sessions)
                })

        return sorted(projects, key=lambda x: x["name"])

    def get_sessions(self, project_id: str) -> list[Session]:
        """Get all sessions for a project"""
        project_path = self.projects_path / project_id
        sessions = []

        if not project_path.exists():
            return sessions

        for session_file in project_path.glob("*.jsonl"):
            if session_file.name.startswith("agent-"):
                continue

            messages = self.parse_session(session_file)
            if messages:
                session = Session(
                    id=session_file.stem,
                    project_path=str(project_path),
                    project_name=project_id,
                    messages=messages,
                    first_message=messages[0].content[:100] if messages else None,
                    created_at=messages[0].timestamp if messages else None
                )
                sessions.append(session)

        return sorted(sessions, key=lambda x: x.created_at or datetime.min, reverse=True)
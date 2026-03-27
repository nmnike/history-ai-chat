# src/viewer/parsers/codex.py
"""Parser for OpenAI Codex CLI conversation history (v0.115.0+)"""
import json
from pathlib import Path
from typing import Optional
from datetime import datetime
from .claude import Message, Session


class CodexParser:
    """Parse Codex CLI rollout JSONL files (v0.115.0+ format)"""

    def __init__(self, sessions_path: str = None):
        import os
        self.sessions_path = Path(sessions_path or os.path.expanduser("~/.codex/sessions"))

    def parse_session(self, session_file: Path) -> tuple[list[Message], dict]:
        """Parse a Codex rollout JSONL file.

        Returns tuple of (messages, metadata) where metadata contains session info.
        """
        messages = []
        metadata = {"cwd": None, "cli_version": None, "models": set(), "efforts": set()}
        last_assistant_idx = None  # Track last assistant message for token attribution
        current_model = None
        current_effort = None

        with open(session_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Extract session metadata
                if data.get("type") == "session_meta":
                    payload = data.get("payload", {})
                    metadata["cwd"] = payload.get("cwd")
                    metadata["cli_version"] = payload.get("cli_version")
                    continue

                # Track current model/effort from each turn_context
                if data.get("type") == "turn_context":
                    payload = data.get("payload", {})
                    current_model = payload.get("model")
                    current_effort = payload.get("effort")
                    if current_model:
                        metadata["models"].add(current_model)
                    if current_effort:
                        metadata["efforts"].add(current_effort)
                    continue

                # Handle token count - attribute to last assistant message
                if data.get("type") == "event_msg":
                    self._handle_token_event(data, messages, last_assistant_idx)
                    continue

                msg = self._parse_message(data, session_file, metadata)
                if msg:
                    # Attach current model/effort to assistant messages
                    if msg.role == "assistant":
                        msg.model = current_model
                        msg.effort = current_effort
                        last_assistant_idx = len(messages)
                    messages.append(msg)

        # Build session-level model/effort strings (sorted for determinism)
        metadata["model"] = ", ".join(sorted(metadata["models"])) or None
        metadata["effort"] = ", ".join(sorted(metadata["efforts"])) or None

        return messages, metadata

    def _handle_token_event(self, data: dict, messages: list[Message], last_assistant_idx: Optional[int]) -> None:
        """Handle token_count event and attribute to last assistant message."""
        payload = data.get("payload", {})
        if payload.get("type") != "token_count":
            return

        info = payload.get("info") or {}
        last_usage = info.get("last_token_usage") or {}

        # Only process if we have actual token values
        input_tokens = last_usage.get("input_tokens") or 0
        output_tokens = last_usage.get("output_tokens") or 0
        if input_tokens == 0 and output_tokens == 0:
            return

        # Attribute to last assistant message
        if last_assistant_idx is not None and last_assistant_idx < len(messages):
            msg = messages[last_assistant_idx]
            # Update token fields on the message
            msg.input_tokens = input_tokens
            msg.output_tokens = output_tokens
            msg.cache_read_tokens = last_usage.get("cached_input_tokens") or 0
            # Codex has reasoning_output_tokens which we don't track separately

    def _parse_message(self, data: dict, session_file: Path, metadata: dict) -> Optional[Message]:
        """Parse a single message from Codex JSONL (v0.115.0+ format)"""
        msg_type = data.get("type", "")

        # v0.115.0+ format: response_item with nested payload
        if msg_type == "response_item":
            return self._parse_response_item(data, session_file, metadata)
        # Legacy format support
        elif msg_type == "message":
            return self._parse_legacy_chat_message(data, session_file)
        elif msg_type == "function_call":
            return self._parse_legacy_tool_use(data, session_file)

        return None

    def _parse_response_item(self, data: dict, session_file: Path, metadata: dict) -> Optional[Message]:
        """Parse v0.115.0+ response_item format"""
        payload = data.get("payload", {})
        role = payload.get("role", "")

        # Only process user/assistant messages
        if role not in ("user", "assistant"):
            return None

        content_list = payload.get("content", [])
        if isinstance(content_list, str):
            content = content_list
        else:
            texts = []
            for block in content_list:
                if isinstance(block, dict):
                    block_type = block.get("type", "")
                    if block_type in ("input_text", "output_text", "text"):
                        texts.append(block.get("text", ""))
            content = "\n".join(texts)

        # Detect system-injected messages and change role
        if role == "user" and self._is_system_message(content):
            role = "system"

        # Use cwd from metadata if available
        project_path = metadata.get("cwd") or self._extract_project_from_path(session_file)

        return Message(
            role=role,
            content=content,
            uuid=payload.get("id", data.get("timestamp", "")),
            timestamp=self._parse_timestamp(data.get("timestamp")),
            session_id=session_file.stem,
            project_path=project_path,
            message_type="text"
        )

    def _is_system_message(self, content: str) -> bool:
        """Detect if message is system-injected (AGENTS.md, environment_context)"""
        return (
            content.startswith("# AGENTS.md") or
            content.startswith("<environment_context>") or
            content.startswith("<INSTRUCTIONS>")
        )

    def _parse_legacy_chat_message(self, data: dict, session_file: Path) -> Optional[Message]:
        """Parse legacy chat message format"""
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

    def _parse_legacy_tool_use(self, data: dict, session_file: Path) -> Optional[Message]:
        """Parse legacy function/tool call"""
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
            messages, metadata = self.parse_session(session_file)
            if messages:
                # Use cwd from metadata for project_path if available
                project_path = metadata.get("cwd") or str(session_file.parent)
                project_name = self._extract_project_name(project_path, metadata)

                # Find first real user message (skip system prompts like AGENTS.md)
                first_user_msg = self._find_first_user_message(messages)

                session = Session(
                    id=session_file.stem,
                    project_path=project_path,
                    project_name=project_name,
                    messages=messages,
                    first_message=first_user_msg.content[:100] if first_user_msg else None,
                    created_at=messages[0].timestamp if messages else None,
                    model=metadata.get("model"),
                    effort=metadata.get("effort")
                )
                sessions.append(session)

        return sorted(sessions, key=lambda x: x.created_at or datetime.min, reverse=True)

    def _find_first_user_message(self, messages: list[Message]) -> Optional[Message]:
        """Find first real user message, skipping system prompts.

        Codex CLI v0.115.0+ injects AGENTS.md and environment_context as first user messages.
        These are now marked as 'system' role, so we just find first 'user' message.
        """
        for msg in messages:
            if msg.role == "user":
                return msg
        return messages[0] if messages else None

    def _extract_project_name(self, project_path: str, metadata: dict) -> str:
        """Extract readable project name from path or metadata"""
        if metadata.get("cwd"):
            # Use directory name from cwd
            return Path(metadata["cwd"]).name
        # Fallback to path-based name
        return Path(project_path).name if project_path else "codex"
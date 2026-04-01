# src/viewer/parsers/codex.py
"""Parser for OpenAI Codex CLI conversation history (v0.115.0+)"""
import json
from pathlib import Path
from typing import Optional
from datetime import datetime
from .claude import Message, Session, model_alias


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
        last_input_tokens = 0  # Track context size for compaction headers
        last_zero_total_tokens = 0  # Post-compaction context size
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
                    current_model = model_alias(payload.get("model"))
                    current_effort = payload.get("effort")
                    if current_model:
                        metadata["models"].add(current_model)
                    if current_effort:
                        metadata["efforts"].add(current_effort)
                    continue

                # Handle token count - attribute to last assistant message
                if data.get("type") == "event_msg":
                    last_input_tokens, last_zero_total_tokens = (
                        self._handle_token_event(
                            data, messages, last_assistant_idx,
                            last_input_tokens, last_zero_total_tokens
                        )
                    )
                    continue

                if data.get("type") == "compacted":
                    msg = self._parse_compacted(
                        data, session_file, metadata,
                        last_input_tokens, last_zero_total_tokens
                    )
                    messages.append(msg)
                    last_zero_total_tokens = 0
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

    def _handle_token_event(
        self, data: dict, messages: list[Message],
        last_assistant_idx: Optional[int],
        last_input_tokens: int, last_zero_total_tokens: int
    ) -> tuple[int, int]:
        """Handle token_count event. Returns (last_input_tokens, last_zero_total_tokens)."""
        payload = data.get("payload", {})
        if payload.get("type") != "token_count":
            return last_input_tokens, last_zero_total_tokens

        info = payload.get("info") or {}
        last_usage = info.get("last_token_usage") or {}

        input_tokens = last_usage.get("input_tokens") or 0
        output_tokens = last_usage.get("output_tokens") or 0
        total_tokens = last_usage.get("total_tokens") or 0

        # Track context size for compaction headers
        if input_tokens > 0:
            last_input_tokens = input_tokens

        # Track post-compaction context size (zero i/o but non-zero total)
        if input_tokens == 0 and output_tokens == 0 and total_tokens > 0:
            last_zero_total_tokens = total_tokens
            return last_input_tokens, last_zero_total_tokens

        # Attribute to last assistant message
        if last_assistant_idx is not None and last_assistant_idx < len(messages):
            msg = messages[last_assistant_idx]
            msg.input_tokens = input_tokens
            msg.output_tokens = output_tokens
            msg.cache_read_tokens = last_usage.get("cached_input_tokens") or 0

        return last_input_tokens, last_zero_total_tokens

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

    def _parse_compacted(
        self, data: dict, session_file: Path, metadata: dict,
        pre_tokens: int = 0, post_tokens: int = 0
    ) -> Message:
        """Parse Codex compaction marker into a visible history event."""
        payload = data.get("payload") or {}
        project_path = metadata.get("cwd") or self._extract_project_from_path(session_file)

        return Message(
            role="system",
            content=self._format_compacted_content(payload, pre_tokens, post_tokens),
            uuid=f"compacted-{data.get('timestamp', session_file.stem)}",
            timestamp=self._parse_timestamp(data.get("timestamp")),
            session_id=session_file.stem,
            project_path=project_path,
            message_type="compacted",
            hidden_messages=self._extract_hidden_messages(payload)
        )

    @staticmethod
    def _extract_hidden_messages(payload: dict) -> list[dict]:
        """Extract readable messages from replacement_history."""
        result = []
        for item in payload.get("replacement_history") or []:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            role = item.get("role", "unknown")
            # Normalize developer → system
            if role == "developer":
                role = "system"
            content_list = item.get("content", [])
            if isinstance(content_list, str):
                text = content_list
            else:
                texts = []
                for block in content_list:
                    if isinstance(block, dict):
                        bt = block.get("type", "")
                        if bt in ("input_text", "output_text", "text"):
                            texts.append(block.get("text", ""))
                text = "\n".join(texts)
            if text:
                result.append({"role": role, "content": text[:500]})
        return result or None

    @staticmethod
    def _format_compacted_content(
        payload: dict, pre_tokens: int = 0, post_tokens: int = 0
    ) -> str:
        """Build a short human-readable summary for compaction events."""
        replacement_history = payload.get("replacement_history") or []

        role_counts: dict[str, int] = {}
        for item in replacement_history:
            if isinstance(item, dict) and item.get("type") == "message":
                role = item.get("role", "unknown")
                role_counts[role] = role_counts.get(role, 0) + 1
        message_count = sum(role_counts.values())

        parts = []
        if pre_tokens > 0:
            token_str = CodexParser._format_tokens(pre_tokens)
            if post_tokens > 0:
                token_str += f" → {CodexParser._format_tokens(post_tokens)}"
            parts.append(f"Compacted at {token_str} tokens")
        else:
            parts.append("Compacted")
        if message_count > 0:
            role_detail = CodexParser._format_role_breakdown(role_counts)
            parts.append(f"{message_count} messages hidden{role_detail}")
        header = " · ".join(parts)

        summary = (payload.get("message") or "").strip()
        if summary:
            return f"{header}\n\n{summary}"
        return header

    @staticmethod
    def _format_tokens(tokens: int) -> str:
        if tokens >= 1_000_000:
            return f"{tokens / 1_000_000:.1f}M"
        if tokens >= 1_000:
            return f"{tokens / 1_000:.0f}K"
        return str(tokens)

    @staticmethod
    def _format_role_breakdown(role_counts: dict[str, int]) -> str:
        if not role_counts or len(role_counts) <= 1:
            return ""
        labels = {"user": "user", "developer": "system", "assistant": "assistant"}
        parts = []
        for role in ("user", "assistant", "developer"):
            if role in role_counts:
                parts.append(f"{role_counts[role]} {labels.get(role, role)}")
        return f" ({', '.join(parts)})"

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

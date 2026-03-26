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
    role: str  # user, assistant, system, tool_result
    content: str
    uuid: str
    timestamp: datetime
    session_id: str
    project_path: str
    message_type: str = "text"  # text, thinking, tool_use, tool_result, compacted
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    thinking_text: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    hidden_messages: Optional[list] = None


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
        raw_lines = []

        with open(session_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                raw_lines.append(data)

        # Process and merge streaming chunks
        messages = []
        pending_assistant_chunks = {}  # message_id -> list of chunks
        pending_compact = None  # compact_boundary data awaiting summary

        for data in raw_lines:
            msg_type = data.get("type")

            if msg_type == "system" and data.get("subtype") == "compact_boundary":
                messages.extend(self._flush_assistant_chunks(pending_assistant_chunks))
                pending_assistant_chunks = {}
                pending_compact = {
                    "data": data,
                    "messages_before": len(messages),
                }
                continue

            if msg_type == "assistant":
                # Group by message.id for streaming chunks
                message = data.get("message", {})
                msg_id = message.get("id", "")

                if msg_id:
                    if msg_id not in pending_assistant_chunks:
                        pending_assistant_chunks[msg_id] = []
                    pending_assistant_chunks[msg_id].append(data)
                else:
                    # No message.id, process directly
                    msg = self._parse_assistant_message(data)
                    if msg:
                        messages.append(msg)

            elif msg_type == "user":
                # Flush any pending assistant chunks before user message
                messages.extend(self._flush_assistant_chunks(pending_assistant_chunks))
                pending_assistant_chunks = {}

                # Check if this user message is a compaction summary
                if pending_compact is not None:
                    summary_text = self._extract_user_text(data)
                    if summary_text.startswith("This session is being continued"):
                        messages.append(self._build_compacted_message(
                            pending_compact, summary_text, data
                        ))
                        pending_compact = None
                        continue
                    # Not a summary — emit compacted marker without summary,
                    # then process this user message normally
                    messages.append(self._build_compacted_message(
                        pending_compact, "", data
                    ))
                    pending_compact = None

                msg = self._parse_user_message(data)
                if msg:
                    messages.append(msg)

        # Flush remaining
        if pending_compact is not None:
            messages.append(self._build_compacted_message(pending_compact, "", raw_lines[-1] if raw_lines else {}))
        messages.extend(self._flush_assistant_chunks(pending_assistant_chunks))

        return messages

    def _flush_assistant_chunks(self, chunks: dict) -> list[Message]:
        """Merge streaming chunks into single messages"""
        messages = []

        for msg_id, chunk_list in chunks.items():
            if not chunk_list:
                continue

            # Merge all chunks: combine content, take tokens from last with output
            merged = self._merge_assistant_chunks(chunk_list)
            if merged:
                messages.append(merged)

        return messages

    def _merge_assistant_chunks(self, chunks: list) -> Optional[Message]:
        """Merge multiple streaming chunks into one message"""
        if not chunks:
            return None

        text_parts = []
        thinking_text = None
        tool_name = None
        tool_input = None
        msg_type = "text"

        # Token values from last chunk (most complete)
        input_tokens = 0
        output_tokens = 0
        cache_read_tokens = 0
        cache_creation_tokens = 0

        session_id = ""
        project_path = ""
        timestamp = None
        uuid = ""

        for chunk in chunks:
            message = chunk.get("message", {})
            content_blocks = message.get("content", [])
            usage = message.get("usage", {})

            # Take tokens from chunk with output_tokens (final chunk)
            if usage.get("output_tokens", 0) > 0:
                input_tokens = usage.get("input_tokens", 0) or 0
                output_tokens = usage.get("output_tokens", 0) or 0
                cache_read_tokens = usage.get("cache_read_input_tokens", 0) or 0
                cache_creation_tokens = usage.get("cache_creation_input_tokens", 0) or 0

            # Extract metadata from first chunk
            if not session_id:
                session_id = chunk.get("sessionId", "")
                project_path = chunk.get("cwd", "")
                timestamp = self._parse_timestamp(chunk.get("timestamp"))
                uuid = chunk.get("uuid", "")

            # Merge content blocks
            if isinstance(content_blocks, list):
                for block in content_blocks:
                    block_type = block.get("type", "")

                    if block_type == "text":
                        text = block.get("text", "")
                        if text and text not in text_parts:
                            text_parts.append(text)
                    elif block_type == "thinking":
                        thinking = block.get("thinking", "")
                        if thinking:
                            thinking_text = thinking
                            msg_type = "thinking"
                    elif block_type == "tool_use":
                        tool_name = block.get("name", "")
                        tool_input = block.get("input", {})
                        msg_type = "tool_use"

        # If no output_tokens found, use last chunk's input tokens
        if output_tokens == 0 and chunks:
            last_usage = chunks[-1].get("message", {}).get("usage", {})
            input_tokens = last_usage.get("input_tokens", 0) or 0

        return Message(
            role="assistant",
            content="\n".join(text_parts) if text_parts else "",
            uuid=uuid,
            timestamp=timestamp,
            session_id=session_id,
            project_path=project_path,
            message_type=msg_type,
            tool_name=tool_name,
            tool_input=tool_input,
            thinking_text=thinking_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_creation_tokens=cache_creation_tokens
        )

    def _extract_user_text(self, data: dict) -> str:
        """Extract plain text from a user-type JSONL entry."""
        message = data.get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    parts.append(block)
            return "\n".join(parts)
        return str(content)

    def _build_compacted_message(self, compact_info: dict, summary: str, context_data: dict) -> Message:
        """Create a unified compacted Message from compact_boundary + optional summary."""
        boundary = compact_info["data"]
        metadata = boundary.get("compactMetadata") or {}
        pre_tokens = metadata.get("preTokens") or 0
        trigger = metadata.get("trigger") or "auto"
        messages_before = compact_info["messages_before"]

        header = self._format_compact_header(pre_tokens, trigger, messages_before)
        content = f"{header}\n\n{summary}" if summary else header

        return Message(
            role="system",
            content=content,
            uuid=boundary.get("uuid", ""),
            timestamp=self._parse_timestamp(boundary.get("timestamp")),
            session_id=boundary.get("sessionId") or context_data.get("sessionId", ""),
            project_path=boundary.get("cwd") or context_data.get("cwd", ""),
            message_type="compacted"
        )

    @staticmethod
    def _format_compact_header(pre_tokens: int, trigger: str, messages_before: int) -> str:
        """Build the short header line for a compaction event."""
        if pre_tokens >= 1_000_000:
            tokens_str = f"{pre_tokens / 1_000_000:.1f}M"
        elif pre_tokens >= 1_000:
            tokens_str = f"{pre_tokens / 1_000:.0f}K"
        else:
            tokens_str = str(pre_tokens)

        parts = [f"Compacted at {tokens_str} tokens"]
        parts.append(trigger)
        if messages_before > 0:
            parts.append(f"{messages_before} messages hidden")
        return " · ".join(parts)

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
            tool_results = []

            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        texts.append(block.get("text", ""))
                    elif block.get("type") == "tool_result":
                        # Collect tool results
                        tool_content = block.get("content", "")
                        tool_results.append(str(tool_content) if tool_content else "")
                else:
                    texts.append(str(block))

            # If only tool results (no user text), return as tool_result message
            if tool_results and not texts:
                return Message(
                    role="tool_result",
                    content=tool_results[0],
                    uuid=data.get("uuid", ""),
                    timestamp=self._parse_timestamp(data.get("timestamp")),
                    session_id=data.get("sessionId", ""),
                    project_path=data.get("cwd", ""),
                    message_type="tool_result"
                )

            # If both text and tool results, combine them
            if tool_results:
                texts.extend(tool_results)

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

        # Extract usage data
        usage = message.get("usage", {})
        input_tokens = usage.get("input_tokens", 0) or 0
        output_tokens = usage.get("output_tokens", 0) or 0
        cache_read_tokens = usage.get("cache_read_input_tokens", 0) or 0
        cache_creation_tokens = usage.get("cache_creation_input_tokens", 0) or 0

        if not isinstance(content_blocks, list):
            return Message(
                role="assistant",
                content=str(content_blocks),
                uuid=data.get("uuid", ""),
                timestamp=self._parse_timestamp(data.get("timestamp")),
                session_id=data.get("sessionId", ""),
                project_path=data.get("cwd", ""),
                message_type="text",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read_tokens,
                cache_creation_tokens=cache_creation_tokens
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
            thinking_text=thinking_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_creation_tokens=cache_creation_tokens
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
                # Use directory name as-is (project-id format like "A--ai-dev-history-ai-chat")
                projects.append({
                    "id": project_dir.name,
                    "name": project_dir.name,
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

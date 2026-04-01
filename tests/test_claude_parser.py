# tests/test_claude_parser.py
import json
from pathlib import Path
from viewer.parsers.claude import ClaudeParser, Message, Session


def test_parse_user_message(tmp_path):
    """Test parsing user message from Claude Code JSONL"""
    session_file = tmp_path / "test-session.jsonl"
    session_file.write_text(json.dumps({
        "type": "user",
        "message": {"role": "user", "content": "Hello"},
        "uuid": "user-123",
        "timestamp": "2026-03-16T10:00:00.000Z",
        "sessionId": "session-abc",
        "cwd": "/test/project"
    }) + "\n")

    parser = ClaudeParser()
    messages = parser.parse_session(session_file)

    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].content == "Hello"
    assert messages[0].session_id == "session-abc"


def test_parse_user_message_with_list_content(tmp_path):
    """Test parsing user message with list content (tool results)"""
    session_file = tmp_path / "test-session.jsonl"
    session_file.write_text(json.dumps({
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {"type": "text", "text": "Check this file"},
                {"type": "tool_result", "tool_use_id": "tool-456", "content": "file content"}
            ]
        },
        "uuid": "user-789",
        "timestamp": "2026-03-16T11:00:00.000Z",
        "sessionId": "session-def",
        "cwd": "/test/project"
    }) + "\n")

    parser = ClaudeParser()
    messages = parser.parse_session(session_file)

    assert len(messages) == 1
    assert "Check this file" in messages[0].content
    assert "file content" in messages[0].content  # tool_result content is included


def test_parse_assistant_message(tmp_path):
    """Test parsing assistant message"""
    session_file = tmp_path / "test-session.jsonl"
    session_file.write_text(json.dumps({
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Hello! How can I help you?"}
            ]
        },
        "uuid": "assistant-123",
        "timestamp": "2026-03-16T10:01:00.000Z",
        "sessionId": "session-abc",
        "cwd": "/test/project"
    }) + "\n")

    parser = ClaudeParser()
    messages = parser.parse_session(session_file)

    assert len(messages) == 1
    assert messages[0].role == "assistant"
    assert messages[0].content == "Hello! How can I help you?"
    assert messages[0].message_type == "text"


def test_parse_assistant_message_with_thinking(tmp_path):
    """Test parsing assistant message with thinking block"""
    session_file = tmp_path / "test-session.jsonl"
    session_file.write_text(json.dumps({
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "Let me think about this..."},
                {"type": "text", "text": "Here is my answer."}
            ]
        },
        "uuid": "assistant-456",
        "timestamp": "2026-03-16T10:02:00.000Z",
        "sessionId": "session-abc",
        "cwd": "/test/project"
    }) + "\n")

    parser = ClaudeParser()
    messages = parser.parse_session(session_file)

    assert len(messages) == 1
    assert messages[0].thinking_text == "Let me think about this..."
    assert messages[0].content == "Here is my answer."
    assert messages[0].message_type == "thinking"


def test_parse_assistant_message_with_tool_use(tmp_path):
    """Test parsing assistant message with tool use"""
    session_file = tmp_path / "test-session.jsonl"
    session_file.write_text(json.dumps({
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Let me read that file."},
                {"type": "tool_use", "id": "tool-789", "name": "Read", "input": {"file_path": "/src/main.py"}}
            ]
        },
        "uuid": "assistant-789",
        "timestamp": "2026-03-16T10:03:00.000Z",
        "sessionId": "session-abc",
        "cwd": "/test/project"
    }) + "\n")

    parser = ClaudeParser()
    messages = parser.parse_session(session_file)

    assert len(messages) == 1
    assert messages[0].message_type == "tool_use"
    assert messages[0].tool_name == "Read"
    assert messages[0].tool_input == {"file_path": "/src/main.py"}


def test_parse_multiple_messages(tmp_path):
    """Test parsing multiple messages from one file"""
    session_file = tmp_path / "test-session.jsonl"
    lines = [
        json.dumps({
            "type": "user",
            "message": {"role": "user", "content": "First message"},
            "uuid": "msg-1",
            "timestamp": "2026-03-16T10:00:00.000Z",
            "sessionId": "session-xyz",
            "cwd": "/test"
        }),
        json.dumps({
            "type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "Response"}]},
            "uuid": "msg-2",
            "timestamp": "2026-03-16T10:01:00.000Z",
            "sessionId": "session-xyz",
            "cwd": "/test"
        }),
        json.dumps({
            "type": "user",
            "message": {"role": "user", "content": "Second message"},
            "uuid": "msg-3",
            "timestamp": "2026-03-16T10:02:00.000Z",
            "sessionId": "session-xyz",
            "cwd": "/test"
        })
    ]
    session_file.write_text("\n".join(lines) + "\n")

    parser = ClaudeParser()
    messages = parser.parse_session(session_file)

    assert len(messages) == 3
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"
    assert messages[2].role == "user"


def test_parse_empty_file(tmp_path):
    """Test parsing empty file"""
    session_file = tmp_path / "empty-session.jsonl"
    session_file.write_text("")

    parser = ClaudeParser()
    messages = parser.parse_session(session_file)

    assert len(messages) == 0


def test_parse_timestamp_various_formats(tmp_path):
    """Test parsing various timestamp formats"""
    parser = ClaudeParser()

    # ISO format with Z
    ts1 = parser._parse_timestamp("2026-03-16T10:00:00.000Z")
    assert ts1 is not None

    # Unix timestamp (milliseconds)
    ts2 = parser._parse_timestamp(1710584400000)
    assert ts2 is not None

    # None
    ts3 = parser._parse_timestamp(None)
    assert ts3 is None


def test_parse_compact_boundary_with_summary(tmp_path):
    """compact_boundary + summary user message → single compacted message."""
    session_file = tmp_path / "test-session.jsonl"
    lines = [
        json.dumps({
            "type": "user",
            "message": {"role": "user", "content": "Hello"},
            "uuid": "msg-1", "timestamp": "2026-03-18T22:00:00.000Z",
            "sessionId": "sess-1", "cwd": "/project"
        }),
        json.dumps({
            "type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "Hi!"}]},
            "uuid": "msg-2", "timestamp": "2026-03-18T22:01:00.000Z",
            "sessionId": "sess-1", "cwd": "/project"
        }),
        json.dumps({
            "type": "system", "subtype": "compact_boundary",
            "content": "Conversation compacted",
            "compactMetadata": {"trigger": "auto", "preTokens": 167648},
            "uuid": "compact-1", "timestamp": "2026-03-18T22:46:39.715Z",
            "sessionId": "sess-1", "cwd": "/project"
        }),
        json.dumps({
            "type": "user",
            "message": {"role": "user", "content": "This session is being continued from a previous conversation.\n\nSummary:\n1. We discussed X."},
            "uuid": "msg-3", "timestamp": "2026-03-18T22:46:40.000Z",
            "sessionId": "sess-1", "cwd": "/project"
        }),
        json.dumps({
            "type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "Continuing..."}]},
            "uuid": "msg-4", "timestamp": "2026-03-18T22:47:00.000Z",
            "sessionId": "sess-1", "cwd": "/project"
        }),
    ]
    session_file.write_text("\n".join(lines) + "\n")

    parser = ClaudeParser()
    messages = parser.parse_session(session_file)

    # user + assistant + compacted + assistant (summary absorbed into compacted)
    assert len(messages) == 4
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"

    compacted = messages[2]
    assert compacted.role == "system"
    assert compacted.message_type == "compacted"
    assert "168K tokens" in compacted.content
    assert "auto" in compacted.content
    assert "2 messages hidden" in compacted.content
    assert "This session is being continued" in compacted.content

    assert messages[3].role == "assistant"
    assert messages[3].content == "Continuing..."


def test_parse_compact_boundary_without_summary(tmp_path):
    """compact_boundary followed by a normal user message (not a summary)."""
    session_file = tmp_path / "test-session.jsonl"
    lines = [
        json.dumps({
            "type": "user",
            "message": {"role": "user", "content": "First"},
            "uuid": "msg-1", "timestamp": "2026-03-18T22:00:00.000Z",
            "sessionId": "sess-1", "cwd": "/project"
        }),
        json.dumps({
            "type": "system", "subtype": "compact_boundary",
            "content": "Conversation compacted",
            "compactMetadata": {"trigger": "manual", "preTokens": 50000},
            "uuid": "compact-1", "timestamp": "2026-03-18T22:10:00.000Z",
            "sessionId": "sess-1", "cwd": "/project"
        }),
        json.dumps({
            "type": "user",
            "message": {"role": "user", "content": "A normal follow-up question"},
            "uuid": "msg-2", "timestamp": "2026-03-18T22:11:00.000Z",
            "sessionId": "sess-1", "cwd": "/project"
        }),
    ]
    session_file.write_text("\n".join(lines) + "\n")

    parser = ClaudeParser()
    messages = parser.parse_session(session_file)

    # user + compacted (no summary) + user
    assert len(messages) == 3
    compacted = messages[1]
    assert compacted.message_type == "compacted"
    assert "50K tokens" in compacted.content
    assert "manual" in compacted.content
    assert "1 messages hidden" in compacted.content

    assert messages[2].role == "user"
    assert messages[2].content == "A normal follow-up question"


def test_format_compact_header():
    """Header formatting for various token sizes."""
    assert ClaudeParser._format_compact_header(167648, "auto", 42) == \
        "Compacted at 168K tokens · auto · 42 messages hidden"
    assert ClaudeParser._format_compact_header(1_500_000, "manual", 0) == \
        "Compacted at 1.5M tokens · manual"
    assert ClaudeParser._format_compact_header(500, "auto", 5) == \
        "Compacted at 500 tokens · auto · 5 messages hidden"
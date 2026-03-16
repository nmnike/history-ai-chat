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
    assert "[Tool Result: tool-456]" in messages[0].content


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
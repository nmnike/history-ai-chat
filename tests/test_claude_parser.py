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
    messages, _ = parser.parse_session(session_file)

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
    messages, _ = parser.parse_session(session_file)

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
    messages, _ = parser.parse_session(session_file)

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
    messages, _ = parser.parse_session(session_file)

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
    messages, _ = parser.parse_session(session_file)

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
    messages, _ = parser.parse_session(session_file)

    assert len(messages) == 3
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"
    assert messages[2].role == "user"


def test_parse_empty_file(tmp_path):
    """Test parsing empty file"""
    session_file = tmp_path / "empty-session.jsonl"
    session_file.write_text("")

    parser = ClaudeParser()
    messages, _ = parser.parse_session(session_file)

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


def test_parse_custom_title(tmp_path):
    """Test that custom-title is extracted into session metadata"""
    import json
    session_file = tmp_path / "session.jsonl"
    session_file.write_text(
        json.dumps({"type": "user", "uuid": "u1", "timestamp": "2026-03-17T10:00:00Z",
                    "sessionId": "s1", "cwd": "/p",
                    "message": {"role": "user", "content": "Hello"}}) + "\n" +
        json.dumps({"type": "custom-title", "customTitle": "My Session",
                    "sessionId": "s1"}) + "\n"
    )

    parser = ClaudeParser()
    messages, metadata = parser.parse_session(session_file)

    assert metadata["custom_title"] == "My Session"


def test_parse_assistant_model(tmp_path):
    """Test that model is extracted from assistant messages, synthetic filtered, alias applied"""
    import json
    session_file = tmp_path / "session.jsonl"
    session_file.write_text(
        json.dumps({"type": "assistant", "uuid": "a1", "timestamp": "2026-03-17T10:00:00Z",
                    "sessionId": "s1", "cwd": "/p",
                    "message": {"id": "msg1", "role": "assistant", "model": "claude-opus-4-6",
                                "content": [{"type": "text", "text": "Hi"}],
                                "usage": {"input_tokens": 10, "output_tokens": 5}}}) + "\n" +
        json.dumps({"type": "assistant", "uuid": "a2", "timestamp": "2026-03-17T10:00:01Z",
                    "sessionId": "s1", "cwd": "/p",
                    "message": {"id": "msg2", "role": "assistant", "model": "<synthetic>",
                                "content": [{"type": "text", "text": "Think"}],
                                "usage": {"input_tokens": 0, "output_tokens": 0}}}) + "\n"
    )

    parser = ClaudeParser()
    messages, metadata = parser.parse_session(session_file)

    assert metadata["model"] == "Opus 4.6"
    assistant_msgs = [m for m in messages if m.role == "assistant" and m.model]
    assert any(m.model == "Opus 4.6" for m in assistant_msgs)
    # synthetic should be filtered
    assert not any(m.model == "<synthetic>" for m in messages)


def test_parse_effort_from_model_command(tmp_path):
    """Test that effort is extracted from /model command output in user events"""
    session_file = tmp_path / "session.jsonl"
    # Real format: content is a string with <local-command-stdout> tag and ANSI codes
    model_command_event = {
        "type": "user",
        "uuid": "u2",
        "timestamp": "2026-03-27T10:00:00Z",
        "sessionId": "s1",
        "cwd": "/p",
        "message": {
            "role": "user",
            "content": "<local-command-stdout>Set model to \x1b[1mSonnet 4.6 (default)\x1b[22m with high effort</local-command-stdout>"
        }
    }
    assistant_event = {
        "type": "assistant",
        "uuid": "a1",
        "timestamp": "2026-03-27T10:00:01Z",
        "sessionId": "s1",
        "cwd": "/p",
        "message": {
            "id": "msg1",
            "role": "assistant",
            "model": "claude-sonnet-4-6",
            "content": [{"type": "text", "text": "Response after effort set"}],
            "usage": {"input_tokens": 10, "output_tokens": 5}
        }
    }
    session_file.write_text(
        json.dumps(model_command_event) + "\n" +
        json.dumps(assistant_event) + "\n"
    )

    parser = ClaudeParser()
    messages, metadata = parser.parse_session(session_file)

    assert metadata["effort"] == "high"
    assistant_msgs = [m for m in messages if m.role == "assistant"]
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0].effort == "high"


def test_parse_effort_none_when_no_model_command(tmp_path):
    """Test that effort is None when no /model command is present"""
    session_file = tmp_path / "session.jsonl"
    session_file.write_text(
        json.dumps({
            "type": "assistant", "uuid": "a1", "timestamp": "2026-03-27T10:00:00Z",
            "sessionId": "s1", "cwd": "/p",
            "message": {"id": "msg1", "role": "assistant", "model": "claude-sonnet-4-6",
                        "content": [{"type": "text", "text": "Hi"}],
                        "usage": {"input_tokens": 5, "output_tokens": 3}}
        }) + "\n"
    )

    parser = ClaudeParser()
    messages, metadata = parser.parse_session(session_file)

    assert metadata["effort"] is None
    assert all(m.effort is None for m in messages if m.role == "assistant")
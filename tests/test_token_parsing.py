# tests/test_token_parsing.py
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from viewer.parsers.claude import ClaudeParser


def test_parse_assistant_message_with_tokens(tmp_path):
    """Test that token usage is extracted from assistant messages"""
    session_file = tmp_path / "test-session.jsonl"
    session_file.write_text(json.dumps({
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello"}],
            "usage": {
                "input_tokens": 1000,
                "output_tokens": 50,
                "cache_read_input_tokens": 200,
                "cache_creation_input_tokens": 10
            }
        },
        "uuid": "test-uuid",
        "timestamp": "2026-03-17T10:00:00Z",
        "sessionId": "test-session",
        "cwd": "/test"
    }) + "\n")

    parser = ClaudeParser(str(tmp_path))
    messages, _ = parser.parse_session(session_file)

    assert len(messages) == 1
    assert messages[0].input_tokens == 1000
    assert messages[0].output_tokens == 50
    assert messages[0].cache_read_tokens == 200
    assert messages[0].cache_creation_tokens == 10


def test_parse_message_without_usage(tmp_path):
    """Test that messages without usage default to 0 tokens"""
    session_file = tmp_path / "test-session.jsonl"
    session_file.write_text(json.dumps({
        "type": "user",
        "message": {
            "role": "user",
            "content": "Hello"
        },
        "uuid": "test-uuid",
        "timestamp": "2026-03-17T10:00:00Z",
        "sessionId": "test-session",
        "cwd": "/test"
    }) + "\n")

    parser = ClaudeParser(str(tmp_path))
    messages, _ = parser.parse_session(session_file)

    assert len(messages) == 1
    assert messages[0].input_tokens == 0
    assert messages[0].output_tokens == 0


def test_parse_message_with_missing_usage_fields(tmp_path):
    """Test partial usage data"""
    session_file = tmp_path / "test-session.jsonl"
    session_file.write_text(json.dumps({
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello"}],
            "usage": {
                "input_tokens": 1000,
                "output_tokens": 50
                # cache fields missing
            }
        },
        "uuid": "test-uuid",
        "timestamp": "2026-03-17T10:00:00Z",
        "sessionId": "test-session",
        "cwd": "/test"
    }) + "\n")

    parser = ClaudeParser(str(tmp_path))
    messages, _ = parser.parse_session(session_file)

    assert messages[0].input_tokens == 1000
    assert messages[0].output_tokens == 50
    assert messages[0].cache_read_tokens == 0
    assert messages[0].cache_creation_tokens == 0


def test_parse_assistant_message_with_tool_use_and_tokens(tmp_path):
    """Test token extraction with tool_use message type"""
    session_file = tmp_path / "test-session.jsonl"
    session_file.write_text(json.dumps({
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "/test"}}],
            "usage": {
                "input_tokens": 500,
                "output_tokens": 100
            }
        },
        "uuid": "test-uuid",
        "timestamp": "2026-03-17T10:00:00Z",
        "sessionId": "test-session",
        "cwd": "/test"
    }) + "\n")

    parser = ClaudeParser(str(tmp_path))
    messages, _ = parser.parse_session(session_file)

    assert len(messages) == 1
    assert messages[0].input_tokens == 500
    assert messages[0].output_tokens == 100
    assert messages[0].tool_name == "Read"
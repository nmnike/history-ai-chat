# tests/test_codex_parser.py
import json
from pathlib import Path
from viewer.parsers.codex import CodexParser

def test_parse_codex_session(tmp_path):
    """Test parsing Codex CLI rollout JSONL (legacy format)"""
    session_file = tmp_path / "rollout-test.jsonl"
    session_file.write_text(json.dumps({
        "type": "message",
        "role": "user",
        "content": "Write a hello world",
        "timestamp": "2026-03-16T10:00:00Z"
    }) + "\n")

    parser = CodexParser()
    messages, metadata = parser.parse_session(session_file)

    assert len(messages) == 1
    assert messages[0].role == "user"


def test_parse_codex_v115_format(tmp_path):
    """Test parsing Codex CLI v0.115.0+ format"""
    session_file = tmp_path / "rollout-v115.jsonl"
    session_file.write_text(
        json.dumps({
            "type": "session_meta",
            "payload": {
                "cwd": "/home/user/project",
                "cli_version": "0.115.0"
            }
        }) + "\n" +
        json.dumps({
            "type": "response_item",
            "timestamp": "2026-03-17T10:00:00Z",
            "payload": {
                "role": "user",
                "content": [{"type": "input_text", "text": "Hello"}]
            }
        }) + "\n" +
        json.dumps({
            "type": "response_item",
            "timestamp": "2026-03-17T10:00:05Z",
            "payload": {
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Hi there!"}]
            }
        }) + "\n"
    )

    parser = CodexParser()
    messages, metadata = parser.parse_session(session_file)

    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "Hello"
    assert messages[1].role == "assistant"
    assert messages[1].content == "Hi there!"
    assert metadata["cwd"] == "/home/user/project"
    assert metadata["cli_version"] == "0.115.0"


def test_first_message_skips_system_prompts(tmp_path):
    """Test that first_message skips AGENTS.md and environment_context"""
    session_file = tmp_path / "rollout-skip-system.jsonl"
    session_file.write_text(
        json.dumps({
            "type": "session_meta",
            "payload": {"cwd": "/project"}
        }) + "\n" +
        json.dumps({
            "type": "response_item",
            "timestamp": "2026-03-17T10:00:00Z",
            "payload": {
                "role": "user",
                "content": [{"type": "input_text", "text": "# AGENTS.md instructions for /project\n<INSTRUCTIONS>\n..."}]
            }
        }) + "\n" +
        json.dumps({
            "type": "response_item",
            "timestamp": "2026-03-17T10:00:01Z",
            "payload": {
                "role": "user",
                "content": [{"type": "input_text", "text": "<environment_context>\n<cwd>/project</cwd>"}]
            }
        }) + "\n" +
        json.dumps({
            "type": "response_item",
            "timestamp": "2026-03-17T10:00:02Z",
            "payload": {
                "role": "user",
                "content": [{"type": "input_text", "text": "What is the project about?"}]
            }
        }) + "\n"
    )

    # Use tmp_path as sessions directory
    parser = CodexParser(sessions_path=str(tmp_path))
    sessions = parser.get_sessions()

    assert len(sessions) == 1
    # Should show actual question, not AGENTS.md
    assert sessions[0].first_message == "What is the project about?"


def test_system_messages_get_system_role(tmp_path):
    """Test that AGENTS.md messages are marked as 'system' not 'user'"""
    session_file = tmp_path / "rollout-system-role.jsonl"
    session_file.write_text(
        json.dumps({
            "type": "response_item",
            "timestamp": "2026-03-17T10:00:00Z",
            "payload": {
                "role": "user",
                "content": [{"type": "input_text", "text": "# AGENTS.md instructions for /project\n..."}]
            }
        }) + "\n" +
        json.dumps({
            "type": "response_item",
            "timestamp": "2026-03-17T10:00:01Z",
            "payload": {
                "role": "user",
                "content": [{"type": "input_text", "text": "<environment_context>\n..."}]
            }
        }) + "\n" +
        json.dumps({
            "type": "response_item",
            "timestamp": "2026-03-17T10:00:02Z",
            "payload": {
                "role": "user",
                "content": [{"type": "input_text", "text": "Real question"}]
            }
        }) + "\n"
    )

    parser = CodexParser(sessions_path=str(tmp_path))
    messages, _ = parser.parse_session(session_file)

    assert len(messages) == 3
    assert messages[0].role == "system"  # AGENTS.md
    assert messages[1].role == "system"  # environment_context
    assert messages[2].role == "user"    # real question


def test_token_parsing(tmp_path):
    """Test that tokens are extracted from token_count events"""
    session_file = tmp_path / "rollout-tokens.jsonl"
    session_file.write_text(
        json.dumps({
            "type": "response_item",
            "timestamp": "2026-03-17T10:00:00Z",
            "payload": {
                "role": "user",
                "content": [{"type": "input_text", "text": "Hello"}]
            }
        }) + "\n" +
        json.dumps({
            "type": "response_item",
            "timestamp": "2026-03-17T10:00:05Z",
            "payload": {
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Hi there!"}]
            }
        }) + "\n" +
        json.dumps({
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "last_token_usage": {
                        "input_tokens": 1000,
                        "output_tokens": 50,
                        "cached_input_tokens": 200
                    }
                }
            }
        }) + "\n"
    )

    parser = CodexParser(sessions_path=str(tmp_path))
    messages, _ = parser.parse_session(session_file)

    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].input_tokens == 0  # No tokens for user

    assert messages[1].role == "assistant"
    assert messages[1].input_tokens == 1000
    assert messages[1].output_tokens == 50
    assert messages[1].cache_read_tokens == 200
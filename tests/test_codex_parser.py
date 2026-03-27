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


def test_turn_context_model_effort(tmp_path):
    """Test that model and effort are extracted from turn_context events"""
    session_file = tmp_path / "rollout-model.jsonl"
    session_file.write_text(
        json.dumps({
            "type": "turn_context",
            "payload": {
                "turn_id": "turn-1",
                "model": "o3",
                "effort": "medium",
                "cwd": "/project"
            }
        }) + "\n" +
        json.dumps({
            "type": "turn_context",
            "payload": {
                "turn_id": "turn-2",
                "model": "o3-mini",
                "effort": "high",
                "cwd": "/project"
            }
        }) + "\n" +
        json.dumps({
            "type": "response_item",
            "timestamp": "2026-03-17T10:00:00Z",
            "payload": {
                "role": "user",
                "content": [{"type": "input_text", "text": "Hello"}]
            }
        }) + "\n"
    )

    parser = CodexParser(sessions_path=str(tmp_path))
    messages, metadata = parser.parse_session(session_file)

    # Both models collected; sorted join
    assert metadata["model"] == "o3, o3-mini"
    assert metadata["effort"] == "high, medium"

    # Assistant message gets model from its preceding turn_context
    # (no assistant message in this file, but verify session-level)
    sessions = parser.get_sessions()
    assert len(sessions) == 1
    assert sessions[0].model == "o3, o3-mini"
    assert sessions[0].effort == "high, medium"


def test_per_message_model_effort(tmp_path):
    """Test that each assistant message gets model/effort from preceding turn_context"""
    session_file = tmp_path / "rollout-per-msg.jsonl"
    session_file.write_text(
        json.dumps({
            "type": "turn_context",
            "payload": {"turn_id": "t1", "model": "o3", "effort": "medium"}
        }) + "\n" +
        json.dumps({
            "type": "response_item",
            "timestamp": "2026-03-17T10:00:00Z",
            "payload": {"role": "user", "content": [{"type": "input_text", "text": "Q1"}]}
        }) + "\n" +
        json.dumps({
            "type": "response_item",
            "timestamp": "2026-03-17T10:00:01Z",
            "payload": {"role": "assistant", "content": [{"type": "output_text", "text": "A1"}]}
        }) + "\n" +
        json.dumps({
            "type": "turn_context",
            "payload": {"turn_id": "t2", "model": "o3-mini", "effort": "high"}
        }) + "\n" +
        json.dumps({
            "type": "response_item",
            "timestamp": "2026-03-17T10:00:02Z",
            "payload": {"role": "user", "content": [{"type": "input_text", "text": "Q2"}]}
        }) + "\n" +
        json.dumps({
            "type": "response_item",
            "timestamp": "2026-03-17T10:00:03Z",
            "payload": {"role": "assistant", "content": [{"type": "output_text", "text": "A2"}]}
        }) + "\n"
    )

    parser = CodexParser()
    messages, metadata = parser.parse_session(session_file)

    assistant_msgs = [m for m in messages if m.role == "assistant"]
    assert len(assistant_msgs) == 2
    assert assistant_msgs[0].model == "o3"
    assert assistant_msgs[0].effort == "medium"
    assert assistant_msgs[1].model == "o3-mini"
    assert assistant_msgs[1].effort == "high"

    # Session-level: both models
    assert metadata["model"] == "o3, o3-mini"
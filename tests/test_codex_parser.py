# tests/test_codex_parser.py
import json
from pathlib import Path
from viewer.parsers.codex import CodexParser

def test_parse_codex_session(tmp_path):
    """Test parsing Codex CLI rollout JSONL"""
    session_file = tmp_path / "rollout-test.jsonl"
    session_file.write_text(json.dumps({
        "type": "message",
        "role": "user",
        "content": "Write a hello world",
        "timestamp": "2026-03-16T10:00:00Z"
    }) + "\n")

    parser = CodexParser()
    messages = parser.parse_session(session_file)

    assert len(messages) == 1
    assert messages[0].role == "user"
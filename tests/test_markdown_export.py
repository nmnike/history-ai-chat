import pytest
from datetime import datetime
from viewer.parsers.claude import Session, Message
from viewer.main import format_token_count, export_to_markdown


@pytest.mark.parametrize("value,expected", [
    (500, "500"),
    (1000, "1.0K"),
    (1500, "1.5K"),
    (1000000, "1.0M"),
    (2500000, "2.5M"),
])
def test_format_token_count(value, expected):
    assert format_token_count(value) == expected


def make_session(messages=None, created_at=None):
    """Helper to create test sessions"""
    return Session(
        id="test-session-123",
        project_path="/test/path",
        project_name="test-project",
        messages=messages or [],
        created_at=created_at
    )


def make_message(role, content="", **kwargs):
    """Helper to create test messages"""
    return Message(
        role=role,
        content=content,
        uuid="test-uuid",
        timestamp=kwargs.get("timestamp", datetime(2026, 3, 17, 14, 30, 0)),
        session_id="test-session-123",
        project_path="/test/path",
        **{k: v for k, v in kwargs.items() if k != "timestamp"}
    )


def test_export_markdown_stats_header():
    messages = [
        make_message("user", "Hello", input_tokens=100),
        make_message("assistant", "Hi there!", output_tokens=50, input_tokens=200),
        make_message("assistant", "Let me help", tool_name="Read", input_tokens=300, output_tokens=100),
    ]
    session = make_session(messages=messages, created_at=datetime(2026, 3, 17, 14, 30))

    result = export_to_markdown(session)

    # Check stats line format
    assert "👤 1" in result  # 1 user message
    assert "🤖 2" in result  # 2 assistant messages
    assert "🔧 1 tool calls" in result  # 1 tool call
    assert "600/150 tokens" in result  # total input/output
    assert "cache:" in result
    assert "**Created:** 2026-03-17 14:30" in result

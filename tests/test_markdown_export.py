import pytest
from datetime import datetime, timezone, timedelta
from viewer.parsers.claude import Session, Message
from viewer.main import format_token_count, export_to_markdown, to_local_datetime


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

    # Check messages line format with tool breakdown
    assert "👤 1 user" in result  # 1 user message
    assert "🤖 2 assistant" in result  # 2 assistant messages
    assert "🔧 1 tool calls (Read: 1)" in result  # tool count with breakdown
    # Check timing format
    assert "**Timing:**" in result
    assert "Start: 2026-03-17 14:30" in result
    # Check tokens section
    assert "**Tokens:**" in result
    assert "600" in result  # total input
    assert "150" in result  # total output


def test_export_markdown_tool_breakdown():
    """Tool breakdown shows multiple tools sorted by count"""
    messages = [
        make_message("user", "Hello"),
        make_message("assistant", "A", tool_name="Read"),
        make_message("assistant", "B", tool_name="Bash"),
        make_message("assistant", "C", tool_name="Read"),
        make_message("assistant", "D", tool_name="Edit"),
        make_message("assistant", "E", tool_name="Bash"),
        make_message("assistant", "F", tool_name="Read"),
    ]
    session = make_session(messages=messages)
    result = export_to_markdown(session)

    # 6 tool calls with breakdown, sorted by count descending
    assert "🔧 6 tool calls (Read: 3, Bash: 2, Edit: 1)" in result


def test_export_markdown_message_timestamp():
    messages = [
        make_message("user", "Hello", timestamp=datetime(2026, 3, 17, 14, 30, 5)),
        make_message("assistant", "Hi!", timestamp=datetime(2026, 3, 17, 14, 30, 10), input_tokens=100, output_tokens=50),
    ]
    session = make_session(messages=messages)

    result = export_to_markdown(session)

    assert "### User • 14:30:05" in result
    assert "### Assistant • 14:30:10 • 100/50 tokens" in result


def test_export_markdown_message_no_timestamp():
    messages = [
        make_message("user", "Hello", timestamp=None),
    ]
    session = make_session(messages=messages)

    result = export_to_markdown(session)

    assert "### User\n" in result  # No time suffix


def test_export_markdown_message_no_tokens():
    messages = [
        make_message("assistant", "Hi!", timestamp=datetime(2026, 3, 17, 14, 30, 0)),
    ]
    session = make_session(messages=messages)

    result = export_to_markdown(session)

    assert "### Assistant • 14:30:00\n" in result  # No token badge


def test_export_markdown_created_at_unknown():
    """When created_at is None, show 'Unknown' in Timing"""
    session = make_session(messages=[], created_at=None)
    result = export_to_markdown(session)
    assert "**Timing:** Start: Unknown" in result


def test_export_markdown_tool_result_not_counted():
    """tool_result messages excluded from user_count and tool_calls"""
    messages = [
        make_message("user", "Hello"),
        make_message("tool_result", "result data"),
        make_message("assistant", "Hi", tool_name="Read"),
    ]
    session = make_session(messages=messages)
    result = export_to_markdown(session)
    assert "👤 1 user" in result  # tool_result excluded from user count
    assert "🤖 1 assistant" in result
    assert "🔧 1 tool calls (Read: 1)" in result  # tool_result not counted as tool call


def test_export_markdown_empty_tool_input():
    """Empty tool_input omits JSON block"""
    messages = [
        make_message("assistant", "Done", tool_name="Bash", tool_input={}),
    ]
    session = make_session(messages=messages)
    result = export_to_markdown(session)
    assert "**Tool: Bash**\n" in result  # No JSON block after tool name


def test_export_markdown_compacted_label():
    """Compaction events should have a dedicated label in export."""
    messages = [
        make_message(
            "system",
            "Codex compacted earlier context to save space in the active session.",
            message_type="compacted",
            timestamp=datetime(2026, 3, 17, 14, 30, 0)
        ),
    ]
    session = make_session(messages=messages)

    result = export_to_markdown(session)

    assert "### Context Compacted • 14:30:00" in result


def test_to_local_datetime_utc_conversion():
    """UTC datetime should be converted to local timezone"""
    # Create a UTC datetime
    utc_dt = datetime(2026, 3, 17, 11, 30, 0, tzinfo=timezone.utc)
    local_dt = to_local_datetime(utc_dt)

    # Should be timezone-aware after conversion
    assert local_dt.tzinfo is not None
    # Hour should differ by timezone offset (e.g., MSK is UTC+3, so 11 UTC -> 14 local)
    # We just check it's converted, not the exact value (depends on local TZ)


def test_to_local_datetime_naive_passthrough():
    """Naive datetime should pass through unchanged"""
    naive_dt = datetime(2026, 3, 17, 14, 30, 0)
    result = to_local_datetime(naive_dt)
    assert result == naive_dt
    assert result.tzinfo is None


def test_to_local_datetime_none():
    """None should return None"""
    assert to_local_datetime(None) is None

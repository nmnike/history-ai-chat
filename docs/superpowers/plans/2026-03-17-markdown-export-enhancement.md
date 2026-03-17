# Markdown Export Enhancement Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance Markdown export with session statistics header and per-message metadata (timestamps, tokens).

**Architecture:** Modify `export_to_markdown()` function to calculate aggregate stats before message loop, add helper function `format_token_count()` for consistent token formatting. Tests verify each output format.

**Tech Stack:** Python 3.13, pytest, dataclasses

---

## Task 1: Add format_token_count helper function

**Files:**
- Modify: `src/viewer/main.py` (add helper near export functions)
- Create: `tests/test_markdown_export.py`

- [ ] **Step 1: Write failing test for format_token_count**

```python
# tests/test_markdown_export.py
import pytest
from viewer.main import format_token_count


@pytest.mark.parametrize("value,expected", [
    (500, "500"),
    (1000, "1.0K"),
    (1500, "1.5K"),
    (1000000, "1.0M"),
    (2500000, "2.5M"),
])
def test_format_token_count(value, expected):
    assert format_token_count(value) == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_markdown_export.py -v`
Expected: FAIL with "cannot import name 'format_token_count'"

- [ ] **Step 3: Implement format_token_count**

Add to `src/viewer/main.py` before `export_to_markdown`:

```python
def format_token_count(n: int) -> str:
    """Format token count with K/M suffix"""
    if n >= 1000000:
        return f"{round(n/1000000, 1)}M"
    if n >= 1000:
        return f"{round(n/1000, 1)}K"
    return str(n)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_markdown_export.py::test_format_token_count -v`
Expected: PASS (5 parametrized cases)

- [ ] **Step 5: Commit**

```bash
git add src/viewer/main.py tests/test_markdown_export.py
git commit -m "feat: add format_token_count helper for markdown export"
```

---

## Task 2: Add session statistics header

**Files:**
- Modify: `src/viewer/main.py`
- Modify: `tests/test_markdown_export.py`

- [ ] **Step 1: Write failing test for stats header**

Add to `tests/test_markdown_export.py`:

```python
from datetime import datetime
from viewer.parsers.claude import Session, Message


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

    from viewer.main import export_to_markdown
    result = export_to_markdown(session)

    # Check stats line format
    assert "👤 1" in result  # 1 user message
    assert "🤖 2" in result  # 2 assistant messages
    assert "🔧 1 tool calls" in result  # 1 tool call
    assert "600/150 tokens" in result  # total input/output
    assert "cache:" in result
    assert "**Created:** 2026-03-17 14:30" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_markdown_export.py::test_export_markdown_stats_header -v`
Expected: FAIL (stats line not present)

- [ ] **Step 3: Implement stats calculation and header**

Replace `export_to_markdown` in `src/viewer/main.py`:

```python
def export_to_markdown(session: Session) -> str:
    """Export session to Markdown format"""
    # Calculate aggregate statistics
    user_count = sum(1 for m in session.messages if m.role == "user")
    assistant_count = sum(1 for m in session.messages if m.role == "assistant")
    tool_calls = sum(1 for m in session.messages if m.tool_name)

    total_input = sum(m.input_tokens for m in session.messages)
    total_output = sum(m.output_tokens for m in session.messages)
    total_cache_read = sum(m.cache_read_tokens for m in session.messages)
    total_cache_created = sum(m.cache_creation_tokens for m in session.messages)

    # Format created_at
    created_str = session.created_at.strftime("%Y-%m-%d %H:%M") if session.created_at else "Unknown"

    # Build stats line
    stats = f"👤 {user_count} • 🤖 {assistant_count} • 🔧 {tool_calls} tool calls • {format_token_count(total_input)}/{format_token_count(total_output)} tokens (cache: {format_token_count(total_cache_read)} read, {format_token_count(total_cache_created)} created)"

    lines = [
        f"# Conversation: {session.id}",
        f"\n**Project:** {session.project_name}",
        f"**Created:** {created_str}",
        f"**Stats:** {stats}",
        "\n---\n"
    ]

    for msg in session.messages:
        if msg.role == "tool_result":
            # Tool result - wrap in code block
            lines.append(f"\n### Tool Result\n")
            if msg.content:
                lines.append(f"```\n{msg.content}\n```")
        elif msg.role == "user":
            lines.append(f"\n### User\n")
            if msg.content:
                lines.append(msg.content)
        else:
            # Assistant
            lines.append(f"\n### Assistant\n")
            if msg.content:
                lines.append(msg.content)
            if msg.thinking_text:
                lines.append(f"\n*Thinking:*\n```\n{msg.thinking_text}\n```")
            if msg.tool_name:
                tool_input = ""
                if msg.tool_input:
                    tool_input = f"\n```json\n{json.dumps(msg.tool_input, indent=2, ensure_ascii=False)}\n```"
                lines.append(f"\n**Tool: {msg.tool_name}**{tool_input}")
        lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_markdown_export.py::test_export_markdown_stats_header -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/viewer/main.py tests/test_markdown_export.py
git commit -m "feat: add session statistics header to markdown export"
```

---

## Task 3: Add per-message timestamp and token badge

**Files:**
- Modify: `src/viewer/main.py`
- Modify: `tests/test_markdown_export.py`

- [ ] **Step 1: Write failing test for message metadata**

Add to `tests/test_markdown_export.py`:

```python
def test_export_markdown_message_timestamp():
    messages = [
        make_message("user", "Hello", timestamp=datetime(2026, 3, 17, 14, 30, 5)),
        make_message("assistant", "Hi!", timestamp=datetime(2026, 3, 17, 14, 30, 10), input_tokens=100, output_tokens=50),
    ]
    session = make_session(messages=messages)

    from viewer.main import export_to_markdown
    result = export_to_markdown(session)

    assert "### User • 14:30:05" in result
    assert "### Assistant • 14:30:10 • 100/50 tokens" in result


def test_export_markdown_message_no_timestamp():
    messages = [
        make_message("user", "Hello", timestamp=None),
    ]
    session = make_session(messages=messages)

    from viewer.main import export_to_markdown
    result = export_to_markdown(session)

    assert "### User\n" in result  # No time suffix


def test_export_markdown_message_no_tokens():
    messages = [
        make_message("assistant", "Hi!", timestamp=datetime(2026, 3, 17, 14, 30, 0)),
    ]
    session = make_session(messages=messages)

    from viewer.main import export_to_markdown
    result = export_to_markdown(session)

    assert "### Assistant • 14:30:00\n" in result  # No token badge
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_markdown_export.py -k "message_timestamp or message_no" -v`
Expected: FAIL (timestamps not in output)

- [ ] **Step 3: Implement timestamp and token badge**

Update the message rendering loop in `export_to_markdown`:

```python
    for msg in session.messages:
        if msg.role == "tool_result":
            # Tool result - no timestamp per spec
            lines.append(f"\n### Tool Result\n")
            if msg.content:
                lines.append(f"```\n{msg.content}\n```")
        else:
            # Format timestamp for user/assistant
            time_str = f" • {msg.timestamp.strftime('%H:%M:%S')}" if msg.timestamp else ""

            if msg.role == "user":
                lines.append(f"\n### User{time_str}\n")
                if msg.content:
                    lines.append(msg.content)
            else:
                # Assistant - add token badge if tokens present
                token_str = ""
                if msg.input_tokens > 0 or msg.output_tokens > 0:
                    token_str = f" • {format_token_count(msg.input_tokens)}/{format_token_count(msg.output_tokens)} tokens"

                lines.append(f"\n### Assistant{time_str}{token_str}\n")
                if msg.content:
                    lines.append(msg.content)
                if msg.thinking_text:
                    lines.append(f"\n*Thinking:*\n```\n{msg.thinking_text}\n```")
                if msg.tool_name:
                    tool_input = ""
                    if msg.tool_input:
                        tool_input = f"\n```json\n{json.dumps(msg.tool_input, indent=2, ensure_ascii=False)}\n```"
                    lines.append(f"\n**Tool: {msg.tool_name}**{tool_input}")
        lines.append("")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_markdown_export.py -k "message_timestamp or message_no" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/viewer/main.py tests/test_markdown_export.py
git commit -m "feat: add timestamp and token badge to markdown export messages"
```

---

## Task 4: Add edge case tests

**Files:**
- Modify: `tests/test_markdown_export.py`

- [ ] **Step 1: Write edge case tests**

Add to `tests/test_markdown_export.py`:

```python
def test_export_markdown_created_at_unknown():
    """When created_at is None, show 'Unknown'"""
    session = make_session(messages=[], created_at=None)
    result = export_to_markdown(session)
    assert "**Created:** Unknown" in result


def test_export_markdown_tool_result_not_counted():
    """tool_result messages excluded from user_count and tool_calls"""
    messages = [
        make_message("user", "Hello"),
        make_message("tool_result", "result data"),
        make_message("assistant", "Hi", tool_name="Read"),
    ]
    session = make_session(messages=messages)
    result = export_to_markdown(session)
    assert "👤 1" in result  # tool_result excluded from user count
    assert "🤖 1" in result
    assert "🔧 1 tool calls" in result  # tool_result not counted as tool call


def test_export_markdown_empty_tool_input():
    """Empty tool_input omits JSON block"""
    messages = [
        make_message("assistant", "Done", tool_name="Bash", tool_input={}),
    ]
    session = make_session(messages=messages)
    result = export_to_markdown(session)
    assert "**Tool: Bash**\n" in result  # No JSON block after tool name
```

- [ ] **Step 2: Run edge case tests**

Run: `python -m pytest tests/test_markdown_export.py -k "created_at_unknown or tool_result_not_counted or empty_tool_input" -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_markdown_export.py
git commit -m "test: add edge case tests for markdown export"
```

---

## Task 5: Verify all tests pass and run integration check

**Files:**
- All modified files

- [ ] **Step 1: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS (check count)

- [ ] **Step 2: Manual verification - start server**

Run: `python -m src.viewer.main` (or `run.bat`)
Then: Open browser, navigate to a conversation, click "Export MD", verify output has stats and timestamps.

- [ ] **Step 3: Final commit if needed**

```bash
git status
# If any uncommitted changes:
git add -A
git commit -m "feat: complete markdown export enhancement"
```
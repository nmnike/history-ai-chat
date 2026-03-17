# Markdown Export Enhancement

## Summary

Add comprehensive statistics header and per-message metadata to Markdown export, making exported documents match the web UI's information density.

## Requirements

### 1. Session Statistics Header

Add a compact stats line after the session metadata:

```markdown
# Conversation: {session_id}

**Project:** {project_name}
**Created:** {YYYY-MM-DD HH:MM}
**Stats:** 👤 {user_count} • 🤖 {assistant_count} • 🔧 {tool_calls} tool calls • {input}/{output} tokens (cache: {cache_read} read, {cache_created} created)

---
```

**Data to calculate:**
- `user_count`: number of messages with `role == "user"` (excludes tool_result)
- `assistant_count`: number of messages with `role == "assistant"`
- `tool_calls`: number of messages where `tool_name is not None`
- `input`: sum of `input_tokens` across all messages
- `output`: sum of `output_tokens` across all messages
- `cache_read`: sum of `cache_read_tokens`
- `cache_created`: sum of `cache_creation_tokens`

**Datetime format:**
- Source: `session.created_at`
- Format: `YYYY-MM-DD HH:MM` (e.g., `2026-03-17 14:32`)
- If `None`: show `Unknown`

**Token formatting (using `round(n, 1)`):**
- >= 1,000,000: `round(n/1000000, 1)M` (e.g., `2.5M`)
- >= 1,000: `round(n/1000, 1)K` (e.g., `45.2K`)
- < 1,000: `{n}` without suffix (e.g., `500`)

### 2. Per-Message Metadata

**User messages:**
```markdown
### User • {HH:MM:SS}

{content}
```

**Assistant messages:**
```markdown
### Assistant • {HH:MM:SS} • {input}/{output} tokens

{content}

*Thinking:*
```
{thinking_text}
```

**Tool: {tool_name}**
```json
{tool_input}
```
```

**Tool result messages:**
```markdown
### Tool Result

```
{content}
```
```

**Timestamp:**
- Format: `HH:MM:SS` in local timezone, 24-hour format
- Source: `msg.timestamp` (datetime object)
- If `msg.timestamp is None`: omit time, show only `### User` or `### Assistant`

**Token badge:**
- Shown on assistant messages only
- Shown only if `(input_tokens + output_tokens) > 0`
- Both values always displayed: `{input}/{output} tokens`
- Uses same formatting as header (K/M suffixes)

**Tool use section:**
- Shown on messages where `tool_name is not None`
- Rendered after content and thinking (if present)
- `tool_input` formatted as JSON code block

## Implementation

**File:** `src/viewer/main.py`

**Function:** `export_to_markdown(session: Session) -> str`

**Changes:**
1. Calculate aggregate statistics before message loop
2. Add stats line to header with formatted token values
3. Format `created_at` as `YYYY-MM-DD HH:MM`
4. Add timestamp to each message heading
5. Add token badge to assistant message headings (when tokens > 0)

**Helper function needed:**
```python
def format_token_count(n: int) -> str:
    """Format token count with K/M suffix"""
    if n >= 1000000:
        return f"{round(n/1000000, 1)}M"
    if n >= 1000:
        return f"{round(n/1000, 1)}K"
    return str(n)
```

## Edge Cases

- Missing timestamp: show `### User` or `### Assistant` without time
- Missing `created_at`: show `Unknown`
- Empty `thinking_text`: omit the entire *Thinking:* section
- Zero total tokens in message: omit token badge
- No tool calls: show `🔧 0 tool calls`
- Zero cache tokens: show `cache: 0 read, 0 created`
- tool_result messages: not counted in user_count, not counted as tool_calls
- Assistant with `tool_name` but no `content`: show only tool section
- Empty `tool_input`: omit JSON block
- Assistant message with no content, thinking, or tool_use: show only `### Assistant` heading
# Markdown Export Enhancement

## Summary

Add comprehensive statistics header and per-message metadata to Markdown export, making exported documents match the web UI's information density.

## Requirements

### 1. Session Statistics Header

Add a compact stats line after the session metadata:

```markdown
# Conversation: {session_id}

**Project:** {project_name}
**Created:** {datetime}
**Stats:** 👤 {user_count} • 🤖 {assistant_count} • 🔧 {tool_calls} tool calls • {input}K/{output}K tokens (cache: {cache_read}K read, {cache_created}K created)

---
```

**Data to calculate:**
- `user_count`: number of messages with `role == "user"`
- `assistant_count`: number of messages with `role == "assistant"`
- `tool_calls`: number of messages with `tool_name` set
- `input`: sum of `input_tokens` across all messages
- `output`: sum of `output_tokens` across all messages
- `cache_read`: sum of `cache_read_tokens`
- `cache_created`: sum of `cache_creation_tokens`

**Token formatting:**
- >= 1,000,000: `{n/1000000}M` (1 decimal)
- >= 1,000: `{n/1000}K` (1 decimal)
- < 1,000: `{n}`

### 2. Per-Message Metadata

**User messages:**
```markdown
### User • {HH:MM:SS}

{content}
```

**Assistant messages:**
```markdown
### Assistant • {HH:MM:SS} • {input}K/{output}K tokens

{content}
```

Timestamp from `msg.timestamp`, formatted as 24-hour time.

Token values from `msg.input_tokens` and `msg.output_tokens`, only shown if > 0.

## Implementation

**File:** `src/viewer/main.py`

**Function:** `export_to_markdown(session: Session) -> str`

**Changes:**
1. Calculate aggregate statistics before message loop
2. Add stats line to header
3. Add timestamp to each message heading
4. Add token badge to assistant message headings

## Edge Cases

- Missing timestamp: omit time from message heading
- Zero tokens: omit token badge from that message
- No tool calls: still show "🔧 0 tool calls"
- Missing cache tokens: show "0K" for cache values
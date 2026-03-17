# Design: Token Statistics

## Overview

Add token usage statistics to the conversation viewer, showing input/output/cache tokens on both the dashboard and conversation pages.

## Data Model

### Message Extension

Add token fields to `Message` dataclass in `src/viewer/parsers/claude.py`:

```python
@dataclass
class Message:
    # ... existing fields ...
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
```

### Parser Update

Extract `usage` from JSONL assistant messages:
- Source: `data["message"]["usage"]`
- Fields: `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`

## UI Components

### Conversation Page

Location: `#session-stats` container in `conversation.html`

Display format:
```
[User: 5] [Assistant: 12] [Tool: 8]  |  Tokens: 45.2K in / 3.1K out
```

Click on tokens badge shows breakdown:
```
Input:        45,231
Output:       3,156
Cache Read:   12,450
Cache Create: 0
─────────────────────
Total:        60,837
```

### Dashboard

Location: Add 4th stat card in `dashboard.html`

Display format:
```
[Tokens: 128K / 12K]  (in / out)
```

Click shows breakdown with totals for selected date period.

## API Changes

### GET /api/conversation/{session_id}

Response includes tokens per message:
```json
{
  "messages": [{
    "input_tokens": 24931,
    "output_tokens": 130,
    "cache_read_tokens": 540,
    "cache_creation_tokens": 0
  }]
}
```

### GET /api/projects

Response includes aggregate token stats:
```json
{
  "projects": [{
    "total_input_tokens": 128000,
    "total_output_tokens": 12000,
    "total_cache_read_tokens": 45000,
    "total_cache_creation_tokens": 0
  }]
}
```

## Files to Modify

1. `src/viewer/parsers/claude.py` - Add token fields, extract from JSONL
2. `src/viewer/main.py` - Update API responses with token data
3. `src/viewer/templates/conversation.html` - Add token stats UI
4. `src/viewer/templates/dashboard.html` - Add aggregate token card
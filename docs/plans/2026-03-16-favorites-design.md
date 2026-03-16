# Favorites Feature Design

**Date:** 2026-03-16
**Status:** Approved

## Overview

Add ability to mark conversations as favorites and view them quickly on Dashboard.

## Scope

- Star icon on conversation page to add/remove from favorites
- Favorites section on Dashboard with preview cards
- API endpoints for CRUD operations

## Architecture

### Backend

**New endpoints in `main.py`:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/favorites/{session_id}` | Add to favorites |
| DELETE | `/api/favorites/{session_id}` | Remove from favorites |
| GET | `/api/favorites` | List all favorites |

**Extend `CacheDB` in `cache.py`:**

- `remove_favorite(session_id)` — remove from favorites
- `is_favorite(session_id)` → bool — check if favorited

Note: Table `favorites` already exists with columns: `session_id`, `tags`, `notes`, `created_at`.

### Frontend

**Conversation page (`conversation.html`):**

- Star icon in header (next to session title)
- States: outline star (not favorited) / filled star (favorited)
- Click → API call → toggle state
- On load: check `is_favorite` to show correct initial state

**Dashboard (`dashboard.html`):**

- "Favorites" section above projects list
- Cards with: project name, platform badge, date, preview of first message
- Empty state: "Нет избранных диалогов"
- Click card → navigate to conversation page
- On load: fetch `/api/favorites`

## Data Flow

```
User clicks star → POST /api/favorites/{id} → CacheDB.add_favorite()
                                                                   ↓
Dashboard loads → GET /api/favorites → CacheDB.get_favorites() → render cards
```

## Out of Scope

- Tags and notes (table supports them but not implemented in UI)
- Bulk operations
- Favorites filtering by project/date
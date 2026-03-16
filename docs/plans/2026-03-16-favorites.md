# Favorites Feature Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add ability to mark conversations as favorites and view them quickly on Dashboard.

**Architecture:** Extend existing CacheDB with remove_favorite/is_favorite methods, add 3 API endpoints, add star icon to conversation page, add favorites section to dashboard.

**Tech Stack:** Python 3.13, FastAPI, SQLite, Bootstrap 5, Jinja2 templates

---

## Task 1: Add remove_favorite and is_favorite to CacheDB

**Files:**
- Modify: `src/viewer/db/cache.py:78-97`
- Modify: `tests/test_cache.py:35-44`

**Step 1: Write the failing tests**

Add to `tests/test_cache.py` after line 44:

```python
def test_remove_favorite(tmp_path):
    """Test removing a favorite"""
    db = CacheDB(tmp_path / "cache.db")

    db.cache_session({"id": "session-1", "project": "p1", "preview": "Test"})
    db.add_favorite("session-1")

    assert db.is_favorite("session-1") is True

    db.remove_favorite("session-1")
    assert db.is_favorite("session-1") is False

    favorites = db.get_favorites()
    assert len(favorites) == 0


def test_is_favorite_not_exists(tmp_path):
    """Test is_favorite returns False for non-existent favorite"""
    db = CacheDB(tmp_path / "cache.db")

    assert db.is_favorite("non-existent") is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cache.py::test_remove_favorite tests/test_cache.py::test_is_favorite_not_exists -v`
Expected: FAIL with "AttributeError: 'CacheDB' object has no attribute 'remove_favorite'"

**Step 3: Write minimal implementation**

Add to `src/viewer/db/cache.py` after line 97:

```python
    def remove_favorite(self, session_id: str):
        """Remove session from favorites"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM favorites WHERE session_id = ?", (session_id,)
            )

    def is_favorite(self, session_id: str) -> bool:
        """Check if session is in favorites"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM favorites WHERE session_id = ?", (session_id,)
            )
            return cursor.fetchone() is not None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cache.py::test_remove_favorite tests/test_cache.py::test_is_favorite_not_exists -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/viewer/db/cache.py tests/test_cache.py
git commit -m "feat: add remove_favorite and is_favorite methods to CacheDB"
```

---

## Task 2: Add favorites API endpoints

**Files:**
- Modify: `src/viewer/main.py:363`
- Modify: `tests/test_integration.py`

**Step 1: Write the failing tests**

Add to `tests/test_integration.py`:

```python
def test_favorites_api(client):
    """Test favorites API endpoints"""
    session_id = "test-fav-session"

    # Add to favorites
    response = client.post(f"/api/favorites/{session_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "added"

    # Check is favorite
    response = client.get(f"/api/favorites/{session_id}/status")
    assert response.status_code == 200
    assert response.json()["is_favorite"] is True

    # Get all favorites
    response = client.get("/api/favorites")
    assert response.status_code == 200
    assert len(response.json()["favorites"]) >= 1

    # Remove from favorites
    response = client.delete(f"/api/favorites/{session_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "removed"

    # Verify removed
    response = client.get(f"/api/favorites/{session_id}/status")
    assert response.json()["is_favorite"] is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_integration.py::test_favorites_api -v`
Expected: FAIL with 404 Not Found

**Step 3: Write minimal implementation**

Add to `src/viewer/main.py` after line 363 (after search endpoint):

```python
# Favorites API

@app.get("/api/favorites")
async def list_favorites():
    """List all favorite sessions"""
    favorites = cache_db.get_favorites()
    return {"favorites": favorites}


@app.post("/api/favorites/{session_id}")
async def add_favorite(session_id: str):
    """Add session to favorites"""
    cache_db.add_favorite(session_id)
    return {"status": "added", "session_id": session_id}


@app.delete("/api/favorites/{session_id}")
async def remove_favorite(session_id: str):
    """Remove session from favorites"""
    cache_db.remove_favorite(session_id)
    return {"status": "removed", "session_id": session_id}


@app.get("/api/favorites/{session_id}/status")
async def check_favorite_status(session_id: str):
    """Check if session is favorited"""
    is_fav = cache_db.is_favorite(session_id)
    return {"session_id": session_id, "is_favorite": is_fav}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_integration.py::test_favorites_api -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/viewer/main.py tests/test_integration.py
git commit -m "feat: add favorites API endpoints"
```

---

## Task 3: Add star icon to conversation page

**Files:**
- Modify: `src/viewer/templates/conversation.html:26-31`
- Modify: `src/viewer/templates/conversation.html:67-126`

**Step 1: Add star icon HTML**

Replace lines 26-31 in `src/viewer/templates/conversation.html`:

```html
<h5>
    <i class="bi bi-chat-dots"></i>
    <span id="session-id">{{ session_id }}</span>
    <span id="platform-badge" class="badge bg-info">{{ platform }}</span>
    <i class="bi bi-star" id="favorite-btn" style="cursor: pointer; font-size: 1.2rem;" title="Add to favorites"></i>
</h5>
```

**Step 2: Add favorite toggle JavaScript**

Add to `src/viewer/templates/conversation.html` after line 70 (in DOMContentLoaded):

```javascript
document.addEventListener('DOMContentLoaded', function() {
    initMessageLayout();
    loadConversation();
    initFavoriteButton();
});
```

Add new function after `exportSession` function (around line 283):

```javascript
// Favorites functionality
function initFavoriteButton() {
    const btn = document.getElementById('favorite-btn');
    if (!btn) return;

    // Check current favorite status
    fetch(`/api/favorites/${encodeURIComponent(sessionId)}/status`)
        .then(response => response.json())
        .then(data => {
            updateFavoriteIcon(data.is_favorite);
        })
        .catch(err => console.error('Failed to check favorite status:', err));

    // Click handler
    btn.addEventListener('click', toggleFavorite);
}

function toggleFavorite() {
    const btn = document.getElementById('favorite-btn');
    const isFav = btn.classList.contains('bi-star-fill');

    const method = isFav ? 'DELETE' : 'POST';
    const url = `/api/favorites/${encodeURIComponent(sessionId)}`;

    fetch(url, { method: method })
        .then(response => response.json())
        .then(data => {
            updateFavoriteIcon(!isFav);
        })
        .catch(err => {
            console.error('Failed to toggle favorite:', err);
            alert('Failed to update favorite');
        });
}

function updateFavoriteIcon(isFavorite) {
    const btn = document.getElementById('favorite-btn');
    if (!btn) return;

    if (isFavorite) {
        btn.classList.remove('bi-star');
        btn.classList.add('bi-star-fill');
        btn.title = 'Remove from favorites';
    } else {
        btn.classList.remove('bi-star-fill');
        btn.classList.add('bi-star');
        btn.title = 'Add to favorites';
    }
}
```

**Step 3: Manual test**

Run: `python -m viewer.main` (or your start command)
Open a conversation page, verify star icon appears and toggles on click.

**Step 4: Commit**

```bash
git add src/viewer/templates/conversation.html
git commit -m "feat: add favorite star icon to conversation page"
```

---

## Task 4: Add favorites section to dashboard

**Files:**
- Modify: `src/viewer/templates/dashboard.html:6-64`
- Modify: `src/viewer/templates/dashboard.html:66-200`

**Step 1: Add favorites section HTML**

Add after line 6 (after stats row opening `<div class="row mb-3">`):

```html
<!-- Favorites Section -->
<div class="row mb-3" id="favorites-section" style="display: none;">
    <div class="col-12">
        <h5><i class="bi bi-star-fill text-warning"></i> Избранное</h5>
        <div id="favorites-list" class="list-group mb-3">
        </div>
    </div>
</div>
```

**Step 2: Add favorites loading JavaScript**

Add to `DOMContentLoaded` in dashboard.html:

```javascript
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('date-filter').value = 'today';
    document.getElementById('date-filter').addEventListener('change', loadProjects);
    loadFavorites();
    loadProjects();
    initSearch();
});
```

Add new function after `loadProjects` function (around line 122):

```javascript
function loadFavorites() {
    fetch('/api/favorites')
        .then(response => response.json())
        .then(data => {
            const favorites = data.favorites || [];
            const section = document.getElementById('favorites-section');
            const list = document.getElementById('favorites-list');

            if (favorites.length === 0) {
                section.style.display = 'none';
                return;
            }

            section.style.display = '';
            list.innerHTML = favorites.map(fav => {
                const platformBadge = fav.platform === 'codex'
                    ? '<span class="badge bg-info">Codex</span>'
                    : '<span class="badge bg-warning text-dark">Claude</span>';
                const date = fav.cached_at ? new Date(fav.cached_at).toLocaleDateString() : '';
                const preview = fav.preview ? escapeHtml(fav.preview.substring(0, 100)) : '';

                return `
                    <a href="/conversation/${encodeURIComponent(fav.session_id)}?platform=${fav.platform}" class="list-group-item list-group-item-action">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <div class="fw-bold">${escapeHtml(fav.project || 'Unknown')}</div>
                                <small class="text-muted">${preview}${preview.length >= 100 ? '...' : ''}</small>
                            </div>
                            <div class="text-end">
                                ${platformBadge}
                                <br><small class="text-muted">${date}</small>
                            </div>
                        </div>
                    </a>
                `;
            }).join('');
        })
        .catch(err => {
            console.error('Failed to load favorites:', err);
        });
}
```

**Step 3: Manual test**

Run: `python -m viewer.main`
1. Add a conversation to favorites
2. Go to dashboard, verify favorites section appears with the favorited conversation
3. Click the card, verify it navigates to the conversation

**Step 4: Commit**

```bash
git add src/viewer/templates/dashboard.html
git commit -m "feat: add favorites section to dashboard"
```

---

## Task 5: Run full test suite

**Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

**Step 2: Final commit if needed**

If any files were modified during testing:

```bash
git add -A
git commit -m "fix: resolve test issues"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | CacheDB methods | cache.py, test_cache.py |
| 2 | API endpoints | main.py, test_integration.py |
| 3 | Conversation star | conversation.html |
| 4 | Dashboard section | dashboard.html |
| 5 | Test suite | - |
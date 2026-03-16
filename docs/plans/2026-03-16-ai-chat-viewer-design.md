# AI Chat History Viewer — Design Document

**Date:** 2026-03-16
**Status:** Approved
**Approach:** Fork AI-Conversation-Viewer with Codex support

## Overview

Веб-приложение для просмотра истории диалогов с AI-агентами (Claude Code, OpenAI Codex CLI) с красивым интерфейсом в стиле мессенджера.

## Platforms Supported

| Platform | Data Location | Format |
|----------|---------------|--------|
| Claude Code | `~/.claude/projects/*/*.jsonl` | JSONL |
| Codex CLI | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` | JSONL |

## Architecture

```
claude-codex-viewer/
├── viewer/                    # Python package
│   ├── main.py               # FastAPI application
│   ├── cli.py                # Command line interface
│   ├── parsers/              # Platform-specific parsers
│   │   ├── claude.py         # Claude Code JSONL parser
│   │   └── codex.py          # Codex CLI JSONL parser
│   ├── db/                   # SQLite for cache/favorites
│   ├── templates/            # Jinja2 templates
│   └── static/               # CSS/JS assets
├── pyproject.toml
└── README.md
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/projects` | GET | List all projects |
| `/api/sessions/{project}` | GET | Sessions for project |
| `/api/conversation/{session_id}` | GET | Full conversation |
| `/api/search?q={query}` | GET | Global search |
| `/api/export/{session_id}?format={md\|html\|json}` | GET | Export session |

## UI Components

### 1. Dashboard
- Platform switcher (Claude/Codex)
- Global search bar
- Statistics cards (sessions, projects, messages)
- Recent sessions list

### 2. Projects View
- Filter by platform, date range
- Project cards with session count

### 3. Sessions View
- Grouped by date (today, yesterday, this week, older)
- Session preview (first message)

### 4. Conversation View
- Chat-style message bubbles
- Message types:
  - **User message** — right-aligned, blue accent
  - **Assistant text** — left-aligned, gray
  - **Thinking block** — collapsible, orange accent
  - **Tool use** — expandable card, green accent
  - **Tool result** — collapsible code block

## Color Scheme

| Element | Light Theme | Dark Theme |
|---------|-------------|------------|
| Background | `#ffffff` | `#1e1e2e` |
| User message | `#e3f2fd` | `#313244` |
| Assistant message | `#f5f5f5` | `#45475a` |
| Thinking block | `#fff3e0` | `#58372d` |
| Tool use | `#e8f5e9` | `#2d4a3e` |
| Accent | `#7c3aed` | `#a78bfa` |

## Features (MVP)

1. **Multi-platform support** — Claude Code + Codex CLI
2. **Global search** — across all projects and sessions
3. **Tool visualization** — display tool_use/tool_result with formatting
4. **Thinking mode** — separate collapsible block for reasoning
5. **Export** — Markdown, HTML, JSON formats
6. **Themes** — Dark/Light with toggle and persistence
7. **Filters** — by platform, project, date range, role

## Technical Stack

- **Backend:** Python 3.10+, FastAPI
- **Frontend:** Jinja2, Bootstrap 5, Vanilla JS
- **Database:** SQLite with WAL mode
- **Syntax highlighting:** Pygments
- **Caching:** LRU cache with TTL

## Installation

```bash
pip install claude-codex-viewer
claude-codex-viewer --port 6300
```

## Environment Variables

```bash
CLAUDE_PROJECTS_PATH=~/.claude/projects
CODEX_SESSIONS_PATH=~/.codex/sessions
```

## Success Criteria

- [ ] All Claude Code sessions visible and searchable
- [ ] All Codex CLI sessions visible and searchable
- [ ] Search returns results in < 500ms
- [ ] Export produces valid Markdown/HTML/JSON
- [ ] Theme toggle persists across sessions
- [ ] Works on Windows, macOS, Linux
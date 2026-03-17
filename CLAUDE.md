# History AI Chat

Веб-просмотрщик истории диалогов Claude Code и Codex CLI (FastAPI + Jinja2).

## Команды

```bash
run.bat                 # Запуск сервера (Windows)
python -m pytest tests/ -v   # Тесты
pip install -e .        # Установка
pip install -e ".[dev]" # Dev-зависимости
build.bat               # Сборка exe
```

## Архитектура

| Путь | Назначение |
|------|------------|
| `src/viewer/main.py` | FastAPI app, API endpoints |
| `src/viewer/parsers/claude.py` | Claude Code JSONL parser, Message/Session dataclasses |
| `src/viewer/parsers/codex.py` | Codex CLI parser |
| `src/viewer/db/cache.py` | SQLite cache (favorites) |
| `src/viewer/templates/` | Jinja2 HTML |
| `src/viewer/static/css/` | Тема (theme.css) |

## Ключевые паттерны

**Парсинг JSONL**: Чтение построчно, merge streaming chunks по `message.id`.

**Message dataclass**: role, content, timestamp, token fields (input/output/cache).

**API**: `/api/projects`, `/api/sessions/{id}`, `/api/conversation/{id}`, `/api/search`.

## Формат данных Claude Code

```
~/.claude/projects/{project-id}/{session-id}.jsonl
```

Токены в `message.usage`:
- `input_tokens`, `output_tokens`
- `cache_read_input_tokens`, `cache_creation_input_tokens`

## Технологии

FastAPI, Jinja2, Pygments, SQLite, PyInstaller (desktop).
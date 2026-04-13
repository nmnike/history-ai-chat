# Conversation Page Enhancements План реализации

> **Для Claude:** ТРЕБУЕМЫЙ ПОД-СКИЛЛ: Используй superpowers:executing-plans для реализации этого плана задача за задачей.

**Цель:** Доработать страницу Conversation: включить мультивыбор badge-фильтров с логикой OR, показать start/end/duration сессии и вывести отдельные красивые блоки с реально вызванными MCP и Skills.

**Архитектура:** Нужны минимальные изменения в существующем потоке данных: расширить `Session` и JSON API вычисляемыми полями, а затем обновить `conversation.html`, чтобы он рендерил новые метаданные и применял множественные client-side фильтры. MCP и Skills не нужно хранить отдельно в парсерах — их достаточно вычислить на уровне API из уже распарсенных `tool_name` сообщений, чтобы не тащить лишнюю доменную логику в ingestion.

**Технологический стек:** Python dataclasses, FastAPI, Jinja2, vanilla JavaScript, Bootstrap 5, pytest, FastAPI TestClient

---

### Задача 1: Зафиксировать API-контракт для времени сессии и инструментария

**Файлы:**
- Изменить: `tests/test_integration.py`
- Изменить: `src/viewer/main.py`

**Шаг 1: Напиши падающий тест для `/api/conversation`**

Добавь в `tests/test_integration.py` новый тест со stub parser, который возвращает сессию с сообщениями на разных timestamp и с tool names `mcp__context7__query-docs`, `functions.Skill`, `Read`, `functions.AskUserQuestion`.

```python
from datetime import datetime, timedelta
from viewer.parsers import Message, Session


def test_api_conversation_returns_timing_and_tool_metadata(monkeypatch):
    base = datetime(2026, 4, 10, 12, 0, 0)
    session = Session(
        id="sess-1",
        project_path="/tmp/test-project",
        project_name="test-project",
        created_at=base,
        messages=[
            Message(role="user", content="hi", uuid="1", timestamp=base, session_id="sess-1", project_path="/tmp/test-project"),
            Message(role="assistant", content="", uuid="2", timestamp=base + timedelta(minutes=2), session_id="sess-1", project_path="/tmp/test-project", message_type="tool_use", tool_name="mcp__context7__query-docs"),
            Message(role="assistant", content="", uuid="3", timestamp=base + timedelta(minutes=4), session_id="sess-1", project_path="/tmp/test-project", message_type="tool_use", tool_name="functions.Skill"),
            Message(role="assistant", content="", uuid="4", timestamp=base + timedelta(minutes=5), session_id="sess-1", project_path="/tmp/test-project", message_type="tool_use", tool_name="Read"),
            Message(role="assistant", content="", uuid="5", timestamp=base + timedelta(minutes=6), session_id="sess-1", project_path="/tmp/test-project", message_type="tool_use", tool_name="functions.AskUserQuestion"),
        ],
    )

    class StubClaudeParser:
        def get_sessions(self, project_id):
            assert project_id == "test-project"
            return [session]

    monkeypatch.setattr("viewer.main.claude_parser", StubClaudeParser())

    response = client.get("/api/conversation/sess-1?project_id=test-project&platform=claude")
    assert response.status_code == 200

    payload = response.json()["session"]
    assert payload["created_at"] == "2026-04-10T12:00:00"
    assert payload["ended_at"] == "2026-04-10T12:06:00"
    assert payload["duration_seconds"] == 360
    assert payload["mcps"] == [{"name": "context7", "count": 1}]
    assert payload["skills"] == [
        {"name": "Skill", "count": 1},
        {"name": "AskUserQuestion", "count": 1},
    ]
```

**Шаг 2: Запусти тест и убедись, что он падает**

Запусти: `rtk pytest tests/test_integration.py -k conversation_returns_timing_and_tool_metadata -v`
Ожидается: FAIL, потому что `session_to_dict()` пока не возвращает `ended_at`, `duration_seconds`, `mcps`, `skills`.

**Шаг 3: Реализуй минимальный код в API**

В `src/viewer/main.py`:
- добавь небольшие helper-функции рядом с `session_to_dict()`:
  - получить `ended_at` как `session.ended_at`, а если оно пустое — как `max(m.timestamp)` по сообщениям с timestamp
  - получить `duration_seconds` как разницу между `created_at` и `ended_at`, минимум `0`
  - классифицировать `tool_name`:
    - MCP: строки, начинающиеся с `mcp__`, имя MCP брать как второй сегмент (`mcp__context7__query-docs` → `context7`)
    - Skills: строки, начинающиеся с `functions.` и не равные обычным low-level tool names. Для этой задачи достаточно whitelist-подхода по фактически «оркестрационным» skill-like вызовам: `Skill`, `AskUserQuestion`, `Agent`, `EnterPlanMode`, `ExitPlanMode`, `TaskCreate`, `TaskUpdate`, `TaskList`, `TaskGet`
- агрегируй counts через обычный словарь
- верни в `session_to_dict()` новые поля:

```python
{
    "created_at": ...,
    "ended_at": ended_at.isoformat() if ended_at else None,
    "duration_seconds": duration_seconds,
    "mcps": [{"name": name, "count": count} for name, count in ...],
    "skills": [{"name": name, "count": count} for name, count in ...],
}
```

**Шаг 4: Запусти тест повторно**

Запусти: `rtk pytest tests/test_integration.py -k conversation_returns_timing_and_tool_metadata -v`
Ожидается: PASS

**Шаг 5: Коммит**

```bash
rtk git add tests/test_integration.py src/viewer/main.py
rtk git commit -m "feat: добавить метаданные времени и инструментов диалога"
```

---

### Задача 2: Добавить end time в модель Session и проверку на уровне парсеров

**Файлы:**
- Изменить: `tests/test_claude_parser.py`
- Изменить: `tests/test_codex_parser.py`
- Изменить: `src/viewer/parsers/claude.py`
- Изменить: `src/viewer/parsers/codex.py`

**Шаг 1: Напиши падающие тесты для `ended_at`**

Добавь по одному тесту в `tests/test_claude_parser.py` и `tests/test_codex_parser.py`, которые создают файл с двумя сообщениями и проверяют, что у итоговой сессии:
- `created_at` равен timestamp первого сообщения
- `ended_at` равен timestamp последнего сообщения

Пример для Claude:

```python
def test_claude_session_tracks_end_time(tmp_path):
    session_file = tmp_path / "test-session.jsonl"
    session_file.write_text(
        json.dumps({... "timestamp": "2026-04-10T10:00:00Z"}) + "\n" +
        json.dumps({... "timestamp": "2026-04-10T10:05:00Z"}) + "\n"
    )

    parser = ClaudeParser(str(tmp_path))
    project_dir = tmp_path / "demo-project"
    project_dir.mkdir()
    session_file.rename(project_dir / session_file.name)

    sessions = parser.get_sessions("demo-project")
    assert sessions[0].created_at.isoformat() == "2026-04-10T10:00:00+00:00"
    assert sessions[0].ended_at.isoformat() == "2026-04-10T10:05:00+00:00"
```

Для Codex используй `CodexParser(sessions_path=str(tmp_path))` и rollout-файл с двумя `response_item`.

**Шаг 2: Запусти только новые тесты**

Запусти: `rtk pytest tests/test_claude_parser.py -k end_time -v && rtk pytest tests/test_codex_parser.py -k end_time -v`
Ожидается: FAIL, потому что у `Session` нет `ended_at`.

**Шаг 3: Реализуй минимальные изменения в парсерах**

В `src/viewer/parsers/claude.py`:
- расширь dataclass `Session`:

```python
@dataclass
class Session:
    ...
    created_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
```

- в `get_sessions()` при создании `Session(...)` установи:

```python
created_at=messages[0].timestamp if messages else None,
ended_at=messages[-1].timestamp if messages else None,
```

В `src/viewer/parsers/codex.py` в месте создания `Session(...)` сделай то же самое.

**Шаг 4: Запусти тесты снова**

Запусти: `rtk pytest tests/test_claude_parser.py -k end_time -v && rtk pytest tests/test_codex_parser.py -k end_time -v`
Ожидается: PASS

**Шаг 5: Коммит**

```bash
rtk git add tests/test_claude_parser.py tests/test_codex_parser.py src/viewer/parsers/claude.py src/viewer/parsers/codex.py
rtk git commit -m "feat: сохранить время окончания сессии"
```

---

### Задача 3: Добавить регрессионный тест на новый markup страницы Conversation

**Файлы:**
- Изменить: `tests/test_integration.py`
- Изменить: `src/viewer/templates/conversation.html`

**Шаг 1: Напиши падающий template-тест**

Добавь тест, который загружает `/conversation/test-session?...` и проверяет наличие новых контейнеров и JS-констант:

```python
def test_conversation_template_contains_metadata_and_multi_filter_ui():
    response = client.get("/conversation/test-session?project_id=test-project&platform=claude")
    assert response.status_code == 200
    assert 'id="session-timing"' in response.text
    assert 'id="session-tools-summary"' in response.text
    assert 'let activeFilters = new Set();' in response.text
    assert 'function applyFilters()' in response.text
    assert 'function renderToolSummary(session)' in response.text
```

**Шаг 2: Запусти тест и убедись, что он падает**

Запусти: `rtk pytest tests/test_integration.py -k metadata_and_multi_filter_ui -v`
Ожидается: FAIL

**Шаг 3: Подготовь HTML-каркас в шаблоне**

В `src/viewer/templates/conversation.html` под строкой с `session-date` добавь два новых контейнера:

```html
<div id="session-timing" class="session-timing mt-2"></div>
<div id="session-tools-summary" class="session-tools-summary mt-3"></div>
```

В script-блоке:
- замени `let activeFilter = null;` на `let activeFilters = new Set();`
- добавь пустые функции-заготовки `renderSessionTiming(session)`, `renderToolSummary(session)`, `applyFilters()`
- вызови `renderSessionTiming(session)` и `renderToolSummary(session)` после загрузки данных

**Шаг 4: Запусти тест снова**

Запусти: `rtk pytest tests/test_integration.py -k metadata_and_multi_filter_ui -v`
Ожидается: PASS

**Шаг 5: Коммит**

```bash
rtk git add tests/test_integration.py src/viewer/templates/conversation.html
rtk git commit -m "feat: подготовить ui-каркас для метаданных conversation"
```

---

### Задача 4: Реализовать мультифильтр badge-фильтров с логикой OR

**Файлы:**
- Изменить: `src/viewer/templates/conversation.html`

**Шаг 1: Добавь падающий js/template regression test**

В `tests/test_integration.py` добавь проверку строк, подтверждающих новую логику:

```python
def test_conversation_template_uses_or_multi_filter_logic():
    response = client.get("/conversation/test-session?project_id=test-project&platform=claude")
    assert response.status_code == 200
    assert 'activeFilters.has(filter)' in response.text
    assert 'activeFilters.size === 0' in response.text
    assert 'return matchesRole || matchesTool;' in response.text
```

**Шаг 2: Запусти тест и убедись, что он падает**

Запусти: `rtk pytest tests/test_integration.py -k or_multi_filter_logic -v`
Ожидается: FAIL

**Шаг 3: Реализуй новую фильтрацию в `conversation.html`**

Замени функцию `toggleFilter(filter)` и связанную логику:
- badge теперь toggle-ится независимо
- если `activeFilters` пуст, показываем все messages
- если не пуст, message показывается, когда совпал хотя бы один выбранный фильтр
- вынеси проверку в helper `messageMatchesFilter(bubble, filter)`
- после изменения набора фильтров всегда обновляй `.active-filter` у badge и вызывай `applyFilters()`

Минимальная структура:

```javascript
function toggleFilter(filter) {
    if (activeFilters.has(filter)) {
        activeFilters.delete(filter);
    } else {
        activeFilters.add(filter);
    }
    updateFilterBadges();
    applyFilters();
}

function applyFilters() {
    const bubbles = document.querySelectorAll('.message-bubble');
    if (activeFilters.size === 0) {
        bubbles.forEach(b => b.style.display = '');
        return;
    }

    bubbles.forEach(bubble => {
        const matches = Array.from(activeFilters).some(filter => messageMatchesFilter(bubble, filter));
        bubble.style.display = matches ? '' : 'none';
    });
}
```

**Шаг 4: Запусти тест**

Запусти: `rtk pytest tests/test_integration.py -k "or_multi_filter_logic or metadata_and_multi_filter_ui" -v`
Ожидается: PASS

**Шаг 5: Коммит**

```bash
rtk git add tests/test_integration.py src/viewer/templates/conversation.html
rtk git commit -m "feat: добавить мультифильтр сообщений на странице conversation"
```

---

### Задача 5: Отрендерить start/end/duration и блоки MCP/Skills

**Файлы:**
- Изменить: `src/viewer/templates/conversation.html`
- Изменить: `src/viewer/static/css/theme.css`

**Шаг 1: Добавь падающий template regression test на содержимое JS/UI**

В `tests/test_integration.py` добавь тест:

```python
def test_conversation_template_renders_timing_and_tool_cards():
    response = client.get("/conversation/test-session?project_id=test-project&platform=claude")
    assert response.status_code == 200
    assert 'Started' in response.text
    assert 'Ended' in response.text
    assert 'Duration' in response.text
    assert 'MCP' in response.text
    assert 'Skills' in response.text
    assert 'formatDuration(' in response.text
```

**Шаг 2: Запусти тест и убедись, что он падает**

Запусти: `rtk pytest tests/test_integration.py -k timing_and_tool_cards -v`
Ожидается: FAIL

**Шаг 3: Реализуй рендер новых блоков**

В `src/viewer/templates/conversation.html`:
- добавь helper `formatDuration(totalSeconds)` с форматом без лишней болтовни:
  - `< 60` → `45s`
  - `< 3600` → `6m 12s`
  - иначе `1h 03m`
- `renderSessionTiming(session)` должен рисовать три компактные карточки/плашки: Started, Ended, Duration
- `renderToolSummary(session)` должен рисовать два отдельных блока только если данные есть:
  - MCP
  - Skills
- внутри каждого блока выводи badge list с count, например `context7 · 1`
- если список пуст, блок не рендерить вообще

Пример структуры:

```javascript
function renderToolSummary(session) {
    const container = document.getElementById('session-tools-summary');
    const sections = [];

    if (session.mcps?.length) {
        sections.push(renderToolGroup('MCP', 'bi-hdd-network', session.mcps, 'tool-group-mcp'));
    }
    if (session.skills?.length) {
        sections.push(renderToolGroup('Skills', 'bi-magic', session.skills, 'tool-group-skills'));
    }

    container.innerHTML = sections.join('');
}
```

В `src/viewer/static/css/theme.css` добавь стили для:
- `.session-timing`
- `.timing-chip`
- `.session-tools-summary`
- `.tool-summary-group`
- `.tool-summary-title`
- `.tool-summary-badges`
- `.tool-summary-badge`

Стиль: компактный, в духе текущей тёмной темы, без тяжёлых карточек.

**Шаг 4: Запусти тест**

Запусти: `rtk pytest tests/test_integration.py -k timing_and_tool_cards -v`
Ожидается: PASS

**Шаг 5: Коммит**

```bash
rtk git add tests/test_integration.py src/viewer/templates/conversation.html src/viewer/static/css/theme.css
rtk git commit -m "feat: показать время и инструменты диалога"
```

---

### Задача 6: Прогнать целевые тесты и проверить отсутствие регрессий

**Файлы:**
- Изменить: нет

**Шаг 1: Запусти набор целевых тестов**

Запусти:

```bash
rtk pytest tests/test_integration.py tests/test_claude_parser.py tests/test_codex_parser.py tests/test_token_parsing.py -v
```

Ожидается: PASS

**Шаг 2: При наличии фронтовых регрессий проверь шаблон вручную**

Запусти:

```bash
rtk pytest tests/test_integration.py -k "conversation or favorites" -v
```

Ожидается: PASS

**Шаг 3: Просмотри diff**

Запусти:

```bash
rtk git diff -- src/viewer/main.py src/viewer/parsers/claude.py src/viewer/parsers/codex.py src/viewer/templates/conversation.html src/viewer/static/css/theme.css tests/test_integration.py tests/test_claude_parser.py tests/test_codex_parser.py
```

Ожидается: только изменения под эту задачу, без лишнего рефакторинга.

**Шаг 4: Финальный коммит (если работал без промежуточных коммитов)**

Если предыдущие атомарные коммиты уже сделаны — этот шаг пропусти.
Если нужен один финальный коммит вместо атомарных:

```bash
rtk git add src/viewer/main.py src/viewer/parsers/claude.py src/viewer/parsers/codex.py src/viewer/templates/conversation.html src/viewer/static/css/theme.css tests/test_integration.py tests/test_claude_parser.py tests/test_codex_parser.py tests/test_token_parsing.py
rtk git commit -m "feat: доработать страницу conversation"
```

---

## Заметки по реализации

- Не делай отдельную persistence-модель для MCP/Skills: это display-метаданные, их достаточно вычислять из `session.messages`.
- Для списка Skills не пытайся «угадывать» любой `functions.*` как skill. Ограничься явным whitelist, иначе туда попадут обычные low-level tools (`Read`, `Edit`, `Write`, `Bash`).
- Для `ended_at` используй фактический timestamp последнего сообщения, а не `datetime.now()`.
- Для OR-фильтра не меняй существующий markup badge-ов сильнее необходимого: задача про поведение, не про редизайн stats bar.
- Если понадобится показать tool_result рядом с tool_use фильтром, сохраняй текущее поведение через `data-tool`, оно уже частично реализовано в `src/viewer/templates/conversation.html`.
- Тесты здесь в основном regression-style по HTML/JS строкам. Этого достаточно для текущей кодовой базы и дешевле, чем тащить отдельный фронтовый тест-раннер.

## Релевантные скиллы

- @superpowers-test-driven-development — если захочешь жёстко следовать TDD в реализации
- @superpowers-systematic-debugging — если сломается фильтрация или парсинг timestamp
- @superpowers-verification-before-completion — перед заявлением, что задача закрыта
- @superpowers-requesting-code-review — после реализации перед merge

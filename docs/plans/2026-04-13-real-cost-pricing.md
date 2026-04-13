# Real Cost Pricing План реализации

> **Для Claude:** ТРЕБУЕМЫЙ ПОД-СКИЛЛ: Используй superpowers:executing-plans для реализации этого плана задача за задачей.

**Цель:** Добавить на страницу диалога реальный расчёт стоимости в USD по токенам с поддержкой моделей Claude, OpenAI и Alibaba Cloud, без `Est. cost`.

**Архитектура:** Выделить расчёт стоимости в отдельный Python-модуль `src/viewer/pricing.py`, чтобы логика тарифов и нормализации моделей не расползалась по FastAPI и шаблонам. Стоимость считать на уровне сообщений, а не по агрегированному `session.model`: это чуть сложнее, но иначе multi-model сессии будут посчитаны неверно. API `/api/conversation` и `/api/sessions/{project_id}` получают готовый `cost`-объект, а `conversation.html` только рендерит итоговую сумму, breakdown токенов и список моделей/провайдеров.

**Технологический стек:** Python dataclasses, FastAPI, Jinja2, vanilla JavaScript, pytest, FastAPI TestClient

---

## Документация, которую проверить перед кодом

- Anthropic pricing: Claude API pricing + prompt caching.
- OpenAI pricing: GPT-5 short-context pricing + cached input pricing.
- Alibaba Cloud Model Studio: Model invocation pricing + context cache billing.

**Важно:**
- Для Alibaba Cloud поддержать:
  - flat-rate модели: `kimi-k2.5`, `MiniMax-M2.5`
  - tiered модели: `glm-5`, `qwen3.5-plus`
- Для `qwen3.5-plus` брать **Global** pricing по умолчанию, потому что в истории диалогов deployment mode не сохраняется.
- Для `qwen-plus`, `qwen-turbo` и других моделей, которых нет в явной таблице поддержки, модуль должен возвращать `available=False`, а UI не должен показывать фальшивый `$`.
- В истории уже есть `cache_read_tokens` и `cache_creation_tokens`; для Claude и Alibaba их можно использовать напрямую. Для OpenAI обычно используется только cached input, поэтому `cache_creation_tokens` там обычно будут `0`.
- Для Alibaba Cloud использовать explicit cache multipliers: `cache_read = 10%` от input price, `cache_creation = 125%` от input price.

---

### Задача 1: Зафиксировать контракт pricing-модуля unit-тестами

**Файлы:**
- Создать: `tests/test_pricing.py`
- Создать: `src/viewer/pricing.py`

**Шаг 1: Напиши падающий unit-тест на Claude, OpenAI, Alibaba и unknown model**

Создай `tests/test_pricing.py`:

```python
from viewer.pricing import calculate_message_cost, calculate_session_cost
from viewer.parsers import Message, Session
from datetime import datetime


def make_message(model, input_tokens=0, output_tokens=0, cache_read_tokens=0, cache_creation_tokens=0):
    return Message(
        role="assistant",
        content="ok",
        uuid="m1",
        timestamp=datetime(2026, 4, 13, 12, 0, 0),
        session_id="s1",
        project_path="/tmp/project",
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_creation_tokens=cache_creation_tokens,
    )


def test_calculate_message_cost_for_claude_alias():
    msg = make_message(
        model="Sonnet 4.6",
        input_tokens=1_000_000,
        output_tokens=100_000,
        cache_read_tokens=200_000,
        cache_creation_tokens=50_000,
    )

    cost = calculate_message_cost(msg)

    assert cost is not None
    assert cost["provider"] == "claude"
    assert cost["model"] == "Sonnet 4.6"
    assert round(cost["total_usd"], 2) == 4.88


def test_calculate_message_cost_for_openai_model():
    msg = make_message(
        model="gpt-5.4",
        input_tokens=1_000_000,
        output_tokens=100_000,
        cache_read_tokens=200_000,
    )

    cost = calculate_message_cost(msg)

    assert cost is not None
    assert cost["provider"] == "openai"
    assert cost["model"] == "gpt-5.4"
    assert round(cost["total_usd"], 3) == 2.026


def test_calculate_message_cost_for_alibaba_flat_rate_model():
    msg = make_message(
        model="kimi-k2.5",
        input_tokens=1_000_000,
        output_tokens=100_000,
        cache_read_tokens=200_000,
        cache_creation_tokens=50_000,
    )

    cost = calculate_message_cost(msg)

    assert cost is not None
    assert cost["provider"] == "alibabacloud"
    assert cost["model"] == "kimi-k2.5"
    assert round(cost["total_usd"], 4) == 0.9455


def test_calculate_message_cost_for_alibaba_tiered_model():
    msg = make_message(
        model="glm-5",
        input_tokens=10_000,
        output_tokens=1_000,
        cache_read_tokens=2_000,
        cache_creation_tokens=500,
    )

    cost = calculate_message_cost(msg)

    assert cost is not None
    assert cost["provider"] == "alibabacloud"
    assert cost["model"] == "glm-5"
    assert cost["pricing_tier"] == "0-32k"
    assert round(cost["total_usd"], 6) == 0.008455


def test_calculate_message_cost_returns_none_for_unknown_model():
    msg = make_message(model="mystery-model", input_tokens=1000, output_tokens=100)
    assert calculate_message_cost(msg) is None


def test_calculate_session_cost_sums_multiple_models():
    session = Session(
        id="s1",
        project_path="/tmp/project",
        project_name="project",
        created_at=datetime(2026, 4, 13, 12, 0, 0),
        messages=[
            make_message("Sonnet 4.6", input_tokens=1000, output_tokens=100),
            make_message("gpt-5.4", input_tokens=2000, output_tokens=200, cache_read_tokens=500),
        ],
    )

    cost = calculate_session_cost(session)

    assert cost["available"] is True
    assert cost["providers"] == ["claude", "openai"]
    assert cost["models"] == ["Sonnet 4.6", "gpt-5.4"]
    assert cost["input_tokens"] == 3000
    assert cost["output_tokens"] == 300
    assert cost["cache_read_tokens"] == 500
    assert cost["cache_creation_tokens"] == 0
    assert cost["total_usd"] > 0
```

**Шаг 2: Запусти тест и убедись, что он падает**

Запусти: `rtk pytest tests/test_pricing.py -v`
Ожидается: FAIL, потому что `viewer.pricing` ещё не существует.

**Шаг 3: Напиши минимальную реализацию pricing-модуля**

Создай `src/viewer/pricing.py`:

```python
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ModelPricing:
    provider: str
    canonical_model: str
    input_per_million: float
    output_per_million: float
    cache_read_per_million: float = 0.0
    cache_creation_per_million: float = 0.0


PRICING = {
    # Claude
    "claude-opus-4-6": ModelPricing("claude", "Opus 4.6", 5.00, 25.00, 0.50, 6.25),
    "claude-opus-4-5": ModelPricing("claude", "Opus 4.5", 5.00, 25.00, 0.50, 6.25),
    "claude-sonnet-4-6": ModelPricing("claude", "Sonnet 4.6", 3.00, 15.00, 0.30, 3.75),
    "claude-sonnet-4-5": ModelPricing("claude", "Sonnet 4.5", 3.00, 15.00, 0.30, 3.75),
    "claude-haiku-4-5": ModelPricing("claude", "Haiku 4.5", 1.00, 5.00, 0.10, 1.25),
    "sonnet 4.6": ModelPricing("claude", "Sonnet 4.6", 3.00, 15.00, 0.30, 3.75),
    "sonnet 4.5": ModelPricing("claude", "Sonnet 4.5", 3.00, 15.00, 0.30, 3.75),
    "opus 4.6": ModelPricing("claude", "Opus 4.6", 5.00, 25.00, 0.50, 6.25),
    "opus 4.5": ModelPricing("claude", "Opus 4.5", 5.00, 25.00, 0.50, 6.25),
    "haiku 4.5": ModelPricing("claude", "Haiku 4.5", 1.00, 5.00, 0.10, 1.25),

    # OpenAI
    "gpt-5.4": ModelPricing("openai", "gpt-5.4", 1.25, 7.50, 0.13, 0.0),
    "gpt-5": ModelPricing("openai", "gpt-5", 1.25, 10.00, 0.625, 0.0),
    "gpt-5.4-mini": ModelPricing("openai", "gpt-5.4-mini", 0.375, 2.25, 0.0375, 0.0),
    "gpt-5.4-nano": ModelPricing("openai", "gpt-5.4-nano", 0.10, 0.625, 0.01, 0.0),
    "codex-mini-latest": ModelPricing("openai", "codex-mini-latest", 1.50, 6.00, 0.375, 0.0),

    # Alibaba Cloud — flat-rate модели.
    "kimi-k2.5": ModelPricing("alibabacloud", "kimi-k2.5", 0.574, 3.011, 0.0574, 0.7175),
    "minimax-m2.5": ModelPricing("alibabacloud", "MiniMax-M2.5", 0.304, 1.213, 0.0304, 0.38),
}


ALIBABA_TIERED_PRICING = {
    "glm-5": [
        {"max_input_tokens": 32_000, "input_per_million": 0.573, "output_per_million": 2.58, "tier": "0-32k"},
        {"max_input_tokens": 166_000, "input_per_million": 0.86, "output_per_million": 3.154, "tier": "32k-166k"},
    ],
    "qwen3.5-plus": [
        {"max_input_tokens": 128_000, "input_per_million": 0.115, "output_per_million": 0.688, "tier": "0-128k"},
        {"max_input_tokens": 256_000, "input_per_million": 0.287, "output_per_million": 1.72, "tier": "128k-256k"},
        {"max_input_tokens": 1_000_000, "input_per_million": 0.573, "output_per_million": 3.44, "tier": "256k-1m"},
    ],
}


UNSUPPORTED_MODELS = {
    "qwen-plus",
    "qwen-plus-latest",
    "qwen-turbo",
    "qwen-turbo-latest",
}


def normalize_model_name(model: Optional[str]) -> str:
    return (model or "").strip().lower()


def get_model_pricing(model: Optional[str]) -> Optional[ModelPricing]:
    key = normalize_model_name(model)
    if not key or key in UNSUPPORTED_MODELS or key in ALIBABA_TIERED_PRICING:
        return None
    return PRICING.get(key)


def get_alibaba_tiered_pricing(model: Optional[str], input_tokens: int) -> Optional[dict]:
    key = normalize_model_name(model)
    tiers = ALIBABA_TIERED_PRICING.get(key)
    if not tiers:
        return None
    for tier in tiers:
        if input_tokens <= tier["max_input_tokens"]:
            return tier
    return None


def calculate_message_cost(message) -> Optional[dict]:
    tiered = get_alibaba_tiered_pricing(message.model, message.input_tokens or 0)
    if tiered is not None:
        input_price = tiered["input_per_million"]
        output_price = tiered["output_per_million"]
        input_cost = message.input_tokens * input_price / 1_000_000
        output_cost = message.output_tokens * output_price / 1_000_000
        cache_read_cost = message.cache_read_tokens * (input_price * 0.10) / 1_000_000
        cache_create_cost = message.cache_creation_tokens * (input_price * 1.25) / 1_000_000
        return {
            "provider": "alibabacloud",
            "model": normalize_model_name(message.model),
            "pricing_tier": tiered["tier"],
            "total_usd": input_cost + output_cost + cache_read_cost + cache_create_cost,
            "input_usd": input_cost,
            "output_usd": output_cost,
            "cache_read_usd": cache_read_cost,
            "cache_creation_usd": cache_create_cost,
        }

    pricing = get_model_pricing(message.model)
    if pricing is None:
        return None

    input_cost = message.input_tokens * pricing.input_per_million / 1_000_000
    output_cost = message.output_tokens * pricing.output_per_million / 1_000_000
    cache_read_cost = message.cache_read_tokens * pricing.cache_read_per_million / 1_000_000
    cache_create_cost = message.cache_creation_tokens * pricing.cache_creation_per_million / 1_000_000
    total_usd = input_cost + output_cost + cache_read_cost + cache_create_cost

    return {
        "provider": pricing.provider,
        "model": pricing.canonical_model,
        "total_usd": total_usd,
        "input_usd": input_cost,
        "output_usd": output_cost,
        "cache_read_usd": cache_read_cost,
        "cache_creation_usd": cache_create_cost,
    }


def calculate_session_cost(session) -> dict:
    total_usd = 0.0
    input_tokens = 0
    output_tokens = 0
    cache_read_tokens = 0
    cache_creation_tokens = 0
    models = []
    providers = []
    priced_messages = 0

    for msg in session.messages:
        input_tokens += msg.input_tokens or 0
        output_tokens += msg.output_tokens or 0
        cache_read_tokens += msg.cache_read_tokens or 0
        cache_creation_tokens += msg.cache_creation_tokens or 0

        message_cost = calculate_message_cost(msg)
        if message_cost is None:
            continue

        total_usd += message_cost["total_usd"]
        priced_messages += 1
        if message_cost["model"] not in models:
            models.append(message_cost["model"])
        if message_cost["provider"] not in providers:
            providers.append(message_cost["provider"])

    return {
        "available": priced_messages > 0,
        "total_usd": total_usd,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_creation_tokens": cache_creation_tokens,
        "models": models,
        "providers": providers,
        "priced_messages": priced_messages,
        "unpriced_messages": len(session.messages) - priced_messages,
    }
```

**Шаг 4: Запусти тест для проверки что проходит**

Запусти: `rtk pytest tests/test_pricing.py -v`
Ожидается: PASS

**Шаг 5: Коммит**

```bash
rtk git add tests/test_pricing.py src/viewer/pricing.py
rtk git commit -m "feat: добавить модуль расчета стоимости моделей"
```

---

### Задача 2: Пробросить real cost в API и покрыть это интеграционным тестом

**Файлы:**
- Изменить: `tests/test_integration.py`
- Изменить: `src/viewer/main.py`
- Изменить: `src/viewer/parsers/__init__.py` (только если понадобится экспорт нового модуля; если не нужен — не трогать)

**Шаг 1: Напиши падающий тест для `/api/conversation` с cost-объектом**

Добавь в `tests/test_integration.py`:

```python
def test_api_conversation_returns_real_cost(monkeypatch):
    base = datetime(2026, 4, 13, 12, 0, 0)
    session = Session(
        id="sess-cost",
        project_path="/tmp/test-project",
        project_name="test-project",
        created_at=base,
        messages=[
            Message(
                role="assistant",
                content="Claude answer",
                uuid="1",
                timestamp=base,
                session_id="sess-cost",
                project_path="/tmp/test-project",
                model="Sonnet 4.6",
                input_tokens=1000,
                output_tokens=100,
                cache_read_tokens=200,
                cache_creation_tokens=50,
            ),
            Message(
                role="assistant",
                content="OpenAI answer",
                uuid="2",
                timestamp=base + timedelta(minutes=1),
                session_id="sess-cost",
                project_path="/tmp/test-project",
                model="gpt-5.4",
                input_tokens=2000,
                output_tokens=200,
                cache_read_tokens=100,
            ),
        ],
    )

    class StubClaudeParser:
        def get_sessions(self, project_id):
            assert project_id == "test-project"
            return [session]

    monkeypatch.setattr("viewer.main.claude_parser", StubClaudeParser())

    response = client.get("/api/conversation/sess-cost?project_id=test-project&platform=claude")
    assert response.status_code == 200

    cost = response.json()["session"]["cost"]
    assert cost["available"] is True
    assert cost["input_tokens"] == 3000
    assert cost["output_tokens"] == 300
    assert cost["cache_read_tokens"] == 300
    assert cost["cache_creation_tokens"] == 50
    assert cost["providers"] == ["claude", "openai"]
    assert cost["models"] == ["Sonnet 4.6", "gpt-5.4"]
    assert cost["total_usd"] > 0
```

**Шаг 2: Запусти тест и убедись, что он падает**

Запусти: `rtk pytest tests/test_integration.py -k real_cost -v`
Ожидается: FAIL, потому что `session_to_dict()` пока не возвращает `cost`.

**Шаг 3: Реализуй минимальный код в API**

В `src/viewer/main.py`:
- импортируй `calculate_session_cost` из `viewer.pricing`
- рядом с `session_to_dict()` не добавляй новую бизнес-логику: просто вызови helper
- дополни результат `session_to_dict()` полем `cost`

Измени `session_to_dict()` так:

```python
from viewer.pricing import calculate_session_cost


def session_to_dict(session: Session, platform: str) -> dict:
    input_tokens = sum(m.input_tokens for m in session.messages)
    output_tokens = sum(m.output_tokens for m in session.messages)
    cache_read_tokens = sum(m.cache_read_tokens for m in session.messages)
    cache_creation_tokens = sum(m.cache_creation_tokens for m in session.messages)
    ended_at = get_ended_at(session)
    duration_seconds = get_duration_seconds(session)
    mcps, skills = classify_tools(session)
    cost = calculate_session_cost(session)

    return {
        "id": session.id,
        "project_name": session.project_name,
        "project_path": session.project_path,
        "platform": platform,
        "first_message": session.first_message,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "ended_at": ended_at.isoformat() if ended_at else None,
        "duration_seconds": duration_seconds,
        "mcps": mcps,
        "skills": skills,
        "message_count": len(session.messages),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_creation_tokens": cache_creation_tokens,
        "model": session.model,
        "effort": session.effort,
        "custom_title": session.custom_title,
        "cost": cost,
    }
```

**Шаг 4: Запусти тест повторно**

Запусти: `rtk pytest tests/test_integration.py -k real_cost -v`
Ожидается: PASS

**Шаг 5: Коммит**

```bash
rtk git add tests/test_integration.py src/viewer/main.py
rtk git commit -m "feat: добавить стоимость в api диалога"
```

---

### Задача 3: Показать real cost в Conversation UI

**Файлы:**
- Изменить: `tests/test_integration.py`
- Изменить: `src/viewer/templates/conversation.html`

**Шаг 1: Напиши падающий template-тест на контейнер и JS-рендер**

Добавь в `tests/test_integration.py`:

```python
def test_conversation_template_contains_real_cost_ui():
    response = client.get("/conversation/test-session?project_id=test-project&platform=claude")
    assert response.status_code == 200
    assert 'id="session-cost"' in response.text
    assert 'function renderSessionCost(session)' in response.text
    assert 'Real cost' in response.text
```

**Шаг 2: Запусти тест и убедись, что он падает**

Запусти: `rtk pytest tests/test_integration.py -k real_cost_ui -v`
Ожидается: FAIL

**Шаг 3: Добавь HTML-контейнер и JS-рендер**

В `src/viewer/templates/conversation.html` под `session-stats` добавь:

```html
<div id="session-cost" class="mt-2"></div>
```

В блоке загрузки сессии после `renderToolSummary(session);` добавь:

```javascript
renderSessionCost(session);
```

Ниже `renderToolSummary(session)` добавь функцию:

```javascript
function renderSessionCost(session) {
    const container = document.getElementById('session-cost');
    const cost = session.cost;

    if (!container || !cost || !cost.available) {
        container.innerHTML = '';
        return;
    }

    const total = '$' + cost.total_usd.toFixed(4);
    const cacheTotal = (cost.cache_read_tokens || 0) + (cost.cache_creation_tokens || 0);
    const providers = (cost.providers || []).join(', ');
    const models = (cost.models || []).join(', ');

    container.innerHTML = `
        <div class="alert alert-success py-2 px-3 mb-0">
            <div class="d-flex flex-wrap align-items-center gap-2">
                <span class="badge bg-success-subtle text-success-emphasis border">Real cost</span>
                <strong>${total}</strong>
                <span class="text-muted">${formatTokens(cost.input_tokens || 0)} in / ${formatTokens(cost.output_tokens || 0)} out / ${formatTokens(cacheTotal)} cache</span>
                ${models ? `<span class="text-muted">• ${escapeHtml(models)}</span>` : ''}
                ${providers ? `<span class="text-muted">• ${escapeHtml(providers)}</span>` : ''}
            </div>
        </div>
    `;
}
```

**Шаг 4: Запусти тест для проверки что проходит**

Запусти: `rtk pytest tests/test_integration.py -k real_cost_ui -v`
Ожидается: PASS

**Шаг 5: Коммит**

```bash
rtk git add tests/test_integration.py src/viewer/templates/conversation.html
rtk git commit -m "feat: показать стоимость на странице диалога"
```

---

### Задача 4: Проверить edge cases и не показывать ложную стоимость

**Файлы:**
- Изменить: `tests/test_pricing.py`
- Изменить: `tests/test_integration.py`
- Изменить: `src/viewer/pricing.py`
- Изменить: `src/viewer/templates/conversation.html`

**Шаг 1: Напиши падающие тесты на tiered/unknown модели**

Добавь в `tests/test_pricing.py`:

```python
def test_calculate_session_cost_marks_unavailable_for_unsupported_tiered_model():
    session = Session(
        id="s-tiered",
        project_path="/tmp/project",
        project_name="project",
        created_at=datetime(2026, 4, 13, 12, 0, 0),
        messages=[make_message("qwen-plus", input_tokens=1000, output_tokens=100)],
    )

    cost = calculate_session_cost(session)

    assert cost["available"] is False
    assert cost["total_usd"] == 0
    assert cost["models"] == []


def test_api_conversation_returns_unavailable_cost_for_unknown_model(monkeypatch):
    base = datetime(2026, 4, 13, 12, 0, 0)
    session = Session(
        id="sess-unknown",
        project_path="/tmp/test-project",
        project_name="test-project",
        created_at=base,
        messages=[
            Message(
                role="assistant",
                content="unknown",
                uuid="1",
                timestamp=base,
                session_id="sess-unknown",
                project_path="/tmp/test-project",
                model="mystery-model",
                input_tokens=500,
                output_tokens=50,
            )
        ],
    )

    class StubClaudeParser:
        def get_sessions(self, project_id):
            return [session]

    monkeypatch.setattr("viewer.main.claude_parser", StubClaudeParser())

    response = client.get("/api/conversation/sess-unknown?project_id=test-project&platform=claude")
    assert response.status_code == 200
    assert response.json()["session"]["cost"]["available"] is False
```

**Шаг 2: Запусти новые тесты и убедись, что они падают**

Запусти: `rtk pytest tests/test_pricing.py -k unavailable -v && rtk pytest tests/test_integration.py -k unavailable_cost -v`
Ожидается: FAIL

**Шаг 3: Реализуй минимальные guard-ветки**

В `src/viewer/pricing.py`:
- если ни одно сообщение не удалось прайсить, возвращай `available=False`
- `total_usd` оставляй `0.0`
- `models` и `providers` оставляй пустыми

В `src/viewer/templates/conversation.html`:
- не рендери `#session-cost`, если `available === false`
- не добавляй fallback вроде `~$0.00`

**Шаг 4: Запусти тесты повторно**

Запусти: `rtk pytest tests/test_pricing.py -k unavailable -v && rtk pytest tests/test_integration.py -k unavailable_cost -v`
Ожидается: PASS

**Шаг 5: Коммит**

```bash
rtk git add tests/test_pricing.py tests/test_integration.py src/viewer/pricing.py src/viewer/templates/conversation.html
rtk git commit -m "fix: не показывать стоимость для неподдерживаемых моделей"
```

---

### Задача 5: Полная проверка без регрессий

**Файлы:**
- Изменить: при необходимости только те файлы, где найдёшь мелкие ошибки после тестов

**Шаг 1: Запусти прицельные тесты по новой функциональности**

Запусти:

```bash
rtk pytest tests/test_pricing.py -v && rtk pytest tests/test_integration.py -k "real_cost or cost" -v
```

Ожидается: PASS

**Шаг 2: Запусти полный набор тестов**

Запусти:

```bash
rtk pytest tests/ -v
```

Ожидается: PASS без новых падений

**Шаг 3: Проверь diff перед финальным коммитом**

Запусти:

```bash
rtk git diff -- src/viewer/pricing.py src/viewer/main.py src/viewer/templates/conversation.html tests/test_pricing.py tests/test_integration.py
```

Ожидается: только pricing-модуль, API cost-поле, UI cost-блок и тесты

**Шаг 4: Финальный коммит**

```bash
rtk git add src/viewer/pricing.py src/viewer/main.py src/viewer/templates/conversation.html tests/test_pricing.py tests/test_integration.py
rtk git commit -m "feat: добавить расчет real cost для диалогов"
```

**Шаг 5: Ручная smoke-проверка в браузере**

Запусти приложение и проверь вручную:
- Claude-сессия с usage показывает `Real cost`
- breakdown содержит `in / out / cache`
- при нескольких моделях отображается список моделей
- для неподдерживаемой модели cost-блок отсутствует
- `Est. cost` нигде не появился

---

## Заметки по реализации

- Не трогать парсеры ради pricing: нужные токены уже есть.
- `message_to_dict()` менять не нужно, если UI показывает только session-level cost.
- Для multi-model сессии использовать сумму по `msg.model`, а не `session.model`.
- Если позже понадобится карточка стоимости на project/dashboard, переиспользовать только `calculate_session_cost()`; не дублировать формулы в JS.
- Для Alibaba Cloud использовать такие допущения, зафиксированные в коде и тестах:
  - `qwen3.5-plus` считать по **Global** pricing
  - `glm-5` считать по tiered pricing Chinese Mainland
  - `kimi-k2.5` считать как flat-rate Chinese Mainland
  - `MiniMax-M2.5` считать как flat-rate Chinese Mainland
- Если позже в логах появится deployment mode или официальные цены изменятся, обновлять таблицы и тесты отдельным точечным коммитом.

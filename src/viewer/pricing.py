import re
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
    "gpt-5.4": ModelPricing("openai", "gpt-5.4", 1.25, 7.50, 0.13, 0.0),
    "gpt-5": ModelPricing("openai", "gpt-5", 1.25, 10.00, 0.625, 0.0),
    "gpt-5.4-mini": ModelPricing("openai", "gpt-5.4-mini", 0.375, 2.25, 0.0375, 0.0),
    "gpt-5.4-nano": ModelPricing("openai", "gpt-5.4-nano", 0.10, 0.625, 0.01, 0.0),
    "codex-mini-latest": ModelPricing("openai", "codex-mini-latest", 1.50, 6.00, 0.375, 0.0),
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
    key = (model or "").strip().lower()
    if not key:
        return key
    return re.sub(r"\((low|medium|high)\)$", "", key).strip()


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
    input_tokens = message.input_tokens or 0
    output_tokens = message.output_tokens or 0
    cache_read_tokens = message.cache_read_tokens or 0
    cache_creation_tokens = message.cache_creation_tokens or 0

    tiered = get_alibaba_tiered_pricing(message.model, input_tokens)
    if tiered is not None:
        input_price = tiered["input_per_million"]
        output_price = tiered["output_per_million"]
        input_cost = input_tokens * input_price / 1_000_000
        output_cost = output_tokens * output_price / 1_000_000
        cache_read_cost = cache_read_tokens * (input_price * 0.10) / 1_000_000
        cache_creation_cost = cache_creation_tokens * (input_price * 1.25) / 1_000_000
        return {
            "provider": "alibabacloud",
            "model": normalize_model_name(message.model),
            "pricing_tier": tiered["tier"],
            "total_usd": input_cost + output_cost + cache_read_cost + cache_creation_cost,
            "input_usd": input_cost,
            "output_usd": output_cost,
            "cache_read_usd": cache_read_cost,
            "cache_creation_usd": cache_creation_cost,
        }

    pricing = get_model_pricing(message.model)
    if pricing is None:
        return None

    input_cost = input_tokens * pricing.input_per_million / 1_000_000
    output_cost = output_tokens * pricing.output_per_million / 1_000_000
    cache_read_cost = cache_read_tokens * pricing.cache_read_per_million / 1_000_000
    cache_creation_cost = cache_creation_tokens * pricing.cache_creation_per_million / 1_000_000

    return {
        "provider": pricing.provider,
        "model": pricing.canonical_model,
        "total_usd": input_cost + output_cost + cache_read_cost + cache_creation_cost,
        "input_usd": input_cost,
        "output_usd": output_cost,
        "cache_read_usd": cache_read_cost,
        "cache_creation_usd": cache_creation_cost,
    }


def is_pricing_eligible_message(message) -> bool:
    if message.model:
        return True
    return any(
        (
            message.input_tokens or 0,
            message.output_tokens or 0,
            message.cache_read_tokens or 0,
            message.cache_creation_tokens or 0,
        )
    )



def calculate_session_cost(session) -> dict:
    total_usd = 0.0
    input_usd = 0.0
    output_usd = 0.0
    cache_read_usd = 0.0
    cache_creation_usd = 0.0
    input_tokens = 0
    output_tokens = 0
    cache_read_tokens = 0
    cache_creation_tokens = 0
    priced_input_tokens = 0
    priced_output_tokens = 0
    priced_cache_read_tokens = 0
    priced_cache_creation_tokens = 0
    models = []
    providers = []
    priced_messages = 0
    eligible_messages = 0

    for message in session.messages:
        message_input_tokens = message.input_tokens or 0
        message_output_tokens = message.output_tokens or 0
        message_cache_read_tokens = message.cache_read_tokens or 0
        message_cache_creation_tokens = message.cache_creation_tokens or 0

        input_tokens += message_input_tokens
        output_tokens += message_output_tokens
        cache_read_tokens += message_cache_read_tokens
        cache_creation_tokens += message_cache_creation_tokens

        if is_pricing_eligible_message(message):
            eligible_messages += 1

        cost = calculate_message_cost(message)
        if cost is None:
            continue

        total_usd += cost["total_usd"]
        input_usd += cost["input_usd"]
        output_usd += cost["output_usd"]
        cache_read_usd += cost["cache_read_usd"]
        cache_creation_usd += cost["cache_creation_usd"]
        priced_messages += 1
        priced_input_tokens += message_input_tokens
        priced_output_tokens += message_output_tokens
        priced_cache_read_tokens += message_cache_read_tokens
        priced_cache_creation_tokens += message_cache_creation_tokens

        if cost["model"] not in models:
            models.append(cost["model"])
        if cost["provider"] not in providers:
            providers.append(cost["provider"])

    unpriced_messages = eligible_messages - priced_messages

    return {
        "available": priced_messages > 0,
        "partial": priced_messages > 0 and unpriced_messages > 0,
        "total_usd": total_usd,
        "input_usd": input_usd,
        "output_usd": output_usd,
        "cache_read_usd": cache_read_usd,
        "cache_creation_usd": cache_creation_usd,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_creation_tokens": cache_creation_tokens,
        "priced_input_tokens": priced_input_tokens,
        "priced_output_tokens": priced_output_tokens,
        "priced_cache_read_tokens": priced_cache_read_tokens,
        "priced_cache_creation_tokens": priced_cache_creation_tokens,
        "models": models,
        "providers": providers,
        "priced_messages": priced_messages,
        "unpriced_messages": unpriced_messages,
    }

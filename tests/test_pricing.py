from datetime import datetime

from viewer.parsers import Message, Session
from viewer.pricing import calculate_message_cost, calculate_session_cost



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
    assert round(cost["total_usd"], 4) == 4.7475



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



def test_calculate_message_cost_for_openai_model_with_quality_suffix():
    msg = make_message(
        model="gpt-5.4(high)",
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
    assert round(cost["total_usd"], 6) == 0.922455



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
    assert round(cost["total_usd"], 6) == 0.008783



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
    assert round(cost["total_usd"], 6) == 0.008565



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



def test_calculate_message_cost_for_minimax_flat_rate_model():
    msg = make_message(
        model="MiniMax-M2.5",
        input_tokens=1_000_000,
        output_tokens=100_000,
        cache_read_tokens=200_000,
        cache_creation_tokens=50_000,
    )

    cost = calculate_message_cost(msg)

    assert cost is not None
    assert cost["provider"] == "alibabacloud"
    assert cost["model"] == "MiniMax-M2.5"
    assert round(cost["total_usd"], 6) == 0.450380



def test_calculate_message_cost_for_qwen35_plus_global_tiered_model():
    msg = make_message(
        model="qwen3.5-plus",
        input_tokens=10_000,
        output_tokens=1_000,
        cache_read_tokens=2_000,
        cache_creation_tokens=500,
    )

    cost = calculate_message_cost(msg)

    assert cost is not None
    assert cost["provider"] == "alibabacloud"
    assert cost["model"] == "qwen3.5-plus"
    assert cost["pricing_tier"] == "0-128k"
    assert round(cost["total_usd"], 6) == 0.001933



def test_calculate_session_cost_marks_partial_for_mixed_supported_and_unknown_models():
    session = Session(
        id="s-partial",
        project_path="/tmp/project",
        project_name="project",
        created_at=datetime(2026, 4, 13, 12, 0, 0),
        messages=[
            make_message("Sonnet 4.6", input_tokens=1000, output_tokens=100),
            make_message("mystery-model", input_tokens=2000, output_tokens=200),
        ],
    )

    cost = calculate_session_cost(session)

    assert cost["available"] is True
    assert cost["partial"] is True
    assert cost["priced_messages"] == 1
    assert cost["unpriced_messages"] == 1
    assert cost["input_tokens"] == 3000
    assert cost["priced_input_tokens"] == 1000
    assert cost["priced_output_tokens"] == 100
    assert round(cost["total_usd"], 6) == 0.004500
    assert cost["models"] == ["Sonnet 4.6"]



def test_calculate_session_cost_ignores_user_and_system_messages_without_usage_for_unpriced_count():
    session = Session(
        id="s-codex-like",
        project_path="/tmp/project",
        project_name="project",
        created_at=datetime(2026, 4, 13, 12, 0, 0),
        messages=[
            Message(
                role="system",
                content="instructions",
                uuid="sys1",
                timestamp=datetime(2026, 4, 13, 12, 0, 0),
                session_id="s-codex-like",
                project_path="/tmp/project",
            ),
            Message(
                role="user",
                content="question",
                uuid="user1",
                timestamp=datetime(2026, 4, 13, 12, 0, 1),
                session_id="s-codex-like",
                project_path="/tmp/project",
            ),
            make_message("gpt-5.4", input_tokens=1000, output_tokens=100),
        ],
    )

    cost = calculate_session_cost(session)

    assert cost["available"] is True
    assert cost["partial"] is False
    assert cost["priced_messages"] == 1
    assert cost["unpriced_messages"] == 0

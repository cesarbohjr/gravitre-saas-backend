from app.services.intent_gateway import response_cache_get, response_cache_put, response_cache_clear
from app.services.prompt_prefix_cache import (
    anthropic_cached_system,
    confirmation_response_cache_isolated,
    history_as_prefix_messages,
    openai_system_messages,
    split_stable_prefix,
)


def setup_function() -> None:
    response_cache_clear()


def test_split_keeps_persona_before_volatile_rag() -> None:
    stable, volatile = split_stable_prefix(
        "You are Gravitre.\n\n## Your Internal Knowledge\nchunk-1\n"
    )
    assert "You are Gravitre." in stable
    assert "## Your Internal Knowledge" in volatile
    assert "chunk-1" in volatile


def test_anthropic_cache_control_on_stable_prefix() -> None:
    system = anthropic_cached_system(
        "Stable persona rules.\n\n## Conversation Task State\nawaiting confirm"
    )
    assert isinstance(system, list)
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert "Stable persona" in system[0]["text"]
    assert "awaiting confirm" in system[1]["text"]


def test_yes_no_stay_isolated_from_response_cache() -> None:
    assert confirmation_response_cache_isolated("yes")
    assert confirmation_response_cache_isolated("no")
    response_cache_put("org", "conv-a", "yes", "wrong cached confirm")
    assert response_cache_get("org", "conv-a", "yes") is None
    response_cache_put("org", "conv-a", "hey", "hello there")
    assert response_cache_get("org", "conv-a", "hey")[0] == "hello there"
    assert response_cache_get("org", "conv-b", "hey") is None


def test_history_prefix_messages_drop_empty() -> None:
    rows = history_as_prefix_messages(
        [
            {"role": "user", "content": "list contacts"},
            {"role": "assistant", "content": "  "},
            {"role": "system", "content": "nope"},
            {"role": "assistant", "content": "Here they are."},
        ]
    )
    assert rows == [
        {"role": "user", "content": "list contacts"},
        {"role": "assistant", "content": "Here they are."},
    ]


def test_openai_system_messages_split_stable_and_volatile() -> None:
    msgs = openai_system_messages(
        "You are Gravitre.\n\n## Operator Act Context\nintent=vague\n"
    )
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert "You are Gravitre." in msgs[0]["content"]
    assert "## Operator Act Context" not in msgs[0]["content"]
    assert "## Operator Act Context" in msgs[1]["content"]


def test_split_treats_operator_act_as_volatile() -> None:
    stable, volatile = split_stable_prefix(
        "Stable persona.\n\n## Operator Act Context\n{\"intent\":\"vague\"}\n"
    )
    assert "Stable persona" in stable
    assert "Operator Act Context" in volatile

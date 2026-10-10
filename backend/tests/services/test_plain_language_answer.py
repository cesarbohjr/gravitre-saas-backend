from app.services.plain_language_answer import read_next_steps, with_next_steps


def test_contact_read_gets_next_steps_without_internals() -> None:
    answer = with_next_steps("This HubSpot account has 57 contacts.", "hubspot.contacts.search", 57)
    assert answer.startswith("This HubSpot account has 57 contacts.")
    assert "Want me to list them" in answer
    assert "lifecycle stage" in answer
    assert "hubspot.contacts.search" not in answer


def test_empty_read_suggests_what_to_check() -> None:
    assert "broader search" in read_next_steps("hubspot.deals.list", 0)


def test_answer_that_already_closes_is_left_alone() -> None:
    text = "Found 3 invoices. Next step: send reminders."
    assert with_next_steps(text, "stripe.invoices.list", 3) == text
    assert with_next_steps("", "x", 1) == ""


def test_assistant_prompt_asks_for_plain_results_and_next_steps() -> None:
    from app.routers.assistant import ASSISTANT_SYSTEM_PROMPT

    assert "whether anything is needed from the user" in ASSISTANT_SYSTEM_PROMPT
    assert "plan or observation ids" in ASSISTANT_SYSTEM_PROMPT

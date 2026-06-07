from disruptron_api.backend.router import classify_intent


def test_routes_quick_qa_interactive() -> None:
    decision = classify_intent("What is the Jubilee line status?")
    assert decision.route.value == "interactive"
    assert decision.agent_id == "disruptron"


def test_routes_autonomous_investigate() -> None:
    decision = classify_intent("Investigate London transport and equity impact")
    assert decision.route.value == "autonomous"
    assert decision.agent_id == "disruptron"
    assert decision.prefetch_briefing is True


def test_routes_digest() -> None:
    decision = classify_intent("Give me my morning briefing")
    assert decision.route.value == "digest"
    assert decision.prefetch_briefing is True


def test_routes_image_interactive() -> None:
    decision = classify_intent("describe this", has_image=True)
    assert decision.route.value == "interactive"

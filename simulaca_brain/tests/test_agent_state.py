"""Unit tests for agent-owned internal needs state."""

from app.modules.agent.state import AgentNeeds, NeedType


def test_need_transitions_clamp_to_supported_range() -> None:
    """Need adjustments never create values outside the 0--100 range."""
    needs = AgentNeeds(hunger=95, thirst=5)

    assert needs.increase(NeedType.HUNGER, 10) == 100
    assert needs.decrease(NeedType.THIRST, 10) == 0
    assert needs.get(NeedType.HUNGER) == 100
    assert needs.get(NeedType.THIRST) == 0


def test_need_helpers_identify_critical_and_highest_needs() -> None:
    """State helpers expose urgency without introducing cognition behavior."""
    needs = AgentNeeds(fatigue=75, social=80)

    assert needs.is_critical(NeedType.SOCIAL)
    assert not needs.is_critical(NeedType.FATIGUE)
    assert needs.highest_priority() is NeedType.SOCIAL


def test_rest_is_accepted_as_a_legacy_fatigue_input() -> None:
    """Existing clients can migrate from the former rest field safely."""
    needs = AgentNeeds.model_validate({"rest": 40})

    assert needs.fatigue == 40
    assert needs.model_dump() == {
        "hunger": 0,
        "thirst": 0,
        "fatigue": 40,
        "safety": 0,
        "comfort": 0,
        "social": 0,
    }

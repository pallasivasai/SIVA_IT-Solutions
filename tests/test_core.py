from agents import build_team
from ai_providers import ProviderRouter


def test_team_members_and_roles():
    team = build_team()
    assert len(team) == 4
    assert [m["name"] for m in team] == ["Mira", "Dev", "Tara", "Shield"]


def test_fallback_detector_recognizes_quota_and_transient_errors():
    assert ProviderRouter.fallback_worthy(RuntimeError("429 rate limit exceeded"))
    assert ProviderRouter.fallback_worthy(RuntimeError("insufficient_quota"))
    assert ProviderRouter.fallback_worthy(RuntimeError("service unavailable"))


def test_fallback_detector_does_not_mask_auth_error():
    assert not ProviderRouter.fallback_worthy(RuntimeError("invalid API key"))

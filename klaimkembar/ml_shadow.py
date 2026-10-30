from dataclasses import dataclass
from math import isfinite
from typing import Protocol


class PairScorer(Protocol):
    """Future approved scorer: input contains numeric features only, never identifiers."""

    version: str

    def score(self, features: tuple[float, ...]) -> float: ...


@dataclass(frozen=True)
class ShadowResult:
    status: str
    score: float | None = None
    model_version: str | None = None


def score_in_shadow(features: tuple[float, ...], scorer: PairScorer | None) -> ShadowResult:
    """Isolated scaffold. Its result must never change the rules queue or decisions.

    No scorer is configured or called by the production workflow. This function is
    deliberately free of storage and log side effects until a reviewed model and
    audited persistence exist.
    """
    if scorer is None:
        return ShadowResult(status='not_available')
    if not features or not all(isfinite(value) for value in features):
        return ShadowResult(status='fallback')
    try:
        value = float(scorer.score(features))
        version = scorer.version
        if not version or not isfinite(value) or not 0 <= value <= 1:
            return ShadowResult(status='fallback')
        return ShadowResult(status='shadow_scored', score=value, model_version=version)
    except Exception:
        # Do not expose error details, input, or model internals in logs or response.
        return ShadowResult(status='fallback')

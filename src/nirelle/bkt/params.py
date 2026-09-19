"""Per-sub-skill BKT parameters."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillParams:
    """Standard four-parameter BKT model for one sub-skill.

    p_init:  P(L0) - prior probability the student already knows the skill.
    p_learn: P(T)  - base probability of learning the skill on one
                     opportunity (the "fixed learning rate" classic BKT
                     never adjusts).
    p_slip:  P(S)  - probability of an incorrect answer despite mastery.
    p_guess: P(G)  - probability of a correct answer despite non-mastery.

    These live in the curriculum layer (per the BRD's data architecture
    section): one set per sub-skill, shared across tenants, fit against
    real attempt data once a pilot school is live.
    """

    p_init: float = 0.3
    p_learn: float = 0.15
    p_slip: float = 0.1
    p_guess: float = 0.2

    def __post_init__(self) -> None:
        for name in ("p_init", "p_learn", "p_slip", "p_guess"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name}={value!r} must be in [0, 1]")

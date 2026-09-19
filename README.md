# Nirelle

See [`Nirelle-BRD.md`](./Nirelle-BRD.md) for full product context.

This package (`src/nirelle`) is the mastery-tracking core: a recency-weighted
Bayesian Knowledge Tracing (BKT) engine, plus the diagnose → remediate →
re-test → escalate loop from the BRD's "Product scope" section. It has no
database, API, or LLM layer yet — those wrap around this engine later.

## Layout

- `src/nirelle/bkt/params.py` — per-sub-skill BKT parameters (`p_init`,
  `p_learn`, `p_slip`, `p_guess`).
- `src/nirelle/bkt/model.py` — the recency-weighted BKT update itself
  (`update_mastery`), with a docstring explaining how it extends classic
  BKT and what's still a tunable approximation pending real pilot data.
- `src/nirelle/bkt/engine.py` — `MasteryEngine`: owns per-(student,
  sub-skill) state and the remediation-loop state machine (`LoopStage`).
- `src/nirelle/bkt/types.py` — `AttemptEvent`, `MasteryState`, `LoopStage`.

## Usage

```python
from nirelle import AttemptEvent, MasteryEngine, SkillParams

engine = MasteryEngine()
params = SkillParams(p_init=0.3, p_learn=0.15, p_slip=0.1, p_guess=0.2)

state = engine.get_or_create_state("student-123", "fractions.add_like_denom", params)

engine.record_attempt(state, AttemptEvent(correct=False, response_time_ms=6200), params)
engine.decide_question_count(state)  # -> 2 or 3

engine.begin_remediation(state)
engine.begin_retest(state)
engine.record_attempt(state, AttemptEvent(correct=True, response_time_ms=4100), params)
engine.evaluate_retest(state)  # -> RESOLVED / DIAGNOSTIC (loop again) / ESCALATED
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Open items carried over from the BRD

- `BKTConfig` (`window`, `decay`, `recency_weight`) and `SkillParams` are
  reasonable defaults, not fit to data yet — fit them against ASSISTments
  and/or real pilot-school attempt logs once available.
- Misconception detection, the pre-vetted explanation-strategy library, the
  LLM personalization layer, and the anti-cheating signal set are not part
  of this engine and are still open builds.

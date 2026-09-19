# Nirelle

See [`Nirelle-BRD.md`](./Nirelle-BRD.md) for full product context.

`src/nirelle` is the backend: recency-weighted BKT, the remediation-loop
state machine, misconception detection, LLM-personalized remediation
wording, anti-cheating signal detection, teacher/parent report generation,
the multi-tenant persistence layer, and an HTTP API wiring it all together.
`frontend/` is a React + TypeScript UI (student, teacher, and parent views)
over that API - see [`frontend/README.md`](./frontend/README.md).

See it live: [why recency-weighted BKT beats the alternatives](https://claude.ai/artifact/6tbgUwBYq8eHFmmiQkvdQD) -
a simulation (built on the real `nirelle.bkt` engine, not a reimplementation)
comparing heuristic rules, classic BKT, and Nirelle's recency-weighted BKT
across four scenarios. Also linked from the app's homepage.

## Quickstart

Two servers: the API (Python) and the UI (Node). Run both, in two terminals,
from the repo root.

```bash
# 1. Backend - installs the package + FastAPI/uvicorn, then runs the API
#    on http://localhost:8000. Auto-seeds the demo curriculum on startup.
python3 -m venv .venv
.venv/bin/pip install -e ".[api]"
.venv/bin/python -m nirelle.api

# 2. Frontend - in a second terminal, from the repo root
cd frontend
npm install
npm run dev             # http://localhost:5173, proxies /api -> :8000
```

Open `http://localhost:5173` and pick a role. Only Grade 4 Math (fractions)
has demo content - other grades correctly show an empty state rather than
fake data. See [`frontend/README.md`](./frontend/README.md) for the design
system and a tour of the pages.

## Layout

- `src/nirelle/bkt/` — the mastery-tracking "brain":
  - `params.py` — per-sub-skill BKT parameters (`p_init`, `p_learn`,
    `p_slip`, `p_guess`).
  - `model.py` — the recency-weighted BKT update itself (`update_mastery`),
    with a docstring explaining how it extends classic BKT and what's
    still a tunable approximation pending real pilot data.
  - `engine.py` — `MasteryEngine`: owns per-(student, sub-skill) state and
    the remediation-loop state machine (`LoopStage`), matching the BRD's
    diagnose → remediate → re-test → escalate → teacher-resolve flowchart.
  - `types.py` — `AttemptEvent`, `MasteryState`, `LoopStage`.
- `src/nirelle/diagnostics/` — misconception detection: diagnostic
  questions carry pre-tagged distractor choices (curriculum-authored, not
  LLM-inferred), and `identify_misconception` tallies which misconception
  a session's wrong answers point to, returning CONFIDENT / AMBIGUOUS /
  NONE rather than guessing under uncertainty.
- `src/nirelle/personalization/` — the LLM personalization layer, scoped
  exactly to the BRD's "LLM handles only the personalization layer
  (wording, examples, language)": a `Personalizer` protocol plus
  `IdentityPersonalizer` (no-op), `TemplatePersonalizer` (deterministic,
  no LLM), and `AnthropicPersonalizer` (real Claude-backed rewriting,
  lazy-imports `anthropic` so it's not a hard dependency - `pip install
  nirelle[llm]`).
- `src/nirelle/reports/` — `build_teacher_escalation` / `build_parent_report`:
  template-driven (not LLM-driven) generation of the teacher escalation
  view and parent report content described in the BRD, built from each
  student's actual diagnostic/attempt data so it's specific, not a data
  dump or generic boilerplate.
- `src/nirelle/integrity/` — the BRD's four anti-cheating signals
  (response-time outliers, answer-pattern-vs-difficulty mismatch, focus
  loss, mastery-prediction mismatch), combined so no single signal decides
  alone (`assess_session`).
- `src/nirelle/db/` — the two-layer schema from the BRD's "Data
  architecture and multi-tenancy" section:
  - `models.py` — curriculum layer (`SubSkill` with its BKT params,
    `ExplanationStrategy`, tenant-agnostic) and student-state layer
    (`School`, `Student`, `MasteryRecord`, `AttemptRecord`,
    `TeacherEscalation`, `ParentReport`, isolated per school). `Student`
    uses a composite `(school_id, id)` primary key since school-issued
    student IDs are only unique within a school, and every dependent table
    carries a matching composite foreign key, so tenant isolation is
    enforced at the schema level too.
  - `repository.py` — `CurriculumRepository` (tenant-agnostic) and
    `TenantRepository` (constructed with one fixed `school_id`; every
    method filters by it, and writes for another school's rows raise
    `PermissionError`) — the BRD's "row-level tenant isolation, every
    query filtered by school ID" MVP model, enforced in one place.
  - `session.py` — engine/session setup, defaulting to a local SQLite
    file; swap `database_url` for a Postgres DSN later without touching
    models or the repository layer.
- `src/nirelle/service.py` — `RemediationService`: the orchestration layer
  the API is a thin wrapper around. Builds a stateless `MasteryEngine` per
  call and always loads/saves state through the DB, so it's correct across
  multiple server processes/workers (unlike using `MasteryEngine`'s own
  in-memory cache directly).
- `src/nirelle/api/` — the HTTP API (FastAPI). `create_app()` wires
  school onboarding, curriculum, student, mastery-loop, escalation,
  parent-report, integrity-check, and demo-diagnostic routes over
  `RemediationService` and the other modules above; CORS is open by
  default for local frontend dev. **No auth exists yet** - `school_id` is
  trusted from the URL path, fine for the one-pilot-school MVP but a real
  gap before a second tenant (see `deps.py`). `python -m nirelle.api` runs
  it locally on port 8000, auto-seeding the demo curriculum.
- `src/nirelle/seed_data.py` — hand-built demo curriculum: Grade 4 Math,
  Fractions chapter, three sub-skills with real explanation strategies and
  misconception-tagged diagnostic questions (per the BRD's MVP sub-skill
  scope), plus display text (`prompt`/`label`) for the `/demo/...` API
  routes the frontend calls. `tests/test_end_to_end.py` runs the full loop
  against it at the Python level.
- `frontend/` — the UI. See [`frontend/README.md`](./frontend/README.md)
  for the design system and how to run it against this API.

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

Or via the DB-backed service (what the API uses internally):

```python
from nirelle import AttemptEvent, RemediationService
from nirelle.db import CurriculumRepository, TenantRepository, create_db_engine, init_db, make_session_factory

engine = create_db_engine("sqlite:///nirelle.db")
init_db(engine)
session = make_session_factory(engine)()

service = RemediationService(
    TenantRepository(session, school_id="school-a"), CurriculumRepository(session)
)
state = service.record_attempt("student-123", "fractions.add_like_denom", AttemptEvent(correct=True, response_time_ms=4100))
session.commit()
```

To run the API itself (not just import the library), see [Quickstart](#quickstart)
above. Once it's up:

```bash
curl -X POST localhost:8000/curriculum/sub-skills -H 'content-type: application/json' \
  -d '{"id": "fractions.add_like_denom", "name": "Adding fractions", "grade": 4, "subject": "math", "chapter": "fractions"}'
```

```python
from nirelle.diagnostics import DiagnosticResponse, identify_misconception
from nirelle.integrity import QuestionAttempt, assess_session
from nirelle.personalization import PersonalizationContext, TemplatePersonalizer
from nirelle.reports import build_teacher_escalation

# misconception detection
result = identify_misconception(question_bank, [DiagnosticResponse("q1", "3_8", 5200)])

# personalized remediation wording (deterministic; swap in AnthropicPersonalizer for real LLM wording)
TemplatePersonalizer().personalize(strategy.content, PersonalizationContext("Asha", grade=4, misconception_tag=result.tag))

# anti-cheating: flagged only once >= 2 of the 4 signals trigger together
assess_session([QuestionAttempt(True, 1400, 0.9)], predicted_mastery=0.9, tab_switch_count=0).flagged

# teacher escalation content, built from this student's actual case
build_teacher_escalation("Asha", "Adding fractions", "adds denominators instead of keeping them fixed", ["Number-line visual"], 2, 0.42, 0.75)
```

## Development

Backend tests (137 tests covering the engine, persistence, and API):

```bash
pip install -e ".[dev]"
pytest
```

Frontend build/lint - see [`frontend/README.md`](./frontend/README.md#development):

```bash
cd frontend && npm run build && npm run lint
```

The simulation behind the model-comparison link above is also reproducible:

```bash
python3 scripts/model_comparison_simulation.py
```

## Open items carried over from the BRD

- `BKTConfig`, `SkillParams`, and `IntegrityConfig` thresholds are
  reasonable defaults, not fit to data yet — tune them against ASSISTments
  and/or real pilot-school logs once available.
- No authentication on the API - see `src/nirelle/api/deps.py`.
- Alembic migrations (schema currently created via `create_all`, fine at
  pilot scale only, not once real data needs safe schema changes).
- A real content/question-serving layer (this repo covers misconception
  *detection* given pre-tagged diagnostic responses, not authoring/serving
  a full adaptive question bank at scale).
- Demo content covers one chapter (Grade 4 Math, Fractions) per the BRD's
  MVP scope; the UI's grade/subject picker for every other grade correctly
  shows an empty state rather than fake content - expanding coverage is
  future curriculum work.
- No real login: the frontend creates/resumes a demo student by a
  browser-local ID, with no server-side auth binding a session to a role
  or school. Switching roles/identities on the same device without an
  explicit "log out" can leave a stale student ID attached to a new name
  in `localStorage` - fine for a demo, not for multi-user pilot use.

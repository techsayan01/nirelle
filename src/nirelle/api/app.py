"""HTTP API: a thin wrapper over `nirelle.service.RemediationService` and
the other engine modules. Route handlers do request/response translation
only - all real logic lives in the modules they call.

School-scoped routes live under `/schools/{school_id}/...`; curriculum
routes (tenant-agnostic) live under `/curriculum/...`. See `deps.py` for
the current (lack of) auth model.
"""
from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from ..bkt import AttemptEvent, BKTConfig, DEFAULT_ENGINE_CONFIG, EngineConfig, MasteryState
from ..bkt import DEFAULT_CONFIG as DEFAULT_BKT_CONFIG
from ..db import (
    CurriculumRepository,
    SchoolRepository,
    TenantRepository,
    create_db_engine,
    init_db,
    make_session_factory,
    models,
)
from ..diagnostics import DiagnosticResponse, identify_misconception
from ..integrity import QuestionAttempt as IntegrityQuestionAttempt
from ..integrity import assess_session
from ..personalization import PersonalizationContext, Personalizer, TemplatePersonalizer
from ..reports import build_parent_report, build_teacher_escalation
from ..seed_data import demo_questions_for_sub_skill, seed_demo_curriculum
from ..service import NotFoundError, RemediationService
from . import schemas
from .deps import get_curriculum_repo, get_school_repo, get_session, get_tenant_repo


def _default_personalizer() -> Personalizer:
    """`AnthropicPersonalizer` when an API key is configured, otherwise the
    deterministic `TemplatePersonalizer` - the demo works with zero setup,
    and picks up real LLM wording the moment a key is provided.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return TemplatePersonalizer()
    from ..personalization import AnthropicPersonalizer

    try:
        return AnthropicPersonalizer(api_key=api_key)
    except ImportError:
        return TemplatePersonalizer()


def create_app(
    database_url: str = "sqlite:///nirelle.db",
    bkt_config: BKTConfig = DEFAULT_BKT_CONFIG,
    engine_config: EngineConfig = DEFAULT_ENGINE_CONFIG,
    cors_origins: list[str] | None = None,
    seed_demo: bool = True,
    personalizer: Personalizer | None = None,
) -> FastAPI:
    app = FastAPI(title="Nirelle", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins if cors_origins is not None else ["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    engine = create_db_engine(database_url)
    init_db(engine)
    app.state.session_factory = make_session_factory(engine)
    app.state.bkt_config = bkt_config
    app.state.engine_config = engine_config
    app.state.personalizer = personalizer if personalizer is not None else _default_personalizer()

    if seed_demo:
        with app.state.session_factory() as seed_session:
            seed_demo_curriculum(seed_session)
            seed_session.commit()

    def _service(repo: TenantRepository, session: Session) -> RemediationService:
        return RemediationService(
            repo, CurriculumRepository(session), app.state.bkt_config, app.state.engine_config
        )

    def _state_out(service: RemediationService, state: MasteryState) -> schemas.MasteryStateOut:
        return schemas.MasteryStateOut(
            student_id=state.student_id,
            sub_skill_id=state.sub_skill_id,
            p_mastery=state.p_mastery,
            stage=state.stage,
            cycle_count=state.cycle_count,
            attempt_count=state.attempt_count,
            recommended_question_count=service.decide_question_count(state),
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # --- schools (tenants) ------------------------------------------------

    @app.post("/schools", response_model=schemas.SchoolOut, status_code=201)
    def create_school(
        payload: schemas.SchoolCreate, repo: SchoolRepository = Depends(get_school_repo)
    ):
        if repo.get_school(payload.id) is not None:
            raise HTTPException(409, f"school_id={payload.id!r} already exists")
        return repo.add_school(models.School(**payload.model_dump()))

    @app.get("/schools/{school_id}", response_model=schemas.SchoolOut)
    def get_school(school_id: str, repo: SchoolRepository = Depends(get_school_repo)):
        row = repo.get_school(school_id)
        if row is None:
            raise HTTPException(404, f"school_id={school_id!r} not found")
        return row

    # --- curriculum layer ----------------------------------------------

    @app.get("/curriculum/sub-skills", response_model=list[schemas.SubSkillOut])
    def list_sub_skills(
        grade: int | None = None,
        subject: str | None = None,
        repo: CurriculumRepository = Depends(get_curriculum_repo),
    ):
        return repo.list_sub_skills(grade=grade, subject=subject)

    @app.post("/curriculum/sub-skills", response_model=schemas.SubSkillOut, status_code=201)
    def create_sub_skill(
        payload: schemas.SubSkillCreate, repo: CurriculumRepository = Depends(get_curriculum_repo)
    ):
        if repo.get_sub_skill(payload.id) is not None:
            raise HTTPException(409, f"sub_skill_id={payload.id!r} already exists")
        return repo.add_sub_skill(models.SubSkill(**payload.model_dump()))

    @app.get("/curriculum/sub-skills/{sub_skill_id}", response_model=schemas.SubSkillOut)
    def get_sub_skill(
        sub_skill_id: str, repo: CurriculumRepository = Depends(get_curriculum_repo)
    ):
        row = repo.get_sub_skill(sub_skill_id)
        if row is None:
            raise HTTPException(404, f"sub_skill_id={sub_skill_id!r} not found")
        return row

    @app.get(
        "/curriculum/sub-skills/{sub_skill_id}/strategies",
        response_model=list[schemas.ExplanationStrategyOut],
    )
    def list_strategies(
        sub_skill_id: str,
        misconception_tag: str | None = None,
        repo: CurriculumRepository = Depends(get_curriculum_repo),
    ):
        sub_skill = repo.get_sub_skill(sub_skill_id)
        if sub_skill is None:
            raise HTTPException(404, f"sub_skill_id={sub_skill_id!r} not found")
        if misconception_tag is not None:
            return repo.strategies_for_misconception(sub_skill_id, misconception_tag)
        return sub_skill.explanation_strategies

    @app.post(
        "/curriculum/sub-skills/{sub_skill_id}/personalize", response_model=schemas.PersonalizeOut
    )
    def personalize_strategy(
        sub_skill_id: str,
        payload: schemas.PersonalizeRequest,
        session: Session = Depends(get_session),
    ):
        strategy = session.get(models.ExplanationStrategy, payload.strategy_id)
        if strategy is None or strategy.sub_skill_id != sub_skill_id:
            raise HTTPException(
                404, f"strategy_id={payload.strategy_id!r} not found on sub_skill_id={sub_skill_id!r}"
            )
        content = app.state.personalizer.personalize(
            strategy.content,
            PersonalizationContext(
                student_display_name=payload.student_display_name,
                grade=payload.grade,
                misconception_tag=strategy.misconception_tag,
                tone_hint=payload.tone_hint,
            ),
        )
        return schemas.PersonalizeOut(content=content)

    @app.post(
        "/curriculum/sub-skills/{sub_skill_id}/strategies",
        response_model=schemas.ExplanationStrategyOut,
        status_code=201,
    )
    def add_strategy(
        sub_skill_id: str,
        payload: schemas.ExplanationStrategyCreate,
        repo: CurriculumRepository = Depends(get_curriculum_repo),
    ):
        if repo.get_sub_skill(sub_skill_id) is None:
            raise HTTPException(404, f"sub_skill_id={sub_skill_id!r} not found")
        return repo.add_explanation_strategy(
            models.ExplanationStrategy(sub_skill_id=sub_skill_id, **payload.model_dump())
        )

    # --- students -----------------------------------------------------------

    @app.post(
        "/schools/{school_id}/students", response_model=schemas.StudentOut, status_code=201
    )
    def create_student(
        school_id: str,
        payload: schemas.StudentCreate,
        session: Session = Depends(get_session),
        repo: TenantRepository = Depends(get_tenant_repo),
    ):
        if SchoolRepository(session).get_school(school_id) is None:
            raise HTTPException(404, f"school_id={school_id!r} not found - onboard it via POST /schools first")
        if repo.get_student(payload.id) is not None:
            raise HTTPException(409, f"student_id={payload.id!r} already exists at this school")
        return repo.add_student(models.Student(school_id=school_id, **payload.model_dump()))

    @app.get(
        "/schools/{school_id}/students/{student_id}", response_model=schemas.StudentOut
    )
    def get_student(
        school_id: str, student_id: str, repo: TenantRepository = Depends(get_tenant_repo)
    ):
        row = repo.get_student(student_id)
        if row is None:
            raise HTTPException(404, f"student_id={student_id!r} not found")
        return row

    # --- mastery loop -------------------------------------------------------

    @app.get(
        "/schools/{school_id}/students/{student_id}/subskills/{sub_skill_id}",
        response_model=schemas.MasteryStateOut,
    )
    def get_state(
        school_id: str,
        student_id: str,
        sub_skill_id: str,
        session: Session = Depends(get_session),
        repo: TenantRepository = Depends(get_tenant_repo),
    ):
        service = _service(repo, session)
        try:
            state = service.get_or_create_state(student_id, sub_skill_id)
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        return _state_out(service, state)

    @app.post(
        "/schools/{school_id}/students/{student_id}/subskills/{sub_skill_id}/attempts",
        response_model=schemas.MasteryStateOut,
    )
    def record_attempt(
        school_id: str,
        student_id: str,
        sub_skill_id: str,
        payload: schemas.AttemptIn,
        session: Session = Depends(get_session),
        repo: TenantRepository = Depends(get_tenant_repo),
    ):
        service = _service(repo, session)
        attempt = AttemptEvent(
            correct=payload.correct,
            response_time_ms=payload.response_time_ms,
            stage=payload.stage,
            misconception_tag=payload.misconception_tag,
        )
        try:
            state = service.record_attempt(student_id, sub_skill_id, attempt)
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        return _state_out(service, state)

    def _stage_transition_route(path_suffix: str, apply_name: str):
        @app.post(
            f"/schools/{{school_id}}/students/{{student_id}}/subskills/{{sub_skill_id}}/{path_suffix}",
            response_model=schemas.MasteryStateOut,
            name=f"{path_suffix}",
        )
        def endpoint(
            school_id: str,
            student_id: str,
            sub_skill_id: str,
            session: Session = Depends(get_session),
            repo: TenantRepository = Depends(get_tenant_repo),
        ):
            service = _service(repo, session)
            method = getattr(service, apply_name)
            try:
                state = method(student_id, sub_skill_id)
            except NotFoundError as exc:
                raise HTTPException(404, str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
            return _state_out(service, state)

        return endpoint

    _stage_transition_route("begin-remediation", "begin_remediation")
    _stage_transition_route("begin-retest", "begin_retest")
    _stage_transition_route("evaluate-retest", "evaluate_retest")
    _stage_transition_route("resolve-teacher-escalation", "resolve_teacher_escalation")
    _stage_transition_route("finalize-teacher-retest", "finalize_teacher_retest")

    # --- escalations / parent reports -------------------------------------------

    @app.get("/schools/{school_id}/escalations", response_model=list[schemas.TeacherEscalationOut])
    def list_escalations(
        school_id: str,
        resolved: bool | None = None,
        repo: TenantRepository = Depends(get_tenant_repo),
    ):
        return repo.list_escalations(resolved=resolved)

    @app.get(
        "/schools/{school_id}/escalations/{escalation_id}",
        response_model=schemas.TeacherEscalationOut,
    )
    def get_escalation(
        school_id: str, escalation_id: int, repo: TenantRepository = Depends(get_tenant_repo)
    ):
        row = repo.get_teacher_escalation(escalation_id)
        if row is None:
            raise HTTPException(404, f"escalation_id={escalation_id!r} not found")
        return row

    @app.post(
        "/schools/{school_id}/escalations",
        response_model=schemas.TeacherEscalationOut,
        status_code=201,
    )
    def create_escalation(
        school_id: str,
        payload: schemas.TeacherEscalationCreate,
        session: Session = Depends(get_session),
        repo: TenantRepository = Depends(get_tenant_repo),
    ):
        student = repo.get_student(payload.student_id)
        if student is None:
            raise HTTPException(404, f"student_id={payload.student_id!r} not found")
        sub_skill = CurriculumRepository(session).get_sub_skill(payload.sub_skill_id)
        if sub_skill is None:
            raise HTTPException(404, f"sub_skill_id={payload.sub_skill_id!r} not found")

        try:
            content = build_teacher_escalation(
                student_display_name=student.display_name,
                sub_skill_name=sub_skill.name,
                misconception_description=payload.misconception_description,
                remediation_strategies_tried=payload.remediation_strategies_tried,
                attempt_count=payload.attempt_count,
                last_mastery_score=payload.last_mastery_score,
                floor_mastery=payload.floor_mastery,
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

        return repo.add_teacher_escalation(
            models.TeacherEscalation(
                school_id=school_id,
                class_section=student.class_section,
                student_id=student.id,
                sub_skill_id=sub_skill.id,
                misconception_summary=content.misconception_summary,
                remediation_attempted=content.remediation_attempted,
                attempt_count=content.attempt_count,
                one_on_one_focus=content.one_on_one_focus,
            )
        )

    @app.post(
        "/schools/{school_id}/escalations/{escalation_id}/resolve",
        response_model=schemas.TeacherEscalationOut,
    )
    def resolve_escalation(
        school_id: str,
        escalation_id: int,
        payload: schemas.EscalationResolve,
        repo: TenantRepository = Depends(get_tenant_repo),
    ):
        row = repo.get_teacher_escalation(escalation_id)
        if row is None:
            raise HTTPException(404, f"escalation_id={escalation_id!r} not found")
        return repo.resolve_teacher_escalation_record(row, payload.resolved_by)

    @app.get(
        "/schools/{school_id}/students/{student_id}/parent-reports",
        response_model=list[schemas.ParentReportOut],
    )
    def list_parent_reports(
        school_id: str, student_id: str, repo: TenantRepository = Depends(get_tenant_repo)
    ):
        return repo.parent_reports_for_student(student_id)

    @app.post(
        "/schools/{school_id}/parent-reports",
        response_model=schemas.ParentReportOut,
        status_code=201,
    )
    def create_parent_report(
        school_id: str,
        payload: schemas.ParentReportCreate,
        repo: TenantRepository = Depends(get_tenant_repo),
    ):
        student = repo.get_student(payload.student_id)
        if student is None:
            raise HTTPException(404, f"student_id={payload.student_id!r} not found")

        try:
            content = build_parent_report(
                student_display_name=student.display_name,
                sub_skill_name_plain=payload.sub_skill_name_plain,
                at_home_actions=payload.at_home_actions,
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

        return repo.add_parent_report(
            models.ParentReport(
                school_id=school_id,
                class_section=student.class_section,
                student_id=student.id,
                sub_skill_id=payload.sub_skill_id,
                plain_summary=content.plain_summary,
                at_home_actions=content.at_home_actions,
            )
        )

    # --- integrity (stateless - not tied to a tenant) ---------------------------

    @app.post("/integrity/check", response_model=schemas.IntegrityAssessmentOut)
    def integrity_check(payload: schemas.IntegrityCheckIn):
        def to_domain(items: list[schemas.QuestionAttemptIn]) -> list[IntegrityQuestionAttempt]:
            return [
                IntegrityQuestionAttempt(a.correct, a.response_time_ms, a.difficulty) for a in items
            ]

        assessment = assess_session(
            to_domain(payload.session),
            predicted_mastery=payload.predicted_mastery,
            retest_session=to_domain(payload.retest_session)
            if payload.retest_session is not None
            else None,
            tab_switch_count=payload.tab_switch_count,
        )
        return schemas.IntegrityAssessmentOut(
            flagged=assessment.flagged,
            signals=[
                schemas.IntegritySignalOut(name=s.name.value, triggered=s.triggered, detail=s.detail)
                for s in assessment.signals
            ],
        )

    # --- demo diagnostics (hand-built Grade 4 Math / Fractions content) ---------
    #
    # Serves nirelle.seed_data's static question bank. Choice payloads never
    # include the correct answer or misconception tag - grading happens
    # server-side in the responses endpoint below.

    @app.get(
        "/demo/sub-skills/{sub_skill_id}/questions", response_model=list[schemas.DemoQuestionOut]
    )
    def demo_questions(sub_skill_id: str):
        questions = demo_questions_for_sub_skill(sub_skill_id)
        if not questions:
            raise HTTPException(404, f"no demo questions for sub_skill_id={sub_skill_id!r}")
        return [
            schemas.DemoQuestionOut(
                id=q.id,
                sub_skill_id=q.sub_skill_id,
                difficulty=q.difficulty,
                prompt=q.prompt,
                choices=[schemas.DemoChoiceOut(id=c.id, label=c.label) for c in q.choices],
            )
            for q in questions
        ]

    @app.post(
        "/demo/sub-skills/{sub_skill_id}/responses", response_model=schemas.DemoSubmissionOut
    )
    def demo_grade_responses(sub_skill_id: str, payload: schemas.DemoSubmissionIn):
        questions = demo_questions_for_sub_skill(sub_skill_id)
        if not questions:
            raise HTTPException(404, f"no demo questions for sub_skill_id={sub_skill_id!r}")
        question_bank = {q.id: q for q in questions}

        domain_responses = []
        graded = []
        for r in payload.responses:
            question = question_bank.get(r.question_id)
            if question is None:
                raise HTTPException(
                    422, f"question_id={r.question_id!r} does not belong to sub_skill_id={sub_skill_id!r}"
                )
            domain_responses.append(
                DiagnosticResponse(
                    question_id=r.question_id,
                    selected_choice_id=r.selected_choice_id,
                    response_time_ms=r.response_time_ms,
                )
            )
            graded.append(
                schemas.DemoGradedResponseOut(
                    question_id=r.question_id,
                    correct=r.selected_choice_id == question.correct_choice_id,
                )
            )

        result = identify_misconception(question_bank, domain_responses)
        return schemas.DemoSubmissionOut(
            graded=graded,
            misconception_tag=result.tag,
            misconception_confidence=result.confidence.value,
        )

    return app

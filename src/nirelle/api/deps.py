"""FastAPI dependency wiring for DB sessions and repositories.

No authentication/authorization exists yet: `school_id` is trusted
straight from the URL path. That's fine for the one-pilot-school MVP but
is a real gap before onboarding a second school - a caller who knows
another school's ID and student IDs could address its data. Add real
per-school auth (e.g. a JWT carrying the caller's school_id, checked
against the path) before that happens.
"""
from __future__ import annotations

from typing import Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from ..db import CurriculumRepository, SchoolRepository, TenantRepository, session_scope


def get_session(request: Request) -> Iterator[Session]:
    with session_scope(request.app.state.session_factory) as session:
        yield session


def get_school_repo(session: Session = Depends(get_session)) -> SchoolRepository:
    return SchoolRepository(session)


def get_curriculum_repo(session: Session = Depends(get_session)) -> CurriculumRepository:
    return CurriculumRepository(session)


def get_tenant_repo(
    school_id: str, session: Session = Depends(get_session)
) -> TenantRepository:
    return TenantRepository(session, school_id=school_id)

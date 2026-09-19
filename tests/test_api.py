from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from nirelle.api import create_app
from nirelle.bkt import EngineConfig


@pytest.fixture
def client():
    # seed_demo=False keeps these tests isolated from the demo curriculum
    # content; see test_demo_routes() for coverage of the seeded data.
    app = create_app(
        database_url="sqlite:///:memory:",
        engine_config=EngineConfig(floor_mastery=0.75, max_cycles=2),
        seed_demo=False,
    )
    return TestClient(app)


@pytest.fixture
def sub_skill(client):
    resp = client.post(
        "/curriculum/sub-skills",
        json={
            "id": "fractions.add_like_denom",
            "name": "Adding fractions with like denominators",
            "grade": 4,
            "subject": "math",
            "chapter": "fractions",
        },
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
def school(client):
    resp = client.post("/schools", json={"id": "school-a", "name": "Green Valley School"})
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
def student(client, school, sub_skill):
    resp = client.post(
        "/schools/school-a/students",
        json={"id": "student-1", "class_section": "4A", "display_name": "Asha"},
    )
    assert resp.status_code == 201
    return resp.json()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_create_and_fetch_sub_skill(client):
    resp = client.post(
        "/curriculum/sub-skills",
        json={"id": "s1", "name": "Test", "grade": 4, "subject": "math", "chapter": "c1"},
    )
    assert resp.status_code == 201
    assert resp.json()["p_init"] == 0.3

    fetched = client.get("/curriculum/sub-skills/s1")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Test"


def test_create_sub_skill_twice_conflicts(client, sub_skill):
    resp = client.post("/curriculum/sub-skills", json=sub_skill)
    assert resp.status_code == 409


def test_get_unknown_sub_skill_404(client):
    resp = client.get("/curriculum/sub-skills/nope")
    assert resp.status_code == 404


def test_add_strategy_to_unknown_sub_skill_404(client):
    resp = client.post(
        "/curriculum/sub-skills/nope/strategies",
        json={"misconception_tag": "t", "content": "c"},
    )
    assert resp.status_code == 404


def test_create_and_fetch_school(client):
    resp = client.post("/schools", json={"id": "school-x", "name": "Riverside School"})
    assert resp.status_code == 201

    fetched = client.get("/schools/school-x")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Riverside School"


def test_create_school_twice_conflicts(client, school):
    resp = client.post("/schools", json=school)
    assert resp.status_code == 409


def test_get_unknown_school_404(client):
    resp = client.get("/schools/nope")
    assert resp.status_code == 404


def test_create_student_for_nonexistent_school_rejected(client, sub_skill):
    """Regression test: SQLite ignores FK constraints unless PRAGMA
    foreign_keys=ON is set per connection. Without it, this would silently
    succeed instead of rejecting a student for a school that was never
    onboarded.
    """
    resp = client.post(
        "/schools/ghost-school/students",
        json={"id": "student-1", "class_section": "4A", "display_name": "Asha"},
    )
    assert resp.status_code == 404


def test_create_student_and_conflict_on_duplicate(client, student):
    resp = client.post(
        "/schools/school-a/students",
        json={"id": "student-1", "class_section": "4B", "display_name": "Someone Else"},
    )
    assert resp.status_code == 409


def test_get_student(client, student):
    resp = client.get("/schools/school-a/students/student-1")
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Asha"


def test_get_unknown_student_404(client, school):
    resp = client.get("/schools/school-a/students/nobody")
    assert resp.status_code == 404


def test_get_state_creates_lazily_and_seeds_from_sub_skill(client, sub_skill, student):
    resp = client.get(f"/schools/school-a/students/student-1/subskills/{sub_skill['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["p_mastery"] == sub_skill["p_init"]
    assert body["stage"] == "diagnostic"


def test_get_state_unknown_student_404(client, sub_skill):
    resp = client.get(f"/schools/school-a/students/nobody/subskills/{sub_skill['id']}")
    assert resp.status_code == 404


def test_record_attempt_updates_mastery(client, sub_skill, student):
    resp = client.post(
        f"/schools/school-a/students/student-1/subskills/{sub_skill['id']}/attempts",
        json={"correct": True, "response_time_ms": 4000},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["p_mastery"] > sub_skill["p_init"]
    assert body["attempt_count"] == 1


def test_stage_transition_wrong_stage_returns_409(client, sub_skill, student):
    client.get(f"/schools/school-a/students/student-1/subskills/{sub_skill['id']}")  # create state
    resp = client.post(
        f"/schools/school-a/students/student-1/subskills/{sub_skill['id']}/evaluate-retest"
    )
    assert resp.status_code == 409


def test_full_loop_via_http_reaches_escalation_and_resolution(client, sub_skill, student):
    skill_id = sub_skill["id"]
    base = f"/schools/school-a/students/student-1/subskills/{skill_id}"

    resp = None
    for _ in range(2):  # max_cycles=2
        client.post(f"{base}/attempts", json={"correct": False, "response_time_ms": 4000})
        client.post(f"{base}/begin-remediation")
        client.post(f"{base}/begin-retest")
        client.post(f"{base}/attempts", json={"correct": False, "response_time_ms": 4000})
        resp = client.post(f"{base}/evaluate-retest")

    assert resp.json()["stage"] == "escalated"

    client.post(f"{base}/resolve-teacher-escalation")
    client.post(f"{base}/attempts", json={"correct": True, "response_time_ms": 4000})
    final = client.post(f"{base}/finalize-teacher-retest")
    assert final.json()["stage"] == "resolved"


def test_create_and_resolve_escalation(client, sub_skill, student):
    resp = client.post(
        "/schools/school-a/escalations",
        json={
            "student_id": "student-1",
            "sub_skill_id": sub_skill["id"],
            "misconception_description": "adds denominators instead of keeping them fixed",
            "remediation_strategies_tried": ["Number-line visual"],
            "attempt_count": 2,
            "last_mastery_score": 0.4,
            "floor_mastery": 0.75,
        },
    )
    assert resp.status_code == 201
    escalation = resp.json()
    assert "Asha" in escalation["misconception_summary"]
    assert escalation["resolved_at"] is None

    resolved = client.post(
        f"/schools/school-a/escalations/{escalation['id']}/resolve",
        json={"resolved_by": "teacher-1"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["resolved_by"] == "teacher-1"
    assert resolved.json()["resolved_at"] is not None


def test_escalation_cannot_be_resolved_from_another_school(client, sub_skill, student):
    resp = client.post(
        "/schools/school-a/escalations",
        json={
            "student_id": "student-1",
            "sub_skill_id": sub_skill["id"],
            "misconception_description": "misc",
            "remediation_strategies_tried": ["Strategy"],
            "attempt_count": 1,
            "last_mastery_score": 0.4,
            "floor_mastery": 0.75,
        },
    )
    escalation_id = resp.json()["id"]

    cross_tenant = client.post(
        f"/schools/school-b/escalations/{escalation_id}/resolve",
        json={"resolved_by": "teacher-2"},
    )
    assert cross_tenant.status_code == 404


def test_create_parent_report(client, sub_skill, student):
    resp = client.post(
        "/schools/school-a/parent-reports",
        json={
            "student_id": "student-1",
            "sub_skill_id": sub_skill["id"],
            "sub_skill_name_plain": "adding fractions",
            "at_home_actions": ["Practice with a pizza cut into slices."],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "Asha" in body["plain_summary"]
    assert "pizza" in body["at_home_actions"]


def test_create_parent_report_rejects_bad_action_count(client, sub_skill, student):
    resp = client.post(
        "/schools/school-a/parent-reports",
        json={
            "student_id": "student-1",
            "sub_skill_id": sub_skill["id"],
            "sub_skill_name_plain": "adding fractions",
            "at_home_actions": [],
        },
    )
    assert resp.status_code == 422


def test_integrity_check_endpoint(client):
    resp = client.post(
        "/integrity/check",
        json={
            "session": [
                {"correct": True, "response_time_ms": 1500, "difficulty": 0.9},
                {"correct": True, "response_time_ms": 1500, "difficulty": 0.85},
                {"correct": False, "response_time_ms": 5000, "difficulty": 0.2},
                {"correct": False, "response_time_ms": 5000, "difficulty": 0.15},
            ],
            "predicted_mastery": 0.9,
            "tab_switch_count": 0,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["flagged"] is True
    assert len(body["signals"]) == 4

"""API coverage for the demo-curriculum routes and the listing/personalize
endpoints added for the frontend: list sub-skills, list strategies,
personalize, list escalations, list parent reports, demo questions/grading.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from nirelle.api import create_app


@pytest.fixture
def client():
    app = create_app(database_url="sqlite:///:memory:")  # seed_demo=True by default
    return TestClient(app)


def test_demo_curriculum_is_seeded_on_startup(client):
    resp = client.get("/curriculum/sub-skills")
    assert resp.status_code == 200
    ids = {s["id"] for s in resp.json()}
    assert "fractions.add_like_denominators" in ids
    assert "fractions.identify_parts" in ids
    assert "fractions.add_unlike_denominators" in ids


def test_list_sub_skills_filters_by_grade(client):
    resp = client.get("/curriculum/sub-skills", params={"grade": 4, "subject": "math"})
    assert resp.status_code == 200
    assert len(resp.json()) == 3

    resp = client.get("/curriculum/sub-skills", params={"grade": 7})
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_strategies_for_sub_skill(client):
    resp = client.get("/curriculum/sub-skills/fractions.add_like_denominators/strategies")
    assert resp.status_code == 200
    strategies = resp.json()
    assert len(strategies) == 1
    assert strategies[0]["misconception_tag"] == "adds_denominators"


def test_list_strategies_filters_by_misconception_tag(client):
    resp = client.get(
        "/curriculum/sub-skills/fractions.add_unlike_denominators/strategies",
        params={"misconception_tag": "converts_only_one_fraction"},
    )
    assert resp.status_code == 200
    strategies = resp.json()
    assert len(strategies) == 1
    assert strategies[0]["misconception_tag"] == "converts_only_one_fraction"


def test_personalize_strategy_wraps_content_with_student_name(client):
    strategies = client.get(
        "/curriculum/sub-skills/fractions.add_like_denominators/strategies"
    ).json()
    strategy_id = strategies[0]["id"]

    resp = client.post(
        "/curriculum/sub-skills/fractions.add_like_denominators/personalize",
        json={"strategy_id": strategy_id, "student_display_name": "Asha", "grade": 4},
    )
    assert resp.status_code == 200
    content = resp.json()["content"]
    assert "Asha" in content
    assert "add how many pieces you have" in content  # original explanation preserved


def test_personalize_unknown_strategy_404(client):
    resp = client.post(
        "/curriculum/sub-skills/fractions.add_like_denominators/personalize",
        json={"strategy_id": 999999, "student_display_name": "Asha", "grade": 4},
    )
    assert resp.status_code == 404


# --- demo diagnostic questions ----------------------------------------------


def test_demo_questions_do_not_leak_answers(client):
    resp = client.get("/demo/sub-skills/fractions.add_like_denominators/questions")
    assert resp.status_code == 200
    questions = resp.json()
    assert len(questions) == 2
    for q in questions:
        assert "correct_choice_id" not in q
        for choice in q["choices"]:
            assert set(choice.keys()) == {"id", "label"}


def test_demo_questions_unknown_sub_skill_404(client):
    resp = client.get("/demo/sub-skills/nope/questions")
    assert resp.status_code == 404


def test_demo_grade_responses_identifies_misconception(client):
    resp = client.post(
        "/demo/sub-skills/fractions.add_like_denominators/responses",
        json={
            "responses": [
                {"question_id": "ald.q1", "selected_choice_id": "3_8", "response_time_ms": 5200},
                {"question_id": "ald.q2", "selected_choice_id": "5_12", "response_time_ms": 4800},
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["graded"] == [
        {"question_id": "ald.q1", "correct": False},
        {"question_id": "ald.q2", "correct": False},
    ]
    assert body["misconception_tag"] == "adds_denominators"
    assert body["misconception_confidence"] == "confident"


def test_demo_grade_responses_all_correct(client):
    resp = client.post(
        "/demo/sub-skills/fractions.add_like_denominators/responses",
        json={
            "responses": [
                {"question_id": "ald.q1", "selected_choice_id": "3_4", "response_time_ms": 4000},
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["graded"] == [{"question_id": "ald.q1", "correct": True}]
    assert body["misconception_tag"] is None
    assert body["misconception_confidence"] == "none"


def test_demo_grade_responses_rejects_question_from_other_sub_skill(client):
    resp = client.post(
        "/demo/sub-skills/fractions.add_like_denominators/responses",
        json={"responses": [{"question_id": "ip.q1", "selected_choice_id": "3_4", "response_time_ms": 4000}]},
    )
    assert resp.status_code == 422


# --- escalation / parent-report listing --------------------------------------


def test_list_escalations_for_school(client):
    client.post("/schools", json={"id": "school-a", "name": "Green Valley School"})
    client.post(
        "/schools/school-a/students",
        json={"id": "student-1", "class_section": "4A", "display_name": "Asha"},
    )
    client.post(
        "/schools/school-a/escalations",
        json={
            "student_id": "student-1",
            "sub_skill_id": "fractions.add_like_denominators",
            "misconception_description": "misc",
            "remediation_strategies_tried": ["Strategy"],
            "attempt_count": 2,
            "last_mastery_score": 0.4,
            "floor_mastery": 0.75,
        },
    )

    resp = client.get("/schools/school-a/escalations")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp_resolved = client.get("/schools/school-a/escalations", params={"resolved": True})
    assert resp_resolved.json() == []


def test_get_escalation_by_id(client):
    client.post("/schools", json={"id": "school-a", "name": "Green Valley School"})
    client.post(
        "/schools/school-a/students",
        json={"id": "student-1", "class_section": "4A", "display_name": "Asha"},
    )
    created = client.post(
        "/schools/school-a/escalations",
        json={
            "student_id": "student-1",
            "sub_skill_id": "fractions.add_like_denominators",
            "misconception_description": "misc",
            "remediation_strategies_tried": ["Strategy"],
            "attempt_count": 2,
            "last_mastery_score": 0.4,
            "floor_mastery": 0.75,
        },
    ).json()

    resp = client.get(f"/schools/school-a/escalations/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["student_id"] == "student-1"


def test_get_escalation_unknown_id_404(client):
    client.post("/schools", json={"id": "school-a", "name": "Green Valley School"})
    resp = client.get("/schools/school-a/escalations/999999")
    assert resp.status_code == 404


def test_list_parent_reports_for_student(client):
    client.post("/schools", json={"id": "school-a", "name": "Green Valley School"})
    client.post(
        "/schools/school-a/students",
        json={"id": "student-1", "class_section": "4A", "display_name": "Asha"},
    )
    client.post(
        "/schools/school-a/parent-reports",
        json={
            "student_id": "student-1",
            "sub_skill_id": "fractions.add_like_denominators",
            "sub_skill_name_plain": "adding fractions",
            "at_home_actions": ["Practice with a pizza cut into slices."],
        },
    )

    resp = client.get("/schools/school-a/students/student-1/parent-reports")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert "Asha" in resp.json()[0]["plain_summary"]

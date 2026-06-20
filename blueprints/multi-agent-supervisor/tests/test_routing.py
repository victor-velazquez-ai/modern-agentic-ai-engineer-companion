"""Routing: a sub-task reaches the correct specialist.

Covers the PLAN's `test_routing.py` requirement — sub-task → correct specialist —
across both the deterministic keyword router and the model-driven router (which must
fall back safely in MOCK).
"""

from __future__ import annotations

import pytest

from multi_agent_supervisor import (
    KeywordRouter,
    MockModel,
    ModelRouter,
    NoWorkerForTask,
    SubTask,
    Worker,
    default_team,
)


@pytest.fixture
def team() -> list[Worker]:
    return default_team(MockModel())


def test_research_subtask_routes_to_researcher(team: list[Worker]) -> None:
    router = KeywordRouter(team)
    worker = router.route(SubTask(id="r1", description="Research vector databases", capability="research"))
    assert worker.name == "researcher"


def test_write_subtask_routes_to_writer(team: list[Worker]) -> None:
    router = KeywordRouter(team)
    worker = router.route(SubTask(id="w1", description="Write a summary", capability="write"))
    assert worker.name == "writer"


def test_capability_is_inferred_from_text_when_blank(team: list[Worker]) -> None:
    # No explicit capability tag — the router must infer it from the description.
    router = KeywordRouter(team)
    assert router.route(SubTask(id="x", description="Please investigate the sources")).name == "researcher"
    assert router.route(SubTask(id="y", description="Now draft the report")).name == "writer"


def test_unroutable_subtask_raises(team: list[Worker]) -> None:
    router = KeywordRouter(team)
    with pytest.raises(NoWorkerForTask):
        router.route(SubTask(id="z", description="Render a 3D animation", capability="animation"))


def test_route_all_preserves_order(team: list[Worker]) -> None:
    router = KeywordRouter(team)
    subtasks = [
        SubTask(id="a", description="Research X", capability="research"),
        SubTask(id="b", description="Write Y", capability="write"),
    ]
    routed = router.route_all(subtasks)
    assert [w.name for _, w in routed] == ["researcher", "writer"]


def test_routing_is_deterministic(team: list[Worker]) -> None:
    router = KeywordRouter(team)
    st = SubTask(id="a", description="Research vector databases", capability="research")
    assert router.route(st).name == router.route(st).name == "researcher"


def test_model_router_falls_back_safely_in_mock(team: list[Worker]) -> None:
    # The mock model does not return a clean worker name, so ModelRouter must validate
    # and fall back to the keyword router rather than route to a non-existent worker.
    router = ModelRouter(team, MockModel())
    worker = router.route(SubTask(id="r1", description="Research vector databases", capability="research"))
    assert worker in team
    assert worker.name == "researcher"


def test_model_router_honors_valid_model_pick() -> None:
    class PickWriter(MockModel):
        def complete(self, prompt, *, system=None, role=None):  # type: ignore[override]
            resp = super().complete(prompt, system=system, role=role)
            return type(resp)(text="writer", model=resp.model)

    team = default_team(MockModel())
    router = ModelRouter(team, PickWriter())
    # Even though the description looks like research, a valid model pick wins.
    assert router.route(SubTask(id="r", description="Research things")).name == "writer"

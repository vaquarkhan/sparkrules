from fastapi.testclient import TestClient

from sre.api import AppDeps, create_app
from sre.runtime import EngineConfig


def test_health() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_simulation() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations",
        json={
            "drl": """
rule r1
when
$t : T ( $t.x == 1 )
then
result.ok = true;
end
""",
            "fact": {"t": {"x": 1}},
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert j["fired"] is True


def test_simulation_chain() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations/chain",
        json={
            "drl": """
rule a
stop_on_fire true
when $t : T ( true ) then
result.n = 1;
end
rule b
when $t : T ( true ) then
result.m = 2;
end
""",
            "fact": {"t": {}},
            "stop_on_decline": False,
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert j["any_fired"] is True
    assert j["stop_reason"] and j["stop_reason"].startswith("stop_on_fire:")
    assert len(j["steps"]) == 1


def test_simulation_chain_bad_drl_400() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations/chain",
        json={"drl": "not valid", "fact": {}},
    )
    assert r.status_code == 400


def test_simulation_chain_agenda_group_mode() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations/chain",
        json={
            "drl": """
rule a salience 10
agenda_group "auth"
when $t : T ( true ) then
result.step = "a";
end
rule b salience 0
agenda_group "auth"
when $t : T ( true ) then
result.step = "b";
end
""",
            "fact": {"t": {}},
            "agenda_group_modes": {"auth": "first_match"},
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert j["steps"][0]["fired"] is True
    assert j["steps"][1]["skipped"] is True


def test_simulation_chain_uses_engine_policy_default() -> None:
    app = create_app(
        AppDeps(engine_cfg=EngineConfig(stop_on_decline=True))
    )
    c = TestClient(app)
    r = c.post(
        "/simulations/chain",
        json={
            "drl": """
rule decline
when $t : T ( true ) then
result.decision = "decline";
end
rule later
when $t : T ( true ) then
result.x = 1;
end
""",
            "fact": {"t": {}},
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert j["stop_reason"] == "stop_on_decline"


def test_simulation_shadow() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations/shadow",
        json={
            "primary_drl": "rule a when $t : T ( true ) then result.decision = \"approve\"; end",
            "shadow_drl": "rule b when $t : T ( true ) then result.decision = \"decline\"; end",
            "fact": {"t": {}},
        },
        headers={"X-Roles": "run_operator", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["drifted"] is True
    assert j["drift_fields"] == ["decision"]


def test_simulation_coverage() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations/coverage",
        json={
            "drl": """
rule a
when $t : T ( $t.x == 1 ) then
result.ok = true;
end
rule b
when $t : T ( $t.y > 10 ) then
result.ok2 = true;
end
""",
            "facts": [{"t": {"x": 1, "y": 0}}, {"t": {"x": 0, "y": 11}}],
        },
        headers={"X-Roles": "run_operator", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["total_facts"] == 2
    assert j["total_rules"] == 2
    assert j["covered_rules"] == 2


def test_simulation_coverage_bad_drl_400() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations/coverage",
        json={"drl": "not drl", "facts": []},
        headers={"X-Roles": "run_operator", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 400

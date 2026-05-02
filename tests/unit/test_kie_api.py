import importlib
import json

import pytest
from fastapi.testclient import TestClient

from sparkrules.api import AppDeps, create_app
from sparkrules.api.kie import reset_kie_containers_for_tests


def test_kie_server_list_and_execute() -> None:
    reset_kie_containers_for_tests()
    app = create_app(AppDeps())
    c = TestClient(app)
    srv = c.get("/kie-server/services/rest/server")
    assert srv.status_code == 200
    assert srv.json()["type"] == "SUCCESS"
    deploy = c.put(
        "/kie-server/services/rest/server/containers/demo",
        json={
            "drl": """
rule r when $person : Person ( true ) then
result.ok = true;
result.decision = "approve";
end
"""
        },
    )
    assert deploy.status_code == 200
    lst = c.get("/kie-server/services/rest/server/containers")
    assert lst.status_code == 200
    assert "demo" in str(lst.json())

    exe = c.post(
        "/kie-server/services/rest/server/containers/instances/demo",
        json={
            "lookup": "defaultKieSession",
            "commands": [
                {"insert": {"object": {"com.demo.Person": {"score": 700}}}},
                {"fire-all-rules": {}},
            ],
        },
    )
    assert exe.status_code == 200
    payload = exe.json()
    raw = payload["result"]
    inner = json.loads(raw) if isinstance(raw, str) else raw
    assert inner["final-action"]["decision"] == "approve"
    assert any(s["rule"] == "r" and s["fired"] for s in inner["results"])


def test_kie_deploy_via_config_items() -> None:
    reset_kie_containers_for_tests()
    c = TestClient(create_app(AppDeps()))
    deploy = c.put(
        "/kie-server/services/rest/server/containers/cfg",
        json={
            "config": {
                "config-items": [
                    {
                        "name": "drl",
                        "value": 'rule rz when $person : Person ( true ) then result.x=1; end',
                    }
                ]
            }
        },
    )
    assert deploy.status_code == 200


def test_kie_deploy_errors_and_execute_validation() -> None:
    reset_kie_containers_for_tests()
    c = TestClient(create_app(AppDeps()))
    bad_json = c.put(
        "/kie-server/services/rest/server/containers/bad",
        content=b"not json",
        headers={"Content-Type": "application/json"},
    )
    assert bad_json.status_code == 400
    nodrl = c.put("/kie-server/services/rest/server/containers/b2", json={})
    assert nodrl.status_code == 400
    baddrl = c.put(
        "/kie-server/services/rest/server/containers/b3",
        json={"drl": "this is not drl {{{"},
    )
    assert baddrl.status_code == 422
    xe = c.post(
        "/kie-server/services/rest/server/containers/instances/missing",
        json={"commands": []},
    )
    assert xe.status_code == 404

    nondict_deploy = c.put(
        "/kie-server/services/rest/server/containers/nonobj",
        content=b"[ 1 ]",
        headers={"Content-Type": "application/json"},
    )
    assert nondict_deploy.status_code == 400
    py = importlib.import_module("sparkrules.api.kie")
    py._kie_containers["x"] = "rule q when $person : Person ( true ) then end"
    nobatch = c.post(
        "/kie-server/services/rest/server/containers/instances/x",
        json={"commands": "nope"},
    )
    assert nobatch.status_code == 400
    c.put(
        "/kie-server/services/rest/server/containers/execjs",
        json={"drl": "rule z when $t : T ( true ) then end"},
    )
    bad_exec_json = c.post(
        "/kie-server/services/rest/server/containers/instances/execjs",
        content=b"not-json-at-all{{{",
        headers={"Content-Type": "application/json"},
    )
    assert bad_exec_json.status_code == 400
    top_list = c.post(
        "/kie-server/services/rest/server/containers/instances/execjs",
        json=[1, 2, 3],
    )
    assert top_list.status_code == 400


def test_kie_deploy_via_config_items_camelcase() -> None:
    reset_kie_containers_for_tests()
    c = TestClient(create_app(AppDeps()))
    deploy = c.put(
        "/kie-server/services/rest/server/containers/cfg2",
        json={
            "config": {
                "configItems": [
                    {
                        "name": "sparkrules-drl",
                        "value": "rule rz2 when $t : T ( true ) then end",
                    },
                ]
            },
        },
    )
    assert deploy.status_code == 200


def test_kie_execute_handles_non_dict_insert_fragments() -> None:
    reset_kie_containers_for_tests()
    c = TestClient(create_app(AppDeps()))
    c.put(
        "/kie-server/services/rest/server/containers/d1",
        json={"drl": 'rule r when $person : Person ( true ) then result.decision="ok"; end'},
    )
    exe = c.post(
        "/kie-server/services/rest/server/containers/instances/d1",
        json={
            "commands": [
                5,
                {"insert": {"object": {"com.X.Y": ["not", "dict"]}}},
                {"insert": {"object": {"com.X.Person": {"age": 1}}}},
                {"insert": {"object": {"com.Y.Person": {"name": "a"}}}},
                {"insert": {"object": "plain"}},
                {"insert": True},
                {"fire-all-rules": {}},
            ],
        },
    )
    assert exe.status_code == 200


def test_kie_server_state_describe_miss_delete_globals_and_dual_rules() -> None:
    reset_kie_containers_for_tests()
    c = TestClient(create_app(AppDeps()))
    assert c.get("/kie-server/services/rest/server/state").json()["type"] == "SUCCESS"
    assert c.get("/kie-server/services/rest/server/containers/missing-desc").status_code == 404

    c.put(
        "/kie-server/services/rest/server/containers/lc",
        json={
            "drl": '''rule hi when $t : T ( true ) then result.x="h"; end
rule lo when $a : A ( true ) then result.y="l"; end'''
        },
    )
    exe = c.post(
        "/kie-server/services/rest/server/containers/instances/lc",
        json={
            "commands": [
                {"insert": {"object": {"com.demo.T": {"n": 1}}}},
                {"insert": {"object": {"com.demo.A": {"m": 2}}}},
                {"set-global": {"identifier": "G", "value": {"z": True}}},
                {"get-global": {"identifier": "G"}},
                {"fireUntilHalt": {}},
            ],
        },
    )
    assert exe.status_code == 200
    inner = json.loads(exe.json()["result"])
    assert isinstance(inner["_kie_globals_echo"], dict)
    assert any(e.get("kind") == "get-global" for e in inner["batch-side-effects"])

    gone = c.delete("/kie-server/services/rest/server/containers/lc").json()
    assert gone["type"] == "SUCCESS"


def test_kie_fire_all_max_limits_firings() -> None:
    reset_kie_containers_for_tests()
    c = TestClient(create_app(AppDeps()))
    c.put(
        "/kie-server/services/rest/server/containers/mx",
        json={
            "drl": """
rule hi salience 10 when $t : T ( true ) then result.x = 1; end
rule lo salience 0 when $t : T ( true ) then result.y = 2; end
"""
        },
    )
    exe = c.post(
        "/kie-server/services/rest/server/containers/instances/mx",
        json={
            "commands": [
                {"insert": {"object": {"com.X.T": {}}}},
                {"fire-all-rules": {"max": 1}},
            ],
        },
    )
    assert exe.status_code == 200
    inner = json.loads(exe.json()["result"])
    assert inner["fire-max-requested"] == 1
    assert inner["stopped"] == "fire_max"
    assert sum(1 for s in inner["results"] if s["fired"]) == 1


def test_kie_describe_deployed_container_and_execute_without_fire() -> None:
    reset_kie_containers_for_tests()
    c = TestClient(create_app(AppDeps()))
    c.put(
        "/kie-server/services/rest/server/containers/desc-me",
        json={"drl": "rule q when $t : T ( true ) then end"},
    )
    info = c.get("/kie-server/services/rest/server/containers/desc-me")
    assert info.status_code == 200
    body = info.json()
    assert body["type"] == "SUCCESS"
    assert body["result"]["drl-char-length"] > 0

    no_fire = c.post(
        "/kie-server/services/rest/server/containers/instances/desc-me",
        json={"commands": [{"insert": {"object": {"com.X.T": {}}}}]},
    )
    assert no_fire.status_code == 200
    inner = json.loads(no_fire.json()["result"])
    assert inner["skipped-fire"] is True

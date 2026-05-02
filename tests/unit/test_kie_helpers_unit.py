from sparkrules.api.kie import (
    _apply_batch_commands,
    _batch_commands_to_fact,
    _fire_steps_from_commands,
    _object_map_to_fact_fragment,
    reset_kie_containers_for_tests,
)


def test_object_map_corner_cases_and_merge_paths() -> None:
    assert _object_map_to_fact_fragment({}) == {}
    assert _object_map_to_fact_fragment({"a": 1, "b": 2}) == {}
    assert _object_map_to_fact_fragment({"com.X.V": {"n": 1}}) == {"v": {"n": 1}}
    assert _object_map_to_fact_fragment({None: {"x": 1}}) == {}

    cmds = [
        {"insert": {"object": {"com.P.Person": {"a": 1}}}},
        {"insert": {"object": {"com.Q.Person": {"b": 2}}}},
    ]
    merged = _batch_commands_to_fact(cmds)
    assert merged == {"person": {"a": 1, "b": 2}}


def test_fire_steps_synonyms_and_max_iterations() -> None:
    assert _fire_steps_from_commands([]) == (False, None)
    assert _fire_steps_from_commands([{"fireUntilHalt": True}])[0]
    assert _fire_steps_from_commands([{"fire-until-halt": {}}])[0]
    assert _fire_steps_from_commands([{"fire-all-rules": {}}])[0]
    assert _fire_steps_from_commands([{"fire-all-rules": {"max": 0}}])[1] is None
    assert _fire_steps_from_commands([{"fire-all-rules": {"max": 4}}])[1] == 4


def test_apply_batch_globals_get_set_agenda_notes() -> None:
    reset_kie_containers_for_tests()
    cmds = [
        {"set-global": {"name": "G1", "value": {"k": 1}}},
        {"get-global": {"name": "G1"}},
        {"get-global": False},
        {"agenda-group-set-focus": {"name": "risk"}},
        {"agendaGroupSetFocus": {"name": "other"}},
        {"set-global": "fromStringAlias"},
        {"fire-all-rules": {}},
    ]
    work, trace = _apply_batch_commands("__tmp__", cmds)
    assert work["kie_global.G1"] == {"k": 1}
    assert work["kie_global.fromStringAlias"] is None
    kinds = [(t["kind"], t["name"]) for t in trace if t["kind"].startswith(("get-global", "agenda"))]
    assert kinds[0][0] == "get-global" and kinds[0][1] == "G1"
    agenda = [x for x in trace if x["kind"].startswith("agenda")]
    assert agenda[0]["name"] == "risk"
    assert agenda[1]["name"] == "other"


def test_retract_out_identifier_alias() -> None:
    reset_kie_containers_for_tests()
    cmds = [
        {"insert": {"object": {"com.A.Person": {"x": 1}}}},
        {"retract": {"outIdentifier": "person"}},
    ]
    work, trace = _apply_batch_commands("__oid__", cmds)
    assert "person" not in work
    assert any(t.get("kind") == "retract" for t in trace)


def test_apply_batch_bpm_compat_keys_in_trace() -> None:
    reset_kie_containers_for_tests()
    cmds = [
        {"query": {"x": 1}},
        {"startProcess": {"id": "p1"}},
        {"complete-work-item": {"wi": 9}},
        {"completeTask": {"id": "t1"}},
        {"claimTask": {"id": "t2"}},
        {"release-task": {}},
        {"delegateTask": {"to": "u1"}},
        {"signal": "go"},
        {"abort": True},
    ]
    _, trace = _apply_batch_commands("__bpm__", cmds)
    kinds = [x["kind"] for x in trace]
    for want in (
        "query",
        "start-process",
        "complete-work-item",
        "complete-task",
        "claim-task",
        "release-task",
        "delegate-task",
        "signal",
        "abort",
    ):
        assert want in kinds


def test_apply_batch_modify_retract_delete_dispose() -> None:
    reset_kie_containers_for_tests()
    cmds = [
        {"insert": {"object": {"com.Z.Person": {"n": 1}}}},
        {"modify": {"object": {"com.Z.Person": {"n": 99}}}},
        {"retract": {"object": {"com.Z.Person": {}}}},
        {"insert": {"object": {"com.Z.Person": {"n": 2}}}},
        {"delete": {"handle": "person"}},
        {"dispose": {}},
    ]
    work, trace = _apply_batch_commands("__batch2__", cmds)
    assert "person" not in work
    kinds = [t["kind"] for t in trace]
    assert "modify" in kinds and "retract" in kinds and "dispose" in kinds

from fastapi.testclient import TestClient

from sre.api import AppDeps, create_app


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

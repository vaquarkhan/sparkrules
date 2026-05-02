from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx


class SreClientError(Exception):
    pass


@dataclass
class SreClient:
    base_url: str
    inproc: object | None = None
    _tries: int = 3
    _fails: int = field(default=0, init=False, repr=False)

    def _request(self, method: str, p: str, *, json_body: object | None = None) -> httpx.Response:
        e: Exception | None = None
        u = f"{self.base_url.rstrip('/')}{p}"
        for a in range(self._tries):
            if self._fails and a < self._fails:
                e = SreClientError("injected")
                time.sleep(0.0)
                continue
            with httpx.Client() as c:
                if method == "GET":
                    return c.get(u, timeout=10.0)
                if method == "POST":
                    return c.post(u, json=json_body, timeout=10.0)
                raise SreClientError(f"unsupported method: {method}")
        raise e or SreClientError("unreachable")

    def get(self, p: str) -> httpx.Response:
        return self._request("GET", p)

    def post(self, p: str, payload: dict[str, object]) -> httpx.Response:
        return self._request("POST", p, json_body=payload)

    def health(self) -> dict[str, str]:
        r = self.get("/health")
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]

    def validate_rule(self, drl: str) -> dict[str, object]:
        r = self.post("/rules/validate", {"drl": drl})
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]

    def simulate(self, drl: str, fact: dict[str, object]) -> dict[str, object]:
        r = self.post("/simulations", {"drl": drl, "fact": fact})
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]

    def simulate_chain(
        self,
        drl: str,
        fact: dict[str, object],
        *,
        stop_on_decline: bool | None = None,
        agenda_group_modes: dict[str, str] | None = None,
    ) -> dict[str, object]:
        body: dict[str, object] = {
            "drl": drl,
            "fact": fact,
            "agenda_group_modes": dict(agenda_group_modes or {}),
        }
        if stop_on_decline is not None:
            body["stop_on_decline"] = stop_on_decline
        r = self.post("/simulations/chain", body)
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]

    def simulate_shadow(
        self,
        primary_drl: str,
        shadow_drl: str,
        fact: dict[str, object],
        *,
        run_id: str = "shadow-local",
    ) -> dict[str, object]:
        r = self.post(
            "/simulations/shadow",
            {
                "primary_drl": primary_drl,
                "shadow_drl": shadow_drl,
                "fact": fact,
                "run_id": run_id,
            },
        )
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]

    def simulate_coverage(
        self,
        drl: str,
        facts: list[dict[str, object]],
    ) -> dict[str, object]:
        r = self.post("/simulations/coverage", {"drl": drl, "facts": facts})
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]

    def counterfactual(
        self,
        drl: str,
        baseline_fact: dict[str, object],
        candidate_fact: dict[str, object],
    ) -> dict[str, object]:
        r = self.post(
            "/simulations/counterfactual",
            {
                "drl": drl,
                "baseline_fact": baseline_fact,
                "candidate_fact": candidate_fact,
            },
        )
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]

    def dmn_evaluate(self, xml: str, env: dict[str, object] | None = None) -> dict[str, object]:
        r = self.post("/dmn/evaluate", {"xml": xml, "env": dict(env or {})})
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]

    def dmn_counterfactual(
        self,
        xml: str,
        base_env: dict[str, object] | None = None,
        env_patch: dict[str, object] | None = None,
    ) -> dict[str, object]:
        r = self.post(
            "/dmn/counterfactual",
            {
                "xml": xml,
                "base_env": dict(base_env or {}),
                "env_patch": dict(env_patch or {}),
            },
        )
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]

    def capture_time_travel(
        self,
        run_id: str,
        drl: str,
        fact: dict[str, object],
    ) -> dict[str, object]:
        r = self.post(
            "/debug/time-travel/capture",
            {"run_id": run_id, "drl": drl, "fact": fact},
        )
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]

    def replay_time_travel(
        self,
        snapshot_id: int,
        run_id: str,
        fact_override: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {"snapshot_id": snapshot_id, "run_id": run_id}
        if fact_override is not None:
            payload["fact_override"] = fact_override
        r = self.post("/debug/time-travel/replay", payload)
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]

    def enforce_deprecations(
        self,
        namespace: str,
        rule_handle: str | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {"namespace": namespace}
        if rule_handle:
            payload["rule_handle"] = rule_handle
        r = self.post("/governance/deprecations/enforce", payload)
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]

    @staticmethod
    def install_transient_failure(c: SreClient, n: int) -> None:
        c._fails = n  # type: ignore[attr-defined]


def install_transient_failure(c: SreClient, n: int) -> None:
    SreClient.install_transient_failure(c, n)

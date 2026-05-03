"""AI rule suggestions: generate, attach simulator evidence, approve.

Uses :class:`sparkrules.ai.service.AiService` with :class:`sparkrules.ai.service.StubAiProvider`
(offline). Set ``SPARKRULES_AI_PROVIDER=openai`` and ``SPARKRULES_OPENAI_API_KEY`` to use the
HTTP provider inside your own integration tests.

  python examples/python/ai_rule_suggestion_workflow_demo.py
"""

from __future__ import annotations

from sparkrules.ai.service import AiService, StubAiProvider


def main() -> None:
    svc = AiService(provider=StubAiProvider())
    batch = svc.create_rule_suggestions(
        namespace="demo",
        payload={"rule_handle": "base", "facts": [{"id": 1}]},
        principal="analyst",
    )
    sid = batch[0].id
    print("created suggestion:", sid, "status=", batch[0].status)
    svc.record_simulation_evidence(
        sid,
        fired=True,
        action={"tier": "gold"},
        bound={"t": {"x": 1}},
    )
    approved = svc.approve(sid)
    print("approved:", approved.status, approved.drl[:60], "...")


if __name__ == "__main__":
    main()

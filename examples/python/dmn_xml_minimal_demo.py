"""Minimal DMN 1.3 XML: parse and evaluate a boxed decision table.

Uses the Camunda-flavored subset in ``sparkrules.dmn.minimal_xml``.

  python examples/python/dmn_xml_minimal_demo.py
"""

from __future__ import annotations

import json

from sparkrules.dmn import evaluate_dmn_decision_table_xml

_MINI_DMN = """<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn" id="def1">
  <decision id="d1" name="TierByScore">
    <decisionTable id="tbl" hitPolicy="FIRST">
      <input id="i1">
        <inputExpression typeRef="number">
          <text>$.score</text>
        </inputExpression>
      </input>
      <output id="o1" name="tier" />
      <rule id="r1">
        <inputEntry><text>700</text></inputEntry>
        <outputEntry><text>"gold"</text></outputEntry>
      </rule>
      <rule id="r2">
        <inputEntry><text>-</text></inputEntry>
        <outputEntry><text>"standard"</text></outputEntry>
      </rule>
    </decisionTable>
  </decision>
</definitions>
"""


def main() -> None:
    # DMN cells are compared with ``==`` to the fact field as parsed (often strings); use the same type.
    for score in ("700", "650"):
        out = evaluate_dmn_decision_table_xml(_MINI_DMN, {"score": score})
        print(f"score={score!r} -> {json.dumps(out)}")


if __name__ == "__main__":
    main()

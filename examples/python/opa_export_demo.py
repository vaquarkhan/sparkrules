"""Export DRL rules to OPA Rego policy format.

Demonstrates converting SparkRules DRL to Open Policy Agent (OPA) Rego
for security team verification with existing OPA toolchain.

  python examples/python/opa_export_demo.py
"""

from __future__ import annotations

from sparkrules.export.opa import export_to_rego

DRL = """
rule "block-high-risk"
  salience 100
  reason_codes ["SEC001"]
  when
    $req : Request( $req.risk_score > 0.9 )
  then
    result.action = "BLOCK";
    result.reason = "High risk score";
end

rule "require-mfa"
  salience 50
  when
    $req : Request( $req.login_country != "US" )
  then
    result.action = "MFA_REQUIRED";
end

rule "allow-trusted"
  salience 10
  when
    $req : Request( $req.trusted_device == true )
  then
    result.action = "ALLOW";
end
"""


def main() -> None:
    rego = export_to_rego(DRL, package_name="sparkrules.security_policy")
    print(rego)
    print("---")
    print("Save this as policy.rego and load it into OPA:")
    print("  opa eval -d policy.rego 'data.sparkrules.security_policy.block_high_risk'")


if __name__ == "__main__":
    main()

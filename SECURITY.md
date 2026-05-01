# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in SparkRules, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, please email **vaborobotics@gmail.com** with:

- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

You should receive an acknowledgment within 48 hours. We will work with you to understand the issue and coordinate a fix before any public disclosure.

## Scope

This policy covers the SparkRules Python package (`sparkrules`) and its API surface. It does not cover third-party dependencies, though we monitor them via automated security scanning (pip-audit) in CI.

## Security Practices

- Dependencies are monitored via Dependabot and pip-audit
- The API supports optional API key authentication (`SPARKRULES_API_KEY`)
- RBAC is enforced via role-based header checks (see [KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md) for architecture scope)
- No secrets are stored in the repository

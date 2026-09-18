# ADR-002: No Direct Model-to-OS Tool Access

**Status:** Accepted baseline

## Decision

Models and agents may request capabilities but may not directly execute arbitrary OS operations. Requests pass through the permission broker and then a sandboxed worker.

## Rationale

Engineering automation, code execution and security tooling can have significant side effects. Separating proposal from authority enables validation, approval, auditing and rollback.

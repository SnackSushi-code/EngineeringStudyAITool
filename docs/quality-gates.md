# Quality Gates

A change is not complete when it merely compiles.

## Required checks

1. Formatting
2. Linting
3. Type checking
4. Unit tests
5. Contract tests
6. Integration tests
7. End-to-end tests where applicable
8. Security/static analysis
9. Dependency and license review
10. Secret scanning
11. Artifact validation
12. Failure-path tests
13. Regression tests

## Reliability scenarios

At minimum, test model timeout, malformed output, tool timeout, worker crash, permission denial, network failure, duplicate requests, cancellation, partial completion, corrupted artifacts and stale/conflicting knowledge.

## Release requirements

- versioned artifacts
- SBOM
- changelog
- migration notes
- rollback path
- reproducible build instructions
- health/smoke test

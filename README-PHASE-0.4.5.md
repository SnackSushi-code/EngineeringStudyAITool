# Ann-E Phase 0.4.5 — Runtime Hardening

This package is intended to be applied to the stable Phase 0.4.4 integration baseline (`640edab`).

## Scope

This milestone hardens the adapter execution boundary against ordinary adapter failures and malformed outputs.

It does not introduce arbitrary shell execution, network execution, credentials, or privileged engineering tools.

## Apply

1. Create/switch to a new local branch from the merged integration baseline:

```powershell
git switch phase-0.4.3/runtime-integration
git pull --ff-only origin phase-0.4.3/runtime-integration
git switch -c phase-0.4.5/runtime-hardening
```

2. Copy the package contents into the repository root, preserving paths.

3. Run:

```powershell
python -m unittest discover -s tests/runtime -p "test_*.py" -v
python -m unittest discover -s tests/architecture -p "test_*.py" -v
python -m unittest discover -s tests/contract -p "test_*.py" -v
python tests/contract/validate_schemas.py
git diff --check
```

4. Review the staged diff before committing.

## Important semantic boundary

The current runtime uses cooperative cancellation. A third-party in-process worker that ignores cancellation cannot safely be forcibly terminated by this phase. Process-level isolation is a later hardening stage.

## Expected version

Runtime package version: `0.4.5`.

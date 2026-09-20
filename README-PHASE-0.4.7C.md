# Ann-E Phase 0.4.7-C — Supervisor/Worker Integration

This package connects the Phase 0.4.7-A `ExecutionSupervisor` to the Phase 0.4.7-B `WorkerProcess` boundary.

## Added

- `anne_runtime.supervised_execution.SupervisedExecution`
- deterministic lifecycle integration;
- supervisor-owned timeout recovery;
- cancellation recovery with forced termination fallback;
- worker correlation validation through the existing supervisor;
- terminal cleanup invariant;
- correlated runtime telemetry;
- focused integration tests;
- ADR-0016 and architecture documentation.

## Validation target

Run the existing complete suites plus:

```powershell
python -m unittest discover -s tests\runtime -p "test_*.py" -v
python -m unittest discover -s tests\architecture -p "test_*.py" -v
python -m unittest discover -s tests\contract -p "test_*.py" -v
python -m compileall services\runtime\src tests\runtime tests\architecture

git diff --check
```

## Important boundary

This phase does **not** claim platform security sandboxing. Process isolation and direct worker termination are implemented at the Python process boundary; actual OS-level enforcement is Phase 0.4.8 work.

# Phase 0.4.6 Isolation State Model

```text
NEW
 |
 v
STARTING
 |  |  \--> STARTUP_FAILED
 v
READY
 |
 v
RUNNING
 |   |   |    |   |   |    \--> CRASHED
 |   |   |
 |   |   +------> TIMING_OUT
 |   |
 |   +----------> CANCELLING
 |
 v
COMPLETED

CANCELLING --> TERMINATING
TIMING_OUT  --> TERMINATING
CRASHED     --> CLEANUP
STARTUP_FAILED --> CLEANUP
COMPLETED   --> CLEANUP
TERMINATING --> CLEANUP
CLEANUP --> TERMINAL
```

Terminal execution outcomes must map to the existing runtime result model without allowing an isolated worker to reactivate a completed task.

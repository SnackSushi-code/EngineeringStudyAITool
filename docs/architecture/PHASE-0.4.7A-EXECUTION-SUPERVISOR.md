# Phase 0.4.7-A — Execution Supervisor Foundation

## 1. Boundary
```text
Authorized ToolCall
       |
       v
ExecutionSupervisor
       |
       +--> validate isolation policy
       +--> validate worker descriptor
       +--> allocate execution identity
       +--> lifecycle state
       +--> protocol envelope
       +--> bounded result contract
       |
       v
Future worker-process boundary
```

This increment stops before actual process creation.

## 2. Lifecycle
```text
NEW
 |
 v
AUTHORIZED
 |
 v
STARTING
 |
 +--> STARTUP_FAILED --> CLEANUP --> TERMINAL
 |
 v
READY
 |
 v
RUNNING
 |
 +--> CANCELLING --> TERMINATING --> CLEANUP --> TERMINAL
 +--> TIMING_OUT --> TERMINATING --> CLEANUP --> TERMINAL
 +--> CRASHED ---------------------> CLEANUP --> TERMINAL
 +--> COMPLETED --------------------> CLEANUP --> TERMINAL
```

No terminal execution can transition back to execution.

## 3. Authorization boundary
The supervisor accepts an explicit authorization snapshot. A registered adapter, worker descriptor, or capability declaration is never treated as authorization.

## 4. Isolation policy
The policy describes timeout, memory, CPU, process-count, workspace, filesystem, network, environment, credentials, and output/message controls. These values are not security enforcement until a platform adapter applies and tests them.

## 5. IPC foundation
Every worker message carries protocol version, request ID, task ID, worker ID, message type, sequence number, and payload. Messages are bounded and correlation-checked.

## 6. Phase boundary
0.4.7-A establishes executable contracts and state management. 0.4.7-B adds concrete worker-process startup and readiness.

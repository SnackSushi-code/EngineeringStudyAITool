# Ann-E Phase 0.4.7-B — Worker Process & IPC

This package adds the first actual worker process and IPC boundary.

### Validation target

- Real worker startup/READY handshake
- JSON IPC
- Correlation and sequence validation
- Bounded IPC waits
- Timeout detection
- Graceful shutdown
- Forced process termination
- Crash/IPC failure containment

### Important boundary

This package does **not** implement the final OS sandbox. Platform-specific
filesystem, network, credential, CPU, memory, process-count, and descendant
controls remain separate implementation work.

Apply this package on top of the existing
`phase-0.4.7/runtime-isolation-implementation` branch.

# ADR-0015 — Worker Process and IPC Boundary

## Status

Accepted — Phase 0.4.7-B.

## Decision

Use a dedicated Python worker process with the `spawn` multiprocessing context
and a bounded JSON message protocol over a multiprocessing connection.

The supervisor owns:

- worker startup;
- startup handshake;
- IPC correlation;
- response deadlines;
- process termination;
- cleanup state.

The worker does not become trusted merely because it was selected by an adapter.

## Rationale

A real process boundary is required before platform-specific sandbox controls
can be attached. The `spawn` context also avoids inheriting arbitrary parent
process state by default.

JSON payloads provide an explicit serialization boundary rather than passing
Python objects directly through IPC.

## Security considerations

Process separation is not equivalent to sandboxing. Filesystem, network,
credential, CPU, memory, process-count, and descendant controls remain
platform enforcement responsibilities.

No arbitrary shell or network capability is exposed by this ADR.

## Consequences

Positive:

- worker crashes are separated from the supervisor process;
- IPC has explicit framing and size limits;
- timeout handling can progress to actual process termination;
- protocol correlation can be validated independently.

Remaining work:

- platform-specific sandbox enforcement;
- descendant control;
- resource enforcement;
- credential isolation;
- network and filesystem policy enforcement;
- integration with the execution supervisor's full lifecycle.

# ADR-0004: Engineering Integration Strategy

- Status: Accepted for Phase 0.1
- Date: 2026-09-18

## Decision

Engineering software will be integrated through **versioned adapters**, not by assuming that an AI model can directly manipulate application internals.

### MATLAB

Primary path:
- Python MATLAB Engine API
- explicit session lifecycle
- timeouts
- captured stdout/stderr
- structured result conversion
- artifact/provenance recording

MathWorks documents the Python Engine as a supported way to call MATLAB functions and scripts from Python. The engine can start a MATLAB process, connect to shared sessions, and execute asynchronously. It requires an installed MATLAB environment for Engine use. citeturn1search0turn1search10

Important:
- MATLAB Engine Python compatibility must be checked against the installed MATLAB release.
- Do not assume Python 3.14 compatibility merely because 3.14 is the current Python release.

### LabVIEW

Primary path:
- official LabVIEW Python integration where applicable
- project/file automation only after validating the specific LabVIEW version and installed toolchain

NI documents native Python interoperability through LabVIEW Python functions/Python Node and emphasizes version compatibility. citeturn1search6

### KiCad

Primary path:
- generate/edit native project artifacts using documented formats/APIs where stable
- invoke KiCad's own validation/automation facilities where available
- parse ERC/DRC/job outputs
- record exact KiCad version and validation results

KiCad 9 documentation describes schematic capture, PCB layout, simulation, 3D rendering, output generation, ERC and DRC automation. citeturn1search9

## Artifact truth model

Every engineering artifact must carry one of these states:

- GENERATED — produced by Ann-E, not independently validated.
- PARSED — successfully read back by the target tool/parser.
- VALIDATED — target-tool checks passed.
- SIMULATED — a simulation completed with recorded settings/results.
- EXPERIMENTALLY VERIFIED — validated against physical measurements supplied by the user.

Ann-E must never describe GENERATED as VALIDATED.

## Adapter contract

Each integration should expose:

```text
discover()
capabilities()
validate_environment()
prepare(input)
execute(input)
validate(output)
collect_artifacts()
collect_logs()
shutdown()
```

All operations must be:
- cancellable where possible
- timeout-bounded
- auditable
- version-recorded
- deterministic where practical
- safe to retry or explicitly marked non-idempotent

## Python baseline

Python 3.14 is the current stable major line as of this architecture decision, with 3.14.7 released August 5, 2026. However, integration environments may pin an older supported Python version when an external engineering product requires it. citeturn0search2turn0search11

The application must therefore support:
- a core supported Python version
- isolated per-integration environments where compatibility requires it
- explicit compatibility matrices

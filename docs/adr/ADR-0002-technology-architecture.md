# ADR-0002: Technology Architecture Baseline

- Status: Accepted for Phase 0.1
- Date: 2026-09-18
- Scope: Ann-E desktop, orchestration, engineering integrations, Colony, security, and evolution system

## Decision

Ann-E will use a **hybrid architecture**:

| Area | Decision |
|---|---|
| Desktop shell | **Tauri 2 + web UI** |
| UI | **React + TypeScript** |
| 3D widget / UI visualization | **Three.js**, with WebGL as the production baseline and WebGPU capability detection/future path |
| Colony simulation | **Godot 4**, isolated as a dedicated visualization/simulation application/service |
| Core orchestration | **Python** |
| Performance/security-critical native components | **Rust**, exposed through narrow process/API boundaries |
| Contracts | Versioned JSON Schema / typed API contracts |
| Local persistence | SQLite initially; abstraction retained for future database migration |
| Vector retrieval | Pluggable vector index; do not hard-code a vendor-specific backend into core domain logic |
| Engineering adapters | Python-first adapters with subprocess/service isolation where applications are external |
| CI/CD | GitHub Actions with deterministic checks and artifact validation |
| Self-extension | Git worktree/branch + isolated build/test environment + explicit approval gate |
| Security | Central policy/permission broker; no agent gets unrestricted OS authority |

## Why this shape

Ann-E needs deep local engineering integration, a polished desktop UI, 3D visualization, Python-friendly scientific tooling, and strong security boundaries. One language/runtime should not be forced to do every job.

Python is the primary orchestration/integration language because MATLAB exposes an official Python Engine API and LabVIEW provides Python integration. MATLAB Engine runs MATLAB as a separate process and supports synchronous/asynchronous calls; this maps naturally to an adapter boundary. citeturn1search0turn1search10

Rust is reserved for components where memory safety, low-level OS integration, or high-performance local services justify native code. The application should not become Rust-heavy merely for prestige.

Tauri is selected as the desktop-shell direction because Ann-E needs a web-quality UI without making the browser runtime the security boundary for privileged operations. The security model will still be designed explicitly rather than assuming the shell is secure by default.

Three.js is selected for the Ann-E widget and ordinary 3D UI because the visual needs are focused, interactive, and tightly coupled to the application UI. Its WebGL renderer is mature; WebGPU can be introduced behind capability detection rather than becoming a hard requirement. WebGPU remains incompletely supported across browsers, so it should not be the only rendering path. citeturn1search8turn0search12

Godot 4 is selected for Colony because Colony is not merely a decorative widget: it is a real-time multi-agent visualization/simulation. Godot 4 provides desktop Forward+ rendering using Vulkan, Direct3D 12, or Metal, while also providing a compatibility renderer. citeturn1search3

## Non-goals

- Do not embed the entire Colony engine inside the desktop renderer.
- Do not give the UI direct access to shells, filesystems, credentials, or arbitrary processes.
- Do not make CAI or Refact a hard dependency of Ann-E.
- Do not make a single LLM/provider a hard dependency.
- Do not make WebGPU mandatory.
- Do not promise that every engineering application can be automated before its official/local API is verified.

## Consequences

Positive:
- Clear security boundaries.
- Python integrates well with engineering software.
- Rust can handle sensitive/native infrastructure.
- UI and Colony can evolve independently.
- Provider/model/integration replacements remain possible.

Costs:
- Multiple runtimes increase packaging and testing complexity.
- IPC contracts become a first-class engineering concern.
- Colony requires a separate build/distribution path.
- More integration tests are required.

## Acceptance criteria

This ADR is considered implemented only after:
1. The repository contains explicit process/API boundaries.
2. The desktop UI cannot directly execute privileged operations.
3. The orchestrator can dispatch a typed tool request.
4. An adapter can return a typed artifact/result.
5. Colony can consume event data without receiving privileged credentials.
6. Security tests verify denied operations.

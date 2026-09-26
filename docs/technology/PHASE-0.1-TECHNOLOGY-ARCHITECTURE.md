# Phase 0.1 Technology Architecture Selection

## Executive decision

Ann-E will be built as a **hybrid desktop engineering platform** rather than a single-runtime application.

### Selected baseline

**Desktop**
- Tauri 2
- React
- TypeScript

**3D Ann-E widget**
- Three.js
- WebGL baseline
- WebGPU capability path

**Colony**
- Godot 4
- separate visualization/simulation process

**Core**
- Python
- typed contracts
- async job orchestration

**Native**
- Rust only where it provides concrete security/performance/OS value

**Storage**
- SQLite first
- abstraction for future database/vector backend replacement

**Engineering**
- adapter-per-tool
- Python integration where official APIs support it
- subprocess isolation for heavyweight desktop engineering applications

**Security**
- centralized permission broker
- sandboxing
- explicit approvals
- immutable audit trail
- secret isolation

**AI**
- model-provider abstraction
- structured tool calls
- no provider lock-in
- agents treated as untrusted planners until actions pass policy

**Self-extension**
- isolated worktree
- build/test/security scan
- approval
- checkpoint
- staged update
- post-update health check
- rollback

## Why not make everything one language?

Ann-E crosses domains with very different requirements. Python is exceptionally useful for engineering automation and scientific software, while Rust is useful for native security-sensitive components. Forcing every layer into one language would create unnecessary integration friction.

## Why not make Colony a Three.js-only simulation?

Three.js is excellent for application-integrated 3D UI. Colony has stronger simulation/game-engine requirements: agent movement, scenes, replay, simulation clocks, effects, fault injection, and future scaling. Godot provides a dedicated runtime with multiple rendering backends. The two should communicate through a narrow event/state protocol.

## Why not embed everything inside Electron?

Electron's process model and security controls are mature, but Ann-E has a particularly high privilege surface because it will eventually control engineering software, code execution, files, and self-updates. Electron is viable, but the architecture should minimize the privileged desktop surface and keep powerful operations outside the renderer regardless of shell choice. Electron's own security guidance emphasizes context isolation, sandboxing, restrictive CSP, secure content, IPC sender validation, and avoiding exposing Electron APIs to untrusted content. citeturn1search7turn1search13

## Research status

This document records architecture decisions based on current official documentation and current repository state checked on 2026-09-18.

Important current ecosystem finding:
- CAI public repository: archived/unmaintained.
- Original Refact repository: archived; successor development is elsewhere.

Those projects remain useful as research/reference inputs, but Ann-E's core architecture must not depend on their continued maintenance. citeturn0search0turn0search1

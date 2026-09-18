# Ann-E System Overview

## Purpose

Ann-E is a modular agent platform. The assistant core coordinates models and specialized agents, but never receives unrestricted operating-system privileges.

## Trust flow

```text
User / UI / Voice
      |
      v
Intent + Context
      |
      v
Planner / Orchestrator
      |
      v
Policy + Permission Broker
      |
      +----> DENY / REQUEST APPROVAL
      |
      v
Sandboxed Tool Worker
      |
      v
Artifact / Result Validator
      |
      v
Audit Event + Observability
      |
      v
User-visible Result
```

## Major subsystems

- **Desktop:** widget, application shell, settings, notifications.
- **Orchestrator:** intent routing, plans, task state, cancellation.
- **Memory:** structured user/project memory and retrieval.
- **Learning:** research-to-knowledge pipeline with provenance and approval.
- **Research:** web/document retrieval and source management.
- **Engineering:** domain agents and engineering tool adapters.
- **Artifacts:** typed files, manifests, validation state and provenance.
- **Tools:** capability registry and execution interfaces.
- **Security:** policy, sandboxing, audit, secrets isolation and emergency controls.
- **Colony:** visual simulation/orchestration of specialized Ann-E agents.
- **Voice:** STT/TTS/audio device abstraction.

## Core rule

Models produce plans and proposed tool calls. The policy layer decides whether a tool call may execute. Tool workers execute with narrowly scoped permissions.

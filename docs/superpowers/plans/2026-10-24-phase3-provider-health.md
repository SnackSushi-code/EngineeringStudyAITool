# Phase 3 Provider Health Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add deterministic per-provider failure tracking and a 30-second circuit breaker to `ModelRouter` without breaking existing provider routing or provenance enforcement.

**Architecture:** Extend the existing `ModelRouter` rather than introducing a new health subsystem. The router will maintain in-memory provider failure counts and circuit-open timestamps, skip providers whose circuit is open, increment retryable failures, reset a provider after successful generation, and preserve the existing non-retryable error and provenance behavior.

**Tech Stack:** Python, pytest, existing `ModelRouter`, `ProviderRegistry`, `ModelProviderError`, `DeterministicModelProvider`.

**Spec:** `docs/superpowers/plans/2026-10-23-phase3-step3-provider-provenance.md`

## Global Constraints

- Failure threshold: `3` retryable failures.
- Circuit cooldown: `30.0` seconds.
- Failure state is tracked independently for each provider.
- Only retryable provider failures contribute to circuit state.
- Non-retryable provider failures continue to raise immediately.
- Successful provider generation resets that provider's failure count to `0`.
- Open providers are skipped while their cooldown has not expired.
- Existing request/task/provider/model provenance validation remains unchanged.
- No new runtime dependency is required.
- Existing routing order remains deterministic.

## Review Focus

- Provider reaches exactly the failure threshold — circuit opens and provider is skipped.
- Provider failure is retryable versus non-retryable — only retryable failures affect health state.
- Fallback provider succeeds after primary opens — fallback response is returned.
- Successful provider recovers — failure count resets to zero.
- Cooldown expires — previously opened provider becomes eligible again.

---

### Task 1: Add provider health state to ModelRouter

**Files:**
- Modify: `services/runtime/src/anne_runtime/model_router.py`
- Test: `services/runtime/tests/test_phase3_provider_health.py`

**Interfaces:**
- `ModelRouter.__init__` retains its existing public signature.
- Add internal state:
  - `_provider_failure_threshold: int = 3`
  - `_provider_cooldown_seconds: float = 30.0`
  - `_provider_failure_counts: dict[str, int]`
  - `_provider_open_until: dict[str, float]`

- [ ] Step 1: Verify the existing RED health tests fail because these attributes do not exist.
- [ ] Step 2: Add the four internal state fields to `ModelRouter.__init__`.
- [ ] Step 3: Run the focused health tests.
- [ ] Step 4: Confirm the initialization/default-state assertions pass.

### Task 2: Implement provider circuit state transitions

**Files:**
- Modify: `services/runtime/src/anne_runtime/model_router.py`
- Test: `services/runtime/tests/test_phase3_provider_health.py`

**Interfaces:**
- Retryable failure increments `_provider_failure_counts[provider_id]`.
- When the count reaches `3`, set `_provider_open_until[provider_id]` to current monotonic time plus `30.0`.
- Successful generation resets `_provider_failure_counts[provider_id]` to `0`.
- A provider is eligible again when the current monotonic time is at or beyond its open-until timestamp.

- [ ] Step 1: Before invoking a provider, skip it when its circuit remains open.
- [ ] Step 2: On a retryable `ModelProviderError`, increment that provider's failure count.
- [ ] Step 3: Open the circuit when the failure count reaches the threshold.
- [ ] Step 4: On successful validated provider response, reset that provider's failure count to zero and clear stale open state.
- [ ] Step 5: Preserve the existing behavior for non-retryable errors.
- [ ] Step 6: Run `services/runtime/tests/test_phase3_provider_health.py`.
- [ ] Step 7: Confirm all provider-health tests pass.

### Task 3: Preserve complete runtime behavior

**Files:**
- Modify: `services/runtime/src/anne_runtime/model_router.py`
- Test: existing runtime test suite

- [ ] Step 1: Run the focused Phase 3 routing/provenance tests.
- [ ] Step 2: Run the complete runtime suite.
- [ ] Step 3: Run `git diff --check`.
- [ ] Step 4: Inspect `git status`.
- [ ] Step 5: Verify no unrelated source files changed.

Expected final runtime result: all existing tests pass, plus the new provider-health tests.

### Task 4: Commit the completed implementation

- [ ] Step 1: Review the final diff.
- [ ] Step 2: Stage only the intended Phase 3 implementation/test/plan files.
- [ ] Step 3: Commit with:

`feat: add provider health circuit breaker`

- [ ] Step 4: Verify the resulting HEAD and clean/expected working tree.

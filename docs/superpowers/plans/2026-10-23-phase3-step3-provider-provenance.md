# Phase 3 Step 3 - Provider Response Provenance Implementation Plan

> **For agentic workers:** Use the implementation workflow and TDD.

**Goal:** Ensure every successful provider response is correlated to the original request and verified against the provider/model selected by the router.

**Architecture:** Keep response validation inside `ModelRouter.generate()`. The router constructs the routed request, invokes eligible providers, validates request/task/provider/model provenance, returns only verified responses, and preserves retryable fallback behavior.

**Tech Stack:** Python 3.14, pytest, existing ANN-E runtime contracts.

**Spec:** Phase 3 Step 3 provider-response provenance contract established in the project conversation.

## Global Constraints

- Preserve provider-agnostic routing.
- Preserve retryable provider fallback from Phase 3 Step 2.
- Non-retryable provider failures remain terminal.
- Correlation mismatches use `RESPONSE_CORRELATION_ERROR`.
- Provider/model provenance mismatches use `RESPONSE_PROVENANCE_ERROR`.
- All retryable eligible-provider failures terminate with `ALL_PROVIDERS_FAILED`.

## Review Focus

- Wrong request_id must fail closed with `RESPONSE_CORRELATION_ERROR`.
- Wrong task_id must fail closed with `RESPONSE_CORRELATION_ERROR`.
- Wrong provider_id must fail closed with `RESPONSE_PROVENANCE_ERROR`.
- Wrong model must fail closed with `RESPONSE_PROVENANCE_ERROR`.
- Retryable provider failure must continue to a valid fallback.

### Task 1: Provenance tests

**Files:**
- Modify: `services/runtime/tests/test_phase3_step3_provenance.py`

- [ ] Add/retain tests covering request_id, task_id, provider_id, and model mismatches.
- [ ] Run the targeted tests and confirm RED for missing behavior.

### Task 2: Router provenance enforcement

**Files:**
- Modify: `services/runtime/src/anne_runtime/model_router.py`

- [ ] Validate provider response request_id against the original request.
- [ ] Validate task_id against the original request.
- [ ] Validate provider_id against the provider descriptor.
- [ ] Validate model against the routed model.
- [ ] Preserve retryable fallback behavior.
- [ ] Preserve terminal behavior for non-retryable failures.
- [ ] Return `ALL_PROVIDERS_FAILED` when all eligible providers fail retryably.

### Task 3: Verification

- [ ] Run targeted Phase 3 routing/provenance tests.
- [ ] Run the complete runtime suite.
- [ ] Run `git diff --check`.
- [ ] Verify no unrelated files are staged.

### Task 4: Commit

- [ ] Commit the Step 3 implementation with a focused commit message.

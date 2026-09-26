# Phase 1A — Intelligence Core

## Purpose

Phase 1A introduces Ann-E's provider-independent model layer.

The goal is to make model invocation a replaceable subsystem rather than
embedding a specific model vendor throughout the runtime.

## Components

### Model contracts

`anne_runtime.model_contracts` defines:

- model messages;
- generation configuration;
- model requests;
- model responses;
- provider descriptors;
- capabilities;
- usage metadata;
- provider errors.

These objects are immutable and validated at construction.

### Provider registry

`ProviderRegistry` contains only explicitly registered providers.

Registration is:

- explicit;
- deterministic;
- thread-safe;
- replaceable only when the caller explicitly requests replacement.

The registry does not download, discover, or execute arbitrary providers.

### Model router

`ModelRouter` converts a model request into a concrete provider/model route.

Routing is deterministic:

1. filter by explicitly requested model;
2. filter by required capabilities;
3. apply configured defaults;
4. use registry order when multiple providers remain.

The router intentionally does not invent a quality ranking between providers.

### Model service

`ModelService` provides the high-level invocation boundary.

It verifies:

- input size;
- provider routing;
- response request correlation;
- response task correlation;
- provider provenance;
- selected model provenance;
- output size;
- invocation timing.

## Security boundary

Phase 1A does not grant models operating-system privileges.

The model layer:

- does not execute shell commands;
- does not access the filesystem;
- does not directly perform network requests;
- does not access credentials;
- does not bypass the policy broker;
- does not automatically invoke tools.

Network-capable production providers must be integrated through an
authorized transport boundary in a later phase.

## Provider implementation

`DeterministicModelProvider` exists only as a dependency-free test/development
provider.

It performs no network operations and provides deterministic output.

A production provider adapter will be introduced only after the tool/network
authorization path is ready.

## Data handling

Model requests and responses carry request/task correlation IDs.

Provider responses retain:

- provider ID;
- provider version;
- selected model;
- finish reason;
- usage metadata;
- provider metadata.

Secrets are not part of the model contract.

## Failure behavior

Provider failures are represented as `ModelProviderError` with:

- stable error code;
- retryability;
- human-readable message.

Contract violations are not automatically retried.

## Phase 1A acceptance criteria

- Model contracts are immutable and validated.
- Providers must explicitly register.
- Duplicate registration fails unless replacement is explicit.
- Routing is deterministic.
- Capability requirements are enforced.
- Request/response correlation is verified.
- Provider/model provenance is verified.
- Input/output limits are enforced.
- Model invocation timing is captured.
- No production network or OS privilege is introduced.
- All Phase 0 runtime tests remain passing.

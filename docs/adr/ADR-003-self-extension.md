# ADR-003: User-Authorized Self-Extension

**Status:** Accepted baseline

## Decision

Ann-E will have an isolated development environment for preparing updates and new capabilities. Production activation requires explicit approval by default.

## Required lifecycle

Research -> proposal -> dependency/license review -> security review -> isolated implementation -> tests -> release candidate -> approval -> checkpoint -> staged install -> post-install validation -> activation.

## Recovery

A failed update enters safe mode and rolls back to the last known-good version when possible. User data and memory must be protected from application rollback.

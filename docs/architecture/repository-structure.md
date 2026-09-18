# Repository Structure

```text
apps/                 User-facing applications
services/             Runtime services
agents/               Specialized agent implementations
packages/             Shared contracts, UI and infrastructure libraries
integrations/         External software/repository adapters
infra/                Containers, sandbox, CI and deployment assets
docs/                 Architecture, ADRs, threat model and runbooks
tests/                Automated verification
```

## Dependency direction

```text
apps -> services -> packages
agents -> services/packages
integrations -> packages
infra -> services/apps
```

Shared contracts must not import application implementations. Integrations must not bypass the policy/tool interfaces.

# Engineering Artifact Contract

Every generated artifact has a lifecycle:

```text
PROPOSED -> GENERATED -> PARSED -> VALIDATED -> SIMULATED -> EXPERIMENTALLY_VERIFIED
```

States may be skipped only when the corresponding activity is genuinely unavailable, and the missing validation must be visible to the user.

Each artifact records:
- artifact ID
- project ID
- creator agent
- tool/integration
- tool version
- source inputs
- timestamp
- validation results
- warnings/errors
- provenance
- checksum when appropriate

Ann-E must never describe a generated artifact as experimentally verified unless real experimental evidence exists.

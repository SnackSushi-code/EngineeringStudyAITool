# Ann-E Architecture Boundary Matrix

| Boundary | Allowed | Forbidden | Enforcement |
|---|---|---|---|
| Presentation → Orchestration | typed task requests, sanitized state | direct OS/tool/secret access | API boundary |
| Orchestration → Policy | permission requests | implicit authorization | policy contract |
| Policy → Worker | authorized scoped operation | broadened scope | broker decision |
| Worker → External Tool | explicit adapter operation | unrestricted execution | sandbox/process policy |
| Orchestration → Memory | approved retrieval/write flows | raw secret storage | memory contract |
| Worker → Artifact Store | artifact creation/update | unverifiable validation claims | artifact contract |
| Orchestration → Colony | sanitized events/state | credentials, secrets, policy authority | Colony event contract |
| Model → Tool layer | structured proposals | direct execution | policy broker |
| Self-extension → Runtime | proposal/checkpoint/update | silent production mutation | approval + rollback |
| External Framework → Ann-E | adapter interface | becoming trust authority | adapter isolation |

## Permission classes
- READ
- WRITE
- EXECUTE
- NETWORK
- DESTRUCTIVE
- SECURITY_SENSITIVE
- SELF_UPDATE

## Default
Unknown or unavailable authorization state is **DENY** for privileged operations.

# Learning & Memory Architecture Baseline

Learning is a controlled ingestion pipeline, not raw chat-history mutation.

```text
Source -> Retrieval -> Claims -> Evidence -> Candidate Knowledge -> Validation -> Approval -> Memory
```

Knowledge records include provenance, timestamp, confidence, topic, version and revalidation policy.

Memory layers:
- session
- user preferences
- project
- engineering knowledge
- study knowledge
- research library
- system configuration

User controls must support inspection, editing, deletion and disabling automatic learning.

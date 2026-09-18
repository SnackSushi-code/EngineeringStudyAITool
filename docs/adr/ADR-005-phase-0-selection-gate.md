# ADR-005: Technology Selection Gate

**Status:** Proposed

Technology choices for the desktop shell, 3D widget, service runtime, database, sandbox and packaging will not be locked until their requirements are compared against:

- Windows desktop support
- GPU rendering requirements
- low idle resource use
- accessibility
- local/offline operation
- Python/Rust/JS ecosystem compatibility
- engineering software automation
- packaging/update support
- testability
- security isolation
- long-term maintenance

The goal is to avoid selecting a fashionable stack that later blocks KiCad/MATLAB/LabVIEW, Colony rendering, or safe self-extension.

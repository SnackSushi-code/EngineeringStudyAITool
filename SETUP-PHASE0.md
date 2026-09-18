# Phase 0 desktop setup

1. Extract `Ann-E-Phase0-Foundation.zip`.
2. Open PowerShell in the extracted `ann-e-phase0` directory.
3. Run `./SETUP-PHASE0.ps1`.
4. Authenticate with GitHub if prompted.
5. Run `git push -u origin main`.

If GitHub rejects the push, do not create a second repository. The target is:

`SnackSushi-code/EngineeringStudyAITool`

The current connected GitHub integration can read this repository but is returning HTTP 403 for write operations, so the initial push must currently be performed from your desktop Git credentials.

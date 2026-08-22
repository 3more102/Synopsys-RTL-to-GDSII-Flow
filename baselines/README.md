# Baselines

This directory reserves repository structure for ASIC comparison baselines.

Actual promoted engineer baselines are created under `baselines/local/<name>/` by `./baseline.sh` and are ignored by Git because provenance can contain local PDK, library, executable, hostname, and filesystem information.

Do not commit a local baseline by bypassing `.gitignore` unless its contents have been reviewed for publication and the evidence class is documented. See `docs/BASELINES.md` for promotion, verification, replacement, QoR-gate, and provenance-comparison workflows.

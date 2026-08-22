# Provenance and Release Manifest

The flow records reproducibility in separate identities rather than one opaque hash:

- **design** — RTL, SDC, project modes/corners/scenarios and design-intent environment;
- **methodology** — Tcl/Bash/Python flow implementation, Makefile and methodology policies;
- **technology** — technology/library configuration plus explicitly configured external PDK/library paths;
- **execution** — resolved EDA executable identity and explicit execution environment.

Build the current provenance record:

```bash
make provenance
```

Outputs:

```text
reports/provenance/run_provenance.json
reports/provenance/run_provenance.sha256
```

Compare with a known run:

```bash
PROVENANCE_BASELINE=/archive/run_provenance.json make compare-provenance
```

By default design, methodology and technology differences are blocking while execution differences are warnings. Use `STRICT_EXECUTION=1` when the exact executable identity must also match.

The release package contains `RELEASE_MANIFEST.json`. It inventories final-delivery files with SHA-256 and size, embeds engineering status evidence, references the provenance digest and carries QoR summary data when available. It does not convert missing foundry evidence into PASS: foundry signoff is PASS only when DRC and LVS statuses are both PASS, FAIL if either is FAIL, otherwise UNKNOWN.

External PDK/library files are identified by normalized path + stat metadata by default to avoid hashing very large vendor databases. Set `PROVENANCE_EXTERNAL_PATH_MODE=sha256` to hash external regular files when practical. Directories remain stat-identified and this limitation is explicit in the JSON.

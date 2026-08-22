# Verify a Final ASIC Delivery Package

A generated `final_delivery/` contains a standalone integrity verifier so the package can be checked on another machine without Synopsys tools, the original repository, or the original PDK.

From the package directory run:

```bash
python3 tools/verify_delivery_integrity.py --delivery . --strict-extra
```

The verifier checks both integrity layers:

1. `RELEASE_MANIFEST.json`
   - every listed artifact exists;
   - file size matches;
   - SHA256 matches;
   - artifact paths are safe package-relative paths;
   - duplicate/unsafe entries are rejected.

2. `checksums.txt`
   - every required artifact has a checksum entry;
   - `RELEASE_MANIFEST.json` itself is checksum-covered;
   - every checksum target exists;
   - every SHA256 is recomputed and compared.

`checksums.txt` intentionally does not checksum itself.

By default unexpected files are warnings. For an immutable reviewed package use:

```bash
python3 tools/verify_delivery_integrity.py --delivery . --strict-extra
```

To require that the release manifest also records qualified DRC **and** LVS PASS evidence:

```bash
python3 tools/verify_delivery_integrity.py --delivery . --strict-extra --require-qualified
```

`--require-qualified` is deliberately separate from basic integrity. A package can be byte-for-byte intact while foundry DRC/LVS remains `UNKNOWN`; integrity must not be confused with physical signoff.

Typical successful output:

```text
DELIVERY_INTEGRITY=PASS manifest_artifacts=<N> checksums=<N+1> foundry_signoff=<PASS|UNKNOWN>
```

Any modified, missing, duplicated, unsafe, or checksum-inconsistent artifact returns a nonzero exit code.

# Release process

This checklist keeps a stable release traceable to one tested commit and one reproducible artifact set. Run it from a clean `main` checkout.

## 1. Confirm version metadata

Update the project version in [`scripts/project_metadata.py`](../scripts/project_metadata.py), `package.json`, `package-lock.json`, the changelog, and the versioned release note. Then confirm the machine-readable result:

```bash
python scripts/cli.py version
```

## 2. Run the release gate

```bash
npm ci
python -m compileall -q scripts tests/python
python -m unittest discover -s tests/python -v
python scripts/validate_repository.py
npm run check
npm test

python -m pip install ruff==0.16.2
ruff check scripts tests/python
ruff format --check scripts tests/python
```

Wait for the same commit's GitHub Actions checks to pass. Automated evidence remains subject to the boundaries in [`VALIDATION.md`](./VALIDATION.md).

## 3. Build and inspect assets

```bash
npm run build:release
```

The builder reads tracked files only, rejects unsafe archive paths and symlinks, applies fixed metadata, and packages everything beneath `douyin-skills-vX.Y.Z/`. Local profiles, dependencies, caches, and prior output are excluded. It writes:

```text
dist/douyin-skills-vX.Y.Z.zip
dist/SHA256SUMS
```

Build the same commit twice and compare SHA-256 values when auditing reproducibility. Open the ZIP, confirm every member stays under the versioned directory, and run `python scripts/cli.py version` from a fresh extraction.

## 4. Tag and publish

1. Create an annotated `vX.Y.Z` tag on the tested `main` commit and push it.
2. Create a non-draft, non-prerelease GitHub Release from that tag.
3. Use the matching file under [`docs/releases/`](./releases/) as the release body.
4. Upload the named ZIP, `SHA256SUMS`, and the privacy-safe `demo.gif`.
5. Download the public assets again, verify the checksum, and confirm the Release and README links resolve.

Never attach account data, browser profiles, cookies, QR codes, phone numbers, or private content to a release.

# Publishing v26.1 to GitHub

The distribution ZIP contains the repository content, but it intentionally does not contain `.git`. Keep the existing `.git` directory in your local clone so GitHub Desktop and Git continue to recognize the repository.

## Recommended update

1. Extract `midterms-2026-forecast_v26.1.0_GITHUB_READY.zip`.
2. Open the extracted `midterms-2026-forecast/` folder.
3. Copy its **contents** into your existing local clone.
4. Allow macOS to merge folders and replace files.
5. Do not copy the ZIP itself into the repository.
6. Do not delete the existing hidden `.git` directory.

The package already excludes old report versions, v25 runtime files, environments, checkpoints, caches, and macOS metadata. The new `.gitignore` prevents those files from being committed again.

## Validate locally

From the repository root:

```bash
python3 scripts/validate_repository.py
```

Then validate Dash inside its own environment:

```bash
cd dash_app
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install --no-cache-dir -r requirements.txt
python3 check_setup.py
```

Expected result:

```text
STATUS: OK
```

## Commit and push

Using Terminal from the repository root:

```bash
git status
git add -A
git commit -m "Publish model v26 and Dash v26.1"
git push origin main
```

Using GitHub Desktop, review the changed and deleted files, use the same commit message, select **Commit to main**, and then **Push origin**.

The workflow in `.github/workflows/validate.yml` automatically checks the repository contracts and Dash setup on every push and pull request. A green check means both jobs passed.

## After the commit

Confirm on GitHub that:

- the README hero and animated tour render;
- the fourteen screenshots load;
- links to the v26 notebook, HTML, report, Dash, and documentation resolve;
- the Actions tab shows both validation jobs in green; and
- old consolidated reports and the v25 runtime no longer appear on the default branch.

The autonomous HTML must be downloaded and opened locally. GitHub displays it as a source file rather than executing the embedded application in the repository view.

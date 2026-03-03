# QA / Tooling

This folder intentionally keeps **developer tooling** (formatting/linting/test config)
separate from both the `server/` and `client/` runtime structures.

## Install (dev/test)

From the repository root:

```bash
python -m pip install -r qa/requirements-test.txt
```

## Run unit tests

```bash
pytest -c qa/pyproject.toml
```

## Lint / Format

```bash
# lint
bash qa/scripts/lint.sh

# format
bash qa/scripts/format.sh
```

> Note: configs live in `qa/pyproject.toml`, so scripts pass `--config qa/pyproject.toml`.

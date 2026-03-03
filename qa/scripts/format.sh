#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."  # repo root

black --config qa/pyproject.toml .
ruff check --config qa/pyproject.toml . --fix

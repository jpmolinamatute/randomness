#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"


log_info() { echo "INFO: $*"; }
log_error() { echo "ERROR: $*" >&2; }


run_pytest() {
    local pyproject_path="${ROOT_DIR}/pyproject.toml"
    log_info "running python tests..."
    uv run pytest --config-file "${pyproject_path}"
}

main() {
    local pyproject_path="${ROOT_DIR}/pyproject.toml"
    log_info "Running mypy..."
    uv run ty check
    log_info "Running ruff check --fix..."
    uv run ruff check --fix --config "${pyproject_path}"
    log_info "Running ruff format..."
    uv run ruff format --config "${pyproject_path}"
    run_pytest
}

main "$@"

#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"


log_info() { echo "INFO: $*"; }
log_error() { echo "ERROR: $*" >&2; }

amend_linter_changes() {
    local modified_py_files=()
    mapfile -t modified_py_files < <(git diff --name-only | grep '\.py$' || true)

    if [[ ${#modified_py_files[@]} -gt 0 ]]; then
        log_info "Linter modified the following Python files:"
        log_info "${modified_py_files[@]}"
        git add "${modified_py_files[@]}"
    fi
}

main() {
    local pyproject_path="${ROOT_DIR}/pyproject.toml"
    log_info "Running Ty..."
    uv run ty check
    log_info "Running ruff check --fix..."
    uv run ruff check --fix --config "${pyproject_path}"
    log_info "Running ruff format..."
    uv run ruff format --config "${pyproject_path}"
    # Only run amend_linter_changes if we are running as a git pre-commit hook
    if [[ "$(basename "$0")" == "pre-commit" ]]; then
        amend_linter_changes
    fi
    
    log_info "running python tests..."
    uv run pytest --config-file "${pyproject_path}"
}

main "$@"

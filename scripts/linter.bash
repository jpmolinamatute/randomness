#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"


log_info() { echo "INFO: $*"; }
log_error() { echo "ERROR: $*" >&2; }


run_pytest() {
    local pyproject_path="${ROOT_DIR}/pyproject.toml"
    log_info "running python tests..."
    pytest --config-file "${pyproject_path}"
}

main() {
    local pyproject_path="${ROOT_DIR}/pyproject.toml"
    # export PYTHONPATH="${ROOT_DIR}/spotify"
    # shellcheck source=../.venv/bin/activate
    source "${ROOT_DIR}/.venv/bin/activate"
    log_info "Running isort..."
    isort --settings-file "${pyproject_path}" "${ROOT_DIR}/spotify" "${ROOT_DIR}/tests"
    log_info "Running black..."
    black --config "${pyproject_path}" "${ROOT_DIR}/spotify" "${ROOT_DIR}/tests"
    log_info "Running mypy..."
    mypy --config-file "${pyproject_path}" "${ROOT_DIR}/spotify" "${ROOT_DIR}/tests"
    log_info "Running pylint..."
    pylint --rcfile "${pyproject_path}" "${ROOT_DIR}/spotify" "${ROOT_DIR}/tests"
    run_pytest
}

main "$@"

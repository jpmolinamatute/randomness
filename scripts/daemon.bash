#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"

COMPOSE_FILE="${ROOT_DIR}/docker/docker-compose.yaml"

start_docker() {
    is_running=$(docker compose -f "${COMPOSE_FILE}" ps --all --filter status=running --quiet | wc -l)
    if [[ ${is_running} -eq 0 ]]; then
        echo "Starting docker compose"
        docker compose -f "${COMPOSE_FILE}" up --detach
        sleep 2
    else
        echo "Docker was already running. Nothing to do here"
    fi
}

stop_docker() {
    echo "Stopping docker compose"
    docker compose -f "${COMPOSE_FILE}" down
    sleep 2
    is_running=$(docker compose -f "${COMPOSE_FILE}" ps --all --filter status=running --quiet | wc -l)
    if [[ ${is_running} -eq 0 ]]; then
        echo "Docker compose stopped successfully"
    else
        echo "Failed to stop docker compose" >&2
    fi
}


main(){
    start_docker
    # shellcheck source=../.venv/bin/activate
    source "${ROOT_DIR}/.venv/bin/activate"
    "${ROOT_DIR}/main.py" "${@}"
    stop_docker
    exit 0
}

main "${@}"

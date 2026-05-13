#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
PATH="${HOME}/.local/bin:/usr/local/bin:/usr/bin:/usr/local/sbin"
COMPOSE_FILE="${ROOT_DIR}/docker/docker-compose.yaml"

get_running_containers_count() {
    docker compose -f "${COMPOSE_FILE}" ps --all --filter status=running --quiet | wc -l
}

start_docker() {
    if [[ $(get_running_containers_count) -eq 0 ]]; then
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
    if [[ $(get_running_containers_count) -eq 0 ]]; then
        echo "Docker compose stopped successfully"
    else
        echo "Failed to stop docker compose" >&2
    fi
}


main(){
    start_docker
    uv run "${ROOT_DIR}/main.py" "${@}"
    stop_docker
    exit 0
}

main "${@}"

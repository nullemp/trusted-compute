#!/usr/bin/env bash
# Stop backend + MariaDB (compose down). Run from project root. Same runtime as start-for-client.sh.
set -e
cd "$(dirname "$0")/.."

RUNTIME_ROOT="${BUNDLED_RUNTIME_ROOT:-$PWD/runtime}"
BUNDLED_PODMAN="$RUNTIME_ROOT/podman/podman"
BUNDLED_DOCKER="$RUNTIME_ROOT/docker/docker"

RUNTIME=""
ADD_TO_PATH=""

if [[ -x "$BUNDLED_PODMAN" ]]; then
  ADD_TO_PATH="$(dirname "$BUNDLED_PODMAN")"
  RUNTIME=podman
elif [[ -x "$BUNDLED_DOCKER" ]]; then
  ADD_TO_PATH="$(dirname "$BUNDLED_DOCKER")"
  RUNTIME=docker
elif command -v podman &>/dev/null; then
  RUNTIME=podman
elif command -v docker &>/dev/null; then
  RUNTIME=docker
fi

if [[ -z "$RUNTIME" ]]; then
  echo "No podman or docker found. Use same runtime as start-for-client.sh."
  exit 1
fi

if [[ -n "$ADD_TO_PATH" ]]; then
  export PATH="$ADD_TO_PATH:$PATH"
fi

if [[ "$RUNTIME" == "podman" ]]; then
  if podman compose version &>/dev/null; then
    podman compose down
  elif command -v podman-compose &>/dev/null; then
    podman-compose down
  elif command -v docker-compose &>/dev/null; then
    docker-compose down
  else
    echo "Need podman compose, podman-compose, or docker-compose to stop."
    exit 1
  fi
else
  if docker compose version &>/dev/null; then
    docker compose down
  else
    docker-compose down
  fi
fi

echo "Services stopped ($RUNTIME)."

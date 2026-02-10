#!/usr/bin/env bash
# Pre-pull container images from domestic mirror (recommended before offline use).
# Run from project root.
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
  echo "No podman or docker found. Place runtime in project or install on PATH. See start-for-client.sh."
  exit 1
fi

if [[ -n "$ADD_TO_PATH" ]]; then
  export PATH="$ADD_TO_PATH:$PATH"
fi

MARIADB_IMAGE="docker.m.daocloud.io/library/mariadb:11"
PYTHON_IMAGE="docker.m.daocloud.io/library/python:3.11-slim"

echo "Pulling images from domestic mirror (DaoCloud)..."
if [[ "$RUNTIME" == "podman" ]]; then
  podman pull "$MARIADB_IMAGE" || echo "Domestic mirror failed for MariaDB; try again when online or use Docker Hub."
  podman pull "$PYTHON_IMAGE" || echo "Domestic mirror failed for Python; try again when online or use Docker Hub."
else
  docker pull "$MARIADB_IMAGE" || echo "Domestic mirror failed for MariaDB; try again when online or use Docker Hub."
  docker pull "$PYTHON_IMAGE" || echo "Domestic mirror failed for Python; try again when online or use Docker Hub."
fi

echo "Pre-pull done. Run scripts/start-for-client.sh to start the project."

#!/usr/bin/env bash
# Client integration: run from project root. Start backend + MariaDB with Podman or Docker (no frontend).
# Prefer bundled runtime under project runtime/ then PATH (Podman before Docker).
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
  export CONTAINER_RUNTIME=podman
elif [[ -x "$BUNDLED_DOCKER" ]]; then
  ADD_TO_PATH="$(dirname "$BUNDLED_DOCKER")"
  RUNTIME=docker
elif command -v podman &>/dev/null; then
  RUNTIME=podman
  export CONTAINER_RUNTIME=podman
elif command -v docker &>/dev/null; then
  RUNTIME=docker
fi

if [[ -z "$RUNTIME" ]]; then
  echo "No podman or docker found. Either place runtime in project: runtime/podman/podman or runtime/docker/docker, or install one on PATH. See DOCKER_IN_CLIENT.md."
  exit 1
fi

if [[ -n "$ADD_TO_PATH" ]]; then
  export PATH="$ADD_TO_PATH:$PATH"
fi

# Prefer domestic mirror when pulling
export MARIADB_IMAGE="${MARIADB_IMAGE:-docker.m.daocloud.io/library/mariadb:11}"
export PYTHON_IMAGE="${PYTHON_IMAGE:-docker.m.daocloud.io/library/python:3.11-slim}"

# Fully offline: if image archives exist under runtime/images, load them first.
IMAGES_DIR="$RUNTIME_ROOT/images"
if [[ -d "$IMAGES_DIR" ]]; then
  for tar in "$IMAGES_DIR"/*.tar; do
    [[ -f "$tar" ]] || continue
    echo "Loading local image: $tar"
    if ! "$RUNTIME" load -i "$tar"; then
      echo "Warning: Failed to load $tar"
    fi
  done
fi

echo "If required images are not present locally, they will be fetched from the network. Please wait."

if [[ "$RUNTIME" == "podman" ]]; then
  if podman compose version &>/dev/null; then
    podman compose up -d --build
  elif command -v podman-compose &>/dev/null; then
    podman-compose up -d --build
  elif command -v docker-compose &>/dev/null; then
    docker-compose up -d --build
  else
    echo "Need one of: podman compose, podman-compose, or docker-compose. Install Podman (has built-in compose) or docker-compose."
    exit 1
  fi
else
  if docker compose version &>/dev/null; then
    docker compose up -d --build
  else
    docker-compose up -d --build
  fi
fi

echo "Started with $RUNTIME. Backend API: http://localhost:8000  Docs: http://localhost:8000/docs"

#!/usr/bin/env bash
# Start backend + sandbox from project root. This project uses Podman; offline machines typically have only Podman (no Docker).
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
  echo "No Podman or Docker found. This project uses Podman; place runtime/podman/podman or add podman to PATH. See README and docs/OFFLINE_DEPLOY.md."
  exit 1
fi

if [[ -n "$ADD_TO_PATH" ]]; then
  export PATH="$ADD_TO_PATH:$PATH"
fi

export PYTHON_IMAGE="${PYTHON_IMAGE:-docker.m.daocloud.io/library/python:3.11-slim}"

# Offline: if image archives exist under runtime/images, load them and use --no-build.
USE_OFFLINE_IMAGES=0
IMAGES_DIR="$RUNTIME_ROOT/images"
if [[ -d "$IMAGES_DIR" ]]; then
  for tar in "$IMAGES_DIR"/*.tar; do
    [[ -f "$tar" ]] || continue
    USE_OFFLINE_IMAGES=1
    echo "Loading local image: $tar"
    if ! "$RUNTIME" load -i "$tar"; then
      echo "Warning: Failed to load $tar"
    fi
  done
fi
if [[ $USE_OFFLINE_IMAGES -eq 1 ]]; then
  COMPOSE_UP_ARGS="up -d --no-build"
else
  echo "If required images are not present locally, they will be fetched from the network. Please wait."
  COMPOSE_UP_ARGS="up -d --build"
fi

if [[ "$RUNTIME" == "podman" ]]; then
  if podman compose version &>/dev/null; then
    podman compose $COMPOSE_UP_ARGS
  elif command -v podman-compose &>/dev/null; then
    podman-compose $COMPOSE_UP_ARGS
  elif command -v docker-compose &>/dev/null; then
    docker-compose $COMPOSE_UP_ARGS
  else
    echo "Need one of: podman compose, podman-compose, or docker-compose. Install Podman (has built-in compose) or docker-compose."
    exit 1
  fi
else
  if docker compose version &>/dev/null; then
    docker compose $COMPOSE_UP_ARGS
  else
    docker-compose $COMPOSE_UP_ARGS
  fi
fi

echo "Started with $RUNTIME. Backend API: http://localhost:8000  Docs: http://localhost:8000/docs"

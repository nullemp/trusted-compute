#!/usr/bin/env bash
# Build backend + sandbox images and export to runtime/images for offline deployment.
# Run from project root (online). Uses Podman or Docker; offline side uses Podman only. Network required for first build.
set -e
cd "$(dirname "$0")/.."

RUNTIME_ROOT="${BUNDLED_RUNTIME_ROOT:-$PWD/runtime}"
IMAGES_DIR="$RUNTIME_ROOT/images"
BUNDLED_PODMAN="$RUNTIME_ROOT/podman/podman"
BUNDLED_DOCKER="$RUNTIME_ROOT/docker/docker"

RUNTIME=""
if [[ -x "$BUNDLED_PODMAN" ]]; then
  export PATH="$(dirname "$BUNDLED_PODMAN"):$PATH"
  RUNTIME=podman
  export CONTAINER_RUNTIME=podman
elif [[ -x "$BUNDLED_DOCKER" ]]; then
  export PATH="$(dirname "$BUNDLED_DOCKER"):$PATH"
  RUNTIME=docker
elif command -v podman &>/dev/null; then
  RUNTIME=podman
  export CONTAINER_RUNTIME=podman
elif command -v docker &>/dev/null; then
  RUNTIME=docker
fi
if [[ -z "$RUNTIME" ]]; then
  echo "No podman or docker found."
  exit 1
fi

export PYTHON_IMAGE="${PYTHON_IMAGE:-docker.m.daocloud.io/library/python:3.11-slim}"
export DOCKER_BUILDKIT=0
export COMPOSE_DOCKER_CLI_BUILD=0

echo "Building images with $RUNTIME (this requires network)..."
if [[ "$RUNTIME" == "podman" ]]; then
  if podman compose version &>/dev/null; then
    podman compose build
  else
    podman-compose build
  fi
else
  if docker compose version &>/dev/null; then
    docker compose build
  else
    docker-compose build
  fi
fi

mkdir -p "$IMAGES_DIR"
echo "Saving images to $IMAGES_DIR ..."
$RUNTIME save -o "$IMAGES_DIR/trusted-compute-backend.tar" trusted-compute-backend
$RUNTIME save -o "$IMAGES_DIR/trusted-compute-sandbox.tar" trusted-compute-sandbox

# MariaDB: 沙箱按需启动的 DB 容器用此镜像；未设 MARIADB_IMAGE 时用国内镜像避免 Docker Hub 超时
MARIADB_SAVE_TAG="docker.io/library/mariadb:11.2"
MARIADB_PULL="${MARIADB_IMAGE:-docker.m.daocloud.io/library/mariadb:11.2}"
echo "Pulling MariaDB from $MARIADB_PULL and saving as $MARIADB_SAVE_TAG for offline sandbox DB..."
$RUNTIME pull "$MARIADB_PULL"
if [[ "$MARIADB_PULL" != "$MARIADB_SAVE_TAG" ]]; then
  $RUNTIME tag "$MARIADB_PULL" "$MARIADB_SAVE_TAG"
fi
$RUNTIME save -o "$IMAGES_DIR/mariadb.tar" "$MARIADB_SAVE_TAG"

# Package examples Python wheels for offline install (run examples scripts without PyPI)
echo "Downloading examples Python wheels for offline install..."
if ! "$(dirname "$0")/download-examples-wheels.sh"; then
  echo "Warning: Examples wheels could not be downloaded (e.g. Python/pip not found). To package them later, run: scripts/download-examples-wheels.sh"
fi

echo "Done. Copy the project (including runtime/images/*.tar and, if present, examples/offline_wheels/) to the offline environment and run the usual start script."

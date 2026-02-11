#!/usr/bin/env bash
# Pre-pull container images from domestic mirror (recommended before offline use).
# Also saves them as .tar archives under runtime/images for fully offline environments.
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

# Default: domestic mirror (faster in China). Set env USE_OFFICIAL_HUB=1 to use Docker Hub.
if [[ "$USE_OFFICIAL_HUB" == "1" ]]; then
  MARIADB_IMAGE="mariadb:11"
  PYTHON_IMAGE="python:3.11-slim"
  echo "Using Docker Hub (USE_OFFICIAL_HUB=1)."
else
  MARIADB_IMAGE="docker.m.daocloud.io/library/mariadb:11"
  PYTHON_IMAGE="docker.m.daocloud.io/library/python:3.11-slim"
  echo "Using domestic mirror (DaoCloud). Set USE_OFFICIAL_HUB=1 to use Docker Hub."
fi

echo "Pulling images..."
if [[ "$RUNTIME" == "podman" ]]; then
  podman pull "$MARIADB_IMAGE" || echo "Domestic mirror failed for MariaDB; try again when online or use Docker Hub."
  podman pull "$PYTHON_IMAGE" || echo "Domestic mirror failed for Python; try again when online or use Docker Hub."
else
  docker pull "$MARIADB_IMAGE" || echo "Domestic mirror failed for MariaDB; try again when online or use Docker Hub."
  docker pull "$PYTHON_IMAGE" || echo "Domestic mirror failed for Python; try again when online or use Docker Hub."
fi

# Save images as .tar under runtime/images for fully offline use (start script will load them when present).
IMAGES_DIR="$RUNTIME_ROOT/images"
mkdir -p "$IMAGES_DIR"
MARIADB_TAR="$IMAGES_DIR/mariadb-11.tar"
PYTHON_TAR="$IMAGES_DIR/python-3.11-slim.tar"

echo "Saving images to $IMAGES_DIR ..."
if [[ "$RUNTIME" == "podman" ]]; then
  if ! podman save -o "$MARIADB_TAR" "$MARIADB_IMAGE"; then
    echo "Warning: Failed to save $MARIADB_IMAGE to $MARIADB_TAR. You may run: podman save -o \"$MARIADB_TAR\" \"$MARIADB_IMAGE\""
  fi
  if ! podman save -o "$PYTHON_TAR" "$PYTHON_IMAGE"; then
    echo "Warning: Failed to save $PYTHON_IMAGE to $PYTHON_TAR. You may run: podman save -o \"$PYTHON_TAR\" \"$PYTHON_IMAGE\""
  fi
else
  if ! docker save -o "$MARIADB_TAR" "$MARIADB_IMAGE"; then
    echo "Warning: Failed to save $MARIADB_IMAGE to $MARIADB_TAR. You may run: docker save -o \"$MARIADB_TAR\" \"$MARIADB_IMAGE\""
  fi
  if ! docker save -o "$PYTHON_TAR" "$PYTHON_IMAGE"; then
    echo "Warning: Failed to save $PYTHON_IMAGE to $PYTHON_TAR. You may run: docker save -o \"$PYTHON_TAR\" \"$PYTHON_IMAGE\""
  fi
fi

echo "Pre-pull and export done. Archives are under runtime/images. Run scripts/start-for-client.sh to start the project."

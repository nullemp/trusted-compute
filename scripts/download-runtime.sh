#!/usr/bin/env bash
# Install Podman and optionally copy to project runtime/podman for bundled use.
# Run from project root or scripts/. Prefer system package manager.
set -e
cd "$(dirname "$0")/.."
RUNTIME_PODMAN="$PWD/runtime/podman"

mkdir -p "$RUNTIME_PODMAN"

if command -v podman &>/dev/null; then
  PODMAN_EXE=$(command -v podman)
  if [[ -x "$RUNTIME_PODMAN/podman" ]]; then
    echo "runtime/podman/podman already exists. Skip."
    exit 0
  fi
  echo "Podman found at $PODMAN_EXE. Copying to runtime/podman/ ..."
  SRC_DIR=$(dirname "$PODMAN_EXE")
  cp -f "$PODMAN_EXE" "$RUNTIME_PODMAN/podman"
  for exe in podman-compose docker-compose; do
    if command -v "$exe" &>/dev/null; then
      cp -f "$(command -v "$exe")" "$RUNTIME_PODMAN/$exe" 2>/dev/null || true
    fi
  done
  echo "Done. Run ./scripts/start-for-client.sh to start services."
  exit 0
fi

# Try to install via package manager
echo "Podman not found. Attempting install..."
if command -v apt-get &>/dev/null; then
  sudo apt-get update && sudo apt-get install -y podman
elif command -v dnf &>/dev/null; then
  sudo dnf install -y podman
elif command -v yum &>/dev/null; then
  sudo yum install -y podman
elif command -v zypper &>/dev/null; then
  sudo zypper install -y podman
elif command -v brew &>/dev/null; then
  brew install podman
else
  echo "No supported package manager. Install Podman manually and run this script again, or place podman binary in runtime/podman/podman. See runtime/README.md."
  exit 1
fi

echo "Podman installed. Run this script again to copy to runtime/podman/, or run ./scripts/start-for-client.sh (will use PATH)."
exit 0

#!/usr/bin/env bash
# Idempotent repair for competition map filenames (run inside repo root or Docker).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MAPS_DIR="$REPO_ROOT/maps"

cd "$MAPS_DIR"

if [[ -f restaurant.yaml.yaml && ! -f restaurant.yaml ]]; then
  mv restaurant.yaml.yaml restaurant.yaml
  echo "Renamed restaurant.yaml.yaml -> restaurant.yaml"
fi

if [[ -f restaurant.yaml.pgm && ! -f restaurant.pgm ]]; then
  mv restaurant.yaml.pgm restaurant.pgm
  echo "Renamed restaurant.yaml.pgm -> restaurant.pgm"
fi

if [[ -f restaurant.yaml ]]; then
  if grep -q 'restaurant.yaml.pgm' restaurant.yaml; then
    sed -i 's/restaurant\.yaml\.pgm/restaurant.pgm/g' restaurant.yaml
    echo "Fixed image reference in restaurant.yaml"
  fi
fi

if [[ -f restaurant.yaml && -f restaurant.pgm ]]; then
  echo "[OK] Competition map ready: maps/restaurant.yaml + maps/restaurant.pgm"
else
  echo "[FAIL] Missing maps/restaurant.yaml or maps/restaurant.pgm" >&2
  exit 1
fi

#!/usr/bin/env bash
# Build a self-contained `opengeneral` binary for the current OS with PyInstaller.
#
# Output: dist/opengeneral  (a single-file executable)
#
# PyInstaller does not cross-compile — run this on each target OS to produce that
# platform's binary. Override the Python used with PYTHON=/path/to/python.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON="${PYTHON:-python3}"

if ! "$PYTHON" -c "import PyInstaller" >/dev/null 2>&1; then
  echo "PyInstaller is not installed for $PYTHON."
  echo "Install the build extra first:  $PYTHON -m pip install -e '.[build]'"
  exit 1
fi

# litellm, keyring and tiktoken pull in data files and lazy/plugin imports that
# PyInstaller's static analysis misses. collect-all bundles them wholesale.
# Only request packages that are actually importable so the build degrades
# gracefully (e.g. a core-only build without the provider extra installed).
COLLECT_PKGS=(litellm keyring tiktoken)
COLLECT_ARGS=()
for pkg in "${COLLECT_PKGS[@]}"; do
  if "$PYTHON" -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('$pkg') else 1)" >/dev/null 2>&1; then
    COLLECT_ARGS+=(--collect-all "$pkg")
    # keyring loads its OS backends as plugins; gather them only when keyring is present.
    if [[ "$pkg" == keyring ]]; then
      COLLECT_ARGS+=(--collect-submodules keyring.backends)
    fi
  else
    echo "Note: '$pkg' not importable; skipping its data files in this build."
  fi
done

echo "Building opengeneral binary with $PYTHON ..."
# ${COLLECT_ARGS[@]+...} guards the empty-array case, which errors under `set -u`
# on bash 3.2 (the /bin/bash shipped with macOS).
"$PYTHON" -m PyInstaller \
  --noconfirm --clean --onefile \
  --name opengeneral \
  --paths src \
  --add-data "$REPO_ROOT/personas:personas" \
  --add-data "$REPO_ROOT/skills:skills" \
  --distpath dist \
  --workpath build/pyinstaller \
  --specpath build/pyinstaller \
  ${COLLECT_ARGS[@]+"${COLLECT_ARGS[@]}"} \
  packaging/entry.py

echo
echo "Built: $REPO_ROOT/dist/opengeneral"
echo "Try it:  ./dist/opengeneral --help"

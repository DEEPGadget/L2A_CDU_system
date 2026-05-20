#!/bin/bash
# install-hooks.sh — point this repo's git hooks at scripts/git-hooks/
#
# Run once after cloning the repo on a new machine. This sets
# core.hooksPath so git invokes scripts/git-hooks/* directly; no copy
# into .git/hooks is needed, and hooks stay version-controlled.
#
# To remove: git config --unset core.hooksPath

set -e

REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"

HOOK_DIR="scripts/git-hooks"

if [[ ! -d "$HOOK_DIR" ]]; then
    echo "ERROR: $HOOK_DIR not found in $REPO_ROOT" >&2
    exit 1
fi

# Ensure hooks are executable (some VCS workflows lose the mode bit).
chmod +x "$HOOK_DIR"/* 2>/dev/null || true

git config core.hooksPath "$HOOK_DIR"

echo "Installed git hooks from $HOOK_DIR:"
ls -1 "$HOOK_DIR" | sed 's/^/  - /'
echo
echo "Active: $(git config --get core.hooksPath)"

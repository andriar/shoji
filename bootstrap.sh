#!/bin/sh
# Shoji in one go: clone (or update) the release into ~/shoji, then run its installer.
#   curl -fsSLo /tmp/shoji-bootstrap.sh https://raw.githubusercontent.com/andriar/shoji/v0.6.0/bootstrap.sh
#   sha256sum /tmp/shoji-bootstrap.sh     # compare with the README, then:
#   sh /tmp/shoji-bootstrap.sh [palette]
# The installer backs up every file it replaces and never edits your Hyprland config.
set -eu
TAG="${SHOJI_TAG:-v0.6.0}"
DIR="${SHOJI_DIR:-$HOME/shoji}"
command -v git >/dev/null || { echo "Shoji needs git to fetch itself."; exit 1; }
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" fetch --quiet --tags origin
  git -C "$DIR" -c advice.detachedHead=false checkout --quiet "$TAG"
else
  git -c advice.detachedHead=false clone --quiet --depth 1 --branch "$TAG" https://github.com/andriar/shoji "$DIR"
fi
exec "$DIR/install.sh" "$@"

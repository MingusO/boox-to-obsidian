#!/bin/sh
# Koeres i Terminal & SSH add on'et i Home Assistant.
# Henter eller opdaterer repoet og kopierer add on'et ind som lokalt add on.
# Brug: sh install_local.sh <repo url>
set -e
REPO_URL="$1"
if [ -z "$REPO_URL" ]; then
  echo "Angiv repo URL, fx https://github.com/dit_brugernavn/boox-to-obsidian.git"
  exit 1
fi
WORK=/root/boox-to-obsidian
if [ -d "$WORK/.git" ]; then
  git -C "$WORK" pull
else
  git clone "$REPO_URL" "$WORK"
fi
mkdir -p /addons
rm -rf /addons/boox_obsidian
cp -r "$WORK/boox_obsidian" /addons/boox_obsidian
echo "Faerdig. Gaa til Indstillinger, Apps, Butik, menuen med de tre prikker, Tjek for opdateringer."

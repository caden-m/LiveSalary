#!/bin/sh
# Renders the social preview cards in build/og/*.svg to assets/og/<slug>.png (1200×630) using
# macOS QuickLook, skipping cards whose PNG is already newer than the SVG. Run after generate.py.
set -e
cd "$(dirname "$0")/.."
mkdir -p assets/og

todo=""
for svg in build/og/*.svg; do
    name=$(basename "$svg" .svg)
    png="assets/og/$name.png"
    if [ ! -f "$png" ] || [ "$svg" -nt "$png" ]; then todo="$todo $svg"; fi
done
if [ -z "$todo" ]; then echo "Social cards already up to date."; exit 0; fi

tmp=$(mktemp -d)
# shellcheck disable=SC2086
qlmanage -t -s 1200 -o "$tmp" $todo >/dev/null 2>&1
count=0
for f in "$tmp"/*.svg.png; do
    name=$(basename "$f" .svg.png)
    # QuickLook pads to a square; crop the middle 1200×630 band.
    sips -c 630 1200 "$f" --out "assets/og/$name.png" >/dev/null
    count=$((count + 1))
done
rm -rf "$tmp"
echo "Rendered $count social cards into assets/og/."

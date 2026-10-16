#!/usr/bin/env bash
# Rendert ein gebautes Iconpack als Kontaktbogen (PNG) auf libadwaita-Hintergründen.
#
#   tools/contact-sheet.sh [PACK] [AUSGABE]          alle Icons eines Packs
#   tools/contact-sheet.sh --accents [AUSGABE]       Akzent-Icons aller Varianten nebeneinander
#
# Braucht rsvg-convert und ImageMagick (magick). Vorher build.py laufen lassen.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
gfx="$root/build/iconpacks"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

render() { # svg png size
	rsvg-convert -w "$3" -h "$3" "$1" -o "$2"
}

if [[ "${1:-}" == "--accents" ]]; then
	out="${2:-$root/build/contact-accents.png}"
	icons=(player_off player_on player_commander_off player_commander_on player_whisper
		channel_green channel_green_subscribed channel_commander subscribe_to_channel
		input_muted output_muted away is_talker group_300 ping_1)
	rows=()
	for pack in "$gfx"/Papirus-Dark-*; do
		name="$(basename "$pack")"
		files=()
		for icon in "${icons[@]}"; do
			render "$pack/$icon.svg" "$work/$name-$icon.png" 32
			files+=("$work/$name-$icon.png")
		done
		magick montage "${files[@]}" -background '#1d1d20' -tile x1 \
			-geometry 32x32+8+8 "$work/row-$name.png"
		magick "$work/row-$name.png" -background '#1d1d20' -fill '#ffffff' -font DejaVu-Sans \
			-pointsize 13 label:"${name#Papirus-Dark-}" +swap -gravity center -append "$work/row-$name.png"
		rows+=("$work/row-$name.png")
	done
	magick montage "${rows[@]}" -background '#222226' -tile 2x -geometry +12+8 "$out"
	echo "$out"
	exit 0
fi

pack="${1:-Papirus-Dark}"
out="${2:-$root/build/contact-$pack.png}"
for svg in "$gfx/$pack"/*.svg; do
	render "$svg" "$work/$(basename "${svg%.svg}").png" 32
done
magick montage -label '%t' "$work"/*.png -background '#1d1d20' -fill '#dddddd' \
	-pointsize 9 -tile 12x -geometry 32x32+44+6 "$out"
echo "$out"

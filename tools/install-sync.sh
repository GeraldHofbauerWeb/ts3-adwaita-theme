#!/usr/bin/env bash
# Richtet den Akzent-Sync als systemd-User-Dienst ein (oder entfernt ihn mit --remove).
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
unit=ts3-adwaita-accent.service
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

if [[ "${1:-}" == "--remove" ]]; then
	systemctl --user disable --now "$unit" 2>/dev/null || true
	rm -f "$unit_dir/$unit"
	systemctl --user daemon-reload
	echo "$unit entfernt."
	exit 0
fi

mkdir -p "$unit_dir"
sed "s|@ROOT@|$root|g" "$root/systemd/$unit" >"$unit_dir/$unit"
systemctl --user daemon-reload
systemctl --user enable --now "$unit"
systemctl --user --no-pager status "$unit" | head -5

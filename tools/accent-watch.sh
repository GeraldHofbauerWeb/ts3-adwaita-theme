#!/usr/bin/env bash
# Baut die Varianten Adwaita-Dark und Papirus-Dark neu, sobald sich die
# GNOME-Akzentfarbe ändert. Läuft als systemd-User-Dienst (tools/install-sync.sh).
set -uo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"

rebuild() {
	python3 "$root/build.py" --variant system --install
}

# Einmal beim Start, falls die Farbe gewechselt wurde, während der Dienst nicht lief.
rebuild

gsettings monitor org.gnome.desktop.interface accent-color | while read -r _; do
	# Wer in den Einstellungen durch die Farben klickt, erzeugt mehrere Ereignisse
	# kurz hintereinander. Erst bauen, wenn eine Sekunde Ruhe ist.
	while read -r -t 1 _; do :; done
	rebuild
done

#!/usr/bin/env bash
# Startet eine abgeschottete TeamSpeak-Testinstanz zum Ansehen des Stils.
#
# Eigenes Profil (TS3_CONFIG_DIR), eigenes HOME, kein Netz (unshare -c -n) und ein
# virtueller Bildschirm (Xvfb). Ein laufender TS3-Client und sein Profil bleiben unberührt.
#
#   tools/preview.sh start [STIL] [ICONPACK]   Varianten ins Testprofil bauen, TS3 starten
#   tools/preview.sh shot DATEI.png            Bildschirmfoto
#   tools/preview.sh key TASTEN…               Tastendruck an das aktive Fenster (xdotool)
#   tools/preview.sh click X Y                 Mausklick
#   tools/preview.sh stop                      TS3 und Xvfb beenden
#   tools/preview.sh clean                     zusätzlich das Testprofil löschen
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
base="${PREVIEW_DIR:-$root/build/preview}"
home="$base/home"
config="$home/.ts3client"
display="${PREVIEW_DISPLAY:-:87}"
ts3="${TS3_DIR:-/opt/teamspeak3}"
export DISPLAY="$display"

set_setting() { # key value
	sqlite3 "$config/settings.db" \
		"UPDATE Application SET value='$2' WHERE key='$1';
		 INSERT INTO Application (timestamp, key, value)
		 SELECT strftime('%s','now'), '$1', '$2'
		 WHERE NOT EXISTS (SELECT 1 FROM Application WHERE key='$1');"
}

wait_for_window() {
	for _ in $(seq 1 60); do
		xdotool search --name "TeamSpeak" >/dev/null 2>&1 && return 0
		sleep 0.5
	done
	echo "Kein TeamSpeak-Fenster erschienen, Log: $base/ts3.log" >&2
	return 1
}

# Alle Programme laufen in TS3s Verzeichnis mit dessen mitgelieferten Qt-Bibliotheken.
ts3_env() {
	env HOME="$home" TS3_CONFIG_DIR="$config" QT_PLUGIN_PATH=. LD_LIBRARY_PATH=".:${LD_LIBRARY_PATH:-}" \
		XDG_SESSION_TYPE=x11 QT_QPA_PLATFORM=xcb DISPLAY="$display" "$@"
}

# Testprozesse an ihrer Umgebung erkennen. Die Kommandozeile gleicht der eines echten
# TS3-Clients, der daneben läuft und auf keinen Fall beendet werden darf.
test_pids() {
	local pid
	for pid in $(pgrep -f 'ts3client_linux_amd64|QtWebEngineProcess' || true); do
		if tr '\0' '\n' <"/proc/$pid/environ" 2>/dev/null | grep -qxF "TS3_CONFIG_DIR=$config"; then
			echo "$pid"
		fi
	done
}

start_ts3() {
	(cd "$ts3" && ts3_env setsid -f unshare -c -n ./ts3client_linux_amd64 -nosingleinstance \
		>"$base/ts3.log" 2>&1)
	wait_for_window
}

stop_ts3() {
	local pids
	pids="$(test_pids)"
	[[ -n "$pids" ]] && kill $pids 2>/dev/null || true
	for _ in $(seq 1 20); do
		[[ -z "$(test_pids)" ]] && return 0
		sleep 0.5
	done
	pids="$(test_pids)"
	[[ -n "$pids" ]] && kill -9 $pids 2>/dev/null || true
}

case "${1:-}" in
start)
	style="${2:-Adwaita-Dark}"
	iconpack="${3:-Papirus-Dark}"
	mkdir -p "$config"
	if ! pgrep -xf "Xvfb $display .*" >/dev/null; then
		setsid -f Xvfb "$display" -screen 0 1600x1000x24 -nolisten tcp >"$base/xvfb.log" 2>&1
		sleep 1
	fi
	if [[ ! -f "$config/settings.db" ]]; then
		# Stil und Icons stehen in settings.db; die legt erst der erste Start an.
		start_ts3
		sleep 4
		stop_ts3
	fi
	python3 "$root/build.py" --install --config-dir "$config" >"$base/install.log" 2>&1 \
		|| { echo "Installation fehlgeschlagen (siehe $base/install.log)" >&2; exit 1; }
	set_setting QtStyleSheet "$style"
	set_setting IconPack "$iconpack"
	start_ts3
	echo "TS3 läuft auf $display mit $style / $iconpack"
	;;
shot)
	import -window root -display "$display" "${2:?Dateiname fehlt}"
	echo "$2"
	;;
key)
	shift
	xdotool key --clearmodifiers "$@"
	;;
click)
	xdotool mousemove "$2" "$3" click 1
	;;
stop)
	stop_ts3
	pkill -xf "Xvfb $display .*" 2>/dev/null || true
	;;
clean)
	"$0" stop
	rm -rf "$base"
	;;
*)
	sed -n '2,13p' "$0"
	exit 1
	;;
esac

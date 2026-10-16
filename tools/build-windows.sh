#!/usr/bin/env bash
# Baut den Windows-Installer dist/ts3-adwaita-theme-setup-<version>.exe.
#
# Inno Setup läuft über Wine in einem eigenen Präfix unter ~/.cache, damit nichts
# davon im (synchronisierten) Repo landet. Beim ersten Lauf wird Inno Setup von
# GitHub geladen und gegen die feste Prüfsumme geprüft.
#
# Braucht wine, xvfb-run und curl.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cache="${XDG_CACHE_HOME:-$HOME/.cache}/ts3-adwaita-theme"
inno_url="https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe"
inno_sha256="9c73c3bae7ed48d44112a0f48e66742c00090bdb5bef71d9d3c056c66e97b732"

export WINEPREFIX="$cache/wine"
export WINEDEBUG=-all
# Kein Mono/Gecko nachinstallieren lassen, Inno Setup braucht beides nicht.
export WINEDLLOVERRIDES="mscoree,mshtml="
iscc="$WINEPREFIX/drive_c/InnoSetup/ISCC.exe"

# Der wineserver bleibt sonst im Hintergrund und hält die Ausgabe des Aufrufers offen.
trap 'wineserver -k 2>/dev/null || true' EXIT

if [[ ! -f "$iscc" ]]; then
	mkdir -p "$cache"
	curl -fsSL -o "$cache/innosetup.exe" "$inno_url"
	echo "$inno_sha256  $cache/innosetup.exe" | sha256sum -c --quiet
	xvfb-run -a wine "$cache/innosetup.exe" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CURRENTUSER \
		'/DIR=C:\InnoSetup' >/dev/null 2>&1 || true
	[[ -f "$iscc" ]] || { echo "Inno Setup ließ sich nicht installieren" >&2; exit 1; }
fi

python3 "$root/build.py" --windows
version="$(cd "$root" && python3 -c 'import build; print(build.VERSION)')"
mkdir -p "$root/dist"
rm -f "$root/dist/ts3-adwaita-theme-setup-$version.exe"
(cd "$root/installer" && xvfb-run -a wine "$iscc" /Q "/DAppVersion=$version" ts3-adwaita-theme.iss) 2>&1 \
	| grep -v -e '^XIO:' -e 'after [0-9]* requests' || true
ls -l "$root/dist/ts3-adwaita-theme-setup-$version.exe"

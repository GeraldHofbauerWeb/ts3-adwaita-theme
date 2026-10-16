# ts3-adwaita-theme

Ein dunkler Stil und ein passendes Iconpack für den TeamSpeak-3-Client unter Linux. Die Farben folgen libadwaita (GNOME, dunkles Erscheinungsbild), die Symbole stammen aus dem Papirus-Dark-Thema.

Das Skript erzeugt elf Stile und elf Iconpacks:

- `Adwaita-Dark` und `Papirus-Dark` übernehmen die Akzentfarbe aus den GNOME-Einstellungen.
- `Adwaita-Dark-Blue` bis `Adwaita-Dark-Maia` und `Papirus-Dark-Blue` bis `Papirus-Dark-Maia` haben je eine der zehn GNOME-Akzentfarben fest eingebaut.

Getestet mit TeamSpeak 3.6.2 unter `/opt/teamspeak3` auf Manjaro mit GNOME 50.

## Voraussetzungen

- TeamSpeak-3-Client 3.6
- Python 3.11 oder neuer (nur Standardbibliothek)
- das Papirus-Icon-Theme unter `/usr/share/icons/Papirus` und `/usr/share/icons/Papirus-Dark`
- optional `rsvg-convert` (librsvg) zum Prüfen der erzeugten SVGs

Für die Vorschau-Werkzeuge kommen ImageMagick, Xvfb und xdotool dazu.

## Installieren

```sh
python3 build.py --install
```

Das schreibt alle Varianten nach `~/.ts3client/styles/` und `~/.ts3client/gfx/`. Ein anderes Profil geht mit `--config-dir PFAD` oder über die Umgebungsvariable `TS3_CONFIG_DIR`.

In TeamSpeak unter *Extras → Optionen → Design* dann das Thema `Adwaita-Dark` und das Icon Pack `Papirus-Dark` wählen. Nach einem Neustart von TeamSpeak ist alles übernommen.

## Akzentfarbe automatisch übernehmen

```sh
tools/install-sync.sh
```

Das richtet den systemd-User-Dienst `ts3-adwaita-accent.service` ein. Er beobachtet `org.gnome.desktop.interface accent-color` und baut bei jeder Änderung `Adwaita-Dark` und `Papirus-Dark` neu, was rund eine Fünftelsekunde dauert. TeamSpeak lädt den Stil beim Start, die neue Farbe erscheint also nach dem nächsten Neustart des Clients. Der Dienst verweist auf diesen Ordner und funktioniert nur, solange das Repo dort liegt.

`tools/install-sync.sh --remove` schaltet den Dienst ab und löscht die Unit.

## Entfernen

Zuerst in TeamSpeak ein anderes Thema und Icon Pack wählen, dann:

```sh
python3 build.py --uninstall
tools/install-sync.sh --remove
```

## Warum es kein .ts3_style-Paket gibt

TeamSpeak hat einen eigenen Installer (`package_inst`) für `.ts3_style`- und `.ts3_iconpack`-Pakete. Mit mehreren Varianten in einem Paket benimmt er sich ungünstig: Er sortiert die Dateiliste selbst, schreibt den Paketnamen an den alphabetisch ersten Eintrag (hier `-Blue`) und aktiviert den letzten. Liegen die Dateien dagegen direkt im Profil, erkennt TeamSpeak sie beim Start und zeigt sie unter ihrem Dateinamen an. Iconpacks lädt TeamSpeak 3.6 außerdem nur als Zip-Archiv, ein Ordner gleichen Namens wird ignoriert.

## Aufbau

| Pfad | Inhalt |
|---|---|
| `palette.toml` | libadwaita-Farben, die zehn Akzentfarben, Farben der Gruppenabzeichen |
| `style/adwaita-dark.qss.in` | Qt-Stylesheet mit Platzhaltern wie `@view_bg` und `@accent` |
| `style/adwaita-dark_chat.qss.in` | Farben für Chatverlauf und Info-Ansicht |
| `style/assets/` | Häkchen, Radiopunkt, Pfeile und Schließen-Kreuz als SVG-Vorlagen |
| `iconpack/mapping.toml` | Zuordnung der 213 TeamSpeak-Symbolschlüssel zu Papirus-Symbolen |
| `build.py` | ersetzt die Platzhalter, färbt die Symbole ein, schreibt Stile und Zip-Archive |
| `tools/` | Kontaktbogen, Vorschau, Akzent-Sync |

Ohne Argumente baut `build.py` alle Varianten nach `build/profile/` und prüft sie: Jedes SVG muss sich parsen und mit `rsvg-convert` rendern lassen, und alle Symbolschlüssel aus TeamSpeaks eigenem Mono-Pack müssen belegt sein.

Die Qt-Palette steht als Kommentarblock oben im Stylesheet (`QPalette::Window = …;`). TeamSpeak liest diese Zeilen selbst aus und setzt damit die Palette, das Stylesheet verfeinert danach nur noch einzelne Widgets. Papirus färbt seine Symbole über CSS-Klassen und `currentColor`. Das wertet QtSvg 5.15 nicht zuverlässig aus, deshalb setzt `build.py` die Farben direkt in die Pfade ein.

### Symbole zuordnen

Ein Eintrag in `iconpack/mapping.toml` sieht so aus:

```toml
INPUT_MUTED = { src = "s:status/microphone-disabled", color = "destructive", solid = true }
CHANNEL_DELETE = { src = "shape:bubble", badge = "s:actions/window-close", badge_color = "destructive" }
```

`src` verweist auf ein Papirus-Symbol (`a:` für `Papirus-Dark/16x16/actions`, `s:` für `Papirus/16x16/symbolic`, `d:`, `p:` und `m:` für Geräte, Orte und Emotes) oder auf eine eigene Form aus `build.py`, etwa den Sprechpunkt oder die Kanal-Sprechblase. `badge` legt ein kleines Abzeichen unten rechts darüber. `solid = true` entfernt die Halbtransparenz, mit der Papirus manche Statussymbole zeichnet.

### Ansehen, ohne den eigenen Client anzufassen

```sh
python3 build.py
tools/contact-sheet.sh Papirus-Dark      # build/contact-Papirus-Dark.png
tools/contact-sheet.sh --accents         # Akzentsymbole aller Varianten nebeneinander
tools/preview.sh start                   # TeamSpeak auf Xvfb, eigenes Profil, ohne Netz
tools/preview.sh shot bild.png
tools/preview.sh clean
```

`preview.sh` startet TeamSpeak mit eigenem `HOME` und `TS3_CONFIG_DIR` unter `build/preview/`, in einem Netz-Namensraum ohne Verbindung nach außen (`unshare -c -n`) und auf einem virtuellen Bildschirm. Ein laufender TeamSpeak-Client bleibt davon unberührt; beim Beenden erkennt das Skript die eigenen Prozesse an ihrer Umgebung, nicht an der Kommandozeile.

## Lizenz

Der eigene Code (Skripte, Stylesheets, Formen, Zuordnung) steht unter der MIT-Lizenz, siehe `LICENSE`.

Das Repo enthält keine Papirus-Dateien. `build.py` liest die Symbole beim Bauen aus dem lokal installierten Papirus-Icon-Theme, und die erzeugten Iconpacks stehen deshalb unter dessen Lizenz (GPL-3.0). Aus TeamSpeak selbst liest das Skript nur die Liste der Symbolschlüssel.

TeamSpeak ist eine Marke der TeamSpeak Systems GmbH. Dieses Projekt hat mit TeamSpeak Systems nichts zu tun.

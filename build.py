#!/usr/bin/env python3
"""Baut den TeamSpeak-3-Stil „Adwaita Dark" und das Iconpack „Papirus Dark".

Ohne Argumente entstehen alle Varianten (System + zehn Akzente) in build/ und
werden geprüft. --install schreibt sie direkt ins TS3-Profil, --uninstall
entfernt sie wieder. Mit --variant system --install baut das Skript nur die
Variante neu, die der GNOME-Akzentfarbe folgt; das nutzt der Akzent-Sync-Dienst.

Warum kein .ts3_style-Paket: Der TS3-Installer sortiert die Dateiliste selbst,
schreibt den Paketnamen an den alphabetisch ersten Stil (also -Blue) und
aktiviert den letzten. Direkt ins Profil gelegte Dateien erkennt TS3 beim Start
selbst und benennt sie nach dem Dateinamen.
"""

import argparse
import math
import os
import re
import shutil
import subprocess
import sys
import tomllib
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"

PAPIRUS_DARK = Path("/usr/share/icons/Papirus-Dark/16x16")
PAPIRUS_SYMBOLIC = Path("/usr/share/icons/Papirus/16x16/symbolic")
TS3_DIR = Path("/opt/teamspeak3")
# Nur zum Abgleich der Schlüsselliste, es wird nichts daraus übernommen.
TS3_REFERENCE_PACK = TS3_DIR / "gfx" / "default_mono_2014.zip"

VERSION = "1.0.0"
STYLE_BASE = "Adwaita-Dark"
ICONPACK_BASE = "Papirus-Dark"

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

# Papirus färbt über CSS-Klassen; QtSvg 5.15 wertet die nicht zuverlässig aus.
CLASS_ROLES = {
    "ColorScheme-Text": "main",
    "ColorScheme-Highlight": "accent",
    "ColorScheme-PositiveText": "success",
    "ColorScheme-NeutralText": "warning",
    "ColorScheme-NegativeText": "destructive",
}
PAPIRUS_DARK_TEXT = "#dfdfdf"


# --- Farben -----------------------------------------------------------------

def hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in rgb)


def mix(a, b, amount):
    """Mischt b mit dem Anteil amount in a."""
    ra, rb = hex_to_rgb(a), hex_to_rgb(b)
    return rgb_to_hex([x + (y - x) * amount for x, y in zip(ra, rb)])


def over(color, alpha, background):
    """Farbe mit Deckkraft alpha über einem Hintergrund, als volle Farbe."""
    return mix(background, color, alpha)


def rgba(color, alpha):
    # Qt liest den vierten Wert als 0–255; 0 und 1 deutet es als Bruch.
    r, g, b = hex_to_rgb(color)
    return f"rgba({r}, {g}, {b}, {max(2, round(alpha * 255))})"


def load_palette():
    with open(ROOT / "palette.toml", "rb") as f:
        return tomllib.load(f)


def system_accent(accents):
    try:
        out = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "accent-color"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip().strip("'")
    except (OSError, subprocess.SubprocessError):
        out = ""
    # libadwaita fällt bei unbekannten Werten ebenfalls auf Blau zurück.
    return out if out in accents else "blue"


def variants(palette, wanted, accent_override):
    accents = palette["accents"]
    result = []
    if wanted in ("all", "system"):
        name = accent_override or system_accent(accents)
        if name not in accents:
            sys.exit(f"Unbekannte Akzentfarbe: {name}")
        result.append({"id": "system", "accent": name,
                       "style": STYLE_BASE, "iconpack": ICONPACK_BASE})
    for name in accents:
        if wanted in ("all", name):
            label = name.capitalize()
            result.append({"id": name, "accent": name,
                           "style": f"{STYLE_BASE}-{label}",
                           "iconpack": f"{ICONPACK_BASE}-{label}"})
    if not result:
        sys.exit(f"Unbekannte Variante: {wanted}")
    return result


def style_tokens(palette, variant):
    base, state = palette["base"], palette["state"]
    win, view, fg = base["window_bg"], base["view_bg"], base["fg"]
    accent = palette["accents"][variant["accent"]]
    return {
        "window_bg": win,
        "view_bg": view,
        "headerbar_bg": base["headerbar_bg"],
        "sidebar_bg": base["sidebar_bg"],
        "dialog_bg": base["dialog_bg"],
        "popover_bg": base["popover_bg"],
        "fg": fg,
        "fg_dim": over(fg, 0.55, win),
        "fg_disabled": over(fg, 0.4, win),
        "border": over(fg, 0.15, win),
        "border_view": over(fg, 0.10, view),
        "button_bg": over(fg, 0.10, win),
        "button_hover": over(fg, 0.15, win),
        "button_active": over(fg, 0.30, win),
        "entry_bg": over(fg, 0.08, win),
        "card_bg": over(fg, 0.08, win),
        "hover": rgba(fg, 0.07),
        "hover_strong": rgba(fg, 0.12),
        "pressed": rgba(fg, 0.20),
        "popover_hover": over(fg, 0.10, base["popover_bg"]),
        "scroll": over(fg, 0.25, view),
        "scroll_hover": over(fg, 0.40, view),
        "tooltip_bg": mix(win, "#000000", 0.5),
        "accent": accent,
        "accent_hover": mix(accent, "#ffffff", 0.1),
        "accent_active": mix(accent, "#000000", 0.15),
        "accent_text": mix(accent, "#ffffff", 0.4),
        "accent_fg": "#ffffff",
        "selection": rgba(accent, 0.30),
        "selection_solid": over(accent, 0.30, view),
        "focus": over(accent, 0.5, win),
        "success": state["success"],
        "warning": state["warning"],
        "destructive": state["destructive"],
        "success_text": mix(state["success"], "#ffffff", 0.4),
        "warning_text": mix(state["warning"], "#ffffff", 0.4),
        "destructive_text": mix(state["destructive"], "#ffffff", 0.4),
        "asset_dir": f"styles:{variant['style']}/assets",
    }


def fill_template(text, tokens, source):
    def replace(match):
        key = match.group(1)
        if key not in tokens:
            sys.exit(f"{source}: unbekannter Platzhalter @{key}")
        return tokens[key]

    # Der Ausdruck ist gierig: @accent_text wird als Ganzes ersetzt, nicht als @accent + _text.
    return re.sub(r"@([a-z][a-z0-9_]*)", replace, text)


# --- Stil -------------------------------------------------------------------

def build_style(palette, variant, styles_dir):
    tokens = style_tokens(palette, variant)
    src = ROOT / "style"
    name = variant["style"]
    styles_dir.mkdir(parents=True, exist_ok=True)
    for template, target in (("adwaita-dark.qss.in", f"{name}.qss"),
                             ("adwaita-dark_chat.qss.in", f"{name}_chat.qss")):
        text = (src / template).read_text(encoding="utf-8")
        (styles_dir / target).write_text(fill_template(text, tokens, template), encoding="utf-8")
    assets = styles_dir / name / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for asset in sorted((src / "assets").glob("*.svg.in")):
        text = asset.read_text(encoding="utf-8")
        (assets / asset.name.removesuffix(".in")).write_text(
            fill_template(text, tokens, asset.name), encoding="utf-8")


# --- Icons ------------------------------------------------------------------

def source_path(spec):
    kind, _, name = spec.partition(":")
    if kind == "a":
        path = PAPIRUS_DARK / "actions" / f"{name}.svg"
    elif kind == "s":
        path = PAPIRUS_SYMBOLIC / f"{name}-symbolic.svg"
    elif kind == "d":
        path = PAPIRUS_DARK / "devices" / f"{name}.svg"
    elif kind == "p":
        path = PAPIRUS_DARK / "places" / f"{name}.svg"
    elif kind == "m":
        path = PAPIRUS_DARK / "emotes" / f"{name}.svg"
    else:
        raise ValueError(f"Unbekannte Quelle: {spec}")
    if not path.exists():
        raise FileNotFoundError(f"{spec} → {path}")
    return path.resolve()


def view_box(root):
    if "viewBox" in root.attrib:
        return [float(v) for v in root.attrib["viewBox"].replace(",", " ").split()]
    width = float(root.attrib.get("width", "16").removesuffix("px"))
    height = float(root.attrib.get("height", "16").removesuffix("px"))
    return [0.0, 0.0, width, height]


def recolor(path, color, roles, solid=False):
    """Liest ein Papirus-SVG und setzt alle Farben fest ein.

    solid entfernt Papirus' Halbtransparenz, etwa bei den Stumm-Symbolen,
    die im Kanalbaum sonst kaum zu sehen sind.
    """
    root = ET.parse(path).getroot()
    for parent in list(root.iter()):
        for child in list(parent):
            if child.tag in (f"{{{SVG_NS}}}style", f"{{{SVG_NS}}}title", f"{{{SVG_NS}}}metadata"):
                parent.remove(child)
    for el in root.iter():
        role_color = color
        for cls in el.attrib.pop("class", "").split():
            if cls in CLASS_ROLES:
                role = CLASS_ROLES[cls]
                role_color = color if role == "main" else roles[role]
                break
        for attr in ("style", "fill", "stroke"):
            value = el.attrib.get(attr)
            if value is None:
                continue
            value = value.replace("currentColor", role_color)
            value = value.replace(PAPIRUS_DARK_TEXT, color).replace(PAPIRUS_DARK_TEXT.upper(), color)
            if solid and attr == "style":
                value = re.sub(r"(?<![-\w])opacity\s*:\s*[^;]+;?", "", value)
            el.attrib[attr] = value
        if solid:
            el.attrib.pop("opacity", None)
    children = [c for c in root if not (c.tag == f"{{{SVG_NS}}}defs" and len(c) == 0)]
    return children, view_box(root)


def placed(children, box, x, y, size):
    min_x, min_y, width, _ = box
    scale = size / width
    steps = []
    if x or y:
        steps.append(f"translate({x:g},{y:g})")
    if scale != 1:
        steps.append(f"scale({scale:g})")
    if min_x or min_y:
        steps.append(f"translate({-min_x:g},{-min_y:g})")
    group = ET.Element(f"{{{SVG_NS}}}g", {"transform": " ".join(steps)} if steps else {})
    group.extend(children)
    return group


def svg_elements(markup):
    root = ET.fromstring(f'<svg xmlns="{SVG_NS}">{markup}</svg>')
    return list(root)


def star_points(cx, cy, outer, inner):
    points = []
    for i in range(10):
        radius = outer if i % 2 == 0 else inner
        angle = math.pi / 5 * i - math.pi / 2
        points.append(f"{cx + radius * math.cos(angle):.2f},{cy + radius * math.sin(angle):.2f}")
    return " ".join(points)


BUBBLE_PATH = ("M4,2.5 H12 A2.5,2.5 0 0 1 14.5,5 V9 A2.5,2.5 0 0 1 12,11.5 H7.5 "
               "L4,14.5 V11.5 A2.5,2.5 0 0 1 1.5,9 V5 A2.5,2.5 0 0 1 4,2.5 Z")


def halo(color):
    return (f'<circle cx="8" cy="8" r="7" fill="none" stroke="{color}" '
            f'stroke-width="1.5" stroke-opacity="0.45"/>')


def bubble(color, outline):
    if outline:
        return (f'<path d="{BUBBLE_PATH}" fill="none" stroke="{color}" '
                f'stroke-width="1.5" stroke-linejoin="round"/>')
    return f'<path d="{BUBBLE_PATH}" fill="{color}"/>'


def shape(name, color):
    """Eigene Formen für TS-Begriffe ohne Gegenstück in Papirus. Liefert (Elemente, viewBox)."""
    if name == "dot":
        markup = f'<circle cx="8" cy="8" r="4.5" fill="{color}"/>'
    elif name == "dot-talking":
        markup = f'<circle cx="8" cy="8" r="4.5" fill="{color}"/>' + halo(color)
    elif name == "ring-talking":
        markup = (f'<circle cx="8" cy="8" r="3.75" fill="none" stroke="{color}" stroke-width="1.5"/>'
                  f'<circle cx="8" cy="8" r="1.5" fill="{color}"/>' + halo(color))
    elif name == "small-dot":
        markup = f'<circle cx="8" cy="8" r="3" fill="{color}"/>'
    elif name == "star":
        markup = f'<polygon points="{star_points(8, 8.4, 6.5, 2.8)}" fill="{color}"/>'
    elif name == "star-talking":
        markup = f'<polygon points="{star_points(8, 8.4, 5.2, 2.3)}" fill="{color}"/>' + halo(color)
    elif name in ("bubble", "bubble-outline"):
        markup = bubble(color, name.endswith("outline"))
    elif name in ("bubbles", "bubbles-outline"):
        outline = name.endswith("outline")
        markup = (f'<g transform="translate(5.5,0) scale(0.66)" opacity="0.6">{bubble(color, True)}</g>'
                  f'<g transform="translate(0,3.5) scale(0.78)">{bubble(color, outline)}</g>')
    elif name.startswith("letter-"):
        letter = name.removeprefix("letter-")
        markup = (f'<rect x="1" y="1" width="14" height="14" rx="3.5" fill="{color}"/>'
                  f'<text x="8" y="12" fill="#ffffff" font-family="Noto Sans, sans-serif" '
                  f'font-weight="bold" font-size="11" text-anchor="middle">{letter}</text>')
    else:
        raise ValueError(f"Unbekannte Form: {name}")
    return svg_elements(markup), [0.0, 0.0, 16.0, 16.0]


def resolve(spec, color, roles, solid=False):
    if spec.startswith("shape:"):
        return shape(spec.removeprefix("shape:"), color)
    return recolor(source_path(spec), color, roles, solid)


def icon_roles(palette, accent):
    base, state = palette["base"], palette["state"]
    roles = {
        "fg": base["icon_fg"],
        "dim": mix(base["icon_fg"], base["view_bg"], 0.55),
        "accent": accent,
        "success": state["success"],
        "warning": state["warning"],
        "destructive": state["destructive"],
        "away": state["away"],
    }
    for name, value in palette["groups"].items():
        roles[f"group:{name}"] = value
    return roles


def render_icon(entry, roles, glyph_color):
    color = roles[entry.get("color", "fg")]
    svg = ET.Element(f"{{{SVG_NS}}}svg", {"width": "16", "height": "16", "viewBox": "0 0 16 16"})
    children, box = resolve(entry["src"], color, roles, entry.get("solid", False))
    svg.append(placed(children, box, 0, 0, 16))
    if "badge" in entry:
        badge_color = roles[entry.get("badge_color", "fg")]
        # Abzeichen wie GNOME-Embleme: farbige Scheibe, dunkles Symbol darauf.
        svg.extend(svg_elements(f'<circle cx="12" cy="12" r="4.25" fill="{badge_color}"/>'))
        if entry["badge"] != "shape:small-dot":
            glyph, glyph_box = resolve(entry["badge"], glyph_color, roles)
            svg.append(placed(glyph, glyph_box, 8.75, 8.75, 6.5))
    ET.indent(svg)
    return ET.tostring(svg, encoding="unicode") + "\n"


def reference_keys():
    if not TS3_REFERENCE_PACK.exists():
        return None
    with zipfile.ZipFile(TS3_REFERENCE_PACK) as z:
        text = z.read("settings.ini").decode("utf-8", "replace")
    keys, active = set(), False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            active = line == "[gfxfiles]"
        elif active and line and not line.startswith("#") and "=" in line:
            keys.add(line.split("=", 1)[0].strip())
    return keys


def build_iconpack(palette, mapping, variant, gfx_dir, staging_dir):
    """Rendert ein Iconpack nach staging_dir/<Name>/ und packt es als gfx_dir/<Name>.zip.

    TS3 3.6 lädt Iconpacks nur als Zip-Archiv, ein Ordner gleichen Namens wird verworfen.
    """
    roles = icon_roles(palette, palette["accents"][variant["accent"]])
    glyph_color = palette["base"]["view_bg"]
    target = staging_dir / variant["iconpack"]
    if target.exists():
        shutil.rmtree(target)
    (target / "emoticons").mkdir(parents=True)

    lines = ["[info]", f"# {variant['iconpack']} – erzeugt von ts3-adwaita-theme {VERSION}, nicht von Hand ändern.",
             "", "[options]", "FALLBACK=true", "PLACEHOLDER=0", "", "[gfxfiles]"]
    for key, entry in mapping["icons"].items():
        filename = f"{key.lower()}.svg"
        (target / filename).write_text(render_icon(entry, roles, glyph_color), encoding="utf-8")
        lines.append(f"{key:<34} = {filename}")
    (target / "settings.ini").write_text("\n".join(lines) + "\n", encoding="utf-8")

    emoticon_lines = []
    for filename, entry in mapping["emoticons"].items():
        (target / "emoticons" / filename).write_text(
            render_icon({"src": entry["src"]}, roles, glyph_color), encoding="utf-8")
        emoticon_lines += [f'{filename} = "{code}"' for code in entry["codes"]]
    (target / "emoticons" / "emoticons.txt").write_text("\n".join(emoticon_lines) + "\n", encoding="utf-8")

    gfx_dir.mkdir(parents=True, exist_ok=True)
    archive = gfx_dir / f"{variant['iconpack']}.zip"
    # Erst daneben schreiben, dann ersetzen: ein laufender TS3 sieht nie ein halbes Archiv.
    partial = archive.with_suffix(".zip.part")
    zip_dir(target, partial)
    os.replace(partial, archive)


def check_keys(mapping):
    expected = reference_keys()
    if expected is None:
        print("Hinweis: kein TS3-Referenzpaket gefunden, Schlüsselabgleich übersprungen.")
        return
    mapped = set(mapping["icons"])
    missing, unknown = sorted(expected - mapped), sorted(mapped - expected)
    print(f"Icon-Schlüssel: {len(mapped & expected)}/{len(expected)} belegt.")
    if missing:
        print("  Unbelegt (TS nimmt dafür default.zip):", ", ".join(missing))
    if unknown:
        print("  Unbekannt für TS:", ", ".join(unknown))


# --- Ausgabe ----------------------------------------------------------------

def zip_dir(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(source.rglob("*")):
            z.write(path, path.relative_to(source))


def uninstall(palette, target):
    removed = 0
    for variant in variants(palette, "all", "blue"):
        style = variant["style"]
        for path in (target / "styles" / f"{style}.qss", target / "styles" / f"{style}_chat.qss",
                     target / "gfx" / f"{variant['iconpack']}.zip"):
            if path.exists():
                path.unlink()
                removed += 1
        if (target / "styles" / style).is_dir():
            shutil.rmtree(target / "styles" / style)
            removed += 1
    print(f"{removed} Einträge aus {target} entfernt.")


def validate(directory):
    count = 0
    for path in directory.rglob("*.svg"):
        ET.parse(path)
        count += 1
    if shutil.which("rsvg-convert"):
        for path in directory.rglob("*.svg"):
            subprocess.run(["rsvg-convert", "-w", "16", str(path)], check=True,
                           stdout=subprocess.DEVNULL)
    return count


def config_dir(args):
    if args.config_dir:
        return Path(args.config_dir).expanduser()
    return Path(os.environ.get("TS3_CONFIG_DIR", Path.home() / ".ts3client"))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variant", default="all",
                        help="all (Standard), system oder ein Akzent: blue, teal, …, maia")
    parser.add_argument("--accent", help="Akzent der System-Variante festlegen statt gsettings zu fragen")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--install", action="store_true", help="Varianten ins TS3-Profil schreiben")
    action.add_argument("--uninstall", action="store_true", help="alle Varianten aus dem TS3-Profil entfernen")
    parser.add_argument("--config-dir", help="TS3-Profil (Standard: $TS3_CONFIG_DIR oder ~/.ts3client)")
    args = parser.parse_args()

    palette = load_palette()
    with open(ROOT / "iconpack" / "mapping.toml", "rb") as f:
        mapping = tomllib.load(f)

    if args.install or args.uninstall:
        target = config_dir(args)
        if not target.is_dir():
            sys.exit(f"TS3-Profil nicht gefunden: {target}")
        if args.uninstall:
            uninstall(palette, target)
            return
    else:
        target = BUILD_DIR / "profile"
        if target.exists():
            shutil.rmtree(target)

    staging = BUILD_DIR / "iconpacks"
    for variant in variants(palette, args.variant, args.accent):
        build_style(palette, variant, target / "styles")
        build_iconpack(palette, mapping, variant, target / "gfx", staging)
        print(f"{variant['style']} + {variant['iconpack']} ({variant['accent']}) → {target}")

    if not args.install:
        check_keys(mapping)
        count = validate(target / "styles") + validate(staging)
        print(f"{count} SVG-Dateien geprüft.")


if __name__ == "__main__":
    main()

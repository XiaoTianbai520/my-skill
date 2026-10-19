#!/usr/bin/env python3
"""generate_plantuml.py — Convert PlantUML source to SVG, PNG, PDF, or ASCII art.

Unified cross-platform (Linux / macOS / Windows) replacement for the previous
Bash + PowerShell script pair. Requires only Python 3.8+ from the host; the
rendering backends (Docker yuzutech/kroki, Docker plantuml/plantuml,
local plantuml.jar, opt-in Kroki public server) are unchanged.

Usage:
    python generate_plantuml.py <input.puml> [output_dir] [options]
    python generate_plantuml.py <dir> <output_dir> [options]   (batch render)
    python generate_plantuml.py <file-or-dir> --lint
    python generate_plantuml.py <file-or-dir> --fix

Options:
    --format {svg,png,pdf,txt}   Output format (default: svg)
    --cjk                        Enable CJK (Chinese/Japanese/Korean) font support
    --no-fix                     Disable automatic aspect ratio correction
    --min-aspect N               Min width/height ratio before correction (default: 0.7)
    --max-aspect N               Max width/height ratio before correction (default: 1.4)
    --dark-mode                  Also emit <basename>.dark.<fmt> companion
    --no-a4-check                Disable automatic A4 paper fit validation
    --min-font-pt N              Min legible font size on A4 paper (default: 8.0)
    --use-public-server          OPT-IN: render via Kroki (kroki.io by default).
                                 Uploads diagram source to a third party.
                                 Override host via PLANTUML_PUBLIC_SERVER env var.
    --lint                       Compatibility check only — no rendering.
                                 Input may be a single .puml or a directory.
                                 Exit 0 = clean, 1 = errors found (CI-friendly).
    --fix                        Auto-fix compatibility issues in place
                                 (strictuml removal, inline class expansion,
                                 deprecated skinparam → CSS migration).
                                 Originals backed up as *.bak.puml.

Compatibility notes (verified against PlantUML 1.2026.6 via yuzutech/kroki
and plantuml/plantuml Docker images):
    * Single-line class bodies (`class A { +m() }`) are a HARD render failure
      on PlantUML >= 1.2025 — auto-expanded to multi-line at render time.
    * Single-line skinparam element blocks (`skinparam class { A; B }`) are a
      HARD render failure on PlantUML >= 1.2026 — auto-expanded to multi-line
      at render time. This affects older mandatory preambles.
    * `skinparam padding / ParticipantPadding / BoxPadding` are deprecated;
      they still render locally, but the official replacement is the CSS
      <style> block. --fix migrates them (opt-in), --lint flags them.

Privacy notice:
    This script renders LOCALLY by default. Diagram source is NOT transmitted
    off-host unless --use-public-server is passed. Backend priority:
        1. Docker (yuzutech/kroki)      - preferred, local, newer PlantUML
        2. Docker (plantuml/plantuml)   - fallback, local
        3. Native `plantuml` on PATH, or a local plantuml.jar
                                       - offline fallback (jar needs Java;
                                         PLANTUML_JAR env overrides the path)
        4. Kroki public server          - OPT-IN ONLY

    Batch render mode (directory input) reuses ONE kroki container for the
    whole run and exits non-zero if any file fails.
"""
from __future__ import annotations

import argparse
import atexit
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from collections import namedtuple
from pathlib import Path
from typing import List, Optional, Tuple

# The renderer logs status symbols (for example, \U0001f5bc\ufe0f and \u2713).  Windows consoles
# commonly default to a legacy code page such as GBK, which cannot encode them and
# would otherwise abort a render before a backend is invoked.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# A4 paper dimensions in CSS pixels @ 96 DPI (1in = 96px, A4 = 210×297 mm)
A4_PORTRAIT_W = 794
A4_PORTRAIT_H = 1123
A4_LANDSCAPE_W = 1123
A4_LANDSCAPE_H = 794

# Body font size (px) produced by the mandatory uml-diagrams.org preamble
DEFAULT_FONT_PX = 12.0

MAX_FIX_ATTEMPTS = 3

STRICTUML_RE = re.compile(
    r"(?im)^[ \t]*skinparam[ \t]+style[ \t]+strictuml[ \t]*\r?\n?"
)

# Single-line class-family bodies: `class A { +greet() }`.
# PlantUML >= 1.2025 rejects these with a hard syntax error (verified on
# 1.2026.6); the multi-line expansion is semantically identical.
# NOTE: lines inside <style> blocks legitimately use single-line braces
# (`class { BackGroundColor #FFFFFF; ... }`) and are excluded via _style_spans.
INLINE_CLASS_RE = re.compile(
    r"^(?P<indent>[ \t]*)"
    r"(?P<decl>(?:abstract[ \t]+)?(?:class|interface|enum)\b[^{\n]*?)"
    r"[ \t]*\{(?P<body>[^{}\n]+)\}[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)

# Deprecated skinparams → CSS <style> equivalents (official migration path,
# cf. plantuml.com/style-evolution). These still render locally on 1.2026.6
# but plantuml.com servers attach "Please use CSS style instead of skinparam"
# warnings to the rendered output. Verified mappings:
#   skinparam padding N            → root { Padding N }
#   skinparam ParticipantPadding N → sequenceDiagram { participant { Padding N } }
#   skinparam BoxPadding N         → sequenceDiagram { box { Padding N } }
DEPRECATED_SKINPARAMS = {
    "padding": ("root", None, "Padding"),
    "participantpadding": ("sequenceDiagram", "participant", "Padding"),
    "boxpadding": ("sequenceDiagram", "box", "Padding"),
}

DEPRECATED_SKINPARAM_RE = re.compile(
    r"(?im)^[ \t]*skinparam[ \t]+(?P<name>padding|participantpadding|boxpadding)"
    r"[ \t]+(?P<value>[\d.]+)(?:[ \t]+'[^\n\r]*)?[ \t]*\r?\n?"
)

# Single-line skinparam element blocks: `skinparam class { A #FFF; B #000 }`.
# PlantUML >= 1.2026.x rejects braces on one line for skinparam COMMANDS with
# a hard syntax error (verified on 1.2026.6 via yuzutech/kroki AND
# plantuml/plantuml Docker images). Semicolons are legal INSIDE the block —
# only the single-line brace form fails. The multi-line expansion is
# semantically identical.
INLINE_SKINPARAM_BLOCK_RE = re.compile(
    r"^(?P<indent>[ \t]*)skinparam[ \t]+(?P<elem>\w+)[ \t]*"
    r"\{(?P<body>[^{}\n]+)\}[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)

# Generated artifacts that lint/fix directory scans must skip
ARTIFACT_SUFFIXES = (".bak.puml", ".fixed.puml", ".a4fixed.puml", ".cjk.puml")

CJK_RANGES = (
    (0x4E00, 0x9FFF),
    (0x3400, 0x4DBF),
    (0x20000, 0x2A6DF),
    (0xF900, 0xFAFF),
    (0x2F800, 0x2FA1F),
    (0x3000, 0x303F),
    (0xFF00, 0xFFEF),
    (0x3040, 0x309F),
    (0x30A0, 0x30FF),
    (0xAC00, 0xD7AF),
)

SPACING_GUARD_BLOCK = """<style>
root {
  padding 8
  wrapWidth 220
}
activityDiagram {
  activity { padding 8 }
}
sequenceDiagram {
  participant { padding 8 }
  box { padding 8 }
}
classDiagram {
  class { padding 8; MinimumWidth 100 }
}
stateDiagram {
  state { padding 8 }
}
</style>
"""

BARE_STROKE_CSS = """<style>@media (prefers-color-scheme: light) {
/* Bare elements: PlantUML CSS mode may omit stroke on some shapes */
ellipse:not([style*="stroke"]):not([stroke]),
circle:not([style*="stroke"]):not([stroke]) {
 stroke: #000000 !important;
 stroke-width: 0.75 !important;
}
rect[fill="#FFFFFF"]:not([style*="stroke"]):not([stroke]),
rect[fill="#ffffff"]:not([style*="stroke"]):not([stroke]) {
 stroke: #000000 !important;
 stroke-width: 0.75 !important;
}
path[fill="none"]:not([style*="stroke"]):not([stroke]) {
 stroke: #000000 !important;
 stroke-width: 0.75 !important;
}
/* Swimlane headers rendered with white stroke (invisible on white canvas) */
[style*="stroke:#FFFFFF"], [style*="stroke: #FFFFFF"],
[style*="stroke:#ffffff"], [style*="stroke: #ffffff"] {
 stroke: #000000 !important;
}
}</style>"""

DARK_MODE_CSS = """<style>@media (prefers-color-scheme: dark) {
 svg {
 background: transparent !important;
 }
 [style*="background:#FFFFFF"], [style*="background: #FFFFFF"],
 [style*="background:#ffffff"], [style*="background: #ffffff"] {
 background: #1e1e2e !important;
 }
 [fill="#FFFFFF"], [fill="#ffffff"], [fill="#FFF"], [fill="#fff"],
 [fill="#FEFEFE"], [fill="#fefefe"], [fill="#F1F1F1"], [fill="#f1f1f1"],
 [fill="#EEEEEE"], [fill="#eeeeee"], [fill="#ECECEC"], [fill="#ececec"],
 [fill="#FFFFCC"], [fill="#ffffcc"] {
 fill: #1e1e2e !important;
 }
 /* Use case ellipses/circles: transparent fill so outline visible */
 ellipse[fill="#FFFFFF"], ellipse[fill="#ffffff"],
 ellipse[fill="#FFF"], ellipse[fill="#fff"],
 ellipse[fill="#FEFEFE"], ellipse[fill="#fefefe"],
 ellipse[style*="fill:#FFFFFF"], ellipse[style*="fill:#ffffff"],
 circle[fill="#FFFFFF"], circle[fill="#ffffff"],
 circle[fill="#FFF"], circle[fill="#fff"],
 circle[fill="#FEFEFE"], circle[fill="#fefefe"],
 circle[style*="fill:#FFFFFF"], circle[style*="fill:#ffffff"] {
 fill: none !important;
 stroke-width: 1.5 !important;
 }
 [stroke="#000000"], [stroke="#000"], [stroke="#181818"],
 [stroke="#222222"], [stroke="#222"], [stroke="#333333"], [stroke="#333"] {
 stroke: #c9d1d9 !important;
 }
 [style*="stroke:#181818"], [style*="stroke: #181818"],
 [style*="stroke:#000000"], [style*="stroke: #000000"],
 [style*="stroke:#222222"], [style*="stroke: #222222"],
 [style*="stroke:#333333"], [style*="stroke: #333333"] {
 stroke: #c9d1d9 !important;
 }
 [style*="stroke:#FFDD88"], [style*="stroke: #FFDD88"],
 [style*="stroke:#ffdd88"], [style*="stroke: #ffdd88"] {
 stroke: #6e7681 !important;
 }
 text, [fill="#000000"], [fill="#000"], [fill="#181818"], [fill="#222222"] {
 fill: #c9d1d9 !important;
 }
 polygon[fill="#000000"], polygon[fill="#181818"], polygon[fill="#222222"],
 polygon[fill="#333333"] {
 fill: #c9d1d9 !important;
 stroke: #c9d1d9 !important;
 }
 rect[style*="stroke:#000000"], rect[style*="stroke: #000000"],
 rect[style*="stroke:#181818"], rect[style*="stroke: #181818"] {
 stroke: #c9d1d9 !important;
 }
 ellipse[style*="stroke:#000000"], ellipse[style*="stroke: #000000"],
 ellipse[style*="stroke:#181818"], ellipse[style*="stroke: #181818"] {
 stroke: #c9d1d9 !important;
 }
 polygon[style*="stroke:#000000"], polygon[style*="stroke: #000000"],
 polygon[style*="stroke:#181818"], polygon[style*="stroke: #181818"],
 polygon[style*="stroke:#222222"], polygon[style*="stroke: #222222"] {
 stroke: #c9d1d9 !important;
 }
 line[stroke="#181818"], line[stroke="#000000"],
 line[style*="stroke:#181818"], line[style*="stroke: #181818"],
 line[style*="stroke:#000000"], line[style*="stroke: #000000"] {
 stroke: #6e7681 !important;
 stroke-dasharray: 4 3 !important;
 }
 text[font-weight="700"], text[font-weight="bold"] {
 fill: #f0f6fc !important;
 }
  /* Bare elements: PlantUML CSS mode may omit stroke on some shapes */
  ellipse:not([style*="stroke"]):not([stroke]),
  circle:not([style*="stroke"]):not([stroke]) {
  stroke: #c9d1d9 !important;
  stroke-width: 0.75 !important;
  }
  rect[fill="#FFFFFF"]:not([style*="stroke"]):not([stroke]),
  rect[fill="#ffffff"]:not([style*="stroke"]):not([stroke]) {
  stroke: #c9d1d9 !important;
  stroke-width: 0.75 !important;
  }
  path[fill="none"]:not([style*="stroke"]):not([stroke]) {
  stroke: #c9d1d9 !important;
  stroke-width: 0.75 !important;
  }
  /* Swimlane headers rendered with white stroke (invisible on dark canvas) */
  [style*="stroke:#FFFFFF"], [style*="stroke: #FFFFFF"],
  [style*="stroke:#ffffff"], [style*="stroke: #ffffff"] {
  stroke: #c9d1d9 !important;
  }
}</style>"""


def log(msg: str = "") -> None:
    print(msg, flush=True)


def elog(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


# ─────────────────────────────────────────────────────────────────────────────
# Source Sanitization (defensive) & Compatibility Migration
# ─────────────────────────────────────────────────────────────────────────────
def sanitize_puml_source(path: Path) -> None:
    """Apply render-time HARD-FAILURE fixes to a .puml working copy.

    1. Strip forbidden `skinparam style strictuml` — it degrades key UML
       shapes (actors→text, use cases→rectangles, class header separator lost).
    2. Expand single-line skinparam element blocks (`skinparam class { A; B }`)
       — PlantUML >= 1.2026.x rejects them with a hard syntax error.
    3. Expand single-line class-family bodies (`class A { +m() }`) —
       PlantUML >= 1.2025 rejects them with a hard syntax error.

    Deprecated-but-working skinparams (padding family) are NOT touched at
    render time: they still render correctly today. Use --lint / --fix to
    migrate them to the official CSS <style> form.
    """
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    new_text, n_strict = STRICTUML_RE.subn("", text)
    new_text, n_spblock = expand_inline_skinparam_blocks(new_text)
    new_text, n_inline = expand_inline_class_bodies(new_text)
    if n_strict or n_spblock or n_inline:
        if n_strict:
            elog(
                "  ⓘ Stripped forbidden 'skinparam style strictuml' "
                "(see SKILL.md → Common Failure Patterns)"
            )
        if n_spblock:
            elog(
                f"  ⓘ Expanded {n_spblock} single-line skinparam block(s) to "
                "multi-line (PlantUML >= 1.2026 rejects `skinparam X { ... }` "
                "on one line; run --fix to update the source file)"
            )
        if n_inline:
            elog(
                f"  ⓘ Expanded {n_inline} single-line class body(ies) to multi-line "
                "(PlantUML >= 1.2025 rejects `class A { ... }` on one line; "
                "run --fix to update the source file)"
            )
        path.write_text(new_text, encoding="utf-8")


def _style_spans(text: str) -> List[Tuple[int, int]]:
    """Return (start, end) spans of <style>...</style> blocks."""
    return [(m.start(), m.end()) for m in re.finditer(r"(?is)<style[^>]*>.*?</style>", text)]


def _iter_inline_class_matches(text: str):
    """Yield INLINE_CLASS_RE matches that are NOT inside <style> blocks."""
    spans = _style_spans(text)
    for m in INLINE_CLASS_RE.finditer(text):
        if any(s <= m.start() < e for s, e in spans):
            continue
        yield m


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _split_class_body(body: str, is_enum: bool) -> List[str]:
    """Split an inline body into members.

    enum literals are comma-separated; class members are semicolon-separated
    (commas legitimately appear inside method signatures, e.g. `+m(a, b)`).
    """
    sep = "," if is_enum else ";"
    return [p.strip() for p in body.split(sep) if p.strip()]


def expand_inline_class_bodies(text: str) -> Tuple[str, int]:
    """Expand single-line class-family bodies to the multi-line form.

    `class A { +greet() }` →
    ```
    class A {
      +greet()
    }
    ```
    Idempotent: the multi-line form never re-matches (braces on separate
    lines). Lines inside <style> blocks are excluded — CSS rules legitimately
    use single-line braces.
    """
    pieces: List[str] = []
    last = 0
    count = 0

    for m in _iter_inline_class_matches(text):
        decl = m.group("decl").rstrip()
        indent = m.group("indent")
        members = _split_class_body(
            m.group("body"), decl.lstrip().lower().startswith("enum")
        )
        if not members:
            continue
        pieces.append(text[last:m.start()])
        inner = indent + "  "
        lines = [decl + " {"]
        lines.extend(inner + mem for mem in members)
        lines.append(indent + "}")
        pieces.append("\n".join(lines))
        last = m.end()
        count += 1

    pieces.append(text[last:])
    return "".join(pieces), count


def expand_inline_skinparam_blocks(text: str) -> Tuple[str, int]:
    """Expand single-line `skinparam X { A; B }` blocks to the multi-line form.

    `skinparam class { BackgroundColor #FFFFFF; BorderColor #000000 }` →
    ```
    skinparam class {
      BackgroundColor #FFFFFF
      BorderColor #000000
    }
    ```
    PlantUML >= 1.2026.x rejects the single-line brace form with a hard
    syntax error; semicolons inside a multi-line block are legal, but each
    property on its own line matches the canonical form. Idempotent.
    """
    pieces: List[str] = []
    last = 0
    count = 0

    for m in INLINE_SKINPARAM_BLOCK_RE.finditer(text):
        elem = m.group("elem")
        indent = m.group("indent")
        props = [p.strip() for p in m.group("body").split(";") if p.strip()]
        if not props:
            continue
        pieces.append(text[last:m.start()])
        inner = indent + "  "
        lines = [f"{indent}skinparam {elem} {{"]
        lines.extend(inner + prop for prop in props)
        lines.append(indent + "}")
        pieces.append("\n".join(lines))
        last = m.end()
        count += 1

    pieces.append(text[last:])
    return "".join(pieces), count


def migrate_deprecated_skinparams(text: str) -> Tuple[str, int]:
    """Convert deprecated padding-family skinparams to CSS <style>.

    The deprecated lines are removed and one consolidated <style> block is
    injected right after @startuml (multiple <style> blocks are legal).
    Idempotent: once migrated, the skinparam lines no longer exist.
    """
    found: dict = {}

    def _sub(m) -> str:
        name = m.group("name").lower()
        scope, selector, prop = DEPRECATED_SKINPARAMS[name]
        found[(scope, selector, prop)] = m.group("value")
        return ""

    new_text = DEPRECATED_SKINPARAM_RE.sub(_sub, text)
    if not found:
        return new_text, 0

    lines = ["<style>"]
    root_val = found.get(("root", None, "Padding"))
    if root_val is not None:
        lines += ["root {", f"  Padding {root_val}", "}"]
    seq_vals = {
        sel: val for (scope, sel, _prop), val in found.items()
        if scope == "sequenceDiagram"
    }
    if seq_vals:
        lines += ["sequenceDiagram {"]
        for sel in ("participant", "box"):
            if sel in seq_vals:
                lines += [f"  {sel} {{", f"    Padding {seq_vals[sel]}", "  }"]
        lines += ["}"]
    lines += ["</style>"]
    css_block = "\n".join(lines)

    if re.search(r"(?m)^@start\w+", new_text):
        new_text = re.sub(
            r"(?m)^(?P<start>@start\w+.*)$",
            lambda m: m.group("start") + "\n" + css_block,
            new_text,
            count=1,
        )
    else:
        new_text = css_block + "\n\n" + new_text
    return new_text, len(found)


# ─────────────────────────────────────────────────────────────────────────────
# CJK Detection & Font Substitution
# ─────────────────────────────────────────────────────────────────────────────
def _contains_cjk(text: str) -> bool:
    for ch in text:
        cp = ord(ch)
        for lo, hi in CJK_RANGES:
            if lo <= cp <= hi:
                return True
    return False


def detect_cjk(path: Path) -> bool:
    try:
        return _contains_cjk(path.read_text(encoding="utf-8", errors="ignore"))
    except OSError:
        return False


# CJK font candidates in priority order: (family name, file names to probe).
# The first family whose file exists on the host wins; if none is found the
# first family is still requested (Docker backends may provide it themselves).
CJK_FONT_CANDIDATES: List[Tuple[str, Tuple[str, ...]]] = [
    ("Noto Sans CJK SC", (
        "NotoSansCJK-Regular.ttc", "NotoSansCJKsc-Regular.otf",
        "NotoSansSC-Regular.otf", "NotoSansSC-Regular.ttf",
    )),
    ("WenQuanYi Micro Hei", ("wqy-microhei.ttc", "wqy-zenhei.ttc")),
    ("SimHei", ("simhei.ttf",)),
    ("Microsoft YaHei", ("msyh.ttc", "msyh.ttf")),
    ("PingFang SC", ("PingFangSC-Regular.otf", "PingFang.ttf")),
]


def _font_search_dirs() -> List[Path]:
    """Platform font directories that exist on this host."""
    raw: List[Optional[Path]] = []
    windir = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
    if windir:
        raw.append(Path(windir) / "Fonts")
    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        raw.append(Path(localappdata) / "Microsoft" / "Windows" / "Fonts")
    for d in (
        "/usr/share/fonts",
        "/usr/local/share/fonts",
        os.path.expanduser("~/.fonts"),
        os.path.expanduser("~/.local/share/fonts"),
        "/System/Library/Fonts",
        "/Library/Fonts",
        os.path.expanduser("~/Library/Fonts"),
    ):
        raw.append(Path(d))
    return [d for d in raw if d is not None and d.is_dir()]


def pick_cjk_font() -> Tuple[str, bool]:
    """Pick the first CJK font family available on this host.

    Returns (family, detected); detected=False means no candidate file was
    found on the host - the family is still returned because a Docker
    backend (e.g. the kroki image ships Noto Sans CJK) may provide it.
    """
    dirs = _font_search_dirs()
    for family, files in CJK_FONT_CANDIDATES:
        for d in dirs:
            for name in files:
                if (d / name).is_file():
                    return family, True
    return CJK_FONT_CANDIDATES[0][0], False


def prepare_puml_for_cjk(src: Path, family: str) -> Path:
    """Rewrite font references in a working copy for CJK rendering.

    Updates legacy `skinparam defaultFontName ...` input when present and the
    `FontName ...` lines inside CSS <style> blocks. If no style block exists,
    inject a minimal pure-CSS root rule.
    """
    dst = src.with_suffix(src.suffix + ".cjk.puml")
    text = src.read_text(encoding="utf-8", errors="replace")
    text = re.sub(
        r"skinparam\s+defaultFontName\s+\S+.*",
        f'skinparam defaultFontName "{family}"',
        text,
    )

    def _sub_style_font(m: "re.Match") -> str:
        body = re.sub(
            r"(?m)^(\s*FontName\s+).+$",
            lambda fm: fm.group(1) + f'"{family}"',
            m.group(2),
        )
        return m.group(1) + body + m.group(3)

    text = re.sub(
        r"(<style>)(.*?)(</style>)",
        _sub_style_font,
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    if "<style>" not in text.lower():
        text = re.sub(
            r"(?m)^(@start\w+)",
            lambda m: f'{m.group(1)}\n<style>\nroot {{ FontName "{family}" }}\n</style>',
            text,
            count=1,
        )
    dst.write_text(text, encoding="utf-8")
    return dst


def validate_cjk_svg_font(svg: Path, family: str) -> None:
    """Warn when a --cjk SVG output does not reference the chosen font."""
    try:
        head = svg.read_text(encoding="utf-8", errors="ignore")[:40000]
    except OSError:
        return
    if "font-family" in head and family not in head:
        log(f"  ⚠ CJK check: output SVG does not reference '{family}'")
        log("    CJK glyphs may render as boxes - check font installation on the backend")


# ─────────────────────────────────────────────────────────────────────────────
# Lint & Fix (P0 compatibility tooling)
# ─────────────────────────────────────────────────────────────────────────────
LintIssue = namedtuple("LintIssue", ["severity", "line", "message", "fix_hint"])

SEVERITY_ICON = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}


def lint_puml_source(text: str) -> List[LintIssue]:
    """Analyze .puml source for PlantUML 1.2026.x compatibility issues."""
    issues: List[LintIssue] = []

    for m in STRICTUML_RE.finditer(text):
        issues.append(LintIssue(
            "error", _line_of(text, m.start()),
            "skinparam style strictuml degrades UML shapes "
            "(actors→text, use cases→rectangles, class header separator lost)",
            "remove the line (auto-fixable via --fix)",
        ))

    for m in INLINE_SKINPARAM_BLOCK_RE.finditer(text):
        snippet = m.group(0).strip()
        if len(snippet) > 60:
            snippet = snippet[:57] + "..."
        issues.append(LintIssue(
            "error", _line_of(text, m.start()),
            f"single-line skinparam block `{snippet}` — hard render failure "
            "on PlantUML >= 1.2026",
            "expand to multi-line (auto-fixable via --fix)",
        ))

    for m in _iter_inline_class_matches(text):
        snippet = m.group(0).strip()
        if len(snippet) > 60:
            snippet = snippet[:57] + "..."
        issues.append(LintIssue(
            "error", _line_of(text, m.start()),
            f"single-line class body `{snippet}` — hard render failure "
            "on PlantUML >= 1.2025",
            "expand to multi-line (auto-fixable via --fix)",
        ))

    for m in DEPRECATED_SKINPARAM_RE.finditer(text):
        name = m.group("name")
        scope, selector, _prop = DEPRECATED_SKINPARAMS[name.lower()]
        target = scope if selector is None else f"{scope} {selector}"
        issues.append(LintIssue(
            "warning", _line_of(text, m.start()),
            f"deprecated skinparam `{name}` — PlantUML servers may attach "
            "'Please use CSS style' warnings to the output",
            f"migrate to CSS `{target} {{ Padding ... }}` (auto-fixable via --fix)",
        ))

    starts = re.findall(r"(?m)^\s*@start\w+", text)
    ends = re.findall(r"(?m)^\s*@end\w+", text)
    if len(starts) != len(ends):
        issues.append(LintIssue(
            "error", 0,
            f"unpaired @start/@end directives "
            f"({len(starts)} start vs {len(ends)} end)",
            "balance the directives",
        ))

    if _contains_cjk(text):
        issues.append(LintIssue(
            "info", 0,
            "CJK characters present — render with --cjk for correct font handling",
            "",
        ))

    return issues


def collect_puml_inputs(input_path: Path) -> List[Path]:
    """Resolve lint/fix inputs: a single file, or all .puml under a directory.

    Generated artifacts (*.bak.puml, *.fixed.puml, *.a4fixed.puml,
    *.cjk.puml) are excluded from directory scans.
    """
    if input_path.is_dir():
        return sorted(
            p for p in input_path.rglob("*.puml")
            if not p.name.lower().endswith(ARTIFACT_SUFFIXES)
        )
    if input_path.is_file():
        return [input_path]
    return []


def run_lint(paths: List[Path]) -> int:
    """Print a compatibility report. Exit 0 = clean, 1 = errors found."""
    total_errors = 0
    total_warnings = 0

    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            print(f"\n📋 {path}")
            print(f"  ❌ cannot read file: {e}")
            total_errors += 1
            continue

        issues = lint_puml_source(text)
        print(f"\n📋 {path}")
        if not issues:
            print("  ✓ no compatibility issues found")
            continue
        for issue in issues:
            line_part = f"line {issue.line}: " if issue.line else ""
            print(f"  {SEVERITY_ICON[issue.severity]} {line_part}{issue.message}")
            if issue.fix_hint:
                print(f"      fix: {issue.fix_hint}")
        total_errors += sum(1 for i in issues if i.severity == "error")
        total_warnings += sum(1 for i in issues if i.severity == "warning")

    print(
        f"\nLint summary: {total_errors} error(s), {total_warnings} warning(s) "
        f"across {len(paths)} file(s)"
    )
    if total_warnings and not total_errors:
        print("(warnings do not fail the lint; run --fix to migrate them)")
    return 1 if total_errors else 0


def run_fix(paths: List[Path]) -> int:
    """Apply compatibility fixes in place. Originals backed up as *.bak.puml."""
    fixed_files = 0

    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            print(f"\n🔧 {path}")
            print(f"  ❌ cannot read file: {e}")
            continue

        new_text, n_strict = STRICTUML_RE.subn("", text)
        new_text, n_spblock = expand_inline_skinparam_blocks(new_text)
        new_text, n_inline = expand_inline_class_bodies(new_text)
        new_text, n_dep = migrate_deprecated_skinparams(new_text)

        if new_text == text:
            print(f"✓ {path} — already clean")
            continue

        backup = path.with_name(path.stem + ".bak.puml")
        if not backup.exists():
            shutil.copy2(path, backup)
            print(f"  ↳ backup saved: {backup}")

        path.write_text(new_text, encoding="utf-8")
        notes = []
        if n_strict:
            notes.append(f"stripped {n_strict} strictuml line(s)")
        if n_spblock:
            notes.append(f"expanded {n_spblock} inline skinparam block(s)")
        if n_inline:
            notes.append(f"expanded {n_inline} inline class body(ies)")
        if n_dep:
            notes.append(f"migrated {n_dep} deprecated skinparam(s) to CSS")
        print(f"🔧 {path} — {', '.join(notes)}")
        fixed_files += 1

    print(f"\nFix summary: {fixed_files}/{len(paths)} file(s) modified")
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# Dimension Detection
# ─────────────────────────────────────────────────────────────────────────────
def get_svg_dimensions(svg: Path) -> Optional[Tuple[int, int]]:
    if not svg.is_file():
        return None
    try:
        # SVGs from PlantUML have viewBox near the top; read a bounded chunk
        with svg.open("r", encoding="utf-8", errors="ignore") as fh:
            head = fh.read(4096)
    except OSError:
        return None
    m = re.search(r'viewBox="([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)"', head)
    if not m:
        return None
    try:
        w = int(float(m.group(3)))
        h = int(float(m.group(4)))
    except ValueError:
        return None
    if w <= 0 or h <= 0:
        return None
    return w, h


def get_png_dimensions(png: Path) -> Optional[Tuple[int, int]]:
    """Read width/height from PNG IHDR — no ImageMagick required."""
    if not png.is_file():
        return None
    try:
        with png.open("rb") as fh:
            header = fh.read(24)
        if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        # IHDR: bytes 16..24 are width (BE u32) + height (BE u32)
        w, h = struct.unpack(">II", header[16:24])
        if w <= 0 or h <= 0:
            return None
        return int(w), int(h)
    except (OSError, struct.error):
        return None


def get_dimensions(img: Path, fmt: str) -> Optional[Tuple[int, int]]:
    if fmt == "svg":
        return get_svg_dimensions(img)
    if fmt == "png":
        return get_png_dimensions(img)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Aspect Ratio Validation & Auto-Fix
# ─────────────────────────────────────────────────────────────────────────────
def check_aspect_ratio(
    img: Path, fmt: str, min_aspect: float, max_aspect: float
) -> Tuple[Optional[str], Optional[Tuple[int, int]]]:
    """Return (problem, (w, h)) where problem ∈ {'ok', 'too_tall', 'too_wide', None}.

    None means dimensions could not be determined.
    """
    dims = get_dimensions(img, fmt)
    if dims is None:
        return None, None
    w, h = dims
    ratio = w / h
    log(
        f"  📐 Dimensions: {w}x{h}, width/height ratio: {ratio:.2f} "
        f"(target {min_aspect}–{max_aspect})"
    )
    if ratio < min_aspect:
        log(f"  ⚠ Aspect ratio {ratio:.2f} is below minimum {min_aspect} — diagram is too tall")
        return "too_tall", dims
    if ratio > max_aspect:
        log(f"  ⚠ Aspect ratio {ratio:.2f} exceeds maximum {max_aspect} — diagram is too wide")
        return "too_wide", dims
    return "ok", dims


def guess_diagram_type(text: str) -> str:
    if re.search(r"(?m)^\s*(start|stop)\s*$", text) or re.search(r"(?m)^\s*:[^;]+;", text):
        return "activity"
    if re.search(r"(?m)^\s*state\s+", text):
        return "state"
    if re.search(r"(?m)^\s*participant\s+", text):
        return "sequence"
    return "other"


def fix_puml_aspect_ratio(puml: Path, problem: str) -> Optional[Path]:
    """Inject spacing guards + direction directive; return new puml path.

    Returns None if already fixed or unable to fix.
    """
    elog(f"  → Attempting to fix aspect ratio ({problem})...")
    text = puml.read_text(encoding="utf-8", errors="replace")

    if "!pragma aspectRatioFixed" in text:
        elog("  → Already auto-fixed; skipping further attempts")
        return None

    # Inject pragma + spacing guards right after @startuml
    injection = "\n!pragma aspectRatioFixed\n" + SPACING_GUARD_BLOCK
    text = re.sub(r"^@startuml", "@startuml" + injection, text, count=1, flags=re.MULTILINE)
    elog("  → Applied: CSS spacing guards (padding/wrapWidth/MinimumWidth)")

    diagram_type = guess_diagram_type(text)
    direction_safe = diagram_type not in ("activity", "sequence", "state")

    if direction_safe:
        if problem == "too_tall":
            text = re.sub(r"(?m)^top to bottom direction\s*\r?\n", "", text)
            if "left to right direction" not in text:
                text = _insert_before_enduml(text, "left to right direction")
                elog("  → Applied: left to right direction")
        else:  # too_wide
            text = re.sub(r"(?m)^left to right direction\s*\r?\n", "", text)
            if "top to bottom direction" not in text:
                text = _insert_before_enduml(text, "top to bottom direction")
                elog("  → Applied: top to bottom direction")
    else:
        elog(f"  → Direction change skipped for {diagram_type} diagram; using spacing guards only")

    fixed = puml.with_suffix(puml.suffix + ".fixed.puml")
    # Rename to match previous naming convention: strip .puml then add .fixed.puml
    if puml.suffix == ".puml":
        fixed = puml.with_name(puml.stem + ".fixed.puml")
    fixed.write_text(text, encoding="utf-8")
    return fixed


def _insert_before_enduml(text: str, line: str) -> str:
    if re.search(r"(?m)^@enduml", text):
        return re.sub(r"(?m)^@enduml", line + "\n@enduml", text, count=1)
    return text.rstrip() + "\n" + line + "\n"


# ─────────────────────────────────────────────────────────────────────────────
# A4 Paper Fit Validation & Auto-Scale
# ─────────────────────────────────────────────────────────────────────────────
def check_a4_fit(img: Path, fmt: str) -> Tuple[Optional[bool], float]:
    """Return (fits, required_scale).

    fits=True  → already fits A4 portrait or landscape.
    fits=False → does not fit; required_scale is what to inject.
    fits=None  → could not determine dimensions.
    """
    dims = get_dimensions(img, fmt)
    if dims is None:
        return None, 1.0
    w, h = dims

    fits_portrait = w <= A4_PORTRAIT_W and h <= A4_PORTRAIT_H
    fits_landscape = w <= A4_LANDSCAPE_W and h <= A4_LANDSCAPE_H

    if fits_portrait or fits_landscape:
        log(
            f"  📄 A4 fit: {w}x{h}px fits A4 portrait ({A4_PORTRAIT_W}x{A4_PORTRAIT_H}) "
            f"or landscape ({A4_LANDSCAPE_W}x{A4_LANDSCAPE_H}) ✓"
        )
        return True, 1.0

    sp = min(A4_PORTRAIT_W / w, A4_PORTRAIT_H / h)
    sl = min(A4_LANDSCAPE_W / w, A4_LANDSCAPE_H / h)
    factor = max(sp, sl)
    factor = max(factor, 0.15)
    factor = round(factor, 3)

    log(
        f"  📄 A4 fit: {w}x{h}px exceeds A4 portrait ({A4_PORTRAIT_W}x{A4_PORTRAIT_H}) "
        f"and landscape ({A4_LANDSCAPE_W}x{A4_LANDSCAPE_H})"
    )
    log(
        f"     Required scale to fit: {factor} "
        f"(portrait factor {sp:.3f}, landscape factor {sl:.3f})"
    )
    return False, factor


def fix_puml_a4_fit(puml: Path, factor: float, min_font_pt: float) -> Optional[Path]:
    if factor == 1.0:
        return None
    text = puml.read_text(encoding="utf-8", errors="replace")
    if "!pragma a4FitFixed" in text:
        return None

    text = re.sub(r"^@startuml", "@startuml\n!pragma a4FitFixed", text, count=1, flags=re.MULTILINE)
    # PlantUML supports only one scale directive; drop any existing one first
    text = re.sub(r"(?m)^\s*scale\s+[\d.]+\s*\r?\n", "", text)
    text = text.replace(
        "!pragma a4FitFixed",
        f"!pragma a4FitFixed\nscale {factor}",
        1,
    )

    elog(f"  → Applied: scale {factor} (A4 fit)")

    effective_pt = round(factor * DEFAULT_FONT_PX * 0.75, 1)
    if effective_pt < min_font_pt:
        elog(f"  ⚠ After scaling to {factor}, estimated font ≈ {effective_pt}pt on A4")
        elog(f"    That is below --min-font-pt {min_font_pt} and may be hard to read in print.")
        elog("    Consider splitting into multiple diagrams or abbreviating labels.")
    else:
        elog(f"     Estimated font ≈ {effective_pt}pt on A4 (≥ min {min_font_pt}pt) ✓")

    fixed = puml.with_name(puml.stem + ".a4fixed.puml")
    fixed.write_text(text, encoding="utf-8")
    return fixed


# ─────────────────────────────────────────────────────────────────────────────
# Post-processing (SVG bare strokes / dark-mode)
# ─────────────────────────────────────────────────────────────────────────────
def _inject_after_svg_tag(content: str, block: str) -> str:
    return re.sub(r"(<svg[^>]*>)", r"\1\n" + block.replace("\\", r"\\"), content, count=1)


def postprocess_svg_bare_strokes(svg: Path) -> None:
    try:
        content = svg.read_text(encoding="utf-8", errors="replace")
        content = _inject_after_svg_tag(content, BARE_STROKE_CSS)
        svg.write_text(content, encoding="utf-8")
    except OSError:
        pass


def postprocess_dark_svg(light: Path, dark: Path) -> bool:
    try:
        content = light.read_text(encoding="utf-8", errors="replace")
        content = _inject_after_svg_tag(content, DARK_MODE_CSS)
        dark.write_text(content, encoding="utf-8")
        return True
    except OSError:
        return False


def postprocess_dark_png(light: Path, dark: Path) -> bool:
    convert = which("convert") or which("magick")
    if not convert:
        return False
    # ImageMagick 7 exposes both `magick` and legacy `convert`; use whichever is present.
    if Path(convert).name.lower().startswith("magick") and not Path(convert).name.lower().startswith("convert"):
        base_cmd = [convert, "convert"]
    else:
        base_cmd = [convert]
    args = [
        str(light),
        "-fuzz", "25%", "-fill", "#1A1A1A", "-opaque", "#FFFFFF",
        "-fuzz", "25%", "-fill", "#2D2D2D", "-opaque", "#FAFAFA",
        "-fuzz", "25%", "-fill", "#2D2D2D", "-opaque", "#F1F1F1",
        "-fuzz", "25%", "-fill", "#2D2D2D", "-opaque", "#F2F2F2",
        "-fuzz", "25%", "-fill", "#C0C0C0", "-opaque", "#222222",
        "-fuzz", "25%", "-fill", "#C0C0C0", "-opaque", "#181818",
        "-fuzz", "25%", "-fill", "#E8E8E8", "-opaque", "#000000",
        str(dark),
    ]
    try:
        subprocess.run(base_cmd + args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return dark.is_file()
    except (OSError, subprocess.CalledProcessError):
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Rendering Backends
# ─────────────────────────────────────────────────────────────────────────────
def _docker_mount_path(p: Path) -> str:
    """Return the string Docker expects for `-v <host>:/data` on the current OS."""
    s = str(p.resolve())
    # On Windows, Docker Desktop accepts both `C:\Users\...` and `/c/Users/...`;
    # Docker for Windows CLI also accepts native Windows paths. Passing the
    # native path avoids MSYS path translation surprises.
    return s


def _iter_output_candidate(dir_: Path, exts: Tuple[str, ...], exclude_name: str) -> Optional[Path]:
    for ext in exts:
        for cand in dir_.glob(f"*.{ext}"):
            if cand.name == exclude_name:
                continue
            return cand
    return None


def _cjk_font_mounts() -> List[Tuple[str, str]]:
    """Host font directories to mount read-only into containers for CJK rendering.

    Deduplicated by host path (case-insensitive) AND by guest mount point -
    Windows path-case variants (C:\\WINDOWS\\Fonts vs C:\\Windows\\Fonts)
    must not produce duplicate guest targets ("Duplicate mount point" error).
    """
    mounts: List[Tuple[str, str]] = []
    seen_hosts = set()
    seen_guests = set()

    def _add(host: str, guest: str) -> None:
        hkey = host.lower()
        if hkey in seen_hosts or guest in seen_guests:
            return
        seen_hosts.add(hkey)
        seen_guests.add(guest)
        mounts.append((host, guest))

    for fd in (
        "/usr/share/fonts",
        "/usr/local/share/fonts",
        "/System/Library/Fonts",
    ):
        if Path(fd).is_dir():
            _add(fd, fd)
    # Windows fonts
    windir = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
    for host in (
        f"{windir}\\Fonts" if windir else None,
        "C:\\Windows\\Fonts",
        "/c/Windows/Fonts",
        "/mnt/c/Windows/Fonts",
    ):
        if host and Path(host).is_dir():
            _add(host, "/Windows/Fonts")
    return mounts


def _validate_rendered_output(output_file: Path, fmt: str) -> bool:
    """Sanity-check a rendered artifact by its format signature."""
    try:
        if fmt == "svg":
            head = output_file.read_text(encoding="utf-8", errors="ignore")[:2048]
            return "<svg" in head
        if fmt == "png":
            return get_png_dimensions(output_file) is not None
        if fmt == "txt":
            return output_file.stat().st_size > 0
        if fmt == "pdf":
            with output_file.open("rb") as fh:
                return fh.read(4) == b"%PDF"
    except OSError:
        pass
    return False


def _log_stderr_tail(stderr: bytes, max_lines: int = 6) -> None:
    """Print the last lines of a failed subprocess's stderr for diagnosis."""
    text = stderr.decode("utf-8", "replace").strip()
    if not text:
        return
    for line in text.splitlines()[-max_lines:]:
        log(f"    {line}")


def _log_http_error_body(e: urllib.error.HTTPError, max_chars: int = 400) -> None:
    """Surface the response body of an HTTP error (kroki returns PlantUML error details)."""
    try:
        body = e.read()
    except (OSError, ValueError):
        return
    text = body.decode("utf-8", "replace").strip()
    if not text:
        return
    if len(text) > max_chars:
        text = text[:max_chars] + " ..."
    for line in text.splitlines()[:4]:
        log(f"    {line}")


def _run_docker_render(
    cmd: List[str], env: dict, tmpdir: Path, ext: str, fmt: str,
    src: Path, output_file: Path, label: str,
) -> bool:
    """Run one `docker run` render command; surface the stderr tail on failure."""
    try:
        r = subprocess.run(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except OSError:
        return False
    if r.returncode != 0:
        _log_stderr_tail(r.stderr)
        return False
    gen = _iter_output_candidate(tmpdir, (ext, fmt), src.name)
    if not gen:
        return False
    shutil.move(str(gen), str(output_file))
    log(f"  ✓ Success ({label})")
    return True


def convert_via_docker(
    src: Path, output_file: Path, fmt: str, cjk: bool
) -> bool:
    if not which("docker"):
        log("  → Docker not available, skipping")
        return False

    log("  → Trying Docker (plantuml/plantuml)...")
    ext = "utxt" if fmt == "txt" else fmt

    tmpdir = Path(tempfile.gettempdir()) / f"plantuml_docker_{uuid.uuid4().hex}"
    tmpdir.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(src, tmpdir / src.name)
        mount = _docker_mount_path(tmpdir)

        env = os.environ.copy()
        env.setdefault("MSYS_NO_PATHCONV", "1")

        base = ["docker", "run", "--rm", "-v", f"{mount}:/data"]

        if cjk:
            font_dirs = _cjk_font_mounts()

            if font_dirs:
                for host, guest in font_dirs:
                    base += ["-v", f"{host}:{guest}:ro"]
                cmd = base + [
                    "--entrypoint", "sh",
                    "plantuml/plantuml:latest",
                    "-c", f"fc-cache -f 2>/dev/null; plantuml -t{ext} /data/{src.name}",
                ]
                log("  → CJK mode: mounting host fonts and refreshing font cache")
                if _run_docker_render(cmd, env, tmpdir, ext, fmt, src, output_file, "Docker + CJK"):
                    return True
            else:
                log("  ⚠ CJK mode: no host font directories found. CJK characters may not render correctly.")
                log("    Install CJK fonts on your system (e.g. 'apt install fonts-wqy-zenhei').")

        cmd = base + ["plantuml/plantuml:latest", f"-t{ext}", f"/data/{src.name}"]
        if _run_docker_render(cmd, env, tmpdir, ext, fmt, src, output_file, "Docker"):
            return True
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    log("  ✗ Docker conversion failed")
    return False


def _find_free_port() -> int:
    """Return a free TCP port on localhost."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_for_http(url: str, timeout_s: float = 15.0) -> bool:
    """Poll a URL until it responds or timeout."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except (urllib.error.URLError, OSError, TimeoutError):
            time.sleep(0.3)
    return False


class KrokiSession:
    """A reusable local yuzutech/kroki render container.

    Starting a kroki container costs seconds (image start + HTTP readiness),
    so the aspect-ratio / A4 re-render loop and batch rendering used to pay
    that cost once PER rendered image. A session keeps ONE container alive
    for the whole process; stop() tears it down (also registered via atexit).
    """

    def __init__(self, cjk: bool) -> None:
        self.cjk = cjk
        self.port = 0
        self.container = ""
        self.dead = False
        self.env = os.environ.copy()
        self.env.setdefault("MSYS_NO_PATHCONV", "1")

    def start(self) -> bool:
        if not which("docker"):
            log("  → Docker not available, skipping")
            return False
        log("  → Trying Docker (yuzutech/kroki)...")
        # `docker run` implicitly pulls a missing image.  Rendering is designed
        # to be local-first and has a plantuml/plantuml fallback, so do not make
        # a normal render block on a download when Kroki is not installed.
        try:
            image = subprocess.run(
                ["docker", "image", "inspect", "yuzutech/kroki"],
                env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except OSError:
            return False
        if image.returncode != 0:
            log("  → Kroki image not installed, falling back to the next local backend")
            return False
        self.port = _find_free_port()
        self.container = f"kroki-render-{uuid.uuid4().hex[:8]}"
        cmd = [
            "docker", "run", "-d", "--rm",
            "-p", f"127.0.0.1:{self.port}:8000",
            "--name", self.container,
        ]
        # Mount host CJK font directories read-only (same as plantuml/plantuml path)
        if self.cjk:
            for host, guest in _cjk_font_mounts():
                cmd += ["-v", f"{host}:{guest}:ro"]
            log("  -> CJK mode: mounting host fonts into kroki container")
        cmd += ["yuzutech/kroki"]
        try:
            r = subprocess.run(cmd, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError as e:
            log(f"  ✗ Failed to start kroki container: {e}")
            return False
        if r.returncode != 0:
            log("  ✗ Failed to start kroki container")
            _log_stderr_tail(r.stderr)
            return False
        if not _wait_for_http(f"http://127.0.0.1:{self.port}/"):
            log("  ✗ Kroki container did not become ready in time")
            self.stop()
            return False
        return True

    def render(self, src: Path, output_file: Path, fmt: str) -> bool:
        """POST one .puml to the running container and validate the artifact."""
        ext = "utxt" if fmt == "txt" else fmt
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{self.port}/plantuml/{ext}",
                data=src.read_bytes(),
                method="POST",
                headers={"Content-Type": "text/plain"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = resp.read()
            output_file.write_bytes(payload)
        except urllib.error.HTTPError as e:
            # 4xx/5xx: for HTTP 400 the body carries the PlantUML syntax error
            log(f"  ✗ Kroki returned HTTP {e.code}")
            _log_http_error_body(e)
            return False
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            # Transport-level failure: the container may have died - mark the
            # session dead so the next call can start a fresh one.
            log(f"  ✗ Kroki Docker failed: {e}")
            self.dead = True
            self.stop()
            return False

        if _validate_rendered_output(output_file, fmt):
            log("  ✓ Success (Docker kroki)")
            return True
        log("  ✗ Kroki Docker conversion produced invalid output")
        return False

    def stop(self) -> None:
        if not self.container:
            return
        # The container has --rm, so it auto-removes after the stop
        subprocess.run(
            ["docker", "stop", self.container],
            env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.container = ""


_KROKI_SESSION: Optional[KrokiSession] = None
_KROKI_TRIED = False


def get_kroki_session(cjk: bool) -> Optional[KrokiSession]:
    """Return the shared kroki session, starting the container on first use.

    A failed start is remembered for the rest of the process (no per-file
    retries); a transport-level death mid-process allows one restart.
    """
    global _KROKI_SESSION, _KROKI_TRIED
    if _KROKI_SESSION is not None and _KROKI_SESSION.dead:
        shutdown_kroki_session()
        _KROKI_TRIED = False
    if _KROKI_SESSION is None and not _KROKI_TRIED:
        _KROKI_TRIED = True
        session = KrokiSession(cjk)
        if session.start():
            _KROKI_SESSION = session
    return _KROKI_SESSION


def shutdown_kroki_session() -> None:
    global _KROKI_SESSION
    if _KROKI_SESSION is not None:
        _KROKI_SESSION.stop()
        _KROKI_SESSION = None


atexit.register(shutdown_kroki_session)


def convert_via_kroki_docker(
    src: Path, output_file: Path, fmt: str, cjk: bool
) -> bool:
    """Render via a reused local yuzutech/kroki container (see KrokiSession).

    Kroki bundles a newer PlantUML version than plantuml/plantuml:latest,
    producing better CJK text layout and wider, less-cramped diagrams.
    The container runs on localhost – no data leaves the host.
    """
    session = get_kroki_session(cjk)
    if session is None:
        return False
    return session.render(src, output_file, fmt)


def _find_local_jar() -> Optional[Path]:
    env_jar = os.environ.get("PLANTUML_JAR")
    candidates = [
        env_jar or "",
        "/usr/local/bin/plantuml.jar",
        "/usr/share/plantuml/plantuml.jar",
        os.path.expanduser("~/plantuml.jar"),
        os.path.join(os.environ.get("USERPROFILE", ""), "plantuml.jar") if os.environ.get("USERPROFILE") else "",
        os.path.join(os.environ.get("PROGRAMFILES", ""), "PlantUML", "plantuml.jar") if os.environ.get("PROGRAMFILES") else "",
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "PlantUML", "plantuml.jar") if os.environ.get("PROGRAMFILES(X86)") else "",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "PlantUML", "plantuml.jar") if os.environ.get("LOCALAPPDATA") else "",
        os.path.join(os.environ.get("USERPROFILE", ""), "scoop", "apps", "plantuml", "current", "plantuml.jar") if os.environ.get("USERPROFILE") else "",
        "./plantuml.jar",
    ]
    for c in candidates:
        if c and Path(c).is_file():
            return Path(c)
    return None


def convert_via_local(src: Path, output_file: Path, fmt: str) -> bool:
    """Offline fallback backend: native `plantuml` on PATH, else a local jar.

    The native command needs no Java; the jar path runs `java -jar`.
    """
    ext = "utxt" if fmt == "txt" else fmt
    native = which("plantuml")
    jar = None if native else _find_local_jar()

    if native:
        base_cmd = [native]
        label = "native plantuml"
        log("  -> Trying native plantuml command (PATH)...")
    elif jar and which("java"):
        base_cmd = ["java", "-jar", str(jar)]
        label = "local JAR"
        log(f"  -> Trying local JAR ({jar})...")
    else:
        log("  -> No native plantuml / local JAR found, skipping")
        return False

    tmpdir = Path(tempfile.gettempdir()) / f"plantuml_local_{uuid.uuid4().hex}"
    tmpdir.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(src, tmpdir / src.name)
        try:
            r = subprocess.run(
                base_cmd + [f"-t{ext}", "-o", str(tmpdir), str(tmpdir / src.name)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except OSError:
            return False
        if r.returncode != 0:
            _log_stderr_tail(r.stderr)
        else:
            gen = _iter_output_candidate(tmpdir, (ext, fmt), src.name)
            if gen:
                shutil.move(str(gen), str(output_file))
                log(f"  ✓ Success ({label})")
                return True
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    log("  ✗ Native/JAR backend failed")
    return False


def convert_via_server(
    src: Path, output_file: Path, fmt: str, use_public_server: bool
) -> bool:
    if not use_public_server:
        log("  → Public server disabled (privacy default). Pass --use-public-server to enable.")
        return False

    server_host = (os.environ.get("PLANTUML_PUBLIC_SERVER") or "https://kroki.io").rstrip("/")
    server_url = f"{server_host}/plantuml/{fmt}"
    host_label = re.sub(r"^https?://", "", server_host).split("/", 1)[0]

    log("")
    log(f"  ⚠  PRIVACY WARNING: about to upload diagram source to {server_url}")
    log(f"     The full contents of '{src}' will be transmitted to {host_label}.")
    if server_host == "https://kroki.io":
        log("     kroki.io is operated by Yuzu Tech (EU). Kroki is open source and")
        log("     self-hostable — set PLANTUML_PUBLIC_SERVER=<your-url> to use your own.")
    else:
        log("     (Custom backend selected via PLANTUML_PUBLIC_SERVER.)")
    log("     Do NOT use this backend for confidential architecture, credentials,")
    log("     customer data, or proprietary business logic.")
    log("")
    log("  → Trying public server (opt-in via --use-public-server)...")

    try:
        body = src.read_bytes()
        req = urllib.request.Request(
            server_url,
            data=body,
            method="POST",
            headers={"Content-Type": "text/plain"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = resp.read()
        output_file.write_bytes(payload)
    except urllib.error.HTTPError as e:
        log(f"  ✗ Public server returned HTTP {e.code}")
        _log_http_error_body(e)
        return False
    except (urllib.error.URLError, OSError, TimeoutError):
        log("  ✗ Public server failed — check network or try Docker/local JAR backend")
        return False

    if _validate_rendered_output(output_file, fmt):
        log("  ✓ Success (public server)")
        return True
    log("  ✗ Public server failed — check network or try Docker/local JAR backend")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="generate_plantuml.py",
        description="Convert PlantUML source to SVG/PNG/PDF/TXT.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Backend priority (local-first):\n"
            "  1. Docker (yuzutech/kroki)       - preferred, local, newer PlantUML\n"
            "  2. Docker (plantuml/plantuml)    - fallback, local\n"
            "  3. Native plantuml cmd / JAR     - offline fallback (PATH 'plantuml'\n"
            "                                     or plantuml.jar; PLANTUML_JAR env)\n"
            "  4. Kroki public server           - OPT-IN ONLY via --use-public-server\n"
            "\n"
            "Batch render (directory input) reuses one kroki container for the\n"
            "whole run and exits non-zero if any file fails.\n"
            "\n"
            "Compatibility tooling (no rendering):\n"
            "  --lint    check .puml files (file or directory) for PlantUML\n"
            "            1.2026.x compatibility; CI-friendly exit codes\n"
            "  --fix     auto-fix strictuml / single-line class bodies /\n"
            "            deprecated skinparams; originals kept as *.bak.puml"
        ),
    )
    p.add_argument("input", help="Path to the .puml source file, or a directory (batch render / --lint / --fix)")
    p.add_argument("output_dir", nargs="?", default="./output", help="Output directory (default: ./output)")
    p.add_argument("--format", choices=("svg", "png", "pdf", "txt"), default="svg", help="Output format (default: svg)")
    p.add_argument("--cjk", action="store_true", help="Enable CJK font support")
    p.add_argument("--no-fix", action="store_true", help="Disable automatic aspect ratio correction")
    p.add_argument("--min-aspect", type=float, default=0.7, help="Min width/height ratio (default: 0.7)")
    p.add_argument("--max-aspect", type=float, default=1.4, help="Max width/height ratio (default: 1.4)")
    p.add_argument("--dark-mode", action="store_true", help="Also emit <basename>.dark.<fmt>")
    p.add_argument("--no-a4-check", action="store_true", help="Disable automatic A4 fit validation")
    p.add_argument("--min-font-pt", type=float, default=8.0, help="Min legible font size on A4 in pt (default: 8.0)")
    p.add_argument("--use-public-server", action="store_true", help="OPT-IN: render via Kroki public server")
    p.add_argument("--lint", action="store_true", help="Compatibility check only (no rendering); input may be a file or directory")
    p.add_argument("--fix", action="store_true", help="Auto-fix compatibility issues in place; originals backed up as *.bak.puml")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    input_path = Path(args.input)

    # ── Lint / Fix modes (no rendering) ───────────────────────────────────
    if args.lint and args.fix:
        elog("ERROR: --lint and --fix are mutually exclusive; pick one")
        return 2
    if args.lint or args.fix:
        paths = collect_puml_inputs(input_path)
        if not paths:
            elog(f"ERROR: no .puml inputs found at: {input_path}")
            return 2
        return run_lint(paths) if args.lint else run_fix(paths)

    output_dir = Path(args.output_dir)

    if input_path.is_dir():
        paths = collect_puml_inputs(input_path)
        if not paths:
            elog(f"ERROR: no .puml inputs found at: {input_path}")
            return 2
        log(f"📦 Batch render: {len(paths)} file(s) from {input_path} → {output_dir}")
        log("   (one shared kroki container is reused for the whole batch)")
        succeeded: List[Path] = []
        failed: List[Path] = []
        try:
            for i, p in enumerate(paths, 1):
                log("")
                log(f"━━━ [{i}/{len(paths)}] {p.name} ━━━")
                if render_single_file(p, output_dir, args):
                    succeeded.append(p)
                else:
                    failed.append(p)
        finally:
            shutdown_kroki_session()
        log("")
        log(f"📦 Batch summary: {len(succeeded)}/{len(paths)} succeeded")
        for p in failed:
            log(f"  ✗ {p}")
        return 0 if not failed else 1

    if not input_path.is_file():
        elog(f"ERROR: Input file not found: {input_path}")
        return 1

    try:
        return 0 if render_single_file(input_path, output_dir, args) else 1
    finally:
        shutdown_kroki_session()


def render_single_file(
    input_path: Path, output_dir: Path, args: argparse.Namespace
) -> bool:
    """Render one .puml through the full pipeline (sanitize → render → postprocess).

    Shared by single-file and batch modes; the kroki container (if any) is
    reused across calls via get_kroki_session(). Returns True on success.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    base = input_path.stem
    for legacy in (".plantuml", ".txt"):
        if base.endswith(legacy):
            base = base[: -len(legacy)]
    fmt = args.format
    output_file = output_dir / f"{base}.{fmt}"

    log(f"🖼️  Converting {input_path} → {output_file} (format: {fmt})")

    # ── CJK auto-detection notice ────────────────────────────────────────────
    cjk = args.cjk
    if not cjk and detect_cjk(input_path):
        log("")
        log("🔤 CJK (Chinese/Japanese/Korean) characters detected in input.")
        log("   These may not render correctly without CJK font support.")
        log("   Re-run with --cjk to enable CJK rendering, or install CJK fonts.")
        log("   Attempting to proceed anyway...")
        log("")

    # ── Prepare working copy ─────────────────────────────────────────────────
    tmpdir = Path(tempfile.gettempdir())
    work_copy = tmpdir / f"plantuml_src_{uuid.uuid4().hex}.puml"
    shutil.copy2(input_path, work_copy)
    sanitize_puml_source(work_copy)

    cjk_copy: Optional[Path] = None
    cjk_family = ""
    if cjk:
        cjk_family, detected = pick_cjk_font()
        if detected:
            log(f"🔤 CJK mode: using host font '{cjk_family}'")
        else:
            log(f"🔤 CJK mode: no CJK font found on host; requesting '{cjk_family}'")
            log("   CJK characters may render as boxes - install e.g. Noto Sans CJK SC")
        cjk_copy = prepare_puml_for_cjk(work_copy, cjk_family)
        try:
            work_copy.unlink()
        except OSError:
            pass
        work_copy = cjk_copy
        sanitize_puml_source(work_copy)

    render_ok = False
    fix_attempt = 0
    aspect_done = False
    a4_tried = False
    last_ok_src = work_copy

    try:
        while fix_attempt <= MAX_FIX_ATTEMPTS:
            attempt_ok = (
                convert_via_kroki_docker(work_copy, output_file, fmt, cjk)
                or convert_via_docker(work_copy, output_file, fmt, cjk)
                or convert_via_local(work_copy, output_file, fmt)
                or convert_via_server(work_copy, output_file, fmt, args.use_public_server)
            )
            if not attempt_ok:
                if render_ok and output_file.is_file():
                    log("  ⚠ Re-render failed; keeping the last successful output")
                    break
                log("")
                log("❌ All conversion methods failed.")
                log("   Install options (local, recommended for privacy):")
                log("   1. Docker: docker pull yuzutech/kroki")
                log("   2. Docker: docker pull plantuml/plantuml:latest")
                log("   3. Java + JAR: download plantuml.jar from https://plantuml.com/download")
                log("   Or, to use the public Kroki server (uploads diagram to kroki.io):")
                log("   4. Re-run with --use-public-server (review the privacy notice first)")
                log("      Override the host with PLANTUML_PUBLIC_SERVER=<url> if self-hosting")
                return False
            render_ok = True
            last_ok_src = work_copy

            if fmt in ("txt", "pdf"):
                break

            if not args.no_fix and not aspect_done:
                problem, _ = check_aspect_ratio(output_file, fmt, args.min_aspect, args.max_aspect)
                if problem is None:
                    log("  ⓘ Could not determine image dimensions; skipping aspect ratio check.")
                    aspect_done = True
                elif problem != "ok":
                    fix_attempt += 1
                    if fix_attempt > MAX_FIX_ATTEMPTS:
                        log(f"  ⚠ Maximum fix attempts ({MAX_FIX_ATTEMPTS}) reached. Manual adjustment may be needed.")
                        aspect_done = True
                    else:
                        fixed = fix_puml_aspect_ratio(work_copy, problem)
                        if not fixed:
                            log("  ✗ Auto-fix step failed; keeping current output.")
                            aspect_done = True
                        else:
                            if work_copy != input_path and work_copy.exists():
                                try:
                                    work_copy.unlink()
                                except OSError:
                                    pass
                            work_copy = fixed
                            log("  → Re-rendering with corrected layout...")
                            continue
                aspect_done = True

            if not args.no_a4_check and not a4_tried:
                fits, factor = check_a4_fit(output_file, fmt)
                if fits is None:
                    log("  ⓘ Could not determine image dimensions; skipping A4 check.")
                    break
                if not fits:
                    fix_attempt += 1
                    if fix_attempt > MAX_FIX_ATTEMPTS:
                        log(f"  ⚠ Maximum fix attempts ({MAX_FIX_ATTEMPTS}) reached; A4 fit may not hold.")
                        break
                    a4_fixed = fix_puml_a4_fit(work_copy, factor, args.min_font_pt)
                    if not a4_fixed:
                        log("  ✗ A4 auto-fit failed; using current diagram.")
                        a4_tried = True
                        break
                    if work_copy != input_path and work_copy.exists():
                        try:
                            work_copy.unlink()
                        except OSError:
                            pass
                    work_copy = a4_fixed
                    a4_tried = True
                    log("  → Re-rendering with A4-fit scale...")
                    continue

            break

        # ── Fix bare strokes in light SVG ────────────────────────────────────
        if render_ok and fmt == "svg":
            postprocess_svg_bare_strokes(output_file)
            if cjk:
                validate_cjk_svg_font(output_file, cjk_family)

        # ── Dark-mode companion ──────────────────────────────────────────────
        dark_output: Optional[Path] = None
        if args.dark_mode and render_ok:
            dark_output = output_dir / f"{base}.dark.{fmt}"
            log("")
            log(f"🌙 Dark-mode variant requested: {dark_output}")
            if fmt == "svg":
                if postprocess_dark_svg(output_file, dark_output):
                    log("  ✓ Dark-mode SVG generated")
                else:
                    dark_output = None
            elif fmt == "png":
                if postprocess_dark_png(output_file, dark_output):
                    log("  ✓ Dark-mode PNG generated")
                else:
                    log("  ⚠ Dark-mode PNG requires ImageMagick (convert); dark variant skipped")
                    dark_output = None
            else:
                log("  ⚠ Dark-mode is only supported for svg and png output; skipping")
                dark_output = None

        # ── Report ───────────────────────────────────────────────────────────
        if render_ok:
            log("")
            log(f"✅ Output: {output_file}")
            print(str(output_file))
            if dark_output and dark_output.is_file():
                log(f"🌙 Dark: {dark_output}")
                print(str(dark_output))
            return True
        return False
    finally:
        # ── Cleanup temp files ───────────────────────────────────────────────
        for p in (work_copy, cjk_copy, last_ok_src):
            if p and p != input_path and Path(p).exists():
                try:
                    Path(p).unlink()
                except OSError:
                    pass


if __name__ == "__main__":
    sys.exit(main())

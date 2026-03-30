#!/usr/bin/env python3
"""
build.py — Static site generator for street photography portfolio.

Usage:
    1. Drop original JPGs into src/
    2. Run: python build.py
    3. Commit & push

Structure:
    config.py              — Site settings (title, sizes, paths)
    templates/base.html    — HTML skeleton with {{placeholders}}
    templates/style.css    — All styles
    templates/script.js    — All client-side logic
"""

import sys, json, hashlib, re
from pathlib import Path
from datetime import datetime

try:
    from PIL import Image, ExifTags
    from PIL.ExifTags import IFD
except ImportError:
    print("Pillow is required: pip install Pillow")
    sys.exit(1)

import config


# --- Paths ---

SRC_DIR = Path(config.SRC_DIR)
THUMB_DIR = Path(config.THUMB_DIR)
FULL_DIR = Path(config.FULL_DIR)
OUTPUT_HTML = Path(config.OUTPUT_HTML)
TEMPLATES_DIR = Path("templates")


# --- EXIF ---

def get_exif(img):
    """Extract EXIF data from PIL Image. Handles both modern and legacy methods."""
    exif_data = {}
    try:
        exif = img.getexif()
        if exif:
            for tag_id, value in exif.items():
                tag = ExifTags.TAGS.get(tag_id, tag_id)
                exif_data[tag] = value
            try:
                exif_ifd = exif.get_ifd(IFD.Exif)
                if exif_ifd:
                    for tag_id, value in exif_ifd.items():
                        tag = ExifTags.TAGS.get(tag_id, tag_id)
                        exif_data[tag] = value
            except Exception:
                pass
        if not exif_data:
            raw = img._getexif()
            if raw:
                for tag_id, value in raw.items():
                    tag = ExifTags.TAGS.get(tag_id, tag_id)
                    exif_data[tag] = value
    except Exception:
        pass
    return exif_data


def format_meta(exif):
    """Format EXIF into display string: ƒ/2.8 · 1/250 · ISO 400 · 12 Mar 2025"""
    parts = []
    fnumber = exif.get("FNumber")
    if fnumber:
        try:
            f = float(fnumber)
            parts.append(f"ƒ/{f:.1f}".rstrip("0").rstrip("."))
        except: pass
    exposure = exif.get("ExposureTime")
    if exposure:
        try:
            exp = float(exposure)
            if exp >= 1: parts.append(f"{exp:.1f}s")
            else: parts.append(f"1/{round(1/exp)}")
        except: pass
    iso = exif.get("ISOSpeedRatings")
    if iso:
        parts.append(f"ISO {iso}")
    date_str = exif.get("DateTimeOriginal")
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            parts.append(dt.strftime("%-d %b %Y"))
        except: pass
    return " · ".join(parts) if parts else "ƒ/— · 1/— · ISO — · —"


def get_sort_key(exif, filename):
    """Sort key: date from EXIF, fallback to filename."""
    date_str = exif.get("DateTimeOriginal")
    if date_str:
        try:
            return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
        except: pass
    return filename


# --- Image processing ---

def make_short_id(name):
    """Generate short ID like 'a3-1832' from filename like 'DSC01832_edit_crop'."""
    digits = re.findall(r'\d{3,}', name)
    num_part = digits[0][-4:] if digits else name[:4]
    h = hashlib.md5(name.encode()).hexdigest()[:2]
    return f"{h}-{num_part}"


def resize_image(img, long_edge):
    """Resize so longest edge equals long_edge, preserving aspect ratio."""
    w, h = img.size
    if max(w, h) <= long_edge:
        return img.copy()
    if w >= h:
        new_w, new_h = long_edge, int(h * (long_edge / w))
    else:
        new_h, new_w = long_edge, int(w * (long_edge / h))
    return img.resize((new_w, new_h), Image.LANCZOS)


def process_images():
    """Scan src/, resize, extract EXIF. Returns (photos_list, all_exif_list)."""
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    FULL_DIR.mkdir(parents=True, exist_ok=True)

    extensions = {".jpg", ".jpeg", ".JPG", ".JPEG"}
    sources = sorted(
        [f for f in SRC_DIR.iterdir() if f.suffix in extensions],
        key=lambda f: f.name
    )
    if not sources:
        print(f"  No images found in {SRC_DIR}/")
        sys.exit(1)

    photos = []
    all_exif = []

    for src_path in sources:
        name = src_path.stem
        print(f"  {src_path.name}")

        img = Image.open(src_path)
        try:
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)
        except: pass

        exif = get_exif(img)
        all_exif.append(exif)
        meta = format_meta(exif)
        sort_key = get_sort_key(exif, name)

        if img.mode != "RGB":
            img = img.convert("RGB")

        # Thumbnail
        thumb = resize_image(img, config.THUMB_LONG_EDGE)
        thumb.save(THUMB_DIR / f"{name}.jpg", "JPEG",
                   quality=config.THUMB_QUALITY, optimize=True)

        # Full size
        full = resize_image(img, config.FULL_LONG_EDGE)
        full.save(FULL_DIR / f"{name}.jpg", "JPEG",
                  quality=config.FULL_QUALITY, optimize=True)

        short_id = make_short_id(name)
        photos.append({
            "id": short_id,
            "thumb": f"photos/thumb/{name}.jpg",
            "full": f"photos/full/{name}.jpg",
            "meta": meta,
            "_sort": sort_key,
        })

    # Sort by date, then filename
    photos.sort(key=lambda p: (isinstance(p["_sort"], str), str(p["_sort"])))
    for p in photos:
        del p["_sort"]

    return photos, all_exif


# --- Stats ---

def generate_stats_html(all_exif):
    """Generate HTML for shooting stats from collected EXIF data."""
    apertures = {}
    isos = {}
    shutters = {}
    has_data = 0

    for exif in all_exif:
        fn = exif.get("FNumber")
        iso = exif.get("ISOSpeedRatings")
        exp = exif.get("ExposureTime")

        if fn or iso or exp:
            has_data += 1

        if fn:
            try:
                f = float(fn)
                key = f"ƒ/{f:.1f}".rstrip("0").rstrip(".")
                apertures[key] = apertures.get(key, 0) + 1
            except: pass
        if iso:
            try:
                key = f"ISO {int(iso)}"
                isos[key] = isos.get(key, 0) + 1
            except: pass
        if exp:
            try:
                e = float(exp)
                if e >= 1: key = f"{e:.1f}s"
                else: key = f"1/{round(1/e)}"
                shutters[key] = shutters.get(key, 0) + 1
            except: pass

    if has_data == 0:
        return ""

    def make_bars(data):
        sorted_items = sorted(data.items(), key=lambda x: -x[1])
        if not sorted_items:
            return ""
        max_count = sorted_items[0][1]
        bars = ""
        for label, count in sorted_items:
            width = max(8, int(120 * count / max_count))
            bars += (
                f'<div class="stat-bar-row">'
                f'<span class="stat-bar-label">{label}</span>'
                f'<div class="stat-bar" style="width:{width}px;"></div>'
                f'<span class="stat-bar-count">{count}</span>'
                f'</div>\n'
            )
        return bars

    sections = []
    if apertures:
        sections.append(f'<div class="stat-group"><div class="stat-label">Aperture</div>{make_bars(apertures)}</div>')
    if shutters:
        sections.append(f'<div class="stat-group"><div class="stat-label">Shutter</div>{make_bars(shutters)}</div>')
    if isos:
        sections.append(f'<div class="stat-group"><div class="stat-label">ISO</div>{make_bars(isos)}</div>')

    if not sections:
        return ""

    return (
        f'<div class="stats">\n'
        f'  <div class="stats-title">{has_data} shots</div>\n'
        f'  <div class="stats-row">\n'
        f'    {"".join(sections)}\n'
        f'  </div>\n'
        f'</div>'
    )


# --- HTML assembly ---

def build_html(photos, all_exif):
    """Read templates, substitute placeholders, write index.html."""
    template = (TEMPLATES_DIR / "base.html").read_text(encoding="utf-8")
    css = (TEMPLATES_DIR / "style.css").read_text(encoding="utf-8")
    js = (TEMPLATES_DIR / "script.js").read_text(encoding="utf-8")

    photos_json = json.dumps(photos, indent=2, ensure_ascii=False)
    stats_html = generate_stats_html(all_exif)

    html = template
    html = html.replace("{{CSS}}", css)
    html = html.replace("{{JS}}", js)
    html = html.replace("{{PHOTOS_JSON}}", photos_json)
    html = html.replace("{{STATS}}", stats_html)
    html = html.replace("{{SITE_TITLE}}", config.SITE_TITLE)
    html = html.replace("{{SITE_SUBTITLE}}", config.SITE_SUBTITLE)
    html = html.replace("{{SITE_EMAIL}}", config.SITE_EMAIL)
    html = html.replace("{{SITE_AUTHOR}}", config.SITE_AUTHOR)

    OUTPUT_HTML.write_text(html, encoding="utf-8")


# --- Main ---

def main():
    print(f"\n  Building {config.SITE_TITLE}...\n")

    if not SRC_DIR.exists():
        SRC_DIR.mkdir()
        print(f"  Created {SRC_DIR}/ — drop your JPGs there and re-run.\n")
        sys.exit(0)

    photos, all_exif = process_images()
    print(f"\n  {len(photos)} photos → {OUTPUT_HTML}\n")

    build_html(photos, all_exif)
    print("  Done. Ready to commit & push.\n")


if __name__ == "__main__":
    main()

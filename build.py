#!/usr/bin/env python3
"""
build.py — Static site generator for street photography portfolio.

Usage:
    1. Drop original JPGs into src/
    2. Run: python build.py
    3. Commit & push — GitHub Pages serves it.

What it does:
    - Scans src/ for .jpg/.jpeg files
    - Resizes to photos/thumb/ (600px long edge, 75% quality)
    - Resizes to photos/full/ (2000px long edge, 85% quality)
    - Reads EXIF (aperture, shutter speed, ISO, date)
    - Generates index.html from the template

Requirements:
    pip install Pillow
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

try:
    from PIL import Image, ExifTags
except ImportError:
    print("Pillow is required: pip install Pillow")
    sys.exit(1)


# Config
SRC_DIR = Path("src")
THUMB_DIR = Path("photos/thumb")
FULL_DIR = Path("photos/full")
THUMB_LONG_EDGE = 600
FULL_LONG_EDGE = 2000
THUMB_QUALITY = 75
FULL_QUALITY = 85
OUTPUT_HTML = Path("index.html")


def get_exif(img):
    """Extract relevant EXIF data from a PIL Image."""
    exif_data = {}
    try:
        raw = img._getexif()
        if not raw:
            return exif_data
        for tag_id, value in raw.items():
            tag = ExifTags.TAGS.get(tag_id, tag_id)
            exif_data[tag] = value
    except Exception:
        pass
    return exif_data


def format_meta(exif):
    """Format EXIF into a display string like: ƒ/2.8 · 1/250 · ISO 400 · 12 Mar 2025"""
    parts = []

    # Aperture
    fnumber = exif.get("FNumber")
    if fnumber:
        try:
            f = float(fnumber)
            parts.append(f"ƒ/{f:.1f}".rstrip("0").rstrip("."))
        except (TypeError, ValueError):
            pass

    # Shutter speed
    exposure = exif.get("ExposureTime")
    if exposure:
        try:
            exp = float(exposure)
            if exp >= 1:
                parts.append(f"{exp:.1f}s")
            else:
                denom = round(1 / exp)
                parts.append(f"1/{denom}")
        except (TypeError, ValueError, ZeroDivisionError):
            pass

    # ISO
    iso = exif.get("ISOSpeedRatings")
    if iso:
        parts.append(f"ISO {iso}")

    # Date
    date_str = exif.get("DateTimeOriginal")
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            parts.append(dt.strftime("%-d %b %Y"))
        except (ValueError, TypeError):
            pass

    if not parts:
        return "ƒ/— · 1/— · ISO — · —"

    return " · ".join(parts)


def get_sort_key(exif, filename):
    """Sort by date taken, fallback to filename."""
    date_str = exif.get("DateTimeOriginal")
    if date_str:
        try:
            return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
        except (ValueError, TypeError):
            pass
    return filename


def resize_image(img, long_edge):
    """Resize so the longest edge equals long_edge, preserving aspect ratio."""
    w, h = img.size
    if max(w, h) <= long_edge:
        return img.copy()
    if w >= h:
        new_w = long_edge
        new_h = int(h * (long_edge / w))
    else:
        new_h = long_edge
        new_w = int(w * (long_edge / h))
    return img.resize((new_w, new_h), Image.LANCZOS)


def process_images():
    """Process all images in src/, return list of photo dicts."""
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    FULL_DIR.mkdir(parents=True, exist_ok=True)

    extensions = {".jpg", ".jpeg", ".JPG", ".JPEG"}
    sources = sorted(
        [f for f in SRC_DIR.iterdir() if f.suffix in extensions],
        key=lambda f: f.name
    )

    if not sources:
        print(f"No images found in {SRC_DIR}/")
        sys.exit(1)

    photos = []

    for src_path in sources:
        name = src_path.stem
        print(f"  Processing {src_path.name}...")

        img = Image.open(src_path)

        # Auto-rotate based on EXIF orientation
        try:
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        # Extract EXIF before any transforms
        exif = get_exif(img)
        meta = format_meta(exif)
        sort_key = get_sort_key(exif, name)

        # Convert to RGB if needed (e.g. RGBA PNGs)
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Generate thumbnail
        thumb = resize_image(img, THUMB_LONG_EDGE)
        thumb_path = THUMB_DIR / f"{name}.jpg"
        thumb.save(thumb_path, "JPEG", quality=THUMB_QUALITY, optimize=True)

        # Generate full-size
        full = resize_image(img, FULL_LONG_EDGE)
        full_path = FULL_DIR / f"{name}.jpg"
        full.save(full_path, "JPEG", quality=FULL_QUALITY, optimize=True)

        photos.append({
            "id": name,
            "thumb": f"photos/thumb/{name}.jpg",
            "full": f"photos/full/{name}.jpg",
            "meta": meta,
            "sort_key": sort_key,
        })

    # Sort by date taken
    photos.sort(key=lambda p: p["sort_key"])

    # Remove sort_key before passing to template
    for p in photos:
        del p["sort_key"]

    return photos


def generate_html(photos):
    """Generate index.html with embedded photo data."""
    photos_json = json.dumps(photos, indent=2, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>street</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400&display=swap');

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    background: #fff;
    color: #000;
    font-family: 'IBM Plex Mono', monospace;
    -webkit-font-smoothing: antialiased;
  }}

  .site-header {{
    padding: 40px 40px 0;
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }}

  .site-title {{
    font-size: 13px;
    font-weight: 400;
    letter-spacing: 0.08em;
    text-transform: lowercase;
  }}

  .site-subtitle {{
    font-size: 11px;
    font-weight: 300;
    color: #999;
    letter-spacing: 0.04em;
  }}

  .flow {{ padding: 40px; }}

  .grid-section {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
  }}

  .grid-item {{ cursor: pointer; }}

  .grid-item img {{
    width: 100%;
    display: block;
    transition: opacity 0.3s ease;
  }}

  .grid-item:hover img {{ opacity: 0.85; }}

  .grid-item .meta {{
    font-size: 10px;
    font-weight: 300;
    color: #b0b0b0;
    letter-spacing: 0.03em;
    margin-top: 6px;
    padding-bottom: 2px;
    transition: color 0.3s ease;
  }}

  .grid-item:hover .meta {{ color: #777; }}

  .expanded-photo {{
    width: 100vw;
    margin-left: -40px;
    margin-top: 20px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    padding: 60px 80px;
    opacity: 0;
    animation: expandIn 0.35s ease forwards;
    position: relative;
  }}

  .close-btn {{
    position: absolute;
    top: 20px;
    right: 32px;
    background: none;
    border: none;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 18px;
    font-weight: 300;
    color: #bbb;
    cursor: pointer;
    transition: color 0.2s;
    line-height: 1;
    padding: 8px;
    z-index: 10;
  }}

  .close-btn:hover {{ color: #333; }}

  .viewer-row {{
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    position: relative;
  }}

  .nav-arrow {{
    background: none;
    border: none;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 20px;
    font-weight: 300;
    color: #ccc;
    cursor: pointer;
    padding: 20px 16px;
    transition: color 0.2s;
    flex-shrink: 0;
    user-select: none;
    line-height: 1;
  }}

  .nav-arrow:hover {{ color: #555; }}
  .nav-arrow:disabled {{ color: #eee; cursor: default; }}

  .img-wrap {{
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 0;
    cursor: zoom-in;
  }}

  .img-wrap img {{
    max-width: 100%;
    max-height: 78vh;
    object-fit: contain;
    display: block;
    user-select: none;
    -webkit-user-drag: none;
    transition: max-width 0.3s ease, max-height 0.3s ease, opacity 0.2s ease;
  }}

  .img-wrap img.fading {{
    opacity: 0;
  }}

  .img-wrap.enlarged {{
    cursor: zoom-out;
  }}

  .img-wrap.enlarged img {{
    max-width: 100%;
    max-height: none;
  }}

  .meta-expanded {{
    font-size: 11px;
    font-weight: 300;
    color: #aaa;
    letter-spacing: 0.03em;
    margin-top: 20px;
    text-align: center;
  }}

  @keyframes expandIn {{
    from {{ opacity: 0; }}
    to {{ opacity: 1; }}
  }}

  .site-footer {{
    padding: 60px 40px 40px;
    text-align: center;
  }}

  .site-footer span {{
    font-size: 10px;
    font-weight: 300;
    color: #ccc;
    letter-spacing: 0.04em;
  }}

  @media (min-width: 1800px) {{
    .grid-section {{ grid-template-columns: repeat(6, 1fr); gap: 16px; }}
    .grid-item .meta {{ font-size: 9px; }}
  }}

  @media (max-width: 1100px) {{
    .grid-section {{ grid-template-columns: repeat(2, 1fr); }}
    .flow {{ padding: 30px; }}
    .expanded-photo {{ margin-left: -30px; padding: 40px 60px; }}
    .site-header {{ padding: 30px 30px 0; }}
  }}

  @media (max-width: 640px) {{
    .grid-section {{ grid-template-columns: 1fr; }}
    .flow {{ padding: 20px; }}
    .expanded-photo {{ margin-left: -20px; padding: 30px 40px; }}
    .site-header {{
      padding: 24px 20px 0;
      flex-direction: column;
      gap: 4px;
    }}
    .nav-arrow {{ padding: 12px 8px; font-size: 16px; }}
    .close-btn {{ right: 12px; top: 8px; }}
  }}

  .grid-item {{
    opacity: 0;
    transform: translateY(8px);
    animation: fadeUp 0.45s ease forwards;
  }}

  @keyframes fadeUp {{
    to {{ opacity: 1; transform: translateY(0); }}
  }}
</style>
</head>
<body>

<header class="site-header">
  <span class="site-title">street</span>
  <span class="site-subtitle">35mm · stuttgart</span>
</header>

<div class="flow" id="flow"></div>

<footer class="site-footer">
  <span>2025</span>
</footer>

<script>
const photos = {photos_json};

const flow = document.getElementById('flow');
let expandedId = null;
let isEnlarged = false;

function getIdx() {{
  return photos.findIndex(p => p.id === expandedId);
}}

function navigateTo(id) {{
  const wasExpanded = expandedId !== null;
  expandedId = id;
  isEnlarged = false;
  history.replaceState(null, '', '#' + id);

  if (wasExpanded) {{
    swapExpandedPhoto(id);
  }} else {{
    render();
    requestAnimationFrame(() => {{
      const el = document.getElementById(id);
      if (el) el.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
    }});
  }}
}}

function swapExpandedPhoto(id) {{
  const photo = photos.find(p => p.id === id);
  if (!photo) return;

  const idx = getIdx();
  const img = document.querySelector('#img-wrap img');
  const meta = document.querySelector('.meta-expanded');
  const imgWrap = document.getElementById('img-wrap');
  const expanded = document.querySelector('.expanded-photo');
  const prevBtn = document.querySelector('.nav-arrow[data-dir="prev"]');
  const nextBtn = document.querySelector('.nav-arrow[data-dir="next"]');

  if (!img || !expanded) return;

  if (imgWrap) imgWrap.classList.remove('enlarged');

  img.classList.add('fading');

  setTimeout(() => {{
    img.src = photo.full;
    if (meta) meta.textContent = photo.meta;
    expanded.id = photo.id;

    if (prevBtn) prevBtn.disabled = idx <= 0;
    if (nextBtn) nextBtn.disabled = idx >= photos.length - 1;

    if (prevBtn) {{
      const newPrev = prevBtn.cloneNode(true);
      prevBtn.replaceWith(newPrev);
      if (idx > 0) {{
        newPrev.addEventListener('click', (e) => {{
          e.stopPropagation();
          navigateTo(photos[idx - 1].id);
        }});
      }}
    }}
    if (nextBtn) {{
      const newNext = nextBtn.cloneNode(true);
      nextBtn.replaceWith(newNext);
      if (idx < photos.length - 1) {{
        newNext.addEventListener('click', (e) => {{
          e.stopPropagation();
          navigateTo(photos[idx + 1].id);
        }});
      }}
    }}

    img.classList.remove('fading');
  }}, 200);
}}

function closeExpanded() {{
  expandedId = null;
  isEnlarged = false;
  history.replaceState(null, '', window.location.pathname);
  render();
}}

function render() {{
  flow.innerHTML = '';
  let gridItems = [];

  function flushGrid() {{
    if (!gridItems.length) return;
    const section = document.createElement('div');
    section.className = 'grid-section';
    gridItems.forEach((item, i) => {{
      item.style.animationDelay = `${{i * 0.035}}s`;
      section.appendChild(item);
    }});
    flow.appendChild(section);
    gridItems = [];
  }}

  photos.forEach((photo) => {{
    if (photo.id === expandedId) {{
      flushGrid();
      buildExpanded(photo);
    }} else {{
      const item = document.createElement('div');
      item.className = 'grid-item';
      item.innerHTML = `
        <img src="${{photo.thumb}}" alt="${{photo.id}}" loading="lazy">
        <div class="meta">${{photo.meta}}</div>
      `;
      item.addEventListener('click', () => navigateTo(photo.id));
      gridItems.push(item);
    }}
  }});

  flushGrid();
}}

function buildExpanded(photo) {{
  const idx = getIdx();
  const hasPrev = idx > 0;
  const hasNext = idx < photos.length - 1;

  const el = document.createElement('div');
  el.className = 'expanded-photo';
  el.id = photo.id;

  el.innerHTML = `
    <button class="close-btn" title="Close">&times;</button>
    <div class="viewer-row">
      <button class="nav-arrow" ${{!hasPrev ? 'disabled' : ''}} data-dir="prev">&#8592;</button>
      <div class="img-wrap ${{isEnlarged ? 'enlarged' : ''}}" id="img-wrap">
        <img src="${{photo.full}}" alt="${{photo.id}}">
      </div>
      <button class="nav-arrow" ${{!hasNext ? 'disabled' : ''}} data-dir="next">&#8594;</button>
    </div>
    <div class="meta-expanded">${{photo.meta}}</div>
  `;

  flow.appendChild(el);

  el.querySelector('.close-btn').addEventListener('click', (e) => {{
    e.stopPropagation();
    closeExpanded();
  }});

  el.querySelectorAll('.nav-arrow').forEach(btn => {{
    btn.addEventListener('click', (e) => {{
      e.stopPropagation();
      if (btn.disabled) return;
      const dir = btn.dataset.dir;
      if (dir === 'prev' && hasPrev) navigateTo(photos[idx - 1].id);
      if (dir === 'next' && hasNext) navigateTo(photos[idx + 1].id);
    }});
  }});

  const imgWrap = el.querySelector('#img-wrap');
  imgWrap.addEventListener('click', (e) => {{
    e.stopPropagation();
    isEnlarged = !isEnlarged;
    imgWrap.classList.toggle('enlarged', isEnlarged);
  }});
}}

document.addEventListener('keydown', (e) => {{
  if (!expandedId) return;
  const idx = getIdx();

  if (e.key === 'Escape') {{
    if (isEnlarged) {{
      isEnlarged = false;
      const w = document.getElementById('img-wrap');
      if (w) w.classList.remove('enlarged');
    }} else {{
      closeExpanded();
    }}
  }} else if (e.key === 'ArrowLeft' && idx > 0) {{
    navigateTo(photos[idx - 1].id);
  }} else if (e.key === 'ArrowRight' && idx < photos.length - 1) {{
    navigateTo(photos[idx + 1].id);
  }}
}});

const hash = window.location.hash.slice(1);
if (hash) {{
  const photo = photos.find(p => p.id === hash);
  if (photo) expandedId = photo.id;
}}

render();

if (expandedId) {{
  requestAnimationFrame(() => {{
    const el = document.getElementById(expandedId);
    if (el) el.scrollIntoView({{ block: 'start' }});
  }});
}}
</script>

</body>
</html>"""

    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"  Generated {OUTPUT_HTML}")


def main():
    print("Building street portfolio...")
    print()

    if not SRC_DIR.exists():
        SRC_DIR.mkdir()
        print(f"Created {SRC_DIR}/ — drop your original JPGs there and re-run.")
        sys.exit(0)

    photos = process_images()
    print()
    print(f"  {len(photos)} photos processed")
    print()

    generate_html(photos)
    print()
    print("Done. Ready to commit & push.")


if __name__ == "__main__":
    main()

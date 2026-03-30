#!/usr/bin/env python3
"""
build.py — Static site generator for street photography portfolio.

Usage:
    1. Drop original JPGs into src/
    2. Run: python build.py
    3. Commit & push — GitHub Pages serves it.

Requirements:
    pip install Pillow
"""

import os, sys, json
from pathlib import Path
from datetime import datetime

try:
    from PIL import Image, ExifTags
except ImportError:
    print("Pillow is required: pip install Pillow")
    sys.exit(1)

SRC_DIR = Path("src")
THUMB_DIR = Path("photos/thumb")
FULL_DIR = Path("photos/full")
THUMB_LONG_EDGE = 600
FULL_LONG_EDGE = 2000
THUMB_QUALITY = 75
FULL_QUALITY = 85
OUTPUT_HTML = Path("index.html")


def get_exif(img):
    exif_data = {}
    try:
        # Try modern method first (works with JFIF+EXIF files from RawTherapee)
        exif = img.getexif()
        if exif:
            for tag_id, value in exif.items():
                tag = ExifTags.TAGS.get(tag_id, tag_id)
                exif_data[tag] = value
            # Also read the Exif sub-IFD (contains FNumber, ExposureTime, ISO, dates)
            try:
                from PIL.ExifTags import IFD
                exif_ifd = exif.get_ifd(IFD.Exif)
                if exif_ifd:
                    for tag_id, value in exif_ifd.items():
                        tag = ExifTags.TAGS.get(tag_id, tag_id)
                        exif_data[tag] = value
            except Exception:
                pass
        # Fallback to legacy method
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
    parts = []
    fnumber = exif.get("FNumber")
    if fnumber:
        try:
            f = float(fnumber)
            parts.append(f"\u0192/{f:.1f}".rstrip("0").rstrip("."))
        except: pass
    exposure = exif.get("ExposureTime")
    if exposure:
        try:
            exp = float(exposure)
            if exp >= 1: parts.append(f"{exp:.1f}s")
            else: parts.append(f"1/{round(1/exp)}")
        except: pass
    iso = exif.get("ISOSpeedRatings")
    if iso: parts.append(f"ISO {iso}")
    date_str = exif.get("DateTimeOriginal")
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            parts.append(dt.strftime("%-d %b %Y"))
        except: pass
    return " \u00b7 ".join(parts) if parts else "\u0192/\u2014 \u00b7 1/\u2014 \u00b7 ISO \u2014 \u00b7 \u2014"


def get_sort_key(exif, filename):
    date_str = exif.get("DateTimeOriginal")
    if date_str:
        try: return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
        except: pass
    return filename


def resize_image(img, long_edge):
    w, h = img.size
    if max(w, h) <= long_edge: return img.copy()
    if w >= h:
        new_w, new_h = long_edge, int(h * (long_edge / w))
    else:
        new_h, new_w = long_edge, int(w * (long_edge / h))
    return img.resize((new_w, new_h), Image.LANCZOS)


def process_images():
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    FULL_DIR.mkdir(parents=True, exist_ok=True)
    extensions = {".jpg", ".jpeg", ".JPG", ".JPEG"}
    sources = sorted([f for f in SRC_DIR.iterdir() if f.suffix in extensions], key=lambda f: f.name)
    if not sources:
        print(f"No images found in {SRC_DIR}/"); sys.exit(1)
    photos = []
    all_exif = []
    for src_path in sources:
        name = src_path.stem
        print(f"  Processing {src_path.name}...")
        img = Image.open(src_path)
        try:
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)
        except: pass
        exif = get_exif(img)
        all_exif.append(exif)
        meta = format_meta(exif)
        sort_key = get_sort_key(exif, name)
        if img.mode != "RGB": img = img.convert("RGB")
        thumb = resize_image(img, THUMB_LONG_EDGE)
        thumb.save(THUMB_DIR / f"{name}.jpg", "JPEG", quality=THUMB_QUALITY, optimize=True)
        full = resize_image(img, FULL_LONG_EDGE)
        full.save(FULL_DIR / f"{name}.jpg", "JPEG", quality=FULL_QUALITY, optimize=True)
        photos.append({"id": name, "thumb": f"photos/thumb/{name}.jpg", "full": f"photos/full/{name}.jpg", "meta": meta, "_sort": sort_key})
    photos.sort(key=lambda p: (isinstance(p["_sort"], str), str(p["_sort"])))
    for p in photos: del p["_sort"]
    return photos, all_exif


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noimageindex">
<title>street</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600&family=DM+Mono:wght@300;400&display=swap');
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #fff; color: #000; font-family: 'Space Grotesk', sans-serif; -webkit-font-smoothing: antialiased; }
  .site-header { padding: 40px 40px 0; display: flex; justify-content: space-between; align-items: baseline; min-height: 360px; align-content: start; flex-wrap: wrap; }
  .site-title { font-size: 18px; font-weight: 500; letter-spacing: 0.12em; text-transform: uppercase; }
  .site-subtitle { font-size: 16px; font-weight: 300; color: #666; letter-spacing: 0.06em; font-family: 'DM Mono', monospace; }
  .flow { padding: 0 40px 40px; }
  .grid-section { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
  .grid-item { cursor: pointer; }
  .grid-item img { width: 100%; display: block; transition: opacity 0.3s ease; -webkit-user-drag: none; user-select: none; pointer-events: none; }
  .grid-item:hover img { opacity: 0.85; }
  .grid-item .meta { font-size: 16px; font-weight: 300; color: #777; letter-spacing: 0.02em; margin-top: 8px; padding-bottom: 2px; transition: color 0.3s ease; font-family: 'DM Mono', monospace; }
  .grid-item:hover .meta { color: #444; }
  .expanded-photo { width: 100vw; margin-left: -40px; margin-top: 20px; margin-bottom: 20px; display: flex; align-items: center; justify-content: center; flex-direction: column; padding: 60px 80px; opacity: 0; animation: expandIn 0.35s ease forwards; position: relative; }
  .close-btn { position: absolute; top: 24px; right: 36px; background: none; border: none; font-family: 'Space Grotesk', sans-serif; font-size: 32px; font-weight: 300; color: #777; cursor: pointer; transition: color 0.2s; line-height: 1; padding: 8px; z-index: 10; }
  .close-btn:hover { color: #000; }
  .viewer-row { display: flex; align-items: center; justify-content: center; width: 100%; position: relative; }
  .nav-arrow { background: none; border: none; font-family: 'Space Grotesk', sans-serif; font-size: 32px; font-weight: 300; color: #777; cursor: pointer; padding: 24px 20px; transition: color 0.2s; flex-shrink: 0; user-select: none; line-height: 1; }
  .nav-arrow:hover { color: #000; }
  .nav-arrow:disabled { color: #ccc; cursor: default; }
  .img-stage { flex: 1; min-width: 0; position: relative; display: flex; align-items: center; justify-content: center; cursor: zoom-in; }
  .img-stage.enlarged { cursor: zoom-out; }
  .img-stage img { max-width: 100%; max-height: 78vh; object-fit: contain; display: block; user-select: none; -webkit-user-drag: none; transition: opacity 0.25s ease, max-height 0.3s ease; }
  .img-stage .img-back { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; }
  .img-stage.enlarged img { max-height: none; }
  .meta-expanded { font-size: 16px; font-weight: 300; color: #666; letter-spacing: 0.02em; margin-top: 20px; text-align: center; font-family: 'DM Mono', monospace; }
  @keyframes expandIn { from { opacity: 0; } to { opacity: 1; } }

  /* Stats */
  .stats { padding: 80px 40px 0; max-width: 720px; }
  .stats-title { font-size: 16px; font-weight: 400; color: #999; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 24px; }
  .stats-row { display: flex; gap: 48px; flex-wrap: wrap; margin-bottom: 16px; }
  .stat-group { min-width: 140px; }
  .stat-label { font-size: 16px; font-weight: 400; color: #666; margin-bottom: 8px; }
  .stat-bar-row { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
  .stat-bar-label { font-size: 16px; font-weight: 300; color: #777; font-family: 'DM Mono', monospace; min-width: 72px; }
  .stat-bar { height: 6px; background: #ddd; border-radius: 3px; transition: width 0.3s ease; }
  .stat-bar-count { font-size: 16px; font-weight: 300; color: #aaa; font-family: 'DM Mono', monospace; }

  /* Footer */
  .site-footer { padding: 80px 40px 40px; }
  .site-footer span { font-size: 16px; font-weight: 300; color: #888; letter-spacing: 0.03em; font-family: 'DM Mono', monospace; }
  .site-footer a { color: #666; text-decoration: none; transition: color 0.2s; }
  .site-footer a:hover { color: #000; }
  .footer-email { margin-top: 16px; }
  .footer-copy { margin-top: 40px; }
  .footer-notice { color: #aaa; margin-top: 6px; display: inline-block; }

  /* Breakpoints: 6 → 5 → 4 → 3 → 2 → 1 */
  @media (min-width: 2200px) { .grid-section { grid-template-columns: repeat(6, 1fr); gap: 16px; } }
  @media (min-width: 1800px) and (max-width: 2199px) { .grid-section { grid-template-columns: repeat(5, 1fr); gap: 18px; } }
  @media (min-width: 1400px) and (max-width: 1799px) { .grid-section { grid-template-columns: repeat(4, 1fr); gap: 18px; } }
  @media (max-width: 1399px) and (min-width: 1101px) { .grid-section { grid-template-columns: repeat(3, 1fr); gap: 20px; } }
  @media (max-width: 1100px) {
    .grid-section { grid-template-columns: repeat(2, 1fr); gap: 16px; }
    .flow { padding: 0 20px 20px; }
    .site-header { padding: 24px 20px 0; min-height: 200px; }
    .grid-item { cursor: default; }
    .grid-item:hover img { opacity: 1; }
    .stats { padding: 60px 20px 0; }
    .site-footer { padding: 60px 20px 40px; }
  }
  @media (max-width: 640px) {
    .grid-section { grid-template-columns: 1fr; gap: 12px; }
    .flow { padding: 0 16px 16px; }
    .site-header { padding: 24px 16px 0; flex-direction: column; gap: 4px; min-height: 160px; }
    .stats { padding: 48px 16px 0; }
    .stats-row { gap: 32px; }
    .site-footer { padding: 48px 16px 32px; }
  }
  .grid-item { opacity: 0; transform: translateY(8px); animation: fadeUp 0.45s ease forwards; }
  @keyframes fadeUp { to { opacity: 1; transform: translateY(0); } }
</style>
</head>
<body>
<header class="site-header">
  <span class="site-title">street</span>
  <span class="site-subtitle">35mm · stuttgart</span>
</header>
<div class="flow" id="flow"></div>
__STATS_HTML__
<footer class="site-footer">
  <div class="footer-email"><span><a href="mailto:hi@kremenskii.art">hi@kremenskii.art</a></span></div>
  <div class="footer-copy">
    <span>&copy; Dmitrii Kremenskii. All rights reserved.</span><br>
    <span class="footer-notice">No image may be reproduced without written permission.</span>
  </div>
</footer>
<script>
const photos = __PHOTOS_JSON__;

const flow = document.getElementById('flow');
let expandedId = null;
let isEnlarged = false;
const preloadCache = {};

function getIdx() {
  return photos.findIndex(p => p.id === expandedId);
}

function preloadImage(src) {
  if (preloadCache[src]) return preloadCache[src];
  const promise = new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(src);
    img.onerror = () => resolve(src);
    img.src = src;
  });
  preloadCache[src] = promise;
  return promise;
}

function preloadNeighbors(idx) {
  if (idx > 0) preloadImage(photos[idx - 1].full);
  if (idx < photos.length - 1) preloadImage(photos[idx + 1].full);
}

function openFromGrid(id) {
  expandedId = id;
  isEnlarged = false;
  history.replaceState(null, '', '#' + id);
  render();
  requestAnimationFrame(() => {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  preloadNeighbors(getIdx());
}

function navigateArrow(id) {
  expandedId = id;
  isEnlarged = false;
  history.replaceState(null, '', '#' + id);
  const photo = photos.find(p => p.id === id);
  if (!photo) return;
  const idx = getIdx();
  const stage = document.querySelector('.img-stage');
  const imgFront = document.getElementById('img-front');
  const imgBack = document.getElementById('img-back');
  const meta = document.querySelector('.meta-expanded');
  const expanded = document.querySelector('.expanded-photo');
  if (!imgFront || !imgBack || !expanded) return;
  if (stage) stage.classList.remove('enlarged');
  preloadImage(photo.full).then(() => {
    imgBack.src = photo.full;
    imgBack.style.opacity = '1';
    imgFront.style.opacity = '0';
    setTimeout(() => {
      imgFront.src = photo.full;
      imgFront.style.opacity = '1';
      imgBack.style.opacity = '0';
      expanded.id = photo.id;
      if (meta) meta.textContent = photo.meta;
      const prevBtn = document.querySelector('.nav-arrow[data-dir="prev"]');
      const nextBtn = document.querySelector('.nav-arrow[data-dir="next"]');
      if (prevBtn) prevBtn.disabled = idx <= 0;
      if (nextBtn) nextBtn.disabled = idx >= photos.length - 1;
      rebindArrows(idx);
      preloadNeighbors(idx);
    }, 260);
  });
}

function rebindArrows(idx) {
  const prevBtn = document.querySelector('.nav-arrow[data-dir="prev"]');
  const nextBtn = document.querySelector('.nav-arrow[data-dir="next"]');
  if (prevBtn) {
    const n = prevBtn.cloneNode(true);
    prevBtn.replaceWith(n);
    n.disabled = idx <= 0;
    if (idx > 0) n.addEventListener('click', (e) => { e.stopPropagation(); navigateArrow(photos[idx - 1].id); });
  }
  if (nextBtn) {
    const n = nextBtn.cloneNode(true);
    nextBtn.replaceWith(n);
    n.disabled = idx >= photos.length - 1;
    if (idx < photos.length - 1) n.addEventListener('click', (e) => { e.stopPropagation(); navigateArrow(photos[idx + 1].id); });
  }
}

function closeExpanded() {
  expandedId = null;
  isEnlarged = false;
  history.replaceState(null, '', window.location.pathname);
  render();
}

function isDesktop() {
  return window.innerWidth > 1100;
}

function render() {
  flow.innerHTML = '';

  if (!isDesktop()) {
    // Simple feed mode: just images, full quality, no interaction
    const section = document.createElement('div');
    section.className = 'grid-section';
    photos.forEach((photo, i) => {
      const item = document.createElement('div');
      item.className = 'grid-item';
      item.id = photo.id;
      item.style.animationDelay = `${i * 0.035}s`;
      item.innerHTML = `<img src="${photo.full}" alt="${photo.id}" loading="lazy"><div class="meta">${photo.meta}</div>`;
      section.appendChild(item);
    });
    flow.appendChild(section);
    return;
  }

  // Desktop: interactive grid with expand
  let gridItems = [];
  function flushGrid() {
    if (!gridItems.length) return;
    const section = document.createElement('div');
    section.className = 'grid-section';
    gridItems.forEach((item, i) => { item.style.animationDelay = `${i * 0.035}s`; section.appendChild(item); });
    flow.appendChild(section);
    gridItems = [];
  }
  photos.forEach((photo) => {
    if (photo.id === expandedId) {
      flushGrid();
      buildExpanded(photo);
    } else {
      const item = document.createElement('div');
      item.className = 'grid-item';
      item.innerHTML = `<img src="${photo.thumb}" alt="${photo.id}" loading="lazy"><div class="meta">${photo.meta}</div>`;
      item.addEventListener('click', () => openFromGrid(photo.id));
      gridItems.push(item);
    }
  });
  flushGrid();
}

function buildExpanded(photo) {
  const idx = getIdx();
  const hasPrev = idx > 0;
  const hasNext = idx < photos.length - 1;
  const el = document.createElement('div');
  el.className = 'expanded-photo';
  el.id = photo.id;
  el.innerHTML = `
    <button class="close-btn" title="Close">&times;</button>
    <div class="viewer-row">
      <button class="nav-arrow" ${!hasPrev ? 'disabled' : ''} data-dir="prev">&#8592;</button>
      <div class="img-stage" id="img-stage">
        <img id="img-front" src="${photo.full}" alt="${photo.id}">
        <img id="img-back" class="img-back" src="" alt="">
      </div>
      <button class="nav-arrow" ${!hasNext ? 'disabled' : ''} data-dir="next">&#8594;</button>
    </div>
    <div class="meta-expanded">${photo.meta}</div>
  `;
  flow.appendChild(el);
  el.querySelector('.close-btn').addEventListener('click', (e) => { e.stopPropagation(); closeExpanded(); });
  rebindArrows(idx);
  const stage = el.querySelector('#img-stage');
  stage.addEventListener('click', (e) => {
    e.stopPropagation();
    isEnlarged = !isEnlarged;
    stage.classList.toggle('enlarged', isEnlarged);
  });
  preloadNeighbors(idx);
}

document.addEventListener('keydown', (e) => {
  if (!expandedId) return;
  const idx = getIdx();
  if (e.key === 'Escape') {
    if (isEnlarged) { isEnlarged = false; const s = document.getElementById('img-stage'); if (s) s.classList.remove('enlarged'); }
    else { closeExpanded(); }
  } else if (e.key === 'ArrowLeft' && idx > 0) { navigateArrow(photos[idx - 1].id); }
  else if (e.key === 'ArrowRight' && idx < photos.length - 1) { navigateArrow(photos[idx + 1].id); }
});

const hash = window.location.hash.slice(1);
if (hash) {
  const photo = photos.find(p => p.id === hash);
  if (photo) {
    if (isDesktop()) expandedId = photo.id;
  }
}
render();
if (hash) {
  requestAnimationFrame(() => {
    const el = document.getElementById(hash);
    if (el) el.scrollIntoView({ block: 'start' });
  });
}
// Block right-click and drag on images
document.addEventListener('contextmenu', (e) => {
  if (e.target.tagName === 'IMG') e.preventDefault();
});
document.addEventListener('dragstart', (e) => {
  if (e.target.tagName === 'IMG') e.preventDefault();
});
</script>
</body>
</html>"""


def generate_stats_html(all_exif):
    """Generate HTML for shooting stats from collected EXIF data."""
    apertures = {}
    isos = {}
    shutters = {}
    total = len(all_exif)
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

    def make_bars(data, max_bars=5):
        sorted_items = sorted(data.items(), key=lambda x: -x[1])[:max_bars]
        if not sorted_items: return ""
        max_count = sorted_items[0][1]
        bars = ""
        for label, count in sorted_items:
            width = max(8, int(120 * count / max_count))
            bars += f'<div class="stat-bar-row"><span class="stat-bar-label">{label}</span><div class="stat-bar" style="width:{width}px;"></div><span class="stat-bar-count">{count}</span></div>\n'
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

    return f'''<div class="stats">
  <div class="stats-title">{has_data} shots</div>
  <div class="stats-row">
    {"".join(sections)}
  </div>
</div>'''


def generate_html(photos, all_exif):
    photos_json = json.dumps(photos, indent=2, ensure_ascii=False)
    stats_html = generate_stats_html(all_exif)
    html = TEMPLATE.replace('__PHOTOS_JSON__', photos_json).replace('__STATS_HTML__', stats_html)
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"  Generated {OUTPUT_HTML}")


def main():
    print("Building street portfolio...\n")
    if not SRC_DIR.exists():
        SRC_DIR.mkdir()
        print(f"Created {SRC_DIR}/ — drop your original JPGs there and re-run.")
        sys.exit(0)
    photos, all_exif = process_images()
    print(f"\n  {len(photos)} photos processed\n")
    generate_html(photos, all_exif)
    print("\nDone. Ready to commit & push.")

if __name__ == "__main__":
    main()

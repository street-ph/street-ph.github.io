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
        raw = img._getexif()
        if not raw: return exif_data
        for tag_id, value in raw.items():
            tag = ExifTags.TAGS.get(tag_id, tag_id)
            exif_data[tag] = value
    except Exception: pass
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
    for src_path in sources:
        name = src_path.stem
        print(f"  Processing {src_path.name}...")
        img = Image.open(src_path)
        try:
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)
        except: pass
        exif = get_exif(img)
        meta = format_meta(exif)
        sort_key = get_sort_key(exif, name)
        if img.mode != "RGB": img = img.convert("RGB")
        thumb = resize_image(img, THUMB_LONG_EDGE)
        (THUMB_DIR / f"{name}.jpg").open("wb")
        thumb.save(THUMB_DIR / f"{name}.jpg", "JPEG", quality=THUMB_QUALITY, optimize=True)
        full = resize_image(img, FULL_LONG_EDGE)
        full.save(FULL_DIR / f"{name}.jpg", "JPEG", quality=FULL_QUALITY, optimize=True)
        photos.append({"id": name, "thumb": f"photos/thumb/{name}.jpg", "full": f"photos/full/{name}.jpg", "meta": meta, "_sort": sort_key})
    photos.sort(key=lambda p: p["_sort"])
    for p in photos: del p["_sort"]
    return photos


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>street</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400&display=swap');
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #fff; color: #000; font-family: 'IBM Plex Mono', monospace; -webkit-font-smoothing: antialiased; }
  .site-header { padding: 40px 40px 0; display: flex; justify-content: space-between; align-items: baseline; }
  .site-title { font-size: 13px; font-weight: 400; letter-spacing: 0.08em; text-transform: lowercase; }
  .site-subtitle { font-size: 11px; font-weight: 300; color: #999; letter-spacing: 0.04em; }
  .flow { padding: 40px; }
  .grid-section { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
  .grid-item { cursor: pointer; }
  .grid-item img { width: 100%; display: block; transition: opacity 0.3s ease; }
  .grid-item:hover img { opacity: 0.85; }
  .grid-item .meta { font-size: 10px; font-weight: 300; color: #b0b0b0; letter-spacing: 0.03em; margin-top: 6px; padding-bottom: 2px; transition: color 0.3s ease; }
  .grid-item:hover .meta { color: #777; }
  .expanded-photo { width: 100vw; margin-left: -40px; margin-top: 20px; margin-bottom: 20px; display: flex; align-items: center; justify-content: center; flex-direction: column; padding: 60px 80px; opacity: 0; animation: expandIn 0.35s ease forwards; position: relative; }
  .close-btn { position: absolute; top: 20px; right: 32px; background: none; border: none; font-family: 'IBM Plex Mono', monospace; font-size: 18px; font-weight: 300; color: #bbb; cursor: pointer; transition: color 0.2s; line-height: 1; padding: 8px; z-index: 10; }
  .close-btn:hover { color: #333; }
  .viewer-row { display: flex; align-items: center; justify-content: center; width: 100%; position: relative; }
  .nav-arrow { background: none; border: none; font-family: 'IBM Plex Mono', monospace; font-size: 20px; font-weight: 300; color: #ccc; cursor: pointer; padding: 20px 16px; transition: color 0.2s; flex-shrink: 0; user-select: none; line-height: 1; }
  .nav-arrow:hover { color: #555; }
  .nav-arrow:disabled { color: #eee; cursor: default; }
  .img-stage { flex: 1; min-width: 0; position: relative; display: flex; align-items: center; justify-content: center; cursor: zoom-in; }
  .img-stage.enlarged { cursor: zoom-out; }
  .img-stage img { max-width: 100%; max-height: 78vh; object-fit: contain; display: block; user-select: none; -webkit-user-drag: none; transition: opacity 0.25s ease, max-height 0.3s ease; }
  .img-stage .img-back { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; }
  .img-stage.enlarged img { max-height: none; }
  .meta-expanded { font-size: 11px; font-weight: 300; color: #aaa; letter-spacing: 0.03em; margin-top: 20px; text-align: center; }
  @keyframes expandIn { from { opacity: 0; } to { opacity: 1; } }
  .site-footer { padding: 60px 40px 40px; text-align: center; }
  .site-footer span { font-size: 10px; font-weight: 300; color: #ccc; letter-spacing: 0.04em; }
  @media (min-width: 1800px) { .grid-section { grid-template-columns: repeat(6, 1fr); gap: 16px; } .grid-item .meta { font-size: 9px; } }
  @media (max-width: 1100px) {
    .grid-section { grid-template-columns: repeat(2, 1fr); gap: 16px; }
    .flow { padding: 20px; }
    .site-header { padding: 24px 20px 0; }
    .grid-item { cursor: default; }
    .grid-item:hover img { opacity: 1; }
  }
  @media (max-width: 640px) {
    .grid-section { grid-template-columns: 1fr; gap: 12px; }
    .flow { padding: 16px; }
    .site-header { padding: 24px 16px 0; flex-direction: column; gap: 4px; }
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
<footer class="site-footer"><span>2025</span></footer>
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
</script>
</body>
</html>"""


def generate_html(photos):
    photos_json = json.dumps(photos, indent=2, ensure_ascii=False)
    html = TEMPLATE.replace('__PHOTOS_JSON__', photos_json)
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"  Generated {OUTPUT_HTML}")


def main():
    print("Building street portfolio...\n")
    if not SRC_DIR.exists():
        SRC_DIR.mkdir()
        print(f"Created {SRC_DIR}/ — drop your original JPGs there and re-run.")
        sys.exit(0)
    photos = process_images()
    print(f"\n  {len(photos)} photos processed\n")
    generate_html(photos)
    print("\nDone. Ready to commit & push.")

if __name__ == "__main__":
    main()

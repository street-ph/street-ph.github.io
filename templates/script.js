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
    // Simple feed mode: full quality, no interaction
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

// Keyboard navigation
document.addEventListener('keydown', (e) => {
  if (!expandedId) return;
  const idx = getIdx();
  if (e.key === 'Escape') {
    if (isEnlarged) { isEnlarged = false; const s = document.getElementById('img-stage'); if (s) s.classList.remove('enlarged'); }
    else { closeExpanded(); }
  } else if (e.key === 'ArrowLeft' && idx > 0) { navigateArrow(photos[idx - 1].id); }
  else if (e.key === 'ArrowRight' && idx < photos.length - 1) { navigateArrow(photos[idx + 1].id); }
});

// Hash navigation
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

// Copy protection
document.addEventListener('contextmenu', (e) => {
  if (e.target.tagName === 'IMG') e.preventDefault();
});
document.addEventListener('dragstart', (e) => {
  if (e.target.tagName === 'IMG') e.preventDefault();
});

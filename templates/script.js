const flow = document.getElementById('flow');
let expandedId = null;
let isEnlarged = false;
const preloadCache = {};

// DOM references — built once, reused
let allGridItems = [];      // all grid-item DOM nodes
let dateDividers = {};       // { index: dividerElement } for date group headers
let expandedEl = null;       // current expanded view element
let lastClickedGridItem = null;

function getIdx() {
  return photos.findIndex(p => p.id === expandedId);
}

function isDesktop() {
  return window.innerWidth > 1100;
}

// --- Preloading ---

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
  [-1, 1].forEach(d => {
    const p = photos[idx + d];
    if (p) preloadImage(p.full);
  });
}

// --- Share button ---

function shareButtonHtml() {
  return `
    <button class="share-btn" title="Copy link">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
    </button>`;
}

function bindShareBtn(container, id) {
  const btn = container.querySelector('.share-btn');
  if (!btn) return;
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    const url = window.location.origin + window.location.pathname + '#' + id;
    navigator.clipboard.writeText(url).then(() => {
      btn.classList.add('copied');
      btn.setAttribute('title', 'Copied!');
      setTimeout(() => { btn.classList.remove('copied'); btn.setAttribute('title', 'Copy link'); }, 2000);
    });
  });
}

// --- Build all grid items ONCE ---

function init() {
  let lastGroup = '';

  allGridItems = photos.map((photo, i) => {
    const div = document.createElement('div');
    div.className = 'grid-item entering';
    div.dataset.itemId = photo.id;
    div.dataset.itemIndex = i;
    div.style.animationDelay = `${i * 0.035}s`;

    // Remove entering class after animation so re-parenting doesn't re-trigger
    div.addEventListener('animationend', () => {
      div.classList.remove('entering');
      div.style.animationDelay = '';
    }, { once: true });

    const src = isDesktop() ? photo.thumb : photo.full;
    div.innerHTML = `<img src="${src}" alt="${photo.id}" loading="lazy"><div class="meta">${photo.meta}</div>`;

    if (isDesktop()) {
      div.addEventListener('click', () => openFromGrid(photo.id));
    }

    // Track date group dividers
    if (photo.date_group && photo.date_group !== lastGroup) {
      lastGroup = photo.date_group;
      const divider = document.createElement('div');
      divider.className = 'date-divider';
      divider.textContent = photo.date_group;
      dateDividers[i] = divider;
    }

    return div;
  });

  renderFlat();
}

// --- Render: flat grid (no expanded) ---

function renderFlat() {
  flow.innerHTML = '';
  let currentSection = null;

  allGridItems.forEach((el, i) => {
    // Insert date divider before this item if needed
    if (dateDividers[i]) {
      if (currentSection && currentSection.children.length > 0) {
        flow.appendChild(currentSection);
      }
      flow.appendChild(dateDividers[i]);
      currentSection = null;
    }

    if (!currentSection) {
      currentSection = document.createElement('div');
      currentSection.className = 'grid-section';
    }
    currentSection.appendChild(el);
  });

  if (currentSection && currentSection.children.length > 0) {
    flow.appendChild(currentSection);
  }
}

// --- Render: split grid around expanded item ---

function renderSplit(itemIndex) {
  flow.innerHTML = '';
  let currentSection = null;
  let expandedInserted = false;

  allGridItems.forEach((el, i) => {
    // Date divider
    if (dateDividers[i]) {
      if (currentSection && currentSection.children.length > 0) {
        flow.appendChild(currentSection);
      }
      flow.appendChild(dateDividers[i]);
      currentSection = null;
    }

    // Before the expanded item — accumulate into grid
    if (i < itemIndex) {
      if (!currentSection) {
        currentSection = document.createElement('div');
        currentSection.className = 'grid-section';
      }
      currentSection.appendChild(el);
    }

    // The expanded item itself
    if (i === itemIndex) {
      // Flush grid before
      if (currentSection && currentSection.children.length > 0) {
        flow.appendChild(currentSection);
        currentSection = null;
      }
      // Insert expanded element
      if (expandedEl) {
        flow.appendChild(expandedEl);
      }
      expandedInserted = true;
    }

    // After the expanded item
    if (i > itemIndex) {
      if (!currentSection) {
        currentSection = document.createElement('div');
        currentSection.className = 'grid-section';
      }
      currentSection.appendChild(el);
    }
  });

  // Flush remaining
  if (currentSection && currentSection.children.length > 0) {
    flow.appendChild(currentSection);
  }
}

// --- Open / Close ---

function openFromGrid(id) {
  if (expandedEl) {
    removeExpanded();
  }

  expandedId = id;
  isEnlarged = false;
  history.replaceState(null, '', '#' + id);

  const idx = getIdx();
  const photo = photos[idx];
  if (!photo) return;

  lastClickedGridItem = allGridItems[idx];
  expandedEl = createExpandedPhoto(photo);
  renderSplit(idx);

  requestAnimationFrame(() => {
    if (expandedEl) expandedEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  preloadNeighbors(idx);
}

function removeExpanded() {
  if (expandedEl) {
    expandedEl.remove();
    expandedEl = null;
  }
}

function closeExpanded() {
  const scrollTarget = lastClickedGridItem;
  removeExpanded();
  expandedId = null;
  isEnlarged = false;
  lastClickedGridItem = null;
  history.replaceState(null, '', window.location.pathname);

  renderFlat();

  if (scrollTarget) {
    requestAnimationFrame(() => {
      scrollTarget.scrollIntoView({ behavior: 'instant', block: 'center' });
    });
  }
}

// --- Create expanded photo element ---

function createExpandedPhoto(photo) {
  const idx = getIdx();
  const hasPrev = idx > 0;
  const hasNext = idx < photos.length - 1;
  const el = document.createElement('div');
  el.className = 'expanded-photo';
  el.id = photo.id;

  const metaHtml = photo.meta + shareButtonHtml();

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
    <div class="meta-expanded">${metaHtml}</div>
  `;

  el.querySelector('.close-btn').addEventListener('click', (e) => { e.stopPropagation(); closeExpanded(); });
  bindShareBtn(el.querySelector('.meta-expanded'), photo.id);

  const stage = el.querySelector('#img-stage');
  stage.addEventListener('click', (e) => {
    e.stopPropagation();
    isEnlarged = !isEnlarged;
    stage.classList.toggle('enlarged', isEnlarged);
  });

  rebindArrows(el, idx);
  return el;
}

// --- Arrow navigation (crossfade in place) ---

function navigateArrow(id) {
  const photo = photos.find(p => p.id === id);
  if (!photo) return;

  expandedId = id;
  isEnlarged = false;
  history.replaceState(null, '', '#' + id);

  const idx = getIdx();
  const stage = expandedEl.querySelector('.img-stage');
  const imgFront = expandedEl.querySelector('#img-front');
  const imgBack = expandedEl.querySelector('#img-back');

  if (!imgFront || !imgBack || !stage) return;

  stage.classList.remove('enlarged');
  preloadImage(photo.full).then(() => {
    imgBack.src = photo.full;
    imgBack.style.opacity = '1';
    imgFront.style.opacity = '0';
    setTimeout(() => {
      imgFront.src = photo.full;
      imgFront.style.opacity = '1';
      imgBack.style.opacity = '0';

      expandedEl.id = photo.id;

      const meta = expandedEl.querySelector('.meta-expanded');
      if (meta) {
        meta.innerHTML = photo.meta + shareButtonHtml();
        bindShareBtn(meta, photo.id);
      }

      rebindArrows(expandedEl, idx);
      preloadNeighbors(idx);
    }, 260);
  });
}

// --- Arrow binding (scoped to container) ---

function rebindArrows(container, idx) {
  const prevBtn = container.querySelector('.nav-arrow[data-dir="prev"]');
  const nextBtn = container.querySelector('.nav-arrow[data-dir="next"]');
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

// --- Keyboard ---

document.addEventListener('keydown', (e) => {
  if (!expandedId) return;
  const idx = getIdx();
  if (e.key === 'Escape') {
    if (isEnlarged) { isEnlarged = false; const s = document.getElementById('img-stage'); if (s) s.classList.remove('enlarged'); }
    else { closeExpanded(); }
  } else if (e.key === 'ArrowLeft' && idx > 0) { navigateArrow(photos[idx - 1].id); }
  else if (e.key === 'ArrowRight' && idx < photos.length - 1) { navigateArrow(photos[idx + 1].id); }
});

// --- Init ---

init();

// Hash navigation on load
const hash = window.location.hash.slice(1);
if (hash && isDesktop()) {
  const idx = photos.findIndex(p => p.id === hash);
  if (idx !== -1) {
    const photo = photos[idx];
    expandedId = photo.id;
    lastClickedGridItem = allGridItems[idx];
    expandedEl = createExpandedPhoto(photo);
    renderSplit(idx);
    requestAnimationFrame(() => {
      if (expandedEl) expandedEl.scrollIntoView({ block: 'start' });
    });
  }
} else if (hash && !isDesktop()) {
  // Mobile: scroll to the photo in feed
  requestAnimationFrame(() => {
    const el = document.getElementById(hash);
    if (el) el.scrollIntoView({ block: 'start' });
  });
}

// --- Copy protection ---

document.addEventListener('contextmenu', (e) => {
  if (e.target.tagName === 'IMG') e.preventDefault();
});
document.addEventListener('dragstart', (e) => {
  if (e.target.tagName === 'IMG') e.preventDefault();
});

// --- Scroll position persistence ---

const SCROLL_KEY = 'street_scroll_pos';

// Restore on load (only if no hash)
if (!hash) {
  try {
    const saved = localStorage.getItem(SCROLL_KEY);
    if (saved) {
      const pos = parseInt(saved, 10);
      requestAnimationFrame(() => {
        setTimeout(() => { window.scrollTo(0, pos); }, 100);
      });
    }
  } catch (e) {}
}

// Save on scroll (debounced)
let scrollTimer = null;
window.addEventListener('scroll', () => {
  if (scrollTimer) clearTimeout(scrollTimer);
  scrollTimer = setTimeout(() => {
    try {
      localStorage.setItem(SCROLL_KEY, String(window.scrollY));
    } catch (e) {}
  }, 200);
}, { passive: true });

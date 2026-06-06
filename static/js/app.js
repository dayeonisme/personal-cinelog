/* ═══════════════════════════════════════════════════════════
   CINELOG · Frontend App
   ═══════════════════════════════════════════════════════════ */

'use strict';

// ── State ─────────────────────────────────────────────────────
const state = {
  currentPage: 'home',
  language: 'ko',
  registerType: 'review',   // 'review' | 'watchlist'
  editingEntryId: null,
  selectedMovie: null,
  pendingDeleteId: null,
  // pagination
  homeEntries: [], homePage: 1, homeTotal: 0,
  reviewEntries: [], reviewPage: 1, reviewTotal: 0,
  watchlistEntries: [], watchlistPage: 1, watchlistTotal: 0,
  // filters
  homeFilter: 'all', homeSort: 'newest',
  reviewFilter: 'all', reviewSort: 'newest',
  watchlistFilter: 'all',
  watchlistSort: 'newest',
  homeSearch: '', homeSearchField: 'all',
  reviewSearch: '', reviewSearchField: 'all',
  watchlistSearch: '', watchlistSearchField: 'all',
  // templates
  ratingTemplates: [],
  commentTemplates: [],
};

// ── Helpers ────────────────────────────────────────────────────
const API = async (path, opts = {}) => {
  const r = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...opts });
  return r.json();
};

const $ = id => document.getElementById(id);
const fmtDate = iso => iso ? new Date(iso).toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' }) : '';

function renderStars(value, max = 5) {
  let html = '';
  for (let i = 1; i <= max; i++) {
    if (value >= i) html += '★';
    else if (value >= i - 0.5) html += '½';
    else html += '☆';
  }
  return html;
}

function showModal(id) { $(id).style.display = 'flex'; }
function hideModal(id) { $(id).style.display = 'none'; }

// ── Navigation ─────────────────────────────────────────────────
function navigateTo(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.gnb-btn').forEach(b => b.classList.remove('active'));
  $(`page-${page}`).classList.add('active');
  const btn = document.querySelector(`.gnb-btn[data-page="${page}"]`);
  if (btn) btn.classList.add('active');
  state.currentPage = page;

  if (page === 'home') loadHome(true);
  else if (page === 'review') loadReviews(true);
  else if (page === 'watchlist') loadWatchlist(true);
}

// ══════════════════════════════════════════════════════════════
// HOME PAGE
// ══════════════════════════════════════════════════════════════
async function loadHome(reset = false) {
  if (reset) { state.homePage = 1; state.homeEntries = []; }
  $('home-loading').style.display = 'block';

  const params = new URLSearchParams({
    page: state.homePage,
    per_page: 40,
    sort: state.homeSort,
    scope: 'home',
    lang: state.language,
  });
  if (state.homeFilter !== 'all') params.set('type', state.homeFilter);
  if (state.homeSearch) {
    params.set('search', state.homeSearch);
    params.set('search_field', state.homeSearchField);
  }

  const data = await API(`/api/entries?${params}`);
  $('home-loading').style.display = 'none';

  if (reset) state.homeEntries = data.items || [];
  else state.homeEntries.push(...(data.items || []));
  state.homeTotal = data.total || 0;

  renderHomeGrid();
}

function renderHomeGrid() {
  const grid = $('home-grid');
  if (state.homeEntries.length === 0) {
    grid.innerHTML = '<div class="empty-state"><div class="empty-icon">🎬</div>등록된 영화가 없습니다.</div>';
    return;
  }
  grid.innerHTML = state.homeEntries.map(entry => {
    const m = entry.movie;
    const typeClass = entry.entry_type === 'review' ? 'type-review' : 'type-watchlist';
    const typeBadge = entry.entry_type === 'review' ? '평가' : '보고싶어요';
    const poster = m.poster_url
      ? `<img class="movie-card-poster" src="${m.poster_url}" alt="${escHtml(m.title)}" loading="lazy">`
      : `<div class="movie-card-no-poster">
          <span class="no-poster-kicker">NO POSTER</span>
          <span class="no-poster-title">${escHtml(m.title)}</span>
        </div>`;
    const year = m.year ? `(${m.year})` : '';
    const director = m.director && m.director !== 'N/A' ? m.director : '';
    return `
      <div class="movie-card ${typeClass}" data-entry-id="${entry.id}" onclick="handleHomeCardClick(${entry.id}, '${entry.entry_type}')">
        ${poster}
        <span class="movie-card-type-badge">${typeBadge}</span>
        <div class="movie-card-overlay">
          <div class="movie-card-overlay-title">${escHtml(m.title)} ${year}</div>
          ${director ? `<div class="movie-card-overlay-sub">${escHtml(director)}</div>` : ''}
        </div>
      </div>`;
  }).join('');
}

function handleHomeCardClick(entryId, type) {
  if (type === 'review') navigateTo('review');
  else navigateTo('watchlist');
  // Could highlight the card — for now just navigate
}

// ══════════════════════════════════════════════════════════════
// REVIEW PAGE
// ══════════════════════════════════════════════════════════════
async function loadReviews(reset = false) {
  if (reset) { state.reviewPage = 1; state.reviewEntries = []; }
  $('review-loading').style.display = 'block';

  const params = new URLSearchParams({
    type: 'review',
    page: state.reviewPage,
    per_page: 20,
    sort: state.reviewSort,
    lang: state.language,
  });
  if (state.reviewFilter !== 'all') params.set('watch_status', state.reviewFilter);
  if (state.reviewSearch) {
    params.set('search', state.reviewSearch);
    params.set('search_field', state.reviewSearchField);
  }

  const data = await API(`/api/entries?${params}`);
  $('review-loading').style.display = 'none';

  if (reset) state.reviewEntries = data.items || [];
  else state.reviewEntries.push(...(data.items || []));
  state.reviewTotal = data.total || 0;

  renderReviewList();
  $('review-load-more').style.display =
    state.reviewEntries.length < state.reviewTotal ? 'block' : 'none';
}

function loadMoreReviews() {
  state.reviewPage++;
  loadReviews(false);
}

function renderReviewList() {
  const list = $('review-list');
  if (state.reviewEntries.length === 0) {
    list.innerHTML = '<div class="empty-state"><div class="empty-icon">✒</div>등록된 평가가 없습니다.</div>';
    return;
  }
  list.innerHTML = state.reviewEntries.map(entry => buildEntryCard(entry)).join('');
}

// ══════════════════════════════════════════════════════════════
// WATCHLIST PAGE
// ══════════════════════════════════════════════════════════════
async function loadWatchlist(reset = false) {
  if (reset) { state.watchlistPage = 1; state.watchlistEntries = []; }
  $('watchlist-loading').style.display = 'block';

  const params = new URLSearchParams({
    type: 'watchlist',
    page: state.watchlistPage,
    per_page: 20,
    sort: state.watchlistSort,
    lang: state.language,
  });
  if (state.watchlistFilter !== 'all') params.set('watchlist_kind', state.watchlistFilter);
  if (state.watchlistSearch) {
    params.set('search', state.watchlistSearch);
    params.set('search_field', state.watchlistSearchField);
  }

  const data = await API(`/api/entries?${params}`);
  $('watchlist-loading').style.display = 'none';

  if (reset) state.watchlistEntries = data.items || [];
  else state.watchlistEntries.push(...(data.items || []));
  state.watchlistTotal = data.total || 0;

  renderWatchlistList();
  $('watchlist-load-more').style.display =
    state.watchlistEntries.length < state.watchlistTotal ? 'block' : 'none';
}

function loadMoreWatchlist() {
  state.watchlistPage++;
  loadWatchlist(false);
}

function renderWatchlistList() {
  const list = $('watchlist-list');
  if (state.watchlistEntries.length === 0) {
    list.innerHTML = '<div class="empty-state"><div class="empty-icon">★</div>등록된 보고싶어요가 없습니다.</div>';
    return;
  }
  list.innerHTML = state.watchlistEntries.map(entry => buildEntryCard(entry)).join('');
}

// ── Entry Card Builder ──────────────────────────────────────────
function buildEntryCard(entry) {
  const m = entry.movie;
  const isReview = entry.entry_type === 'review';
  const typeClass = isReview ? 'type-review' : 'type-watchlist';
  const year = m.year ? `(${m.year})` : '';
  const director = m.director && m.director !== 'N/A' ? m.director : '';

  const poster = m.poster_url
    ? `<img class="entry-poster" src="${m.poster_url}" alt="${escHtml(m.title)}" loading="lazy">`
    : `<div class="entry-poster-placeholder">
        <span>NO POSTER</span>
        <strong>${escHtml(m.title)}</strong>
      </div>`;

  const statusBadgeMap = { completed: '완료', in_progress: '진행중', stopped: '중단' };
  const statusBadge = entry.watch_status
    ? `<span class="entry-status-badge status-${entry.watch_status}">${statusBadgeMap[entry.watch_status] || entry.watch_status}</span>`
    : '';
  const watchlistBadge = !isReview && entry.watchlist_label
    ? `<span class="entry-status-badge watchlist-kind-${entry.watchlist_kind}">${escHtml(entry.watchlist_label)}</span>`
    : '';

  // Ratings
  let ratingsHtml = '';
  if (entry.ratings && entry.ratings.length > 0) {
    const chips = entry.ratings.map(r => {
      const stars = renderStars(r.value || 0);
      return `<div class="rating-chip">
        <span class="rating-chip-name">${r.emoji || '⭐'} ${escHtml(r.name)}</span>
        <span class="rating-chip-stars">${stars}</span>
        <span class="rating-chip-value">${r.value != null ? r.value.toFixed(1) : '–'}</span>
      </div>`;
    }).join('');
    ratingsHtml = `<div class="ratings-row">${chips}</div>`;
  }

  // Comments
  let commentsHtml = '';
  if (entry.comments && entry.comments.length > 0) {
    const blocks = entry.comments.map(c => {
      const md = (c.content && typeof marked !== 'undefined')
        ? `<div class="comment-module-content md-content">${marked.parse(c.content || '')}</div>`
        : `<div class="comment-module-content">${escHtml(c.content || '')}</div>`;
      const imgs = (c.images && c.images.length > 0)
        ? `<div class="comment-module-images">${c.images.map(u => `<img src="${u}" alt="" loading="lazy">`).join('')}</div>`
        : '';
      return `<div class="comment-module-block">
        <div class="comment-module-name">${escHtml(c.name)}</div>
        ${md}
        ${imgs}
      </div>`;
    }).join('');
    commentsHtml = `<div class="comment-modules">${blocks}</div>`;
  }

  return `
    <div class="entry-card ${typeClass}" data-entry-id="${entry.id}">
      <div class="entry-card-inner">
        ${poster}
        <div class="entry-body">
          <div class="entry-header">
            <div class="entry-title-block">
              <div class="entry-movie-name">${escHtml(m.title)} ${year}</div>
              <div class="entry-meta-line">
                ${director ? `<span>${escHtml(director)}</span><span class="separator">·</span>` : ''}
                ${m.genre && m.genre !== 'N/A' ? `<span>${escHtml(m.genre)}</span>` : ''}
              </div>
              <div class="entry-date-line">
                등록 ${fmtDate(entry.created_at)}
                ${entry.updated_at !== entry.created_at ? ` · 수정 ${fmtDate(entry.updated_at)}` : ''}
              </div>
              ${statusBadge}
              ${watchlistBadge}
            </div>
          </div>
          ${ratingsHtml}
          ${commentsHtml}
        </div>
      </div>
      <!-- Kebab -->
      <button class="kebab-btn" onclick="toggleKebab(event, ${entry.id})">···</button>
      <div class="kebab-menu" id="kebab-${entry.id}">
        <button onclick="editEntry(${entry.id})">수정</button>
        <button class="danger" onclick="confirmDelete(${entry.id})">삭제</button>
      </div>
    </div>`;
}

// ── Kebab Menu ──────────────────────────────────────────────────
function toggleKebab(e, entryId) {
  e.stopPropagation();
  document.querySelectorAll('.kebab-menu.open').forEach(m => {
    if (m.id !== `kebab-${entryId}`) m.classList.remove('open');
  });
  $(`kebab-${entryId}`).classList.toggle('open');
}
document.addEventListener('click', () => {
  document.querySelectorAll('.kebab-menu.open').forEach(m => m.classList.remove('open'));
});

// ── Delete ──────────────────────────────────────────────────────
function confirmDelete(entryId) {
  state.pendingDeleteId = entryId;
  showModal('modal-delete');
}

$('modal-delete-cancel').onclick = () => hideModal('modal-delete');
$('modal-delete-confirm').onclick = async () => {
  hideModal('modal-delete');
  await API(`/api/entries/${state.pendingDeleteId}`, { method: 'DELETE' });
  // Refresh current page
  if (state.currentPage === 'review') loadReviews(true);
  else if (state.currentPage === 'watchlist') loadWatchlist(true);
  else loadHome(true);
};

$('modal-name-error-close').onclick = () => hideModal('modal-name-error');

// ══════════════════════════════════════════════════════════════
// REGISTER PAGE
// ══════════════════════════════════════════════════════════════

function openRegisterPage(type, entryData = null) {
  state.registerType = type;
  state.editingEntryId = entryData ? entryData.id : null;
  state.selectedMovie = null;

  $('register-title').textContent = entryData
    ? (type === 'review' ? '평가 수정' : '보고싶어요 수정')
    : (type === 'review' ? '평가 등록' : '보고싶어요 등록');

  // Show/hide sections
  $('watch-status-section').style.display = type === 'review' ? 'block' : 'none';
  $('ratings-section').style.display = type === 'review' ? 'block' : 'none';

  // Reset steps
  showStep(1);
  resetStep2();

  if (entryData) {
    // Pre-fill from existing entry
    state.selectedMovie = entryData.movie;
    setSelectedMovieUI(entryData.movie);
    $('step1-next-btn').disabled = false;

    // Fill step 2
    if (type === 'review') {
      document.querySelectorAll('.status-btn').forEach(b => b.classList.remove('active'));
      const sb = document.querySelector(`.status-btn[data-status="${entryData.watch_status}"]`);
      if (sb) sb.classList.add('active');

      // Ratings
      entryData.ratings.forEach(r => {
        if (r.is_default) {
          // Update default rating value
          const first = document.querySelector('#ratings-modules .module-box');
          if (first) {
            const input = first.querySelector('.star-rating-hidden');
            if (input) { input.value = r.value; updateStarDisplay(first, r.value); }
          }
        } else {
          addRatingModule({ name: r.name, emoji: r.emoji, value: r.value });
        }
      });

      // Comments
      entryData.comments.forEach(c => {
        if (c.is_default) {
          const first = document.querySelector('#comments-modules .module-box');
          if (first) {
            const ta = first.querySelector('.comment-textarea');
            if (ta) ta.value = c.content || '';
          }
        } else {
          addCommentModule({ name: c.name, content: c.content, images: c.images });
        }
      });
    } else {
      // watchlist
      entryData.comments.forEach(c => {
        if (c.is_default) {
          const first = document.querySelector('#comments-modules .module-box');
          if (first) {
            const ta = first.querySelector('.comment-textarea');
            if (ta) ta.value = c.content || '';
          }
        } else {
          addCommentModule({ name: c.name, content: c.content, images: c.images });
        }
      });
    }
  }

  navigateTo('register');
}

function showStep(n) {
  document.querySelectorAll('.register-step').forEach(s => s.classList.remove('active'));
  $(`step-${n}`).classList.add('active');
}

function resetStep2() {
  // Reset status
  document.querySelectorAll('.status-btn').forEach(b => b.classList.remove('active'));
  document.querySelector('.status-btn[data-status="completed"]').classList.add('active');

  // Reset ratings
  $('ratings-modules').innerHTML = '';
  addDefaultRatingModule();

  // Reset comments
  $('comments-modules').innerHTML = '';
  addDefaultCommentModule();
}

// ── Movie Search ────────────────────────────────────────────────
$('reg-movie-search-btn').onclick = searchMovieForReg;
$('reg-movie-search').addEventListener('keydown', e => { if (e.key === 'Enter') searchMovieForReg(); });

async function searchMovieForReg() {
  const q = $('reg-movie-search').value.trim();
  if (!q) return;
  $('reg-search-results').innerHTML = '<div class="loading-indicator">검색 중...</div>';
  const results = await API(`/api/search/movies?q=${encodeURIComponent(q)}`);
  if (results.error) {
    $('reg-search-results').innerHTML = `<div class="empty-state">${escHtml(results.error)}</div>`;
    return;
  }
  if (!results.length) {
    $('reg-search-results').innerHTML = '<div class="empty-state">검색 결과가 없습니다.</div>';
    return;
  }
  $('reg-search-results').innerHTML = results.map(m => {
    const poster = m.poster_url
      ? `<img class="search-result-poster" src="${m.poster_url}" alt="" loading="lazy">`
      : `<div class="search-result-poster-placeholder">?</div>`;
    return `<div class="search-result-item" onclick="selectMovieFromSearch('${m.imdb_id}')">
      ${poster}
      <div class="search-result-info">
        <h4>${escHtml(m.title)}</h4>
        <p>${m.year || ''}</p>
      </div>
    </div>`;
  }).join('');
}

async function selectMovieFromSearch(imdbId) {
  $('reg-search-results').innerHTML = '<div class="loading-indicator">영화 정보 로딩 중...</div>';
  const movie = await API(`/api/search/movies/${imdbId}`);
  if (movie.error) {
    $('reg-search-results').innerHTML = `<div class="empty-state">${escHtml(movie.error)}</div>`;
    return;
  }
  state.selectedMovie = movie;
  setSelectedMovieUI(movie);
  $('reg-search-results').innerHTML = '';
  $('step1-next-btn').disabled = false;
}

function setSelectedMovieUI(movie) {
  $('reg-selected-movie').style.display = 'flex';
  $('reg-poster').src = movie.poster_url || '';
  $('reg-poster').style.display = movie.poster_url ? 'block' : 'none';
  $('reg-title').textContent = `${movie.title}${movie.year ? ` (${movie.year})` : ''}`;
  $('reg-year-director').textContent = movie.director && movie.director !== 'N/A' ? `감독: ${movie.director}` : '';
  $('reg-actors').textContent = movie.actors && movie.actors !== 'N/A' ? `출연: ${movie.actors}` : '';
  $('reg-genre').textContent = movie.genre && movie.genre !== 'N/A' ? movie.genre : '';
}

$('reg-reselect-btn').onclick = () => {
  state.selectedMovie = null;
  $('reg-selected-movie').style.display = 'none';
  $('step1-next-btn').disabled = true;
  $('reg-movie-search').value = '';
};

$('step1-next-btn').onclick = async () => {
  // Load templates before step 2
  const [rt, ct] = await Promise.all([
    API('/api/templates/ratings'),
    API('/api/templates/comments'),
  ]);
  state.ratingTemplates = rt;
  state.commentTemplates = ct;
  showStep(2);
};

$('step2-back-btn').onclick = () => showStep(1);

// ── Watch Status ────────────────────────────────────────────────
document.querySelectorAll('.status-btn').forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll('.status-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  };
});

// ══════════════════════════════════════════════════════════════
// RATING MODULES
// ══════════════════════════════════════════════════════════════

function addDefaultRatingModule() {
  const wrap = $('ratings-modules');
  const box = buildRatingModuleBox({ name: '평점', emoji: '⭐', value: 0, isDefault: true });
  wrap.appendChild(box);
}

function addRatingModule(opts = {}) {
  const wrap = $('ratings-modules');
  const box = buildRatingModuleBox({ ...opts, isDefault: false });
  wrap.appendChild(box);
}

function buildRatingModuleBox({ name = '', emoji = '⭐', value = 0, isDefault = false }) {
  const box = document.createElement('div');
  box.className = 'module-box';
  box.dataset.isDefault = isDefault;

  let headerHtml;
  if (isDefault) {
    headerHtml = `
      <div class="module-header">
        <span class="module-name-label">⭐ 평점</span>
      </div>`;
  } else {
    // Build dropdown options from templates
    const templateOpts = state.ratingTemplates
      .filter(t => t.name !== '평점')
      .map(t => `<option value="${escAttr(t.name)}" data-emoji="${escAttr(t.emoji)}">${escHtml(t.name)}</option>`)
      .join('');
    headerHtml = `
      <div class="module-header">
        <span class="module-name-label">별점명</span>
        <select class="module-name-select rating-name-select">
          <option value="__direct__">직접 입력</option>
          ${templateOpts}
        </select>
        <input class="module-name-input rating-name-input" type="text" placeholder="별점 이름" value="${escAttr(name)}">
        <input class="module-emoji-input rating-emoji-input" type="text" value="${escAttr(emoji)}" maxlength="2" placeholder="🌟">
        <button class="module-remove-btn" onclick="this.closest('.module-box').remove()">×</button>
      </div>`;
  }

  const starHtml = buildStarInput(value);
  box.innerHTML = `${headerHtml}${starHtml}`;

  if (!isDefault) {
    // Select listener
    const sel = box.querySelector('.rating-name-select');
    const nameInput = box.querySelector('.rating-name-input');
    const emojiInput = box.querySelector('.rating-emoji-input');
    if (sel) {
      sel.value = name ? name : '__direct__';
      sel.addEventListener('change', () => {
        if (sel.value !== '__direct__') {
          const opt = sel.options[sel.selectedIndex];
          nameInput.value = sel.value;
          emojiInput.value = opt.dataset.emoji || '⭐';
        } else {
          nameInput.value = '';
        }
      });
    }
  }

  // Init star interaction
  initStarInteraction(box);
  updateStarDisplay(box, value);

  return box;
}

function buildStarInput(value = 0) {
  const stars = [];
  for (let i = 1; i <= 5; i++) {
    stars.push(`<button type="button" class="star-btn" data-index="${i}" data-half-index="${i - 0.5}">☆</button>`);
  }
  return `
    <div class="star-rating-input">
      <div class="stars-interactive">${stars.join('')}</div>
      <span class="star-value-display">${value.toFixed(1)}</span>
      <input type="hidden" class="star-rating-hidden" value="${value}">
    </div>`;
}

function initStarInteraction(box) {
  const starsWrap = box.querySelector('.stars-interactive');
  const display = box.querySelector('.star-value-display');
  const hidden = box.querySelector('.star-rating-hidden');

  starsWrap.addEventListener('mousemove', e => {
    const btn = e.target.closest('.star-btn');
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    const half = e.clientX < rect.left + rect.width / 2;
    const val = half ? parseFloat(btn.dataset.halfIndex) : parseFloat(btn.dataset.index);
    updateStarDisplay(box, val);
    display.textContent = val.toFixed(1);
  });
  starsWrap.addEventListener('mouseleave', () => {
    updateStarDisplay(box, parseFloat(hidden.value));
    display.textContent = parseFloat(hidden.value).toFixed(1);
  });
  starsWrap.addEventListener('click', e => {
    const btn = e.target.closest('.star-btn');
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    const half = e.clientX < rect.left + rect.width / 2;
    const val = half ? parseFloat(btn.dataset.halfIndex) : parseFloat(btn.dataset.index);
    hidden.value = val;
    display.textContent = val.toFixed(1);
    updateStarDisplay(box, val);
  });
}

function updateStarDisplay(box, value) {
  const btns = box.querySelectorAll('.star-btn');
  btns.forEach((btn, i) => {
    const full = i + 1;
    const half = i + 0.5;
    if (value >= full) {
      btn.textContent = '★';
      btn.classList.add('filled');
      btn.classList.remove('half-filled');
    } else if (value >= half) {
      btn.textContent = '⯨';
      btn.classList.add('half-filled');
      btn.classList.remove('filled');
    } else {
      btn.textContent = '☆';
      btn.classList.remove('filled', 'half-filled');
    }
  });
}

$('add-rating-btn').onclick = () => addRatingModule();

// ══════════════════════════════════════════════════════════════
// COMMENT MODULES
// ══════════════════════════════════════════════════════════════

function addDefaultCommentModule() {
  const wrap = $('comments-modules');
  const box = buildCommentModuleBox({ name: '감상평', content: '', isDefault: true });
  wrap.appendChild(box);
}

function addCommentModule(opts = {}) {
  const wrap = $('comments-modules');
  const box = buildCommentModuleBox({ ...opts, isDefault: false });
  wrap.appendChild(box);
}

function buildCommentModuleBox({ name = '', content = '', images = [], isDefault = false }) {
  const box = document.createElement('div');
  box.className = 'module-box';
  box.dataset.isDefault = isDefault;
  box.dataset.images = JSON.stringify(images);

  let headerHtml;
  if (isDefault) {
    headerHtml = `
      <div class="module-header">
        <span class="module-name-label">📝 감상평</span>
      </div>`;
  } else {
    const templateOpts = state.commentTemplates
      .filter(t => t.name !== '감상평')
      .map(t => `<option value="${escAttr(t.name)}">${escHtml(t.name)}</option>`)
      .join('');
    headerHtml = `
      <div class="module-header">
        <span class="module-name-label">코멘트명</span>
        <select class="module-name-select comment-name-select">
          <option value="__direct__">직접 입력</option>
          ${templateOpts}
        </select>
        <input class="module-name-input comment-name-input" type="text" placeholder="코멘트 이름" value="${escAttr(name)}">
        <button class="module-remove-btn" onclick="this.closest('.module-box').remove()">×</button>
      </div>`;
  }

  // Image previews
  const imgPreviews = images.map(url => `
    <div class="image-preview-wrap">
      <img src="${url}" alt="">
      <button class="remove-img-btn" onclick="removeCommentImage(this, '${escAttr(url)}')">×</button>
    </div>`).join('');

  box.innerHTML = `${headerHtml}
    <textarea class="comment-textarea" placeholder="${isDefault ? '감상평을 작성하세요... (마크다운 지원)' : '내용을 입력하세요...'}">${escHtml(content)}</textarea>
    <div class="comment-image-section">
      <div class="comment-image-label">이미지</div>
      <div class="comment-image-previews">${imgPreviews}</div>
      <button type="button" class="image-upload-btn" onclick="triggerImageUpload(this)">+ 이미지 첨부</button>
      <input type="file" class="hidden-file-input" accept="image/*" style="display:none" onchange="handleImageUpload(this)">
    </div>`;

  if (!isDefault) {
    const sel = box.querySelector('.comment-name-select');
    const nameInput = box.querySelector('.comment-name-input');
    if (sel) {
      sel.value = name ? name : '__direct__';
      sel.addEventListener('change', () => {
        if (sel.value !== '__direct__') nameInput.value = sel.value;
        else nameInput.value = '';
      });
    }
  }

  return box;
}

$('add-comment-btn').onclick = () => addCommentModule();

// ── Image Upload ────────────────────────────────────────────────
function triggerImageUpload(btn) {
  btn.nextElementSibling.click();
}

async function handleImageUpload(input) {
  const file = input.files[0];
  if (!file) return;
  const box = input.closest('.module-box');
  const formData = new FormData();
  formData.append('file', file);
  const resp = await fetch('/api/upload', { method: 'POST', body: formData });
  const data = await resp.json();
  if (data.url) {
    const previews = box.querySelector('.comment-image-previews');
    const wrap = document.createElement('div');
    wrap.className = 'image-preview-wrap';
    wrap.innerHTML = `<img src="${data.url}" alt=""><button class="remove-img-btn" onclick="removeCommentImage(this, '${escAttr(data.url)}')">×</button>`;
    previews.appendChild(wrap);
    // Update stored images
    const imgs = JSON.parse(box.dataset.images || '[]');
    imgs.push(data.url);
    box.dataset.images = JSON.stringify(imgs);
  }
  input.value = '';
}

function removeCommentImage(btn, url) {
  const box = btn.closest('.module-box');
  btn.closest('.image-preview-wrap').remove();
  const imgs = JSON.parse(box.dataset.images || '[]').filter(u => u !== url);
  box.dataset.images = JSON.stringify(imgs);
}

// ══════════════════════════════════════════════════════════════
// SUBMIT ENTRY
// ══════════════════════════════════════════════════════════════
$('submit-entry-btn').onclick = submitEntry;

async function submitEntry() {
  if (!state.selectedMovie) return;
  const type = state.registerType;

  const watchStatus = type === 'review'
    ? (document.querySelector('.status-btn.active')?.dataset.status || 'completed')
    : null;

  // Collect ratings
  const ratings = [];
  if (type === 'review') {
    document.querySelectorAll('#ratings-modules .module-box').forEach((box, i) => {
      const isDefault = box.dataset.isDefault === 'true';
      const name = isDefault ? '평점' : (box.querySelector('.rating-name-input')?.value || '').trim();
      if (!name && !isDefault) return;
      const emoji = isDefault ? '⭐' : (box.querySelector('.rating-emoji-input')?.value || '⭐');
      const value = parseFloat(box.querySelector('.star-rating-hidden')?.value || '0');
      ratings.push({ name, emoji, value, is_default: isDefault, order: i });
    });
  }

  // Collect comments
  const comments = [];
  document.querySelectorAll('#comments-modules .module-box').forEach((box, i) => {
    const isDefault = box.dataset.isDefault === 'true';
    const name = isDefault ? '감상평' : (box.querySelector('.comment-name-input')?.value || '').trim();
    if (!name && !isDefault) return;
    // Validate reserved names for custom modules
    if (!isDefault && (name === '평점' || name === '감상평')) {
      showModal('modal-name-error');
      return;
    }
    const content = box.querySelector('.comment-textarea')?.value || '';
    const images = JSON.parse(box.dataset.images || '[]');
    comments.push({ name, content, images, is_default: isDefault, order: i });
  });

  const payload = {
    movie: state.selectedMovie,
    entry_type: type,
    watch_status: watchStatus,
    ratings,
    comments,
  };

  let result;
  if (state.editingEntryId) {
    result = await API(`/api/entries/${state.editingEntryId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  } else {
    result = await API('/api/entries', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  if (result.id) {
    // Navigate back and refresh
    if (type === 'review') {
      navigateTo('review');
    } else {
      navigateTo('watchlist');
    }
  }
}

// ── Edit Entry ────────────────────────────────────────────────
async function editEntry(entryId) {
  const entry = await API(`/api/entries/${entryId}`);
  openRegisterPage(entry.entry_type, entry);
}

// ── Back button ─────────────────────────────────────────────────
$('register-back-btn').onclick = () => {
  if (state.registerType === 'review') navigateTo('review');
  else navigateTo('watchlist');
};

// ══════════════════════════════════════════════════════════════
// GNB & FABs
// ══════════════════════════════════════════════════════════════
document.querySelectorAll('.gnb-btn').forEach(btn => {
  btn.onclick = () => {
    const page = btn.dataset.page;
    navigateTo(page);
  };
});

$('review-fab').onclick = () => openRegisterPage('review');
$('watchlist-fab').onclick = () => openRegisterPage('watchlist');

function refreshCurrentPage() {
  if (state.currentPage === 'home') loadHome(true);
  else if (state.currentPage === 'review') loadReviews(true);
  else if (state.currentPage === 'watchlist') loadWatchlist(true);
}

document.querySelectorAll('.lang-toggle-btn').forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll('.lang-toggle-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.language = btn.dataset.lang;
    refreshCurrentPage();
  };
});

// ── Sort & Filter Listeners ──────────────────────────────────────

// Home filters
document.querySelectorAll('#page-home .filter-btn').forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll('#page-home .filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.homeFilter = btn.dataset.filter;
    loadHome(true);
  };
});
$('home-sort').onchange = () => { state.homeSort = $('home-sort').value; loadHome(true); };
$('home-search-btn').onclick = () => {
  state.homeSearch = $('home-search-input').value.trim();
  state.homeSearchField = $('home-search-field').value;
  loadHome(true);
};
$('home-search-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') { $('home-search-btn').click(); }
});

// Review filters
document.querySelectorAll('#page-review .filter-btn').forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll('#page-review .filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.reviewFilter = btn.dataset.filter;
    loadReviews(true);
  };
});
$('review-sort').onchange = () => { state.reviewSort = $('review-sort').value; loadReviews(true); };
$('review-search-btn').onclick = () => {
  state.reviewSearch = $('review-search-input').value.trim();
  state.reviewSearchField = $('review-search-field').value;
  loadReviews(true);
};
$('review-search-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') { $('review-search-btn').click(); }
});

// Watchlist
document.querySelectorAll('#page-watchlist .filter-btn').forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll('#page-watchlist .filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.watchlistFilter = btn.dataset.filter;
    loadWatchlist(true);
  };
});
$('watchlist-sort').onchange = () => { state.watchlistSort = $('watchlist-sort').value; loadWatchlist(true); };
$('watchlist-search-btn').onclick = () => {
  state.watchlistSearch = $('watchlist-search-input').value.trim();
  state.watchlistSearchField = $('watchlist-search-field').value;
  loadWatchlist(true);
};
$('watchlist-search-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') { $('watchlist-search-btn').click(); }
});

// ══════════════════════════════════════════════════════════════
// UTILS
// ══════════════════════════════════════════════════════════════
function escHtml(s) {
  if (!s) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
function escAttr(s) { return escHtml(s); }

// ══════════════════════════════════════════════════════════════
// INIT
// ══════════════════════════════════════════════════════════════
loadHome(true);

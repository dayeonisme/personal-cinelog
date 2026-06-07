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
  // hashtags
  hashtagPool: [],
  selectedHashtags: [],
};

// ── Helpers ────────────────────────────────────────────────────
const API = async (path, opts = {}) => {
  const r = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...opts });
  return r.json();
};

const $ = id => document.getElementById(id);
const fmtDate = iso => iso ? new Date(iso).toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' }) : '';

// 레이어 방식으로 별을 그려 0.5점 단위 반채움을 정확히 표현 (깨진 이모지 문제 해결)
function renderStarsHtml(value, max = 5) {
  let html = '';
  for (let i = 1; i <= max; i++) {
    let pct = 0;
    let halfCls = '';
    if (value >= i) pct = 100;
    else if (value >= i - 0.5) { pct = 50; halfCls = ' star-disp-half'; }
    html += `<span class="star-disp${halfCls}"><span class="star-disp-bg">★</span><span class="star-disp-fg" style="width:${pct}%">★</span></span>`;
  }
  return html;
}

function fmtRuntime(runtime) {
  if (!runtime) return '';
  const minutes = parseInt(String(runtime).replace(/[^0-9]/g, ''), 10);
  if (!minutes || isNaN(minutes)) return '';
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h && m) return `${h}시간 ${m}분`;
  if (h) return `${h}시간`;
  return `${m}분`;
}

function defaultRatingOf(entry) {
  if (!entry || !entry.ratings) return null;
  const d = entry.ratings.find(r => r.is_default) || entry.ratings[0];
  return (d && d.value != null) ? d.value : null;
}

// 왓챠에서 마이그레이션된 평점명에서 "왓챠" 표기를 제거
function displayRatingName(name) {
  if (!name) return name;
  return name.replace(/^왓챠\s*/, '').trim() || '평점';
}

function buildRatingsHtml(ratings) {
  if (!ratings || ratings.length === 0) return '';
  const chips = ratings.map(r => {
    const stars = renderStarsHtml(r.value || 0);
    return `<div class="rating-chip">
      <span class="rating-chip-name">${r.emoji || '⭐'} ${escHtml(displayRatingName(r.name))}</span>
      <span class="rating-chip-stars">${stars}</span>
      <span class="rating-chip-value">${r.value != null ? r.value.toFixed(1) : '–'}</span>
    </div>`;
  }).join('');
  return `<div class="ratings-row">${chips}</div>`;
}

function buildCommentsHtml(comments) {
  if (!comments || comments.length === 0) return '';
  const blocks = comments.map(c => {
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
  return `<div class="comment-modules">${blocks}</div>`;
}

function buildHashtagsHtml(hashtags) {
  if (!hashtags || hashtags.length === 0) return '';
  return `<div class="hashtag-line">${hashtags.map(h => `#${escHtml(h.name)}`).join(' ')}</div>`;
}

function showModal(id) { $(id).style.display = 'flex'; }
function hideModal(id) { $(id).style.display = 'none'; }

// ── Navigation ─────────────────────────────────────────────────
function navigateTo(page, opts = {}) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.gnb-btn').forEach(b => b.classList.remove('active'));
  $(`page-${page}`).classList.add('active');
  const btn = document.querySelector(`.gnb-btn[data-page="${page}"]`);
  if (btn) btn.classList.add('active');
  state.currentPage = page;

  if (page === 'home') loadHome(true);
  else if (page === 'review') loadReviews(true);
  else if (page === 'watchlist') loadWatchlist(true);

  if (!opts.skipPush) {
    pushNavState({ view: 'page', page });
  }
}

// ── 브라우저 히스토리 연동 (앱 내 이동 시 '뒤로가기'가 앱을 벗어나지 않도록) ──
function pushNavState(navState) {
  history.pushState(navState, '', '');
}

window.addEventListener('popstate', e => {
  const s = e.state;
  if (!s || s.view === 'page') {
    navigateTo((s && s.page) || 'home', { skipPush: true });
  } else if (s.view === 'movie') {
    state.movieDetailFrom = s.from || 'home';
    navigateToMovie(s.movieId, { skipPush: true });
  } else if (s.view === 'register') {
    reopenRegisterFromHistory(s);
  }
});

async function reopenRegisterFromHistory(s) {
  let entryData = null;
  if (s.entryId) {
    try { entryData = await API(`/api/entries/${s.entryId}`); } catch (err) { /* ignore */ }
  }
  await openRegisterPage(s.registerType, entryData, { skipPush: true, fromPageOverride: s.from });
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
    const rating = defaultRatingOf(entry);
    const ratingHtml = rating != null
      ? `<div class="movie-card-overlay-rating">${renderStarsHtml(rating)} ${rating.toFixed(1)}/5.0</div>`
      : '';
    return `
      <div class="movie-card ${typeClass}" data-entry-id="${entry.id}" onclick="navigateToMovie(${m.id})">
        ${poster}
        <span class="movie-card-type-badge">${typeBadge}</span>
        <div class="movie-card-overlay">
          <div class="movie-card-overlay-title">${escHtml(m.title)} ${year}</div>
          ${director ? `<div class="movie-card-overlay-sub">${escHtml(director)}</div>` : ''}
          ${ratingHtml}
        </div>
      </div>`;
  }).join('');
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

  const ratingsHtml = isReview ? buildRatingsHtml(entry.ratings) : '';
  const commentsHtml = buildCommentsHtml(entry.comments);
  const hashtagsHtml = buildHashtagsHtml(entry.hashtags);

  return `
    <div class="entry-card ${typeClass}" data-entry-id="${entry.id}">
      <div class="entry-card-inner" onclick="navigateToMovie(${m.id})">
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
          ${hashtagsHtml}
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
// MOVIE DETAIL PAGE
// ══════════════════════════════════════════════════════════════
function navigateToMovie(movieId, opts = {}) {
  if (state.currentPage !== 'movie') state.movieDetailFrom = state.currentPage;
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.gnb-btn').forEach(b => b.classList.remove('active'));
  $('page-movie').classList.add('active');
  state.currentPage = 'movie';
  loadMovieDetail(movieId);

  if (!opts.skipPush) {
    pushNavState({ view: 'movie', movieId, from: state.movieDetailFrom || 'home' });
  }
}

$('movie-back-btn').onclick = () => history.back();

async function loadMovieDetail(movieId) {
  $('movie-detail-content').innerHTML = '<div class="loading-indicator">로딩 중...</div>';
  const data = await API(`/api/movies/${movieId}?lang=${state.language}`);
  if (data.error) {
    $('movie-detail-content').innerHTML = `<div class="empty-state">${escHtml(data.error)}</div>`;
    return;
  }
  renderMovieDetail(data);
}

function renderMovieDetail(data) {
  const m = data.movie;
  const year = m.year ? `(${m.year})` : '';
  const director = m.director && m.director !== 'N/A' ? m.director : '';

  const poster = m.poster_url
    ? `<img class="movie-detail-poster" src="${m.poster_url}" alt="${escHtml(m.title)}">`
    : `<div class="movie-detail-poster-placeholder"><span class="no-poster-kicker">NO POSTER</span><span class="no-poster-title">${escHtml(m.title)}</span></div>`;

  const metaRows = [
    ['배우', m.actors && m.actors !== 'N/A' ? m.actors : null],
    ['장르', m.genre && m.genre !== 'N/A' ? m.genre : null],
    ['러닝타임', fmtRuntime(m.runtime) || null],
    ['국가', m.country && m.country !== 'N/A' ? m.country : null],
  ].filter(([, v]) => v);
  const metaHtml = metaRows.length
    ? `<dl class="movie-detail-meta-grid">${metaRows.map(([k, v]) => `<dt>${escHtml(k)}</dt><dd>${escHtml(v)}</dd>`).join('')}</dl>`
    : '';

  const reviewSection = data.review
    ? buildMovieDetailEntrySection('review', '평가 정보', data.review)
    : `<div class="movie-detail-section review">
        <div class="movie-detail-section-header">
          <h2 class="movie-detail-section-title">평가 정보 <span class="badge">미등록</span></h2>
        </div>
        <div class="movie-detail-empty">아직 등록된 평가가 없습니다.</div>
      </div>`;

  const watchlistSection = data.watchlist
    ? buildMovieDetailEntrySection('watchlist', '보고싶어요 정보', data.watchlist)
    : `<div class="movie-detail-section watchlist">
        <div class="movie-detail-section-header">
          <h2 class="movie-detail-section-title">보고싶어요 정보 <span class="badge">미등록</span></h2>
        </div>
        <div class="movie-detail-empty">아직 등록된 보고싶어요가 없습니다.</div>
      </div>`;

  $('movie-detail-content').innerHTML = `
    <div class="movie-detail-hero">
      ${poster}
      <div class="movie-detail-info">
        <h1 class="movie-detail-title">${escHtml(m.title)} ${year}</h1>
        ${director ? `<div class="movie-detail-director">감독 · ${escHtml(director)}</div>` : ''}
        ${metaHtml}
      </div>
    </div>
    ${reviewSection}
    ${watchlistSection}
  `;
}

function buildMovieDetailEntrySection(kind, title, entry) {
  const isReview = kind === 'review';
  const statusBadgeMap = { completed: '완료', in_progress: '진행중', stopped: '중단' };
  let badge = '';
  if (isReview && entry.watch_status) {
    badge = `<span class="badge">${statusBadgeMap[entry.watch_status] || entry.watch_status}</span>`;
  } else if (!isReview && entry.watchlist_label) {
    badge = `<span class="badge">${escHtml(entry.watchlist_label)}</span>`;
  }
  const ratingsHtml = isReview ? buildRatingsHtml(entry.ratings) : '';
  const commentsHtml = buildCommentsHtml(entry.comments);
  const hashtagsHtml = buildHashtagsHtml(entry.hashtags);
  return `
    <div class="movie-detail-section ${kind}">
      <div class="movie-detail-section-header">
        <h2 class="movie-detail-section-title">${escHtml(title)} ${badge}</h2>
        <button type="button" class="movie-detail-edit-btn" onclick="editEntry(${entry.id})">수정</button>
      </div>
      ${hashtagsHtml}
      ${ratingsHtml}
      ${commentsHtml}
    </div>`;
}

// ══════════════════════════════════════════════════════════════
// REGISTER PAGE
// ══════════════════════════════════════════════════════════════

async function loadStep2Resources() {
  const [rt, ct, ht] = await Promise.all([
    API('/api/templates/ratings'),
    API('/api/templates/comments'),
    API('/api/hashtags'),
  ]);
  state.ratingTemplates = rt;
  state.commentTemplates = ct;
  state.hashtagPool = ht;
}

async function openRegisterPage(type, entryData = null, opts = {}) {
  const fromPage = opts.fromPageOverride || (state.currentPage === 'register' ? 'review' : state.currentPage) || 'review';
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
  resetStep2();

  if (entryData) {
    // 수정 모드: 영화 검색 단계를 건너뛰고 바로 정보 수정 화면으로 진입
    state.selectedMovie = entryData.movie;
    setSelectedMovieUI(entryData.movie);
    $('step1-next-btn').disabled = false;

    await loadStep2Resources();
    setSelectedHashtags(entryData.hashtags || []);

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

    // 수정 모드: 영화 검색(1단계)을 건너뛰고 정보 수정(2단계)부터 시작
    showStep(2);
  } else {
    showStep(1);
  }

  navigateTo('register', { skipPush: true });

  if (!opts.skipPush) {
    pushNavState({ view: 'register', registerType: type, entryId: state.editingEntryId, from: fromPage });
  }
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

  // Reset hashtags
  setSelectedHashtags([]);
  $('hashtag-input').value = '';
  hideHashtagDropdown();
}

// ══════════════════════════════════════════════════════════════
// HASHTAGS (평가/보고싶어요 공통)
// ══════════════════════════════════════════════════════════════
function setSelectedHashtags(hashtags) {
  state.selectedHashtags = (hashtags || []).map(h => h.name);
  renderHashtagChips();
}

function renderHashtagChips() {
  $('hashtag-chips').innerHTML = state.selectedHashtags.map(name => `
    <span class="hashtag-chip-editable">#${escHtml(name)}<button type="button" onclick="removeHashtag('${escAttr(name)}')">×</button></span>
  `).join('');
}

function addHashtag(rawName) {
  const name = (rawName || '').trim().replace(/^#/, '').replace(/\s+/g, '');
  if (!name) return;
  if (!state.selectedHashtags.includes(name)) {
    state.selectedHashtags.push(name);
    renderHashtagChips();
  }
  $('hashtag-input').value = '';
  hideHashtagDropdown();
}

function removeHashtag(name) {
  state.selectedHashtags = state.selectedHashtags.filter(n => n !== name);
  renderHashtagChips();
}

function hideHashtagDropdown() {
  const dd = $('hashtag-dropdown');
  dd.style.display = 'none';
  dd.innerHTML = '';
}

function showHashtagDropdown(query) {
  const dd = $('hashtag-dropdown');
  const q = (query || '').trim().replace(/^#/, '').toLowerCase();
  const candidates = state.hashtagPool
    .map(h => h.name)
    .filter(name => !state.selectedHashtags.includes(name))
    .filter(name => !q || name.toLowerCase().includes(q));
  if (candidates.length === 0) { hideHashtagDropdown(); return; }
  dd.innerHTML = candidates.map(name =>
    `<button type="button" class="hashtag-dropdown-item" onclick="addHashtag('${escAttr(name)}')">#${escHtml(name)}</button>`
  ).join('');
  dd.style.display = 'block';
}

$('hashtag-input').addEventListener('focus', () => showHashtagDropdown($('hashtag-input').value));
$('hashtag-input').addEventListener('input', () => {
  const input = $('hashtag-input');
  // 해시태그는 공백 없이만 등록 가능 — 입력 중 공백은 즉시 제거
  if (/\s/.test(input.value)) input.value = input.value.replace(/\s+/g, '');
  showHashtagDropdown(input.value);
});
$('hashtag-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    e.preventDefault();
    addHashtag($('hashtag-input').value);
  } else if (e.key === 'Escape') {
    hideHashtagDropdown();
  } else if (e.key === ' ') {
    e.preventDefault();
  }
});
document.addEventListener('click', e => {
  if (!e.target.closest('.hashtag-input-wrap')) hideHashtagDropdown();
});

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
  const extra = [movie.genre, fmtRuntime(movie.runtime), movie.country].filter(v => v && v !== 'N/A');
  $('reg-genre').textContent = extra.join(' · ');
}

$('reg-reselect-btn').onclick = () => {
  state.selectedMovie = null;
  $('reg-selected-movie').style.display = 'none';
  $('step1-next-btn').disabled = true;
  $('reg-movie-search').value = '';
};

$('step1-next-btn').onclick = async () => {
  // Load templates before step 2
  const [rt, ct, ht] = await Promise.all([
    API('/api/templates/ratings'),
    API('/api/templates/comments'),
    API('/api/hashtags'),
  ]);
  state.ratingTemplates = rt;
  state.commentTemplates = ct;
  state.hashtagPool = ht;
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
  box.draggable = !isDefault;
  if (!isDefault) box.classList.add('module-draggable');

  let headerHtml;
  if (isDefault) {
    headerHtml = `
      <div class="module-header">
        <span class="module-drag-handle module-drag-handle-locked" title="기본 평점은 항상 첫번째에 고정됩니다">🔒</span>
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
        <span class="module-drag-handle" title="드래그하여 순서 변경">⠿</span>
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
    stars.push(`<button type="button" class="star-btn" data-index="${i}" data-half-index="${i - 0.5}"><span class="star-disp"><span class="star-disp-bg">★</span><span class="star-disp-fg">★</span></span></button>`);
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
    const fg = btn.querySelector('.star-disp-fg');
    const disp = btn.querySelector('.star-disp');
    if (value >= full) {
      if (fg) fg.style.width = '100%';
      btn.classList.add('filled');
      btn.classList.remove('half-filled');
      if (disp) disp.classList.remove('star-disp-half');
    } else if (value >= half) {
      if (fg) fg.style.width = '50%';
      btn.classList.add('half-filled');
      btn.classList.remove('filled');
      if (disp) disp.classList.add('star-disp-half');
    } else {
      if (fg) fg.style.width = '0%';
      btn.classList.remove('filled', 'half-filled');
      if (disp) disp.classList.remove('star-disp-half');
    }
  });
}

$('add-rating-btn').onclick = () => addRatingModule();

// ── 별점 모듈 드래그 정렬 (기본 평점은 항상 첫번째 자리 고정) ──────
(function initRatingsDragSort() {
  const wrap = $('ratings-modules');
  let dragEl = null;

  function getDragAfterElement(y) {
    const candidates = [...wrap.querySelectorAll('.module-box.module-draggable:not(.dragging)')];
    return candidates.reduce((closest, child) => {
      const rect = child.getBoundingClientRect();
      const offset = y - rect.top - rect.height / 2;
      if (offset < 0 && offset > closest.offset) {
        return { offset, element: child };
      }
      return closest;
    }, { offset: Number.NEGATIVE_INFINITY, element: null }).element;
  }

  wrap.addEventListener('dragstart', e => {
    const box = e.target.closest('.module-box');
    if (!box || box.dataset.isDefault === 'true') { e.preventDefault(); return; }
    dragEl = box;
    requestAnimationFrame(() => box.classList.add('dragging'));
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', '');
  });

  wrap.addEventListener('dragend', () => {
    if (dragEl) dragEl.classList.remove('dragging');
    dragEl = null;
  });

  wrap.addEventListener('dragover', e => {
    if (!dragEl) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    const defaultBox = wrap.querySelector('.module-box[data-is-default="true"]');
    const afterEl = getDragAfterElement(e.clientY);
    if (afterEl == null) {
      wrap.appendChild(dragEl);
    } else {
      wrap.insertBefore(dragEl, afterEl);
    }
    // 안전장치: 기본 평점 모듈은 항상 첫번째 자리 유지
    if (defaultBox && wrap.firstElementChild !== defaultBox) {
      wrap.insertBefore(defaultBox, wrap.firstElementChild);
    }
  });
})();

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
    hashtags: state.selectedHashtags.slice(),
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
$('register-back-btn').onclick = () => history.back();

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
// 초기 진입 시 현재 히스토리 항목에 'home' 상태를 부여 (앱 내 이동마다 새 항목이
// 쌓이므로, 뒤로가기를 누르면 이 항목으로 돌아오기 전까지는 앱을 벗어나지 않음)
history.replaceState({ view: 'page', page: 'home' }, '', '');
loadHome(true);

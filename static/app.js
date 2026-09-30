'use strict';

/* ================================================================ utilities */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ESC[c]);
const icon = (id, cls = '') => `<svg class="icon ${cls}"><use href="#i-${id}"/></svg>`;
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const fold = s => String(s || '').replace(/ı/g, 'i').replace(/İ/g, 'i').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase();
const collator = new Intl.Collator('tr', { sensitivity: 'base', numeric: true });
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
};
const api = {
  async get(u) { const r = await fetch(u); if (!r.ok) throw new Error(r.status); return r.json(); },
  async post(u, body) {
    const r = await fetch(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
    if (!r.ok) throw new Error(r.status);
    return r.headers.get('content-type')?.includes('json') ? r.json() : r.text();
  },
};

function fmtTime(t) {
  t = Math.max(0, Math.floor(t || 0));
  const h = Math.floor(t / 3600), m = Math.floor(t % 3600 / 60), s = t % 60;
  return (h ? h + ':' + String(m).padStart(2, '0') : m) + ':' + String(s).padStart(2, '0');
}
function fmtRuntime(min) {
  if (!min) return '';
  const h = Math.floor(min / 60), m = min % 60;
  return h ? `${h} sa${m ? ' ' + m + ' dk' : ''}` : `${m} dk`;
}
function fmtLeft(pos, dur) {
  const left = Math.max(0, Math.round((dur - pos) / 60));
  return left >= 60 ? `${Math.floor(left / 60)} sa ${left % 60} dk kaldı` : `${left} dk kaldı`;
}
function fmtSize(b) { return b > 1e9 ? (b / 1e9).toFixed(1) + ' GB' : Math.round(b / 1e6) + ' MB'; }
function hue(s) { let h = 0; for (const c of String(s)) h = (h * 31 + c.charCodeAt(0)) % 360; return h; }
function shuffle(a, seed) {
  a = a.slice();
  let s = seed ?? Math.random() * 1e9;
  const rnd = () => ((s = (s * 9301 + 49297) % 233280) / 233280);
  for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
  return a;
}
const genresOf = it => (it.g || '').split(',').map(g => g.trim()).filter(g => g && g !== 'N/A');
const daySeed = Math.floor(Date.now() / 864e5);

function toast(msg, ms = 2600) {
  const el = document.createElement('div');
  el.className = 'toast';
  el.innerHTML = msg;
  $('#toasts').appendChild(el);
  setTimeout(() => { el.classList.add('out'); setTimeout(() => el.remove(), 320); }, ms);
}

/* ================================================================ data */
const S = {
  titles: [], series: [], cols: [], byKey: new Map(), movieToTitle: new Map(), colById: new Map(),
  genres: [], progress: {}, mylist: new Set(), cont: [], version: 0, loaded: false,
  view: 'home', browse: { movies: { genre: '', sort: 'added' }, series: { genre: '', sort: 'added' } },
};

function img(kind, id, type, w) {
  const it = type === 'poster' && (kind === 'm' ? S.movieToTitle.get(id)?.versions.find(v => v.id === id) : kind === 's' ? S.byKey.get('s:' + id) : null);
  return `/img/${type}/${kind}/${id}?w=${w || 0}${it && it.ph ? '&v=' + it.ph : ''}`;
}

function buildLibrary(lib) {
  const groups = new Map();
  for (const m of lib.movies) {
    const k = m.tm ? 't' + m.tm : 'i' + m.id;
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(m);
  }
  S.movieToTitle.clear();
  S.titles = [...groups.values()].map(vs => {
    vs.sort((a, b) => (b.ph - a.ph) || (b.sz - a.sz));
    const p = vs[0];
    const t = {
      ...p, kind: 'm', key: 'm:' + p.id, versions: vs,
      add: Math.max(...vs.map(v => v.add || 0)),
      r: p.r || vs.find(v => v.r)?.r || '', g: p.g || vs.find(v => v.g)?.g || '',
      p: p.p || vs.find(v => v.p)?.p || '', bd: vs.some(v => v.bd), c: vs.find(v => v.c)?.c || null,
    };
    t.bdId = (vs.find(v => v.bd) || p).id;
    t.search = fold([t.t, t.ot, t.g, t.y, t.p].join(' '));
    vs.forEach(v => S.movieToTitle.set(v.id, t));
    return t;
  });
  S.series = lib.series.map(s => ({ ...s, kind: 's', key: 's:' + s.id, search: fold([s.t, s.ot, s.g, s.y, s.p].join(' ')) }));
  S.cols = lib.collections.map(c => {
    const items = [];
    for (const id of c.items) { const t = S.movieToTitle.get(id); if (t && !items.includes(t)) items.push(t); }
    return { ...c, kind: 'c', key: 'c:' + c.id, titles: items };
  }).filter(c => c.titles.length >= 2);
  S.byKey = new Map([...S.titles, ...S.series, ...S.cols].map(x => [x.key, x]));
  S.series.forEach(s => (s.ids || []).forEach(i => { if (!S.byKey.has('s:' + i)) S.byKey.set('s:' + i, s); }));
  S.colById = new Map(S.cols.map(c => [String(c.id), c]));
  const count = new Map();
  [...S.titles, ...S.series].forEach(it => genresOf(it).forEach(g => count.set(g, (count.get(g) || 0) + 1)));
  S.genres = [...count.entries()].sort((a, b) => b[1] - a[1]).map(([g, n]) => ({ g, n }));
  S.version = lib.version;
  S.loaded = true;
}

async function loadLibrary() { buildLibrary(await api.get('/api/library')); }
async function loadUser() {
  const u = await api.get('/api/user');
  S.progress = u.progress; S.mylist = new Set(u.mylist); S.cont = u.continue;
}
const inList = it => it.kind === 'm' ? it.versions.some(v => S.mylist.has('m:' + v.id)) : S.mylist.has(it.key);
function movieProgress(t) {
  let best = null;
  for (const v of t.versions || []) {
    const p = S.progress['m:' + v.id];
    if (p && (!best || p[3] > best[3])) best = [...p, v.id];
  }
  return best;
}
const isNew = it => it.add && (Date.now() / 1000 - it.add) < 21 * 864e2;

/* ================================================================ cards */
function artHTML(it, w = 342) {
  if (it.kind === 'c') {
    const first = it.titles.find(t => t.bd) || it.titles[0];
    const src = it.backdrop ? img('c', it.id, 'backdrop', 780) : first?.bd ? img('m', first.bdId, 'backdrop', 780) : null;
    return src ? `<img src="${src}" alt="" loading="lazy" decoding="async" onload="this.classList.add('ok')" onerror="this.remove()">` :
      `<div class="ph" style="--h:${hue(it.name)}">${esc(it.name)}</div>`;
  }
  const ph = `<div class="ph" style="--h:${hue(it.t)}">${esc(it.t)}</div>`;
  if (!it.ph) return ph;
  return `${ph}<img src="${img(it.kind, it.id, 'poster', w)}" alt="${esc(it.t)}" loading="lazy" decoding="async" onload="this.classList.add('ok')" onerror="this.remove()">`;
}

function posterCard(it, { caption = false, current = false } = {}) {
  const prog = it.kind === 'm' ? movieProgress(it) : null;
  const pct = prog && !prog[2] && prog[1] ? clamp(prog[0] / prog[1] * 100, 2, 100) : 0;
  const sub = [it.y, it.kind === 's' ? `${it.seasons} sezon` : fmtRuntime(it.rt)].filter(Boolean).join(' · ');
  return `<div class="card${current ? ' current' : ''}" tabindex="0" role="button" data-open="${it.key}" aria-label="${esc(it.t)}">
    <div class="art">${artHTML(it)}
      ${isNew(it) && !caption ? '<span class="flag new">YENİ</span>' : ''}
      <div class="shade"><strong>${esc(it.t)}</strong><span>${it.r ? `<b class="score">${icon('star')}${esc(it.r)}</b>` : ''}${esc(sub)}</span></div>
      ${pct ? `<div class="pbar progress-line"><i style="width:${pct}%"></i></div>` : ''}
    </div>
    ${caption ? `<div class="caption"><strong>${esc(it.t)}</strong><span>${esc(it.y || '')}${it.r ? ` <b class="score">${icon('star')}${esc(it.r)}</b>` : ''}</span></div>` : ''}
  </div>`;
}

function continueCard(c) {
  const series = c.kind === 'e' ? S.byKey.get('s:' + c.sid) : null;
  const movie = c.kind === 'm' ? S.movieToTitle.get(c.id) : null;
  const src = series ? (series.bd ? img('s', series.id, 'backdrop', 640) : series.ph ? img('s', series.id, 'poster', 342) : '')
    : movie ? (movie.bd ? img('m', movie.bdId, 'backdrop', 640) : movie.ph ? img('m', movie.id, 'poster', 342) : '') : '';
  const pct = c.dur ? clamp(c.pos / c.dur * 100, 2, 100) : 0;
  return `<div class="card land" tabindex="0" role="button" data-play="${c.kind}:${c.id}" aria-label="${esc(c.title)}">
    <div class="art">${src ? `<img src="${src}" alt="" loading="lazy" onload="this.classList.add('ok')" onerror="this.remove()">` : `<div class="ph" style="--h:${hue(c.title)}">${esc(c.title)}</div>`}
      ${c.up_next ? '<span class="flag new">SIRADAKİ</span>' : ''}
      <button class="x" data-forget="${c.kind}:${c.id}" title="Listeden kaldır" aria-label="Kaldır">${icon('x')}</button>
      <div class="play-glyph">${icon('play', 'fill')}</div>
      <div class="shade"><strong>${esc(c.title)}</strong><span>${esc(c.sub || '')}${c.dur ? ` · ${fmtLeft(c.pos, c.dur)}` : ''}</span></div>
      ${pct ? `<div class="pbar progress-line"><i style="width:${pct}%"></i></div>` : ''}
    </div></div>`;
}

function collectionCard(c) {
  const stack = c.titles.filter(t => t.ph).slice(0, 3).map(t => `<img src="${img('m', t.id, 'poster', 154)}" alt="" loading="lazy">`).join('');
  return `<div class="card col" tabindex="0" role="button" data-open="${c.key}" aria-label="${esc(c.name)}">
    <div class="art">${artHTML(c)}<div class="stack">${stack}</div>
      <div class="shade"><strong>${esc(c.name)}</strong><span>${c.titles.length} film${c.parts > c.titles.length ? ` · serinin ${c.parts} filminden` : ''}</span></div>
    </div></div>`;
}

function row(title, items, { kind = 'poster', more = '' } = {}) {
  if (!items.length) return '';
  const body = items.map(x => kind === 'cont' ? continueCard(x) : kind === 'col' ? collectionCard(x) : posterCard(x)).join('');
  return `<section class="row">
    <div class="row-head"><h2>${esc(title)}</h2>${more ? `<a class="more" href="${more}">Tümünü gör ${icon('right')}</a>` : ''}</div>
    <div class="rail-wrap">
      <button class="rail-btn prev" aria-label="Geri" hidden>${icon('left')}</button>
      <div class="rail${kind !== 'poster' ? ' wide' : ''}">${body}</div>
      <button class="rail-btn next" aria-label="İleri">${icon('right')}</button>
    </div></section>`;
}

function wireRails(root) {
  $$('.rail-wrap', root).forEach(w => {
    const rail = $('.rail', w), prev = $('.prev', w), next = $('.next', w);
    const upd = () => {
      prev.hidden = rail.scrollLeft < 8;
      next.hidden = rail.scrollLeft + rail.clientWidth >= rail.scrollWidth - 8;
    };
    prev.onclick = () => rail.scrollBy({ left: -rail.clientWidth * .9, behavior: 'smooth' });
    next.onclick = () => rail.scrollBy({ left: rail.clientWidth * .9, behavior: 'smooth' });
    rail.addEventListener('scroll', upd, { passive: true });
    requestAnimationFrame(upd);
  });
}

function metaLine(it, { runtime = true } = {}) {
  const bits = [];
  if (it.r) bits.push(`<span class="score">${icon('star')}${esc(it.r)}</span>`);
  if (it.y) bits.push(`<span>${esc(it.y)}</span>`);
  if (it.kind === 'm' && runtime && it.rt) bits.push(`<span>${fmtRuntime(it.rt)}</span>`);
  if (it.kind === 's') bits.push(`<span>${it.seasons} sezon · ${it.eps} bölüm</span>`);
  const g = genresOf(it).slice(0, 3).join(', ');
  if (g) bits.push(`<span>${esc(g)}</span>`);
  return bits.join('<i class="sep"></i>');
}

/* ================================================================ views */
let heroTimer = null;

function heroHTML(picks) {
  if (!picks.length) return '<div style="height:calc(var(--nav-h) + 20px)"></div>';
  const slides = picks.map((it, i) => `<div class="hero-slide${i ? '' : ' on'}"><img src="${img(it.kind, it.kind === 'm' ? it.bdId : it.id, 'backdrop', 1600)}" alt="" ${i ? 'loading="lazy"' : 'fetchpriority="high"'}></div>`).join('');
  return `<section class="hero" id="hero">${slides}<div class="hero-content" id="hero-content"></div>
    ${picks.length > 1 ? `<div class="hero-dots">${picks.map((_, i) => `<button data-hero="${i}" class="${i ? '' : 'on'}" aria-label="Öne çıkan ${i + 1}"></button>`).join('')}</div>` : ''}</section>`;
}

function heroContent(it) {
  const col = it.c ? S.colById.get(String(it.c)) : null;
  const kicker = it.kind === 's' ? 'Dizi' : col ? `Koleksiyon · ${col.name}` : isNew(it) ? 'Yeni Eklendi' : 'Öne Çıkan Film';
  const prog = it.kind === 'm' ? movieProgress(it) : null;
  const resume = prog && !prog[2] && prog[0] > 30;
  return `<div class="kicker"><b>H</b>${esc(kicker)}</div>
    <h1>${esc(it.t)}</h1>
    <div class="meta">${metaLine(it)}</div>
    <p class="plot">${esc(it.p)}</p>
    <div class="actions">
      <button class="btn btn-play" data-${it.kind === 's' ? 'open' : 'play'}="${it.kind === 's' ? it.key : 'm:' + it.id}">${icon('play', 'fill')}${resume ? 'Devam Et' : 'Oynat'}</button>
      <button class="btn btn-ghost" data-open="${it.key}">${icon('info')}Daha Fazla Bilgi</button>
    </div>`;
}

function startHero(picks) {
  clearInterval(heroTimer);
  const hero = $('#hero');
  if (!hero || !picks.length) return;
  let i = 0;
  const show = n => {
    i = (n + picks.length) % picks.length;
    $$('.hero-slide', hero).forEach((s, k) => s.classList.toggle('on', k === i));
    $$('.hero-dots button', hero).forEach((s, k) => s.classList.toggle('on', k === i));
    $('#hero-content').innerHTML = heroContent(picks[i]);
  };
  show(0);
  hero.onclick = e => { const d = e.target.closest('[data-hero]'); if (d) { show(+d.dataset.hero); restart(); } };
  const restart = () => { clearInterval(heroTimer); heroTimer = setInterval(() => { if (!document.hidden && !anyOverlay()) show(i + 1); }, 9000); };
  if (picks.length > 1) restart();
}

function renderHome() {
  const pool = [...S.titles, ...S.series];
  const withBd = pool.filter(t => t.bd && t.p && parseFloat(t.r || 0) >= 6.5);
  const picks = shuffle(withBd.length ? withBd : pool.filter(t => t.bd), daySeed + (Date.now() / 36e5 | 0)).slice(0, 6);
  const byAdd = [...S.titles].sort((a, b) => b.add - a.add);
  const top = S.titles.filter(t => parseFloat(t.r) >= 7.2).sort((a, b) => parseFloat(b.r) - parseFloat(a.r));
  const list = [...S.mylist].map(k => S.byKey.get(k) || S.movieToTitle.get(+k.slice(2))).filter((x, i, a) => x && a.indexOf(x) === i);
  const cols = [...S.cols].sort((a, b) => b.titles.length - a.titles.length);
  const series = [...S.series].sort((a, b) => b.add - a.add);
  let html = heroHTML(picks) + '<div class="rows">';
  html += row('İzlemeye Devam Et', S.cont, { kind: 'cont' });
  html += row('Listem', list, { more: '#list' });
  html += row('Yeni Eklenenler', byAdd.slice(0, 24), { more: '#movies' });
  html += row('Koleksiyonlar', cols.slice(0, 16), { kind: 'col', more: '#collections' });
  html += row('Diziler', series.slice(0, 24), { more: '#series' });
  html += row('En Yüksek Puanlılar', top.slice(0, 24));
  const used = new Set();
  S.genres.filter(g => g.n >= 10).slice(0, 7).forEach(({ g }) => {
    const items = shuffle(S.titles.filter(t => genresOf(t).includes(g) && !used.has(t.key)), daySeed + hue(g))
      .sort((a, b) => (parseFloat(b.r) || 0) - (parseFloat(a.r) || 0)).slice(0, 20);
    items.slice(0, 6).forEach(t => used.add(t.key));
    html += row(g, shuffle(items, daySeed), { more: `#movies/${encodeURIComponent(g)}` });
  });
  html += row('Bugün Ne İzlesem?', shuffle(S.titles, daySeed * 7).slice(0, 24));
  html += '</div>';
  $('#view').innerHTML = html;
  wireRails($('#view'));
  startHero(picks);
}

const SORTS = [
  ['added', 'Yeni eklenen'], ['rating', 'Puan (yüksek)'], ['rating_asc', 'Puan (düşük)'],
  ['name', 'İsim (A–Z)'], ['year', 'Yıl (yeni)'], ['year_asc', 'Yıl (eski)'],
];
function sortItems(items, sort) {
  const r = x => parseFloat(x.r) || 0, y = x => parseInt(x.y) || 0;
  const f = {
    added: (a, b) => b.add - a.add, rating: (a, b) => r(b) - r(a), rating_asc: (a, b) => (r(a) || 99) - (r(b) || 99),
    name: (a, b) => collator.compare(a.t, b.t), year: (a, b) => y(b) - y(a), year_asc: (a, b) => (y(a) || 9999) - (y(b) || 9999),
  }[sort] || (() => 0);
  return items.slice().sort(f);
}

function renderBrowse(kind) {
  const st = S.browse[kind];
  const base = kind === 'movies' ? S.titles : S.series;
  const genreCount = new Map();
  base.forEach(it => genresOf(it).forEach(g => genreCount.set(g, (genreCount.get(g) || 0) + 1)));
  const genres = [...genreCount.entries()].filter(([, n]) => n >= 2).sort((a, b) => b[1] - a[1]).map(([g]) => g);
  const items = sortItems(st.genre ? base.filter(it => genresOf(it).includes(st.genre)) : base, st.sort);
  $('#view').innerHTML = `
    <div class="page-head"><h1>${kind === 'movies' ? 'Filmler' : 'Diziler'}</h1><span class="count">${items.length} ${kind === 'movies' ? 'film' : 'dizi'}</span></div>
    <div class="toolbar">
      <div class="chips"><button class="chip${st.genre ? '' : ' on'}" data-genre="">Tümü</button>${genres.map(g => `<button class="chip${st.genre === g ? ' on' : ''}" data-genre="${esc(g)}">${esc(g)}</button>`).join('')}</div>
      <label class="select"><span class="sr">Sırala</span><select id="sort">${SORTS.map(([v, l]) => `<option value="${v}"${st.sort === v ? ' selected' : ''}>${l}</option>`).join('')}</select></label>
    </div>
    <div class="grid" id="grid">${items.map(it => posterCard(it, { caption: true })).join('') || emptyState('Bu türde içerik yok', 'Başka bir tür seçmeyi deneyin.')}</div>`;
  $('.chips').onclick = e => {
    const c = e.target.closest('[data-genre]');
    if (!c) return;
    st.genre = c.dataset.genre;
    history.replaceState(history.state, '', `#${kind}${st.genre ? '/' + encodeURIComponent(st.genre) : ''}`);
    renderBrowse(kind);
  };
  $('#sort').onchange = e => { st.sort = e.target.value; store.set('sort_' + kind, st.sort); renderBrowse(kind); };
  const on = $('.chip.on'); if (on) on.scrollIntoView({ inline: 'center', block: 'nearest' });
}

function emptyState(title, text, ic = 'popcorn') {
  return `<div class="empty">${icon(ic)}<h3>${esc(title)}</h3><p>${esc(text)}</p></div>`;
}

function renderCollections() {
  const cols = [...S.cols].sort((a, b) => collator.compare(a.name, b.name));
  $('#view').innerHTML = `
    <div class="page-head"><h1>Koleksiyonlar</h1><span class="count">${cols.length} seri · ${cols.reduce((n, c) => n + c.titles.length, 0)} film</span></div>
    <div class="grid cols" style="padding-top:20px">${cols.map(collectionCard).join('') || emptyState('Henüz koleksiyon yok', 'Film bilgileri tamamlandıkça devam filmleri burada gruplanacak.')}</div>`;
}

function renderList() {
  const items = [...S.mylist].map(k => S.byKey.get(k) || S.movieToTitle.get(+k.slice(2))).filter((x, i, a) => x && a.indexOf(x) === i);
  $('#view').innerHTML = `
    <div class="page-head"><h1>Listem</h1><span class="count">${items.length} içerik</span></div>
    <div class="grid" style="padding-top:20px">${items.map(it => posterCard(it, { caption: true })).join('') ||
      emptyState('Listeniz boş', 'Bir filmin ya da dizinin sayfasındaki + düğmesiyle buraya ekleyin.', 'bookmark')}</div>`;
}

function route() {
  const [view, arg] = (location.hash.slice(1) || 'home').split('/');
  S.view = ['home', 'movies', 'series', 'collections', 'list'].includes(view) ? view : 'home';
  if ((S.view === 'movies' || S.view === 'series')) S.browse[S.view].genre = arg ? decodeURIComponent(arg) : '';
  $$('[data-tab]').forEach(t => t.classList.toggle('active', t.dataset.tab === S.view));
  render();
  window.scrollTo(0, 0);
}

function render() {
  if (!S.loaded) return;
  clearInterval(heroTimer);
  const y = window.scrollY;
  ({ home: renderHome, movies: () => renderBrowse('movies'), series: () => renderBrowse('series'),
     collections: renderCollections, list: renderList })[S.view]();
  return y;
}
function softRender() { const y = window.scrollY; render(); window.scrollTo(0, y); }

/* ================================================================ overlays & history */
const stack = [];
const anyOverlay = () => stack.length > 0;
function pushOverlay(name, onClose) {
  stack.push({ name, onClose });
  history.pushState({ ov: stack.length }, '');
  document.body.classList.add('locked');
}
function back() { if (stack.length) history.back(); }
window.addEventListener('popstate', () => {
  const top = stack.pop();
  if (top) top.onClose();
  if (!stack.length) document.body.classList.remove('locked');
});

/* ================================================================ detail */
let detailKey = null;

async function openDetail(key) {
  const it = S.byKey.get(key) || (key.startsWith('m:') ? S.movieToTitle.get(+key.slice(2)) : null);
  if (!it) return;
  const el = $('#detail');
  if (!el.classList.contains('open')) {
    el.classList.add('open');
    pushOverlay('detail', () => { el.classList.remove('open'); detailKey = null; });
  }
  detailKey = it.key;
  $('#detail-scroll').scrollTop = 0;
  if (it.kind === 'c') return renderCollectionDetail(it);
  renderDetail(it);
  if (it.kind === 's') loadEpisodes(it);
}

function detailHero(it, title, actions, metaHTML) {
  const kind = it.kind === 'c' ? 'c' : it.kind;
  const bdSrc = it.kind === 'c' ? (it.backdrop ? img('c', it.id, 'backdrop', 1280) : (() => { const f = it.titles.find(t => t.bd); return f ? img('m', f.bdId, 'backdrop', 1280) : ''; })())
    : it.bd ? img(kind, kind === 'm' ? it.bdId : it.id, 'backdrop', 1280) : '';
  const posterSrc = it.kind !== 'c' && it.ph ? img(kind, it.id, 'poster', 500) : '';
  const fallback = posterSrc ? `<img class="blurposter" src="${posterSrc}" alt="">` : `<div class="ph" style="--h:${hue(title)}"></div>`;
  return `<div class="d-hero">${bdSrc ? `<img src="${bdSrc}" alt="" onload="this.classList.add('ok')" onerror="this.outerHTML=this.dataset.fb" data-fb='${esc(fallback)}'>` : fallback}
    <div class="d-head"><h1>${esc(title)}</h1>${metaHTML ? `<div class="meta" style="margin-bottom:18px">${metaHTML}</div>` : ''}<div class="actions">${actions}</div></div></div>`;
}

function listButton(it) {
  const on = inList(it);
  return `<button class="round-btn${on ? ' on' : ''}" data-list="${it.key}" title="${on ? 'Listemden çıkar' : 'Listeme ekle'}" aria-label="Listem">${icon(on ? 'check' : 'plus')}</button>`;
}

function renderDetail(it) {
  const col = it.kind === 'm' && it.c ? S.colById.get(String(it.c)) : null;
  let actions = '', resumeNote = '';
  if (it.kind === 'm') {
    const prog = movieProgress(it);
    const resume = prog && !prog[2] && prog[0] > 30;
    const vid = resume ? prog[4] : it.id;
    actions = `<button class="btn btn-play" data-play="m:${vid}">${icon('play', 'fill')}${resume ? 'Devam Et' : 'Oynat'}</button>
      ${resume ? `<button class="btn btn-ghost" data-play="m:${vid}" data-from="0">${icon('refresh')}Baştan Başla</button>` : ''}${listButton(it)}`;
    if (resume && prog[1]) resumeNote = `<div class="resume-note"><div class="progress-line"><i style="width:${clamp(prog[0] / prog[1] * 100, 2, 100)}%"></i></div>${fmtLeft(prog[0], prog[1])}</div>`;
  } else {
    actions = `<button class="btn btn-play" id="series-play" data-play="">${icon('play', 'fill')}Oynat</button>${listButton(it)}`;
  }
  const similar = [...S.titles, ...S.series].filter(x => x !== it && !(col && x.c === it.c))
    .map(x => ({ x, s: genresOf(x).filter(g => genresOf(it).includes(g)).length + (parseFloat(x.r) || 0) / 20 }))
    .filter(o => o.s >= 1).sort((a, b) => b.s - a.s).slice(0, 12).map(o => o.x);
  const facts = [];
  if (it.ot && fold(it.ot) !== fold(it.t)) facts.push(`<div>Orijinal ad: <b>${esc(it.ot)}</b></div>`);
  if (genresOf(it).length) facts.push(`<div>Türler: <b>${esc(genresOf(it).join(', '))}</b></div>`);
  if (col) facts.push(`<div>Koleksiyon: <a data-open="${col.key}">${esc(col.name)}</a></div>`);
  if (it.kind === 'm') facts.push(`<div>Kütüphaneye eklendi: <b>${new Date(it.add * 1000).toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' })}</b></div>`);
  const versions = it.kind === 'm' && it.versions.length > 1 ? `<div class="section"><div class="section-head"><h3>Sürümler</h3></div><div class="versions">
    ${it.versions.map((v, i) => `<button class="version" data-play="m:${v.id}" data-from="0">${icon('play', 'fill')}<span>${esc(v.t)}${i === 0 ? ' · varsayılan' : ''}</span><small>${v.sz ? fmtSize(v.sz) : ''}</small></button>`).join('')}</div></div>` : '';
  $('#detail-sheet').innerHTML = `
    <button class="close" data-action="back" aria-label="Kapat">${icon('x')}</button>
    ${detailHero(it, it.t, actions, metaLine(it))}
    <div class="d-body">
      <div class="d-grid"><div><p class="plot">${esc(it.p || 'Bu içerik için açıklama bulunamadı.')}</p>${resumeNote}</div><div class="facts">${facts.join('')}</div></div>
      ${it.kind === 's' ? '<div class="section" id="episodes"><div class="section-head"><h3>Bölümler</h3></div><div class="eps"><div class="spin" style="margin:20px auto"></div></div></div>' : ''}
      ${col ? `<div class="section"><div class="section-head"><h3>${esc(col.name)} Koleksiyonu</h3><a class="more" style="opacity:1;transform:none;color:var(--muted);font-weight:600;font-size:14px;cursor:pointer" data-open="${col.key}">Koleksiyonu aç</a></div>
        <div class="grid">${col.titles.map(t => posterCard(t, { caption: true, current: t === it })).join('')}</div></div>` : ''}
      ${versions}
      ${similar.length ? `<div class="section"><div class="section-head"><h3>Benzer İçerikler</h3></div><div class="grid">${similar.map(x => posterCard(x, { caption: true })).join('')}</div></div>` : ''}
    </div>`;
}

function renderCollectionDetail(c) {
  const next = c.titles.find(t => { const p = movieProgress(t); return !p || !p[2]; }) || c.titles[0];
  const years = c.titles.map(t => parseInt(t.y)).filter(Boolean);
  const meta = [`<span>${c.titles.length} film</span>`, years.length ? `<span>${Math.min(...years)}–${Math.max(...years)}</span>` : '',
    c.parts > c.titles.length ? `<span>Seride ${c.parts} film var</span>` : ''].filter(Boolean).join('<i class="sep"></i>');
  $('#detail-sheet').innerHTML = `
    <button class="close" data-action="back" aria-label="Kapat">${icon('x')}</button>
    ${detailHero(c, c.name, `<button class="btn btn-play" data-play="m:${next.id}">${icon('play', 'fill')}${next === c.titles[0] ? 'Seriye Başla' : 'Sıradakini İzle'}</button>`, meta)}
    <div class="d-body">
      ${c.ov ? `<p class="plot" style="font-size:16px;color:#e4e4e7;margin:14px 0 0;max-width:760px;line-height:1.6">${esc(c.ov)}</p>` : ''}
      <div class="section"><div class="section-head"><h3>Filmler</h3><span style="color:var(--dim);font-size:14px">Çıkış sırasına göre</span></div>
      <div class="grid">${c.titles.map(t => posterCard(t, { caption: true })).join('')}</div></div>
    </div>`;
}

async function loadEpisodes(s, season, tries = 0) {
  let data;
  try { data = await api.get(`/api/series/${s.id}`); } catch { return; }
  if (detailKey !== s.key) return;
  const box = $('#episodes');
  if (!box || !data.seasons.length) { if (box) box.innerHTML = emptyState('Bölüm bulunamadı', ''); return; }
  const all = data.seasons.flatMap(x => x.eps.map(e => ({ ...e, season: x.n })));
  const last = all.filter(e => e.at).sort((a, b) => b.at - a.at)[0];
  let target = all[0];
  if (last) {
    const i = all.indexOf(last);
    target = last.fin ? (all[i + 1] || last) : last;
  }
  const cur = season ?? target.season;
  const playBtn = $('#series-play');
  if (playBtn) {
    const resume = target.pos > 30 && !target.fin;
    playBtn.dataset.play = 'e:' + target.id;
    playBtn.innerHTML = `${icon('play', 'fill')}${resume ? 'Devam Et' : last ? 'Oynat' : 'İzlemeye Başla'} · S${target.season}:B${target.n}`;
  }
  const seasonSel = data.seasons.length > 1 ? `<label class="select"><select id="season-sel">${data.seasons.map(x => `<option value="${x.n}"${x.n === cur ? ' selected' : ''}>Sezon ${x.n}</option>`).join('')}</select></label>` : `<span style="color:var(--dim)">Sezon ${cur}</span>`;
  const eps = data.seasons.find(x => x.n === cur)?.eps || [];
  box.innerHTML = `<div class="section-head"><h3>Bölümler</h3>${seasonSel}</div><div class="eps">${eps.map(e => {
    const pct = e.dur && !e.fin ? clamp(e.pos / e.dur * 100, 2, 100) : e.fin ? 100 : 0;
    const thumb = e.still ? `/img/still/${e.id}` : s.bd ? img('s', s.id, 'backdrop', 400) : s.ph ? img('s', s.id, 'poster', 342) : '';
    return `<div class="ep${target.id === e.id ? ' now' : ''}" tabindex="0" role="button" data-play="e:${e.id}">
      <div class="num">${e.n}</div>
      <div class="thumb">${thumb ? `<img src="${thumb}" alt="" loading="lazy" onload="this.classList.add('ok')">` : ''}<div class="play-glyph"><span>${icon('play', 'fill')}</span></div>
        ${pct ? `<div class="pbar progress-line"><i style="width:${pct}%"></i></div>` : ''}</div>
      <div><h4><span>${esc(e.name || `${e.n}. Bölüm`)}</span><small>${e.fin ? `<span class="done">${icon('check')}İzlendi</span>` : e.rt ? e.rt + ' dk' : ''}</small></h4>
        <p>${esc(e.ov || e.file)}</p></div></div>`;
  }).join('')}</div>`;
  const sel = $('#season-sel');
  if (sel) sel.onchange = () => loadEpisodes(s, +sel.value);
  if (data.pending && tries < 4) setTimeout(() => detailKey === s.key && loadEpisodes(s, season, tries + 1), 1500);
}

async function toggleList(key, btn) {
  const it = S.byKey.get(key);
  if (!it) return;
  const on = !inList(it);
  const keys = it.kind === 'm' ? (on ? [it.key] : it.versions.map(v => 'm:' + v.id)) : [it.key];
  for (const k of keys) { await api.post('/api/mylist', { key: k, on }); on ? S.mylist.add(k) : S.mylist.delete(k); }
  if (btn) { btn.classList.toggle('on', on); btn.innerHTML = icon(on ? 'check' : 'plus'); btn.title = on ? 'Listemden çıkar' : 'Listeme ekle'; }
  toast(on ? `${icon('check')} <b>${esc(it.t)}</b> listene eklendi` : `<b>${esc(it.t)}</b> listenden çıkarıldı`);
  if (S.view === 'list' || S.view === 'home') softRender();
}

/* ================================================================ search */
function openSearch() {
  const el = $('#search');
  if (el.classList.contains('open')) return $('#search-input').focus();
  el.classList.add('open');
  pushOverlay('search', () => el.classList.remove('open'));
  const inp = $('#search-input');
  inp.value = '';
  runSearch('');
  setTimeout(() => inp.focus(), 30);
}
function runSearch(q) {
  const box = $('#search-results');
  const terms = fold(q).split(/\s+/).filter(Boolean);
  if (!terms.length) {
    box.innerHTML = `<div class="search-hint">Türlere göz atın</div><div class="chips">${S.genres.slice(0, 24).map(({ g, n }) => `<button class="chip" data-goto="#movies/${encodeURIComponent(g)}">${esc(g)} <span style="color:var(--dim);margin-left:4px">${n}</span></button>`).join('')}</div>
      ${S.cols.length ? `<div class="search-hint">Koleksiyonlar</div><div class="grid cols" style="padding-top:0">${S.cols.slice(0, 6).map(collectionCard).join('')}</div>` : ''}`;
    return;
  }
  const score = it => {
    const t = fold(it.t), ot = fold(it.ot);
    let s = 0;
    for (const w of terms) {
      if (!it.search.includes(w)) return 0;
      s += t.startsWith(w) ? 6 : t.includes(w) ? 4 : ot.includes(w) ? 3 : 1;
    }
    return s + (parseFloat(it.r) || 0) / 10;
  };
  const hits = [...S.titles, ...S.series].map(it => [it, score(it)]).filter(x => x[1] > 0).sort((a, b) => b[1] - a[1]).map(x => x[0]);
  const cols = S.cols.filter(c => terms.every(w => fold(c.name).includes(w)));
  box.innerHTML = `<div class="search-hint">${hits.length ? `${hits.length} sonuç` : ''}</div>
    ${cols.length ? `<div class="grid cols" style="padding-bottom:20px">${cols.map(collectionCard).join('')}</div>` : ''}
    <div class="grid">${hits.slice(0, 120).map(it => posterCard(it, { caption: true })).join('') || emptyState(`“${q}” için sonuç yok`, 'Farklı bir yazım ya da orijinal adıyla aramayı deneyin.', 'search')}</div>`;
}

/* ================================================================ settings */
async function openSettings() {
  const el = $('#settings');
  el.classList.add('open');
  pushOverlay('settings', () => el.classList.remove('open'));
  const sheet = $('#settings-sheet');
  sheet.innerHTML = `<div style="padding:60px;display:grid;place-items:center"><div class="spin"></div></div>`;
  const s = await api.get('/api/settings');
  sheet.innerHTML = `
    <button class="close" data-action="back" aria-label="Kapat">${icon('x')}</button>
    <div class="d-body" style="padding-top:34px">
      <h2 style="margin:0 0 22px;font-size:28px;font-weight:800;letter-spacing:-.02em">Ayarlar</h2>
      <div class="stats">
        <div class="stat"><b>${s.stats.movies}</b><span>Film</span></div>
        <div class="stat"><b>${s.stats.series}</b><span>Dizi</span></div>
        <div class="stat"><b>${s.stats.episodes}</b><span>Bölüm</span></div>
        <div class="stat"><b>${S.cols.length}</b><span>Koleksiyon</span></div>
      </div>
      <div class="section"><div class="section-head"><h3>Kütüphane</h3></div>
        <div class="form">
          <div class="field"><label for="conf-movie">Film klasörü</label><input id="conf-movie" value="${esc(s.movie_dir)}"></div>
          <div class="field"><label for="conf-series">Dizi klasörü</label><input id="conf-series" value="${esc(s.series_dir)}"></div>
          <div class="field"><label for="conf-key">OMDb API anahtarı</label><input id="conf-key" value="${esc(s.omdb_api_key)}"></div>
          <div class="actions">
            <button class="btn btn-accent btn-sm" data-action="save-settings">${icon('check')}Kaydet ve Tara</button>
            <button class="btn btn-ghost btn-sm" data-action="rescan">${icon('refresh')}Yeniden Tara</button>
            <button class="btn btn-ghost btn-sm" data-action="emby">Emby'den Güncelle</button>
            <button class="btn btn-ghost btn-sm" data-action="enrich">Eksik Bilgileri Tekrar Ara</button>
          </div>
        </div></div>
      <div class="section"><div class="section-head"><h3>Diğer cihazlardan bağlan</h3></div>
        <div class="urls">${(s.urls.length ? s.urls : [location.origin]).map(u => `<div class="url"><span>${esc(u)}</span><button class="icon-btn" data-copy="${esc(u)}" title="Kopyala">${icon('copy')}</button></div>`).join('')}</div>
        <p style="color:var(--dim);font-size:13px;margin:10px 0 0">Telefon, tablet veya TV tarayıcısından bu adrese girin. Aynı Wi-Fi ağında olmanız yeterli.</p></div>
      <div class="section"><div class="section-head"><h3>Klavye kısayolları</h3></div>
        <div class="keys">
          <div><kbd>/</kbd>Ara</div><div><kbd>Boşluk</kbd>Oynat / Duraklat</div><div><kbd>← →</kbd>10 sn geri / ileri</div>
          <div><kbd>↑ ↓</kbd>Ses</div><div><kbd>F</kbd>Tam ekran</div><div><kbd>M</kbd>Sessiz</div>
          <div><kbd>C</kbd>Ses ve altyazı</div><div><kbd>N</kbd>Sonraki bölüm</div><div><kbd>Esc</kbd>Geri</div>
        </div></div>
      <p style="color:#52525b;font-size:12px;margin-top:34px">Homeflix 2 · Film bilgileri TMDb, Emby ve OMDb'den alınır.</p>
    </div>`;
}

async function settingsAction(a) {
  if (a === 'save-settings') {
    await api.post('/api/settings', { movie_dir: $('#conf-movie').value, series_dir: $('#conf-series').value, omdb_api_key: $('#conf-key').value });
    await api.post('/api/scan');
    toast('Ayarlar kaydedildi, tarama başladı');
  } else if (a === 'rescan') { await api.post('/api/rescan'); toast('Diskteki dosyalar taranıyor…'); }
  else if (a === 'emby') { const r = await api.post('/api/sync_emby'); toast(`Emby: ${r.movies} film, ${r.series} dizi güncellendi`); await refresh(); }
  else if (a === 'enrich') { await api.post('/api/enrich'); toast('Eksik bilgiler yeniden aranıyor'); }
  pollStatus(true);
}

/* ================================================================ status polling */
let pollTimer = null, wasBusy = false;
async function pollStatus(now) {
  clearTimeout(pollTimer);
  if (now || !document.hidden) {
    try {
      const st = await api.get('/api/status');
      $('#status').classList.toggle('on', st.busy);
      $('#status-text').textContent = st.tasks.join(' · ');
      if ((st.version !== S.version && !st.busy) || (wasBusy && !st.busy)) await refresh();
      else if (st.version !== S.version) await Promise.all([loadLibrary(), loadUser()]);
      wasBusy = st.busy;
    } catch {}
  }
  pollTimer = setTimeout(pollStatus, wasBusy ? 4000 : 30000);
}
async function refresh() {
  await Promise.all([loadLibrary(), loadUser()]);
  if (!P.open) softRender();
}

/* ================================================================ player */
const P = {
  open: false, kind: '', id: 0, info: null, mode: 'direct', offset: 0, audio: 0, subs: null, subDelay: 0, subIdx: -1,
  hideT: 0, lastSave: 0, raf: 0, next: null, upnextT: 0, upnextDismissed: false, speed: 1, fsFallback: false,
  seekTarget: null, lastSubHTML: '',
};
const V = () => $('#video');

function pTime() { const v = V(); return P.mode === 'stream' ? P.offset + (v.currentTime || 0) : (v.currentTime || 0); }
function pDur() { const v = V(); return P.mode === 'direct' && isFinite(v.duration) && v.duration > 0 ? v.duration : (P.info?.duration || 0); }

async function play(kind, id, opts = {}) {
  const pl = $('#player');
  if (!P.open) {
    P.open = true;
    pl.classList.add('open', 'ui', 'loading');
    pushOverlay('player', closePlayerNow);
    document.body.classList.add('locked');
  } else {
    savePosition(true);
    pl.classList.add('loading');
  }
  Object.assign(P, { kind, id, info: null, subs: null, subIdx: -1, audio: 0, next: null, upnextDismissed: false, lastSubHTML: '' });
  $('#p-subs').innerHTML = '';
  $('#upnext').classList.remove('open');
  $('#p-panel').classList.remove('open');
  $('#p-title').textContent = opts.title || '';
  $('#p-sub').textContent = '';
  let info;
  try { info = await api.get(`/api/media/${kind}/${id}`); } catch { toast('Video dosyası bulunamadı. Disk bağlı mı?'); return back(); }
  if (P.kind !== kind || P.id !== id) return;
  P.info = info;
  P.next = info.next || null;
  $('#p-title').textContent = info.title;
  $('#p-sub').textContent = info.sub || '';
  $('#p-next').hidden = !P.next;
  document.title = `${info.title} · Homeflix`;
  const start = opts.from !== undefined ? +opts.from : (info.resume > 30 ? info.resume : 0);
  P.mode = info.direct ? 'direct' : 'stream';
  loadSource(start);
  if (start > 30) toast(`Kaldığın yerden devam ediliyor · ${fmtTime(start)}`);
  autoSubtitles();
  mediaSession();
  showUI();
  cancelAnimationFrame(P.raf);
  P.raf = requestAnimationFrame(tick);
}

function loadSource(t) {
  const v = V();
  const pl = $('#player');
  pl.classList.add('loading');
  t = Math.max(0, t || 0);
  const base = `/play/${P.kind}/${P.id}`;
  if (P.mode === 'stream') {
    P.offset = t;
    v.src = `${base}?mode=stream&a=${P.audio}${t ? '&t=' + t.toFixed(1) : ''}`;
  } else {
    P.offset = 0;
    v.src = base;
    if (t) v.addEventListener('loadedmetadata', () => { v.currentTime = t; }, { once: true });
  }
  v.playbackRate = P.speed;
  v.play().catch(() => {});
}

function seek(t) {
  const v = V();
  t = clamp(t, 0, Math.max(0, pDur() - 1));
  if (P.mode === 'direct') { v.currentTime = t; return; }
  const rel = t - P.offset;
  for (let i = 0; i < v.buffered.length; i++) {
    if (rel >= v.buffered.start(i) && rel <= v.buffered.end(i) - 0.5) { v.currentTime = rel; return; }
  }
  loadSource(t);
}

function togglePlay() {
  const v = V();
  if (v.paused) { v.play().catch(() => {}); flash('play'); } else { v.pause(); flash('pause'); }
}
function flash(ic) {
  const f = $('#p-flash');
  f.innerHTML = icon(ic, 'fill');
  f.classList.remove('go'); void f.offsetWidth; f.classList.add('go');
}
function seekHint(dir) {
  const h = $(dir < 0 ? '#p-hint-l' : '#p-hint-r');
  h.classList.add('on');
  clearTimeout(h._t); h._t = setTimeout(() => h.classList.remove('on'), 600);
}

function showUI() {
  const pl = $('#player');
  pl.classList.add('ui');
  pl.classList.remove('idle');
  clearTimeout(P.hideT);
  P.hideT = setTimeout(() => {
    if (V().paused || $('#p-panel').classList.contains('open') || $('#p-bar').classList.contains('drag')) return;
    pl.classList.remove('ui');
    pl.classList.add('idle');
  }, 3200);
}

function tick() {
  if (!P.open) return;
  const v = V(), t = pTime(), d = pDur();
  if (!$('#p-bar').classList.contains('drag')) {
    const pct = d ? clamp(t / d * 100, 0, 100) : 0;
    $('#p-played').style.width = pct + '%';
    $('#p-knob').style.left = pct + '%';
    $('#p-cur').textContent = fmtTime(t);
  }
  $('#p-dur').textContent = fmtTime(d);
  let bufEnd = 0;
  for (let i = 0; i < v.buffered.length; i++) if (v.buffered.start(i) <= v.currentTime + 1) bufEnd = Math.max(bufEnd, v.buffered.end(i));
  $('#p-buf').style.width = d ? clamp((P.offset + bufEnd) / d * 100, 0, 100) + '%' : '0';
  renderSubtitle(t);
  if (P.next && d && !P.upnextDismissed && d - t < 30 && d - t > 0 && !v.paused) showUpNext();
  if (!v.paused && Date.now() - P.lastSave > 10000) savePosition();
  P.raf = requestAnimationFrame(tick);
}

function savePosition(beacon = false) {
  if (!P.info) return;
  const t = pTime(), d = pDur();
  if (t < 5 || !d) return;
  P.lastSave = Date.now();
  const body = JSON.stringify({ key: `${P.kind}:${P.id}`, position: t, duration: d });
  if (beacon && navigator.sendBeacon) navigator.sendBeacon('/api/progress', new Blob([body], { type: 'application/json' }));
  else fetch('/api/progress', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body, keepalive: true }).catch(() => {});
  if (P.kind === 'm') S.progress[`m:${P.id}`] = [t, d, t >= d * 0.93 ? 1 : 0, Date.now() / 1000];
}

function closePlayerNow() {
  savePosition(true);
  const v = V();
  v.pause();
  v.removeAttribute('src');
  v.load();
  P.open = false;
  cancelAnimationFrame(P.raf);
  clearTimeout(P.upnextT);
  $('#player').classList.remove('open', 'ui', 'idle', 'loading');
  $('#p-panel').classList.remove('open');
  $('#upnext').classList.remove('open');
  document.title = 'Homeflix';
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
  if (P.fsFallback && window.pywebview?.api) { window.pywebview.api.toggle_fullscreen(); P.fsFallback = false; }
  setTimeout(async () => {
    await loadUser();
    if (detailKey) { const it = S.byKey.get(detailKey); if (it && it.kind !== 'c') { renderDetail(it); if (it.kind === 's') loadEpisodes(it); } }
    else softRender();
  }, 400);
}

async function toggleFullscreen() {
  const pl = $('#player');
  try {
    if (document.fullscreenElement || document.webkitFullscreenElement) {
      await (document.exitFullscreen?.() || document.webkitExitFullscreen?.());
    } else if (pl.requestFullscreen || pl.webkitRequestFullscreen) {
      await (pl.requestFullscreen ? pl.requestFullscreen() : pl.webkitRequestFullscreen());
    } else throw new Error('no-fs');
  } catch {
    if (window.pywebview?.api) { window.pywebview.api.toggle_fullscreen(); P.fsFallback = !P.fsFallback; }
    else if (V().webkitEnterFullscreen) V().webkitEnterFullscreen();
  }
}
document.addEventListener('fullscreenchange', () => { $('#p-fsicon').setAttribute('href', document.fullscreenElement ? '#i-shrink' : '#i-expand'); });

function mediaSession() {
  if (!('mediaSession' in navigator) || !P.info) return;
  const art = P.kind === 'm' ? img('m', P.id, 'poster', 500) : img('s', P.info.sid, 'poster', 500);
  try {
    navigator.mediaSession.metadata = new MediaMetadata({ title: P.info.title, artist: P.info.sub || 'Homeflix', artwork: [{ src: art, sizes: '500x750', type: 'image/jpeg' }] });
    navigator.mediaSession.setActionHandler('play', () => V().play());
    navigator.mediaSession.setActionHandler('pause', () => V().pause());
    navigator.mediaSession.setActionHandler('seekbackward', () => seek(pTime() - 10));
    navigator.mediaSession.setActionHandler('seekforward', () => seek(pTime() + 10));
    navigator.mediaSession.setActionHandler('nexttrack', P.next ? () => playNext() : null);
  } catch {}
}

function playNext() {
  if (!P.next) return;
  savePosition();
  api.post('/api/progress', { key: `${P.kind}:${P.id}`, position: pDur(), duration: pDur() }).catch(() => {});
  play('e', P.next.id, { from: 0 });
}

function showUpNext() {
  const box = $('#upnext');
  if (box.classList.contains('open')) return;
  const n = P.next;
  const still = n.still ? `/img/still/${n.id}` : (P.info.sid ? img('s', P.info.sid, 'backdrop', 640) : '');
  let left = 10;
  box.innerHTML = `<div class="still" style="background-image:url('${still}')">
      <svg class="ring" viewBox="0 0 64 64"><circle cx="32" cy="32" r="28" fill="rgba(0,0,0,.55)" stroke="rgba(255,255,255,.25)" stroke-width="4"/>
      <circle id="upring" cx="32" cy="32" r="28" fill="none" stroke="#fff" stroke-width="4" stroke-dasharray="176" stroke-dashoffset="0" transform="rotate(-90 32 32)" style="transition:stroke-dashoffset 1s linear"/>
      <text id="upnum" x="32" y="39" text-anchor="middle" fill="#fff" font-size="20" font-weight="700" font-family="sans-serif">${left}</text></svg></div>
    <div class="body"><small>Sonraki bölüm</small><strong>${esc(n.label)}${n.name ? ' · ' + esc(n.name) : ''}</strong>
      <div class="actions"><button class="btn btn-play" data-p="next">${icon('play', 'fill')}Şimdi Oynat</button><button class="btn btn-ghost" data-p="dismiss-next">Kapat</button></div></div>`;
  box.classList.add('open');
  const step = () => {
    left--;
    const ring = $('#upring'), num = $('#upnum');
    if (ring) ring.style.strokeDashoffset = String(176 * (1 - left / 10));
    if (num) num.textContent = Math.max(0, left);
    if (left <= 0) return playNext();
    P.upnextT = setTimeout(step, 1000);
  };
  clearTimeout(P.upnextT);
  P.upnextT = setTimeout(step, 1000);
}
function dismissUpNext() { clearTimeout(P.upnextT); P.upnextDismissed = true; $('#upnext').classList.remove('open'); }

/* ---------------- subtitles */
function parseTime(s) {
  const p = s.trim().replace(',', '.').split(':').map(Number);
  return p.length === 3 ? p[0] * 3600 + p[1] * 60 + p[2] : p[0] * 60 + p[1];
}
function sanitizeCue(text) {
  return esc(text.replace(/\{\\[^}]*\}/g, '').replace(/<(?!\/?[ibu]>)[^>]+>/gi, ''))
    .replace(/&lt;(\/?)([ibu])&gt;/gi, '<$1$2>');
}
function parseSubs(text) {
  const cues = [];
  text = text.replace(/\r/g, '').replace(/^﻿/, '');
  if (!/-->/.test(text)) return cues;
  for (const block of text.split(/\n{2,}/)) {
    const lines = block.split('\n');
    const i = lines.findIndex(l => l.includes('-->'));
    if (i < 0) continue;
    const m = lines[i].match(/([\d:.,]+)\s*-->\s*([\d:.,]+)/);
    if (!m) continue;
    const body = lines.slice(i + 1).join('\n').trim();
    if (body) cues.push({ s: parseTime(m[1]), e: parseTime(m[2]), h: sanitizeCue(body) });
  }
  return cues.sort((a, b) => a.s - b.s);
}
function setSubs(text, label, source) {
  const cues = parseSubs(text || '');
  if (!cues.length) { toast('Altyazı dosyası okunamadı'); return false; }
  P.subs = { cues, label, source };
  P.lastSubHTML = null;
  toast(`${icon('cc')} Altyazı: <b>${esc(label)}</b>`);
  if ($('#p-panel').classList.contains('open')) renderPanel();
  return true;
}
function renderSubtitle(t) {
  const el = $('#p-subs');
  let html = '';
  if (P.subs) {
    const cues = P.subs.cues, tt = t - P.subDelay;
    let lo = 0, hi = cues.length - 1, idx = -1;
    while (lo <= hi) { const mid = (lo + hi) >> 1; if (cues[mid].s <= tt) { idx = mid; lo = mid + 1; } else hi = mid - 1; }
    const out = [];
    for (let i = idx; i >= 0 && i > idx - 6; i--) if (cues[i].e > tt) out.unshift(cues[i].h);
    html = out.map(h => `<span>${h}</span>`).join('<br>');
  }
  if (html !== P.lastSubHTML) { el.innerHTML = html; P.lastSubHTML = html; }
}
async function loadServerSub(url, label, source) {
  const slow = source.startsWith('emb') ? setTimeout(() => toast('Gömülü altyazı hazırlanıyor, bu biraz sürebilir…'), 900) : 0;
  try {
    const r = await fetch(url);
    clearTimeout(slow);
    if (!r.ok) throw 0;
    setSubs(await r.text(), label, source);
  } catch { clearTimeout(slow); toast('Altyazı yüklenemedi'); }
}
function autoSubtitles() {
  const info = P.info;
  if (!info || store.get('subsOff', false)) return;
  const k = P.kind, id = P.id;
  if (info.local_subs.length) return loadServerSub(`/sub/${k}/${id}/local/0`, info.local_subs[0].label, 'local:0');
  const turkishAudio = info.audio.some(a => ['tur', 'tr'].includes(a.lang));
  const tr = info.subs.find(s => ['tur', 'tr'].includes(s.lang));
  if (tr && !turkishAudio) loadServerSub(`/sub/${k}/${id}/embedded/${tr.index}`, tr.label, 'emb:' + tr.index);
}
function loadSubFile(file) {
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    let text = e.target.result;
    if (/�/.test(text)) { const r2 = new FileReader(); r2.onload = e2 => setSubs(e2.target.result, file.name, 'file'); r2.readAsText(file, 'windows-1254'); return; }
    setSubs(text, file.name, 'file');
  };
  reader.readAsText(file, 'utf-8');
}

function renderPanel(view = 'main') {
  const pn = $('#p-panel'), info = P.info;
  if (!info) return;
  if (view === 'online') {
    pn.innerHTML = `<button class="back" data-p="panel-main">${icon('left')}Çevrimiçi altyazı</button><div class="results" id="sub-results"><div style="padding:30px;display:grid;place-items:center"><div class="spin"></div></div></div>`;
    api.get(`/api/subs/search/${P.kind}/${P.id}`).then(list => {
      const box = $('#sub-results');
      if (!box) return;
      box.innerHTML = list.length ? list.map(s => `<button class="opt" data-p="dl-sub" data-fid="${s.file_id}" data-label="${esc(s.release || s.lang)}">
        <span><b style="color:#fff">${s.lang === 'tr' ? 'Türkçe' : 'İngilizce'}</b> · ${esc(s.release || '')}</span><small>${s.match === 'HASH' ? 'tam eşleşme · ' : ''}${s.downloads} ⬇</small></button>`).join('')
        : '<p style="padding:20px;color:var(--muted)">Bu video için altyazı bulunamadı.</p>';
    }).catch(() => { const box = $('#sub-results'); if (box) box.innerHTML = '<p style="padding:20px;color:var(--muted)">Arama başarısız. İnternet bağlantınızı kontrol edin.</p>'; });
    return;
  }
  const src = P.subs?.source || 'off';
  const opt = (on, attrs, label, small = '') => `<button class="opt${on ? ' on' : ''}" ${attrs}>${icon('check', 'chk')}<span>${esc(label)}</span>${small ? `<small>${esc(small)}</small>` : ''}</button>`;
  const audio = (info.audio.length ? info.audio : [{ index: 0, label: 'Varsayılan' }]).map(a => opt(P.audio === a.index, `data-p="audio" data-i="${a.index}"`, a.label, a.codec ? a.codec.toUpperCase() : '')).join('');
  let subs = opt(src === 'off', 'data-p="sub-off"', 'Kapalı');
  subs += info.local_subs.map(s => opt(src === 'local:' + s.index, `data-p="sub" data-url="/sub/${P.kind}/${P.id}/local/${s.index}" data-src="local:${s.index}" data-label="${esc(s.label)}"`, s.label, 'dosya')).join('');
  subs += info.subs.map(s => opt(src === 'emb:' + s.index, `data-p="sub" data-url="/sub/${P.kind}/${P.id}/embedded/${s.index}" data-src="emb:${s.index}" data-label="${esc(s.label)}"`, s.label, 'gömülü')).join('');
  if (P.subs && (src === 'file' || src === 'online')) subs += opt(true, '', P.subs.label, src === 'file' ? 'yüklendi' : 'indirildi');
  subs += `<button class="opt" data-p="panel-online">${icon('globe')}<span>Çevrimiçi ara…</span></button>`;
  subs += `<button class="opt" data-p="sub-file">${icon('upload')}<span>Dosyadan yükle…</span></button>`;
  const size = store.get('subSize', 'm');
  pn.innerHTML = `<div class="cols"><div class="col"><h5>Ses</h5>${audio}</div><div class="col"><h5>Altyazı</h5>${subs}</div></div>
    <div class="foot">
      <span>Boyut</span><div class="seg">${[['s', 'Küçük'], ['m', 'Orta'], ['l', 'Büyük']].map(([k, l]) => `<button class="${size === k ? 'on' : ''}" data-p="sub-size" data-v="${k}">${l}</button>`).join('')}</div>
      <span>Senkron</span><div class="seg"><button data-p="sub-delay" data-v="-0.5">−0,5</button><button class="on" style="min-width:58px">${P.subDelay > 0 ? '+' : ''}${P.subDelay.toFixed(1).replace('.', ',')} sn</button><button data-p="sub-delay" data-v="0.5">+0,5</button></div>
      <div class="seg"><button class="${store.get('subBox', false) ? 'on' : ''}" data-p="sub-box">Arka plan</button></div>
    </div>`;
}
function applySubStyle() {
  const size = { s: 'clamp(15px, 2vw, 32px)', m: 'clamp(18px, 2.6vw, 42px)', l: 'clamp(22px, 3.4vw, 54px)' }[store.get('subSize', 'm')];
  document.documentElement.style.setProperty('--sub-size', size);
  $('#p-subs').classList.toggle('boxed', store.get('subBox', false));
}

async function playerAction(a, el) {
  const v = V();
  switch (a) {
    case 'close': return back();
    case 'toggle': return togglePlay();
    case 'back10': seekHint(-1); return seek(pTime() - 10);
    case 'fwd10': seekHint(1); return seek(pTime() + 10);
    case 'mute': v.muted = !v.muted; return updateVolIcon();
    case 'fullscreen': return toggleFullscreen();
    case 'next': return playNext();
    case 'dismiss-next': return dismissUpNext();
    case 'speed': {
      const speeds = [1, 1.25, 1.5, 2, 0.75];
      P.speed = speeds[(speeds.indexOf(P.speed) + 1) % speeds.length];
      v.playbackRate = P.speed;
      $('#p-speedtag').textContent = P.speed === 1 ? '' : P.speed + 'x';
      return toast(`Oynatma hızı ${String(P.speed).replace('.', ',')}x`, 1400);
    }
    case 'panel': {
      const pn = $('#p-panel');
      if (pn.classList.toggle('open')) renderPanel();
      return showUI();
    }
    case 'panel-main': return renderPanel();
    case 'panel-online': return renderPanel('online');
    case 'audio': {
      const i = +el.dataset.i;
      if (i === P.audio) return;
      const t = pTime();
      P.audio = i;
      P.mode = (P.info.direct && i === 0) ? 'direct' : 'stream';
      loadSource(t);
      return renderPanel();
    }
    case 'sub-off': P.subs = null; store.set('subsOff', true); P.lastSubHTML = null; return renderPanel();
    case 'sub': store.set('subsOff', false); await loadServerSub(el.dataset.url, el.dataset.label, el.dataset.src); return renderPanel();
    case 'sub-file': return $('#sub-file').click();
    case 'dl-sub': {
      el.innerHTML = '<div class="spin"></div><span>İndiriliyor…</span>';
      try { const vtt = await api.post('/api/subs/download', { file_id: +el.dataset.fid }); if (setSubs(vtt, el.dataset.label, 'online')) renderPanel(); }
      catch { toast('Altyazı indirilemedi (günlük limit dolmuş olabilir)'); renderPanel('online'); }
      return;
    }
    case 'sub-size': store.set('subSize', el.dataset.v); applySubStyle(); return renderPanel();
    case 'sub-box': store.set('subBox', !store.get('subBox', false)); applySubStyle(); return renderPanel();
    case 'sub-delay': P.subDelay = Math.round((P.subDelay + parseFloat(el.dataset.v)) * 10) / 10; P.lastSubHTML = null; return renderPanel();
  }
}

function updateVolIcon() {
  const v = V();
  $('#p-volicon').setAttribute('href', v.muted || v.volume === 0 ? '#i-mute' : '#i-vol');
  $('#p-volume').value = v.muted ? 0 : v.volume;
  store.set('volume', v.volume);
}

function wirePlayer() {
  const pl = $('#player'), v = V(), bar = $('#p-bar');
  v.volume = store.get('volume', 1);
  applySubStyle();
  updateVolIcon();
  v.addEventListener('waiting', () => pl.classList.add('loading'));
  v.addEventListener('seeking', () => pl.classList.add('loading'));
  ['playing', 'canplay', 'seeked'].forEach(e => v.addEventListener(e, () => pl.classList.remove('loading')));
  v.addEventListener('play', () => { $('#p-playicon').setAttribute('href', '#i-pause'); showUI(); });
  v.addEventListener('pause', () => { $('#p-playicon').setAttribute('href', '#i-play'); showUI(); savePosition(); });
  v.addEventListener('ended', () => {
    savePosition();
    if (P.next && !P.upnextDismissed) playNext();
    else if (P.mode === 'stream' && pDur() - pTime() > 20) loadSource(pTime());
    else { pl.classList.add('ui'); api.post('/api/progress', { key: `${P.kind}:${P.id}`, position: pDur(), duration: pDur() }).catch(() => {}); }
  });
  v.addEventListener('error', () => {
    if (!P.open || !v.getAttribute('src')) return;
    if (P.mode === 'direct') { P.mode = 'stream'; loadSource(pTime()); }
    else { pl.classList.remove('loading'); toast('Video oynatılamadı. Dosya bozuk ya da desteklenmiyor olabilir.', 4000); }
  });
  $('#p-volume').addEventListener('input', e => { v.volume = +e.target.value; v.muted = v.volume === 0; updateVolIcon(); });

  pl.addEventListener('pointermove', showUI);
  pl.addEventListener('click', e => {
    const b = e.target.closest('[data-p]');
    if (b) { e.stopPropagation(); return playerAction(b.dataset.p, b); }
    if (e.target.closest('.p-panel, .upnext, .p-bottom, .p-top')) return;
    if ($('#p-panel').classList.contains('open')) { $('#p-panel').classList.remove('open'); return; }
    if (matchMedia('(hover: none)').matches && !pl.classList.contains('ui')) return showUI();
    togglePlay();
  });
  pl.addEventListener('dblclick', e => { if (!e.target.closest('.p-bottom, .p-top, .p-panel, .upnext')) toggleFullscreen(); });

  const posFromEvent = e => { const r = $('.p-track', bar).getBoundingClientRect(); return clamp((e.clientX - r.left) / r.width, 0, 1); };
  const tip = $('#p-tip');
  const preview = f => {
    const t = f * pDur();
    tip.textContent = fmtTime(t);
    tip.style.left = clamp(f * 100, 3, 97) + '%';
    return t;
  };
  bar.addEventListener('pointermove', e => preview(posFromEvent(e)));
  bar.addEventListener('pointerdown', e => {
    bar.setPointerCapture(e.pointerId);
    bar.classList.add('drag');
    const upd = ev => { const f = posFromEvent(ev); preview(f); $('#p-played').style.width = f * 100 + '%'; $('#p-knob').style.left = f * 100 + '%'; $('#p-cur').textContent = fmtTime(f * pDur()); };
    upd(e);
    const move = ev => upd(ev);
    const up = ev => {
      bar.removeEventListener('pointermove', move);
      bar.removeEventListener('pointerup', up);
      bar.removeEventListener('pointercancel', up);
      bar.classList.remove('drag');
      seek(posFromEvent(ev) * pDur());
      showUI();
    };
    bar.addEventListener('pointermove', move);
    bar.addEventListener('pointerup', up);
    bar.addEventListener('pointercancel', up);
  });

  $('#sub-file').addEventListener('change', e => { loadSubFile(e.target.files[0]); e.target.value = ''; });
  pl.addEventListener('dragover', e => { e.preventDefault(); pl.classList.add('dragover'); });
  pl.addEventListener('dragleave', e => { if (e.target === pl || !pl.contains(e.relatedTarget)) pl.classList.remove('dragover'); });
  pl.addEventListener('drop', e => { e.preventDefault(); pl.classList.remove('dragover'); loadSubFile(e.dataTransfer.files[0]); });
  document.addEventListener('visibilitychange', () => { if (document.hidden && P.open) savePosition(true); });
  window.addEventListener('pagehide', () => { if (P.open) savePosition(true); });
}

function playerKeys(e) {
  const v = V();
  const k = e.key.toLowerCase();
  const map = {
    ' ': togglePlay, k: togglePlay,
    arrowleft: () => { seekHint(-1); seek(pTime() - 10); }, j: () => { seekHint(-1); seek(pTime() - 10); },
    arrowright: () => { seekHint(1); seek(pTime() + 10); }, l: () => { seekHint(1); seek(pTime() + 10); },
    arrowup: () => { v.muted = false; v.volume = clamp(v.volume + 0.1, 0, 1); updateVolIcon(); toast(`Ses %${Math.round(v.volume * 100)}`, 900); },
    arrowdown: () => { v.volume = clamp(v.volume - 0.1, 0, 1); updateVolIcon(); toast(`Ses %${Math.round(v.volume * 100)}`, 900); },
    f: toggleFullscreen, m: () => { v.muted = !v.muted; updateVolIcon(); },
    c: () => playerAction('panel'), n: () => P.next && playNext(),
    escape: () => {
      if ($('#p-panel').classList.contains('open')) return $('#p-panel').classList.remove('open');
      if (!document.fullscreenElement) back();
    },
  };
  if (/^[0-9]$/.test(k)) { seek(pDur() * (+k) / 10); showUI(); e.preventDefault(); return; }
  if (map[k]) { e.preventDefault(); map[k](); showUI(); }
}

/* ================================================================ global events */
function shuffleMovie() {
  const good = S.titles.filter(t => parseFloat(t.r) >= 6);
  const pool = good.length ? good : S.titles;
  if (!pool.length) return;
  const m = pool[Math.floor(Math.random() * pool.length)];
  toast(`${icon('shuffle')} Rastgele seçildi: <b>${esc(m.t)}</b>`, 2200);
  setTimeout(() => play('m', m.id, { title: m.t }), 1100);
}

document.addEventListener('click', async e => {
  const t = e.target;
  if (t.closest('#player')) return;
  const forget = t.closest('[data-forget]');
  if (forget) {
    e.stopPropagation();
    await fetch('/api/progress/' + encodeURIComponent(forget.dataset.forget), { method: 'DELETE' });
    await loadUser();
    return softRender();
  }
  const pl = t.closest('[data-play]');
  if (pl && pl.dataset.play) {
    const [kind, id] = pl.dataset.play.split(':');
    const it = kind === 'm' ? S.movieToTitle.get(+id) : null;
    return play(kind, +id, { title: it?.t, ...(pl.dataset.from !== undefined ? { from: +pl.dataset.from } : {}) });
  }
  const lst = t.closest('[data-list]');
  if (lst) return toggleList(lst.dataset.list, lst);
  const open = t.closest('[data-open]');
  if (open) {
    if ($('#search').classList.contains('open')) { back(); await new Promise(r => setTimeout(r, 30)); }
    return openDetail(open.dataset.open);
  }
  const cp = t.closest('[data-copy]');
  if (cp) { navigator.clipboard?.writeText(cp.dataset.copy); return toast('Adres kopyalandı'); }
  const go = t.closest('[data-goto]');
  if (go) { back(); setTimeout(() => { location.hash = go.dataset.goto; }, 60); return; }
  const act = t.closest('[data-action]');
  if (act) {
    const a = act.dataset.action;
    if (a === 'back') return back();
    if (a === 'search') return openSearch();
    if (a === 'settings') return openSettings();
    if (a === 'shuffle') return shuffleMovie();
    return settingsAction(a);
  }
  if (t.hasAttribute('data-dismiss')) back();
});

document.addEventListener('keydown', e => {
  if (P.open) return playerKeys(e);
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName);
  if (e.key === 'Escape' && stack.length) { e.preventDefault(); return back(); }
  if (typing) return;
  if (e.key === '/' || (e.key.toLowerCase() === 'k' && (e.ctrlKey || e.metaKey))) { e.preventDefault(); return openSearch(); }
  if ((e.key === 'Enter' || e.key === ' ') && document.activeElement?.matches('[data-open], [data-play]')) {
    e.preventDefault(); document.activeElement.click();
  }
});

let searchT = 0;
$('#search-input').addEventListener('input', e => { clearTimeout(searchT); searchT = setTimeout(() => runSearch(e.target.value), 90); });
$('#search-input').addEventListener('keydown', e => { if (e.key === 'Enter') { const first = $('#search-results [data-open]'); if (first) first.click(); } });
window.addEventListener('scroll', () => $('#nav').classList.toggle('solid', window.scrollY > 30), { passive: true });
window.addEventListener('hashchange', () => { while (stack.length) { const o = stack.pop(); o.onClose(); } document.body.classList.remove('locked'); route(); });
document.addEventListener('visibilitychange', () => { if (!document.hidden) pollStatus(); });

/* ================================================================ boot */
async function migrateV1() {
  if (store.get('hf2_migrated', false)) return;
  try {
    const favorites = store.get('favorites', []);
    const positions = {};
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith('pos_')) positions[k.slice(4)] = parseFloat(localStorage.getItem(k));
    }
    if (favorites.length || Object.keys(positions).length) await api.post('/api/migrate', { favorites, positions });
    store.set('hf2_migrated', true);
  } catch {}
}

async function boot() {
  S.browse.movies.sort = store.get('sort_movies', 'added');
  S.browse.series.sort = store.get('sort_series', 'added');
  wirePlayer();
  $('#view').innerHTML = `<div style="height:100vh;display:grid;place-items:center"><div class="spin" style="width:40px;height:40px;border-width:3px"></div></div>`;
  await migrateV1();
  try { await Promise.all([loadLibrary(), loadUser()]); }
  catch { $('#view').innerHTML = emptyState('Sunucuya ulaşılamıyor', 'Homeflix sunucusunun çalıştığından emin olun ve sayfayı yenileyin.'); return; }
  route();
  pollStatus(true);
}
boot();

/* Homeflix TV: kumanda (D-pad) ile gezinme katmanı.
 * Sayfa her yüklendiğinde enjekte edilir; tek seferlik kurulur. */
(function () {
  if (window.__hfTv) return;
  window.__hfTv = true;

  var style = document.createElement('style');
  style.textContent =
    '.hf-focus{outline:4px solid #fff!important;outline-offset:3px!important;' +
    'box-shadow:0 0 0 8px rgba(229,9,20,.85)!important;border-radius:8px}';
  document.head.appendChild(style);

  var CLICKABLE = 'a[href],button,input:not([type=hidden]),select,textarea,summary,' +
    '[tabindex]:not([tabindex="-1"]),[role=button],[role=link],[role=tab],[role=menuitem],[onclick]';
  var GUESS = 'div,li,span,img,figure,article,section,label';
  var FORM = /^(INPUT|TEXTAREA|SELECT)$/;
  var cur = null;

  function curValid() {
    return cur && document.documentElement.contains(cur) &&
      cur.getBoundingClientRect().width > 0;
  }

  function candidates() {
    var out = [], seen = new Set(), vh = window.innerHeight, vw = window.innerWidth;

    function add(el) {
      if (seen.has(el) || el.disabled) return;
      var r = el.getBoundingClientRect();
      if (r.width < 8 || r.height < 8) return;
      var cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none' ||
          cs.pointerEvents === 'none' || parseFloat(cs.opacity) < 0.05) return;
      var cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      if (cx >= 0 && cx < vw && cy >= 0 && cy < vh) {
        var t = document.elementFromPoint(cx, cy);
        if (t && !(el.contains(t) || t.contains(el))) return;
      }
      seen.add(el);
      out.push({ el: el, r: r });
    }

    var list = document.querySelectorAll(CLICKABLE), i;
    for (i = 0; i < list.length; i++) add(list[i]);

    var g = document.querySelectorAll(GUESS);
    for (i = 0; i < g.length; i++) {
      var el = g[i];
      if (seen.has(el)) continue;
      var r = el.getBoundingClientRect();
      if (r.width < 24 || r.height < 24) continue;
      if (r.bottom < -vh || r.top > vh * 2) continue;
      if (getComputedStyle(el).cursor !== 'pointer') continue;
      var p = el.parentElement;
      if (p && getComputedStyle(p).cursor === 'pointer') continue; // yalnızca en dıştaki
      add(el);
    }
    return out;
  }

  function setCur(el, vertical) {
    if (cur) cur.classList.remove('hf-focus');
    var a = document.activeElement;
    if (a && a !== document.body && a !== el) { try { a.blur(); } catch (e) {} }
    cur = el;
    el.classList.add('hf-focus');
    if (!FORM.test(el.tagName)) {
      if (!el.hasAttribute('tabindex') && !/^(A|BUTTON|SUMMARY)$/.test(el.tagName)) {
        el.setAttribute('tabindex', '-1');
      }
      try { el.focus({ preventScroll: true }); } catch (e) {}
    }
    try {
      el.scrollIntoView({
        block: vertical ? 'center' : 'nearest',
        inline: vertical ? 'nearest' : 'center'
      });
    } catch (e) {}
  }

  function move(dir) {
    var list = candidates();
    if (!list.length) return;

    var a = document.activeElement;
    if (a && a !== document.body && a !== cur && a.matches && a.matches(CLICKABLE)) cur = a;

    var vertical = dir === 'up' || dir === 'down';

    if (!curValid()) {
      var first = null, fs = 1e12;
      list.forEach(function (c) {
        if (c.r.bottom <= 0 || c.r.top >= window.innerHeight) return;
        var s = Math.max(c.r.top, 0) * 2 + c.r.left;
        if (s < fs) { fs = s; first = c.el; }
      });
      setCur(first || list[0].el, vertical);
      return;
    }

    var cr = cur.getBoundingClientRect();
    var ccx = cr.left + cr.width / 2, ccy = cr.top + cr.height / 2;
    var best = null, bs = 1e12;

    list.forEach(function (c) {
      if (c.el === cur) return;
      var r = c.r;
      var dx = r.left + r.width / 2 - ccx, dy = r.top + r.height / 2 - ccy;
      var prim, sec;
      if (dir === 'right') { prim = dx; sec = Math.abs(dy); }
      else if (dir === 'left') { prim = -dx; sec = Math.abs(dy); }
      else if (dir === 'down') { prim = dy; sec = Math.abs(dx); }
      else { prim = -dy; sec = Math.abs(dx); }
      if (prim <= 4) return;
      if (!vertical && sec > Math.max(cr.height, r.height) * 0.8) return; // aynı satırda kal
      var score = prim + sec * (vertical ? 2 : 3);
      if (score < bs) { bs = score; best = c.el; }
    });

    if (best) {
      setCur(best, vertical);
    } else if (vertical) {
      window.scrollBy(0, (dir === 'down' ? 1 : -1) * Math.round(window.innerHeight * 0.7));
    }
  }

  function mainVideo() {
    var vs = document.querySelectorAll('video'), best = null, area = 0;
    for (var i = 0; i < vs.length; i++) {
      var r = vs[i].getBoundingClientRect();
      if (r.width * r.height > area) { area = r.width * r.height; best = vs[i]; }
    }
    return best;
  }

  function playerOpen() {
    var v = mainVideo();
    if (!v) return false;
    var r = v.getBoundingClientRect();
    return r.width * r.height > window.innerWidth * window.innerHeight * 0.5;
  }

  window.hfTvMedia = function (a) {
    // Homeflix'in kendi oynatıcı komutları dönüştürülen (mkv/avi) videolarda da doğru sarar.
    if (typeof mediaCommand === 'function') {
      if (typeof P !== 'undefined' && P.open) mediaCommand(a);
      return;
    }
    var v = mainVideo();
    if (!v) return;
    if (a === 'toggle') { v.paused ? v.play() : v.pause(); }
    else if (a === 'play') { v.play(); }
    else if (a === 'pause') { v.pause(); }
    else if (a === 'back') { v.currentTime = Math.max(0, v.currentTime - 10); }
    else if (a === 'fwd') { v.currentTime = Math.min(v.duration || 1e9, v.currentTime + 10); }
  };

  document.addEventListener('keydown', function (e) {
    var k = e.keyCode;
    var isArrow = k >= 37 && k <= 40;
    var isEnter = k === 13 || k === 23;
    if (!isArrow && !isEnter) return;

    var a = document.activeElement;

    // Oynatıcı açıkken yön tuşları uygulamanın kendi kısayollarına kalır.
    if (playerOpen()) {
      if (isEnter && !e.repeat && (!a || a === document.body || a.tagName === 'VIDEO')) {
        e.preventDefault();
        window.hfTvMedia('toggle');
      }
      return;
    }

    var typing = a && (a.tagName === 'TEXTAREA' ||
      (a.tagName === 'INPUT' && !/^(button|submit|checkbox|radio|range|file)$/i.test(a.type)));
    var onRange = a && a.tagName === 'INPUT' && a.type === 'range';
    var onSelect = a && a.tagName === 'SELECT';

    if (isArrow) {
      if ((typing || onRange) && (k === 37 || k === 39)) return;
      if (onSelect) return;
      e.preventDefault();
      e.stopPropagation();
      move(k === 37 ? 'left' : k === 38 ? 'up' : k === 39 ? 'right' : 'down');
      return;
    }

    // Enter / DPAD merkez
    if (typing || onSelect) return;
    if (e.repeat) { e.preventDefault(); return; }
    if (curValid()) {
      e.preventDefault();
      e.stopPropagation();
      if (FORM.test(cur.tagName)) {
        try { cur.focus(); } catch (x) {}
      }
      cur.click();
    }
  }, true);
})();

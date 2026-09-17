/* WUREC site behaviour: sticky header state, mobile menu, nav folders, reveal-on-scroll, filmstrip. */
(function () {
  var header = document.querySelector('.site-header');
  var nav = document.querySelector('.site-nav');
  var toggle = document.querySelector('.nav-toggle');
  var reduceMotion = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

  function onScroll() {
    header.classList.toggle('scrolled', window.scrollY > 40);
  }
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });

  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(open));
      toggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
      header.classList.toggle('nav-open', open);
      document.body.classList.toggle('no-scroll', open);
    });
  }

  Array.prototype.forEach.call(document.querySelectorAll('.folder-toggle'), function (btn) {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      var li = btn.parentElement;
      var open = li.classList.toggle('open');
      btn.setAttribute('aria-expanded', String(open));
    });
  });
  document.addEventListener('click', function (e) {
    if (e.target.closest && e.target.closest('.folder')) { return; }
    Array.prototype.forEach.call(document.querySelectorAll('.folder.open'), function (li) {
      li.classList.remove('open');
      var b = li.querySelector('.folder-toggle');
      if (b) { b.setAttribute('aria-expanded', 'false'); }
    });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      Array.prototype.forEach.call(document.querySelectorAll('.folder.open'), function (li) { li.classList.remove('open'); });
      if (nav && nav.classList.contains('open')) { toggle.click(); }
    }
  });

  /* Reveal on scroll: elements marked data-reveal fade up once they enter the viewport.
     Siblings are staggered by 120ms. Without IntersectionObserver, or with reduced motion,
     everything is shown at once. */
  var revealed = document.querySelectorAll('[data-reveal]');
  function showAll() {
    Array.prototype.forEach.call(revealed, function (el) { el.classList.add('is-visible'); });
  }
  if (!('IntersectionObserver' in window) || reduceMotion) {
    showAll();
  } else {
    Array.prototype.forEach.call(revealed, function (el) {
      var siblings = el.parentElement ? el.parentElement.querySelectorAll(':scope > [data-reveal]') : [];
      var index = Array.prototype.indexOf.call(siblings, el);
      if (index > 0) { el.style.transitionDelay = Math.min(index, 5) * 120 + 'ms'; }
    });
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) { return; }
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -6% 0px' });
    Array.prototype.forEach.call(revealed, function (el) { observer.observe(el); });
    /* Anything already in view at load, or missed by the observer, shows after a moment. */
    window.setTimeout(showAll, 2500);
  }

  /* Filmstrip: the slow drift stops once the visitor scrolls the strip themselves. */
  Array.prototype.forEach.call(document.querySelectorAll('.strip'), function (strip) {
    var track = strip.querySelector('.strip__track');
    if (!track) { return; }
    track.addEventListener('scroll', function () { strip.classList.add('is-touched'); }, { passive: true, once: true });
  });

  /* Committee switcher: tabs on the left choose the panel on the right (an accordion on phones).
     Arrow keys move between tabs. */
  Array.prototype.forEach.call(document.querySelectorAll('.switcher'), function (box) {
    var tabs = box.querySelectorAll('.switcher__tab');
    function select(tab, focus) {
      Array.prototype.forEach.call(tabs, function (t) {
        var on = t === tab;
        t.classList.toggle('is-on', on);
        t.setAttribute('aria-selected', String(on));
        t.tabIndex = on ? 0 : -1;
        var panel = document.getElementById(t.getAttribute('aria-controls'));
        if (panel) { panel.classList.toggle('is-on', on); }
      });
      if (focus) { tab.focus(); }
    }
    Array.prototype.forEach.call(tabs, function (tab, n) {
      tab.addEventListener('click', function () { select(tab, false); });
      tab.addEventListener('keydown', function (e) {
        var step = (e.key === 'ArrowDown' || e.key === 'ArrowRight') ? 1 : (e.key === 'ArrowUp' || e.key === 'ArrowLeft') ? -1 : 0;
        if (!step) { return; }
        e.preventDefault();
        select(tabs[(n + step + tabs.length) % tabs.length], true);
      });
    });
  });

  /* Executive board: clicking a member's photo copies their email address instead of
     opening a mail client. Without JavaScript, or if the clipboard is unavailable, the
     mailto: link behaves as a normal email link. */
  var announcer = null;
  function announce(text) {
    if (!announcer) {
      announcer = document.createElement('div');
      announcer.className = 'visually-hidden';
      announcer.setAttribute('aria-live', 'polite');
      document.body.appendChild(announcer);
    }
    announcer.textContent = '';
    setTimeout(function () { announcer.textContent = text; }, 50);
  }
  function copyText(text, done) {
    function legacy() {
      var box = document.createElement('textarea');
      box.value = text;
      box.setAttribute('readonly', '');
      box.style.position = 'fixed';
      box.style.top = '-1000px';
      document.body.appendChild(box);
      box.select();
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (err) { ok = false; }
      document.body.removeChild(box);
      done(ok);
    }
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(function () { done(true); }, legacy);
    } else {
      legacy();
    }
  }
  Array.prototype.forEach.call(document.querySelectorAll('.member__photo-link[href^="mailto:"]'), function (link) {
    var email = link.getAttribute('href').replace(/^mailto:/i, '').split('?')[0];
    var heading = link.parentElement && link.parentElement.querySelector('h3');
    var name = heading ? heading.textContent.trim() : '';
    var timer = null;
    link.setAttribute('aria-label', name ? 'Copy ' + name + '\u2019s email address' : 'Copy email address');
    link.addEventListener('click', function (e) {
      e.preventDefault();
      copyText(email, function (ok) {
        if (!ok) { window.location.href = link.href; return; }
        link.classList.add('is-copied');
        announce('Copied ' + email + ' to the clipboard');
        clearTimeout(timer);
        timer = setTimeout(function () { link.classList.remove('is-copied'); }, 1800);
      });
    });
  });

  Array.prototype.forEach.call(document.querySelectorAll('[data-year]'), function (el) {
    el.textContent = String(new Date().getFullYear());
  });
})();

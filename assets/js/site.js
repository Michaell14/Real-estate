/* WUREC site behaviour: sticky header state, mobile menu, nav folders, calendar embed. */
(function () {
  var header = document.querySelector('.site-header');
  var nav = document.querySelector('.site-nav');
  var toggle = document.querySelector('.nav-toggle');

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

  /* Google Calendar embed: set data-calendar-src on the .calendar-embed element. */
  Array.prototype.forEach.call(document.querySelectorAll('[data-calendar-src]'), function (el) {
    var src = el.getAttribute('data-calendar-src');
    if (!src) { return; }
    var frame = document.createElement('iframe');
    frame.src = src;
    frame.title = 'WUREC events calendar';
    frame.setAttribute('loading', 'lazy');
    el.appendChild(frame);
    el.classList.add('has-embed');
  });

  /* Photo carousel: arrows, thumbnail tabs, keyboard, swipe and autoplay.
     Autoplay pauses while hovered or keyboard-focused, when the tab is hidden, and via
     the pause button; it starts paused for users who prefer reduced motion. */
  Array.prototype.forEach.call(document.querySelectorAll('.carousel'), function (root) {
    var slides = root.querySelectorAll('.carousel__slide');
    var thumbs = root.querySelectorAll('.carousel__thumb');
    var strip = root.querySelector('.carousel__thumbs');
    var live = root.querySelector('.carousel__slides');
    var toggle = root.querySelector('.carousel__toggle');
    var interval = parseInt(root.getAttribute('data-interval'), 10) || 5000;
    var canHover = window.matchMedia && window.matchMedia('(hover: hover)').matches;
    var paused = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    var index = 0, timer = null, hovered = false, focused = false, touchX = null, touchY = null;
    if (slides.length < 2) { return; }

    function show(i) {
      index = (i + slides.length) % slides.length;
      Array.prototype.forEach.call(slides, function (slide, n) {
        slide.classList.toggle('is-active', n === index);
        slide.setAttribute('aria-hidden', String(n !== index));
      });
      Array.prototype.forEach.call(thumbs, function (thumb, n) {
        var on = n === index;
        thumb.classList.toggle('is-active', on);
        thumb.setAttribute('aria-selected', String(on));
        thumb.tabIndex = on ? 0 : -1;
      });
      var active = thumbs[index];
      if (strip && active) {
        var left = active.offsetLeft - (strip.clientWidth - active.offsetWidth) / 2;
        if (strip.scrollTo) { strip.scrollTo({ left: left, behavior: 'smooth' }); } else { strip.scrollLeft = left; }
      }
    }
    function rotating() { return !paused && !hovered && !focused && !document.hidden; }
    function schedule() {
      clearTimeout(timer);
      if (live) { live.setAttribute('aria-live', rotating() ? 'off' : 'polite'); }
      if (rotating()) { timer = setTimeout(function () { show(index + 1); schedule(); }, interval); }
    }
    function setPaused(state) {
      paused = state;
      root.classList.toggle('is-paused', paused);
      if (toggle) { toggle.setAttribute('aria-label', paused ? 'Play slideshow' : 'Pause slideshow'); }
      schedule();
    }
    function step(delta) { show(index + delta); schedule(); }
    /* A mouse click leaves focus on the button it hit; only keyboard focus should hold the slideshow. */
    function keyboardFocus(el) {
      try { return el.matches(':focus-visible'); } catch (err) { return true; }
    }

    root.querySelector('.carousel__arrow--prev').addEventListener('click', function () { step(-1); });
    root.querySelector('.carousel__arrow--next').addEventListener('click', function () { step(1); });
    Array.prototype.forEach.call(thumbs, function (thumb, n) {
      thumb.addEventListener('click', function () { show(n); schedule(); });
    });
    if (toggle) { toggle.addEventListener('click', function () { setPaused(!paused); }); }

    root.addEventListener('keydown', function (e) {
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') { return; }
      e.preventDefault();
      step(e.key === 'ArrowLeft' ? -1 : 1);
      if (e.target.classList && e.target.classList.contains('carousel__thumb')) { thumbs[index].focus(); }
    });
    if (canHover) {
      root.addEventListener('mouseenter', function () { hovered = true; schedule(); });
      root.addEventListener('mouseleave', function () { hovered = false; schedule(); });
    }
    root.addEventListener('focusin', function (e) { focused = keyboardFocus(e.target); schedule(); });
    root.addEventListener('focusout', function (e) {
      if (!root.contains(e.relatedTarget)) { focused = false; schedule(); }
    });
    root.addEventListener('touchstart', function (e) {
      touchX = e.changedTouches[0].clientX; touchY = e.changedTouches[0].clientY;
    }, { passive: true });
    root.addEventListener('touchend', function (e) {
      if (touchX === null) { return; }
      var dx = e.changedTouches[0].clientX - touchX, dy = e.changedTouches[0].clientY - touchY;
      touchX = touchY = null;
      if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy)) { step(dx < 0 ? 1 : -1); }
    }, { passive: true });
    document.addEventListener('visibilitychange', schedule);

    setPaused(paused);
  });

  Array.prototype.forEach.call(document.querySelectorAll('[data-year]'), function (el) {
    el.textContent = String(new Date().getFullYear());
  });
})();

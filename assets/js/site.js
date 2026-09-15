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

  Array.prototype.forEach.call(document.querySelectorAll('[data-year]'), function (el) {
    el.textContent = String(new Date().getFullYear());
  });
})();

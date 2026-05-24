/* ============================================================
   CycloStats — main.js v2.0
   ============================================================ */
'use strict';

// ─── Chart.js global defaults ─────────────────────────────────
if (typeof Chart !== 'undefined') {
  Chart.defaults.color = '#94a3b8';
  Chart.defaults.borderColor = 'rgba(255,255,255,.05)';
  Chart.defaults.plugins.legend.labels.color = '#e2e8f0';
  Chart.defaults.plugins.tooltip.backgroundColor = '#101929';
  Chart.defaults.plugins.tooltip.borderColor = 'rgba(30,54,90,.75)';
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.titleColor = '#f59e0b';
  Chart.defaults.plugins.tooltip.bodyColor = '#e2e8f0';
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
}

// ─── DOMContentLoaded init ─────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  initTooltips();
  initAutoDismissAlerts();
  initActiveNavLink();
  initStickyThead();
  initYearSelectors();
  initBackToTop();
  fixCompareForm();
  initSortableTables();
  initSearchKeyboard();
  initCounterAnimation();
  initSearchAutocompleteKeyboard();
});

// ─── Tooltips ─────────────────────────────────────────────────
function initTooltips() {
  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
    new bootstrap.Tooltip(el, { trigger: 'hover' });
  });
}

// ─── Auto-dismiss alerts ───────────────────────────────────────
function initAutoDismissAlerts() {
  document.querySelectorAll('.alert.alert-success, .alert.alert-info').forEach(function (el) {
    setTimeout(function () {
      const a = bootstrap.Alert.getOrCreateInstance(el);
      if (a) a.close();
    }, 5000);
  });
}

// ─── Active nav link ───────────────────────────────────────────
function initActiveNavLink() {
  const path = window.location.pathname;
  document.querySelectorAll('.navbar-nav .nav-link').forEach(function (link) {
    const href = link.getAttribute('href');
    if (href && href !== '/' && path.startsWith(href)) {
      link.classList.add('active', 'text-warning');
    }
  });
}

// ─── Sticky table head ─────────────────────────────────────────
function initStickyThead() {
  document.querySelectorAll('.table-sticky-head thead th').forEach(function (th) {
    th.style.background = 'var(--cs-bg-2)';
  });
}

// ─── Year select auto-submit ───────────────────────────────────
function initYearSelectors() {
  document.querySelectorAll('select[name="year"]').forEach(function (sel) {
    sel.addEventListener('change', function () {
      const form = this.closest('form');
      if (form) form.submit();
    });
  });
}

// ─── Back to top ───────────────────────────────────────────────
function initBackToTop() {
  const btn = document.createElement('button');
  btn.id = 'backToTop';
  btn.innerHTML = '<i class="bi bi-chevron-up"></i>';
  btn.className = 'btn btn-warning btn-sm rounded-circle shadow';
  btn.style.cssText =
    'position:fixed;bottom:24px;right:24px;width:40px;height:40px;' +
    'display:none;z-index:999;padding:0;align-items:center;justify-content:center;';
  document.body.appendChild(btn);

  window.addEventListener('scroll', function () {
    const show = window.scrollY > 400;
    btn.style.display = show ? 'flex' : 'none';
  });

  btn.addEventListener('click', function () {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
}

// ─── Rider compare form ────────────────────────────────────────
function fixCompareForm() {
  const form = document.querySelector('form[action*="compare"], form[method="get"]');
  if (!form) return;
  const inputs = form.querySelectorAll('input[list="ridersList"]');
  const options = document.querySelectorAll('#ridersList option');
  const nameToSlug = {};
  options.forEach(function (opt) {
    if (opt.dataset.slug) nameToSlug[opt.value.toLowerCase()] = opt.dataset.slug;
  });
  form.addEventListener('submit', function () {
    inputs.forEach(function (inp) {
      const slug = nameToSlug[inp.value.toLowerCase()];
      if (slug) inp.value = slug;
    });
  });
}

// ─── Sortable tables ───────────────────────────────────────────
function initSortableTables() {
  document.querySelectorAll('table.sortable thead th').forEach(function (th, idx) {
    th.style.cursor = 'pointer';
    th.title = 'Cliquer pour trier';
    th.addEventListener('click', function () {
      sortTable(th.closest('table'), idx);
    });
  });
}

function sortTable(table, colIdx) {
  const tbody = table.querySelector('tbody');
  if (!tbody) return;
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const asc = table.dataset.sortCol == colIdx && table.dataset.sortDir !== 'asc';
  table.dataset.sortCol = colIdx;
  table.dataset.sortDir = asc ? 'asc' : 'desc';

  rows.sort(function (a, b) {
    const valA = (a.cells[colIdx] || {}).innerText || '';
    const valB = (b.cells[colIdx] || {}).innerText || '';
    const numA = parseFloat(valA.replace(/[^0-9.-]/g, ''));
    const numB = parseFloat(valB.replace(/[^0-9.-]/g, ''));
    if (!isNaN(numA) && !isNaN(numB)) return asc ? numA - numB : numB - numA;
    return asc ? valA.localeCompare(valB) : valB.localeCompare(valA);
  });

  rows.forEach(function (row) { tbody.appendChild(row); });
}

// ─── Keyboard shortcut: Ctrl/Cmd+K → focus search ─────────────
function initSearchKeyboard() {
  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      const inp = document.getElementById('navSearch');
      if (inp) { inp.focus(); inp.select(); }
    }
    // Escape closes autocomplete
    if (e.key === 'Escape') {
      const box = document.getElementById('searchSuggestions');
      if (box) box.style.display = 'none';
    }
  });
}

// ─── Autocomplete keyboard navigation ─────────────────────────
function initSearchAutocompleteKeyboard() {
  const input = document.getElementById('navSearch');
  const box   = document.getElementById('searchSuggestions');
  if (!input || !box) return;

  input.addEventListener('keydown', function (e) {
    const items = Array.from(box.querySelectorAll('.dropdown-item'));
    const focused = box.querySelector('.keyboard-focus');
    const idx = focused ? items.indexOf(focused) : -1;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (focused) focused.classList.remove('keyboard-focus');
      const next = items[Math.min(idx + 1, items.length - 1)];
      if (next) next.classList.add('keyboard-focus');
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (focused) focused.classList.remove('keyboard-focus');
      const prev = items[Math.max(idx - 1, 0)];
      if (prev) prev.classList.add('keyboard-focus');
    } else if (e.key === 'Enter') {
      if (focused) { e.preventDefault(); window.location = focused.href; }
    }
  });
}

// ─── Counter animation (homepage stats) ───────────────────────
function initCounterAnimation() {
  const counters = document.querySelectorAll('[data-counter]');
  if (!counters.length) return;

  const obs = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      animateCounter(entry.target);
      obs.unobserve(entry.target);
    });
  }, { threshold: 0.5 });

  counters.forEach(function (el) { obs.observe(el); });
}

function animateCounter(el) {
  const target = parseInt(el.dataset.counter, 10);
  if (isNaN(target)) return;
  const duration = 1200;
  const start = performance.now();

  function step(now) {
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(eased * target).toLocaleString('fr-FR');
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// ─── Copy to clipboard ─────────────────────────────────────────
function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(function () {
    showToast('Copié !', 'success');
  });
}

// ─── Toast notifications ───────────────────────────────────────
function showToast(message, type) {
  type = type || 'info';
  const container = document.getElementById('toastContainer') || createToastContainer();
  const id = 'toast-' + Date.now();
  const colors = { success: '#10b981', warning: '#f59e0b', danger: '#ef4444', info: '#3b82f6' };
  const html = `
    <div id="${id}" class="toast align-items-center border-0 show" role="alert"
         style="background:#101929;border-left:3px solid ${colors[type] || colors.info} !important;border-radius:8px;min-width:220px;">
      <div class="d-flex">
        <div class="toast-body text-white small fw-medium">${message}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>
    </div>`;
  container.insertAdjacentHTML('beforeend', html);
  setTimeout(function () {
    const el = document.getElementById(id);
    if (el) el.remove();
  }, 3500);
}

function createToastContainer() {
  const div = document.createElement('div');
  div.id = 'toastContainer';
  div.style.cssText =
    'position:fixed;top:70px;right:16px;z-index:9999;display:flex;flex-direction:column;gap:8px;';
  document.body.appendChild(div);
  return div;
}

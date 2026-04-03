/* ============================================================
   CycloStats — main.js
   ============================================================ */

'use strict';

// ─── Chart.js global defaults ─────────────────────────────────
if (typeof Chart !== 'undefined') {
  Chart.defaults.color = '#8b949e';
  Chart.defaults.borderColor = 'rgba(255,255,255,.06)';
  Chart.defaults.plugins.legend.labels.color = '#e6edf3';
  Chart.defaults.plugins.tooltip.backgroundColor = '#161b22';
  Chart.defaults.plugins.tooltip.borderColor = '#30363d';
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.titleColor = '#f39c12';
  Chart.defaults.plugins.tooltip.bodyColor = '#e6edf3';
}

// ─── Bootstrap tooltips & popovers ────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  // Tooltips
  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
    new bootstrap.Tooltip(el);
  });

  // Auto-dismiss alerts after 5s
  document.querySelectorAll('.alert.alert-success, .alert.alert-info').forEach(function (el) {
    setTimeout(function () {
      const alert = bootstrap.Alert.getOrCreateInstance(el);
      if (alert) alert.close();
    }, 5000);
  });

  // Active nav link highlight
  const path = window.location.pathname;
  document.querySelectorAll('.navbar-nav .nav-link').forEach(function (link) {
    const href = link.getAttribute('href');
    if (href && href !== '/' && path.startsWith(href)) {
      link.classList.add('active', 'text-warning');
    }
  });

  // Sticky table head enhancement
  document.querySelectorAll('.table-responsive table').forEach(function (table) {
    table.querySelectorAll('thead th').forEach(function (th) {
      th.style.position = 'sticky';
      th.style.top = '0';
      th.style.zIndex = '1';
      th.style.backgroundColor = '#161b22';
    });
  });

  // Year selectors — auto-submit on change
  document.querySelectorAll('select[name="year"]').forEach(function (sel) {
    sel.addEventListener('change', function () {
      this.closest('form') && this.closest('form').submit();
    });
  });

  // Smooth back-to-top
  addBackToTop();

  // Fix rider compare datalist (map name → slug in URL)
  fixCompareForm();
});

// ─── Back to top button ────────────────────────────────────────
function addBackToTop() {
  const btn = document.createElement('button');
  btn.id = 'backToTop';
  btn.innerHTML = '<i class="bi bi-chevron-up"></i>';
  btn.className = 'btn btn-warning btn-sm rounded-circle shadow';
  btn.style.cssText = 'position:fixed;bottom:24px;right:24px;width:40px;height:40px;display:none;z-index:999;padding:0;';
  document.body.appendChild(btn);

  window.addEventListener('scroll', function () {
    btn.style.display = window.scrollY > 400 ? 'flex' : 'none';
    btn.style.alignItems = 'center';
    btn.style.justifyContent = 'center';
  });

  btn.addEventListener('click', function () {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
}

// ─── Rider compare form: map name → slug ──────────────────────
function fixCompareForm() {
  const form = document.querySelector('form[action*="compare"], form[method="get"]');
  if (!form) return;
  const inputs = form.querySelectorAll('input[list="ridersList"]');
  const options = document.querySelectorAll('#ridersList option');
  const nameToSlug = {};
  options.forEach(function (opt) {
    if (opt.dataset.slug) {
      nameToSlug[opt.value.toLowerCase()] = opt.dataset.slug;
    }
  });
  // Map on submit
  form.addEventListener('submit', function (e) {
    inputs.forEach(function (inp) {
      const slug = nameToSlug[inp.value.toLowerCase()];
      if (slug) inp.value = slug;
    });
  });
}

// ─── Table sorting (client-side for small tables) ─────────────
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('table.sortable thead th').forEach(function (th, idx) {
    th.style.cursor = 'pointer';
    th.addEventListener('click', function () {
      sortTable(th.closest('table'), idx);
    });
  });
});

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

// ─── Copy to clipboard helper ──────────────────────────────────
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
  const colors = { success: '#2ecc71', warning: '#f39c12', danger: '#e74c3c', info: '#3498db' };
  const html = `
    <div id="${id}" class="toast align-items-center border-0 show" role="alert" style="background:#161b22;border-left:3px solid ${colors[type] || colors.info} !important;">
      <div class="d-flex">
        <div class="toast-body text-white small">${message}</div>
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
  div.style.cssText = 'position:fixed;top:70px;right:16px;z-index:9999;display:flex;flex-direction:column;gap:8px;';
  document.body.appendChild(div);
  return div;
}

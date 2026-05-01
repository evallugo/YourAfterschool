/* Your After School Inventory System — app.js */

document.addEventListener('DOMContentLoaded', function () {

  // ── Auto-dismiss success alerts ──
  setTimeout(function () {
    document.querySelectorAll('.alert-success, .alert-info').forEach(function (el) {
      var a = bootstrap.Alert.getOrCreateInstance(el);
      if (a) a.close();
    });
  }, 4500);

  // ── Packing checklist toggle (AJAX) ──
  document.querySelectorAll('.pack-check').forEach(function (cb) {
    cb.addEventListener('change', function () {
      var itemId   = parseInt(this.dataset.itemId);
      var lessonId = parseInt(this.dataset.lessonId);
      var row      = this.closest('tr');
      var self     = this;

      fetch('/packing/lesson/' + lessonId + '/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: itemId })
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          // Row styling
          if (data.is_packed) {
            row.classList.add('is-packed');
          } else {
            row.classList.remove('is-packed');
          }

          // Progress bar
          var pct = data.total > 0 ? Math.round((data.packed / data.total) * 100) : 0;
          var bar = document.querySelector('.progress-bar');
          if (bar) {
            bar.style.width = pct + '%';
            bar.setAttribute('aria-valuenow', pct);
            bar.classList.toggle('full',    pct === 100);
            bar.classList.toggle('partial', pct > 0 && pct < 100);
          }

          // Packed counter
          var counter = document.getElementById('packed-count');
          if (counter) counter.textContent = data.packed + '/' + data.total;

          // Pct label
          var pctLabel = document.getElementById('pct-label');
          if (pctLabel) pctLabel.textContent = pct + '%';

          // Status badge
          var badge = document.querySelector('.lesson-status-badge');
          if (badge) {
            var labels  = { unpacked: 'Not Started', in_progress: 'In Progress', packed: 'Done ✓' };
            var classes = { unpacked: 's-unpacked',  in_progress: 's-in-progress', packed: 's-packed' };
            badge.className   = 'status-badge lesson-status-badge ' + (classes[data.status] || '');
            badge.textContent = labels[data.status] || data.status;
          }
        })
        .catch(function () {
          self.checked = !self.checked; // revert checkbox on network error
        });
    });
  });

  // ── Inventory: quick quantity adjust ──
  document.querySelectorAll('.qty-adjust-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var itemId = this.dataset.itemId;
      var delta  = parseInt(this.dataset.delta);
      fetch('/inventory/' + itemId + '/adjust', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'delta=' + delta
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var qtyEl = document.querySelector('[data-qty-item="' + itemId + '"]');
          if (qtyEl) {
            qtyEl.textContent = data.quantity;
            qtyEl.parentElement.className = 'qty-badge ' +
              (data.quantity === 0 ? 'empty' : data.quantity <= 10 ? 'low' : 'good');
          }
        })
        .catch(function () {
          console.error('Quantity adjust failed for item ' + itemId);
        });
    });
  });

  // ── Confirm dangerous actions ──
  document.querySelectorAll('[data-confirm]').forEach(function (el) {
    el.addEventListener('click', function (e) {
      if (!confirm(this.dataset.confirm || 'Are you sure?')) {
        e.preventDefault();
      }
    });
  });

  // ── Print button shortcut ──
  document.querySelectorAll('.btn-print').forEach(function (btn) {
    btn.addEventListener('click', function () { window.print(); });
  });

  // ── Category filter sidebar (inventory) ──
  document.querySelectorAll('.cat-filter-link').forEach(function (link) {
    link.addEventListener('click', function (e) {
      e.preventDefault();
      var url = new URL(window.location.href);
      var cat = this.dataset.catId;
      if (cat) {
        url.searchParams.set('cat', cat);
      } else {
        url.searchParams.delete('cat');
      }
      url.searchParams.set('page', '1');
      window.location.href = url.toString();
    });
  });

  // ── Arriving: link item dropdown auto-fills description ──
  var itemSelect = document.getElementById('arriving-item-select');
  if (itemSelect) {
    itemSelect.addEventListener('change', function () {
      var opt  = this.options[this.selectedIndex];
      var desc = document.getElementById('arriving-item-desc');
      var unit = document.getElementById('arriving-unit');
      if (opt && opt.value) {
        if (desc && !desc.value) desc.value = opt.text.split(' (')[0];
        if (unit && opt.dataset.unit) unit.value = opt.dataset.unit;
      }
    });
  }

  // ── Subcategory cascade (inventory form) ──
  var catCheckboxes = document.querySelectorAll('.cat-checkbox');
  var subcatSelect  = document.getElementById('subcategory_id');
  if (subcatSelect) {
    function filterSubcats() {
      var checkedCats = Array.from(catCheckboxes)
        .filter(function (cb) { return cb.checked; })
        .map(function (cb) { return cb.value; });
      Array.from(subcatSelect.options).forEach(function (opt) {
        if (!opt.value) return;
        opt.hidden = checkedCats.length > 0 && !checkedCats.includes(opt.dataset.catId);
      });
    }
    catCheckboxes.forEach(function (cb) { cb.addEventListener('change', filterSubcats); });
    filterSubcats();
  }

});

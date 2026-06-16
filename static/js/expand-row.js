// Shared expandable-table-row interaction.
// Any <tr class="expandable-row"> followed by a <tr class="detail-row"> becomes a
// clickable / keyboard-focusable row that toggles its detail drawer open and closed.
// Used by both Manage Batches and Raw Materials — one copy, no per-template duplication.
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.expandable-row').forEach(function (row) {
        function toggle() {
            var detail = row.nextElementSibling;
            if (!detail || !detail.classList.contains('detail-row')) return;
            var open = detail.classList.toggle('open');
            row.setAttribute('aria-expanded', open);
        }
        row.addEventListener('click', toggle);
        row.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); }
        });
    });
});

// ADDED: planned-deduction-mode feature.
// Shared renderer for the "Materials" drawer on the batches and manage-batches pages, which both
// read GET /batches/<id>/materials. That endpoint returns {materials, planned, fifo}:
//   planned = true  -> these are lots RESERVED by a deferred Planned batch, not yet deducted.
//   fifo    = true  -> deferred Planned batch with no picks; oldest lots get used at promotion.
// A deferred batch has zero batch_materials rows until it promotes, so without the planned/fifo
// distinction the drawer would say "No materials recorded" for a batch whose lots were chosen.

function renderBatchMaterials(data) {
    var materials = (data && data.materials) || [];

    if (!materials.length) {
        if (data && data.fifo) {
            return '<em>No lots selected — the oldest lots (FIFO) will be used on the planned completion date.</em>';
        }
        return '<em>No materials recorded for this batch.</em>';
    }

    var html = '';
    if (data.planned) {
        html += '<div class="materials-caption">Reserved — not yet deducted. These lots come off stock on the planned completion date.</div>';
    }
    html += '<table class="materials-inner-table"><thead><tr>' +
            '<th>Material</th><th>Lot #</th>' +
            // cost-of-material feature — Cost/Unit column in the materials expansion panel.
            '<th>' + (data.planned ? 'Quantity Reserved' : 'Quantity Used') + '</th><th>Unit</th><th>Cost/Unit</th>' +
            '</tr></thead><tbody>';

    materials.forEach(function (m) {
        var cpu = (m.cost_per_unit != null && m.cost_per_unit > 0) ? '$' + parseFloat(m.cost_per_unit).toFixed(2) : '—';
        // A reserved lot can expire or be used up before the planned date. Flag it here rather than
        // letting the batch silently fail to promote.
        var stale = (m.lot_status && m.lot_status !== 'active')
            ? ' <span class="badge badge-out">unavailable</span>' : '';
        html += '<tr><td>' + m.material_name + '</td><td>' + m.lot_number + stale + '</td><td class="num">' +
                m.quantity_used + '</td><td>' + m.unit + '</td><td class="num">' + cpu + '</td></tr>';
    });

    return html + '</tbody></table>';
}

odoo.define("quoter.range_columns", function (require) {
    "use strict";

    const rpc = require("web.rpc");
    const FormRenderer = require("web.FormRenderer");

    const LOG = "[quoter.range.columns]";

    function log() {
        if (typeof console !== "undefined" && console.log) {
            var a = Array.prototype.slice.call(arguments);
            a.unshift(LOG);
            console.log.apply(console, a);
        }
    }

    function idFromM2o(value) {
        if (value === null || value === undefined || value === false) {
            return null;
        }
        if (Array.isArray(value) && value.length >= 1) {
            return value[0];
        }
        if (typeof value === "object") {
            if (typeof value.res_id === "number") {
                return value.res_id;
            }
            if (typeof value.id === "number") {
                return value.id;
            }
            if (value.data && typeof value.data.id === "number") {
                return value.data.id;
            }
        }
        return null;
    }

    async function fetchAreaRanges(areaId) {
        if (!areaId) {
            return [];
        }
        try {
            const area = await rpc.query({
                model: "quoter.professional.area",
                method: "read",
                args: [[areaId], ["area_range_ids"]],
            });
            const rangeIds = (area && area[0] && area[0].area_range_ids) || [];
            if (!rangeIds.length) {
                return [];
            }
            const ranges = await rpc.query({
                model: "quoter.area.complexity.range",
                method: "read",
                args: [rangeIds, ["name", "sequence"]],
            });
            ranges.sort(function (a, b) {
                const sa = a.sequence || 0;
                const sb = b.sequence || 0;
                if (sa !== sb) return sa - sb;
                return (a.id || 0) - (b.id || 0);
            });
            return ranges.slice(0, 4);
        } catch (e) {
            log("fetchAreaRanges error", e);
            return [];
        }
    }

    function applyHeaders($root, names) {
        const fallback = ["Rango 1", "Rango 2", "Rango 3", "Rango 4"];
        for (let i = 0; i < 4; i++) {
            const label = names[i] || fallback[i];
            const fieldName = "quoter_range_" + (i + 1) + "_hours";
            $root.find('th[data-name="' + fieldName + '"] .o_column_title, th[data-name="' + fieldName + '"]')
                .first()
                .text(label);
        }
    }

    async function updateAllSlotRangeHeaders(renderer) {
        if (!renderer || renderer.state.model !== "sale.order") {
            return;
        }
        const data = renderer.state.data || {};
        if (!data.is_quotation) {
            return;
        }
        const $form = $(renderer.el);
        for (let slot = 1; slot <= 5; slot++) {
            const areaId = idFromM2o(data["quoter_slot_" + slot + "_area_id"]);
            const ranges = await fetchAreaRanges(areaId);
            const names = ranges.map((r) => r.name);
            // Buscar el contenido del tab del slot (tiene marker).
            const $marker = $form.find('.o_quoter_slot_tab_marker[data-quoter-slot="' + slot + '"]').first();
            if (!$marker.length) continue;
            const $pane = $marker.closest(".tab-pane");
            if (!$pane.length) continue;
            applyHeaders($pane, names);
        }
    }

    FormRenderer.include({
        _renderView: function () {
            const res = this._super.apply(this, arguments);
            const self = this;
            function run() {
                updateAllSlotRangeHeaders(self);
            }
            if (res && typeof res.then === "function") {
                return res.then(function () {
                    run();
                });
            }
            run();
            return res;
        },
    });
});


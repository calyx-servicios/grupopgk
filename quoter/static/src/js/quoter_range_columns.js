odoo.define("quoter.range_columns", function (require) {
    "use strict";

    const rpc = require("web.rpc");
    const FormRenderer = require("web.FormRenderer");
    const ListRenderer = require("web.ListRenderer");

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

    /**
     * Renombra cabeceras de columnas slot_N_hours o quoter_range_N_hours.
     * @param {jQuery} $root contenedor (form tab o lista)
     * @param {string[]} names nombres de rango del área (hasta 4)
     * @param {string} fieldPrefix "slot_" (lista quoter.product.level.range) o "quoter_range_" (tabs pedido)
     */
    function applySlotHourColumnTitles($root, names, fieldPrefix) {
        const fallback = ["Rango 1", "Rango 2", "Rango 3", "Rango 4"];
        const prefix = fieldPrefix || "quoter_range_";
        for (let i = 0; i < 4; i++) {
            const label = names[i] || fallback[i];
            const fieldName = prefix + (i + 1) + "_hours";
            const $th = $root.find('th[data-name="' + fieldName + '"]');
            const $title = $th.find(".o_column_title").first();
            if ($title.length) {
                $title.text(label);
            } else if ($th.length) {
                $th.first().text(label);
            }
        }
    }

    async function updateAllSlotRangeHeaders(renderer) {
        if (!renderer || !renderer.state || renderer.state.model !== "sale.order") {
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
            const $marker = $form.find('.o_quoter_slot_tab_marker[data-quoter-slot="' + slot + '"]').first();
            if (!$marker.length) continue;
            const $pane = $marker.closest(".tab-pane");
            if (!$pane.length) continue;
            applySlotHourColumnTitles($pane, names, "quoter_range_");
        }
    }

    function getFirstAreaIdFromLevelRangeList(renderer) {
        if (!renderer || !renderer.state || renderer.state.model !== "quoter.product.level.range") {
            return null;
        }
        const records = renderer.state.data || [];
        for (let i = 0; i < records.length; i++) {
            const rec = records[i];
            if (!rec || !rec.data) {
                continue;
            }
            const aid = idFromM2o(rec.data.area_id);
            if (aid) {
                return aid;
            }
        }
        return null;
    }

    async function updateLevelRangeListSlotHeaders(renderer) {
        if (!renderer || !renderer.el || renderer.isGrouped) {
            return;
        }
        if (!renderer.state || renderer.state.model !== "quoter.product.level.range") {
            return;
        }
        const areaId = getFirstAreaIdFromLevelRangeList(renderer);
        if (!areaId) {
            return;
        }
        const ranges = await fetchAreaRanges(areaId);
        const names = ranges.map(function (r) {
            return r.name;
        });
        applySlotHourColumnTitles($(renderer.el), names, "slot_");
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

    ListRenderer.include({
        _renderView: function () {
            const res = this._super.apply(this, arguments);
            const self = this;
            function run() {
                updateLevelRangeListSlotHeaders(self);
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

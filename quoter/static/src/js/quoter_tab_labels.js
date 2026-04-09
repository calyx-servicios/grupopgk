odoo.define("quoter.tab_labels", function (require) {
    "use strict";

    const FormRenderer = require("web.FormRenderer");
    const FormController = require("web.FormController");

    function labelFromM2o(value) {
        if (value === null || value === undefined || value === false) {
            return null;
        }
        if (Array.isArray(value) && value.length >= 2) {
            return value[1];
        }
        if (typeof value === "object") {
            if (value.display_name) {
                return value.display_name;
            }
            if (value.data && value.data.display_name) {
                return value.data.display_name;
            }
        }
        return null;
    }

    function updateLabels(renderer) {
        if (!renderer || renderer.state.model !== "sale.order") {
            return;
        }
        const data = renderer.state.data || {};
        if (!data.is_quotation) {
            return;
        }
        const $form = $(renderer.el);
        $form.find(".o_quoter_slot_tab_marker").each(function () {
            const slot = parseInt($(this).attr("data-quoter-slot"), 10);
            if (!slot || slot < 1 || slot > 5) return;
            const areaVal = data["quoter_slot_" + slot + "_area_id"];
            let title = labelFromM2o(areaVal);
            if (!title) title = "Área " + slot;

            const $pane = $(this).closest(".tab-pane");
            const paneId = $pane.attr("id");
            if (!paneId) return;
            const href = "#" + paneId;
            const $link = $form.find('a.nav-link[href="' + href + '"]').first();
            if ($link.length) {
                $link.text(title);
            }
        });
    }

    FormRenderer.include({
        _renderView: function () {
            const res = this._super.apply(this, arguments);
            const self = this;
            const run = () => updateLabels(self);
            if (res && typeof res.then === "function") {
                return res.then(function () {
                    run();
                });
            }
            run();
            return res;
        },
    });

    FormController.include({
        _onFieldChanged: function (ev) {
            this._super.apply(this, arguments);
            if (this.modelName !== "sale.order") {
                return;
            }
            const changed = (ev.data && ev.data.changes) || {};
            // Cuando cambian áreas / slots, renombrar pestañas.
            const keys = Object.keys(changed);
            const relevant = keys.some(function (k) {
                return (
                    k === "quoter_area_ids" ||
                    k === "is_quotation" ||
                    (k.startsWith("quoter_slot_") && k.endsWith("_area_id"))
                );
            });
            if (relevant) {
                setTimeout(
                    function () {
                        updateLabels(this.renderer);
                    }.bind(this),
                    0
                );
            }
        },
    });
});


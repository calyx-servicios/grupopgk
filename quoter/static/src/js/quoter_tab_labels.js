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
        if (!renderer || !renderer.state || renderer.state.model !== "sale.order") {
            return;
        }
        const data = renderer.state.data || {};
        if (!data.is_quotation) {
            return;
        }
        const $form = $(renderer.el);
        $form.find(".o_form_label").each(function () {
            const text = ($(this).text() || "").trim().toLowerCase();
            if (text.indexOf("factura dividida") >= 0) {
                const $label = $(this);
                $label.closest(".o_row, .o_inner_group, .o_group").hide();
            }
        });
        $form.find(".o_quoter_slot_tab_marker").each(function () {
            const slot = parseInt($(this).attr("data-quoter-slot"), 10);
            if (!slot || slot < 1 || slot > 5) return;
            const areaVal = data["quoter_slot_" + slot + "_area_id"];
            let title = labelFromM2o(areaVal);

            const $pane = $(this).closest(".tab-pane");
            const paneId = $pane.attr("id");
            if (!paneId) return;
            const href = "#" + paneId;
            const $link = $form.find('a.nav-link[href="' + href + '"]').first();
            if ($link.length) {
                if (!title) {
                    title = ($link.text() || "").trim();
                }
                if (!title) {
                    return;
                }
                $link.text(title);
            }
            const isTax = title && /\btax\b/i.test(String(title).trim());
            $pane.toggleClass("o_quoter_slot_tax", !!isTax);
            if (!isTax) {
                $pane.find(".o_quoter_tax_resumen_align").removeClass("o_quoter_tax_resumen_align");
                $pane.find(".o_horizontal_separator").each(function () {
                    const st = ($(this).text() || "").trim();
                    if (st === "Resumen por roles o rango") {
                        $(this).text("Resumen por rango");
                    }
                });
                $pane.find(".o_quoter_resumen_rango_title").each(function () {
                    const st = ($(this).text() || "").trim();
                    if (st === "Resumen por roles o rango") {
                        $(this).text("Resumen por rango");
                    }
                });
                $pane.find("label.o_form_label").each(function () {
                    if (($(this).text() || "").trim() === "Nivel de complejidad") {
                        $(this).text("Nivel del área");
                    }
                });
                return;
            }
            $pane.find("label.o_form_label").each(function () {
                const lt = ($(this).text() || "").trim();
                if (lt === "Nivel del área") {
                    $(this).text("Nivel de complejidad");
                }
            });
            $pane.find(".o_horizontal_separator").each(function () {
                const st = ($(this).text() || "").trim();
                if (st === "Resumen por rango") {
                    $(this).text("Resumen por roles o rango");
                }
            });
            $pane.find(".o_quoter_resumen_rango").each(function () {
                $(this).addClass("o_quoter_tax_resumen_align");
            });
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


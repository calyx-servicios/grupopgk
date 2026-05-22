odoo.define("quoter.tab_labels", function (require) {
    "use strict";

    const FormRenderer = require("web.FormRenderer");
    const FormController = require("web.FormController");

    // Modo contingencia: desactivar parches de pestañas para descartar crash en bootstrap.
    // Rehabilitar cambiando a `false`.
    const QUOTER_DISABLE_TAB_LABEL_PATCH = false;
    if (QUOTER_DISABLE_TAB_LABEL_PATCH) {
        return;
    }

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

    function collectAreasFromTags($form) {
        const areas = [];
        const seen = {};
        const $root = $form.find('.o_field_many2manytags[name="quoter_area_ids"]');
        $root.find(".o_tag_badge_text").each(function () {
            const name = ($(this).text() || "").trim();
            if (!name || seen[name]) {
                return;
            }
            seen[name] = true;
            const $badge = $(this).closest(".badge, .o_tag");
            areas.push({
                id: parseInt($badge.data("id") || $badge.attr("data-id"), 10) || null,
                name: name,
            });
        });
        if (!areas.length) {
            $root.find(".badge").each(function () {
                const $badge = $(this);
                const $clone = $badge.clone();
                $clone.find(".o_tag_delete, .fa, .o_badge_delete").remove();
                const name = ($clone.text() || "").trim();
                if (!name || seen[name]) {
                    return;
                }
                seen[name] = true;
                areas.push({
                    id: parseInt($badge.data("id") || $badge.attr("data-id"), 10) || null,
                    name: name,
                });
            });
        }
        return areas;
    }

    /** Pestaña cotización por área: buscar por el o2m (no depende de class en tab-pane). */
    function findQuoterAreaPaneAndNav($form) {
        const $pane = $form
            .find('.o_field_one2many[name="quoter_area_block_ids"]')
            .closest(".tab-pane")
            .first();
        if (!$pane.length) {
            return {$pane: $(), $nav: $(), $link: $()};
        }
        const $nav = $pane.closest(".o_notebook").find("ul.nav-tabs").first();
        let $link = $();
        const paneId = $pane.attr("id");
        if (paneId) {
            $link = $nav.find('a.nav-link[href="#' + paneId + '"]').first();
        }
        if (!$link.length) {
            $nav.find("a.nav-link").each(function () {
                const href = $(this).attr("href");
                if (
                    href &&
                    href.indexOf("#") === 0 &&
                    $form.find(href).find('[name="quoter_area_block_ids"]').length
                ) {
                    $link = $(this);
                    return false;
                }
            });
        }
        return {$pane: $pane, $nav: $nav, $link: $link};
    }

    function updateQuoterAreaTabs(renderer) {
        const $form = $(renderer.el);
        const areas = collectAreasFromTags($form);
        const parts = findQuoterAreaPaneAndNav($form);
        const $pane = parts.$pane;
        const $nav = parts.$nav;
        const $link = parts.$link;
        if (!$pane.length || !$nav.length) {
            return;
        }
        const $staticLi = $link.closest("li.nav-item");
        $nav.find("li.o_quoter_dyn_area_tab").remove();

        if (!areas.length) {
            $staticLi.hide();
            $pane.removeClass("o_quoter_slot_tax");
            return;
        }

        const href =
            ($link.length && $link.attr("href")) || "#" + ($pane.attr("id") || "");

        if (areas.length === 1) {
            if ($link.length) {
                const tabTitle = areas[0].name;
                if (($link.text() || "").trim() !== tabTitle) {
                    $link.text(tabTitle);
                }
            }
            $staticLi.show().removeClass("d-none");
            $pane.toggleClass("o_quoter_slot_tax", /\btax\b/i.test(areas[0].name));
            return;
        }

        $staticLi.hide();
        areas.forEach(function (area, idx) {
            const $li = $('<li class="nav-item o_quoter_dyn_area_tab"/>');
            const $a = $('<a class="nav-link" role="tab" data-toggle="tab"/>')
                .attr("href", href)
                .text(area.name);
            if (idx === 0) {
                $a.addClass("active");
            }
            $li.append($a);
            $nav.append($li);
            if (idx === 0) {
                $pane.toggleClass("o_quoter_slot_tax", /\btax\b/i.test(area.name));
            }
        });
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
        updateQuoterAreaTabs(renderer);
        $form.find(".tab-pane").has('[name="quoter_area_block_ids"]').each(function () {
            const $pane = $(this);
            const $active = $pane.closest(".o_notebook").find("a.nav-link.active");
            const title = ($active.text() || "").trim();
            if (!title) {
                return;
            }
            const isTax = /\btax\b/i.test(String(title));
            $pane.toggleClass("o_quoter_slot_tax", !!isTax);
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
            const changed = (ev && ev.data && ev.data.changes) || {};
            // Cuando cambian áreas / slots, renombrar pestañas.
            const keys = Object.keys(changed);
            const relevant = keys.some(function (k) {
                return (
                    k === "quoter_area_ids" ||
                    k === "quoter_area_block_ids" ||
                    k === "quoter_primary_tab_area_name" ||
                    k === "quoter_area_block_count" ||
                    k === "is_quotation" ||
                    k === "date_order" ||
                    (k.startsWith("quoter_slot_") && k.endsWith("_area_id"))
                );
            });
            if (relevant) {
                const self = this;
                [0, 80, 250, 600].forEach(function (ms) {
                    setTimeout(function () {
                        updateLabels(self.renderer);
                    }, ms);
                });
            }
        },
    });
});


odoo.define("quoter.bulk_add_lines", function (require) {
    "use strict";

    const AbstractAction = require("web.AbstractAction");
    const core = require("web.core");
    const Dialog = require("web.Dialog");
    const ListRenderer = require("web.ListRenderer");
    const relationalFields = require("web.relational_fields");
    const rpc = require("web.rpc");

    const _t = core._t;

    const COLOR_PALETTE = [
        "#212529",
        "#e74c3c",
        "#3498db",
        "#f1c40f",
        "#2ecc71",
        "#9b59b6",
        "#e67e22",
        "#1abc9c",
        "#34495e",
        "#d35400",
        "#16a085",
        "#7f8c8d",
    ];

    const SIN_ETIQUETA = "Sin Etiqueta";

    function escapeHtml(s) {
        return String(s == null ? "" : s)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function hexToRgb(hex) {
        const clean = (hex || "").replace("#", "");
        if (clean.length !== 6) {
            return { r: 33, g: 37, b: 41 };
        }
        return {
            r: parseInt(clean.slice(0, 2), 16),
            g: parseInt(clean.slice(2, 4), 16),
            b: parseInt(clean.slice(4, 6), 16),
        };
    }

    function sectionColor(colorIndex, sectionLabel) {
        if (sectionLabel === SIN_ETIQUETA) {
            return "#212529";
        }
        const idx = parseInt(colorIndex, 10);
        if (isNaN(idx) || idx < 0) {
            return "#212529";
        }
        return COLOR_PALETTE[Math.abs(idx) % COLOR_PALETTE.length];
    }

    function groupProductsBySection(products) {
        const groups = [];
        const index = {};
        (products || []).forEach(function (row) {
            const section = row.section || SIN_ETIQUETA;
            if (!index[section]) {
                index[section] = {
                    section: section,
                    color: row.separator_color,
                    items: [],
                };
                groups.push(index[section]);
            }
            index[section].items.push(row);
        });
        return groups;
    }

    function buildBulkDialogHtml(products) {
        if (!products.length) {
            return (
                '<p class="text-muted mb-0">' +
                escapeHtml(_t("No hay productos pendientes de cargar.")) +
                "</p>"
            );
        }
        const groups = groupProductsBySection(products);
        let html =
            '<div class="o_quoter_bulk_add_lines_dialog">' +
            '<p class="text-muted small mb-2">' +
            escapeHtml(
                _t(
                    "Productos del área que aún no están en este bloque. Desmarque los que no desea cargar."
                )
            ) +
            "</p>" +
            '<div class="o_quoter_bulk_add_toolbar mb-2">' +
            '<label class="mb-0 o_quoter_bulk_add_select_all_label">' +
            '<input type="checkbox" class="o_quoter_bulk_add_select_all mr-1" checked="checked"/> ' +
            escapeHtml(_t("Seleccionar todos")) +
            "</label>" +
            "</div>" +
            '<div class="o_quoter_bulk_add_lines_list border rounded">';
        groups.forEach(function (group) {
            const color = sectionColor(group.color, group.section);
            const rgb = hexToRgb(color);
            html +=
                '<div class="o_quoter_bulk_add_section" style="border-top: 2px solid ' +
                escapeHtml(color) +
                "; background-color: rgba(" +
                rgb.r +
                "," +
                rgb.g +
                "," +
                rgb.b +
                ',0.08); margin-top: 6px; padding-top: 4px;">' +
                '<div class="o_quoter_bulk_add_section_title font-weight-bold px-1 py-1" style="color: ' +
                escapeHtml(color) +
                ';">' +
                escapeHtml(group.section) +
                "</div>";
            group.items.forEach(function (row) {
                const pid = String(row.product_id);
                html +=
                    '<div class="form-check o_quoter_bulk_add_product_row">' +
                    '<input type="checkbox" class="form-check-input o_quoter_bulk_add_chk" ' +
                    'checked="checked" id="quoter_bulk_pid_' +
                    escapeHtml(pid) +
                    '" data-product-id="' +
                    escapeHtml(pid) +
                    '"/>' +
                    '<label class="form-check-label" for="quoter_bulk_pid_' +
                    escapeHtml(pid) +
                    '">' +
                    escapeHtml(row.name || "") +
                    "</label>" +
                    "</div>";
            });
            html += "</div>";
        });
        html += "</div></div>";
        return html;
    }

    function syncSelectAllCheckbox($content) {
        const $all = $content.find(".o_quoter_bulk_add_chk");
        const $checked = $all.filter(":checked");
        const $selectAll = $content.find(".o_quoter_bulk_add_select_all");
        if (!$all.length) {
            $selectAll.prop("checked", false).prop("indeterminate", false);
            return;
        }
        if ($checked.length === 0) {
            $selectAll.prop("checked", false).prop("indeterminate", false);
        } else if ($checked.length === $all.length) {
            $selectAll.prop("checked", true).prop("indeterminate", false);
        } else {
            $selectAll.prop("checked", false).prop("indeterminate", true);
        }
    }

    function bindBulkDialogEvents(dialog) {
        dialog.opened(function () {
            if (dialog.$modal) {
                dialog.$modal
                    .find(".modal-dialog")
                    .addClass("o_quoter_bulk_add_modal_dialog");
            }
            const $content = dialog.$content;
            $content.on("change.quoter_bulk", ".o_quoter_bulk_add_select_all", function () {
                const checked = $(this).prop("checked");
                $(this).prop("indeterminate", false);
                $content.find(".o_quoter_bulk_add_chk").prop("checked", checked);
            });
            $content.on("change.quoter_bulk", ".o_quoter_bulk_add_chk", function () {
                syncSelectAllCheckbox($content);
            });
            syncSelectAllCheckbox($content);
        });
    }

    function walkWidgetParents(widget) {
        const out = [];
        let p = widget;
        while (p) {
            out.push(p);
            p = p.getParent ? p.getParent() : null;
        }
        return out;
    }

    function getAreaBlocksHostFromDom($el) {
        const $embed = $el.closest(".o_quoter_area_blocks_embed");
        if (!$embed.length) {
            const $global = $(".o_quoter_area_blocks_embed").first();
            if ($global.length) {
                return (
                    $global
                        .find('.o_field_one2many[name="quoter_area_block_ids"]')
                        .data("quoterAreaBlockO2M") || null
                );
            }
            return null;
        }
        return (
            $embed
                .find('.o_field_one2many[name="quoter_area_block_ids"]')
                .data("quoterAreaBlockO2M") || null
        );
    }

    function getAreaBlocksHost(widget) {
        const fromDom = widget && widget.$el && getAreaBlocksHostFromDom(widget.$el);
        if (fromDom) {
            return fromDom;
        }
        const chain = walkWidgetParents(widget);
        for (let i = 0; i < chain.length; i++) {
            const p = chain[i];
            if (p && typeof p._quoterGetAreaBlocksHostField === "function") {
                const host = p._quoterGetAreaBlocksHostField();
                if (host) {
                    return host;
                }
            }
        }
        return null;
    }

    function getOrderLineFieldWidget(widget) {
        if (widget && widget.name === "order_line_ids") {
            return widget;
        }
        const chain = walkWidgetParents(widget);
        for (let i = 0; i < chain.length; i++) {
            const p = chain[i];
            if (p && p.name === "order_line_ids") {
                return p;
            }
        }
        return widget;
    }

    function getEmbedFormView(host, widget, blockId) {
        if (host && host.__quoterEmbedForm) {
            if (!blockId || host.__quoterEmbedForm.res_id === blockId) {
                return host.__quoterEmbedForm;
            }
        }
        const chain = walkWidgetParents(widget);
        for (let i = 0; i < chain.length; i++) {
            const p = chain[i];
            if (
                p &&
                p.modelName === "quoter.sale.order.area" &&
                p.handle &&
                p.model &&
                (!blockId || p.res_id === blockId)
            ) {
                return p;
            }
        }
        return null;
    }

    function getBlockContext(host, formView) {
        if (!formView || !formView.model || !formView.handle) {
            return null;
        }
        const dp = formView.model.get(formView.handle, {raw: true});
        if (!dp || !dp.data) {
            return null;
        }
        return {
            host: host,
            formView: formView,
            data: dp.data,
            res_id: dp.res_id,
        };
    }

    function isQuoterBlockOrderLineContext($el) {
        return !!$el.closest(".o_quoter_area_blocks_embed, .o_quoter_area_block_form_body")
            .length;
    }

    function blockAllowsBulkAdd(block) {
        if (!block || !block.data) {
            return false;
        }
        if (!block.data.area_bulk_line_load) {
            return false;
        }
        if (block.data.lines_frozen || block.data.block_editable === false) {
            return false;
        }
        if (block.data.area_is_formula) {
            return true;
        }
        return !!block.data.complexity_level_id;
    }

    function findAddLineCell($scope) {
        let $cell = $scope.find("td.o_field_x2many_list_row_add").first();
        if ($cell.length) {
            return $cell;
        }
        $cell = $scope.find("td.o_group_field_row_add").first();
        if ($cell.length) {
            return $cell;
        }
        let found = null;
        $scope.find("tbody tr").last().find("td").each(function () {
            const $td = $(this);
            const $a = $td.find('a[role="button"]').first();
            if (!$a.length) {
                return;
            }
            const txt = ($a.text() || "").toLowerCase();
            if (txt.indexOf("agregar") >= 0 && txt.indexOf("línea") >= 0) {
                found = $td;
                return false;
            }
            if (txt.indexOf("agregar") >= 0 && txt.indexOf("linea") >= 0) {
                found = $td;
                return false;
            }
        });
        return found;
    }

    function getParentSaleOrderController(widget) {
        let p = widget;
        while (p) {
            if (p.modelName === "sale.order" && p.handle) {
                return p;
            }
            p = p.getParent && p.getParent();
        }
        return null;
    }

    function quoterEnsureParentEditMode(parentFc) {
        if (!parentFc) {
            return Promise.resolve();
        }
        if (parentFc.mode === "readonly" && typeof parentFc._setMode === "function") {
            parentFc._setMode("edit");
        }
        const orderDp =
            parentFc.model && parentFc.handle
                ? parentFc.model.get(parentFc.handle, {raw: true})
                : null;
        if (orderDp && !orderDp.res_id && typeof parentFc.saveRecord === "function") {
            return parentFc
                .saveRecord(parentFc.handle, {
                    stayInEdit: true,
                    reload: false,
                    savePoint: false,
                })
                .catch(function () {
                    return Promise.resolve();
                });
        }
        return Promise.resolve();
    }

    /**
     * Persiste pedido/bloque en servidor si hace falta (sin pedir guardar la cotización al usuario).
     */
    function quoterEnsureBlockSavedForBulkAdd(widget, block) {
        const formView = block.formView;
        const host = block.host || widget;
        if (!formView || !formView.model || !formView.handle) {
            return Promise.resolve(false);
        }
        const parentFc = getParentSaleOrderController(host || widget);
        return quoterEnsureParentEditMode(parentFc).then(function () {
            const dp = formView.model.get(formView.handle, {raw: true});
            if (dp && dp.res_id) {
                block.res_id = dp.res_id;
                return dp.res_id;
            }
            if (host && typeof host._quoterInvokeEmbeddedFormSave === "function") {
                return host._quoterInvokeEmbeddedFormSave(formView).then(function () {
                    const dp2 = formView.model.get(formView.handle, {raw: true});
                    const rid = dp2 && dp2.res_id;
                    if (rid) {
                        block.res_id = rid;
                    }
                    return rid || false;
                });
            }
            return false;
        });
    }

    function quoterAfterBulkAddLines(widget, block) {
        const host = block.host || getAreaBlocksHost(widget);
        const formView = block.formView;
        if (host && typeof host._quoterAfterBulkLinesAdded === "function" && formView) {
            return host._quoterAfterBulkLinesAdded(formView);
        }
        if (host && typeof host._quoterRefreshAfterAdjustmentLine === "function" && formView) {
            return host._quoterRefreshAfterAdjustmentLine(formView);
        }
        return Promise.resolve();
    }

    /**
     * Diálogo HTML (sin formulario Odoo) para evitar conflictos con la lista editable.
     */
    function openBulkAddDialog(widget, block) {
        return quoterEnsureBlockSavedForBulkAdd(widget, block).then(function (blockId) {
            if (!blockId) {
                Dialog.alert(
                    widget,
                    _t(
                        "No se pudo preparar el bloque del área. Verifique el nivel del área e intente de nuevo."
                    ),
                    {title: _t("Carga múltiple")}
                );
                return;
            }
            block.res_id = blockId;
            return rpc
                .query({
                    model: "quoter.sale.order.area",
                    method: "get_bulk_add_lines_data",
                    args: [[blockId]],
                })
                .then(function (payload) {
                    if (!payload || !payload.enabled) {
                        Dialog.alert(
                            widget,
                            (payload && payload.message) ||
                                _t("La carga múltiple no está disponible."),
                            {title: _t("Carga múltiple")}
                        );
                        return;
                    }
                    const products = payload.products || [];
                    const dialog = new Dialog(widget, {
                        title: _t("Agregar múltiples líneas"),
                        size: "large",
                        $content: $(buildBulkDialogHtml(products)),
                        buttons: [
                            {
                                text: _t("Aceptar"),
                                classes: "btn-primary",
                                close: false,
                                click: function () {
                                    const $content = dialog.$content;
                                    const selected = [];
                                    $content
                                        .find(".o_quoter_bulk_add_chk:checked")
                                        .each(function () {
                                            const pid = $(this).data("product-id");
                                            if (pid) {
                                                selected.push(parseInt(pid, 10));
                                            }
                                        });
                                    if (!selected.length) {
                                        Dialog.alert(
                                            widget,
                                            _t("Seleccione al menos un producto."),
                                            {title: _t("Carga múltiple")}
                                        );
                                        return;
                                    }
                                    dialog.$footer.find("button").prop("disabled", true);
                                    return rpc
                                        .query({
                                            model: "quoter.sale.order.area",
                                            method: "action_quoter_bulk_add_lines",
                                            args: [[blockId], selected],
                                        })
                                        .then(function () {
                                            dialog.close();
                                            if (!block.host) {
                                                block.host = getAreaBlocksHost(widget);
                                            }
                                            if (!block.formView && block.host) {
                                                block.formView = getEmbedFormView(
                                                    block.host,
                                                    widget,
                                                    blockId
                                                );
                                            }
                                            const refresh = quoterAfterBulkAddLines(
                                                block.host || widget,
                                                block
                                            );
                                            if (
                                                refresh &&
                                                typeof refresh.guardedCatch === "function"
                                            ) {
                                                return refresh.guardedCatch(function () {
                                                    return Promise.resolve();
                                                });
                                            }
                                            return refresh;
                                        })
                                        .catch(function () {
                                            dialog.$footer.find("button").prop(
                                                "disabled",
                                                false
                                            );
                                        });
                                },
                            },
                            {
                                text: _t("Cancelar"),
                                close: true,
                            },
                        ],
                    });
                    bindBulkDialogEvents(dialog);
                    dialog.open();
                });
        });
    }

    /**
     * Botón del encabezado del bloque: abre el diálogo sin acción cliente (no vacía la vista).
     */
    function quoterPatchEmbedFormBulkAddButton(embedForm, areaBlockField) {
        if (!embedForm || embedForm.__quoterBulkAddBtnPatched) {
            return;
        }
        embedForm.__quoterBulkAddBtnPatched = true;
        const origOnButtonClicked = embedForm._onButtonClicked.bind(embedForm);
        embedForm._onButtonClicked = function (ev) {
            const attrs = ev.data && ev.data.attrs;
            if (
                attrs &&
                attrs.type === "object" &&
                attrs.name === "action_quoter_open_bulk_add_wizard"
            ) {
                ev.stopPropagation();
                if (ev.preventDefault) {
                    ev.preventDefault();
                }
                if (ev.originalEvent && ev.originalEvent.preventDefault) {
                    ev.originalEvent.preventDefault();
                }
                let blockId = false;
                if (embedForm.model && embedForm.handle) {
                    const dp = embedForm.model.get(embedForm.handle, {raw: true});
                    blockId = dp && dp.res_id;
                }
                return openBulkAddDialog(areaBlockField || embedForm, {
                    res_id: blockId,
                    host: areaBlockField,
                    formView: embedForm,
                });
            }
            return origOnButtonClicked(ev);
        };
    }

    function injectBulkAddIntoCell($cell, widget) {
        if (!$cell || !$cell.length) {
            return;
        }
        $cell.find("a.o_quoter_bulk_add_lines_trigger").remove();
        const fieldWidget = getOrderLineFieldWidget(widget);
        const host = getAreaBlocksHost(fieldWidget || widget);
        const formView = getEmbedFormView(host, fieldWidget || widget);
        const block = getBlockContext(host, formView);
        if (!blockAllowsBulkAdd(block)) {
            return;
        }
        $cell.addClass("o_quoter_bulk_add_line_cell");
        const $link = $(
            '<a href="#" role="button" class="o_quoter_bulk_add_lines_trigger ml16">' +
                escapeHtml(_t("Agregar múltiples líneas")) +
                "</a>"
        );
        $cell.append($link);
        $link.off("click.quoterBulk").on("click.quoterBulk", function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            const hostNow = getAreaBlocksHost(fieldWidget || widget);
            const fv = getEmbedFormView(hostNow, fieldWidget || widget);
            const blk = getBlockContext(hostNow, fv);
            if (blk) {
                blk.host = hostNow;
                openBulkAddDialog(fieldWidget || widget, blk);
            }
        });
    }

    function scheduleInjectBulkAdd(widget) {
        const fieldWidget = getOrderLineFieldWidget(widget);
        const $scope =
            fieldWidget && fieldWidget.$el && fieldWidget.$el.length
                ? fieldWidget.$el
                : widget && widget.$el
                ? widget.$el
                : null;
        if (!$scope || !$scope.length || !isQuoterBlockOrderLineContext($scope)) {
            return;
        }
        const $cell = findAddLineCell($scope);
        if ($cell) {
            injectBulkAddIntoCell($cell, fieldWidget || widget);
        }
    }

    function injectInEmbedBlock($body, formView, host) {
        if (!$body || !$body.length) {
            return;
        }
        scheduleInjectBulkAdd(host || {__quoterEmbedForm: formView, $el: $body});
        [50, 200, 500, 1200].forEach(function (ms) {
            setTimeout(function () {
                scheduleInjectBulkAdd(host || {__quoterEmbedForm: formView, $el: $body});
            }, ms);
        });
    }

    ListRenderer.include({
        _renderRows: function () {
            const $rows = this._super.apply(this, arguments);
            const self = this;
            if (
                this.addCreateLine &&
                isQuoterBlockOrderLineContext($(this.el)) &&
                $rows &&
                $rows.length
            ) {
                const $tr = $rows[$rows.length - 1];
                const $td = $tr && $tr.find("td.o_field_x2many_list_row_add");
                if ($td && $td.length) {
                    setTimeout(function () {
                        if (!self.isDestroyed()) {
                            injectBulkAddIntoCell($td, self);
                        }
                    }, 0);
                }
            }
            return $rows;
        },

        _renderView: function () {
            const def = this._super.apply(this, arguments);
            const self = this;
            const run = function () {
                if (!self.isDestroyed()) {
                    scheduleInjectBulkAdd(self);
                }
            };
            if (def && typeof def.then === "function") {
                return def.then(run);
            }
            run();
            return def;
        },
    });

    relationalFields.FieldOne2Many.include({
        _render: function () {
            const result = this._super.apply(this, arguments);
            if (this.name === "order_line_ids" && isQuoterBlockOrderLineContext(this.$el)) {
                const self = this;
                const run = function () {
                    scheduleInjectBulkAdd(self);
                };
                if (result && typeof result.then === "function") {
                    return result.then(run);
                }
                run();
                [80, 300, 800].forEach(function (ms) {
                    setTimeout(function () {
                        if (!self.isDestroyed()) {
                            scheduleInjectBulkAdd(self);
                        }
                    }, ms);
                });
            }
            return result;
        },
    });

    /**
     * Si la URL quedó con la antigua acción cliente (p. ej. tras F5), volver al pedido
     * sin abrir el popup.
     */
    const QuoterBulkAddLinesLegacyRedirect = AbstractAction.extend({
        start: function () {
            const self = this;
            const blockId =
                (this.action.params && this.action.params.block_id) ||
                (this.action.context && this.action.context.default_block_id);
            if (!blockId) {
                return self.do_action({type: "ir.actions.act_window_close"});
            }
            return rpc
                .query({
                    model: "quoter.sale.order.area",
                    method: "read",
                    args: [[blockId], ["order_id"]],
                })
                .then(function (rows) {
                    const orderId =
                        rows &&
                        rows[0] &&
                        rows[0].order_id &&
                        rows[0].order_id[0];
                    if (!orderId) {
                        return self.do_action({type: "ir.actions.act_window_close"});
                    }
                    return self.do_action({
                        type: "ir.actions.act_window",
                        res_model: "sale.order",
                        res_id: orderId,
                        views: [[false, "form"]],
                        view_mode: "form",
                        target: "current",
                    });
                })
                .guardedCatch(function () {
                    return self.do_action({type: "ir.actions.act_window_close"});
                });
        },
    });

    core.action_registry.add(
        "quoter_bulk_add_lines_dialog",
        QuoterBulkAddLinesLegacyRedirect
    );

    return {
        injectInEmbedBlock: injectInEmbedBlock,
        scheduleInjectBulkAdd: scheduleInjectBulkAdd,
        quoterPatchEmbedFormBulkAddButton: quoterPatchEmbedFormBulkAddButton,
        openBulkAddDialog: openBulkAddDialog,
    };
});

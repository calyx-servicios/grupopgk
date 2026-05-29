odoo.define("quoter.formula_matrix", function (require) {
    "use strict";

    const core = require("web.core");
    const Dialog = require("web.Dialog");
    const FormController = require("web.FormController");
    const FormRenderer = require("web.FormRenderer");
    const rpc = require("web.rpc");

    const _t = core._t;

    function escapeHtml(s) {
        return String(s == null ? "" : s)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function escapeAttr(s) {
        return escapeHtml(s).replace(/'/g, "&#39;");
    }

    function getFormDatabaseId(renderer) {
        const st = renderer.state;
        if (!st) {
            return null;
        }
        const rid = st.res_id;
        if (typeof rid === "number" && rid > 0) {
            return rid;
        }
        if (typeof rid === "string" && /^\d+$/.test(rid)) {
            return parseInt(rid, 10);
        }
        const d = st.data || {};
        if (typeof d.id === "number" && d.id > 0) {
            return d.id;
        }
        return null;
    }

    function getFormController(renderer) {
        let parent = renderer && renderer.getParent ? renderer.getParent() : null;
        while (parent) {
            if (parent.do_action && parent.modelName) {
                return parent;
            }
            parent = parent.getParent ? parent.getParent() : null;
        }
        return null;
    }

    function chainPromiseResult(result, fn) {
        if (result && typeof result.then === "function") {
            return result.then(fn);
        }
        fn();
        return result;
    }

    function readData($el, name) {
        const attr = "data-" + name.replace(/([A-Z])/g, "-$1").toLowerCase();
        const camel = name.replace(/-([a-z])/g, function (_m, c) {
            return c.toUpperCase();
        });
        return $el.attr(attr) || $el.data(camel) || $el.data(name);
    }

    function formatNum(n) {
        const x = Number(n);
        if (Number.isNaN(x)) {
            return String(n == null ? 0 : n);
        }
        return x.toLocaleString(undefined, {
            minimumFractionDigits: 0,
            maximumFractionDigits: 2,
        });
    }

    function buildSelectHtml(options, selected, attrs, readOnly) {
        if (readOnly) {
            const opt = (options || []).find(function (o) {
                return o.value === selected;
            });
            return escapeHtml((opt && opt.label) || selected || "");
        }
        let html = "<select " + (attrs || "") + ">";
        (options || []).forEach(function (o) {
            const sel = o.value === selected ? ' selected="selected"' : "";
            html +=
                '<option value="' +
                escapeHtml(o.value) +
                '"' +
                sel +
                ">" +
                escapeHtml(o.label || o.value) +
                "</option>";
        });
        html += "</select>";
        return html;
    }

    function buildFormulaLineEditorHtml(expr) {
        const parts = (expr && expr.parts) || [];
        if (!parts.length) {
            return (
                '<p class="text-muted mb-0">' +
                escapeHtml(_t("Sin fórmula para este rol.")) +
                "</p>"
            );
        }
        let html = '<div class="o_quoter_formula_popup_line o_quoter_formula_expr_editor">';
        parts.forEach(function (part) {
            if (part.type === "text") {
                html +=
                    '<span class="o_quoter_formula_expr_txt">' +
                    escapeHtml(part.content || "") +
                    "</span>";
            } else if (part.type === "param") {
                html +=
                    '<input type="text" inputmode="decimal" tabindex="0" ' +
                    'class="o_quoter_formula_param_input form-control form-control-sm" ' +
                    'data-param-code="' +
                    escapeHtml(part.code || "") +
                    '" value="' +
                    escapeHtml(String(part.value != null ? part.value : 1)) +
                    '"/>';
            }
        });
        html += "</div>";
        return html;
    }

    function bindFormulaPopupTab($container) {
        $container.on("keydown.quoterFormulaTab", ".o_quoter_formula_param_input", function (ev) {
            if (ev.key !== "Tab") {
                return;
            }
            const $inputs = $container.find(".o_quoter_formula_param_input");
            const idx = $inputs.index(ev.currentTarget);
            const next = ev.shiftKey ? idx - 1 : idx + 1;
            if (next >= 0 && next < $inputs.length) {
                ev.preventDefault();
                $inputs.eq(next).focus().select();
            }
        });
    }

    function parseFormulaParamNumber(raw) {
        const s = String(raw == null ? "" : raw).trim().replace(",", ".");
        if (s === "") {
            return null;
        }
        const n = Number(s);
        return Number.isFinite(n) ? n : NaN;
    }

    function validatePopupParamValues($container) {
        let message = "";
        let firstInvalid = null;
        $container.find(".o_quoter_formula_param_input").removeClass("is-invalid");
        $container.find(".o_quoter_formula_param_input").each(function () {
            const $inp = $(this);
            const n = parseFormulaParamNumber($inp.val());
            if (n === null) {
                message = _t("Complete todos los valores de la fórmula.");
                if (!firstInvalid) {
                    firstInvalid = $inp;
                }
                $inp.addClass("is-invalid");
            } else if (Number.isNaN(n)) {
                message = _t("Los valores de la fórmula deben ser numéricos.");
                if (!firstInvalid) {
                    firstInvalid = $inp;
                }
                $inp.addClass("is-invalid");
            }
        });
        if (firstInvalid) {
            firstInvalid.focus().select();
        }
        return {ok: !message, message: message};
    }

    function collectPopupParamValues($container) {
        const values = [];
        $container.find(".o_quoter_formula_param_input").each(function () {
            const $inp = $(this);
            values.push({
                code: readData($inp, "param-code"),
                value: parseFormulaParamNumber($inp.val()),
            });
        });
        return values;
    }

    function showFormulaError(controller, message) {
        if (controller && controller.displayNotification) {
            controller.displayNotification({
                title: _t("Fórmula"),
                message: message,
                type: "danger",
            });
            return;
        }
        Dialog.alert(controller, message, {title: _t("Fórmula")});
    }

    function buildRoleFormulaCell(cell, isFixed, canEdit, areaId) {
        if (isFixed) {
            if (!canEdit) {
                return (
                    '<span class="o_quoter_formula_fixed_hours_val">' +
                    escapeHtml(formatNum(cell.horas_fijas)) +
                    "</span>"
                );
            }
            return (
                '<input type="number" step="any" class="o_quoter_matrix_num_input o_quoter_formula_horas_input form-control form-control-sm text-center" ' +
                'data-line-id="' +
                escapeHtml(String(cell.line_id || "")) +
                '" data-range-id="' +
                escapeHtml(String(cell.range_id)) +
                '" value="' +
                escapeHtml(String(cell.horas_fijas != null ? cell.horas_fijas : 0)) +
                '"/>'
            );
        }
        const rangeLineId = cell.range_line_id;
        const composed = cell.formula_composed || "";
        const title = composed
            ? escapeAttr(composed)
            : escapeAttr(_t("Sin fórmula configurada"));
        let html =
            '<div class="o_quoter_formula_role_hours_cell" title="' + title + '">';
        html += '<div class="o_quoter_formula_role_result_wrap">';
        if (!cell.formula_active) {
            html += '<span class="text-muted o_quoter_formula_hours_val">—</span>';
        } else {
            html +=
                '<span class="o_quoter_formula_hours_val font-weight-bold">' +
                escapeHtml(formatNum(cell.hours)) +
                "</span>";
        }
        if (canEdit) {
            html +=
                '<button type="button" class="o_quoter_formula_edit_btn btn btn-sm btn-outline-secondary py-0 px-1 ml-1" ' +
                'data-area-id="' +
                escapeHtml(String(areaId || "")) +
                '" data-service-line-id="' +
                escapeHtml(String(cell.service_line_id || cell.line_id || "")) +
                '" data-area-range-id="' +
                escapeHtml(String(cell.range_id || "")) +
                '" data-range-line-id="' +
                escapeHtml(String(rangeLineId || "")) +
                '" title="' +
                escapeAttr(_t("Configurar fórmula de este rol")) +
                '">' +
                '<span class="o_quoter_formula_edit_plus" aria-hidden="true">+</span>' +
                "</button>";
        }
        html += "</div></div>";
        return html;
    }

    function buildAreaFormulaMatrixHtml(data) {
        const readOnly = !!(data && data.matrix_read_only);
        const canEdit = !readOnly && !!(data && data.matrix_editor_open);
        const ranges = (data && data.ranges) || [];
        const rows = (data && data.rows) || [];
        const tipoOpts = (data && data.tipo_options) || [];
        const kindOpts = (data && data.formula_kind_options) || [];
        const areaId = (data && data.area_id) || "";

        let html = "";
        if (data && data.section_title) {
            html +=
                '<div class="font-weight-bold mb-2">' +
                escapeHtml(data.section_title) +
                "</div>";
        }
        if (!rows.length) {
            return (
                html +
                '<p class="text-muted mb-0">' +
                escapeHtml((data && data.empty_message) || _t("Sin productos.")) +
                "</p>"
            );
        }

        html +=
            '<div class="o_quoter_matrix_table_responsive mt-1 mb-2">' +
            '<div class="o_quoter_matrix_list o_list_view">' +
            '<table class="o_list_table table table-sm table-hover table-striped o_quoter_area_hours_matrix o_quoter_formula_area_matrix">' +
            "<thead><tr>" +
            '<th class="o_quoter_matrix_th_line">' +
            escapeHtml(_t("Producto")) +
            "</th>" +
            '<th class="o_quoter_matrix_th_line">' +
            escapeHtml(_t("Referencia")) +
            "</th>" +
            '<th class="o_quoter_matrix_th_line">' +
            escapeHtml(_t("Tipo")) +
            "</th>" +
            '<th class="o_quoter_matrix_th_line o_quoter_formula_th_kind">' +
            escapeHtml(_t("Fórmula Excel")) +
            "</th>" +
            '<th class="o_quoter_matrix_th_range o_quoter_formula_th_volume text-center">' +
            escapeHtml(_t("VOLUMEN")) +
            "</th>";
        ranges.forEach(function (r) {
            html +=
                '<th class="o_quoter_matrix_th_range text-center">' +
                escapeHtml(r.name || "") +
                "</th>";
        });
        html += "</tr></thead><tbody>";

        rows.forEach(function (row) {
            const fixed = !!row.is_fixed;
            const lid = row.line_id;
            const rowCls = row.below_vol_min ? " o_quoter_formula_below_vol_min" : "";
            html += '<tr class="' + rowCls + '">';
            html +=
                '<td class="o_quoter_matrix_line_cell">' +
                escapeHtml(row.product_name || "") +
                "</td>";
            html += '<td class="o_quoter_matrix_line_cell">';
            if (!canEdit) {
                html += escapeHtml(row.referencia || "");
            } else {
                html +=
                    '<input type="text" class="form-control form-control-sm o_quoter_formula_ref_input" ' +
                    'data-line-id="' +
                    escapeHtml(String(lid)) +
                    '" value="' +
                    escapeHtml(row.referencia || "") +
                    '"/>';
            }
            html += "</td>";
            html += '<td class="o_quoter_matrix_line_cell">';
            html += buildSelectHtml(
                tipoOpts,
                row.tipo_calculo,
                'class="form-control form-control-sm o_quoter_formula_tipo_select" data-line-id="' +
                    escapeHtml(String(lid)) +
                    '"',
                !canEdit
            );
            html += "</td>";
            html += '<td class="o_quoter_matrix_line_cell o_quoter_formula_kind_col">';
            if (fixed) {
                html += '<span class="text-muted">—</span>';
            } else if (!canEdit) {
                const kopt = kindOpts.find(function (o) {
                    return o.value === row.formula_kind;
                });
                html += escapeHtml((kopt && kopt.label) || row.formula_kind || "");
            } else {
                html += buildSelectHtml(
                    kindOpts,
                    row.formula_kind || "linear",
                    'class="form-control form-control-sm o_quoter_formula_kind_select" data-line-id="' +
                        escapeHtml(String(lid)) +
                        '"',
                    false
                );
            }
            html += "</td>";
            html += '<td class="o_quoter_matrix_cell text-center o_quoter_formula_volume_col">';
            if (!canEdit || fixed) {
                html += escapeHtml(formatNum(row.volume));
            } else {
                html +=
                    '<input type="number" step="any" class="o_quoter_matrix_num_input o_quoter_formula_volume_input form-control form-control-sm text-center" ' +
                    'data-line-id="' +
                    escapeHtml(String(lid)) +
                    '" value="' +
                    escapeHtml(String(row.volume != null ? row.volume : 1)) +
                    '"/>';
            }
            html += "</td>";

            (row.role_cells || []).forEach(function (cell) {
                const cellData = Object.assign({}, cell, {
                    line_id: lid,
                    service_line_id: lid,
                });
                const belowCls = cell.below_vol_min ? " o_quoter_formula_role_below_min" : "";
                const editCls =
                    canEdit && !fixed ? " o_quoter_formula_role_cell--editable" : "";
                html +=
                    '<td class="o_quoter_matrix_cell text-center o_quoter_formula_role_cell' +
                    belowCls +
                    editCls +
                    '" data-service-line-id="' +
                    escapeHtml(String(lid)) +
                    '" data-area-range-id="' +
                    escapeHtml(String(cell.range_id || "")) +
                    '">';
                html += buildRoleFormulaCell(cellData, fixed, canEdit, areaId);
                html += "</td>";
            });
            html += "</tr>";
        });

        html += "</tbody></table></div></div>";
        if (canEdit) {
            html +=
                '<p class="text-muted small mb-0">' +
                escapeHtml(
                    _t(
                        "Fórmula Excel: plantilla por fila. Botón + o doble clic en un rol: popup para completar la fórmula (Tab entre cada nº)."
                    )
                ) +
                "</p>";
        } else if (!readOnly) {
            html +=
                '<p class="text-warning small mb-0">' +
                escapeHtml(
                    _t(
                        "Abra el editor de tabla (cabecera del área) para editar fórmulas y ver el botón de edición por rol."
                    )
                ) +
                "</p>";
        }
        return html;
    }

    function buildQuotationVolumeTableHtml(data) {
        const readOnly = !!(data && data.matrix_read_only);
        const ranges = (data && data.ranges) || [];
        const rows = (data && data.rows) || [];
        if (!rows.length) {
            return (
                '<p class="text-muted mb-0">' +
                escapeHtml((data && data.empty_message) || _t("Sin filas.")) +
                "</p>"
            );
        }
        let html =
            '<div class="o_quoter_matrix_table_responsive mt-2 mb-2">' +
            '<div class="o_quoter_matrix_list o_list_view">' +
            '<table class="o_list_table table table-sm table-hover table-striped o_quoter_area_hours_matrix">' +
            "<thead><tr>" +
            '<th class="o_quoter_matrix_th_line">' +
            escapeHtml(_t("Producto")) +
            "</th>" +
            '<th class="o_quoter_matrix_th_line">' +
            escapeHtml(_t("Referencia")) +
            "</th>" +
            '<th class="o_quoter_matrix_th_range text-center">' +
            escapeHtml(_t("Volumen")) +
            "</th>";
        ranges.forEach(function (r) {
            html +=
                '<th class="o_quoter_matrix_th_range text-center">' +
                escapeHtml(r.name || "") +
                "</th>";
        });
        html += "</tr></thead><tbody>";
        rows.forEach(function (row) {
            const fixed = row.tipo_calculo === "fija";
            html += "<tr>";
            html +=
                '<td class="o_quoter_matrix_line_cell">' +
                escapeHtml(row.product_name || "") +
                "</td>";
            html +=
                '<td class="o_quoter_matrix_line_cell text-muted">' +
                escapeHtml(row.referencia || "") +
                "</td>";
            html += '<td class="o_quoter_matrix_cell text-center">';
            if (readOnly || fixed) {
                html += escapeHtml(String(row.volume != null ? row.volume : ""));
            } else {
                html +=
                    '<input type="number" step="any" class="o_quoter_matrix_num_input o_quoter_formula_volume_input form-control form-control-sm text-center" ' +
                    'data-line-id="' +
                    escapeHtml(String(row.line_id)) +
                    '" value="' +
                    escapeHtml(String(row.volume != null ? row.volume : 0)) +
                    '"/>';
            }
            html += "</td>";
            (row.hours || []).forEach(function (h) {
                html +=
                    '<td class="o_quoter_matrix_cell text-center">' +
                    escapeHtml(String(h != null ? h : 0)) +
                    "</td>";
            });
            html += "</tr>";
        });
        html += "</tbody></table></div></div>";
        return html;
    }

    function rpcFormulaWrite(areaId, lineId, writeKind, value, rangeId) {
        return rpc.query({
            model: "quoter.professional.area",
            method: "matrix_preview_write_formula",
            args: [[areaId], lineId, writeKind, value, rangeId || false],
        });
    }

    function bindAreaFormulaMatrix($root, areaId, controller) {
        function reload(result) {
            $root.html(buildAreaFormulaMatrixHtml(result));
            bindAreaFormulaMatrix($root, areaId, controller);
        }

        function onWrite(ev, writeKind, getValue, rangeId) {
            const $el = $(ev.currentTarget);
            const lineId = readData($el, "line-id");
            $el.prop("disabled", true);
            rpcFormulaWrite(areaId, lineId, writeKind, getValue($el), rangeId)
                .then(reload)
                .catch(function () {
                    $el.prop("disabled", false);
                });
        }

        $root.off("change.quoterFormulaArea");
        $root.on(
            "change.quoterFormulaArea",
            ".o_quoter_formula_volume_input",
            function (ev) {
                onWrite(ev, "volume", function ($e) {
                    return $e.val();
                });
            }
        );
        $root.on(
            "change.quoterFormulaArea",
            ".o_quoter_formula_ref_input",
            function (ev) {
                onWrite(ev, "referencia", function ($e) {
                    return $e.val();
                });
            }
        );
        $root.on(
            "change.quoterFormulaArea",
            ".o_quoter_formula_tipo_select",
            function (ev) {
                onWrite(ev, "tipo_calculo", function ($e) {
                    return $e.val();
                });
            }
        );
        $root.on(
            "change.quoterFormulaArea",
            ".o_quoter_formula_kind_select",
            function (ev) {
                onWrite(ev, "formula_kind", function ($e) {
                    return $e.val();
                });
            }
        );
        $root.on(
            "change.quoterFormulaArea",
            ".o_quoter_formula_horas_input",
            function (ev) {
                const $el = $(ev.currentTarget);
                onWrite(
                    ev,
                    "horas_fijas",
                    function ($e) {
                        return $e.val();
                    },
                    readData($el, "range-id")
                );
            }
        );
    }

    function bindQuotationVolumeSave($root, blockId) {
        $root.off("change.quoterFormula", ".o_quoter_formula_volume_input");
        $root.on("change.quoterFormula", ".o_quoter_formula_volume_input", function (ev) {
            const $inp = $(ev.currentTarget);
            const lineId = $inp.data("line-id");
            const volume = $inp.val();
            $inp.prop("disabled", true);
            rpc.query({
                model: "quoter.sale.order.area",
                method: "matrix_preview_write_formula_volume",
                args: [[blockId], lineId, volume],
            })
                .then(function (result) {
                    $root.html(buildQuotationVolumeTableHtml(result));
                    bindQuotationVolumeSave($root, blockId);
                })
                .catch(function () {
                    $inp.prop("disabled", false);
                });
        });
    }

    function renderAreaFormulaMatrix(renderer) {
        if (!renderer || renderer.state.model !== "quoter.professional.area") {
            return;
        }
        const $roots = $(renderer.el).find(".o_quoter_formula_area_matrix_root");
        if (!$roots.length) {
            return;
        }
        const resId = getFormDatabaseId(renderer);
        const controller = getFormController(renderer);
        if (!resId) {
            $roots.html(
                '<p class="text-muted">' +
                    escapeHtml(_t("Guarde el área para configurar la matriz.")) +
                    "</p>"
            );
            return;
        }
        $roots.html(
            '<div class="text-center text-muted py-2"><i class="fa fa-spinner fa-spin"></i></div>'
        );
        rpc.query({
            model: "quoter.professional.area",
            method: "get_formula_test_preview_data",
            args: [[resId]],
        })
            .then(function (result) {
                $roots.html(buildAreaFormulaMatrixHtml(result));
                bindAreaFormulaMatrix($roots, resId, controller);
            })
            .catch(function () {
                $roots.html(
                    '<p class="text-danger">' +
                        escapeHtml(_t("No se pudo cargar la matriz.")) +
                        "</p>"
                );
            });
    }

    function renderQuotationFormulaMatrix() {
        /* Volumen y horas por rol van en order_line_ids del bloque; sin tabla JS duplicada. */
    }

    function safeRender(renderer) {
        try {
            renderAreaFormulaMatrix(renderer);
            renderQuotationFormulaMatrix(renderer);
        } catch (e) {
            if (window.console && console.error) {
                console.error("[quoter.formula_matrix]", e);
            }
        }
    }

    function afterMutation(controllerOrRenderer) {
        const renderer =
            controllerOrRenderer && controllerOrRenderer.renderer
                ? controllerOrRenderer.renderer
                : controllerOrRenderer;
        if (!renderer) {
            return;
        }
        safeRender(renderer);
    }

    FormRenderer.include({
        _renderView: function () {
            const res = this._super.apply(this, arguments);
            const self = this;
            return chainPromiseResult(res, function () {
                safeRender(self);
            });
        },
    });

    function openFormulaRangeEditor(controller, areaId, serviceLineId, areaRangeId, onReload) {
        if (!controller || !areaId || !serviceLineId || !areaRangeId) {
            return;
        }
        const areaIdInt = parseInt(areaId, 10);
        rpc.query({
            model: "quoter.professional.area",
            method: "get_formula_range_edit_data",
            args: [[areaIdInt]],
            kwargs: {
                service_line_id: parseInt(serviceLineId, 10),
                area_range_id: parseInt(areaRangeId, 10),
            },
        }).then(function (data) {
            const $content = $(buildFormulaLineEditorHtml(data.expression));
            bindFormulaPopupTab($content);
            const title = data.role_name
                ? _t("Fórmula") + " — " + data.role_name
                : _t("Fórmula");
            const dialog = new Dialog(controller, {
                title: title,
                size: "medium",
                buttons: [
                    {
                        text: _t("Guardar"),
                        classes: "btn-primary",
                        close: false,
                        click: function () {
                            const check = validatePopupParamValues($content);
                            if (!check.ok) {
                                showFormulaError(controller, check.message);
                                return;
                            }
                            const paramValues = collectPopupParamValues($content);
                            rpc.query({
                                model: "quoter.professional.area",
                                method: "save_formula_range_edit",
                                args: [
                                    [areaIdInt],
                                    data.range_line_id,
                                    paramValues,
                                ],
                            })
                                .then(function () {
                                    dialog.close();
                                    if (onReload) {
                                        onReload();
                                    }
                                })
                                .guardedCatch(function (err) {
                                    const msg =
                                        (err && err.data && err.data.message) ||
                                        (err && err.message) ||
                                        _t("No se pudo guardar la fórmula.");
                                    showFormulaError(controller, msg);
                                });
                        },
                    },
                    {
                        text: _t("Descartar"),
                        close: true,
                    },
                ],
                $content: $content,
            });
            const opened = dialog.open();
            function focusFirstInput() {
                const $first = dialog.$(".o_quoter_formula_param_input").first();
                if ($first.length) {
                    $first.focus().select();
                }
            }
            if (opened && typeof opened.then === "function") {
                opened.then(focusFirstInput);
            } else {
                setTimeout(focusFirstInput, 80);
            }
        });
    }

    function triggerFormulaEditFromElement(controller, $el) {
        const $td = $el.closest("td");
        let areaId = readData($el, "area-id");
        if (!areaId && controller && controller.renderer) {
            areaId = getFormDatabaseId(controller.renderer);
        }
        const serviceLineId =
            readData($el, "service-line-id") || readData($td, "service-line-id");
        const areaRangeId =
            readData($el, "area-range-id") || readData($td, "area-range-id");
        if (!controller || !areaId || !serviceLineId || !areaRangeId) {
            return;
        }
        openFormulaRangeEditor(
            controller,
            areaId,
            serviceLineId,
            areaRangeId,
            function () {
                if (controller.renderer) {
                    safeRender(controller.renderer);
                }
            }
        );
    }

    FormController.include({
        start: function () {
            const res = this._super.apply(this, arguments);
            if (this.modelName === "quoter.professional.area") {
                this.$el.on(
                    "click.quoterFormulaEdit",
                    ".o_quoter_formula_edit_btn",
                    this._onQuoterFormulaEditClick.bind(this)
                );
                this.$el.on(
                    "dblclick.quoterFormulaEdit",
                    ".o_quoter_formula_role_cell",
                    this._onQuoterFormulaRoleDblClick.bind(this)
                );
            }
            return res;
        },
        destroy: function () {
            if (this.modelName === "quoter.professional.area") {
                this.$el.off("click.quoterFormulaEdit");
                this.$el.off("dblclick.quoterFormulaEdit");
            }
            return this._super.apply(this, arguments);
        },
        _onQuoterFormulaEditClick: function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            triggerFormulaEditFromElement(this, $(ev.currentTarget));
        },
        _onQuoterFormulaRoleDblClick: function (ev) {
            const $td = $(ev.currentTarget);
            if ($td.closest("tr").find(".o_quoter_formula_tipo_select").val() === "fija") {
                return;
            }
            if (!$td.find(".o_quoter_formula_edit_btn").length) {
                return;
            }
            ev.preventDefault();
            triggerFormulaEditFromElement(this, $td);
        },
        saveRecord: function () {
            const res = this._super.apply(this, arguments);
            if (
                this.modelName === "quoter.sale.order.area" ||
                this.modelName === "quoter.professional.area"
            ) {
                const self = this;
                return chainPromiseResult(res, function () {
                    afterMutation(self);
                });
            }
            return res;
        },
    });
});

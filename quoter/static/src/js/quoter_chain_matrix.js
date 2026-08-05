odoo.define("quoter.chain_matrix", function (require) {
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

    function formatNum(n) {
        const x = Number(n);
        if (Number.isNaN(x)) {
            return String(n == null ? 0 : n);
        }
        return x.toLocaleString(undefined, {
            minimumFractionDigits: 0,
            maximumFractionDigits: 4,
        });
    }

    function chainTableIdEq(a, b) {
        if (a == null || b == null) {
            return false;
        }
        return parseInt(a, 10) === parseInt(b, 10);
    }

    function getPersistedActiveTableId($root) {
        const $wrap = $root.find(".o_quoter_chain_matrix_wrap");
        if (!$wrap.length) {
            return false;
        }
        const fromData = $wrap.data("activeTableId");
        if (fromData != null && fromData !== false) {
            return fromData;
        }
        const payload = $wrap.data("chainPayload") || {};
        return payload.active_table_id || false;
    }

    function focusActiveChainTab($root) {
        const $tab = $root.find(".o_quoter_chain_tab.active");
        if ($tab.length && $tab[0].scrollIntoView) {
            $tab[0].scrollIntoView({block: "nearest", inline: "nearest"});
        }
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
        let html =
            '<div class="o_quoter_formula_popup_line o_quoter_formula_expr_editor">';
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

    function bindChainFormulaPopupTab($container) {
        $container.on(
            "keydown.quoterChainFormulaTab",
            ".o_quoter_formula_param_input",
            function (ev) {
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
            }
        );
    }

    function parseChainFormulaParamNumber(raw) {
        const s = String(raw == null ? "" : raw).trim().replace(",", ".");
        if (s === "") {
            return null;
        }
        const n = Number(s);
        return Number.isFinite(n) ? n : NaN;
    }

    function validateChainPopupParamValues($container) {
        let message = "";
        let firstInvalid = null;
        $container.find(".o_quoter_formula_param_input").removeClass("is-invalid");
        $container.find(".o_quoter_formula_param_input").each(function () {
            const $inp = $(this);
            const n = parseChainFormulaParamNumber($inp.val());
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
                code: $inp.data("param-code") || $inp.attr("data-param-code"),
                value: parseChainFormulaParamNumber($inp.val()),
            });
        });
        return values;
    }

    function showChainFormulaError(controller, message) {
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

    function buildChainRoleCell(cell, canEdit, areaId, isFirstTable) {
        const title = escapeAttr(
            cell.formula_composed ||
                (typeof cell.formula_expression === "string"
                    ? cell.formula_expression
                    : "") ||
                ""
        );
        const canUseFormula = !isFirstTable;
        const isFormula = canUseFormula && cell.value_kind === "formula";
        const hidden = !!cell.hide_in_quote;
        const btnKindClass = isFormula
            ? "o_quoter_chain_edit_btn--formula"
            : "o_quoter_chain_edit_btn--fixed";
        let html =
            '<div class="o_quoter_chain_role_cell" title="' + title + '">';
        if (hidden) {
            html += '<span class="o_quoter_chain_hours_val text-muted">—</span>';
        } else {
            html +=
                '<span class="o_quoter_chain_hours_val font-weight-bold">' +
                escapeHtml(formatNum(cell.computed)) +
                "</span>";
        }
        if (canEdit) {
            html +=
                '<button type="button" class="o_quoter_chain_edit_btn ' +
                btnKindClass +
                '" data-area-id="' +
                escapeHtml(String(areaId || "")) +
                '" data-chain-line-id="' +
                escapeHtml(String(cell.chain_line_id || "")) +
                '" data-has-parent="' +
                (canUseFormula ? "1" : "0") +
                '" title="' +
                escapeAttr(_t("Configurar celda (fijo / fórmula)")) +
                '">' +
                '<span class="o_quoter_chain_edit_plus" aria-hidden="true">+</span>' +
                "</button>";
        }
        html += "</div>";
        return html;
    }

    function buildChainProductMatrixTable(data) {
        const readOnly = !!(data && data.matrix_read_only);
        const canEdit = !readOnly && !!(data && data.matrix_editor_open);
        const ranges = (data && data.ranges) || [];
        const rows = (data && data.rows) || [];
        const areaId = (data && data.area_id) || "";
        const isFirstTable = !!(data && data.is_first_table);

        if (!rows.length) {
            return (
                '<p class="text-muted mb-0">' +
                escapeHtml(
                    (data && data.empty_message) ||
                        _t("Sin productos en el área.")
                ) +
                "</p>"
            );
        }

        let html =
            '<div class="o_quoter_matrix_table_responsive mt-1 mb-2">' +
            '<div class="o_quoter_matrix_list o_list_view">' +
            '<table class="o_list_table table table-sm table-hover table-striped o_quoter_area_hours_matrix o_quoter_chain_product_matrix">' +
            "<thead><tr>" +
            '<th class="o_quoter_matrix_th_line">' +
            escapeHtml(_t("Producto")) +
            "</th>";
        ranges.forEach(function (r) {
            html +=
                '<th class="o_quoter_matrix_th_range text-center">' +
                escapeHtml(r.name || "") +
                "</th>";
        });
        html += "</tr></thead><tbody>";

        rows.forEach(function (row) {
            html += "<tr>";
            html +=
                '<td class="o_quoter_matrix_line_cell">' +
                escapeHtml(row.product_name || "") +
                "</td>";
            const cellsByRange = {};
            (row.role_cells || []).forEach(function (c) {
                cellsByRange[c.range_id] = c;
            });
            ranges.forEach(function (r) {
                const cell = cellsByRange[r.id] || {
                    computed: 0,
                    chain_line_id: 0,
                };
                html +=
                    '<td class="o_quoter_matrix_cell text-center o_quoter_chain_role_col">' +
                    buildChainRoleCell(cell, canEdit, areaId, isFirstTable) +
                    "</td>";
            });
            html += "</tr>";
        });

        html += "</tbody></table></div></div>";
        if (canEdit) {
            html +=
                '<p class="text-muted small mb-0">' +
                escapeHtml(
                        _t(
                            "Botón + en cada rol: Fijo o Fórmula (=último fijo en cadena+nº/delta×(empleados−valor)). La primera tabla solo admite Fijo."
                        )
                ) +
                "</p>";
        }
        return html;
    }

    function buildChainMatrixShell(data) {
        const readOnly = !!(data && data.matrix_read_only);
        const canEdit = !readOnly && !!(data && data.matrix_editor_open);
        const tables = (data && data.tables) || [];
        const activeId = data && data.active_table_id;

        let html = '<div class="o_quoter_chain_matrix_wrap">';
        if (data && data.section_title) {
            html +=
                '<div class="font-weight-bold mb-2">' +
                escapeHtml(data.section_title) +
                "</div>";
        }
        if (canEdit) {
            html +=
                '<div class="o_quoter_chain_toolbar btn-toolbar mb-2">' +
                '<button type="button" class="btn btn-primary o_quoter_chain_btn_new" style="display:none">' +
                escapeHtml(_t("Nueva tabla")) +
                "</button>" +
                '<p class="text-muted small mb-0 o_quoter_chain_create_hint" style="display:none"></p>' +
                "</div>";
        }
        html += '<div class="d-flex align-items-center mb-2 o_quoter_chain_nav">';
        html +=
            '<button type="button" class="btn btn-secondary o_quoter_chain_prev"><i class="fa fa-chevron-left"/></button>';
        html +=
            '<div class="flex-grow-1 mx-2 o_quoter_chain_table_title text-center font-weight-bold"></div>';
        html +=
            '<button type="button" class="btn btn-secondary o_quoter_chain_next"><i class="fa fa-chevron-right"/></button>';
        if (canEdit) {
            html +=
                '<button type="button" class="btn btn-outline-danger ml-2 o_quoter_chain_btn_delete">' +
                escapeHtml(_t("Eliminar tabla")) +
                "</button>";
        }
        html += "</div>";

        if (canEdit) {
            html +=
                '<div class="mb-2 o_quoter_chain_bounds_col">' +
                '<div class="text-muted o_quoter_chain_range_hint mb-2"></div>' +
                '<div class="o_quoter_chain_field_row mb-2">' +
                '<label class="d-block small mb-1">' +
                escapeHtml(_t("Cantidad máxima de empleados")) +
                "</label>" +
                '<input type="text" inputmode="numeric" pattern="[0-9]*" autocomplete="off" ' +
                'class="form-control form-control-sm o_quoter_chain_people_max_input o_quoter_num_no_spin" style="width:6rem"/>' +
                "</div>" +
                '<div class="o_quoter_chain_field_row mb-2">' +
                '<label class="d-block small mb-1">' +
                escapeHtml(_t("Delta")) +
                "</label>" +
                '<input type="text" inputmode="numeric" pattern="[0-9]*" autocomplete="off" ' +
                'class="form-control form-control-sm o_quoter_chain_delta_input o_quoter_num_no_spin" style="width:5rem"/>' +
                "</div></div>" +
                '<div class="mb-2 o_quoter_chain_test_row">' +
                '<label class="d-block small mb-1">' +
                escapeHtml(_t("Empleados (vista previa)")) +
                "</label>" +
                '<div class="d-flex align-items-center flex-wrap">' +
                '<input type="text" inputmode="numeric" pattern="[0-9]*" autocomplete="off" ' +
                'class="form-control form-control-sm o_quoter_chain_test_employees o_quoter_num_no_spin" style="width:6rem"/>' +
                '<span class="ml-2 small text-info o_quoter_chain_resolved_hint"></span>' +
                "</div></div>" +
                '<div class="mb-2 o_quoter_chain_test_complexity_row mt-2">' +
                '<label class="d-block small mb-1">' +
                escapeHtml(_t("Nivel de complejidad (vista previa)")) +
                "</label>" +
                '<div class="d-flex align-items-center flex-wrap">' +
                '<select class="form-control form-control-sm o_quoter_chain_test_complexity" style="max-width:14rem"></select>' +
                '<span class="ml-2 small text-info o_quoter_chain_complexity_hint"></span>' +
                "</div></div>";
        }

        html += '<div class="o_quoter_chain_matrix_body"></div>';
        html += '<ul class="nav nav-tabs mt-2 o_quoter_chain_tabs">';
        tables.forEach(function (t) {
            const active = chainTableIdEq(t.id, activeId) ? " active" : "";
            html +=
                '<li class="nav-item"><a class="nav-link o_quoter_chain_tab' +
                active +
                '" href="#" data-table-id="' +
                escapeHtml(String(t.id)) +
                '">' +
                escapeHtml(t.tab_label || String(t.people_min)) +
                "</a></li>";
        });
        html += "</ul></div>";
        return html;
    }

    function applyChainMatrixData($wrap, data) {
        $wrap.data("chainPayload", data);
        $wrap.data("areaId", data.area_id);
        $wrap.data("activeTableId", data.active_table_id);
        $wrap.find(".o_quoter_chain_matrix_body").html(
            buildChainProductMatrixTable(data)
        );
        const tables = data.tables || [];
        const activeTable = tables.find(function (t) {
            return chainTableIdEq(t.id, data.active_table_id);
        });
        $wrap.find(".o_quoter_chain_table_title").text(
            activeTable ? activeTable.label : ""
        );
        if (activeTable) {
            $wrap
                .find(".o_quoter_chain_range_hint")
                .text(
                    activeTable.tab_label
                        ? _t("Tramo: %s").replace("%s", activeTable.tab_label)
                        : ""
                );
            $wrap
                .find(".o_quoter_chain_people_max_input")
                .val(activeTable.people_max != null ? activeTable.people_max : "");
            $wrap
                .find(".o_quoter_chain_delta_input")
                .val(activeTable.delta != null ? activeTable.delta : 1);
        }
        $wrap
            .find(".o_quoter_chain_test_employees")
            .val(data.test_employee_count || 1);
        const resolvedTab = tables.find(function (t) {
            return chainTableIdEq(t.id, data.resolved_table_id);
        });
        $wrap.find(".o_quoter_chain_tab").removeClass("active");
        if (data.active_table_id != null) {
            $wrap
                .find(
                    '.o_quoter_chain_tab[data-table-id="' +
                        String(data.active_table_id) +
                        '"]'
                )
                .addClass("active");
        }
        if (resolvedTab) {
            $wrap
                .find(".o_quoter_chain_resolved_hint")
                .text(
                    _t("Con %s empleados aplica tabla «%s».")
                        .replace("%s", String(data.test_employee_count))
                        .replace("«%s»", resolvedTab.tab_label || resolvedTab.label)
                );
        }
        const $complexitySel = $wrap.find(".o_quoter_chain_test_complexity");
        if ($complexitySel.length) {
            $complexitySel.empty();
            $complexitySel.append(
                $("<option>", {value: "", text: _t("— Sin nivel —")})
            );
            (data.complexity_levels || []).forEach(function (lev) {
                $complexitySel.append(
                    $("<option>", {
                        value: String(lev.id),
                        text: lev.name || String(lev.id),
                    })
                );
            });
            if (data.test_complexity_level_id) {
                $complexitySel.val(String(data.test_complexity_level_id));
            }
        }
        const $complexityHint = $wrap.find(".o_quoter_chain_complexity_hint");
        if ($complexityHint.length) {
            if (data.test_complexity_level_id && data.complexity_increase_percent != null) {
                $complexityHint.text(
                    _t("Aumento aplicado: %s%.").replace(
                        "%s",
                        String(data.complexity_increase_percent)
                    )
                );
            } else {
                $complexityHint.text(_t("Sin aumento por complejidad."));
            }
        }
        const $newBtn = $wrap.find(".o_quoter_chain_btn_new");
        const $createHint = $wrap.find(".o_quoter_chain_create_hint");
        if ($newBtn.length) {
            if (data.can_create_table) {
                $newBtn.show();
            } else {
                $newBtn.hide();
            }
        }
        if ($createHint.length) {
            if (data.chain_create_table_hint) {
                $createHint.text(data.chain_create_table_hint).show();
            } else {
                $createHint.hide().text("");
            }
        }
    }

    function mountChainMatrix($root, data, areaId, controller) {
        const $wrap = $(buildChainMatrixShell(data));
        applyChainMatrixData($wrap, data);
        $root.empty().append($wrap);
        bindAreaChainMatrix($root, areaId, controller);
        focusActiveChainTab($root);
    }

    function reloadAreaChain($root, areaId, activeTableId, controller) {
        const tableId =
            activeTableId != null && activeTableId !== false
                ? activeTableId
                : getPersistedActiveTableId($root);
        $root.html(
            '<div class="text-center text-muted py-2"><i class="fa fa-spinner fa-spin"></i></div>'
        );
        return rpc
            .query({
                model: "quoter.professional.area",
                method: "get_chain_matrix_preview_data",
                args: [[areaId]],
                kwargs: {active_table_id: tableId || false},
            })
            .then(function (data) {
                mountChainMatrix($root, data, areaId, controller);
            });
    }

    function getChainTestComplexityLevelId() {
        const payload = $(".o_quoter_chain_matrix_wrap").data("chainPayload") || {};
        const raw =
            $(".o_quoter_chain_test_complexity").val() ||
            payload.test_complexity_level_id ||
            false;
        return raw ? parseInt(raw, 10) : false;
    }

    function openChainCellEditor(controller, areaId, chainLineId, onReload) {
        const payload = $(".o_quoter_chain_matrix_wrap").data("chainPayload") || {};
        const emp =
            parseInt(
                $(".o_quoter_chain_test_employees").val() ||
                    payload.test_employee_count,
                10
            ) || 1;
        const complexityLevelId = getChainTestComplexityLevelId();
        rpc.query({
            model: "quoter.professional.area",
            method: "get_chain_line_edit_data",
            args: [[parseInt(areaId, 10)]],
            kwargs: {
                line_id: parseInt(chainLineId, 10),
                employee_count: emp,
                complexity_level_id: complexityLevelId || false,
            },
        }).then(function (data) {
            const canFormula = data.has_parent_table && !data.is_first_table;
            const isFixed = data.is_first_table || data.value_kind === "fixed";
            const $content = $('<div class="o_quoter_chain_popup"></div>');
            if (data.product_name) {
                $content.append(
                    '<p class="text-muted small mb-2">' +
                        escapeHtml(data.product_name) +
                        "</p>"
                );
            }
            if (!canFormula) {
                $content.append(
                    '<div class="o_quoter_chain_popup_fixed mb-2">' +
                        '<label class="d-block small mb-1">' +
                        escapeHtml(_t("Valor fijo")) +
                        "</label>" +
                        '<input type="text" inputmode="decimal" class="form-control o_quoter_chain_popup_fixed_val o_quoter_num_no_spin" value="' +
                        escapeHtml(String(data.fixed_value != null ? data.fixed_value : 0)) +
                        '"/></div>'
                );
            } else {
                $content.append(
                    '<div class="form-group mb-2">' +
                        '<label class="mr-3"><input type="radio" name="ck" value="fixed" ' +
                        (isFixed ? "checked" : "") +
                        "/> " +
                        escapeHtml(_t("Fijo")) +
                        "</label>" +
                        '<label><input type="radio" name="ck" value="formula" ' +
                        (!isFixed ? "checked" : "") +
                        "/> " +
                        escapeHtml(_t("Fórmula")) +
                        "</label></div>" +
                        '<div class="o_quoter_chain_popup_fixed mb-2">' +
                        '<label class="d-block small mb-1">' +
                        escapeHtml(_t("Valor fijo")) +
                        "</label>" +
                        '<input type="text" inputmode="decimal" class="form-control o_quoter_chain_popup_fixed_val o_quoter_num_no_spin" value="' +
                        escapeHtml(String(data.fixed_value != null ? data.fixed_value : 0)) +
                        '"/></div>'
                );
            }
            const $formulaBlock = $(
                '<div class="o_quoter_chain_popup_formula mb-2"></div>'
            );
            $formulaBlock.append(
                buildFormulaLineEditorHtml(data.expression || {})
            );
            $formulaBlock.append(
                '<p class="text-muted small mt-2 mb-0 o_quoter_chain_popup_formula_meta">' +
                    escapeHtml(
                        _t("Delta tabla: %s · Empleados vista previa: %s").replace(
                            "%s",
                            String(data.delta)
                        ).replace(
                            "%s",
                            String(data.employee_count)
                        )
                    ) +
                    "<br/>" +
                    escapeHtml(
                        _t("Base fijo: %s · Resultado: %s")
                            .replace("%s", formatNum(data.parent_value))
                            .replace("%s", formatNum(data.computed_preview))
                    ) +
                    (data.complexity_increase_percent
                        ? "<br/>" +
                          escapeHtml(
                              _t("Aumento complejidad: %s%.").replace(
                                  "%s",
                                  String(data.complexity_increase_percent)
                              )
                          )
                        : "") +
                    "</p>"
            );
            $content.append($formulaBlock);
            bindChainFormulaPopupTab($formulaBlock);

            function isFormulaMode() {
                return (
                    canFormula &&
                    $content.find('input[name="ck"]:checked').val() === "formula"
                );
            }

            function togglePopup() {
                const fixedOnly = !canFormula;
                const fixed =
                    fixedOnly ||
                    $content.find('input[name="ck"]:checked').val() === "fixed";
                $content.find(".o_quoter_chain_popup_fixed").toggle(fixed);
                $content.find(".o_quoter_chain_popup_formula").toggle(!fixed);
            }
            $content.on("change", 'input[name="ck"]', togglePopup);
            togglePopup();

            const dialogTitle = canFormula && !isFixed
                ? _t("Fórmula") + " — " + (data.role_name || "")
                : _t("Celda") + " — " + (data.role_name || "");

            const dialog = new Dialog(controller, {
                title: dialogTitle,
                size: "medium",
                buttons: [
                    {
                        text: _t("Guardar"),
                        classes: "btn-primary",
                        close: false,
                        click: function () {
                            const kind = !canFormula
                                ? "fixed"
                                : $content.find('input[name="ck"]:checked').val();
                            if (kind === "formula") {
                                const check = validateChainPopupParamValues(
                                    $formulaBlock
                                );
                                if (!check.ok) {
                                    showChainFormulaError(controller, check.message);
                                    return;
                                }
                            }
                            const fixedRaw = parseChainFormulaParamNumber(
                                $content
                                    .find(".o_quoter_chain_popup_fixed_val")
                                    .val()
                            );
                            rpc.query({
                                model: "quoter.professional.area",
                                method: "save_chain_line_edit",
                                args: [[parseInt(areaId, 10)]],
                                kwargs: {
                                    line_id: parseInt(chainLineId, 10),
                                    value_kind: kind,
                                    fixed_value:
                                        fixedRaw == null || Number.isNaN(fixedRaw)
                                            ? 0
                                            : fixedRaw,
                                    param_values: collectPopupParamValues(
                                        $formulaBlock
                                    ),
                                },
                            })
                                .then(function () {
                                    dialog.close();
                                    onReload();
                                })
                                .guardedCatch(function (err) {
                                    const msg =
                                        (err && err.data && err.data.message) ||
                                        (err && err.message) ||
                                        _t("No se pudo guardar la celda.");
                                    showChainFormulaError(controller, msg);
                                });
                        },
                    },
                    {text: _t("Descartar"), close: true},
                ],
                $content: $content,
            });
            dialog.open();
            if (isFormulaMode()) {
                const $first = $formulaBlock.find(".o_quoter_formula_param_input").first();
                if ($first.length) {
                    $first.focus().select();
                }
            }
        });
    }

    function bindAreaChainMatrix($root, areaId, controller) {
        const $wrap = $root.find(".o_quoter_chain_matrix_wrap");
        if (!$wrap.length) {
            return;
        }
        const activeTableId = $wrap.data("activeTableId");

        function reload(activeId) {
            return reloadAreaChain($root, areaId, activeId || activeTableId, controller);
        }

        $wrap.off("click.quoterChain change.quoterChain");
        $wrap.on("click.quoterChain", ".o_quoter_chain_tab", function (ev) {
            ev.preventDefault();
            reload(parseInt($(ev.currentTarget).data("table-id"), 10));
        });
        $wrap.on("click.quoterChain", ".o_quoter_chain_prev", function () {
            const data = $wrap.data("chainPayload");
            const tables = (data && data.tables) || [];
            const idx = tables.findIndex(function (t) {
                return chainTableIdEq(t.id, data.active_table_id);
            });
            if (idx > 0) {
                reload(tables[idx - 1].id);
            }
        });
        $wrap.on("click.quoterChain", ".o_quoter_chain_next", function () {
            const data = $wrap.data("chainPayload");
            const tables = (data && data.tables) || [];
            const idx = tables.findIndex(function (t) {
                return chainTableIdEq(t.id, data.active_table_id);
            });
            if (idx >= 0 && idx < tables.length - 1) {
                reload(tables[idx + 1].id);
            }
        });
        $wrap.on("click.quoterChain", ".o_quoter_chain_btn_new", function () {
            const $btn = $(this);
            $btn.prop("disabled", true);
            rpc
                .query({
                    model: "quoter.professional.area",
                    method: "action_chain_create_table",
                    args: [[areaId]],
                })
                .then(function (data) {
                    const newId = data && data.active_table_id;
                    if (newId) {
                        return reloadAreaChain($root, areaId, newId, controller);
                    }
                    mountChainMatrix($root, data, areaId, controller);
                })
                .guardedCatch(function () {})
                .then(function () {
                    $btn.prop("disabled", false);
                });
        });
        $wrap.on("click.quoterChain", ".o_quoter_chain_btn_delete", function () {
            if (!activeTableId) {
                return;
            }
            Dialog.confirm(controller, _t("¿Eliminar esta tabla?"), {
                confirm_callback: function () {
                    rpc.query({
                        model: "quoter.professional.area",
                        method: "action_chain_delete_table",
                        args: [[areaId]],
                        kwargs: {table_id: activeTableId},
                    }).then(function (data) {
                        mountChainMatrix($root, data, areaId, controller);
                    });
                },
            });
        });
        $wrap.on("change.quoterChain", ".o_quoter_chain_people_max_input", function (ev) {
            rpc.query({
                model: "quoter.professional.area",
                method: "chain_matrix_write_cell",
                args: [[areaId], false, "people_max", $(ev.currentTarget).val()],
                kwargs: {active_table_id: activeTableId},
            }).then(function (data) {
                mountChainMatrix($root, data, areaId, controller);
            });
        });
        $wrap.on("change.quoterChain", ".o_quoter_chain_delta_input", function (ev) {
            rpc.query({
                model: "quoter.professional.area",
                method: "chain_matrix_write_cell",
                args: [[areaId], false, "delta", $(ev.currentTarget).val()],
                kwargs: {active_table_id: activeTableId},
            }).then(function (data) {
                mountChainMatrix($root, data, areaId, controller);
            });
        });
        $wrap.on("change.quoterChain", ".o_quoter_chain_test_employees", function (ev) {
            rpc.query({
                model: "quoter.professional.area",
                method: "chain_matrix_set_test_employees",
                args: [[areaId], $(ev.currentTarget).val()],
            }).then(function (data) {
                mountChainMatrix($root, data, areaId, controller);
            });
        });
        $wrap.on("change.quoterChain", ".o_quoter_chain_test_complexity", function (ev) {
            rpc.query({
                model: "quoter.professional.area",
                method: "chain_matrix_set_test_complexity_level",
                args: [[areaId], $(ev.currentTarget).val() || false],
            }).then(function (data) {
                mountChainMatrix($root, data, areaId, controller);
            });
        });
        $wrap.on("click.quoterChain", ".o_quoter_chain_edit_btn", function (ev) {
            ev.preventDefault();
            openChainCellEditor(
                controller,
                areaId,
                $(ev.currentTarget).data("chain-line-id"),
                function () {
                    reload(activeTableId);
                }
            );
        });
        $wrap.on("dblclick.quoterChain", ".o_quoter_chain_role_col", function (ev) {
            const $btn = $(ev.currentTarget).find(".o_quoter_chain_edit_btn");
            if ($btn.length) {
                $btn.trigger("click");
            }
        });
    }

    function renderAreaChainMatrix(renderer) {
        if (!renderer || renderer.state.model !== "quoter.professional.area") {
            return;
        }
        const $roots = $(renderer.el).find(".o_quoter_chain_area_matrix_root");
        if (!$roots.length) {
            return;
        }
        const resId = getFormDatabaseId(renderer);
        const controller = getFormController(renderer);
        if (!resId) {
            $roots.html(
                '<p class="text-muted">' +
                    escapeHtml(_t("Guarde el área para configurar tablas en cadena.")) +
                    "</p>"
            );
            return;
        }
        $roots.each(function () {
            const $r = $(this);
            reloadAreaChain($r, resId, getPersistedActiveTableId($r), controller);
        });
    }

    function safeRender(renderer) {
        try {
            renderAreaChainMatrix(renderer);
        } catch (e) {
            if (window.console && console.error) {
                console.error("[quoter.chain_matrix]", e);
            }
        }
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

    FormController.include({
        saveRecord: function () {
            const res = this._super.apply(this, arguments);
            if (this.modelName === "quoter.professional.area") {
                const self = this;
                return chainPromiseResult(res, function () {
                    if (self.renderer) {
                        safeRender(self.renderer);
                    }
                });
            }
            return res;
        },
    });
});

odoo.define("quoter.area_hours_matrix", function (require) {
    "use strict";

    const core = require("web.core");
    const FormRenderer = require("web.FormRenderer");
    const rpc = require("web.rpc");

    const _t = core._t;

    // Misma paleta que $o-colors en Odoo 15 (addons/web/.../secondary_variables.scss).
    // Índice 7 = #2C8397 (teal/celeste); el verde de etiquetas Odoo es índice 10 = #30C381.
    const TAG_COLOR_HEX = [
        "#777777",
        "#F06050",
        "#F4A460",
        "#F7CD1F",
        "#6CC1ED",
        "#814968",
        "#EB7E7F",
        "#2C8397",
        "#475577",
        "#D6145F",
        "#30C381",
        "#9365B8",
    ];

    function tagColorHex(colorIndex) {
        const i = Math.abs(parseInt(colorIndex, 10) || 0) % TAG_COLOR_HEX.length;
        return TAG_COLOR_HEX[i];
    }

    function hexToRgb(hex) {
        const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        if (!m) {
            return null;
        }
        return {
            r: parseInt(m[1], 16),
            g: parseInt(m[2], 16),
            b: parseInt(m[3], 16),
        };
    }

    /** Texto claro u oscuro según luminancia (p. ej. amarillo → texto oscuro). */
    function contrastTextForBackground(hex) {
        const rgb = hexToRgb(hex);
        if (!rgb) {
            return "#ffffff";
        }
        const yiq = (rgb.r * 299 + rgb.g * 587 + rgb.b * 114) / 1000;
        return yiq >= 165 ? "#212529" : "#ffffff";
    }

    /** Primera letra mayúscula, el resto minúsculas (toda la cadena). */
    function sentenceCase(s) {
        if (s === null || s === undefined) {
            return "";
        }
        const t = String(s).trim();
        if (!t) {
            return "";
        }
        return t.charAt(0).toUpperCase() + t.slice(1).toLowerCase();
    }

    function escapeHtml(s) {
        if (s === null || s === undefined) {
            return "";
        }
        return String(s)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function escapeAttr(s) {
        return String(s).replace(/"/g, "&quot;");
    }

    function formatNum(n) {
        if (n === null || n === undefined || n === "") {
            return "0";
        }
        const x = Number(n);
        if (Number.isNaN(x)) {
            return String(n);
        }
        return x.toLocaleString(undefined, {
            minimumFractionDigits: 0,
            maximumFractionDigits: 2,
        });
    }

    function colgroupHtml(numDataCols) {
        if (numDataCols < 1) {
            return "";
        }
        const namePct = 18;
        const rest = 100 - namePct;
        const w = rest / numDataCols;
        let html =
            '<colgroup><col class="o_quoter_matrix_col_handle" style="width:32px;min-width:32px;max-width:32px"/>';
        html += '<col style="width:' + namePct + '%"/>';
        for (let i = 0; i < numDataCols; i++) {
            html += '<col style="width:' + w + '%"/>';
        }
        html += "</colgroup>";
        return html;
    }

    /**
     * @param {boolean} includeRangeRow - Si es false (tabla A unificada/compact), solo 2 filas de cabecera.
     *   Si es true, tercera fila con el nombre de cada rango (AE, SR, …) bajo cada nivel.
     */
    function theadHtml(levels, ranges, labels, totalDataCols, includeRangeRow) {
        const R = ranges.length;
        const complexityLabel = sentenceCase(labels.complexity || "");
        const rs = includeRangeRow ? 3 : 2;
        let html = "<thead>";
        html += "<tr>";
        html +=
            '<th rowspan="' +
            rs +
            '" class="o_handle_cell o_quoter_matrix_handle_cell align-middle"></th>';
        html +=
            '<th rowspan="' +
            rs +
            '" class="align-middle o_quoter_matrix_th_line o_list_char">&nbsp;</th>';
        html +=
            '<th colspan="' +
            totalDataCols +
            '" class="text-center font-weight-bold o_quoter_matrix_th_group">' +
            escapeHtml(complexityLabel) +
            "</th>";
        html += "</tr><tr>";
        levels.forEach(function (lev) {
            const bg = tagColorHex(lev.color);
            const fg = contrastTextForBackground(bg);
            html +=
                '<th colspan="' +
                R +
                '" class="o_quoter_matrix_level_head text-center align-middle">' +
                '<span class="o_quoter_matrix_level_pill" style="background-color:' +
                escapeAttr(bg) +
                ";color:" +
                escapeAttr(fg) +
                ';">' +
                escapeHtml(lev.name != null ? String(lev.name) : "") +
                "</span></th>";
        });
        html += "</tr>";
        if (includeRangeRow) {
            html += "<tr>";
            levels.forEach(function (lev, li) {
                ranges.forEach(function (r, ri) {
                    let cls =
                        "o_quoter_matrix_th_range text-center align-middle font-weight-bold o_list_char";
                    if (li > 0 && ri === 0) {
                        cls += " o_quoter_matrix_th_range_level_start";
                    }
                    if (ri < R - 1) {
                        cls += " o_quoter_matrix_th_range_sep_after";
                    }
                    html += "<th class=\"" + cls + "\">" + escapeHtml(sentenceCase(r.name || "")) + "</th>";
                });
            });
            html += "</tr>";
        }
        html += "</thead>";
        return html;
    }

    function tdHandle() {
        return (
            '<td class="o_handle_cell o_quoter_matrix_handle_cell text-center align-middle">' +
            '<span class="o_row_handle fa fa-sort text-muted" role="presentation"></span>' +
            "</td>"
        );
    }

    function tdCell(align, content, extraTdClass) {
        const a = align || "center";
        let cls = "o_quoter_matrix_cell";
        if (extraTdClass) {
            cls += " " + extraTdClass;
        }
        if (a === "left") {
            cls += " o_list_char";
        } else if (a === "number") {
            cls += " o_list_number o_quoter_matrix_num_cell";
        } else {
            cls += " text-center";
        }
        return '<td class="' + cls + '">' + content + "</td>";
    }

    function cellInput(writeKind, levelRangeId, areaRangeId, value, extraClass) {
        return (
            '<input type="number" step="any" class="q-matrix-cell o_quoter_matrix_num_input o_list_number ' +
            (extraClass || "") +
            '" style="width:100%;min-width:0;padding:0 2px;height:auto;text-align:right;line-height:inherit;"' +
            ' data-write-kind="' +
            escapeAttr(writeKind) +
            '" data-level-range-id="' +
            escapeAttr(levelRangeId) +
            '" data-area-range-id="' +
            escapeAttr(areaRangeId) +
            '" value="' +
            escapeAttr(value) +
            '"/>'
        );
    }

    function tbodyOutput(
        rows,
        levels,
        ranges,
        rangeIds,
        emptyMessage,
        readOnly,
        combined
    ) {
        const R = ranges.length;
        let html = "<tbody>";
        if (!rows.length) {
            html +=
                '<tr><td colspan="' +
                (2 + levels.length * R) +
                '" class="o_quoter_matrix_cell o_list_char text-muted">' +
                escapeHtml(sentenceCase(emptyMessage || "")) +
                "</td></tr>";
        } else {
            rows.forEach(function (row) {
                html += "<tr>";
                html += tdHandle();
                html += tdCell("left", escapeHtml(sentenceCase(row.line_name || "")), "o_quoter_matrix_line_cell");
                const lh = row.levels_hours || [];
                const metaList = row.levels_meta || [];
                levels.forEach(function (lev, li) {
                    const cells = lh[li] || [];
                    const meta = metaList[li] || {};
                    const lrId = meta.level_range_id || 0;
                    const outIds = meta.output_ids || [];
                    ranges.forEach(function (r, ri) {
                        const v = cells[ri] != null ? cells[ri] : 0;
                        const arId = rangeIds[ri] || 0;
                        const oid = outIds[ri] || 0;
                        const canEdit = !readOnly && !combined && lrId && oid;
                        let inner;
                        if (canEdit) {
                            inner = cellInput("output", lrId, arId, v);
                        } else {
                            inner = escapeHtml(formatNum(v));
                        }
                        html += tdCell("number", inner);
                    });
                });
                html += "</tr>";
            });
        }
        html += "</tbody>";
        return html;
    }

    function tbodyMatrixA(
        rows,
        levels,
        ranges,
        rangeIds,
        compactA,
        emptyMessage,
        readOnly,
        combined
    ) {
        const R = ranges.length;
        const firstAr = rangeIds[0] || 0;
        let html = "<tbody>";
        if (!rows.length) {
            html +=
                '<tr><td colspan="' +
                (2 + levels.length * R) +
                '" class="o_quoter_matrix_cell o_list_char text-muted">' +
                escapeHtml(sentenceCase(emptyMessage || "")) +
                "</td></tr>";
        } else {
            rows.forEach(function (row) {
                html += "<tr>";
                html += tdHandle();
                html += tdCell("left", escapeHtml(sentenceCase(row.line_name || "")), "o_quoter_matrix_line_cell");
                const la = row.levels_matrix_a || [];
                const metaList = row.levels_meta || [];
                levels.forEach(function (lev, li) {
                    const cells = la[li] || [];
                    const meta = metaList[li] || {};
                    const lrId = meta.level_range_id || 0;
                    const aIds = meta.matrix_a_ids || [];
                    if (compactA) {
                        const v = cells[0] != null ? cells[0] : 0;
                        const hasA = aIds.some(function (id) {
                            return id > 0;
                        });
                        const canEdit =
                            !readOnly &&
                            combined &&
                            lrId &&
                            hasA;
                        let inner;
                        if (canEdit) {
                            inner = cellInput("matrix_a_compact", lrId, firstAr, v);
                        } else {
                            inner = escapeHtml(formatNum(v));
                        }
                        html +=
                            '<td colspan="' +
                            R +
                            '" class="o_quoter_matrix_cell o_quoter_matrix_num_cell o_list_number text-right">' +
                            inner +
                            "</td>";
                    } else {
                        ranges.forEach(function (r, ri) {
                            const v = cells[ri] != null ? cells[ri] : 0;
                            const arId = rangeIds[ri] || 0;
                            const aid = aIds[ri] || 0;
                            const canEdit = !readOnly && combined && lrId && aid;
                            let inner;
                            if (canEdit) {
                                inner = cellInput("matrix_a", lrId, arId, v);
                            } else {
                                inner = escapeHtml(formatNum(v));
                            }
                            html += tdCell("number", inner);
                        });
                    }
                });
                html += "</tr>";
            });
        }
        html += "</tbody>";
        return html;
    }

    function tbodyMatrixB(
        rows,
        levels,
        ranges,
        rangeIds,
        emptyMessage,
        readOnly,
        combined
    ) {
        const R = ranges.length;
        let html = "<tbody>";
        if (!rows.length) {
            html +=
                '<tr><td colspan="' +
                (2 + levels.length * R) +
                '" class="o_quoter_matrix_cell o_list_char text-muted">' +
                escapeHtml(sentenceCase(emptyMessage || "")) +
                "</td></tr>";
        } else {
            rows.forEach(function (row) {
                html += "<tr>";
                html += tdHandle();
                html += tdCell("left", escapeHtml(sentenceCase(row.line_name || "")), "o_quoter_matrix_line_cell");
                const lb = row.levels_matrix_b || [];
                const metaList = row.levels_meta || [];
                levels.forEach(function (lev, li) {
                    const cells = lb[li] || [];
                    const meta = metaList[li] || {};
                    const lrId = meta.level_range_id || 0;
                    const bIds = meta.matrix_b_ids || [];
                    ranges.forEach(function (r, ri) {
                        const v = cells[ri] != null ? cells[ri] : 0;
                        const arId = rangeIds[ri] || 0;
                        const bid = bIds[ri] || 0;
                        const canEdit = !readOnly && combined && lrId && bid;
                        let inner;
                        if (canEdit) {
                            inner = cellInput("matrix_b", lrId, arId, v);
                        } else {
                            inner = escapeHtml(formatNum(v));
                        }
                        html += tdCell("number", inner);
                    });
                });
                html += "</tr>";
            });
        }
        html += "</tbody>";
        return html;
    }

    function oneTable(title, colgroup, thead, tbody) {
        return (
            '<div class="quoter-area-matrix-block mb-3">' +
            '<div class="o_horizontal_separator">' +
            escapeHtml(title) +
            "</div>" +
            '<div class="o_list_view o_quoter_matrix_list">' +
            '<div class="table-responsive o_quoter_matrix_table_responsive">' +
            '<table class="o_list_table table table-sm table-hover table-striped o_quoter_area_hours_matrix" style="table-layout:fixed;width:100%;">' +
            colgroup +
            thead +
            tbody +
            "</table>" +
            '<div class="o_quoter_matrix_table_bottom_bar" role="presentation"></div>' +
            "</div></div></div>"
        );
    }

    function buildMatrixHtml(data) {
        if (!data) {
            return "";
        }
        const labels = data.labels || {};
        const ranges = data.ranges || [];
        const levels = data.levels || [];
        const rows = data.rows || [];
        const rangeIds = data.range_ids || [];
        const totalDataCols = levels.length * ranges.length;
        const compactA = data.table_a_layout === "compact";
        const showAB = !!data.show_matrix_ab;
        const readOnly = !!data.matrix_read_only;
        const combined = showAB;

        if (!totalDataCols) {
            return (
                '<p class="text-muted">' +
                escapeHtml(sentenceCase(data.empty_message || "")) +
                "</p>"
            );
        }

        const cg = colgroupHtml(totalDataCols);
        const thOutput = theadHtml(levels, ranges, labels, totalDataCols, true);
        const thMatrixA = theadHtml(levels, ranges, labels, totalDataCols, !compactA);
        const thMatrixB = theadHtml(levels, ranges, labels, totalDataCols, true);

        let out = "";
        if (labels.matrix_edit_hint) {
            out +=
                '<p class="text-warning small mb-2">' +
                escapeHtml(sentenceCase(labels.matrix_edit_hint)) +
                "</p>";
        }
        out +=
            '<div class="quoter-area-matrix-caption text-muted small mb-2">' +
            escapeHtml(sentenceCase(labels.mode || "")) +
            "</div>";

        out += oneTable(
            sentenceCase(labels.output_title || _t("Salida (horas resultado)")),
            cg,
            thOutput,
            tbodyOutput(rows, levels, ranges, rangeIds, data.empty_message, readOnly, combined)
        );

        if (showAB) {
            out += oneTable(
                sentenceCase(labels.matrix_a_title || _t("Tabla A (horas base)")),
                cg,
                thMatrixA,
                tbodyMatrixA(
                    rows,
                    levels,
                    ranges,
                    rangeIds,
                    compactA,
                    data.empty_message,
                    readOnly,
                    combined
                )
            );
            out += oneTable(
                sentenceCase(labels.matrix_b_title || _t("Tabla B")),
                cg,
                thMatrixB,
                tbodyMatrixB(
                    rows,
                    levels,
                    ranges,
                    rangeIds,
                    data.empty_message,
                    readOnly,
                    combined
                )
            );
        }

        return out;
    }

    function pickErrorText(v) {
        if (v == null || v === undefined) {
            return "";
        }
        if (typeof v === "string") {
            return v;
        }
        if (typeof v === "number") {
            return String(v);
        }
        if (Array.isArray(v)) {
            return v
                .map(pickErrorText)
                .filter(Boolean)
                .join(" ");
        }
        if (typeof v === "object") {
            if (v.arguments && v.arguments.length) {
                return pickErrorText(v.arguments);
            }
            if (v.message) {
                const m = pickErrorText(v.message);
                if (m) {
                    return m;
                }
            }
            if (v.data) {
                const inner = pickErrorText(v.data);
                if (inner) {
                    return inner;
                }
            }
        }
        return "";
    }

    function matrixRpcErrorMessage(err) {
        if (!err) {
            return _t("Error al guardar.");
        }
        const d = err.data || {};
        let msg = pickErrorText(d.arguments && d.arguments.length ? d.arguments : d.message);
        if (!msg) {
            msg = pickErrorText(err.message);
        }
        if (!msg || msg === "Odoo Server Error") {
            msg = pickErrorText(err);
        }
        if (!msg) {
            try {
                msg = JSON.stringify(err);
            } catch (e) {
                msg = _t("Error al guardar.");
            }
        }
        return msg;
    }

    function bindMatrixRowEditUi($roots) {
        $roots
            .off("focusin.quoterMatrixRow focusout.quoterMatrixRow", "input.q-matrix-cell")
            .on("focusin.quoterMatrixRow", "input.q-matrix-cell", function () {
                const $td = $(this).closest("td");
                const $tr = $(this).closest("tr");
                $roots.find("td.o_quoter_matrix_cell_focus").removeClass("o_quoter_matrix_cell_focus");
                $tr.addClass("o_quoter_matrix_row_editing");
                $td.addClass("o_quoter_matrix_cell_focus");
            })
            .on("focusout.quoterMatrixRow", "input.q-matrix-cell", function () {
                const $tr = $(this).closest("tr");
                window.setTimeout(function () {
                    if ($tr.find("input.q-matrix-cell:focus").length) {
                        return;
                    }
                    $tr.removeClass("o_quoter_matrix_row_editing");
                    $tr.find("td.o_quoter_matrix_cell_focus").removeClass("o_quoter_matrix_cell_focus");
                }, 0);
            });
    }

    function bindMatrixSave($roots, areaId) {
        bindMatrixRowEditUi($roots);
        $roots
            .off("change.quoterMatrix", "input.q-matrix-cell")
            .on("change.quoterMatrix", "input.q-matrix-cell", function (ev) {
                const $inp = $(ev.target);
                const kind = $inp.data("writeKind");
                const lrId = $inp.data("levelRangeId");
                const arId = $inp.data("areaRangeId");
                if (!kind || !lrId || !arId) {
                    return;
                }
                const raw = $inp.val();
                let num = parseFloat(String(raw).replace(",", "."));
                if (Number.isNaN(num)) {
                    num = 0;
                }
                const $cells = $roots.find("input.q-matrix-cell");
                $cells.prop("disabled", true);
                const q1 = rpc.query({
                    model: "quoter.professional.area",
                    method: "matrix_preview_write_cell",
                    args: [[areaId], lrId, arId, kind, num],
                });
                const done = q1.then(function () {
                    return rpc.query({
                        model: "quoter.professional.area",
                        method: "get_hours_matrix_preview_data",
                        args: [[areaId]],
                    });
                });
                function onErr(err) {
                    $roots.find(".o_quoter_matrix_err").remove();
                    const msg = matrixRpcErrorMessage(err);
                    $roots.prepend(
                        '<div class="alert alert-danger alert-dismissible fade show o_quoter_matrix_err" role="alert">' +
                            escapeHtml(msg) +
                            '<button type="button" class="close" data-dismiss="alert" aria-label="Close">' +
                            '<span aria-hidden="true">&times;</span></button></div>'
                    );
                }
                function enableCells() {
                    $roots.find("input.q-matrix-cell").prop("disabled", false);
                }
                if (done && typeof done.then === "function") {
                    let tail = done.then(function (fresh) {
                        $roots.html(buildMatrixHtml(fresh));
                        bindMatrixSave($roots, areaId);
                    });
                    if (typeof tail.catch === "function") {
                        tail = tail.catch(onErr);
                    } else if (typeof tail.fail === "function") {
                        tail = tail.fail(onErr);
                    } else {
                        tail = tail.then(null, onErr);
                    }
                    if (tail && typeof tail.finally === "function") {
                        tail.finally(enableCells);
                    } else if (tail && typeof tail.always === "function") {
                        tail.always(enableCells);
                    } else if (tail && typeof tail.then === "function") {
                        tail.then(enableCells, enableCells);
                    } else {
                        enableCells();
                    }
                }
            });
    }

    function getFormDatabaseId(renderer) {
        const st = renderer.state || {};
        let rid = st.res_id;
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

    function renderAreaMatrix(renderer) {
        if (!renderer || !renderer.state || renderer.state.model !== "quoter.professional.area") {
            return;
        }
        const $roots = $(renderer.el).find(".o_quoter_area_hours_matrix_root");
        if (!$roots.length) {
            return;
        }
        const resId = getFormDatabaseId(renderer);
        if (!resId) {
            $roots.each(function () {
                $(this).html(
                    '<p class="text-muted">' + escapeHtml(_t("Guarde el área para generar la matriz.")) + "</p>"
                );
            });
            return;
        }
        $roots.each(function () {
            $(this).html(
                '<div class="text-center text-muted py-2"><i class="fa fa-spinner fa-spin"></i> ' +
                    escapeHtml(_t("Cargando…")) +
                    "</div>"
            );
        });
        const rpcDef = rpc.query({
            model: "quoter.professional.area",
            method: "get_hours_matrix_preview_data",
            args: [[resId]],
        });
        const onOk = function (result) {
            const aid = (result && result.area_id) || resId;
            $roots.html(buildMatrixHtml(result));
            bindMatrixSave($roots, aid);
        };
        const onFail = function () {
            $roots.html(
                '<p class="text-danger">' + escapeHtml(_t("No se pudo cargar la matriz.")) + "</p>"
            );
        };
        if (rpcDef && typeof rpcDef.then === "function") {
            if (typeof rpcDef.catch === "function") {
                rpcDef.then(onOk).catch(onFail);
            } else if (typeof rpcDef.fail === "function") {
                rpcDef.then(onOk).fail(onFail);
            } else {
                rpcDef.then(onOk, onFail);
            }
        }
    }

    FormRenderer.include({
        _renderView: function () {
            const res = this._super.apply(this, arguments);
            const self = this;
            function safeMatrix() {
                try {
                    renderAreaMatrix(self);
                } catch (e) {
                    if (window.console && console.error) {
                        console.error("[quoter.area_hours_matrix]", e);
                    }
                }
            }
            if (res && typeof res.then === "function") {
                return res.then(function () {
                    safeMatrix();
                });
            }
            safeMatrix();
            return res;
        },
    });
});

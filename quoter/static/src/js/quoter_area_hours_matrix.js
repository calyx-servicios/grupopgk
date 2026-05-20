odoo.define("quoter.area_hours_matrix", function (require) {
    "use strict";

    const QUOTER_DISABLE_AREA_HOURS_MATRIX = false;
    if (QUOTER_DISABLE_AREA_HOURS_MATRIX) {
        return;
    }

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
    function theadHtml(levels, ranges, labels, totalDataCols, includeRangeRow, hideLevelBranchRows, showBranchRow) {
        const R = ranges.length;
        const complexityLabel = sentenceCase(labels.complexity || "");
        const branchRowEnabled =
            !!showBranchRow &&
            levels.some(function (lev) {
                return !!String((lev && lev.branch_name) || "").trim();
            });
        const showRows = !hideLevelBranchRows;
        const rs = showRows
            ? (includeRangeRow ? 3 : 2) + (branchRowEnabled ? 1 : 0)
            : includeRangeRow
            ? 2
            : 1;
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
        html += "</tr>";
        if (showRows && branchRowEnabled) {
            html += "<tr>";
            let li = 0;
            while (li < levels.length) {
                const current = levels[li] || {};
                const bname = String((current.branch_name || "").trim());
                let spanLevels = 1;
                let lj = li + 1;
                while (lj < levels.length) {
                    const next = levels[lj] || {};
                    if (String((next.branch_name || "").trim()) !== bname) {
                        break;
                    }
                    spanLevels++;
                    lj++;
                }
                html +=
                    '<th colspan="' +
                    spanLevels * R +
                    '" class="o_quoter_matrix_branch_head text-center align-middle font-weight-bold o_list_char">' +
                    escapeHtml(sentenceCase(bname)) +
                    "</th>";
                li += spanLevels;
            }
            html += "</tr>";
        }
        if (showRows) {
            html += "<tr>";
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
        }
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

    /**
     * Cabecera Tabla B compacta: mismas filas rama / nivel / rol que el resto, pero solo el ancho
     * de columnas necesario (roles uniformes en una columna; roles variables expandidos).
     */
    function theadHtmlMatrixBCompact(columns, labels, showBranchRow) {
        const cols = columns || [];
        const C = cols.length;
        if (!C) {
            return "";
        }
        const complexityLabel = sentenceCase(labels.complexity || "");
        const showLevelRow = cols.some(function (c) {
            return c.expand === "level" || c.expand === "branch_level";
        });
        const branchRowEnabled =
            !!showBranchRow &&
            cols.some(function (c) {
                return !!String((c && c.branch_name) || "").trim();
            });
        const innerRows = (branchRowEnabled ? 1 : 0) + (showLevelRow ? 1 : 0) + 1;
        const rs = 1 + innerRows;
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
            C +
            '" class="text-center font-weight-bold o_quoter_matrix_th_group">' +
            escapeHtml(complexityLabel) +
            "</th>";
        html += "</tr>";

        function thSingleRole(col) {
            return (
                '<th rowspan="' +
                innerRows +
                '" class="o_quoter_matrix_th_range text-center align-middle font-weight-bold o_list_char">' +
                escapeHtml(sentenceCase((col && col.role_name) || "")) +
                "</th>"
            );
        }

        if (branchRowEnabled) {
            html += "<tr>";
            let ci = 0;
            while (ci < C) {
                const col = cols[ci];
                if (!col.expand || col.expand === "none") {
                    html += thSingleRole(col);
                    ci++;
                    continue;
                }
                const bname = String((col.branch_name || "").trim());
                let span = 1;
                let cj = ci + 1;
                while (cj < C) {
                    const c2 = cols[cj];
                    if (!c2.expand || c2.expand === "none") {
                        break;
                    }
                    if (String((c2.branch_name || "").trim()) !== bname) {
                        break;
                    }
                    span++;
                    cj++;
                }
                html +=
                    '<th colspan="' +
                    span +
                    '" class="o_quoter_matrix_branch_head text-center align-middle font-weight-bold o_list_char">' +
                    escapeHtml(sentenceCase(bname)) +
                    "</th>";
                ci += span;
            }
            html += "</tr>";
        }

        if (showLevelRow) {
            html += "<tr>";
            cols.forEach(function (col) {
                if (!col.expand || col.expand === "none") {
                    if (!branchRowEnabled) {
                        html +=
                            '<th rowspan="2" class="o_quoter_matrix_th_range text-center align-middle font-weight-bold o_list_char">' +
                            escapeHtml(sentenceCase((col && col.role_name) || "")) +
                            "</th>";
                    }
                    return;
                }
                const bg = tagColorHex(col.level_color || 0);
                const fg = contrastTextForBackground(bg);
                const ln = col.level_name != null ? String(col.level_name) : "";
                html +=
                    '<th class="o_quoter_matrix_level_head text-center align-middle">' +
                    '<span class="o_quoter_matrix_level_pill" style="background-color:' +
                    escapeAttr(bg) +
                    ";color:" +
                    escapeAttr(fg) +
                    ';">' +
                    escapeHtml(ln) +
                    "</span></th>";
            });
            html += "</tr>";
        }

        html += "<tr>";
        cols.forEach(function (col) {
            if (!col.expand || col.expand === "none") {
                if (!showLevelRow && !showBranchRow) {
                    html += thSingleRole(col);
                }
                return;
            }
            const nm = col.role_name != null ? String(col.role_name) : "";
            html +=
                '<th class="o_quoter_matrix_th_range text-center align-middle font-weight-bold o_list_char">' +
                escapeHtml(sentenceCase(nm)) +
                "</th>";
        });
        html += "</tr>";
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
        globalA,
        emptyMessage,
        readOnly,
        combined
    ) {
        const R = ranges.length;
        const totalDataCols = levels.length * R;
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
                if (globalA) {
                    const v = row.global_matrix_a_value != null ? row.global_matrix_a_value : 0;
                    const lrId = row.global_matrix_a_level_range_id || 0;
                    const canEdit = !readOnly && combined && lrId;
                    let inner;
                    if (canEdit) {
                        inner = cellInput("matrix_a_global", lrId, firstAr, v);
                    } else {
                        inner = escapeHtml(formatNum(v));
                    }
                    html +=
                        '<td colspan="' +
                        totalDataCols +
                        '" class="o_quoter_matrix_cell o_quoter_matrix_num_cell o_list_number text-right">' +
                        inner +
                        "</td>";
                    html += "</tr>";
                    return;
                }
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
                    const lrIdsPerCol = meta.matrix_b_level_range_ids || [];
                    const bIds = meta.matrix_b_ids || [];
                    ranges.forEach(function (r, ri) {
                        const v = cells[ri] != null ? cells[ri] : 0;
                        const arId = rangeIds[ri] || 0;
                        const bid = bIds[ri] || 0;
                        const lrPerCol =
                            lrIdsPerCol.length > ri ? Number(lrIdsPerCol[ri]) || 0 : 0;
                        const lrId = lrPerCol || meta.level_range_id || 0;
                        const useSingleCellWrite = lrPerCol > 0;
                        const writeKind = useSingleCellWrite ? "matrix_b_single" : "matrix_b";
                        const canEdit = !readOnly && combined && lrId && bid;
                        let inner;
                        if (canEdit) {
                            inner = cellInput(writeKind, lrId, arId, v);
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

    function oneTable(title, colgroup, thead, tbody, optionsHtml, tableOpts) {
        const opts = tableOpts || {};
        const tableStyle = opts.tableStyle || "table-layout:fixed;width:100%;";
        const responsiveExtraCls = opts.responsiveClass || "";
        const responsiveClass = (
            "table-responsive o_quoter_matrix_table_responsive " + responsiveExtraCls
        ).trim();
        return (
            '<div class="quoter-area-matrix-block mb-3">' +
            '<div class="o_horizontal_separator">' +
            escapeHtml(title) +
            "</div>" +
            (optionsHtml || "") +
            '<div class="o_list_view o_quoter_matrix_list">' +
            '<div class="' +
            responsiveClass +
            '">' +
            '<table class="o_list_table table table-sm table-hover table-striped o_quoter_area_hours_matrix" style="' +
            escapeAttr(tableStyle) +
            '">' +
            colgroup +
            thead +
            tbody +
            "</table>" +
            '<div class="o_quoter_matrix_table_bottom_bar" role="presentation"></div>' +
            "</div></div></div>"
        );
    }

    function tableOptionsHtml(tableKey, opts, readOnly) {
        const unifyKey = "matrix_" + tableKey + "_unify_role_values";
        const hideKey = "matrix_" + tableKey + "_hide_repeated_columns";
        const unifyChecked = !!opts[unifyKey];
        const hideChecked = !!opts[hideKey];
        const disabledAttr = readOnly ? ' disabled="disabled"' : "";
        let html =
            '<div class="o_quoter_matrix_options text-muted small mb-1">' +
            '<label class="mr-3 mb-0">' +
            '<input type="checkbox" class="q-matrix-opt mr-1" data-option-name="' +
            escapeAttr(unifyKey) +
            '" ' +
            (unifyChecked ? 'checked="checked"' : "") +
            disabledAttr +
            "/>" +
            escapeHtml(_t("Unificar valores por rol")) +
            "</label>";
        if (unifyChecked) {
            html +=
                '<label class="mb-0">' +
                '<input type="checkbox" class="q-matrix-opt mr-1" data-option-name="' +
                escapeAttr(hideKey) +
                '" ' +
                (hideChecked ? 'checked="checked"' : "") +
                disabledAttr +
                "/>" +
                escapeHtml(_t("Ocultar columnas repetidas")) +
                "</label>";
        }
        html += "</div>";
        return html;
    }

    function reorderIndicesByBranchThenLevel(levels) {
        const orderedBranchIds = [];
        const orderedLevelIds = [];
        (levels || []).forEach(function (lev) {
            const bid = lev && lev.branch_id;
            const lid = lev && lev.level_id;
            if (bid && orderedBranchIds.indexOf(bid) === -1) {
                orderedBranchIds.push(bid);
            }
            if (lid && orderedLevelIds.indexOf(lid) === -1) {
                orderedLevelIds.push(lid);
            }
        });
        if (orderedBranchIds.length <= 1 || !orderedLevelIds.length) {
            return [];
        }
        const idxs = [];
        orderedBranchIds.forEach(function (bid) {
            orderedLevelIds.forEach(function (lid) {
                const idx = (levels || []).findIndex(function (lev) {
                    return lev && lev.branch_id === bid && lev.level_id === lid;
                });
                if (idx >= 0) {
                    idxs.push(idx);
                }
            });
        });
        return idxs.length === (levels || []).length ? idxs : [];
    }

    function reorderByIndices(arr, idxs) {
        if (!Array.isArray(arr) || !idxs || !idxs.length) {
            return arr;
        }
        return idxs.map(function (idx) {
            return arr[idx];
        });
    }

    function prepareABData(data) {
        const levels = data.levels || [];
        const idxs = reorderIndicesByBranchThenLevel(levels);
        if (!idxs.length) {
            return {
                levelsAB: levels,
                rowsAB: data.rows || [],
            };
        }
        const rowsAB = (data.rows || []).map(function (row) {
            return Object.assign({}, row, {
                levels_matrix_a: reorderByIndices(row.levels_matrix_a || [], idxs),
                levels_matrix_b: reorderByIndices(row.levels_matrix_b || [], idxs),
                levels_meta: reorderByIndices(row.levels_meta || [], idxs),
            });
        });
        return {
            levelsAB: reorderByIndices(levels, idxs),
            rowsAB: rowsAB,
        };
    }

    function collapseABForRepeatedRoles(rows, levels, ranges, sourceKey, idKey) {
        const R = (ranges || []).length;
        if (!R || !(levels || []).length) {
            return { levels: levels || [], rows: rows || [] };
        }
        const oneLevel = [
            {
                name: "",
                color: 0,
                branch_name: "",
                level_id: levels[0].level_id,
                branch_id: levels[0].branch_id,
            },
        ];
        const collapsedRows = (rows || []).map(function (row) {
            const src = row[sourceKey] || [];
            const meta = row.levels_meta || [];
            const values = [];
            const ids = [];
            let anchorLevelRangeId = 0;
            for (let ri = 0; ri < R; ri++) {
                let chosenValue = 0;
                let chosenId = 0;
                for (let li = 0; li < src.length; li++) {
                    const metaLine = meta[li] || {};
                    const idsLine = metaLine[idKey] || [];
                    if (idsLine[ri]) {
                        chosenId = idsLine[ri];
                        chosenValue =
                            src[li] && src[li][ri] != null ? src[li][ri] : 0;
                        if (!anchorLevelRangeId) {
                            anchorLevelRangeId = metaLine.level_range_id || 0;
                        }
                        break;
                    }
                }
                values.push(chosenValue);
                ids.push(chosenId);
            }
            if (!anchorLevelRangeId && meta.length) {
                anchorLevelRangeId = (meta[0] && meta[0].level_range_id) || 0;
            }
            const collapsedMeta = [
                {
                    level_range_id: anchorLevelRangeId,
                    output_ids: [],
                    matrix_a_ids: idKey === "matrix_a_ids" ? ids : [],
                    matrix_b_ids: idKey === "matrix_b_ids" ? ids : [],
                },
            ];
            const out = Object.assign({}, row);
            out[sourceKey] = [values];
            out.levels_meta = collapsedMeta;
            return out;
        });
        return {
            levels: oneLevel,
            rows: collapsedRows,
        };
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
        const compactA = data.table_a_layout === "compact";
        const globalA = data.table_a_layout === "global";
        const showAB = !!data.show_matrix_ab;
        const readOnly = !!data.matrix_read_only;
        const combined = showAB;
        const abPrepared = prepareABData(data);
        const levelsAB = abPrepared.levelsAB;
        const rowsAB = abPrepared.rowsAB;

        let levelsA = levelsAB;
        let rowsA = rowsAB;
        let levelsB = levelsAB;
        let rowsB = rowsAB;
        let rangesB = ranges;
        let rangeIdsB = rangeIds;
        let useCompactBThead = false;
        const hideA = !!data.matrix_a_hide_repeated_columns;
        const hideB = !!data.matrix_b_hide_repeated_columns;
        if (hideA && !globalA) {
            const cA = collapseABForRepeatedRoles(rowsAB, levelsAB, ranges, "levels_matrix_a", "matrix_a_ids");
            levelsA = cA.levels;
            rowsA = cA.rows;
        }
        const compactColsB =
            hideB &&
            !!data.matrix_b_unify_role_values &&
            (data.matrix_b_compact_columns || []).length > 0;
        if (compactColsB) {
            const compactCols = data.matrix_b_compact_columns || [];
            useCompactBThead = true;
            rangesB = compactCols.map(function () {
                return { name: "" };
            });
            rangeIdsB = compactCols.map(function (c) {
                return c.area_range_id || 0;
            });
            rowsB = (data.rows || []).map(function (row) {
                const cells = row.matrix_b_compact_cells || [];
                const vals = cells.map(function (c) {
                    return c.value != null ? c.value : 0;
                });
                const lrIds = cells.map(function (c) {
                    return c.level_range_id || 0;
                });
                const bIds = cells.map(function (c) {
                    return c.matrix_b_id || 0;
                });
                return Object.assign({}, row, {
                    levels_matrix_b: [vals],
                    levels_meta: [
                        {
                            level_range_id: 0,
                            output_ids: [],
                            matrix_a_ids: [],
                            matrix_b_ids: bIds,
                            matrix_b_level_range_ids: lrIds,
                        },
                    ],
                });
            });
            levelsB = levelsAB.length
                ? [
                      {
                          name: "",
                          color: 0,
                          branch_name: "",
                          level_id: levelsAB[0].level_id,
                          branch_id: levelsAB[0].branch_id,
                      },
                  ]
                : [
                      {
                          name: "",
                          color: 0,
                          branch_name: "",
                          level_id: 0,
                          branch_id: 0,
                      },
                  ];
        } else if (hideB) {
            const cB = collapseABForRepeatedRoles(rowsAB, levelsAB, ranges, "levels_matrix_b", "matrix_b_ids");
            levelsB = cB.levels;
            rowsB = cB.rows;
        }

        const dataColsOutput = levelsAB.length * ranges.length;
        const dataColsA = levelsA.length * ranges.length;
        const dataColsB = levelsB.length * rangesB.length;
        if (!dataColsOutput) {
            return (
                '<p class="text-muted">' +
                escapeHtml(sentenceCase(data.empty_message || "")) +
                "</p>"
            );
        }
        const cgOutput = colgroupHtml(dataColsOutput);
        const cgA = colgroupHtml(dataColsA);
        const cgB = colgroupHtml(dataColsB);
        const showBranchesInHeaders = !!labels.matrix_has_area_branches;
        const thOutput = theadHtml(levelsAB, ranges, labels, dataColsOutput, true, false, showBranchesInHeaders);
        const thMatrixA = theadHtml(
            levelsA,
            ranges,
            labels,
            dataColsA,
            !(compactA || globalA),
            hideA,
            false
        );
        const thMatrixB = useCompactBThead
            ? theadHtmlMatrixBCompact(
                  data.matrix_b_compact_columns || [],
                  labels,
                  showBranchesInHeaders
              )
            : theadHtml(levelsB, rangesB, labels, dataColsB, true, hideB, showBranchesInHeaders);

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
            cgOutput,
            thOutput,
            tbodyOutput(rowsAB, levelsAB, ranges, rangeIds, data.empty_message, readOnly, combined),
            "",
            {}
        );

        if (showAB) {
            const optionsA = data.table_a_layout === "normal" ? tableOptionsHtml("a", data, readOnly) : "";
            const optionsB = tableOptionsHtml("b", data, readOnly);
            const compactBRight = !!data.matrix_b_unify_role_values && !!data.matrix_b_hide_repeated_columns;
            out += oneTable(
                sentenceCase(labels.matrix_a_title || _t("Tabla A (horas base)")),
                cgA,
                thMatrixA,
                tbodyMatrixA(
                    rowsA,
                    levelsA,
                    ranges,
                    rangeIds,
                    compactA,
                    globalA,
                    data.empty_message,
                    readOnly,
                    combined
                ),
                optionsA,
                {}
            );
            out += oneTable(
                sentenceCase(labels.matrix_b_title || _t("Tabla B")),
                cgB,
                thMatrixB,
                tbodyMatrixB(
                    rowsB,
                    levelsB,
                    rangesB,
                    rangeIdsB,
                    data.empty_message,
                    readOnly,
                    combined
                ),
                optionsB,
                compactBRight
                    ? {
                          tableStyle: "table-layout:fixed;width:auto;min-width:0;",
                          responsiveClass: "d-flex justify-content-start",
                      }
                    : {}
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
                const hourKinds = {
                    output: true,
                    matrix_a: true,
                    matrix_a_compact: true,
                    matrix_a_global: true,
                };
                const bKinds = {matrix_b: true, matrix_b_single: true};
                if (hourKinds[kind] && num <= 0) {
                    $roots.find(".o_quoter_matrix_err").remove();
                    $roots.prepend(
                        '<div class="alert alert-danger alert-dismissible fade show o_quoter_matrix_err" role="alert">' +
                            escapeHtml(
                                _t("Las horas deben ser mayores a cero.")
                            ) +
                            '<button type="button" class="close" data-dismiss="alert" aria-label="Close">' +
                            '<span aria-hidden="true">&times;</span></button></div>'
                    );
                    return;
                }
                if (bKinds[kind] && num <= 0) {
                    $roots.find(".o_quoter_matrix_err").remove();
                    $roots.prepend(
                        '<div class="alert alert-danger alert-dismissible fade show o_quoter_matrix_err" role="alert">' +
                            escapeHtml(
                                _t(
                                    "El valor de la tabla B debe ser mayor a cero."
                                )
                            ) +
                            '<button type="button" class="close" data-dismiss="alert" aria-label="Close">' +
                            '<span aria-hidden="true">&times;</span></button></div>'
                    );
                    return;
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
        $roots
            .off("change.quoterMatrixOpt", "input.q-matrix-opt")
            .on("change.quoterMatrixOpt", "input.q-matrix-opt", function (ev) {
                const $inp = $(ev.target);
                const optionName = $inp.data("optionName");
                if (!optionName) {
                    return;
                }
                const enabled = !!$inp.prop("checked");
                const $cells = $roots.find("input.q-matrix-cell, input.q-matrix-opt");
                $cells.prop("disabled", true);
                const q = rpc.query({
                    model: "quoter.professional.area",
                    method: "matrix_preview_set_option",
                    args: [[areaId], optionName, enabled],
                });
                const done = q.then(function () {
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
                    $roots.find("input.q-matrix-cell, input.q-matrix-opt").prop("disabled", false);
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

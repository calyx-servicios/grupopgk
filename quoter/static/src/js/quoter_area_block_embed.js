odoo.define("quoter.area_block_embed", function (require) {
    "use strict";

    const FormRenderer = require("web.FormRenderer");
    const FormController = require("web.FormController");
    const FieldOne2Many = require("web.relational_fields").FieldOne2Many;
    const view_registry = require("web.view_registry");
    const core = require("web.core");
    const Dialog = require("web.Dialog");
    const fieldUtils = require("web.field_utils");
    const quoterPreserveActive = require("quoter.preserve_active_record");
    const _t = core._t;

    // Modo contingencia: desactivar embed para recuperar UI cuando hay crash global.
    // Rehabilitar cambiando a `false`.
    const QUOTER_DISABLE_AREA_EMBED = false;
    if (QUOTER_DISABLE_AREA_EMBED) {
        return;
    }

    if (typeof window !== "undefined" && !window.__quoterEmbedGlobalDiagAttached) {
        window.__quoterEmbedGlobalDiagAttached = true;
        window.addEventListener("unhandledrejection", function (ev) {
            if (window.console && console.error) {
                console.error("[quoter][global unhandledrejection] reason=", ev && ev.reason, ev);
            }
        });
        window.addEventListener("error", function (ev) {
            if (window.console && console.error) {
                console.error(
                    "[quoter][global error]",
                    ev && ev.message,
                    "at",
                    ev && ev.filename,
                    ev && ev.lineno,
                    ev && ev.colno,
                    ev && ev.error
                );
            }
        });
    }

    /**
     * `true`: solo pinta un panel de prueba en el slot (no monta FormView). Útil para verificar
     * que el JS llega al DOM. `false`: formulario embebido completo.
     */
    const QUOTER_AREA_EMBED_SIMPLE_PROBE = false;

    /**
     * Pestaña del notebook visible: Odoo/Bootstrap pueden usar solo `active` o también `show`,
     * o no usar `.tab-pane` en el ancestro; si exigimos solo `active` el embed nunca corre.
     */
    function quoterAreaEmbedTabAllowsUpdate($wrap) {
        const $pane = $wrap.closest(".tab-pane");
        if (!$pane.length) {
            return true;
        }
        if ($pane.hasClass("active") || $pane.hasClass("show")) {
            return true;
        }
        try {
            return $wrap.is(":visible");
        } catch (e) {
            return false;
        }
    }

    /**
     * En el BasicModel, ``list.data`` suele ser un array de **ids locales** (string),
     * no objetos ``{id: ...}``. Sin normalizar, ``lines[0].id`` es undefined y el embed falla.
     */
    function quoterListRowLocalId(row) {
        if (row === null || row === undefined) {
            return null;
        }
        if (typeof row === "object" && row.id !== undefined && row.id !== null) {
            return row.id;
        }
        return row;
    }

    function quoterResolveLineDatapointId(lines, fieldW, preferredDatapointId, preferredResId) {
        if (!lines || !lines.length) {
            return null;
        }
        if (
            preferredDatapointId &&
            lines.some(function (line) {
                return quoterListRowLocalId(line) === preferredDatapointId;
            })
        ) {
            return preferredDatapointId;
        }
        if (preferredResId) {
            const fc = getFormControllerFromField(fieldW);
            if (fc && fc.model) {
                for (let i = 0; i < lines.length; i++) {
                    const localId = quoterListRowLocalId(lines[i]);
                    const row = localId ? fc.model.get(localId) : null;
                    if (row && row.res_id === preferredResId) {
                        return localId;
                    }
                }
            }
        }
        return quoterListRowLocalId(lines[0]);
    }

    function x2manyRecordCount(val) {
        if (val === null || val === undefined || val === false) {
            return 0;
        }
        if (Array.isArray(val)) {
            if (!val.length) {
                return 0;
            }
            if (Array.isArray(val[0])) {
                for (let i = val.length - 1; i >= 0; i--) {
                    const cmd = val[i];
                    if (cmd && cmd[0] === 6 && Array.isArray(cmd[2])) {
                        return cmd[2].length;
                    }
                }
                return 0;
            }
            return val.length;
        }
        return 0;
    }

    function walkWidgetParents(widget) {
        const seen = new Set();
        const out = [];
        let p = widget;
        while (p && !seen.has(p)) {
            seen.add(p);
            out.push(p);
            p =
                (typeof p.getParent === "function" && p.getParent()) ||
                p.__parentedParent ||
                null;
        }
        return out;
    }

    function getFormControllerFromField(fieldWidget) {
        const chain = walkWidgetParents(fieldWidget);
        for (let i = 0; i < chain.length; i++) {
            const p = chain[i];
            if (
                p &&
                p.modelName === "sale.order" &&
                typeof p.saveRecord === "function" &&
                p.model
            ) {
                return p;
            }
        }
        return null;
    }

    function quoterM2oId(val) {
        if (val === null || val === undefined || val === false) {
            return null;
        }
        if (Array.isArray(val)) {
            return val[0] || null;
        }
        if (typeof val === "object") {
            if (val.res_id) {
                return val.res_id;
            }
            if (val.data && val.data.id) {
                return val.data.id;
            }
        }
        if (typeof val === "number") {
            return val;
        }
        return null;
    }

    function quoterM2oDisplayName(val) {
        if (Array.isArray(val) && val.length >= 2) {
            return val[1];
        }
        if (val && val.data && val.data.display_name) {
            return val.data.display_name;
        }
        return "";
    }

    function quoterAreaTabNavInForm($form) {
        const $pane = $form
            .find('.o_field_one2many[name="quoter_area_block_ids"]')
            .closest(".tab-pane")
            .first();
        if (!$pane.length) {
            return $();
        }
        return $pane.closest(".o_notebook").find("ul.nav-tabs").first();
    }

    function quoterActiveTabAreaIdInForm($form) {
        const $nav = quoterAreaTabNavInForm($form);
        if (!$nav.length) {
            return null;
        }
        const $active = $nav.find("a.nav-link.active").first();
        if (!$active.length) {
            return null;
        }
        const aid = parseInt($active.attr("data-quoter-area-id"), 10);
        return Number.isFinite(aid) ? aid : null;
    }

    function quoterResolveLineByAreaId(lines, fieldW, areaId) {
        if (!areaId || !lines || !lines.length) {
            return null;
        }
        const fc = getFormControllerFromField(fieldW);
        if (!fc) {
            return null;
        }
        for (let i = 0; i < lines.length; i++) {
            const localId = quoterListRowLocalId(lines[i]);
            if (!localId) {
                continue;
            }
            const row = fc.model.get(localId);
            if (!row || !row.data) {
                continue;
            }
            if (quoterM2oId(row.data.area_id) === areaId) {
                return localId;
            }
        }
        return null;
    }

    function getOrderedBlockRows(renderer) {
        const ctrl = getSaleOrderFormControllerFromRenderer(renderer);
        if (!ctrl || !ctrl.model) {
            return [];
        }
        const $wrap = $(renderer.el).find(".o_quoter_area_blocks_embed");
        const fieldW = findQuoterAreaBlockField(renderer, $wrap);
        if (!fieldW || !fieldW.value || !fieldW.value.id) {
            return [];
        }
        const listDp = ctrl.model.get(fieldW.value.id);
        if (!listDp || !listDp.data || !listDp.data.length) {
            return [];
        }
        const rows = [];
        listDp.data.forEach(function (localId) {
            const row = ctrl.model.get(localId);
            if (!row || !row.data) {
                return;
            }
            // Ocultar bloques de áreas cuyo grupo el usuario no tiene.
            if ("user_can_view_block" in row.data && !row.data.user_can_view_block) {
                return;
            }
            rows.push({
                localId: localId,
                res_id: row.res_id,
                sequence: parseInt(row.data.sequence, 10) || 0,
                area_id: quoterM2oId(row.data.area_id),
                area_name: quoterM2oDisplayName(row.data.area_id),
            });
        });
        rows.sort(function (a, b) {
            if (a.sequence !== b.sequence) {
                return a.sequence - b.sequence;
            }
            return (a.area_id || 0) - (b.area_id || 0);
        });
        return rows;
    }

    function switchEmbedToArea(renderer, areaId) {
        if (!areaId || !renderer) {
            return Promise.resolve();
        }
        const $wrap = $(renderer.el).find(".o_quoter_area_blocks_embed");
        const fieldW = findQuoterAreaBlockField(renderer, $wrap);
        if (!fieldW || !fieldW._quoterMountEmbedForDatapoint) {
            return Promise.resolve();
        }
        let lines = fieldW.value && fieldW.value.data;
        const fc = getFormControllerFromField(fieldW);
        if ((!lines || !lines.length) && fieldW.value && fieldW.value.id && fc) {
            const listDp = fc.model.get(fieldW.value.id);
            if (listDp && listDp.data && listDp.data.length) {
                lines = listDp.data;
            }
        }
        const targetId = quoterResolveLineByAreaId(lines, fieldW, areaId);
        if (!targetId) {
            return Promise.resolve();
        }
        fieldW.__quoterEmbedActiveDatapointId = targetId;
        const row = fc && fc.model.get(targetId, {raw: true});
        if (row) {
            fieldW.__quoterEmbedActiveResId = row.res_id;
        }
        return Promise.resolve(fieldW._quoterMountEmbedForDatapoint(targetId));
    }

    function syncEmbedToActiveTab(renderer) {
        const $form = $(renderer.el);
        const $pane = $form
            .find('.o_field_one2many[name="quoter_area_block_ids"]')
            .closest(".tab-pane")
            .first();
        if ($pane.length && !$pane.hasClass("active") && !$pane.hasClass("show")) {
            return Promise.resolve();
        }
        const areaId = quoterActiveTabAreaIdInForm($form);
        if (areaId) {
            return switchEmbedToArea(renderer, areaId);
        }
        const rows = getOrderedBlockRows(renderer);
        if (rows.length && rows[0].area_id) {
            return switchEmbedToArea(renderer, rows[0].area_id);
        }
        return Promise.resolve();
    }

    function bindQuoterAreaTabNav(renderer) {
        const $form = $(renderer.el);
        const $nav = quoterAreaTabNavInForm($form);
        if (!$nav.length) {
            return;
        }
        $nav.off("shown.bs.tab.quoterAreaBlock click.quoterAreaBlock");
        $nav.on("shown.bs.tab.quoterAreaBlock click.quoterAreaBlock", "a.nav-link", function () {
            const $a = $(this);
            const areaId = parseInt($a.attr("data-quoter-area-id"), 10);
            if (!Number.isFinite(areaId)) {
                return;
            }
            $nav.find("li.o_quoter_dyn_area_tab a.nav-link").removeClass(
                "o_quoter_area_subtab_selected"
            );
            $a.addClass("o_quoter_area_subtab_selected");
            switchEmbedToArea(renderer, areaId);
        });
    }

    /**
     * El form embebido (quoter.sale.order.area) no debe hacer _pushState con su res_id:
     * F5/sessionStorage quedarían con el id del bloque en lugar del sale.order.
     */
    function quoterPatchEmbedFormPushState(embedForm, areaBlockField) {
        if (!embedForm || embedForm.__quoterEmbedPushStatePatched) {
            return;
        }
        embedForm.__quoterEmbedPushStatePatched = true;
        embedForm.__quoterIsAreaBlockEmbed = true;
        embedForm._pushState = function () {
            const parentFc = getFormControllerFromField(areaBlockField);
            quoterPreserveActive.quoterPushSaleOrderFormState(parentFc);
        };
        quoterPatchEmbedFormLineObjectButtons(embedForm, areaBlockField);
        const bulkAdd = require("quoter.bulk_add_lines");
        if (bulkAdd && typeof bulkAdd.quoterPatchEmbedFormBulkAddButton === "function") {
            bulkAdd.quoterPatchEmbedFormBulkAddButton(embedForm, areaBlockField);
        }
    }

    /**
     * Botones type="object" en order_line_ids del bloque embebido: el FormController
     * estándar guarda todo el bloque antes de ejecutar la acción (p. ej. Ajustar),
     * lo que impide abrir el wizard de observación. Ejecutamos la acción sobre la
     * línea y refrescamos el bloque al cerrar el diálogo.
     */
    function quoterPatchEmbedFormLineObjectButtons(embedForm, areaBlockField) {
        if (!embedForm || embedForm.__quoterLineBtnPatched) {
            return;
        }
        embedForm.__quoterLineBtnPatched = true;
        const origOnButtonClicked = embedForm._onButtonClicked.bind(embedForm);
        embedForm._onButtonClicked = function (ev) {
            const attrs = ev.data && ev.data.attrs;
            const record = ev.data && ev.data.record;
            if (
                !record ||
                record.model !== "sale.order.line" ||
                !attrs ||
                attrs.type !== "object" ||
                !attrs.name ||
                attrs.special === "cancel"
            ) {
                return origOnButtonClicked(ev);
            }
            ev.stopPropagation();
            const self = embedForm;
            self._disableButtons();
            const lineRecord = self.model.get(record.id) || record;
            const actionData = Object.assign({}, attrs, {
                context: lineRecord.getContext({ additionalContext: attrs.context || {} }),
            });
            const recordData = {
                context: lineRecord.getContext(),
                currentID: lineRecord.res_id || lineRecord.data.id,
                model: lineRecord.model,
                resIDs: lineRecord.res_id ? [lineRecord.res_id] : lineRecord.res_ids,
            };
            const commitEdits = function () {
                if (
                    areaBlockField &&
                    typeof areaBlockField._quoterCommitEmbeddedOrderLineEdits === "function"
                ) {
                    return areaBlockField._quoterCommitEmbeddedOrderLineEdits();
                }
                return Promise.resolve();
            };
            const afterClose = function () {
                if (self.isDestroyed()) {
                    return Promise.resolve();
                }
                const host = areaBlockField;
                if (
                    host &&
                    attrs.name === "action_quoter_add_adjustment_line" &&
                    typeof host._quoterRefreshAfterAdjustmentLine === "function"
                ) {
                    return host._quoterRefreshAfterAdjustmentLine(self);
                }
                if (
                    host &&
                    host.__quoterEmbedForm &&
                    typeof host._quoterRefreshEmbeddedDataAfterSave === "function"
                ) {
                    return host._quoterRefreshEmbeddedDataAfterSave(host.__quoterEmbedForm);
                }
                if (typeof self.reload === "function") {
                    return self.reload();
                }
                return Promise.resolve();
            };
            const prom = commitEdits().then(function () {
                return new Promise(function (resolve, reject) {
                    self.trigger_up("execute_action", {
                        action_data: actionData,
                        env: recordData,
                        on_closed: afterClose,
                        on_success: resolve,
                        on_fail: function () {
                            return self
                                .update({}, { reload: false })
                                .then(reject)
                                .guardedCatch(reject);
                        },
                    });
                });
            });
            return self
                .alive(prom)
                .then(function () {
                    self._enableButtons();
                })
                .guardedCatch(function () {
                    self._enableButtons();
                });
        };
    }

    function getSaleOrderFormControllerFromRenderer(renderer) {
        const chain = walkWidgetParents(renderer);
        for (let i = 0; i < chain.length; i++) {
            const p = chain[i];
            if (
                p &&
                p.modelName === "sale.order" &&
                typeof p.saveRecord === "function" &&
                p.model
            ) {
                return p;
            }
        }
        return null;
    }

    /** Longitud de filas del x2many en el BasicModel (state.data suele guardar el id de la lista). */
    function getO2mListLineCount(model, listRef) {
        if (!model || listRef === null || listRef === undefined || listRef === false) {
            return 0;
        }
        if (typeof listRef !== "string") {
            return null;
        }
        const listDp = model.get(listRef);
        if (!listDp || listDp.type !== "list" || !Array.isArray(listDp.data)) {
            return null;
        }
        return listDp.data.length;
    }

    function findQuoterAreaBlockField(renderer, $wrap) {
        if ($wrap && $wrap.length) {
            const $root = $wrap.find('.o_field_one2many[name="quoter_area_block_ids"]').first();
            const fromDom = $root.data("quoterAreaBlockO2M");
            if (fromDom) {
                return fromDom;
            }
        }
        const widgets = renderer.allFieldWidgets && renderer.allFieldWidgets[renderer.state.id];
        if (!widgets) {
            return null;
        }
        for (let i = 0; i < widgets.length; i++) {
            if (widgets[i].name === "quoter_area_block_ids") {
                return widgets[i];
            }
        }
        return null;
    }

    function quoterPatchEmbedComplexityLevelLabel($body, formView) {
        if (!$body || !$body.length || !formView || !formView.model || !formView.handle) {
            return;
        }
        const rec = formView.model.get(formView.handle);
        if (!rec || !rec.data) {
            return;
        }
        const custom = String(rec.data.complexity_level_custom_label || "").trim();
        const isAuditoria = !!rec.data.area_is_auditoria;
        const labelText = custom
            ? custom
            : isAuditoria
            ? _t("Nivel de riesgo")
            : rec.data.area_is_tax
            ? _t("Nivel de complejidad")
            : _t("Nivel del área");
        $body.find("label[for^='complexity_level_id']").each(function () {
            const $lbl = $(this);
            const taxInvisible = $lbl.closest(".o_wrap_field, .o_row, tr").find(
                ".o_quoter_block_complexity_level"
            );
            if (!taxInvisible.length) {
                return;
            }
            const isHidden = taxInvisible.filter(function () {
                return $(this).closest(".o_wrap_field, .o_row, tr").css("display") === "none";
            }).length;
            if (isHidden) {
                return;
            }
            $lbl.text(labelText);
        });
        $body.find(".o_quoter_block_complexity_level").each(function () {
            const $inp = $(this);
            const $wrap = $inp.closest(".o_wrap_field, .o_row, tr");
            const $lbl = $wrap.find("label").first();
            if ($lbl.length) {
                $lbl.text(labelText);
            }
        });
    }

    function quoterComplexityLevelIdFromData(data) {
        if (!data || !data.complexity_level_id) {
            return false;
        }
        const v = data.complexity_level_id;
        if (Array.isArray(v)) {
            return v[0] || false;
        }
        if (typeof v === "number") {
            return v;
        }
        if (v.data && v.data.id) {
            return v.data.id;
        }
        if (v.res_id) {
            return v.res_id;
        }
        return false;
    }

    function quoterBindEmbedComplexityLevelConfirm(formView, areaBlockField) {
        if (!formView || formView.__quoterComplexityConfirmBound) {
            return;
        }
        if (!formView.model || typeof formView._onFieldChanged !== "function") {
            return;
        }
        formView.__quoterComplexityConfirmBound = true;
        let confirmedLevelId = quoterComplexityLevelIdFromData(
            formView.model.get(formView.handle).data
        );
        const originalOnFieldChanged = formView._onFieldChanged.bind(formView);
        formView._onFieldChanged = function (event) {
            const changes = event && event.data && event.data.changes;
            if (changes) {
                quoterEnsureParentSaleOrderEditMode(areaBlockField || formView);
                quoterMarkParentSaleOrderDirty(areaBlockField || formView);
            }
            if (
                !changes ||
                !Object.prototype.hasOwnProperty.call(changes, "complexity_level_id")
            ) {
                return originalOnFieldChanged(event);
            }
            const handle = (event && event.data && event.data.dataPointID) || formView.handle;
            const rec = formView.model.get(handle);
            const newId = changes.complexity_level_id;
            if (!rec || !rec.data || !rec.data.area_is_auditoria) {
                confirmedLevelId = newId;
                return originalOnFieldChanged(event);
            }
            if (!confirmedLevelId) {
                confirmedLevelId = quoterComplexityLevelIdFromData(rec.data);
            }
            if (formView.__quoterRiskLevelReverting) {
                formView.__quoterRiskLevelReverting = false;
                return originalOnFieldChanged(event);
            }
            const prevId = confirmedLevelId;
            if (!prevId || prevId === newId) {
                confirmedLevelId = newId;
                return originalOnFieldChanged(event);
            }
            Dialog.confirm(formView, _t("¿Desea modificar el nivel de riesgo?"), {
                confirm_callback: function () {
                    confirmedLevelId = newId;
                    originalOnFieldChanged(event);
                },
                cancel_callback: function () {
                    formView.__quoterRiskLevelReverting = true;
                    formView.model.notifyChanges(handle, {
                        complexity_level_id: prevId,
                    });
                },
            });
            return Promise.resolve();
        };
    }

    function quoterSanitizeEmbedFormButtons($container) {
        if (!$container || !$container.length) {
            return;
        }
        $container.find(".o_form_button_create").remove();
        $container
            .find(
                ".o_form_buttons_view button, .o_form_buttons_edit button, .o_form_statusbar .o_statusbar_buttons button"
            )
            .each(function () {
                const $btn = $(this);
                if ($btn.hasClass("o_form_button_edit") || $btn.hasClass("o_form_button_save")) {
                    return;
                }
                if ($btn.hasClass("o_form_button_cancel") || $btn.hasClass("o_form_button_discard")) {
                    return;
                }
                const label = ($btn.text() || "").trim().toLowerCase();
                if (label === "crear" || label === "create" || label === "new") {
                    $btn.remove();
                }
            });
    }

    function clearEmbedSlots($wrap) {
        $wrap.find(".o_quoter_area_block_form_body").empty();
    }

    /** Sincroniza modo edición del bloque embebido con el formulario sale.order (sin botones propios). */
    function quoterSyncEmbedFormMode(saleOrderController, mode) {
        if (!saleOrderController || !saleOrderController.renderer) {
            return;
        }
        const $wrap = $(saleOrderController.renderer.el).find(".o_quoter_area_blocks_embed");
        const fieldW = findQuoterAreaBlockField(saleOrderController.renderer, $wrap);
        const formView = fieldW && fieldW.__quoterEmbedForm;
        if (!formView || typeof formView._setMode !== "function" || formView.mode === mode) {
            return;
        }
        formView._setMode(mode);
    }

    function quoterUniqueIntIds(ids) {
        const out = [];
        const seen = new Set();
        (ids || []).forEach(function (rid) {
            if (typeof rid === "number" && rid > 0 && !seen.has(rid)) {
                seen.add(rid);
                out.push(rid);
            }
        });
        return out;
    }

    function quoterRelationalId(value) {
        if (value === false || value === null || value === undefined) {
            return null;
        }
        if (typeof value === "number") {
            return value;
        }
        if (Array.isArray(value)) {
            return value[0] || null;
        }
        if (typeof value === "object") {
            if (typeof value.id === "number") {
                return value.id;
            }
            if (value.data && typeof value.data.id === "number") {
                return value.data.id;
            }
        }
        return null;
    }

    function quoterNormalizeServerLineSyncResult(result) {
        if (result === true || result === false) {
            return { removed_ids: [], line_ids: [], has_line_ids: false };
        }
        if (result && typeof result === "object" && !Array.isArray(result)) {
            return {
                removed_ids: quoterUniqueIntIds(result.removed_ids || []),
                line_ids: quoterUniqueIntIds(result.line_ids || []),
                has_line_ids: Array.isArray(result.line_ids),
            };
        }
        if (Array.isArray(result)) {
            return {
                removed_ids: quoterUniqueIntIds(result),
                line_ids: [],
                has_line_ids: false,
            };
        }
        return { removed_ids: [], line_ids: [], has_line_ids: false };
    }

    /** Datapoint real en BasicModel (model.get() devuelve copia sin _cache). */
    function quoterGetRawDatapoint(model, datapointId) {
        if (!model || !datapointId || !model.localData) {
            return null;
        }
        return model.localData[datapointId] || null;
    }

    function quoterGetRawListDatapoint(model, listDatapointId) {
        const dp = quoterGetRawDatapoint(model, listDatapointId);
        if (!dp || dp.type !== "list") {
            return null;
        }
        if (!dp._cache) {
            dp._cache = {};
        }
        return dp;
    }

    const QUOTER_RANGE_HOUR_FIELD_NAMES = [
        "quoter_range_1_hours",
        "quoter_range_2_hours",
        "quoter_range_3_hours",
        "quoter_range_4_hours",
    ];

    function quoterIsCanBeSaveFalseError(err) {
        const raw =
            err === null || err === undefined
                ? ""
                : err.message || err.reason || String(err);
        let msg = raw;
        if (typeof msg !== "string") {
            try {
                msg = JSON.stringify(msg);
            } catch (_e) {
                msg = String(msg);
            }
        }
        return (msg || "").indexOf("canBeSave") >= 0;
    }

    function quoterResolveO2mListId(fieldValue) {
        if (!fieldValue) {
            return null;
        }
        if (typeof fieldValue === "string") {
            return fieldValue;
        }
        if (typeof fieldValue === "object" && fieldValue.id) {
            return fieldValue.id;
        }
        return null;
    }

    /** Al editar líneas del bloque, el pedido padre debe pasar a modo edición (coherencia con Guardar/Descartar). */
    function quoterEnsureParentSaleOrderEditMode(widget) {
        const parentFc = getFormControllerFromField(widget);
        if (!parentFc || parentFc.modelName !== "sale.order") {
            return;
        }
        if (parentFc.mode === "readonly" && typeof parentFc._setMode === "function") {
            parentFc._setMode("edit");
            quoterSyncEmbedFormMode(parentFc, "edit");
        }
    }

    /** Marca el sale.order como modificado (sin tocar quoter_area_block_ids: evita reset que vacía líneas). */
    function quoterMarkParentSaleOrderDirty(fieldWidget) {
        const parentFc = getFormControllerFromField(fieldWidget);
        if (!parentFc || !parentFc.model || !parentFc.handle) {
            return;
        }
        const orderDp = quoterGetRawDatapoint(parentFc.model, parentFc.handle);
        if (!orderDp) {
            return;
        }
        if (typeof parentFc.model.isDirty === "function") {
            try {
                if (parentFc.model.isDirty(parentFc.handle)) {
                    return;
                }
            } catch (err) {
                if (window.console && console.warn) {
                    console.warn("[quoter] isDirty skipped (broken tree):", err);
                }
            }
        }
        orderDp._isDirty = true;
    }

    function quoterAttachCatch(def, onErr) {
        if (!def || typeof def.then !== "function") {
            return def;
        }
        if (typeof def.guardedCatch === "function") {
            return def.guardedCatch(onErr);
        }
        if (typeof def.catch === "function") {
            return def.catch(onErr);
        }
        if (typeof def.fail === "function") {
            return def.fail(onErr);
        }
        return def.then(null, onErr);
    }

    function quoterSafeEnsureVisible(fieldW, sourceTag) {
        if (!fieldW || typeof fieldW._quoterEnsureEmbedVisible !== "function") {
            return;
        }
        try {
            const def = fieldW._quoterEnsureEmbedVisible();
            Promise.resolve(def).catch(function (err) {
                if (window.console && console.error) {
                    console.error("[quoter] ensure embed failed (" + sourceTag + "):", err);
                }
            });
        } catch (err) {
            if (window.console && console.error) {
                console.error("[quoter] ensure embed sync failed (" + sourceTag + "):", err);
            }
        }
    }

    function updateAreaBlockEmbed(renderer) {
        if (!renderer || !renderer.state || renderer.state.model !== "sale.order") {
            return;
        }
        const data = renderer.state.data || {};
        if (!data.is_quotation) {
            return;
        }
        if (!data.quoter_show_area_workspace) {
            const $wrapHidden = $(renderer.el).find(".o_quoter_area_blocks_embed");
            const fieldW = findQuoterAreaBlockField(renderer, $wrapHidden);
            if (fieldW && fieldW._quoterDestroyEmbedForm) {
                fieldW._quoterDestroyEmbedForm();
            }
            return;
        }
        const $wrap = $(renderer.el).find(".o_quoter_area_blocks_embed");
        if (!$wrap.length) {
            return;
        }
        if (!quoterAreaEmbedTabAllowsUpdate($wrap)) {
            return;
        }
        const ctrl = getSaleOrderFormControllerFromRenderer(renderer);
        const listLen = ctrl
            ? getO2mListLineCount(ctrl.model, data.quoter_area_block_ids)
            : null;
        const parsedCount = parseInt(data.quoter_area_block_count, 10);
        const nFromCompute =
            typeof data.quoter_area_block_count === "number"
                ? data.quoter_area_block_count
                : Number.isFinite(parsedCount)
                ? parsedCount
                : NaN;
        const nFallback = x2manyRecordCount(data.quoter_area_block_ids);
        const n = Math.max(
            listLen !== null && listLen !== undefined ? listLen : 0,
            !isNaN(nFromCompute) ? nFromCompute : 0,
            nFallback
        );
        $wrap.toggleClass("o_quoter_area_single_block", n === 1);
        $wrap.toggleClass("o_quoter_area_multi_block", n > 1);

        if (n === 0) {
            const fieldW = findQuoterAreaBlockField(renderer, $wrap);
            if (QUOTER_AREA_EMBED_SIMPLE_PROBE && fieldW && fieldW._quoterMountSimpleProbe) {
                fieldW._quoterMountSimpleProbe($wrap, [], null);
                return;
            }
            if (fieldW && fieldW._quoterDestroyEmbedForm) {
                fieldW._quoterDestroyEmbedForm();
            } else {
                clearEmbedSlots($wrap);
            }
            return;
        }

        function tryEmbed(ms) {
            setTimeout(function () {
                const fieldW = findQuoterAreaBlockField(renderer, $wrap);
                quoterSafeEnsureVisible(fieldW, "renderer:" + String(ms));
            }, ms);
        }
        bindQuoterAreaTabNav(renderer);
        // Pestaña lazy: el o2m puede montarse después del primer render.
        tryEmbed(0);
        tryEmbed(80);
        tryEmbed(250);
        tryEmbed(600);
        tryEmbed(1500);
    }

    FormRenderer.include({
        /**
         * Odoo 15 no copia attrs del <page> al div.tab-pane; sin esto no aplica class en DOM.
         */
        _renderTabPage: function (page, page_id) {
            const $result = this._super(page, page_id);
            if (page && page.attrs && page.attrs.class) {
                $result.addClass(page.attrs.class);
            }
            return $result;
        },
        _renderView: function () {
            const res = this._super.apply(this, arguments);
            const self = this;
            const run = function () {
                updateAreaBlockEmbed(self);
            };
            if (res && typeof res.then === "function") {
                return res.then(function () {
                    run();
                });
            }
            run();
            return res;
        },
        _onNotebookTabChanged: function () {
            this._super.apply(this, arguments);
            if (this.state && this.state.model === "sale.order") {
                const self = this;
                setTimeout(function () {
                    updateAreaBlockEmbed(self);
                }, 40);
                setTimeout(function () {
                    updateAreaBlockEmbed(self);
                }, 200);
            }
        },
    });

    FormController.include({
        _setMode: function (mode, recordID) {
            const res = this._super.apply(this, arguments);
            if (this.modelName === "sale.order") {
                quoterSyncEmbedFormMode(this, mode);
            }
            return res;
        },
        _quoterOnDomUpdatedForAreaEmbed: function () {
            if (this.modelName !== "sale.order" || !this.renderer) {
                return;
            }
            if (!this.renderer.state || this.renderer.state.model !== "sale.order") {
                return;
            }
            const self = this;
            clearTimeout(this.__quoterAreaEmbedDomTimer);
            this.__quoterAreaEmbedDomTimer = setTimeout(function () {
                updateAreaBlockEmbed(self.renderer);
            }, 50);
        },
        start: function () {
            const def = this._super.apply(this, arguments);
            if (this.modelName === "sale.order") {
                core.bus.on("DOM_updated", this, this._quoterOnDomUpdatedForAreaEmbed);
            }
            return def;
        },
        destroy: function () {
            core.bus.off("DOM_updated", this, this._quoterOnDomUpdatedForAreaEmbed);
            if (this.__quoterAreaEmbedDomTimer) {
                clearTimeout(this.__quoterAreaEmbedDomTimer);
            }
            return this._super.apply(this, arguments);
        },
        _onFieldChanged: function (ev) {
            this._super.apply(this, arguments);
            if (this.modelName !== "sale.order") {
                return;
            }
            const changed = (ev && ev.data && ev.data.changes) || {};
            const keys = Object.keys(changed);
            const relevant = keys.some(function (k) {
                return (
                    k === "quoter_area_block_ids" ||
                    k === "quoter_primary_tab_area_name" ||
                    k === "quoter_area_block_count" ||
                    k === "quoter_show_area_workspace" ||
                    k === "quoter_area_ids"
                );
            });
            if (relevant) {
                setTimeout(
                    function () {
                        updateAreaBlockEmbed(this.renderer);
                    }.bind(this),
                    0
                );
            }
        },
        saveRecord: function () {
            const args = arguments;
            const superSave = this._super && this._super.bind(this);
            const runParentSave = function () {
                if (!superSave) {
                    return Promise.reject(new Error("[quoter] super saveRecord not available"));
                }
                return superSave.apply(null, args);
            };
            if (this.modelName !== "sale.order" || !this.renderer || !this.renderer.el) {
                return runParentSave();
            }
            const $wrap = $(this.renderer.el).find(".o_quoter_area_blocks_embed");
            const fieldW = findQuoterAreaBlockField(this.renderer, $wrap);
            if (!fieldW || typeof fieldW._quoterFlushEmbeddedBlock !== "function") {
                return runParentSave();
            }
            const parentFc = getFormControllerFromField(fieldW);
            const embedForm = fieldW.__quoterEmbedForm;
            const hadServerUnlink = !!fieldW.__quoterHadServerLineUnlink;
            if (
                parentFc &&
                parentFc.model &&
                (fieldW.__quoterRemovedLineResIds || []).length
            ) {
                fieldW._quoterPurgeGhostLinesByResIds(
                    parentFc.model,
                    fieldW.__quoterRemovedLineResIds
                );
            }
            const syncParentOrderLines = function () {
                if (!hadServerUnlink) {
                    return Promise.resolve();
                }
                return fieldW._quoterHardResetParentOrderLineFromServer(parentFc);
            };
            const prepBeforeSave = function () {
                if (!hadServerUnlink && !(fieldW.__quoterRemovedLineResIds || []).length) {
                    return Promise.resolve();
                }
                if (embedForm) {
                    fieldW._quoterSanitizeEmbedModelBeforeSave(embedForm);
                }
                return fieldW
                    ._quoterPurgeParentOrderLineGhostState(parentFc, {
                        reloadOrder: false,
                    })
                    .then(syncParentOrderLines);
            };
            const prepAfterSave = function () {
                if (hadServerUnlink) {
                    return syncParentOrderLines();
                }
                return Promise.resolve();
            };
            return fieldW
                ._quoterCommitEmbeddedOrderLineEdits()
                .then(prepBeforeSave)
                .then(function () {
                    return fieldW._quoterSaveEmbeddedBeforeParent();
                })
                .then(prepAfterSave)
                .then(runParentSave)
                .catch(function (err) {
                    if (quoterIsCanBeSaveFalseError(err)) {
                        if (window.console && console.warn) {
                            console.warn(
                                "[quoter] guardado embebido omitido (validación); se guarda el pedido igual"
                            );
                        }
                        return runParentSave();
                    }
                    throw err;
                })
                .finally(function () {
                    fieldW.__quoterHadServerLineUnlink = false;
                    fieldW.__quoterRemovedLineResIds = [];
                    quoterPreserveActive.quoterPushSaleOrderFormState(parentFc);
                });
        },
        discardChanges: function () {
            const args = arguments;
            const superDiscard = this._super && this._super.bind(this);
            const runParentDiscard = function () {
                if (!superDiscard) {
                    return Promise.reject(new Error("[quoter] super discardChanges not available"));
                }
                return superDiscard.apply(null, args);
            };
            if (this.modelName !== "sale.order" || !this.renderer || !this.renderer.el) {
                return runParentDiscard();
            }
            const $wrap = $(this.renderer.el).find(".o_quoter_area_blocks_embed");
            const fieldW = findQuoterAreaBlockField(this.renderer, $wrap);
            if (!fieldW || typeof fieldW._quoterDiscardEmbeddedIfDirty !== "function") {
                return runParentDiscard();
            }
            const parentFc = getFormControllerFromField(fieldW);
            const embedForm = fieldW.__quoterEmbedForm;
            const hadLineDeletes =
                !!fieldW.__quoterHadServerLineUnlink ||
                (fieldW.__quoterRemovedLineResIds || []).length > 0;
            if (parentFc && parentFc.model && hadLineDeletes) {
                fieldW._quoterPurgeGhostLinesByResIds(
                    parentFc.model,
                    fieldW.__quoterRemovedLineResIds || []
                );
            }
            return Promise.resolve()
                .then(function () {
                    if (embedForm) {
                        fieldW._quoterSanitizeEmbedModelBeforeSave(embedForm);
                    }
                    return fieldW._quoterPurgeParentOrderLineGhostState(parentFc, {
                        reloadOrder: false,
                    });
                })
                .then(function () {
                    return fieldW._quoterDiscardEmbeddedBeforeParent();
                })
                .then(function () {
                    if (embedForm && !hadLineDeletes) {
                        return fieldW._quoterRefreshEmbeddedDataAfterSave(embedForm);
                    }
                    fieldW._quoterDestroyEmbedForm();
                })
                .then(function () {
                    return fieldW._quoterPurgeParentOrderLineGhostState(parentFc, {
                        reloadOrder: !hadLineDeletes,
                    });
                })
                .then(runParentDiscard)
                .finally(function () {
                    fieldW.__quoterHadServerLineUnlink = false;
                    fieldW.__quoterRemovedLineResIds = [];
                });
        },
    });

    FieldOne2Many.include({
        _quoterIsAreaBlocksEmbedField: function () {
            return (
                this.name === "quoter_area_block_ids" &&
                this.$el &&
                this.$el.closest(".o_quoter_area_blocks_embed").length
            );
        },

        start: async function () {
            const res = await this._super.apply(this, arguments);
            if (this._quoterIsAreaBlocksEmbedField()) {
                this.$el.data("quoterAreaBlockO2M", this);
                const self = this;
                [0, 80, 200, 500, 1200].forEach(function (ms) {
                    setTimeout(function () {
                        if (!self.isDestroyed() && self._quoterUseEmbedAreaBlocks()) {
                            quoterSafeEnsureVisible(self, "field.start:" + String(ms));
                        }
                    }, ms);
                });
            }
            return res;
        },

        on_attach_callback: function () {
            this._super.apply(this, arguments);
            const self = this;
            if (this._quoterIsAreaBlocksEmbedField()) {
                [0, 120, 400].forEach(function (ms) {
                    setTimeout(function () {
                        if (!self.isDestroyed() && self._quoterUseEmbedAreaBlocks()) {
                            quoterSafeEnsureVisible(self, "field.attach:" + String(ms));
                        }
                    }, ms);
                });
            }
        },

        /**
         * Form embebido en la pestaña (sin modal). El listado o2m va oculto en la vista.
         */
        _quoterUseEmbedAreaBlocks: function () {
            if (this.name !== "quoter_area_block_ids") {
                return false;
            }
            const fc = getFormControllerFromField(this);
            if (!fc || fc.modelName !== "sale.order") {
                return false;
            }
            return !!(this.record && this.record.data && this.record.data.is_quotation);
        },

        _quoterDestroyEmbedForm: function (options) {
            options = options || {};
            if (this.__quoterEmbedForm) {
                this.__quoterEmbedForm.destroy();
                this.__quoterEmbedForm = null;
            }
            if (!options.keepActiveDatapointId) {
                this.__quoterEmbedActiveDatapointId = null;
                this.__quoterEmbedActiveResId = null;
            }
            this.__quoterEmbedSavePendingPromise = null;
            const $wrap = this.$el && this.$el.closest(".o_quoter_area_blocks_embed");
            if ($wrap && $wrap.length) {
                clearEmbedSlots($wrap);
            }
        },
        _quoterSyncEmbeddedRecordLink: function (record) {
            if (!record) {
                return;
            }
            const fc = getFormControllerFromField(this);
            if (!fc || !fc.model) {
                return;
            }
            const lineRows = (this.value && this.value.data) || [];
            const recId = record.id;
            const recResId = record.res_id;
            const byDatapoint = lineRows.some(function (line) {
                return quoterListRowLocalId(line) === recId;
            });
            const byResId =
                recResId &&
                lineRows.some(function (line) {
                    const row = fc.model.get(quoterListRowLocalId(line));
                    return row && row.res_id === recResId;
                });
            if (byDatapoint || byResId) {
                this._setValue({ operation: "UPDATE", id: recId });
            } else if (recResId) {
                this._setValue({ operation: "ADD", id: recId });
            }
            this.__quoterEmbedActiveResId = recResId || null;
        },
        /**
         * Borrar una fila en order_line_ids ensucia la lista anidada aunque el form del bloque
         * no marque isDirty en el handle del bloque; sin esto el pedido padre guarda con ids viejos.
         */
        _quoterEmbeddedHasUnsavedChanges: function (formView) {
            if (!formView || !formView.model || !formView.handle) {
                return false;
            }
            const model = formView.model;
            if (typeof model.isDirty === "function" && model.isDirty(formView.handle)) {
                return true;
            }
            const block = model.get(formView.handle);
            if (!block || !block.data) {
                return false;
            }
            const lineRef = block.data.order_line_ids;
            const lineListId = lineRef && lineRef.id;
            if (lineListId && typeof model.isDirty === "function" && model.isDirty(lineListId)) {
                return true;
            }
            const rec = model.get(formView.handle);
            return !!(rec && rec._changes && Object.keys(rec._changes).length);
        },

        _quoterTrackRemovedLineResId: function (lineResId) {
            if (typeof lineResId !== "number" || lineResId <= 0) {
                return;
            }
            this.__quoterRemovedLineResIds = quoterUniqueIntIds(
                (this.__quoterRemovedLineResIds || []).concat([lineResId])
            );
        },

        /**
         * res_ids a purgar al borrar una línea (ajustes en cascada + sección de separador).
         */
        _quoterCollectRelatedLineResIdsForUnlink: function (model, localId, formView) {
            const ids = [];
            const row = model && model.get(localId, {raw: true});
            if (!row || typeof row.res_id !== "number" || row.res_id <= 0) {
                return ids;
            }
            ids.push(row.res_id);
            const childField = row.data && row.data.quoter_adjustment_child_line_ids;
            const childListId =
                childField && typeof childField === "object" ? childField.id : childField;
            const childList = childListId && model.get(childListId);
            if (childList && Array.isArray(childList.data)) {
                childList.data.forEach(function (cid) {
                    const child = model.get(cid);
                    if (child && typeof child.res_id === "number" && child.res_id > 0) {
                        ids.push(child.res_id);
                    }
                });
            }
            if (childList && Array.isArray(childList.res_ids)) {
                childList.res_ids.forEach(function (rid) {
                    if (typeof rid === "number" && rid > 0) {
                        ids.push(rid);
                    }
                });
            }
            const productTagId = quoterRelationalId(
                row.data && row.data.quoter_separator_tag_id
            );
            const blockDp =
                formView && formView.handle && model.get(formView.handle, {raw: true});
            const lineListId = quoterResolveO2mListId(
                blockDp && blockDp.data && blockDp.data.order_line_ids
            );
            const lineList = quoterGetRawListDatapoint(model, lineListId);
            if (lineList && Array.isArray(lineList.data)) {
                const localIdx = lineList.data.indexOf(localId);
                if (localIdx >= 0) {
                    for (let i = localIdx - 1; i >= 0; i--) {
                        const prev = model.localData[lineList.data[i]];
                        if (!prev || typeof prev.res_id !== "number" || prev.res_id <= 0) {
                            continue;
                        }
                        const prevData = Object.assign({}, prev.data, prev._changes);
                        if (prevData.display_type === "line_section") {
                            ids.push(prev.res_id);
                            break;
                        }
                        if (!prevData.display_type) {
                            break;
                        }
                    }
                    if (localIdx + 1 < lineList.data.length) {
                        const next = model.localData[lineList.data[localIdx + 1]];
                        const nextData = next && Object.assign({}, next.data, next._changes);
                        if (
                            next &&
                            typeof next.res_id === "number" &&
                            next.res_id > 0 &&
                            nextData &&
                            nextData.quoter_is_adjustment_line
                        ) {
                            ids.push(next.res_id);
                        }
                    }
                }
                if (productTagId) {
                    lineList.data.forEach(function (lid) {
                        const sec = model.localData[lid];
                        if (!sec || typeof sec.res_id !== "number" || sec.res_id <= 0) {
                            return;
                        }
                        const secData = Object.assign({}, sec.data, sec._changes);
                        if (secData.display_type !== "line_section") {
                            return;
                        }
                        const secTagId = quoterRelationalId(
                            secData.quoter_separator_section_tag_id
                        );
                        if (secTagId === productTagId) {
                            ids.push(sec.res_id);
                        }
                    });
                }
            }
            return quoterUniqueIntIds(ids);
        },

        /**
         * Borra por completo la caché local de una lista x2many (evita sublistas rotas).
         */
        _quoterWipeLineListCache: function (model, listDatapointId) {
            if (!model || !listDatapointId) {
                return;
            }
            const listDp = quoterGetRawListDatapoint(model, listDatapointId);
            if (!listDp) {
                return;
            }
            Object.keys(listDp._cache).forEach(function (cacheKey) {
                const dpId = listDp._cache[cacheKey];
                if (dpId && model.localData[dpId]) {
                    delete model.localData[dpId];
                }
            });
            if (Array.isArray(listDp.data)) {
                listDp.data.forEach(function (lid) {
                    if (lid && model.localData[lid]) {
                        delete model.localData[lid];
                    }
                });
            }
            listDp._cache = {};
            listDp.data = [];
            listDp._changes = [];
            listDp.orderedResIDs = null;
        },

        /**
         * Reconstruye order_line_ids desde cero con los ids del servidor (sin reload).
         * Usar model.reload (no _readUngroupedList): la API interna exige list._cache y
         * model.get() devuelve copias sin ese campo.
         */
        _quoterHardResetLineListFromServer: function (model, listDatapointId, serverLineIds) {
            if (!model || !listDatapointId) {
                return Promise.resolve();
            }
            const orderedIds = quoterUniqueIntIds(serverLineIds || []);
            this._quoterWipeLineListCache(model, listDatapointId);
            const listDp = quoterGetRawListDatapoint(model, listDatapointId);
            if (!listDp) {
                return Promise.resolve();
            }
            listDp.res_ids = orderedIds.slice();
            listDp.count = orderedIds.length;
            if (!orderedIds.length || typeof model.reload !== "function") {
                return Promise.resolve();
            }
            return quoterAttachCatch(
                model.reload(listDatapointId, { ids: orderedIds }),
                function (err) {
                    if (window.console && console.warn) {
                        console.warn("[quoter] hard reset line list failed:", err);
                    }
                }
            );
        },

        /**
         * order_line del pedido padre comparte tabla con el bloque: tras borrado RPC hay que
         * alinear res_ids desde servidor antes de guardar sale.order.
         */
        _quoterHardResetParentOrderLineFromServer: function (fc) {
            const self = this;
            if (!fc || !fc.model || fc.modelName !== "sale.order" || !fc.handle) {
                return Promise.resolve();
            }
            const model = fc.model;
            const orderDp = quoterGetRawDatapoint(model, fc.handle);
            if (!orderDp || !orderDp.res_id || !orderDp.data || !orderDp.data.order_line) {
                return Promise.resolve();
            }
            const parentListId = quoterResolveO2mListId(orderDp.data.order_line);
            const removed = self.__quoterRemovedLineResIds || [];
            if (removed.length) {
                self._quoterPurgeGhostLinesByResIds(model, removed);
            }
            if (orderDp._changes && orderDp._changes.order_line) {
                delete orderDp._changes.order_line;
            }
            const ctx =
                typeof orderDp.getContext === "function" ? orderDp.getContext() : {};
            return self
                ._rpc({
                    model: "sale.order",
                    method: "read",
                    args: [[orderDp.res_id], ["order_line"]],
                    context: ctx,
                })
                .then(function (records) {
                    const rec = records && records[0];
                    const lineIds = (rec && rec.order_line) || [];
                    return self._quoterHardResetLineListFromServer(
                        model,
                        parentListId,
                        lineIds
                    );
                });
        },

        /**
         * @deprecated use _quoterHardResetLineListFromServer
         */
        _quoterReplaceLineListFromServerIds: function (model, listDatapointId, serverLineIds) {
            return this._quoterHardResetLineListFromServer(model, listDatapointId, serverLineIds);
        },

        /**
         * Limpia todas las listas del BasicModel (cache/res_ids/data/_changes huérfanos).
         */
        _quoterSanitizeAllModelLists: function (model) {
            if (!model || !model.localData) {
                return;
            }
            const self = this;
            Object.keys(model.localData).forEach(function (key) {
                const dp = model.localData[key];
                if (!dp || dp.type !== "list") {
                    return;
                }
                if (dp._cache) {
                    Object.keys(dp._cache).forEach(function (cacheKey) {
                        const dpId = dp._cache[cacheKey];
                        if (!dpId || !model.localData[dpId]) {
                            delete dp._cache[cacheKey];
                        }
                    });
                }
                if (Array.isArray(dp.res_ids)) {
                    dp.res_ids = dp.res_ids.filter(function (rid) {
                        const cached = dp._cache && dp._cache[rid];
                        return !cached || !!model.localData[cached];
                    });
                }
                if (Array.isArray(dp.data)) {
                    dp.data = dp.data.filter(function (lid) {
                        return !!(lid && model.localData[lid]);
                    });
                }
                if (Array.isArray(dp._changes)) {
                    dp._changes = dp._changes.filter(function (chg) {
                        if (!chg || !chg.id) {
                            return true;
                        }
                        return !!model.localData[chg.id];
                    });
                }
                self._quoterResyncLineListResIdsFromData(model, dp.id);
            });
        },

        _quoterClearLineListPendingChanges: function (model, listDatapointId) {
            if (!model || !listDatapointId) {
                return;
            }
            const listDp = quoterGetRawListDatapoint(model, listDatapointId);
            if (listDp) {
                listDp._changes = [];
            }
        },

        /**
         * Alinea res_ids con las filas que quedan en data (evita link_to/update sobre ids borrados).
         */
        _quoterResyncLineListResIdsFromData: function (model, listDatapointId) {
            if (!model || !listDatapointId) {
                return;
            }
            const listDp = quoterGetRawListDatapoint(model, listDatapointId);
            if (!listDp || !Array.isArray(listDp.data)) {
                return;
            }
            const resIds = [];
            listDp.data.forEach(function (lid) {
                const row = model.localData[lid];
                if (row && typeof row.res_id === "number" && row.res_id > 0) {
                    resIds.push(row.res_id);
                }
            });
            listDp.res_ids = resIds;
        },

        /**
         * Quita ids de fila huérfanos en una lista (evita elem undefined en reload/discard).
         */
        _quoterSanitizeListDatapoint: function (model, listDatapointId) {
            if (!model || !listDatapointId) {
                return;
            }
            const listDp = quoterGetRawListDatapoint(model, listDatapointId);
            if (!listDp || !Array.isArray(listDp.data)) {
                return;
            }
            listDp.data = listDp.data.filter(function (lid) {
                return !!(lid && model.localData[lid]);
            });
            this._quoterResyncLineListResIdsFromData(model, listDatapointId);
            listDp._changes = [];
        },

        /**
         * Tras borrar en servidor: quitar datapoints y comandos que referencian res_id inexistente.
         */
        _quoterPurgeGhostLinesByResIds: function (model, resIds) {
            const self = this;
            const idSet = new Set(quoterUniqueIntIds(resIds));
            if (!model || !model.localData || !idSet.size) {
                return;
            }
            const lineTouchesGhost = function (lineId) {
                if (!lineId) {
                    return false;
                }
                const row = model.get(lineId);
                return !!(row && row.res_id && idSet.has(row.res_id));
            };
            Object.keys(model.localData).forEach(function (key) {
                const dp = model.localData[key];
                if (
                    dp &&
                    dp.model === "sale.order.line" &&
                    dp.res_id &&
                    idSet.has(dp.res_id)
                ) {
                    delete model.localData[key];
                }
            });
            const pruneList = function (listDp) {
                if (!listDp || listDp.type !== "list" || !Array.isArray(listDp.data)) {
                    return;
                }
                listDp.data = listDp.data.filter(function (lid) {
                    const row = model.localData[lid];
                    return !!(row && (!row.res_id || !idSet.has(row.res_id)));
                });
                if (Array.isArray(listDp.res_ids)) {
                    listDp.res_ids = listDp.res_ids.filter(function (rid) {
                        return !idSet.has(rid);
                    });
                }
                if (listDp._cache) {
                    Object.keys(listDp._cache).forEach(function (cacheKey) {
                        const dpId = listDp._cache[cacheKey];
                        const row = dpId && model.localData[dpId];
                        const resId = row && row.res_id;
                        if (idSet.has(Number(cacheKey)) || (resId && idSet.has(resId))) {
                            delete listDp._cache[cacheKey];
                        }
                    });
                }
                if (Array.isArray(listDp.orderedResIDs)) {
                    listDp.orderedResIDs = listDp.orderedResIDs.filter(function (rid) {
                        return !idSet.has(rid);
                    });
                }
                listDp.orderedResIDs = null;
                if (Array.isArray(listDp._changes)) {
                    listDp._changes = listDp._changes.filter(function (chg) {
                        if (!chg || !chg.id) {
                            return true;
                        }
                        const row = model.get(chg.id);
                        return !row || !row.res_id || !idSet.has(row.res_id);
                    });
                }
                if (!listDp._cache) {
                    listDp._cache = {};
                }
                self._quoterResyncLineListResIdsFromData(model, listDp.id);
            };
            const scrubRecordChanges = function (rec) {
                if (!rec || !rec._changes || !Array.isArray(rec._changes)) {
                    return;
                }
                rec._changes = rec._changes.filter(function (chg) {
                    if (!chg || !chg.id) {
                        return true;
                    }
                    if (chg.model === "sale.order.line" && chg.res_id && idSet.has(chg.res_id)) {
                        return false;
                    }
                    return !lineTouchesGhost(chg.id);
                });
            };
            const formView = this.__quoterEmbedForm;
            if (formView && formView.handle) {
                const blockDp = quoterGetRawDatapoint(model, formView.handle);
                scrubRecordChanges(blockDp);
                if (blockDp && blockDp.data && blockDp.data.order_line_ids) {
                    pruneList(
                        quoterGetRawListDatapoint(
                            model,
                            quoterResolveO2mListId(blockDp.data.order_line_ids)
                        )
                    );
                }
            }
            const fc = getFormControllerFromField(this);
            if (fc && fc.handle) {
                const order = quoterGetRawDatapoint(model, fc.handle);
                scrubRecordChanges(order);
                if (order && order.data && order.data.order_line) {
                    pruneList(
                        quoterGetRawListDatapoint(
                            model,
                            quoterResolveO2mListId(order.data.order_line)
                        )
                    );
                }
            }
            if (this.value && this.value.id) {
                pruneList(quoterGetRawListDatapoint(model, this.value.id));
            }
            self._quoterSanitizeAllModelLists(model);
        },

        _quoterSanitizeEmbedModelBeforeSave: function (formView) {
            if (!formView || !formView.model) {
                return;
            }
            const model = formView.model;
            const removed = this.__quoterRemovedLineResIds || [];
            if (removed.length) {
                this._quoterPurgeGhostLinesByResIds(model, removed);
            }
            const blockDp = quoterGetRawDatapoint(model, formView.handle);
            if (blockDp && blockDp.data && blockDp.data.order_line_ids) {
                this._quoterResyncLineListResIdsFromData(
                    model,
                    quoterResolveO2mListId(blockDp.data.order_line_ids)
                );
            }
            const fc = getFormControllerFromField(this);
            if (fc && fc.handle) {
                const order = quoterGetRawDatapoint(model, fc.handle);
                if (order && order.data && order.data.order_line) {
                    this._quoterResyncLineListResIdsFromData(
                        model,
                        quoterResolveO2mListId(order.data.order_line)
                    );
                }
            }
        },

        _quoterFlushEmbeddedBlock: function () {
            const formView = this.__quoterEmbedForm;
            if (!formView || !formView.model || !formView.handle) {
                return Promise.resolve();
            }
            this._quoterSanitizeEmbedModelBeforeSave(formView);
            return this._quoterInvokeEmbeddedFormSave(formView);
        },

        _quoterSaveEmbeddedIfDirty: function () {
            const formView = this.__quoterEmbedForm;
            if (!formView || !this._quoterEmbeddedHasUnsavedChanges(formView)) {
                return Promise.resolve();
            }
            return this._quoterFlushEmbeddedBlock();
        },

        /**
         * Paso 1 al guardar la cotización: mismo efecto que Guardar del form embebido
         * (botón oculto por CSS pero activo), luego sale.order en el FormController.
         */
        _quoterSaveEmbeddedBeforeParent: function () {
            const self = this;
            const formView = this.__quoterEmbedForm;
            if (!formView || !formView.model || !formView.handle) {
                return Promise.resolve();
            }
            return self
                ._quoterCommitEmbeddedOrderLineEdits()
                .then(function () {
                    return self._quoterSaveEmbeddedBeforeParentCore(formView);
                });
        },

        _quoterEmbeddedCanSaveBlock: function (formView) {
            if (!formView || typeof formView.canBeSaved !== "function") {
                return true;
            }
            return formView.canBeSaved(formView.handle);
        },

        _quoterPrepareEmbeddedListBeforeBlockSave: function () {
            const lw = this._quoterFindBlockOrderLineListWidget();
            if (!lw || lw.isDestroyed()) {
                return Promise.resolve();
            }
            const renderer = lw.renderer;
            if (renderer && typeof renderer.unselectRow === "function") {
                try {
                    return Promise.resolve(renderer.unselectRow());
                } catch (err) {
                    if (window.console && console.warn) {
                        console.warn("[quoter] unselectRow before block save failed:", err);
                    }
                }
            }
            if (typeof lw.commitChanges === "function") {
                try {
                    return Promise.resolve(lw.commitChanges());
                } catch (err) {
                    if (window.console && console.warn) {
                        console.warn("[quoter] commitChanges before block save failed:", err);
                    }
                }
            }
            return Promise.resolve();
        },

        _quoterSaveEmbeddedBeforeParentCore: function (formView) {
            const self = this;
            const block = formView.model.get(formView.handle, {raw: true});
            if (!block || !block.res_id) {
                return Promise.resolve();
            }
            if (formView.mode === "readonly") {
                return Promise.resolve();
            }
            this._quoterSanitizeEmbedModelBeforeSave(formView);
            const removed = this.__quoterRemovedLineResIds || [];
            const hadServerUnlink = !!this.__quoterHadServerLineUnlink;
            const dirty = this._quoterEmbeddedHasUnsavedChanges(formView);
            if (hadServerUnlink && !dirty) {
                return Promise.resolve();
            }
            if (!dirty) {
                if (removed.length && !hadServerUnlink) {
                    return this._quoterRefreshEmbeddedDataAfterSave(formView);
                }
                return Promise.resolve();
            }
            return self._quoterPrepareEmbeddedListBeforeBlockSave().then(function () {
                if (!self._quoterEmbeddedCanSaveBlock(formView)) {
                    if (window.console && console.warn) {
                        console.warn(
                            "[quoter] formulario del bloque con campos inválidos; horas vía RPC, sin saveRecord del embed"
                        );
                    }
                    return Promise.resolve();
                }
                return self._quoterInvokeEmbeddedFormSave(formView);
            });
        },

        /**
         * Llama saveRecord del controlador embebido (equivalente al botón Guardar oculto).
         */
        _quoterInvokeEmbeddedFormSave: function (formView) {
            const self = this;
            if (!formView || typeof formView.saveRecord !== "function") {
                return self._quoterFlushEmbeddedBlock();
            }
            if (self.__quoterEmbedSavePendingPromise) {
                return self.__quoterEmbedSavePendingPromise;
            }
            const savePromise = self
                ._quoterPrepareEmbeddedListBeforeBlockSave()
                .then(function () {
                    if (!self._quoterEmbeddedCanSaveBlock(formView)) {
                        return Promise.resolve([]);
                    }
                    return formView.saveRecord(formView.handle, {
                        stayInEdit: true,
                        reload: false,
                        savePoint: false,
                        viewType: "form",
                    });
                })
                .then(function (changedFields) {
                    const rec = formView.model.get(formView.handle);
                    self._quoterSyncEmbeddedRecordLink(rec);
                    return changedFields;
                })
                .catch(function (err) {
                    if (quoterIsCanBeSaveFalseError(err)) {
                        if (window.console && console.warn) {
                            console.warn(
                                "[quoter] saveRecord embebido rechazado (canBeSaved=false); continuar"
                            );
                        }
                        return [];
                    }
                    if (window.console && console.error) {
                        console.error("[quoter] embedded form save failed:", err);
                    }
                    throw err;
                })
                .finally(function () {
                    if (self.__quoterEmbedSavePendingPromise === savePromise) {
                        self.__quoterEmbedSavePendingPromise = null;
                    }
                });
            self.__quoterEmbedSavePendingPromise = savePromise;
            return savePromise;
        },

        _quoterDiscardEmbeddedBeforeParent: function () {
            const formView = this.__quoterEmbedForm;
            if (!formView) {
                return Promise.resolve();
            }
            const dirty = this._quoterEmbeddedHasUnsavedChanges(formView);
            const hadUnlink = !!this.__quoterHadServerLineUnlink;
            if (!dirty && !hadUnlink) {
                return Promise.resolve();
            }
            return this._quoterDiscardEmbeddedIfDirty();
        },

        /**
         * El pedido padre carga order_line (oculto) y el bloque order_line_ids: misma tabla.
         * Tras guardar el bloque hay que recargar ambas listas en el BasicModel.
         */
        /**
         * El pedido tiene order_line invisible pero el BasicModel puede conservar
         * datapoints de líneas borradas en el bloque; limpiar antes de guardar el pedido.
         */
        _quoterPurgeParentOrderLineGhostState: function (fc, options) {
            options = options || {};
            if (!fc || !fc.model || fc.modelName !== "sale.order" || !fc.handle) {
                return Promise.resolve();
            }
            const model = fc.model;
            const order = quoterGetRawDatapoint(model, fc.handle);
            if (!order || !order.data || !order.data.order_line) {
                return Promise.resolve();
            }
            const listId = quoterResolveO2mListId(order.data.order_line);
            const list = quoterGetRawListDatapoint(model, listId);
            const removed = new Set(this.__quoterRemovedLineResIds || []);
            if (list && removed.size) {
                this._quoterPurgeGhostLinesByResIds(model, Array.from(removed));
                if (list._cache) {
                    removed.forEach(function (rid) {
                        const dpId = list._cache[rid];
                        if (dpId && model.localData[dpId]) {
                            delete model.localData[dpId];
                        }
                        delete list._cache[rid];
                    });
                }
                if (Array.isArray(list.res_ids)) {
                    list.res_ids = list.res_ids.filter(function (rid) {
                        return !removed.has(rid);
                    });
                }
                if (Array.isArray(list.data)) {
                    list.data = list.data.filter(function (lid) {
                        const row = model.localData[lid];
                        return row && (!row.res_id || !removed.has(row.res_id));
                    });
                }
                list._changes = [];
            }
            // Por defecto no recargar el pedido: antes de saveRecord del padre borraría
            // los cambios de cabecera aún no persistidos en el BasicModel.
            if (options.reloadOrder !== true || typeof model.reload !== "function") {
                return Promise.resolve();
            }
            return model.reload(fc.handle).then(function () {
                quoterPreserveActive.quoterPushSaleOrderFormState(fc);
            });
        },

        _quoterMergeLineRowData: function (row) {
            if (!row) {
                return {};
            }
            return Object.assign({}, row.data || {}, row._changes || {});
        },

        /**
         * Lee horas desde inputs visibles del listado (BasicModel a veces queda en 0).
         */
        _quoterHarvestAdjustmentHoursFromDom: function (lw, formView) {
            const harvested = {};
            if (!lw || !lw.$el || !formView || !formView.model) {
                return harvested;
            }
            const model = formView.model;
            const $tbody = lw.$el.find("table.o_list_table tbody").first();
            const $rows = $tbody.length ? $tbody.find("tr") : lw.$el.find("tbody tr");
            $rows.each(function () {
                const $tr = $(this);
                if (
                    $tr.hasClass("o_group_header") ||
                    $tr.hasClass("o_list_table_grouped") ||
                    !$tr.is(":visible")
                ) {
                    return;
                }
                let localId = $tr.data("id");
                if (!localId) {
                    const $withId = $tr.find("[data-id]").first();
                    if ($withId.length) {
                        localId = $withId.data("id");
                    }
                }
                const row = localId ? quoterGetRawDatapoint(model, localId) : null;
                const data = row
                    ? Object.assign({}, row.data || {}, row._changes || {})
                    : {};
                if (!data.quoter_is_adjustment_line) {
                    return;
                }
                const resId = row && row.res_id;
                if (typeof resId !== "number" || resId <= 0) {
                    return;
                }
                const item = {id: resId};
                let found = false;
                QUOTER_RANGE_HOUR_FIELD_NAMES.forEach(function (key) {
                    let $input = $tr.find('input[name="' + key + '"]');
                    if (!$input.length) {
                        $input = $tr.find('[name="' + key + '"] input');
                    }
                    if (!$input.length) {
                        $input = $tr.find('td[name="' + key + '"] input');
                    }
                    if (!$input.length) {
                        $input = $tr.find('td.o_data_cell[name="' + key + '"] input');
                    }
                    if (!$input.length) {
                        return;
                    }
                    const raw = $input.val();
                    if (raw === undefined || raw === null || raw === "") {
                        return;
                    }
                    const num = parseFloat(String(raw).replace(",", "."));
                    if (isNaN(num)) {
                        return;
                    }
                    item[key] = num;
                    found = true;
                });
                const $noteCell = $tr.find('[name="quoter_adjustment_note"]');
                const $noteInput = $noteCell.find("input, textarea");
                if ($noteInput.length) {
                    const noteVal = $noteInput.val();
                    if (noteVal !== undefined && noteVal !== null && String(noteVal).trim()) {
                        item.quoter_adjustment_note = String(noteVal).trim();
                        found = true;
                    }
                }
                if (found) {
                    harvested[resId] = item;
                }
            });
            return harvested;
        },

        /**
         * Lee volumen fórmula desde inputs visibles (BasicModel puede quedar desincronizado).
         */
        _quoterHarvestFormulaVolumeFromDom: function (lw, formView) {
            const harvested = {};
            if (!lw || !lw.$el || !formView || !formView.model) {
                return harvested;
            }
            const model = formView.model;
            const $tbody = lw.$el.find("table.o_list_table tbody").first();
            const $rows = $tbody.length ? $tbody.find("tr") : lw.$el.find("tbody tr");
            $rows.each(function () {
                const $tr = $(this);
                if (
                    $tr.hasClass("o_group_header") ||
                    $tr.hasClass("o_list_table_grouped") ||
                    !$tr.is(":visible")
                ) {
                    return;
                }
                let localId = $tr.data("id");
                if (!localId) {
                    const $withId = $tr.find("[data-id]").first();
                    if ($withId.length) {
                        localId = $withId.data("id");
                    }
                }
                const row = localId ? quoterGetRawDatapoint(model, localId) : null;
                const data = row
                    ? Object.assign({}, row.data || {}, row._changes || {})
                    : {};
                if (data.quoter_formula_is_fixed || data.display_type) {
                    return;
                }
                const resId = row && row.res_id;
                if (typeof resId !== "number" || resId <= 0) {
                    return;
                }
                let $input = $tr.find('input[name="quoter_formula_volume"]');
                if (!$input.length) {
                    $input = $tr.find('[name="quoter_formula_volume"] input');
                }
                if (!$input.length) {
                    $input = $tr.find('td[name="quoter_formula_volume"] input');
                }
                if (!$input.length) {
                    $input = $tr.find('td.o_data_cell[name="quoter_formula_volume"] input');
                }
                if (!$input.length) {
                    return;
                }
                const raw = $input.val();
                if (raw === undefined || raw === null || raw === "") {
                    return;
                }
                const num = parseFloat(String(raw).replace(",", "."));
                if (isNaN(num)) {
                    return;
                }
                harvested[resId] = num;
            });
            return harvested;
        },

        _quoterStripAdjustmentHourFieldChanges: function (formView) {
            if (!formView || !formView.model) {
                return;
            }
            const model = formView.model;
            const block = quoterGetRawDatapoint(model, formView.handle);
            const listId = quoterResolveO2mListId(
                block && block.data && block.data.order_line_ids
            );
            const list = quoterGetRawListDatapoint(model, listId);
            if (!list || !Array.isArray(list.data)) {
                return;
            }
            list.data.forEach(function (lid) {
                const row = quoterGetRawDatapoint(model, lid);
                if (!row || !row.data || !row.data.quoter_is_adjustment_line) {
                    return;
                }
                if (!row._changes) {
                    return;
                }
                QUOTER_RANGE_HOUR_FIELD_NAMES.forEach(function (key) {
                    delete row._changes[key];
                });
                delete row._changes.quoter_range_hour_ids;
                delete row._changes.quoter_total_hours;
                delete row._changes.price_unit;
                if (!Object.keys(row._changes).length) {
                    delete row._changes;
                }
            });
        },

        _quoterStripFormulaVolumeFieldChanges: function (formView) {
            if (!formView || !formView.model) {
                return;
            }
            const model = formView.model;
            const block = quoterGetRawDatapoint(model, formView.handle);
            const listId = quoterResolveO2mListId(
                block && block.data && block.data.order_line_ids
            );
            const list = quoterGetRawListDatapoint(model, listId);
            if (!list || !Array.isArray(list.data)) {
                return;
            }
            list.data.forEach(function (lid) {
                const row = quoterGetRawDatapoint(model, lid);
                if (!row || !row.data || row.data.quoter_formula_is_fixed) {
                    return;
                }
                if (!row._changes) {
                    return;
                }
                delete row._changes.quoter_formula_volume;
                if (!Object.keys(row._changes).length) {
                    delete row._changes;
                }
            });
        },

        _quoterCollectAdjustmentLineHoursPayloads: function (formView) {
            const payloads = [];
            if (!formView || !formView.model) {
                return payloads;
            }
            const lw = this._quoterFindBlockOrderLineListWidget();
            const domByResId = this._quoterHarvestAdjustmentHoursFromDom(lw, formView);
            const model = formView.model;
            const block = quoterGetRawDatapoint(model, formView.handle);
            const listId = quoterResolveO2mListId(
                block && block.data && block.data.order_line_ids
            );
            const list = quoterGetRawListDatapoint(model, listId);
            if (!list || !Array.isArray(list.data)) {
                return payloads;
            }
            const self = this;
            list.data.forEach(function (lid) {
                const row = quoterGetRawDatapoint(model, lid);
                if (!row) {
                    return;
                }
                const data = self._quoterMergeLineRowData(row);
                if (!data.quoter_is_adjustment_line) {
                    return;
                }
                const resId = row.res_id;
                if (typeof resId !== "number" || resId <= 0) {
                    return;
                }
                const item = {id: resId};
                let hasPayload = false;
                const domItem = domByResId[resId];
                QUOTER_RANGE_HOUR_FIELD_NAMES.forEach(function (key) {
                    if (domItem && domItem[key] !== undefined && domItem[key] !== null) {
                        item[key] = domItem[key];
                        hasPayload = true;
                        return;
                    }
                    if (data[key] !== undefined && data[key] !== null) {
                        item[key] = data[key];
                        hasPayload = true;
                    }
                });
                if (domItem && domItem.quoter_adjustment_note) {
                    item.quoter_adjustment_note = domItem.quoter_adjustment_note;
                    hasPayload = true;
                } else if (data.quoter_adjustment_note) {
                    item.quoter_adjustment_note = data.quoter_adjustment_note;
                    hasPayload = true;
                }
                if (hasPayload) {
                    payloads.push(item);
                }
            });
            return payloads;
        },

        _quoterCollectFormulaVolumePayloads: function (formView) {
            const payloads = [];
            if (!formView || !formView.model) {
                return payloads;
            }
            const lw = this._quoterFindBlockOrderLineListWidget();
            const domByResId = this._quoterHarvestFormulaVolumeFromDom(lw, formView);
            const model = formView.model;
            const block = quoterGetRawDatapoint(model, formView.handle);
            const listId = quoterResolveO2mListId(
                block && block.data && block.data.order_line_ids
            );
            const list = quoterGetRawListDatapoint(model, listId);
            if (!list || !Array.isArray(list.data)) {
                return payloads;
            }
            const self = this;
            list.data.forEach(function (lid) {
                const row = quoterGetRawDatapoint(model, lid);
                if (!row) {
                    return;
                }
                const data = self._quoterMergeLineRowData(row);
                if (data.quoter_formula_is_fixed || data.display_type) {
                    return;
                }
                const resId = row.res_id;
                if (typeof resId !== "number" || resId <= 0) {
                    return;
                }
                let volume = null;
                if (
                    domByResId[resId] !== undefined &&
                    domByResId[resId] !== null &&
                    !isNaN(domByResId[resId])
                ) {
                    volume = domByResId[resId];
                } else if (
                    data.quoter_formula_volume !== undefined &&
                    data.quoter_formula_volume !== null
                ) {
                    volume = data.quoter_formula_volume;
                }
                if (volume === null) {
                    return;
                }
                payloads.push({id: resId, quoter_formula_volume: volume});
            });
            return payloads;
        },

        _quoterApplyAdjustmentHoursReadToEmbed: function (formView, readRows) {
            if (!formView || !formView.model || !readRows || !readRows.length) {
                return;
            }
            const model = formView.model;
            const block = quoterGetRawDatapoint(model, formView.handle);
            const listId = quoterResolveO2mListId(
                block && block.data && block.data.order_line_ids
            );
            const list = quoterGetRawListDatapoint(model, listId);
            if (!list || !Array.isArray(list.data)) {
                return;
            }
            readRows.forEach(function (rec) {
                if (!rec || typeof rec.id !== "number") {
                    return;
                }
                const localId = list.data.find(function (lid) {
                    const row = quoterGetRawDatapoint(model, lid);
                    return row && row.res_id === rec.id;
                });
                if (!localId) {
                    return;
                }
                const dp = quoterGetRawDatapoint(model, localId);
                if (!dp) {
                    return;
                }
                if (!dp.data) {
                    dp.data = {};
                }
                QUOTER_RANGE_HOUR_FIELD_NAMES.forEach(function (key) {
                    if (rec[key] !== undefined) {
                        dp.data[key] = rec[key];
                        if (dp._changes && key in dp._changes) {
                            delete dp._changes[key];
                        }
                    }
                });
                if (rec.quoter_formula_volume !== undefined) {
                    dp.data.quoter_formula_volume = rec.quoter_formula_volume;
                    if (dp._changes && "quoter_formula_volume" in dp._changes) {
                        delete dp._changes.quoter_formula_volume;
                    }
                }
                if (rec.quoter_total_hours !== undefined) {
                    dp.data.quoter_total_hours = rec.quoter_total_hours;
                    if (dp._changes && "quoter_total_hours" in dp._changes) {
                        delete dp._changes.quoter_total_hours;
                    }
                }
                if (rec.price_unit !== undefined) {
                    dp.data.price_unit = rec.price_unit;
                    if (dp._changes && "price_unit" in dp._changes) {
                        delete dp._changes.price_unit;
                    }
                }
            });
        },

        _quoterPersistAdjustmentLineHoursBeforeSave: function (formView) {
            const self = this;
            const payloads = self._quoterCollectAdjustmentLineHoursPayloads(formView);
            if (!payloads.length) {
                return Promise.resolve();
            }
            const lineIds = payloads.map(function (p) {
                return p.id;
            });
            const readFields = QUOTER_RANGE_HOUR_FIELD_NAMES.concat([
                "quoter_total_hours",
                "price_unit",
            ]);
            return self
                ._rpc({
                    model: "sale.order.line",
                    method: "quoter_persist_adjustment_line_hours_batch",
                    args: [payloads],
                })
                .then(function () {
                    return self._rpc({
                        model: "sale.order.line",
                        method: "read",
                        args: [lineIds, readFields],
                    });
                })
                .then(function (rows) {
                    self._quoterApplyAdjustmentHoursReadToEmbed(formView, rows);
                    self._quoterStripAdjustmentHourFieldChanges(formView);
                })
                .catch(function (err) {
                    if (window.console && console.warn) {
                        console.warn("[quoter] persist adjustment hours failed:", err);
                    }
                    return Promise.resolve();
                });
        },

        _quoterPersistFormulaVolumeBeforeSave: function (formView) {
            const self = this;
            const payloads = self._quoterCollectFormulaVolumePayloads(formView);
            if (!payloads.length) {
                return Promise.resolve();
            }
            const lineIds = payloads.map(function (p) {
                return p.id;
            });
            const readFields = ["quoter_formula_volume"].concat(
                QUOTER_RANGE_HOUR_FIELD_NAMES,
                ["quoter_total_hours", "price_unit"]
            );
            return self
                ._rpc({
                    model: "sale.order.line",
                    method: "quoter_persist_formula_volume_batch",
                    args: [payloads],
                })
                .then(function () {
                    return self._rpc({
                        model: "sale.order.line",
                        method: "read",
                        args: [lineIds, readFields],
                    });
                })
                .then(function (rows) {
                    self._quoterApplyAdjustmentHoursReadToEmbed(formView, rows);
                    self._quoterStripFormulaVolumeFieldChanges(formView);
                })
                .catch(function (err) {
                    if (window.console && console.warn) {
                        console.warn("[quoter] persist formula volume failed:", err);
                    }
                    return Promise.resolve();
                });
        },

        /**
         * Lee horas por rango (y precio unitario en Finanzas/regular_manual) desde el
         * listado del bloque para las líneas con carga manual de horas: área regular_manual
         * o producto con `manual_load = True` (campo `quoter_can_edit_range_hours`).
         * El BasicModel del form embebido puede quedar con datapoints duplicados/obsoletos
         * para la misma línea, por lo que se toma el valor visible del DOM.
         */
        _quoterHarvestRegularManualFromDom: function (lw, formView) {
            const harvested = {};
            if (!lw || !lw.$el || !formView || !formView.model) {
                return harvested;
            }
            const model = formView.model;
            const hourKeys = QUOTER_RANGE_HOUR_FIELD_NAMES;
            const $tbody = lw.$el.find("table.o_list_table tbody").first();
            const $rows = $tbody.length ? $tbody.find("tr") : lw.$el.find("tbody tr");
            const readCellValue = function ($tr, name) {
                let $input = $tr.find('td[name="' + name + '"] input');
                if (!$input.length) {
                    $input = $tr.find('[name="' + name + '"] input');
                }
                if ($input.length) {
                    const raw = $input.val();
                    return raw === undefined || raw === null ? "" : String(raw);
                }
                const $cell = $tr.find('td[name="' + name + '"]');
                if ($cell.length) {
                    return String($cell.text() || "");
                }
                return "";
            };
            const parseNum = function (raw) {
                if (raw === undefined || raw === null) {
                    return null;
                }
                const s = String(raw).trim();
                if (s === "") {
                    return null;
                }
                try {
                    const v = fieldUtils.parse.float(s);
                    if (typeof v === "number" && !isNaN(v)) {
                        return v;
                    }
                } catch (e) {
                    // fallback below
                }
                const n = parseFloat(
                    s.replace(/[^0-9,.\-]/g, "").replace(/\./g, "").replace(",", ".")
                );
                return isNaN(n) ? null : n;
            };
            $rows.each(function () {
                const $tr = $(this);
                if (
                    $tr.hasClass("o_group_header") ||
                    $tr.hasClass("o_list_table_grouped") ||
                    !$tr.is(":visible")
                ) {
                    return;
                }
                let localId = $tr.data("id");
                if (!localId) {
                    const $withId = $tr.find("[data-id]").first();
                    if ($withId.length) {
                        localId = $withId.data("id");
                    }
                }
                const row = localId ? quoterGetRawDatapoint(model, localId) : null;
                const data = row
                    ? Object.assign({}, row.data || {}, row._changes || {})
                    : {};
                if (data.display_type || data.quoter_is_adjustment_line) {
                    return;
                }
                // Solo líneas con horas manuales: Finanzas (regular_manual) o producto
                // con manual_load = True. `quoter_can_edit_range_hours` cubre ambos casos.
                if (!data.quoter_can_edit_range_hours) {
                    return;
                }
                const resId = row && row.res_id;
                if (typeof resId !== "number" || resId <= 0) {
                    return;
                }
                const item = {id: resId};
                let found = false;
                const price = parseNum(readCellValue($tr, "price_unit"));
                if (price !== null) {
                    item.price_unit = price;
                    found = true;
                }
                hourKeys.forEach(function (key) {
                    const val = parseNum(readCellValue($tr, key));
                    if (val !== null) {
                        item[key] = val;
                        found = true;
                    }
                });
                if (found) {
                    harvested[resId] = item;
                }
            });
            return harvested;
        },

        _quoterCollectRegularManualLinePayloads: function (formView) {
            const payloads = [];
            if (!formView || !formView.model) {
                return payloads;
            }
            const model = formView.model;
            const block = quoterGetRawDatapoint(model, formView.handle);
            if (!block || !block.data) {
                return payloads;
            }
            // No se filtra por tipo de área: la cosecha por fila ya incluye solo líneas
            // con horas manuales (regular_manual o producto manual_load = True).
            const lw = this._quoterFindBlockOrderLineListWidget();
            const domByResId = this._quoterHarvestRegularManualFromDom(lw, formView);
            Object.keys(domByResId).forEach(function (resIdStr) {
                const item = domByResId[resIdStr];
                if (item && typeof item.id === "number" && item.id > 0) {
                    payloads.push(item);
                }
            });
            return payloads;
        },

        /**
         * Actualiza data y limpia _changes de precio/horas en TODOS los datapoints de las
         * líneas persistidas (evita que un datapoint obsoleto pise el valor al guardar).
         */
        _quoterApplyRegularManualReadToEmbed: function (formView, readRows) {
            if (!formView || !formView.model || !readRows) {
                return;
            }
            const model = formView.model;
            const byId = {};
            readRows.forEach(function (rec) {
                if (rec && typeof rec.id === "number") {
                    byId[rec.id] = rec;
                }
            });
            const keys = QUOTER_RANGE_HOUR_FIELD_NAMES.concat([
                "price_unit",
                "price_subtotal",
                "quoter_total_hours",
            ]);
            Object.keys(model.localData).forEach(function (k) {
                const dp = model.localData[k];
                if (
                    !dp ||
                    dp.model !== "sale.order.line" ||
                    dp.type !== "record" ||
                    !byId[dp.res_id]
                ) {
                    return;
                }
                const rec = byId[dp.res_id];
                if (!dp.data) {
                    dp.data = {};
                }
                keys.forEach(function (key) {
                    if (rec[key] !== undefined) {
                        dp.data[key] = rec[key];
                        if (dp._changes && key in dp._changes) {
                            delete dp._changes[key];
                        }
                    }
                });
                if (dp._changes && "quoter_range_hour_ids" in dp._changes) {
                    delete dp._changes.quoter_range_hour_ids;
                }
                if (dp._changes && !Object.keys(dp._changes).length) {
                    delete dp._changes;
                }
            });
        },

        _quoterPersistRegularManualLineEditsBeforeSave: function (formView) {
            const self = this;
            const payloads = self._quoterCollectRegularManualLinePayloads(formView);
            if (!payloads.length) {
                return Promise.resolve();
            }
            const lineIds = payloads.map(function (p) {
                return p.id;
            });
            const readFields = QUOTER_RANGE_HOUR_FIELD_NAMES.concat([
                "quoter_total_hours",
                "price_unit",
                "price_subtotal",
            ]);
            return self
                ._rpc({
                    model: "sale.order.line",
                    method: "quoter_persist_regular_manual_line_edits_batch",
                    args: [payloads],
                })
                .then(function () {
                    return self._rpc({
                        model: "sale.order.line",
                        method: "read",
                        args: [lineIds, readFields],
                    });
                })
                .then(function (rows) {
                    self._quoterApplyRegularManualReadToEmbed(formView, rows);
                })
                .catch(function (err) {
                    if (window.console && console.warn) {
                        console.warn(
                            "[quoter] persist regular manual line edits failed:",
                            err
                        );
                    }
                    return Promise.resolve();
                });
        },

        /**
         * Confirma la fila en edición del listado (horas, nota) antes de guardar o abrir wizard.
         */
        _quoterCommitEmbeddedOrderLineEdits: function () {
            const self = this;
            const lw = self._quoterFindBlockOrderLineListWidget();
            if (!lw || lw.isDestroyed()) {
                return Promise.resolve();
            }
            const unselect = function () {
                const renderer = lw.renderer;
                if (renderer && typeof renderer.unselectRow === "function") {
                    try {
                        renderer.unselectRow();
                    } catch (err) {
                        if (window.console && console.warn) {
                            console.warn("[quoter] unselect embedded line row failed:", err);
                        }
                    }
                }
                return Promise.resolve();
            };
            const commit = function () {
                if (typeof lw.commitChanges !== "function") {
                    return Promise.resolve();
                }
                try {
                    return Promise.resolve(lw.commitChanges());
                } catch (err) {
                    if (window.console && console.warn) {
                        console.warn("[quoter] commit embedded line edits failed:", err);
                    }
                    return Promise.resolve();
                }
            };
            const formView = self.__quoterEmbedForm;
            return unselect()
                .then(commit)
                .then(function () {
                    if (!formView) {
                        return Promise.resolve();
                    }
                    return Promise.all([
                        self._quoterPersistAdjustmentLineHoursBeforeSave(formView),
                        self._quoterPersistFormulaVolumeBeforeSave(formView),
                        self._quoterPersistRegularManualLineEditsBeforeSave(formView),
                    ]);
                });
        },

        _quoterFindBlockOrderLineListWidget: function () {
            const formView = this.__quoterEmbedForm;
            if (!formView || !formView.renderer || !formView.handle) {
                return null;
            }
            const widgets =
                formView.renderer.allFieldWidgets &&
                formView.renderer.allFieldWidgets[formView.handle];
            if (!widgets) {
                return null;
            }
            for (let i = 0; i < widgets.length; i++) {
                if (widgets[i].name === "order_line_ids") {
                    return widgets[i];
                }
            }
            return null;
        },

        /**
         * Sincroniza el widget order_line_ids con el BasicModel (this.value queda stale
         * si solo se llama renderer.updateState sin reset del campo).
         */
        _quoterRepaintBlockOrderLineField: function (formView, lineListWidget, listId) {
            return this._quoterSyncBlockLineListRenderer(formView, lineListWidget, listId);
        },

        /**
         * Repinta la lista del bloque tras borrado/reload (form del bloque + list renderer).
         */
        _quoterSyncBlockLineListRenderer: function (formView, lineListWidget, listId) {
            const self = this;
            if (!formView || !formView.model || !formView.handle) {
                return Promise.resolve();
            }
            const model = formView.model;
            const lw =
                lineListWidget &&
                !lineListWidget.isDestroyed() &&
                lineListWidget.name === "order_line_ids"
                    ? lineListWidget
                    : self._quoterFindBlockOrderLineListWidget();
            if (!lw || lw.isDestroyed()) {
                return Promise.resolve();
            }
            const blockHandle = formView.handle;
            let reloadDef = Promise.resolve();
            if (typeof model.reload === "function") {
                reloadDef = quoterAttachCatch(
                    model.reload(blockHandle),
                    function (err) {
                        if (window.console && console.warn) {
                            console.warn("[quoter] reload block form after line sync:", err);
                        }
                    }
                );
            }
            return reloadDef.then(function () {
                const blockRecord = model.get(blockHandle);
                if (!blockRecord) {
                    return Promise.resolve();
                }
                const resolvedListId =
                    listId ||
                    quoterResolveO2mListId(
                        blockRecord.data && blockRecord.data.order_line_ids
                    );
                const listDp = resolvedListId && model.get(resolvedListId);
                if (!listDp) {
                    return Promise.resolve();
                }
                let resetDef = Promise.resolve();
                if (typeof lw.reset === "function") {
                    resetDef = Promise.resolve(
                        lw.reset(blockRecord, { fieldChanged: true })
                    );
                }
                return resetDef.then(function () {
                    if (
                        lw.renderer &&
                        typeof lw.renderer.updateState === "function"
                    ) {
                        return lw.renderer.updateState(listDp, {
                            addCreateLine: lw._hasCreateLine(),
                            addTrashIcon: lw._hasTrashIcon(),
                            columnInvisibleFields: lw._evalColumnInvisibleFields(),
                            keepWidths: true,
                        });
                    }
                    if (typeof lw._render === "function") {
                        return lw._render();
                    }
                });
            });
        },

        _quoterCollectLocalLineIdsForResIds: function (model, listDatapointId, resIds) {
            const wanted = new Set(quoterUniqueIntIds(resIds || []));
            const localIds = [];
            if (!wanted.size || !model || !listDatapointId) {
                return localIds;
            }
            const listDp = quoterGetRawListDatapoint(model, listDatapointId);
            if (!listDp || !Array.isArray(listDp.data)) {
                return localIds;
            }
            listDp.data.forEach(function (lid) {
                const row = quoterGetRawDatapoint(model, lid);
                if (row && typeof row.res_id === "number" && wanted.has(row.res_id)) {
                    localIds.push(lid);
                }
            });
            return localIds;
        },

        /**
         * Quita filas del listado del bloque en el BasicModel y repinta al instante.
         */
        _quoterOptimisticRemoveBlockLinesFromUI: function (
            formView,
            localIds,
            resIds
        ) {
            if (!formView || !formView.model) {
                return Promise.resolve();
            }
            const model = formView.model;
            const blockDp = quoterGetRawDatapoint(model, formView.handle);
            const listId = quoterResolveO2mListId(
                blockDp && blockDp.data && blockDp.data.order_line_ids
            );
            const listDp = quoterGetRawListDatapoint(model, listId);
            if (!listDp || !Array.isArray(listDp.data)) {
                return Promise.resolve();
            }
            const localSet = new Set(localIds || []);
            const resSet = new Set(quoterUniqueIntIds(resIds || []));
            listDp.data = listDp.data.filter(function (lid) {
                if (localSet.has(lid)) {
                    if (model.localData[lid]) {
                        delete model.localData[lid];
                    }
                    return false;
                }
                const row = quoterGetRawDatapoint(model, lid);
                if (row && typeof row.res_id === "number" && resSet.has(row.res_id)) {
                    delete model.localData[lid];
                    return false;
                }
                return true;
            });
            if (Array.isArray(listDp.res_ids)) {
                listDp.res_ids = listDp.res_ids.filter(function (rid) {
                    return !resSet.has(rid);
                });
            }
            listDp.count = listDp.data.length;
            listDp._changes = [];
            if (blockDp && blockDp._changes && blockDp._changes.order_line_ids) {
                delete blockDp._changes.order_line_ids;
            }
            return this._quoterSyncBlockLineListRenderer(formView, null, listId);
        },

        /**
         * Tras borrar en servidor: alinear pedido padre (order_line) y bloque (order_line_ids).
         * Los predeterminados se cargan en order_line del sale.order; si solo se refresca el
         * bloque, esas filas siguen en el BasicModel del padre hasta guardar.
         */
        _quoterRefreshBlockLinesAfterDelete: function (blockDatapointId, serverPayload, lineListWidget) {
            const self = this;
            serverPayload = quoterNormalizeServerLineSyncResult(serverPayload || {});
            const removed = quoterUniqueIntIds(
                serverPayload.removed_ids.concat(self.__quoterRemovedLineResIds || [])
            );
            const formView = self.__quoterEmbedForm;
            const fc = getFormControllerFromField(self);
            if (!fc || !fc.model || !blockDatapointId || !formView) {
                return Promise.resolve();
            }
            const model = fc.model;
            const blockDp = quoterGetRawDatapoint(model, blockDatapointId);
            if (!blockDp) {
                return Promise.resolve();
            }
            if (removed.length) {
                self._quoterPurgeGhostLinesByResIds(model, removed);
            }
            const listId = quoterResolveO2mListId(
                blockDp.data && blockDp.data.order_line_ids
            );
            if (blockDp._changes && blockDp._changes.order_line_ids) {
                delete blockDp._changes.order_line_ids;
            }
            if (listId) {
                self._quoterClearLineListPendingChanges(model, listId);
            }
            self._quoterSanitizeAllModelLists(model);

            const lineIds = serverPayload.has_line_ids ? serverPayload.line_ids : null;

            const resetList = function () {
                if (!listId) {
                    return Promise.resolve();
                }
                if (lineIds === null) {
                    return Promise.resolve();
                }
                return self._quoterHardResetLineListFromServer(model, listId, lineIds);
            };
            return self
                ._quoterHardResetParentOrderLineFromServer(fc)
                .then(resetList)
                .then(function () {
                    return self._quoterSyncBlockLineListRenderer(
                        formView,
                        lineListWidget,
                        listId
                    );
                })
                .then(function () {
                    quoterEnsureParentSaleOrderEditMode(lineListWidget || self);
                })
                .guardedCatch(function (err) {
                    if (window.console && console.warn) {
                        console.warn("[quoter] refresh block lines after delete:", err);
                    }
                    return self._quoterSyncBlockLineListRenderer(
                        formView,
                        lineListWidget,
                        listId
                    );
                });
        },

        _quoterFetchBlockOrderLineSync: function (blockResId) {
            return this._rpc({
                model: "quoter.sale.order.area",
                method: "action_quoter_get_block_order_line_sync",
                args: [[blockResId]],
            }).then(function (result) {
                return quoterNormalizeServerLineSyncResult(result);
            });
        },

        _quoterResyncEmbeddedBlockLinesFromServer: function (blockDatapointId, blockResId) {
            const self = this;
            const blockDpId = blockDatapointId || self.__quoterEmbedActiveDatapointId;
            if (!blockResId || !blockDpId) {
                return Promise.resolve();
            }
            return self._quoterFetchBlockOrderLineSync(blockResId).then(function (payload) {
                return self._quoterRefreshBlockLinesAfterDelete(blockDpId, payload, self);
            });
        },

        _quoterRefreshParentOrderLineList: function () {
            const fc = getFormControllerFromField(this);
            if (!fc || !fc.model || fc.modelName !== "sale.order" || !fc.handle) {
                return Promise.resolve();
            }
            const order = fc.model.get(fc.handle);
            if (!order || !order.data || !order.data.order_line) {
                return Promise.resolve();
            }
            const listId = order.data.order_line.id;
            if (listId && fc.model.get(listId) && typeof fc.model.reload === "function") {
                return fc.model.reload(listId);
            }
            return Promise.resolve();
        },

        /**
         * Tras crear una línea de ajuste en servidor (wizard): recargar bloque y lista
         * order_line_ids para mostrarla sin guardar el pedido completo.
         */
        /**
         * Tras carga múltiple RPC: refresca líneas del bloque sin saveRecord del pedido
         * (evita formulario embebido en blanco).
         */
        _quoterAfterBulkLinesAdded: function (formView) {
            const self = this;
            quoterEnsureParentSaleOrderEditMode(self);
            quoterMarkParentSaleOrderDirty(self);
            return self._quoterRefreshAfterAdjustmentLine(formView);
        },

        _quoterRefreshAfterAdjustmentLine: function (formView) {
            const host = this;
            const fc = getFormControllerFromField(host);
            if (!fc || !fc.model || !formView || !formView.handle) {
                return Promise.resolve();
            }
            const model = fc.model;
            const blockDp = quoterGetRawDatapoint(model, formView.handle);
            if (!blockDp || !blockDp.res_id) {
                return Promise.resolve();
            }
            const listId = quoterResolveO2mListId(
                blockDp.data && blockDp.data.order_line_ids
            );
            return host
                ._quoterHardResetParentOrderLineFromServer(fc)
                .then(function () {
                    return host._quoterFetchBlockOrderLineSync(blockDp.res_id);
                })
                .then(function (payload) {
                    if (!listId || !payload || !Array.isArray(payload.line_ids)) {
                        return Promise.resolve();
                    }
                    return host._quoterHardResetLineListFromServer(
                        model,
                        listId,
                        payload.line_ids
                    );
                })
                .then(function () {
                    return host._quoterRepaintBlockOrderLineField(formView, null, listId);
                })
                .then(function () {
                    quoterEnsureParentSaleOrderEditMode(host);
                });
        },

        _quoterRefreshEmbeddedDataAfterSave: function (formView) {
            const self = this;
            const fc = getFormControllerFromField(this);
            if (!fc || !fc.model || !formView || !formView.handle) {
                return Promise.resolve();
            }
            if (self.__quoterHadServerLineUnlink) {
                const blockDp = quoterGetRawDatapoint(fc.model, formView.handle);
                return self._quoterHardResetParentOrderLineFromServer(fc).then(function () {
                    if (!blockDp || !blockDp.res_id) {
                        return;
                    }
                    return self._quoterFetchBlockOrderLineSync(blockDp.res_id).then(function (payload) {
                        const listRef =
                            blockDp.data &&
                            blockDp.data.order_line_ids &&
                            quoterResolveO2mListId(blockDp.data.order_line_ids);
                        if (listRef) {
                            return self._quoterHardResetLineListFromServer(
                                fc.model,
                                listRef,
                                payload.line_ids
                            );
                        }
                    });
                });
            }
            return self._quoterRepaintBlockOrderLineField(formView, null);
        },

        /**
         * Descarta el form embebido sin rollback: las líneas borradas vía RPC ya no existen
         * en BD y rollback provoca MissingError al re-leer sale.order.line(id).
         */
        _quoterDiscardEmbeddedIfDirty: function () {
            const formView = this.__quoterEmbedForm;
            if (!formView || !formView.model || !formView.handle) {
                return Promise.resolve();
            }
            const self = this;
            const dirty = self._quoterEmbeddedHasUnsavedChanges(formView);
            const hadServerUnlink = !!self.__quoterHadServerLineUnlink;
            const finish = function () {
                self.__quoterHadServerLineUnlink = false;
                self._quoterDestroyEmbedForm();
            };
            if (!dirty && !hadServerUnlink) {
                finish();
                return Promise.resolve();
            }
            const model = formView.model;
            if (hadServerUnlink) {
                const removed = self.__quoterRemovedLineResIds || [];
                if (removed.length) {
                    self._quoterPurgeGhostLinesByResIds(model, removed);
                }
                const blockDp = model.get(formView.handle);
                if (blockDp && blockDp.data && blockDp.data.order_line_ids) {
                    self._quoterSanitizeListDatapoint(
                        model,
                        blockDp.data.order_line_ids.id
                    );
                }
                finish();
                return Promise.resolve();
            }
            const dropEmbedded = function () {
                if (typeof model.discardChanges === "function") {
                    try {
                        model.discardChanges(formView.handle, { rollback: false });
                    } catch (err) {
                        if (window.console && console.error) {
                            console.error("[quoter] discard embedded form failed:", err);
                        }
                    }
                }
                return Promise.resolve();
            };
            return dropEmbedded()
                .then(function () {
                    return self._quoterRefreshEmbeddedDataAfterSave(formView);
                })
                .catch(function (err) {
                    if (window.console && console.error) {
                        console.error("[quoter] discard embedded form failed:", err);
                    }
                })
                .finally(finish);
        },

        /**
         * Panel visible mínimo: confirma que el slot y el widget o2m se ejecutan.
         * Desactivá con QUOTER_AREA_EMBED_SIMPLE_PROBE = false.
         */
        _quoterMountSimpleProbe: function ($wrap, lines, targetId) {
            if (this.__quoterEmbedForm) {
                this.__quoterEmbedForm.destroy();
                this.__quoterEmbedForm = null;
            }
            this.__quoterEmbedActiveDatapointId = targetId || null;
            const $body = $wrap.find(".o_quoter_area_block_form_body");
            if (!$body.length) {
                return;
            }
            const fc = getFormControllerFromField(this);
            let listMeta = "(sin lista en model)";
            if (fc && this.value && this.value.id) {
                const dp = fc.model.get(this.value.id);
                if (dp && dp.type === "list") {
                    listMeta = JSON.stringify({
                        count: dp.count,
                        res_ids_len: (dp.res_ids || []).length,
                        dataLen: (dp.data || []).length,
                    });
                }
            }
            let recordSnap = "(sin targetId o sin registro)";
            if (targetId && fc) {
                const rec = fc.model.get(targetId);
                if (rec && rec.data) {
                    recordSnap =
                        "area_id=" + String(rec.data.area_id) + ", state=" + String(rec.data.state);
                }
            }
            const orderName = this.record && this.record.data && this.record.data.name;
            $body.html(
                '<div class="alert alert-success mb-0 o_quoter_area_embed_probe" role="status">' +
                    "<strong>PRUEBA — slot cotización por área</strong><br/>" +
                    "Si ves esto, el JS y el contenedor <code>.o_quoter_area_block_form_body</code> funcionan.<br/>" +
                    "<code>QUOTER_AREA_EMBED_SIMPLE_PROBE</code> está en <strong>true</strong>; " +
                    "ponela en <strong>false</strong> en <code>quoter_area_block_embed.js</code> para el form embebido.<br/><br/>" +
                    "Pedido (name): " +
                    String(orderName) +
                    "<br/>" +
                    "is_quotation: " +
                    String(this.record && this.record.data && this.record.data.is_quotation) +
                    "<br/>" +
                    "Líneas en value.data: " +
                    String((lines || []).length) +
                    "<br/>" +
                    "Lista BasicModel: " +
                    listMeta +
                    "<br/>" +
                    "targetId: " +
                    String(targetId) +
                    "<br/>" +
                    "Muestra 1er registro: " +
                    recordSnap +
                    "</div>"
            );
        },

        destroy: function () {
            if (this.$el) {
                this.$el.removeData("quoterAreaBlockO2M");
            }
            this._quoterDestroyEmbedForm();
            return this._super.apply(this, arguments);
        },

        reset: function (record, ev, fieldChanged) {
            const self = this;
            const def = this._super.apply(this, arguments);
            return Promise.resolve(def).then(function () {
                if (!self._quoterUseEmbedAreaBlocks()) {
                    return;
                }
                if (self.__quoterEmbedActiveDatapointId) {
                    const lines = self.value.data || [];
                    const fc = getFormControllerFromField(self);
                    const still = lines.some(function (line) {
                        return quoterListRowLocalId(line) === self.__quoterEmbedActiveDatapointId;
                    });
                    const stillByResId =
                        !still &&
                        !!self.__quoterEmbedActiveResId &&
                        !!fc &&
                        lines.some(function (line) {
                            const localId = quoterListRowLocalId(line);
                            const row = localId ? fc.model.get(localId) : null;
                            return row && row.res_id === self.__quoterEmbedActiveResId;
                        });
                    if (!still && !stillByResId) {
                        const activeId = self.__quoterEmbedActiveDatapointId;
                        const activeRow =
                            activeId && fc && fc.model.localData
                                ? fc.model.localData[activeId]
                                : null;
                        if (activeRow && activeRow.res_id && self.__quoterEmbedForm) {
                            return;
                        }
                        self._quoterDestroyEmbedForm();
                    }
                }
            });
        },

        /**
         * Si la lista del x2many tiene filas en el BasicModel pero `value.data` está vacío
         * (p. ej. lista oculta con display:none), fuerza /read vía API interna de Odoo.
         */
        _quoterReloadAreaBlockListFromModel: function () {
            const fc = getFormControllerFromField(this);
            if (!fc || !fc.model || !this.value || !this.value.id) {
                return Promise.resolve();
            }
            const model = fc.model;
            const listId = this.value.id;
            const listDp = quoterGetRawListDatapoint(model, listId);
            if (!listDp) {
                return Promise.resolve();
            }
            const self = this;
            if (typeof model.reload !== "function") {
                return Promise.resolve();
            }
            return model.reload(listId).then(function () {
                const fresh = model.get(listId);
                if (self.renderer && self.renderer.updateState && fresh) {
                    return self.renderer.updateState(fresh, {
                        addCreateLine: self._hasCreateLine(),
                        addTrashIcon: self._hasTrashIcon(),
                        columnInvisibleFields: self._evalColumnInvisibleFields(),
                        keepWidths: true,
                    });
                }
            });
        },

        /**
         * Mantiene el formulario embebido: primer bloque si no hay selección válida.
         */
        _quoterEnsureEmbedVisible: function () {
            if (!this._quoterUseEmbedAreaBlocks()) {
                return Promise.resolve();
            }
            const $wrap = this.$el && this.$el.closest(".o_quoter_area_blocks_embed");
            if (!$wrap || !$wrap.length) {
                return Promise.resolve();
            }
            if (!quoterAreaEmbedTabAllowsUpdate($wrap)) {
                return Promise.resolve();
            }
            let lines = this.value && this.value.data;
            if ((!lines || !lines.length) && this.value && this.value.id) {
                const fc = getFormControllerFromField(this);
                if (fc) {
                    const listDp = fc.model.get(this.value.id);
                    if (listDp && listDp.data && listDp.data.length) {
                        lines = listDp.data;
                    }
                }
            }
            if (lines && lines.length) {
                this.__quoterO2mReloadAttempts = 0;
            }
            if (!lines || !lines.length) {
                const fc2 = getFormControllerFromField(this);
                let listCount = 0;
                if (fc2 && this.value && this.value.id) {
                    const dp = fc2.model.get(this.value.id);
                    if (dp && dp.type === "list") {
                        listCount = dp.count || 0;
                        if (!listCount && dp.res_ids && dp.res_ids.length) {
                            listCount = dp.res_ids.length;
                        }
                    }
                }
                if (listCount > 0 && (this.__quoterO2mReloadAttempts || 0) < 3) {
                    this.__quoterO2mReloadAttempts = (this.__quoterO2mReloadAttempts || 0) + 1;
                    const self = this;
                    const reloadDef = this._quoterReloadAreaBlockListFromModel()
                        .then(function () {
                            return self._quoterEnsureEmbedVisible();
                        })
                        .then(function () {
                            self.__quoterO2mReloadAttempts = 0;
                        });
                    return quoterAttachCatch(reloadDef, function (err) {
                            if (window.console && console.error) {
                                console.error("[quoter] reload list failed:", err);
                            }
                            self.__quoterO2mReloadAttempts = 0;
                            self._quoterDestroyEmbedForm();
                        });
                }
                this.__quoterO2mReloadAttempts = 0;
                this._quoterDestroyEmbedForm();
                return Promise.resolve();
            }
            const $b = $wrap.find(".o_quoter_area_block_form_body");
            const $formRoot = $wrap.closest("form, .o_form_view");
            let targetId = null;
            const tabAreaId = quoterActiveTabAreaIdInForm($formRoot);
            if (tabAreaId) {
                targetId = quoterResolveLineByAreaId(lines, this, tabAreaId);
            }
            if (!targetId) {
                targetId = quoterResolveLineDatapointId(
                    lines,
                    this,
                    this.__quoterEmbedActiveDatapointId,
                    this.__quoterEmbedActiveResId
                );
            }
            if (!targetId) {
                this._quoterDestroyEmbedForm();
                return Promise.resolve();
            }
            if (this.__quoterMountPendingPromise && this.__quoterMountPendingTargetId === targetId) {
                return this.__quoterMountPendingPromise;
            }
            if (
                this.__quoterEmbedForm &&
                $b.children().length &&
                this.__quoterEmbedActiveDatapointId === targetId
            ) {
                return Promise.resolve();
            }
            if (this.__quoterEmbedForm && !$b.children().length) {
                this.__quoterEmbedForm.destroy();
                this.__quoterEmbedForm = null;
            }
            if (QUOTER_AREA_EMBED_SIMPLE_PROBE) {
                return Promise.resolve(this._quoterMountSimpleProbe($wrap, lines, targetId));
            }
            return Promise.resolve(this._quoterMountEmbedForDatapoint(targetId));
        },

        _quoterMountEmbedForDatapoint: function (id, options) {
            options = options || {};
            if (QUOTER_AREA_EMBED_SIMPLE_PROBE) {
                return Promise.resolve();
            }
            const self = this;
            const fc = getFormControllerFromField(this);
            const $wrap = this.$el.closest(".o_quoter_area_blocks_embed");
            const $body = $wrap.find(".o_quoter_area_block_form_body");
            this.__quoterMountRequestId = (this.__quoterMountRequestId || 0) + 1;
            const mountReqId = this.__quoterMountRequestId;
            this.__quoterMountPendingTargetId = id;

            if (!fc || !$body.length) {
                return Promise.resolve();
            }

            const context = this.record.getContext(Object.assign({}, this.recordParams));
            const fieldsView = this.attrs.views && this.attrs.views.form;
            if (!fieldsView) {
                return Promise.resolve();
            }

            if (!options.skipDestroy) {
                this._quoterDestroyEmbedForm();
            }
            this.__quoterEmbedActiveDatapointId = id;

            const record = fc.model.get(id, { raw: true });
            if (!record) {
                return Promise.resolve();
            }
            return fc.model.mutex.getUnlockedDef().then(function () {
                if (self.__quoterMountRequestId !== mountReqId) {
                    return;
                }
                const refinedContext = {};
                if (context) {
                    Object.keys(context).forEach(function (key) {
                        if (key.indexOf("_view_ref") === -1) {
                            refinedContext[key] = context[key];
                        }
                    });
                }
                const parentFc = getFormControllerFromField(self);
                const parentMode =
                    parentFc && parentFc.mode ? parentFc.mode : self.mode || "readonly";
                const embedMode =
                    record.res_id && parentMode === "readonly" ? "readonly" : "edit";
                const FormViewClass = view_registry.get("form");
                const formview = new FormViewClass(fieldsView, {
                    modelName: self.field.relation,
                    context: refinedContext,
                    ids: record.res_id ? [record.res_id] : [],
                    currentId: record.res_id || undefined,
                    index: 0,
                    mode: embedMode,
                    footerToButtons: true,
                    default_buttons: true,
                    withControlPanel: false,
                    model: fc.model,
                    parentID: self.value.id,
                    recordID: record.id,
                    isFromFormViewDialog: false,
                    editable: !self.hasReadonlyModifier,
                });
                const controllerDef = formview
                    .getController(fc)
                    .then(function (formView) {
                        if (self.__quoterMountRequestId !== mountReqId) {
                            formView.destroy();
                            return;
                        }
                        self.__quoterEmbedForm = formView;
                        formView.__quoterAreaBlockHostField = self;
                        quoterPatchEmbedFormPushState(formView, self);
                        return formView.appendTo($body[0]).then(function () {
                            if (self.__quoterMountRequestId !== mountReqId) {
                                formView.destroy();
                                return;
                            }
                            quoterSanitizeEmbedFormButtons($body);
                            quoterPatchEmbedComplexityLevelLabel($body, formView);
                            quoterBindEmbedComplexityLevelConfirm(formView, self);
                            if (embedMode === "edit") {
                                quoterEnsureParentSaleOrderEditMode(self);
                            }
                        });
                    });
                const pending = quoterAttachCatch(controllerDef, function (err) {
                        if (window.console && console.error) {
                            console.error("[quoter] formulario embebido bloque área:", err);
                        }
                    });
                self.__quoterMountPendingPromise = pending;
                return Promise.resolve(pending).finally(function () {
                    if (self.__quoterMountPendingPromise === pending) {
                        self.__quoterMountPendingPromise = null;
                        self.__quoterMountPendingTargetId = null;
                    }
                });
            }, function (err) {
                if (window.console && console.error) {
                    console.error("[quoter] mutex/get unlocked failed:", err);
                }
            });
        },

        _quoterIsBlockOrderLineField: function () {
            if (this.name !== "order_line_ids") {
                return false;
            }
            if (
                !this.$el.closest(
                    ".o_quoter_area_blocks_embed, .o_quoter_area_block_form_body"
                ).length
            ) {
                return false;
            }
            return true;
        },

        /**
         * Borrado local estándar Odoo (sin RPC). No usar _super en callbacks async.
         */
        _quoterRemoveBlockOrderLineLocalFallback: function (recordId) {
            this._setValue({
                operation: this.isMany2Many ? "FORGET" : "DELETE",
                ids: [recordId],
            });
        },

        /**
         * Borrado inmediato en servidor (icono papelera del bloque embebido).
         */
        _quoterRemoveBlockOrderLineRecord: function (recordId) {
            const host = this._quoterGetAreaBlocksHostField();
            const formView = host && host.__quoterEmbedForm;
            const model = formView && formView.model;
            if (!host || !model || !formView) {
                return Promise.resolve(false);
            }
            const localId = recordId;
            const row = model.get(localId, {raw: true});
            const blockDp = model.get(formView.handle, {raw: true});
            if (!row || !row.res_id || !blockDp || !blockDp.res_id) {
                return Promise.resolve(false);
            }
            const blockResId = blockDp.res_id;
            const lineResId = row.res_id;
            const blockDatapointId = formView.handle;
            const self = this;
            const resIdsToPurge = host._quoterCollectRelatedLineResIdsForUnlink(
                model,
                localId,
                formView
            );
            if (host.__quoterAdjHourRpcTimer) {
                clearTimeout(host.__quoterAdjHourRpcTimer);
                host.__quoterAdjHourRpcTimer = null;
            }
            host.__quoterHadServerLineUnlink = true;
            resIdsToPurge.forEach(function (rid) {
                host._quoterTrackRemovedLineResId(rid);
            });
            const blockDpForList = quoterGetRawDatapoint(model, formView.handle);
            const listIdForOpt = quoterResolveO2mListId(
                blockDpForList && blockDpForList.data && blockDpForList.data.order_line_ids
            );
            const localIdsToDrop = [localId].concat(
                host._quoterCollectLocalLineIdsForResIds(
                    model,
                    listIdForOpt,
                    resIdsToPurge
                )
            );
            quoterEnsureParentSaleOrderEditMode(this);
            return host
                ._quoterOptimisticRemoveBlockLinesFromUI(
                    formView,
                    localIdsToDrop,
                    resIdsToPurge
                )
                .then(function () {
                    return self._rpc({
                        model: "quoter.sale.order.area",
                        method: "action_quoter_unlink_order_line",
                        args: [[blockResId], lineResId],
                    });
                })
                .then(function (serverResult) {
                    const payload = quoterNormalizeServerLineSyncResult(serverResult);
                    const allRemoved = quoterUniqueIntIds(
                        resIdsToPurge.concat(payload.removed_ids || [])
                    );
                    allRemoved.forEach(function (rid) {
                        host._quoterTrackRemovedLineResId(rid);
                    });
                    host._quoterPurgeGhostLinesByResIds(model, allRemoved);
                    host._quoterPruneLocalLineDatapoint(model, localId, lineResId);
                    host._quoterSanitizeAllModelLists(model);
                    if (payload.has_line_ids) {
                        return host._quoterRefreshBlockLinesAfterDelete(
                            blockDatapointId,
                            payload,
                            self
                        );
                    }
                    return host._quoterFetchBlockOrderLineSync(blockResId).then(function (sync) {
                        sync.removed_ids = quoterUniqueIntIds(
                            allRemoved.concat(sync.removed_ids || [])
                        );
                        return host._quoterRefreshBlockLinesAfterDelete(
                            blockDatapointId,
                            sync,
                            self
                        );
                    });
                })
                .then(function () {
                    return true;
                })
                .guardedCatch(function (err) {
                    if (window.console && console.error) {
                        console.error("[quoter] unlink order line failed:", err);
                    }
                    return host
                        ._quoterResyncEmbeddedBlockLinesFromServer(
                            blockDatapointId,
                            blockResId
                        )
                        .then(function () {
                            throw err;
                        });
                });
        },

        _quoterGetAreaBlocksHostField: function () {
            const $embed = this.$el.closest(".o_quoter_area_blocks_embed");
            if ($embed.length) {
                const fromData = $embed
                    .find('.o_field_one2many[name="quoter_area_block_ids"]')
                    .data("quoterAreaBlockO2M");
                if (fromData) {
                    return fromData;
                }
            }
            const $blockBody = this.$el.closest(".o_quoter_area_block_form_body");
            if ($blockBody.length) {
                const embedCtrl = getFormControllerFromField(this);
                if (embedCtrl && embedCtrl.__quoterAreaBlockHostField) {
                    return embedCtrl.__quoterAreaBlockHostField;
                }
                const $wrap = $blockBody.closest(".o_quoter_area_blocks_embed");
                if ($wrap.length) {
                    const fromWrap = $wrap
                        .find('.o_field_one2many[name="quoter_area_block_ids"]')
                        .data("quoterAreaBlockO2M");
                    if (fromWrap) {
                        return fromWrap;
                    }
                }
            }
            const fc = getFormControllerFromField(this);
            if (fc && fc.renderer) {
                const $wrap = $(fc.renderer.el).find(".o_quoter_area_blocks_embed");
                return findQuoterAreaBlockField(fc.renderer, $wrap);
            }
            return null;
        },

        _onEditLine: function (ev) {
            if (this._quoterIsBlockOrderLineField()) {
                quoterEnsureParentSaleOrderEditMode(this);
                quoterMarkParentSaleOrderDirty(this);
            }
            return this._super.apply(this, arguments);
        },

        _onAddRecord: function (ev) {
            if (this._quoterIsBlockOrderLineField()) {
                quoterEnsureParentSaleOrderEditMode(this);
            }
            return this._super.apply(this, arguments);
        },

        _quoterScheduleFormulaVolumeRpc: function (lineLocalId, volume) {
            const host = this._quoterGetAreaBlocksHostField();
            const formView = host && host.__quoterEmbedForm;
            if (!host || !formView || !formView.model || !lineLocalId) {
                return;
            }
            const row = quoterGetRawDatapoint(formView.model, lineLocalId);
            if (!row || !row.data || row.data.quoter_formula_is_fixed) {
                return;
            }
            const resId = row.res_id;
            if (typeof resId !== "number" || resId <= 0) {
                return;
            }
            const lw = host._quoterFindBlockOrderLineListWidget
                ? host._quoterFindBlockOrderLineListWidget()
                : null;
            const domHarvest = host._quoterHarvestFormulaVolumeFromDom
                ? host._quoterHarvestFormulaVolumeFromDom(lw, formView)
                : {};
            let payloadVol = volume;
            if (
                (payloadVol === undefined || payloadVol === null) &&
                domHarvest[resId] !== undefined &&
                domHarvest[resId] !== null &&
                !isNaN(domHarvest[resId])
            ) {
                payloadVol = domHarvest[resId];
            }
            if (payloadVol === undefined || payloadVol === null) {
                const merged = this._quoterMergeLineRowData(row);
                payloadVol = merged.quoter_formula_volume;
            }
            if (host.__quoterFormulaVolRpcTimer) {
                clearTimeout(host.__quoterFormulaVolRpcTimer);
            }
            const capturedVol = payloadVol;
            host.__quoterFormulaVolRpcTimer = setTimeout(function () {
                host.__quoterFormulaVolRpcTimer = null;
                host
                    ._rpc({
                        model: "sale.order.line",
                        method: "quoter_persist_formula_volume_batch",
                        args: [[{id: resId, quoter_formula_volume: capturedVol}]],
                    })
                    .then(function () {
                        return host._rpc({
                            model: "sale.order.line",
                            method: "read",
                            args: [
                                [resId],
                                ["quoter_formula_volume"].concat(
                                    QUOTER_RANGE_HOUR_FIELD_NAMES,
                                    ["quoter_total_hours", "price_unit"]
                                ),
                            ],
                        });
                    })
                    .then(function (rows) {
                        host._quoterApplyAdjustmentHoursReadToEmbed(formView, rows);
                        host._quoterStripFormulaVolumeFieldChanges(formView);
                    })
                    .catch(function (err) {
                        if (window.console && console.warn) {
                            console.warn("[quoter] auto-save formula volume failed:", err);
                        }
                    });
            }, 100);
        },

        _quoterScheduleAdjustmentHoursRpc: function (lineLocalId, changes) {
            const host = this._quoterGetAreaBlocksHostField();
            const formView = host && host.__quoterEmbedForm;
            if (!host || !formView || !formView.model || !lineLocalId) {
                return;
            }
            const row = quoterGetRawDatapoint(formView.model, lineLocalId);
            if (!row || !row.data || !row.data.quoter_is_adjustment_line) {
                return;
            }
            const resId = row.res_id;
            if (typeof resId !== "number" || resId <= 0) {
                return;
            }
            const data = Object.assign({}, row.data, row._changes || {}, changes || {});
            const item = {id: resId};
            let hasHour = false;
            QUOTER_RANGE_HOUR_FIELD_NAMES.forEach(function (key) {
                if (data[key] !== undefined && data[key] !== null) {
                    item[key] = data[key];
                    hasHour = true;
                }
            });
            if (!hasHour) {
                return;
            }
            if (host.__quoterAdjHourRpcTimer) {
                clearTimeout(host.__quoterAdjHourRpcTimer);
            }
            host.__quoterAdjHourRpcTimer = setTimeout(function () {
                host.__quoterAdjHourRpcTimer = null;
                host
                    ._rpc({
                        model: "sale.order.line",
                        method: "quoter_persist_adjustment_line_hours_batch",
                        args: [[item]],
                    })
                    .then(function () {
                        return host._rpc({
                            model: "sale.order.line",
                            method: "read",
                            args: [
                                [resId],
                                QUOTER_RANGE_HOUR_FIELD_NAMES.concat([
                                    "quoter_total_hours",
                                    "price_unit",
                                ]),
                            ],
                        });
                    })
                    .then(function (rows) {
                        host._quoterApplyAdjustmentHoursReadToEmbed(formView, rows);
                        host._quoterStripAdjustmentHourFieldChanges(formView);
                    })
                    .catch(function (err) {
                        if (window.console && console.warn) {
                            console.warn("[quoter] auto-save adjustment hours failed:", err);
                        }
                    });
            }, 350);
        },

        _onFieldChanged: function (event) {
            const res = this._super.apply(this, arguments);
            if (
                this._quoterIsBlockOrderLineField() &&
                event &&
                event.data &&
                event.data.changes
            ) {
                quoterEnsureParentSaleOrderEditMode(this);
                quoterMarkParentSaleOrderDirty(this);
                const changes = event.data.changes;
                const hourTouched = QUOTER_RANGE_HOUR_FIELD_NAMES.some(function (key) {
                    return Object.prototype.hasOwnProperty.call(changes, key);
                });
                if (hourTouched && event.data.dataPointID) {
                    this._quoterScheduleAdjustmentHoursRpc(
                        event.data.dataPointID,
                        changes
                    );
                }
                if (
                    Object.prototype.hasOwnProperty.call(changes, "quoter_formula_volume") &&
                    event.data.dataPointID
                ) {
                    let mergedVol = changes.quoter_formula_volume;
                    if (mergedVol === undefined || mergedVol === null) {
                        const hostField = this._quoterGetAreaBlocksHostField
                            ? this._quoterGetAreaBlocksHostField()
                            : null;
                        const embedForm =
                            hostField && hostField.__quoterEmbedForm
                                ? hostField.__quoterEmbedForm
                                : null;
                        if (embedForm && embedForm.model) {
                            const volRow = quoterGetRawDatapoint(
                                embedForm.model,
                                event.data.dataPointID
                            );
                            if (volRow) {
                                mergedVol =
                                    this._quoterMergeLineRowData(volRow).quoter_formula_volume;
                            }
                        }
                    }
                    this._quoterScheduleFormulaVolumeRpc(
                        event.data.dataPointID,
                        mergedVol
                    );
                }
            }
            return res;
        },

        _removeRecord: function (recordId) {
            if (!this._quoterIsBlockOrderLineField()) {
                return this._super.apply(this, arguments);
            }
            const self = this;
            return this._quoterRemoveBlockOrderLineRecord(recordId).then(function (handled) {
                if (!handled) {
                    self._quoterRemoveBlockOrderLineLocalFallback(recordId);
                }
            });
        },

        _onRemoveRecord: function (ev) {
            if (!this._quoterIsBlockOrderLineField()) {
                return this._super.apply(this, arguments);
            }
            ev.stopPropagation();
            if (this._canQuickEdit && this.isReadonly) {
                return this._super.apply(this, arguments);
            }
            const self = this;
            const recordId = ev.data.id;
            return this._quoterRemoveBlockOrderLineRecord(recordId).then(function (handled) {
                if (!handled) {
                    self._quoterRemoveBlockOrderLineLocalFallback(recordId);
                }
            });
        },

        _quoterClearBlockLineListChanges: function (model, formView) {
            if (!model || !formView || !formView.handle) {
                return;
            }
            const blockDp = quoterGetRawDatapoint(model, formView.handle);
            if (blockDp && blockDp.data && blockDp.data.order_line_ids) {
                this._quoterClearLineListPendingChanges(
                    model,
                    quoterResolveO2mListId(blockDp.data.order_line_ids)
                );
            }
        },

        /**
         * Quita del BasicModel la fila ya borrada en servidor (evita lecturas a res_id inexistente).
         */
        _quoterPruneLocalLineDatapoint: function (model, localId, lineResId) {
            if (!model || !localId) {
                return;
            }
            const rec = quoterGetRawDatapoint(model, localId);
            if (rec && rec.id) {
                delete model.localData[rec.id];
            }
            if (!lineResId) {
                return;
            }
            const walk = function (listDatapointId) {
                const dp = quoterGetRawListDatapoint(model, listDatapointId);
                if (!dp || !Array.isArray(dp.data)) {
                    return;
                }
                dp.data = dp.data.filter(function (lid) {
                    const row = model.localData[lid];
                    return !!(row && row.res_id !== lineResId);
                });
                if (Array.isArray(dp.res_ids)) {
                    dp.res_ids = dp.res_ids.filter(function (rid) {
                        return rid !== lineResId;
                    });
                }
                if (dp._cache) {
                    Object.keys(dp._cache).forEach(function (cacheKey) {
                        if (Number(cacheKey) === lineResId) {
                            delete dp._cache[cacheKey];
                            return;
                        }
                        const dpId = dp._cache[cacheKey];
                        const row = dpId && model.localData[dpId];
                        if (row && row.res_id === lineResId) {
                            delete dp._cache[cacheKey];
                        }
                    });
                }
                if (Array.isArray(dp.orderedResIDs)) {
                    dp.orderedResIDs = dp.orderedResIDs.filter(function (rid) {
                        return rid !== lineResId;
                    });
                }
                dp.orderedResIDs = null;
                dp._changes = [];
            };
            walk(this.value && this.value.id);
            const formView = this.__quoterEmbedForm;
            if (formView && formView.handle) {
                const blockDp = quoterGetRawDatapoint(model, formView.handle);
                if (blockDp && blockDp.data && blockDp.data.order_line_ids) {
                    walk(quoterResolveO2mListId(blockDp.data.order_line_ids));
                }
            }
            const fc = getFormControllerFromField(this);
            if (fc && fc.handle) {
                const order = quoterGetRawDatapoint(model, fc.handle);
                if (order && order.data && order.data.order_line) {
                    walk(quoterResolveO2mListId(order.data.order_line));
                }
            }
        },

        _onOpenRecord: function (ev) {
            if (!this._quoterUseEmbedAreaBlocks()) {
                return this._super.apply(this, arguments);
            }
            ev.stopPropagation();
            if (QUOTER_AREA_EMBED_SIMPLE_PROBE) {
                const $wrap = this.$el.closest(".o_quoter_area_blocks_embed");
                const lines = (this.value && this.value.data) || [];
                return Promise.resolve(this._quoterMountSimpleProbe($wrap, lines, ev.data.id));
            }
            return this._quoterMountEmbedForDatapoint(ev.data.id);
        },
    });

    return {
        getOrderedBlockRows: getOrderedBlockRows,
        bindQuoterAreaTabNav: bindQuoterAreaTabNav,
        syncEmbedToActiveTab: syncEmbedToActiveTab,
        switchEmbedToArea: switchEmbedToArea,
    };
});

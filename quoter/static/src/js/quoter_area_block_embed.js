odoo.define("quoter.area_block_embed", function (require) {
    "use strict";

    const FormRenderer = require("web.FormRenderer");
    const FormController = require("web.FormController");
    const FieldOne2Many = require("web.relational_fields").FieldOne2Many;
    const view_registry = require("web.view_registry");
    const core = require("web.core");
    const quoterPreserveActive = require("quoter.preserve_active_record");

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
            if (custom) {
                $lbl.text(custom);
            }
        });
        $body.find(".o_quoter_block_complexity_level").each(function () {
            const $inp = $(this);
            const $wrap = $inp.closest(".o_wrap_field, .o_row, tr");
            const $lbl = $wrap.find("label").first();
            if (custom && $lbl.length) {
                $lbl.text(custom);
            }
        });
    }

    function quoterSanitizeEmbedFormButtons($container) {
        if (!$container || !$container.length) {
            return;
        }
        $container.find(".o_form_button_create").remove();
        $container.find("button").each(function () {
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
            const prepBeforeSave = function () {
                if (embedForm) {
                    fieldW._quoterSanitizeEmbedModelBeforeSave(embedForm);
                }
                // No recargar desde servidor antes del flush: la línea borrada sigue en BD
                // hasta que se guarde el bloque y reaparecería en la grilla.
                return fieldW._quoterPurgeParentOrderLineGhostState(parentFc, {
                    reloadOrder: false,
                });
            };
            const prepAfterSave = function () {
                if (!embedForm) {
                    return fieldW._quoterPurgeParentOrderLineGhostState(parentFc);
                }
                return fieldW._quoterRefreshEmbeddedDataAfterSave(embedForm).then(function () {
                    return fieldW._quoterPurgeParentOrderLineGhostState(parentFc);
                });
            };
            return prepBeforeSave()
                .then(function () {
                    return fieldW._quoterSaveEmbeddedBeforeParent();
                })
                .then(prepAfterSave)
                .then(function () {
                    const removed = fieldW.__quoterRemovedLineResIds || [];
                    if (removed.length && embedForm && embedForm.model) {
                        fieldW._quoterPurgeGhostLinesByResIds(
                            embedForm.model,
                            removed
                        );
                    }
                    return fieldW._quoterPurgeParentOrderLineGhostState(parentFc, {
                        reloadOrder: true,
                    });
                })
                .then(runParentSave)
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

        _quoterDestroyEmbedForm: function () {
            if (this.__quoterEmbedForm) {
                this.__quoterEmbedForm.destroy();
                this.__quoterEmbedForm = null;
            }
            this.__quoterEmbedActiveDatapointId = null;
            this.__quoterEmbedActiveResId = null;
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

        _quoterClearLineListPendingChanges: function (model, listDatapointId) {
            if (!model || !listDatapointId) {
                return;
            }
            const listDp = model.get(listDatapointId);
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
            const listDp = model.get(listDatapointId);
            if (!listDp || listDp.type !== "list" || !Array.isArray(listDp.data)) {
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
                    return !row || !row.res_id || !idSet.has(row.res_id);
                });
                if (Array.isArray(listDp.res_ids)) {
                    listDp.res_ids = listDp.res_ids.filter(function (rid) {
                        return !idSet.has(rid);
                    });
                }
                if (Array.isArray(listDp._changes)) {
                    listDp._changes = listDp._changes.filter(function (chg) {
                        if (!chg || !chg.id) {
                            return true;
                        }
                        const row = model.get(chg.id);
                        return !row || !row.res_id || !idSet.has(row.res_id);
                    });
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
                const blockDp = model.get(formView.handle);
                scrubRecordChanges(blockDp);
                if (blockDp && blockDp.data && blockDp.data.order_line_ids) {
                    pruneList(model.get(blockDp.data.order_line_ids.id));
                }
            }
            const fc = getFormControllerFromField(this);
            if (fc && fc.handle) {
                const order = model.get(fc.handle);
                scrubRecordChanges(order);
                if (order && order.data && order.data.order_line) {
                    pruneList(model.get(order.data.order_line.id));
                }
            }
            if (this.value && this.value.id) {
                pruneList(model.get(this.value.id));
            }
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
            const blockDp = model.get(formView.handle);
            if (blockDp && blockDp.data && blockDp.data.order_line_ids) {
                this._quoterResyncLineListResIdsFromData(
                    model,
                    blockDp.data.order_line_ids.id
                );
            }
            const fc = getFormControllerFromField(this);
            if (fc && fc.handle) {
                const order = model.get(fc.handle);
                if (order && order.data && order.data.order_line) {
                    this._quoterResyncLineListResIdsFromData(model, order.data.order_line.id);
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
            const formView = this.__quoterEmbedForm;
            if (!formView || !formView.model || !formView.handle) {
                return Promise.resolve();
            }
            const block = formView.model.get(formView.handle, {raw: true});
            if (!block || !block.res_id) {
                return Promise.resolve();
            }
            if (formView.mode === "readonly") {
                return Promise.resolve();
            }
            this._quoterSanitizeEmbedModelBeforeSave(formView);
            const removed = this.__quoterRemovedLineResIds || [];
            const dirty = this._quoterEmbeddedHasUnsavedChanges(formView);
            if (!dirty && removed.length) {
                return this._quoterRefreshEmbeddedDataAfterSave(formView);
            }
            return this._quoterInvokeEmbeddedFormSave(formView);
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
            const savePromise = Promise.resolve(
                formView.saveRecord(formView.handle, {
                    stayInEdit: true,
                    reload: false,
                    savePoint: false,
                    viewType: "form",
                })
            )
                .then(function (changedFields) {
                    const rec = formView.model.get(formView.handle);
                    self._quoterSyncEmbeddedRecordLink(rec);
                    return self._quoterRefreshEmbeddedDataAfterSave(formView).then(function () {
                        return changedFields;
                    });
                })
                .catch(function (err) {
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
            const order = model.get(fc.handle);
            if (!order || !order.data || !order.data.order_line) {
                return Promise.resolve();
            }
            const listId = order.data.order_line.id;
            const list = model.get(listId);
            const removed = new Set(this.__quoterRemovedLineResIds || []);
            if (list && removed.size) {
                this._quoterPurgeGhostLinesByResIds(model, Array.from(removed));
            }
            if (options.reloadOrder === false || typeof model.reload !== "function") {
                return Promise.resolve();
            }
            return model.reload(fc.handle).then(function () {
                quoterPreserveActive.quoterPushSaleOrderFormState(fc);
            });
        },

        /**
         * Tras borrar una línea en servidor: recargar solo bloque + lista (no repintar value viejo).
         */
        _quoterRefreshBlockLinesAfterDelete: function (formView, lineListWidget) {
            const self = this;
            if (!formView || !formView.model || !formView.handle) {
                return Promise.resolve();
            }
            const model = formView.model;
            const reloads = [model.reload(formView.handle)];
            const blockDp = model.get(formView.handle);
            let listId = null;
            if (blockDp && blockDp.data && blockDp.data.order_line_ids) {
                listId = blockDp.data.order_line_ids.id;
                reloads.push(model.reload(listId));
            }
            return Promise.all(reloads).then(function () {
                const fc = getFormControllerFromField(self);
                return self._quoterPurgeParentOrderLineGhostState(fc, {
                    reloadOrder: false,
                }).then(function () {
                    if (!lineListWidget || !lineListWidget.renderer || !listId) {
                        return;
                    }
                    const listDp = model.get(listId);
                    if (!listDp) {
                        return;
                    }
                    return lineListWidget.renderer.updateState(listDp, {
                        addCreateLine: lineListWidget._hasCreateLine(),
                        addTrashIcon: lineListWidget._hasTrashIcon(),
                        keepWidths: true,
                    });
                });
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

        _quoterRefreshEmbeddedDataAfterSave: function (formView) {
            const self = this;
            const fc = getFormControllerFromField(this);
            if (!fc || !fc.model || !formView || !formView.handle) {
                return Promise.resolve();
            }
            const model = fc.model;
            const reloads = [];
            const hadDeletes = (self.__quoterRemovedLineResIds || []).length > 0;
            const pushReload = function (handle) {
                if (handle && model.get(handle) && typeof model.reload === "function") {
                    reloads.push(model.reload(handle));
                }
            };
            // Tras borrar líneas en servidor: no recargar el pedido completo (relee ids fantasma).
            if (!hadDeletes && fc.handle) {
                pushReload(fc.handle);
            }
            if (self.value && self.value.id) {
                pushReload(self.value.id);
            }
            pushReload(formView.handle);
            const blockDp = model.get(formView.handle);
            if (blockDp && blockDp.data && blockDp.data.order_line_ids) {
                pushReload(blockDp.data.order_line_ids.id);
            }
            if (hadDeletes && fc.handle) {
                const order = model.get(fc.handle);
                if (order && order.data && order.data.order_line) {
                    pushReload(order.data.order_line.id);
                }
            }
            if (!reloads.length) {
                return self._quoterRefreshParentOrderLineList();
            }
            return Promise.all(reloads).then(function () {
                return self._quoterRefreshParentOrderLineList().then(function () {
                    return self._quoterPurgeParentOrderLineGhostState(fc);
                });
            });
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
            const dropEmbedded = function () {
                // Odoo 15: discardChanges es síncrono (no devuelve Promise).
                if (typeof model.discardChanges === "function") {
                    model.discardChanges(formView.handle, { rollback: false });
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
            const list = model.get(listId);
            if (!list || list.type !== "list") {
                return Promise.resolve();
            }
            const self = this;
            // _readUngroupedList exige list._cache; si falta, usar reload público.
            if (!list._cache) {
                if (typeof model.reload === "function") {
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
                }
                return Promise.resolve();
            }
            if (typeof model._readUngroupedList !== "function") {
                return Promise.resolve();
            }
            return model._readUngroupedList(list).then(function () {
                if (typeof model._fetchX2ManysBatched === "function") {
                    return model._fetchX2ManysBatched(list);
                }
            }).then(function () {
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
            let targetId = quoterResolveLineDatapointId(
                lines,
                this,
                this.__quoterEmbedActiveDatapointId,
                this.__quoterEmbedActiveResId
            );
            if (!targetId) {
                this._quoterDestroyEmbedForm();
                return Promise.resolve();
            }
            if (this.__quoterMountPendingPromise && this.__quoterMountPendingTargetId === targetId) {
                return this.__quoterMountPendingPromise;
            }
            if (this.__quoterEmbedForm && $b.children().length && this.__quoterEmbedActiveDatapointId === targetId) {
                return Promise.resolve();
            }
            if (QUOTER_AREA_EMBED_SIMPLE_PROBE) {
                return Promise.resolve(this._quoterMountSimpleProbe($wrap, lines, targetId));
            }
            return Promise.resolve(this._quoterMountEmbedForDatapoint(targetId));
        },

        _quoterMountEmbedForDatapoint: function (id) {
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

            this._quoterDestroyEmbedForm();
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
                        quoterPatchEmbedFormPushState(formView, self);
                        return formView.appendTo($body[0]).then(function () {
                            if (self.__quoterMountRequestId !== mountReqId) {
                                formView.destroy();
                                return;
                            }
                            quoterSanitizeEmbedFormButtons($body);
                            quoterPatchEmbedComplexityLevelLabel($body, formView);
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
            const self = this;
            host.__quoterHadServerLineUnlink = true;
            host._quoterTrackRemovedLineResId(lineResId);
            quoterEnsureParentSaleOrderEditMode(this);
            return this._rpc({
                model: "quoter.sale.order.area",
                method: "action_quoter_unlink_order_line",
                args: [[blockResId], lineResId],
            }).then(function () {
                host._quoterPurgeGhostLinesByResIds(model, [lineResId]);
                self._quoterPruneLocalLineDatapoint(model, localId, lineResId);
                return host._quoterRefreshBlockLinesAfterDelete(formView, self).then(
                    function () {
                        return true;
                    }
                );
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
            const fc = getFormControllerFromField(this);
            if (fc && fc.renderer) {
                const $wrap = $(fc.renderer.el).find(".o_quoter_area_blocks_embed");
                return findQuoterAreaBlockField(fc.renderer, $wrap);
            }
            return null;
        },

        _onAddRecord: function (ev) {
            if (this._quoterIsBlockOrderLineField()) {
                quoterEnsureParentSaleOrderEditMode(this);
            }
            return this._super.apply(this, arguments);
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
            const blockDp = model.get(formView.handle);
            if (blockDp && blockDp.data && blockDp.data.order_line_ids) {
                this._quoterClearLineListPendingChanges(
                    model,
                    blockDp.data.order_line_ids.id
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
            const rec = model.get(localId);
            if (rec && rec.id) {
                delete model.localData[rec.id];
            }
            if (!lineResId) {
                return;
            }
            const walk = function (dp) {
                if (!dp || dp.type !== "list" || !Array.isArray(dp.data)) {
                    return;
                }
                dp.data = dp.data.filter(function (lid) {
                    const row = model.get(lid);
                    return !row || row.res_id !== lineResId;
                });
                if (Array.isArray(dp.res_ids)) {
                    dp.res_ids = dp.res_ids.filter(function (rid) {
                        return rid !== lineResId;
                    });
                }
                dp._changes = [];
            };
            walk(model.get(this.value && this.value.id));
            const formView = this.__quoterEmbedForm;
            if (formView && formView.handle) {
                const blockDp = model.get(formView.handle);
                if (blockDp && blockDp.data && blockDp.data.order_line_ids) {
                    walk(model.get(blockDp.data.order_line_ids.id));
                }
            }
            const fc = getFormControllerFromField(this);
            if (fc && fc.handle) {
                const order = model.get(fc.handle);
                if (order && order.data && order.data.order_line) {
                    walk(model.get(order.data.order_line.id));
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
});

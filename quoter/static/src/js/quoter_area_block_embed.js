odoo.define("quoter.area_block_embed", function (require) {
    "use strict";

    const FormRenderer = require("web.FormRenderer");
    const FormController = require("web.FormController");
    const FieldOne2Many = require("web.relational_fields").FieldOne2Many;
    const view_registry = require("web.view_registry");
    const core = require("web.core");

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

    function clearEmbedSlots($wrap) {
        const $body = $wrap.find(".o_quoter_area_block_form_body");
        const $footer = $wrap.find(".o_quoter_area_block_form_footer");
        $body.empty();
        $footer.empty();
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
            return Promise.resolve(fieldW._quoterFlushEmbeddedBlock())
                .then(function () {
                    return fieldW._quoterPurgeParentOrderLineGhostState(parentFc);
                })
                .then(runParentSave);
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
            return Promise.resolve(fieldW._quoterDiscardEmbeddedIfDirty()).then(runParentDiscard);
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

        _quoterFlushEmbeddedBlock: function () {
            const formView = this.__quoterEmbedForm;
            if (!formView || !formView.model || !formView.handle) {
                return Promise.resolve();
            }
            if (this.__quoterEmbedSavePendingPromise) {
                return this.__quoterEmbedSavePendingPromise;
            }
            const self = this;
            const savePromise = Promise.resolve(
                formView.saveRecord(formView.handle, {
                    stayInEdit: true,
                    reload: true,
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
                        console.error("[quoter] flush embedded block failed:", err);
                    }
                    throw err;
                })
                .finally(function () {
                    if (self.__quoterEmbedSavePendingPromise === savePromise) {
                        self.__quoterEmbedSavePendingPromise = null;
                    }
                });
            this.__quoterEmbedSavePendingPromise = savePromise;
            return savePromise;
        },

        _quoterSaveEmbeddedIfDirty: function () {
            const formView = this.__quoterEmbedForm;
            if (!formView || !this._quoterEmbeddedHasUnsavedChanges(formView)) {
                return Promise.resolve();
            }
            return this._quoterFlushEmbeddedBlock();
        },

        /**
         * El pedido padre carga order_line (oculto) y el bloque order_line_ids: misma tabla.
         * Tras guardar el bloque hay que recargar ambas listas en el BasicModel.
         */
        /**
         * El pedido tiene order_line invisible pero el BasicModel puede conservar
         * datapoints de líneas borradas en el bloque; limpiar antes de guardar el pedido.
         */
        _quoterPurgeParentOrderLineGhostState: function (fc) {
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
            if (list) {
                list._changes = [];
            }
            if (typeof model.reload === "function") {
                return model.reload(fc.handle);
            }
            return Promise.resolve();
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
            const pushReload = function (handle) {
                if (handle && model.get(handle) && typeof model.reload === "function") {
                    reloads.push(model.reload(handle));
                }
            };
            // Pedido primero (order_line oculto), luego listas del bloque.
            if (fc.handle) {
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
            if (!reloads.length) {
                return self._quoterRefreshParentOrderLineList();
            }
            return Promise.all(reloads).then(function () {
                return self._quoterRefreshParentOrderLineList().then(function () {
                    return self._quoterPurgeParentOrderLineGhostState(fc);
                });
            });
        },

        _quoterDiscardEmbeddedIfDirty: function () {
            const formView = this.__quoterEmbedForm;
            if (!formView || !formView.model || !formView.handle) {
                return Promise.resolve();
            }
            const self = this;
            let dirty = false;
            if (typeof formView.model.isDirty === "function") {
                dirty = !!formView.model.isDirty(formView.handle);
            } else {
                const rec = formView.model.get(formView.handle);
                dirty = !!(rec && rec._changes && Object.keys(rec._changes).length);
            }
            const finish = function () {
                self._quoterDestroyEmbedForm();
            };
            if (!dirty) {
                finish();
                return Promise.resolve();
            }
            return Promise.resolve(
                formView.model.discardChanges(formView.handle, { rollback: true })
            )
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
            const $footer = $wrap.find(".o_quoter_area_block_form_footer");
            $footer.empty();
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
            const $footer = $wrap.find(".o_quoter_area_block_form_footer");
            this.__quoterMountRequestId = (this.__quoterMountRequestId || 0) + 1;
            const mountReqId = this.__quoterMountRequestId;
            this.__quoterMountPendingTargetId = id;

            if (!fc || !$body.length || !$footer.length) {
                return Promise.resolve();
            }

            const onSaved = function (record) {
                self._quoterSyncEmbeddedRecordLink(record);
            };

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
                const readonlyParent = self.mode === "readonly";
                const FormViewClass = view_registry.get("form");
                const formview = new FormViewClass(fieldsView, {
                    modelName: self.field.relation,
                    context: refinedContext,
                    ids: record.res_id ? [record.res_id] : [],
                    currentId: record.res_id || undefined,
                    index: 0,
                    mode: record.res_id && readonlyParent ? "readonly" : "edit",
                    footerToButtons: false,
                    default_buttons: true,
                    withControlPanel: false,
                    model: fc.model,
                    parentID: self.value.id,
                    recordID: record.id,
                    isFromFormViewDialog: true,
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
                        $footer.empty();
                        formView._onSave = function (saveEv) {
                            saveEv.stopPropagation();
                            formView._disableButtons();
                            const saveDef = formView
                                .saveRecord(formView.handle, {
                                    stayInEdit: true,
                                    reload: true,
                                    savePoint: false,
                                    viewType: "form",
                                })
                                .then(function (changedFields) {
                                    const rec = formView.model.get(formView.handle);
                                    onSaved(rec);
                                    return self._quoterRefreshEmbeddedDataAfterSave(formView).then(
                                        function () {
                                            return changedFields;
                                        }
                                    );
                                })
                                .then(formView._enableButtons.bind(formView));
                            return quoterAttachCatch(saveDef, function (err) {
                                    formView._enableButtons();
                                    if (window.console && console.error) {
                                        console.error("[quoter] save embedded form failed:", err);
                                    }
                                });
                        };
                        formView._onDiscard = function (discardEv) {
                            discardEv.stopPropagation();
                            formView._disableButtons();
                            const discardDef = formView.model
                                .discardChanges(formView.handle, { rollback: true })
                                .then(function () {
                                    return self._quoterRefreshEmbeddedDataAfterSave(formView);
                                })
                                .then(formView._enableButtons.bind(formView));
                            return quoterAttachCatch(discardDef, function (err) {
                                    formView._enableButtons();
                                    if (window.console && console.error) {
                                        console.error("[quoter] discard embedded form failed:", err);
                                    }
                                });
                        };
                        return formView.appendTo($body[0]).then(function () {
                            if (self.__quoterMountRequestId !== mountReqId) {
                                formView.destroy();
                                return;
                            }
                            const $btnHolder = $("<div/>");
                            formView.renderButtons($btnHolder);
                            if ($btnHolder.children().length) {
                                $footer.append($btnHolder.contents());
                            }
                            formView.updateButtons();
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
            return (
                this.name === "order_line_ids" &&
                this.record &&
                this.record.model === "quoter.sale.order.area" &&
                this.$el.closest(".o_quoter_area_block_form_body").length
            );
        },

        _quoterGetAreaBlocksHostField: function () {
            const $embed = this.$el.closest(".o_quoter_area_blocks_embed");
            if (!$embed.length) {
                return null;
            }
            const host = $embed.find('.o_field_one2many[name="quoter_area_block_ids"]').data(
                "quoterAreaBlockO2M"
            );
            return host || null;
        },

        _onRemoveRecord: function (ev) {
            if (!this._quoterIsBlockOrderLineField()) {
                return this._super.apply(this, arguments);
            }
            const host = this._quoterGetAreaBlocksHostField();
            const formView = host && host.__quoterEmbedForm;
            const model = formView && formView.model;
            if (!model || !formView) {
                return this._super.apply(this, arguments);
            }
            const localId = ev.data.id;
            const row = model.get(localId, {raw: true});
            const blockDp = model.get(formView.handle, {raw: true});
            if (!blockDp || !blockDp.res_id || !row || !row.res_id) {
                return this._super.apply(this, arguments);
            }
            ev.stopPropagation();
            const blockResId = blockDp.res_id;
            return this._rpc({
                model: "quoter.sale.order.area",
                method: "action_quoter_unlink_order_line",
                args: [[blockResId], row.res_id],
            }).then(function () {
                return host._quoterRefreshEmbeddedDataAfterSave(formView);
            });
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

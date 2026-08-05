odoo.define("quoter.preserve_active_record", function (require) {
    "use strict";

    const FormController = require("web.FormController");

    const STORAGE_ID = "quoter_sale_order_active_id";
    const STORAGE_ACTION = "quoter_sale_order_action_id";
    const STORAGE_FLAG = "quoter_sale_order_is_quotation_session";
    const STORAGE_MODEL = "quoter_sale_order_active_model";
    const SALE_ORDER_MODEL = "sale.order";

    function quoterParseLocationHash() {
        const raw = window.location.hash.replace(/^#/, "");
        if (!raw) {
            return null;
        }
        try {
            return new URLSearchParams(raw);
        } catch (e) {
            return null;
        }
    }

    /**
     * Antes de cargar el web client: si F5 perdió id/action, restaurar la cotización abierta.
     */
    function quoterFixHashBeforeWebClientLoad() {
        const params = quoterParseLocationHash();
        if (!params) {
            return;
        }
        if (params.get("model") !== "sale.order" || params.get("view_type") !== "form") {
            return;
        }
        const urlId = params.get("id");
        if (urlId) {
            // La URL manda: no redirigir a un id viejo guardado en sessionStorage.
            sessionStorage.setItem(STORAGE_ID, urlId);
            sessionStorage.setItem(STORAGE_MODEL, SALE_ORDER_MODEL);
            return;
        }
        if (sessionStorage.getItem(STORAGE_FLAG) !== "1") {
            return;
        }
        if (sessionStorage.getItem(STORAGE_MODEL) !== SALE_ORDER_MODEL) {
            sessionStorage.removeItem(STORAGE_FLAG);
            sessionStorage.removeItem(STORAGE_ID);
            sessionStorage.removeItem(STORAGE_MODEL);
            return;
        }
        const storedId = sessionStorage.getItem(STORAGE_ID);
        if (!storedId) {
            return;
        }
        params.set("id", storedId);
        const storedAction = sessionStorage.getItem(STORAGE_ACTION);
        if (storedAction) {
            params.set("action", storedAction);
        }
        window.location.replace(
            window.location.pathname +
                window.location.search +
                "#" +
                params.toString()
        );
    }

    quoterFixHashBeforeWebClientLoad();

    function quoterRememberQuotationForm(controller) {
        if (!controller || controller.modelName !== "sale.order" || !controller.handle) {
            return;
        }
        const rec = controller.model.get(controller.handle, {raw: true});
        if (!rec || !rec.data) {
            return;
        }
        if (!rec.data.is_quotation) {
            sessionStorage.removeItem(STORAGE_FLAG);
            sessionStorage.removeItem(STORAGE_MODEL);
            return;
        }
        if (!rec.res_id) {
            return;
        }
        sessionStorage.setItem(STORAGE_FLAG, "1");
        sessionStorage.setItem(STORAGE_MODEL, SALE_ORDER_MODEL);
        sessionStorage.setItem(STORAGE_ID, String(rec.res_id));
        if (controller.action && controller.action.id) {
            sessionStorage.setItem(STORAGE_ACTION, String(controller.action.id));
        }
    }

    /**
     * Sincroniza id de cotización en la URL (F5 / compartir enlace).
     */
    function quoterPushSaleOrderFormState(controller) {
        if (!controller || controller.modelName !== "sale.order") {
            return;
        }
        quoterRememberQuotationForm(controller);
        if (typeof controller._pushState === "function") {
            controller._pushState();
        }
    }

    FormController.include({
        start: function () {
            const def = this._super.apply(this, arguments);
            if (this.modelName !== "sale.order") {
                return def;
            }
            const self = this;
            return def.then(function () {
                quoterRememberQuotationForm(self);
            });
        },
        /**
         * Form embebido del bloque: no actualizar hash con quoter.sale.order.area&id.
         */
        _pushState: function () {
            if (
                this.modelName === "quoter.sale.order.area" &&
                this.$el &&
                this.$el.closest(".o_quoter_area_block_form_body").length
            ) {
                return;
            }
            if (this.__quoterIsAreaBlockEmbed) {
                return;
            }
            return this._super.apply(this, arguments);
        },
    });

    return {
        quoterPushSaleOrderFormState: quoterPushSaleOrderFormState,
        quoterRememberQuotationForm: quoterRememberQuotationForm,
    };
});

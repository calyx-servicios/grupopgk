odoo.define("dms_employee_classification.signature_prefill", function (require) {
    "use strict";

    const SignRegistry = require("sign_oca.SignRegistry");
    const core = require("web.core");
    const Dialog = require("web.Dialog");
    const NameAndSignature = require("web.name_and_signature").NameAndSignature;

    /**
     * Extend the SignatureDialog to prefill with employee's digital signature
     */
    const SignatureDialog = Dialog.extend({
        template: "sign_oca.sign_oca_sign_dialog",
        custom_events: {
            signature_changed: "_onChangeSignature",
        },
        init: function (parent, options) {
            options = options || {};
            this.item = options.item;
            this.prefillSignature = options.prefillSignature || false;
            options.title = options.title || core._t("Adopt Your Signature");
            options.size = options.size || "medium";
            if (!options.buttons) {
                options.buttons = [];
                options.buttons.push({text: core._t("Cancel"), close: true});
                options.buttons.push({
                    text: core._t("Sign"),
                    classes: "btn-primary",
                    disabled: !this.prefillSignature, // No disabled si hay firma prellenada
                    click: () => {
                        this.sign();
                    },
                });
            }
            this._super(parent, options);
            this.nameAndSignature = new NameAndSignature(
                this,
                options.signatureOptions
            );
        },
        willStart: function () {
            return Promise.all([
                this.nameAndSignature.appendTo($("<div>")),
                this._super.apply(this, arguments),
            ]);
        },
        start: function () {
            var self = this;
            this.opened().then(function () {
                self.$(".o_sign_oca_signature").replaceWith(
                    self.nameAndSignature.$el
                );
                
                // Resetear primero para inicializar jSignature
                self.nameAndSignature.resetSignature();
                
                // Si hay firma prellenada, cargarla DESPUÉS del reset
                if (self.prefillSignature) {
                    // Esperar un momento para que jSignature esté listo
                    setTimeout(function() {
                        try {
                            var $canvas = self.nameAndSignature.$signatureField;
                            if ($canvas && $canvas.jSignature) {
                                // Usar importData con formato image
                                var imageData = "data:image/png;base64," + self.prefillSignature;
                                $canvas.jSignature("importData", imageData);
                                
                                // Marcar que la firma NO está vacía
                                self.nameAndSignature.isSignatureEmpty = function () {
                                    return false;
                                };
                                self._onChangeSignature();
                            }
                        } catch (error) {
                            // Silently fail if signature can't be loaded
                        }
                    }, 100);
                }
            });
            return this._super.apply(this, arguments);
        },
        _onChangeSignature: function () {
            this.$footer
                .find(".btn-primary")
                .prop("disabled", this.nameAndSignature.isSignatureEmpty());
        },
        sign: function () {
            if (this.nameAndSignature.isSignatureEmpty()) {
                /* TODO: Remove signature*/
            } else {
                var signature = this.nameAndSignature.getSignatureImage()[1];
                this.item.value = signature;
                this.getParent().postIframeField(this.item);
            }
            this.getParent().checkFilledAll();
            var next_items = _.filter(
                this.getParent().info.items,
                (i) =>
                    i.tabindex > this.item.tabindex &&
                    i.role_id === this.getParent().info.role_id
            ).sort((a, b) => a.tabindex - b.tabindex);
            if (next_items.length > 0) {
                this.getParent().items[next_items[0].id].dispatchEvent(
                    new Event("focus_signature")
                );
            }
            this.close();
        },
    });

    /**
     * Override the signature element generator to use prefilled signature
     */
    const originalSignature = SignRegistry.get("signature");
    const signatureWithPrefill = {
        generate: function (parent, item, signatureItem) {
            var input = $(
                core.qweb.render("sign_oca.sign_iframe_field_signature", {item: item})
            )[0];
            
            // AUTO-FILL: Si hay firma digital y el campo está vacío, rellenarlo automáticamente
            if (item.role_id === parent.info.role_id && 
                !item.value && 
                parent.info.partner.digital_signature) {
                
                item.value = parent.info.partner.digital_signature;
                parent.postIframeField(item);
                parent.checkFilledAll();
            }
            
            if (item.role_id === parent.info.role_id) {
                signatureItem[0].addEventListener("focus_signature", () => {
                    var signatureOptions = {
                        fontColor: "DarkBlue",
                        defaultName: parent.info.partner.name,
                    };
                    var prefillSignature =
                        parent.info.partner.digital_signature || false;
                    
                    new SignatureDialog(parent, {
                        signatureOptions,
                        item,
                        prefillSignature,
                    }).open();
                });
                input.addEventListener("click", (ev) => {
                    ev.preventDefault();
                    ev.stopPropagation();
                    var signatureOptions = {
                        fontColor: "DarkBlue",
                        defaultName: parent.info.partner.name,
                    };
                    var prefillSignature =
                        parent.info.partner.digital_signature || false;
                    
                    new SignatureDialog(parent, {
                        signatureOptions,
                        item,
                        prefillSignature,
                    }).open();
                });
                input.addEventListener("keydown", (ev) => {
                    if ((ev.keyCode || ev.which) !== 9) {
                        return true;
                    }
                    ev.preventDefault();
                    var next_items = _.filter(
                        parent.info.items,
                        (i) =>
                            i.tabindex > item.tabindex && i.role_id === parent.role_id
                    );
                    if (next_items.length > 0) {
                        ev.currentTarget.blur();
                        parent.items[next_items[0].id].dispatchEvent(
                            new Event("focus_signature")
                        );
                    }
                });
            }
            return input;
        },
        check: function (item) {
            return Boolean(item.value);
        },
    };

    // Reemplazar el elemento signature en el registry
    SignRegistry.add("signature", signatureWithPrefill);

    return signatureWithPrefill;
});

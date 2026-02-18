/** @odoo-module **/

import { ChatterTopbar } from "@mail/components/chatter_topbar/chatter_topbar";
import { patch } from "web.utils";

const GROUP_XML_ID = "mail_restrict_send_button.group_show_send_message_button";

const _originalSetup = ChatterTopbar.prototype.setup;
const _originalWillStart = ChatterTopbar.prototype.willStart;

function findServicesInTree(component) {
    let comp = component;
    while (comp) {
        const services = comp.env && comp.env.services;
        if (services && (services.orm || services.user)) {
            return services;
        }
        comp = comp.__owl__ && comp.__owl__.parent;
    }
    return null;
}

function rpcHasGroupFallback() {
    const url = "/web/dataset/call_kw/res.users/has_group";
    const params = {
        model: "res.users",
        method: "has_group",
        args: [GROUP_XML_ID],
        kwargs: {},
    };
    const body = JSON.stringify({
        jsonrpc: "2.0",
        method: "call",
        params: params,
        id: Math.floor(Math.random() * 1e9),
    });
    return fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body,
        credentials: "same-origin",
    })
        .then((res) => res.json())
        .then((data) => data.result === true)
        .catch(() => false);
}

function getHasGroupPromise(component) {
    const services = findServicesInTree(component);
    if (services) {
        if (services.orm && typeof services.orm.call === "function") {
            return services.orm.call("res.users", "has_group", [GROUP_XML_ID]);
        }
        if (services.user && typeof services.user.hasGroup === "function") {
            return services.user.hasGroup(GROUP_XML_ID);
        }
    }
    return rpcHasGroupFallback();
}

patch(
    ChatterTopbar.prototype,
    "mail_restrict_send_button/static/src/js/chatter.esm.js",
    {
        setup() {
            _originalSetup.apply(this, arguments);
            this.isSendMessage = false;
        },

        async willStart() {
            await _originalWillStart.apply(this, arguments);
            try {
                const result = await getHasGroupPromise(this);
                this.isSendMessage = Boolean(result);
            } catch (_e) {
                this.isSendMessage = false;
            }
        },
    }
);

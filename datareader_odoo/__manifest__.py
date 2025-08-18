# pylint: disable=missing-module-docstring
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Datareader Odoo",
    "summary": "Integración con DataReader para importar y procesar órdenes de pago y facturas.",
    "author": "Calyx Servicios S.A.",
    "maintainers": ["sgutierrez"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Accounting",
    "version": "15.0.1.0.0",
    "application": False,
    "installable": True,
    "development_status": "Production/Stable",
    "external_dependencies": {
        "python": ["requests"],
    },
    "depends": [
        "base",
        "account",
        "purchase",
        "mail",
        "account_payment_group",
        "payment_withholding",
    ],
    "data": [
        "views/normalized_text.xml",
        "security/ir.model.access.csv",
        "views/res_config_settings.xml",
        "views/datareader_connector_log_item_view.xml",
        "views/datareader_connector_log_view.xml",
        "views/account_payment_receiptbook.xml",
        "views/account_tax.xml",
    ],
}

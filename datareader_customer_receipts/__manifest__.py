# pylint: disable=missing-module-docstring
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Datareader Odoo for Customer Reciepts",
    "summary": "DataReader integration to import and process payment orders and impact unpaid invoices.",
    "author": "Calyx Servicios S.A.",
    "maintainers": ["sgutierrez"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Accounting",
    "version": "15.0.1.6.2",
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
        "security/datareader_security.xml",
        "security/ir_model_access.xml",
        "data/ir_config_parameter_data.xml",
        "data/l10n_latam_document_type.xml",
        "views/normalized_text.xml",
        "views/res_config_settings.xml",
        "views/datareader_connector_log_item_view.xml",
        "views/datareader_connector_log_view.xml",
        "views/account_payment_receiptbook.xml",
        "views/account_tax.xml",
        "views/res_partner.xml",
    ],
}
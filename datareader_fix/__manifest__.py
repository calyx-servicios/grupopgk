# pylint: disable=missing-module-docstring
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Datareader Fix - Campos de Tolerancia",
    "summary": "Módulo que agrega campos de tolerancia a res.company para evitar problemas en staging",
    "author": "Calyx Servicios S.A.",
    "maintainers": ["sgutierrez"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Accounting",
    "version": "15.0.1.0.0",
    "application": False,
    "installable": True,
    "development_status": "Production/Stable",
    "depends": [
        "base",
        "account",
        "datareader_customer_receipts",
    ],
    "data": [
        "views/res_config_settings.xml",
    ],
}


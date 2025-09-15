# pylint: disable=missing-module-docstring,pointless-statement
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Account Tax Totals Fix",
    "summary": "Evita romper al renderizar facturas sin impuestos en QWeb",
    "author": "Calyx Servicios S.A.",
    "maintainers": [],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Accounting",
    "version": "15.0.1.0.0",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "depends": ["account"],
    "data": [
        "views/report_invoice.xml",
    ],
}

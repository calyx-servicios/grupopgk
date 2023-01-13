# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Invoice Without Details",
    "summary": """
        remove details in invoice""",
    "author": "Calyx Servicios S.A.",
    "maintainers": ["GeorginaGuzman"],
    "website": "http://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Custom",
    "version": "15.0.1.1.0",
    "development_status": "Production/Stable",
    "depends": ['account','l10n_ar','sale_ux','l10n_latam_invoice_document'],
    "data": [
        "views/template.xml",
    ],
}

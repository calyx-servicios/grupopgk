# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Invoice Without Details",
    "summary": """
        remove details in invoice""",
    "author": "Calyx Servicios S.A.",
    "maintainers": ["GeorginaGuzman", "leandro090685"],
    "website": "http://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Custom",
    "version": "15.2.0.0.2",
    "development_status": "Production/Stable",
    "depends": ['account','l10n_ar','sale_ux','l10n_latam_invoice_document','mail'],
    "data": [
        "views/template.xml",
        "data/mail_template_data_without_detail.xml",
    ],
}

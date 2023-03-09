# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "DGI Conector",
    "summary": """
        """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Paradiso Cristian"],
    "website": "http://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Account",
    "version": "15.0.3.0.0",
    "application": False,
    "installable": True,
    "depends": [
        'account','base','l10n_latam_base', 'l10n_latam_invoice_document','account_check_printing'
    ],
    "data": [
        "views/account_view.xml",
        "views/res_company_views.xml",
        "data/l10n_latam_identification_type_data.xml",
    ],
}

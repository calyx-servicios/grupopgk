# pylint: disable=missing-module-docstring,pointless-statement
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Personal Pay Account",
    "summary": """
        This module extends the functionality of account to add Personal Pay fields and methods
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["marcooegg"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "13.0.1.3.0",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "depends": ["base", "account", "l10n_ar"],
    "data": [
        "security/ir.model.access.csv",
        "views/account_view.xml",
    ],
}

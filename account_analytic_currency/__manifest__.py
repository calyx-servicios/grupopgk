# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Account Analytic Currency",
    "summary": """
        This module show on analytic line the currency from journal entry.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Zamora, Javier"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.1.1.0",
    "application": False,
    "installable": True,
    "depends": [
        "analytic",
        "account",
    ],
    "data": [
        "views/account_analytic_line.xml",
    ],
}

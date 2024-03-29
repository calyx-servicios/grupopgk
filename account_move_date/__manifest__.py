# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Date Field",
    "summary": """
        This module show fields date on account_move.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Zamora. Javier", "PerezGabriela"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.2.0.0",
    "application": False,
    "installable": True,
    "depends": [
        "account"
    ],
    "data": [
        "views/account_move.xml",
    ],
}

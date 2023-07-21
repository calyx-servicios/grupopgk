# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Purchase Own Records",
    "summary": """
        This module adds a permission for only current users to view records.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Zamora. Javier"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.1.0.0",
    "application": False,
    "installable": True,
    "depends": [
        'purchase',
    ],
    "data": [
        'security/purchase_security.xml',
    ],
}

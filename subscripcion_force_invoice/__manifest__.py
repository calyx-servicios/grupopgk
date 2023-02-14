# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Force Invoice",
    "summary": """
        This module forces the creation of invoices in the subscriptions.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Zamora. Javier"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.2.2.0",
    "application": False,
    "installable": True,
    "depends": [
        "subscription_package"
    ],
    "data": [
        'views/subscription_package.xml',
    ],
}

# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Fix Subscription Cron",
    "summary": """
        This module fixes the schedule action and adds a button to execute it manually.
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
        "subscription_package"
    ],
    "data": [
        'views/subscription_package.xml',
    ],
}

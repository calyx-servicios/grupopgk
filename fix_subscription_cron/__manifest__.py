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
    "version": "15.0.3.1.3",
    "application": False,
    "installable": True,
    "depends": [
        "subscripcion_force_invoice"
    ],
    "data": [
        'data/cron.xml',
        'views/subscription_plan.xml',
        'views/subscription_package_tree.xml',
    ],
}

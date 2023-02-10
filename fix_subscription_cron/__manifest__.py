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
    "version": "15.0.2.0.0",
    "application": False,
    "installable": True,
    "depends": [
        "subscripcion_force_invoice"
    ],
    "data": [
        'data/cron.xml',
        'views/subscription_plan.xml',
    ],
}

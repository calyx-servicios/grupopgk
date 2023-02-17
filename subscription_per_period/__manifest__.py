# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Total Subscription Per Period",
    "summary": """
        This module generates in the subscription a total per month
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Zamora, Javier"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Sales",
    "version": "15.0.1.0.0",
    "application": False,
    "installable": True,
    "depends": [
        'sale_management',
        'subscription_templates',
    ],
}
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Sale Order Subscription",
    "summary": """
        This module adds the function of creating a subscription from Sale Orders.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Zamora, Javier"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Sign",
    "version": "15.0.1.0.0",
    "application": False,
    "installable": True,
    "depends": [
        'sale_management',
        'subscription_package',
    ],
    "data": [
        'views/sale_order.xml',
        'views/subscription_package.xml',
    ],
}
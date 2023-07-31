# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Multi Subscription Templates",
    "summary": """
        This module adds multiple templates in the product and manages the subscription by sales order lines.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Zamora, Javier"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Sales",
    "version": "15.0.4.5.0",
    "application": False,
    "installable": True,
    "depends": [
        'sale_management',
        'sale_order_subscription',
        'sale_order_split_invoices',
    ],
    "data": [
        'views/subscription_products.xml',
        'views/sale_order.xml',
    ],
}

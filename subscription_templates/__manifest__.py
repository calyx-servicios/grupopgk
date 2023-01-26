# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Multi Subscription Templates",
    "summary": """
        This module adds multiple templates on product.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Zamora, Javier"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Sales",
    "version": "15.0.2.0.0",
    "application": False,
    "installable": True,
    "depends": [
        'sale_management',
        'subscription_package',
        'sale_order_split_invoices',
    ],
    "data": [
        'views/subscription_products.xml',
        'views/sale_order.xml',
    ],
}
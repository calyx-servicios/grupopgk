# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Sale Subscription Fields",
    "summary": """
        This module transfers key fields from Sales Orders to Subscriptions and Invoices, improving subscription management and saving time.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Zamora, Javier"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Sign",
    "version": "15.0.1.4.2",
    "application": False,
    "installable": True,
    "depends": [
        'subscription_templates',
        'sale_order_subscription',
        'sale_order_split_invoices',
        'subscripcion_force_invoice',
    ],
    "data": [
        'views/subscription_package.xml',
    ],
}

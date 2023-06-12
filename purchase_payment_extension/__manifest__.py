# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Purchase Payment Extension",
    "summary": """
        This module adds the payment method field to the purchase form and allows grouping by the same field.
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
        'purchase',
        'account',
        'account_payment',
    ],
    "data": [
        'views/purchase_order.xml',
        'views/account_move.xml',
    ],
}
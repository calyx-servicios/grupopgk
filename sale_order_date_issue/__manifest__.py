# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Sale Order Date issue",
    "summary": """
        This module adds new field on form and tree view for date of issue with filters.
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
    ],
    "data": [
        'views/sale_order.xml',
    ],
}
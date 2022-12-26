# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Sale Order location of the fields",
    "summary": """
        This module modifies the location of the fields.
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
        'sale_project',
        'stock',
    ],
    "data": [
        'views/sale_order.xml',
    ],
}
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Partner fields",
    "summary": """
        This module adds the partner field in different views.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Zamora, Javier"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Sales",
    "version": "15.0.1.1.0",
    "application": False,
    "installable": True,
    "depends": [
        'base',
        'hr',
        'project',
        'account',
        'sale_management',
    ],
    "data": [
        'views/account_move.xml',
        'views/hr_employee.xml',
        'views/res_users.xml',
        'views/project.xml',
        'views/sale_order.xml',

    ],
}
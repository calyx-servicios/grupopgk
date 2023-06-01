# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Custom Access Permissions",
    "summary": """
        This module fixes the schedule action and adds a button to execute it manually.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Zamora. Javier"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.2.4.2",
    "application": False,
    "installable": True,
    "depends": [
        'res_users_partner_fields',
        'sale_timesheet',
        'hr_timesheet',
        'sale_order_split_invoices',
    ],
    "data": [
        'security/permissions.xml',
        'security/ir.model.access.csv',
        'views/project_view.xml',
        'views/sale_order.xml',
        'views/subscription_package.xml',
        'views/menu_items.xml',
    ],
}

# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Custom Purchase Order",
    "summary": """
        This module adds the option Is it salary? in the purchase order that is transferred to the invoice that is generated
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["leandro090685"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.1.0.0",
    "application": False,
    "installable": True,
    "depends": [
        'purchase',
        'associated_partner_employee',
        'department_analytic_account'
        
    ],
    "data": [
        'views/purchase_order_views.xml',
    ],
}

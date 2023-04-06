# pylint: disable=missing-module-docstring,pointless-statement
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Analytic Account Modifier",
    "summary": """
        This module will allow the creation of analytic accounts outside of the Account configuration menu
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["lucianobaleani"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Account",
    "version": "15.0.1.0.0",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "depends": ["account", "purchase", "sale", "sol_analytic_account"],
    "data": [
        "views/account_move_inherited_views.xml",
        "views/sale_order_inherited_views.xml",
        "views/purchase_order_inherited_views.xml",
        "views/purchase_requisition_inherited_views.xml",
    ],
}

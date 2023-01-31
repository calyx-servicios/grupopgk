{
    "name": "Project for each Sale Order Line",
    "summary": """
        This module adds the functionality of creating a project for each sales order line based on the type of product.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Zamora Javier","ParadisoCristian"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.3.1.0",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "depends": [
        "sale_management",
        "project",
        "sale_project",
        "sol_analytic_account",
        "account_analytic_parent",
    ],
    "data": [
        "security/project_for_each_sol_security.xml",
        "views/sale_order.xml",
        "data/ir_sequence.xml",
    ],
}
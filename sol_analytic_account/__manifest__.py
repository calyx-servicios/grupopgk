{
    "name": "SOL analytical account",
    "summary": """
        This module adds the analytical account field to the SOL and passes it to the invoice
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Zamora Javier"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.1.0.0",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "depends": [
        "sale_management",
        "project",
    ],
    "data": [
        "views/sale_order.xml",
    ],

}

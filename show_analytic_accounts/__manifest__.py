{
    "name": "Show Analytical Accounts",
    "summary": """
        This module allow show analytical accounts with the check enabled.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Zamora Javier"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.1.1.0",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "depends": [
        "analytic",
        "sol_analytic_account",
    ],
    "data": [
        "views/sale_order.xml",
        "views/account_analytic_account.xml",
    ],

}

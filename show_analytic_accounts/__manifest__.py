{
    "name": "Show Analytical Accounts",
    "summary": """
        This module allows you to show analytical accounts with the check enabled and does not allow you to archive analytical accounts that have active associated subscriptions
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Zamora Javier", "leandro090685"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.3.1.0",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "depends": [
        "analytic",
        "sol_analytic_account",
        "subscription_package",
    ],
    "data": [
        "views/sale_order.xml",
        "views/account_analytic_account.xml",
    ],

}

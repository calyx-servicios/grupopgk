{
    "name": "Subscription Massive Update",
    "summary": """
        This module adds an action to modify all selected subscription prices by percentage.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Zamora Javier"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.1.5.0",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "depends": [
        "account",
        "subscription_package",
    ],
    "data": [
        "data/decimal_precision_data.xml",
        "security/permissions.xml",
        "views/subscription_ipc_monthly_views.xml",
        "views/subscription_package_views.xml",
        "views/action_menu.xml",
        "wizards/subscription_massive_update.xml",
    ]
}

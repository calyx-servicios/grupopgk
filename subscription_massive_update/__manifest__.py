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
    "version": "15.0.1.1.1",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "depends": [
        "subscription_package",
    ],
    "data": [
        "security/permissions.xml",
        "views/action_menu.xml",
        "wizards/subscription_massive_update.xml",
    ]
}

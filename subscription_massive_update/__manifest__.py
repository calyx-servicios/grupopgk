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
    "version": "15.0.1.10.0",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "depends": [
        "account",
        "report_xlsx",
        "subscription_package",
    ],
    "data": [
        "data/decimal_precision_data.xml",
        "security/groups.xml",
        "security/permissions.xml",
        "views/subscription_ipc_monthly_views.xml",
        "views/subscription_package_views.xml",
        "wizards/subscription_tariff_control_report_wizard_views.xml",
        "report/subscription_tariff_control_report_templates.xml",
        "views/action_menu.xml",
        "wizards/subscription_massive_update.xml",
    ]
}

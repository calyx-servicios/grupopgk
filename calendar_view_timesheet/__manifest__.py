{
    "name": "Calendar View on Timesheet",
    "summary": """
        This module add a new model with holiday with calendar view on timesheets config.
        """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Zamora, Javier"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Customizations",
    "version": "15.0.2.0.0",
    "application": False,
    "installable": True,
    "depends": ["hr_timesheet"],
    "data": [
        "security/ir.model.access.csv",
        "views/calendar_holidays_timesheets.xml",
        "views/menu_items.xml",
    ],
}

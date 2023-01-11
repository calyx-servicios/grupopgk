{
    "name": "Timesheet Odoo",
    "summary": """
       This module creates a timesheet
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["carlamiquetan", "PerezGabriela","Zamora, Javier"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Timesheet",
    "version": "15.0.3.0.1",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "depends": ['base', 'hr_timesheet', 'calendar_view_timesheet'],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/timesheet_sige_views.xml",
    ],
}

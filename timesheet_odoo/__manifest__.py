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
    "version": "15.0.4.0.2",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "depends": ['base', 'hr_timesheet', 'calendar_view_timesheet'],
    "data": [
        "security/timesheet_sige_security.xml",
        "security/ir.model.access.csv",
        "data/mail_template_data.xml",
        "views/timesheet_sige_views.xml",
        "views/period_sige_views.xml",
    ],
}
{
    "name": "Timesheet Odoo",
    "summary": """
       This module creates a timesheet
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["carlamiquetan", "PerezGabriela"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Timesheet",
    "version": "15.0.2.0.1",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "depends": ['base', 'hr_timesheet'],
    "data": [
        "security/ir.model.access.csv",
        "views/timesheet_sige_views.xml",
    ],
}

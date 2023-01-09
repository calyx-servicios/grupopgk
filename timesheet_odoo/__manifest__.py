{
    "name": "Timesheet Odoo",
    "summary": """
       This module creates a timesheet
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["carlamiquetan"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.1.0.0",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "depends": ['base', 'hr', 'project', 'hr_timesheet'],
    "data": [
        "security/ir.model.access.csv",
        "views/timesheet_sige.xml",
    ],
}

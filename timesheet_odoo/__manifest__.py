{
    "name": "Timesheet Odoo",
    "summary": """
       This module creates a timesheet
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["carlamiquetan", "PerezGabriela","Zamora, Javier", "leandro090685"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Timesheet",
    "version": "15.0.21.0.0",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "depends": ['base', 'calendar_view_timesheet', 'hr_timesheet', 'account'],
    "data": [
        "security/timesheet_sige_security.xml",
        "security/ir.model.access.csv",
        "data/timesheet_rule_odoo.xml",
        "data/mail_template_data.xml",
        "data/project_project_data.xml",
        "wizard/timesheet_sige_wizard_view.xml",
        "views/timesheet_sige_views.xml",
        "views/period_sige_views.xml",
    ],
}

{
    "name": "Timesheet Reclassify Odoo",
    "summary": """
       This module allows to reclassify closed periods from sige
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["fcarlini"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Timesheet",
    "version": "15.0.0.0.1",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "depends": [
        'timesheet_odoo'
    ],
    "data": [
        "wizard/timesheet_reclassify_wizard_view.xml",
        "views/timesheet_sige_views.xml",
        "views/timesheet_reclassify_views.xml",
        "security/ir.model.access.csv"
    ],
}

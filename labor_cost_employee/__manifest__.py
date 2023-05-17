{
    "name": "Labor Cost Employee",
    "summary": """
       This module adds the calculation of 
       the labor cost for each employee.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["PerezGabriela"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Employees",
    "version": "15.0.2.3.0",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "depends": ['account', 'contacts', 'timesheet_odoo'],
    "data": [
        "security/ir.model.access.csv",
        "wizard/labor_cost_employee_wizard_views.xml",
        "views/account_move_views.xml",
        "views/labor_cost_employee_views.xml"
    ],
    "assets": {
        "web.assets_backend": [
            "/labor_cost_employee/static/src/js/calculate_labor.js",
        ],
        "web.assets_qweb": [
            "/labor_cost_employee/static/src/xml/qweb.xml",
        ],
    },
}

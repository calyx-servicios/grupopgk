{
    "name": "Associated Partner Employee",
    "summary": """
       This module generates a relationship between partner and employee
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Leandro090685"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Employees",
    "version": "15.0.1.0.0",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "depends": ['account', 'hr'],
    "data": [
        "views/hr_employee_view_form_inherit.xml",
        "views/res_partner_view_inherit.xml",
    ],
}

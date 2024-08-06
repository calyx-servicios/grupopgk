{
    "name": "Hr Recruitment PGK",
    "summary": """
       This module adds the vat field in the recruitment module
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
    "depends": ['website_hr_recruitment'],
    "data": [
        'views/website_hr_recruitment_templates.xml',
        'views/hr_applicant_views.xml',
        'data/data.xml',
    ],
}

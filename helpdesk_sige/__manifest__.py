{
    "name": "Helpdesk Sige",
    "summary": """
      This module integrates the loading of hours that is carried out in the help desk tickets with the SIGE timesheet
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
    "depends": [
            'account',
            'helpdesk_mgmt',
            'timesheet_odoo',
            'helpdesk_mgmt_timesheet',
            ],
    "data": [
        'views/helpdesk_ticket_view.xml',
        ],
}

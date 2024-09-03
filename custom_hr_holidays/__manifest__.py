# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Custom Hr Holidays",
    "summary": """
        This module customizes the vacation request
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["leandro090685"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.7.0.1",
    "application": False,
    "installable": True,
    "depends": ['hr_holidays',
                'calendar_view_timesheet',
                'res_users_partner_fields',
                'hr_contract'
    ],
    "data": [
        'views/hr_leave_type_views.xml',
        'views/hr_leave_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_leave_allocation.xml',
        'views/hr_contract_views.xml',
        'data/ir_cron_data.xml',
    ],
}

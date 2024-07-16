{
    "name": "Custom State Account Move",
    "summary": """
       This module adds states to the "account.move"
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
    "depends": ['account', 'res_users_partner_fields'],
    "data": [
        'views/account_move_views.xml',
    ],
}

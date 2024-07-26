{
    'name': 'Custom Helpdesk',
    'version': '1.0',
    'summary': 'Customize Helpdesk ticket creation',
    'description': 'This module customizes the Helpdesk ticket creation process.',
    'author': 'enzogonzalezdev',
    'category': 'Helpdesk',
    'depends': ['helpdesk_mgmt', 'helpdesk_motive'],
    'data': [
        "views/helpdesk_ticket_motive.xml",
        "security/ir.model.access.csv"],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}

{
    "name": "Mail Template Reminder",
    "summary": "Extensión de plantillas de correo para recordatorios de facturas vencidas",
    "author": "Calyx Servicios S.A.",
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "LGPL-3",
    "category": "Mail",
    "version": "15.0.1.0.0",
    "application": False,
    "installable": True,
    "depends": [
        "base",
        "mail",
        "account_invoice_overdue_reminder",
    ],
    "data": [
        "views/res_partner_views.xml",
        "views/mail_template_views.xml",
        "views/overdue_reminder_views.xml",
        "views/overdue_reminder_start_views.xml",
        "data/mail_template.xml",
    ],
    "demo": [],
}

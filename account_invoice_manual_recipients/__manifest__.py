{
    "name": "Account Invoice Manual Recipients",
    "summary": "Send invoices to manually entered email recipients",
    "author": "Calyx Servicios S.A.",
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Accounting",
    "version": "15.0.1.0.2",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "depends": [
        "account",
        "mail"
    ],
    "data": [
        "views/account_invoice_send_views.xml"
    ],
}

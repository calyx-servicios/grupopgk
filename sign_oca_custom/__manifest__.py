# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Sign OCA Custom",
    "summary": "Plantilla de correo editable y control de notificación por plantilla de firma.",
    "author": "Calyx Servicios S.A.",
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Sign",
    "version": "15.0.1.0.0",
    "application": False,
    "installable": True,
    "depends": [
        "sign_oca",
        "mail",
    ],
    "data": [
        "data/mail_template_data.xml",
        "views/sign_oca_template_views.xml",
    ],
}

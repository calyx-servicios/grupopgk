# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class SignOcaTemplate(models.Model):
    _inherit = "sign.oca.template"

    send_notification = fields.Boolean(
        string="Notificar al firmante por correo",
        default=True,
        help="Si está desactivado, no se envía correo al crear la solicitud.",
    )

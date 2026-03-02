# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class DmsClassificationTemplate(models.Model):
    _inherit = "dms.classification.template"

    signature_template_id = fields.Many2one(
        comodel_name="sign.oca.template",
        string="Plantilla de Firma",
        help="Plantilla de firma que se usará al clasificar documentos "
        "con esta plantilla de clasificación",
    )

from odoo import models, fields


class CrmRequestOrigin(models.Model):
    _name = "crm.request.origin"
    _description = "Traceability Origin"
    _order = "sequence, name"

    name = fields.Char(
        string="Name",
        required=True
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10
    )
    active = fields.Boolean(
        string="Active",
        default=True
    )

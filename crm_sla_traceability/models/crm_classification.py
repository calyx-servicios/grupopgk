from odoo import models, fields


class CrmClassification(models.Model):
    _name = "crm.classification"
    _description = "Opportunity Classification"
    _order = "sequence, name"

    name = fields.Char(
        string="Name",
        required=True,
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
    )
    complexity = fields.Selection(
        selection=[("simple", "Simple"), ("compleja", "Complex")],
        string="Complexity Type",
        required=True,
        default="simple",
    )
    sla_hours = fields.Integer(
        string="SLA Time (hours)",
        required=True,
        help="Business hours that define the SLA deadline (e.g. 24 or 72).",
    )
    active = fields.Boolean(
        string="Active",
        default=True
    )

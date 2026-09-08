from odoo import models, fields


class CrmOpportunityType(models.Model):
    _name = "crm.opportunity.type"
    _description = "Opportunity Type"
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

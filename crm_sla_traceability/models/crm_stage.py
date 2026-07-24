from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CrmStage(models.Model):
    _inherit = "crm.stage"

    is_new_stage = fields.Boolean(
        string="Is Initial Stage",
        help="Marks this stage as the initial one. It cannot be left without filling in "
        "Opportunity Type, Classification and Traceability Origin. "
        "Only one stage can be marked as initial.",
    )
    is_estimation_stage = fields.Boolean(
        string="Is Survey/Estimation Stage",
        help="In this stage the estimation fields are enabled "
        "(estimated hours and validity)",
    )
    is_approval_stage = fields.Boolean(
        string="Is Quotation/Internal Resolution Stage",
        help="In this stage the DC Approval button is shown.",
    )

    @api.constrains("is_new_stage")
    def _check_unique_new_stage(self):
        for stage in self:
            if not stage.is_new_stage:
                continue
            other = self.search(
                [("is_new_stage", "=", True), ("id", "!=", stage.id)], limit=1
            )
            if other:
                raise ValidationError(
                    _(
                        "There is already a stage marked as 'Is Initial Stage': %s. "
                        "Only one is allowed.",
                        other.name,
                    )
                )

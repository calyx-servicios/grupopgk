from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProjectProject(models.Model):
    _inherit = 'project.project'

    is_non_billable = fields.Boolean(
        string='Non-Billable',
        help='Marks the project as non-billable for the consolidation report.'
    )

    @api.constrains('is_non_billable', 'allow_billable')
    def _check_non_billable(self):
        for project in self:
            if project.is_non_billable and project.allow_billable:
                raise ValidationError(
                    _("A project cannot be Billable and Non-Billable at the same time.")
                )

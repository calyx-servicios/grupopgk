# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    employee_document_ids = fields.One2many(
        comodel_name="hr.employee.document",
        inverse_name="employee_id",
        string="Documentos",
    )
    digital_signature = fields.Binary(
        string="Firma",
    )
    can_upload_digital_signature = fields.Boolean(
        compute="_compute_can_upload_digital_signature",
    )

    def _compute_can_upload_digital_signature(self):
        user = self.env.user
        is_manager = user.has_group("hr.group_hr_manager")
        for employee in self:
            employee.can_upload_digital_signature = not is_manager

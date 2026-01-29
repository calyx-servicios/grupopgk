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

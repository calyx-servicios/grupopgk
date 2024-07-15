from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    associated_employee_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Empleado Asociado",
        readonly=True
    )

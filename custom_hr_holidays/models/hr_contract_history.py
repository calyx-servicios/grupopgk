from odoo import models, fields, api


class HrContractHistory(models.Model):
    _inherit = "hr.contract.history"

    legajo = fields.Integer(related="employee_id.legajo", string="Legajo", readonly=True)

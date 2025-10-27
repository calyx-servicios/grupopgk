from odoo import models, fields

class HrJob(models.Model):
    _inherit = "hr.job"

    applicant_category_id = fields.Many2many(
        comodel_name="hr.applicant.category",
        string="Applicant Category",
        help="Categoría asociada a este puesto",
    )
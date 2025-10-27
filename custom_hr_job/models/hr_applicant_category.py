from odoo import models, fields

class HrApplicantCategory(models.Model):
    _inherit = "hr.applicant.category"

    job_id = fields.Many2many(
        comodel_name="hr.job",
        string="Job",
        help="Puesto asociado a esta categoría",
    )
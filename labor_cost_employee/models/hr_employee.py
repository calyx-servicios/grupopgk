from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    associated_contact_ids = fields.One2many(
        comodel_name="res.partner",
        inverse_name="associated_employee_id",
        string="Contactos Asociados",
    )

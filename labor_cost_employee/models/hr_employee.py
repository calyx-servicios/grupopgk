from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    associated_contact_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="employee_associated_contact_rel",
        column1="employee_id",
        column2="partner_id",
        string="Associated Contacts",
    )


class ResPartner(models.Model):
    _inherit = "res.partner"

    associated_employee_ids = fields.Many2many(
        comodel_name="hr.employee",
        relation="employee_associated_contact_rel",
        column1="partner_id",
        column2="employee_id",
        string="Associated employees",
    )

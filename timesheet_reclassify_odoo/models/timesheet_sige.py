from odoo import fields, models, api, _


class TimesheetSige(models.Model):
    _inherit = "timesheet.sige"

    can_reclassify = fields.Boolean(
        string="Can reclassify",
        compute="_compute_can_reclassify"
    )

    @api.constrains("state")
    def _compute_can_reclassify(self):
        employee = self.env.user.employee_id
        for rec in self:
            rec.can_reclassify = False
            if employee and rec.employee_id:
                if employee.id == rec.employee_id.id and rec.state == "close":
                    rec.can_reclassify = True

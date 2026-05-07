# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class ResUsers(models.Model):
    _inherit = "res.users"

    def _get_restricted_hr_department(self):
        department = self.env["hr.department"].sudo().search(
            [
                ("name", "=", "RRHH - Carolina Paludi"),
                ("parent_id.name", "=", "RRHH"),
            ],
            limit=1,
        )
        if department:
            return department
        return self.env["hr.department"].sudo().search(
            [("name", "=", "RRHH - Carolina Paludi")],
            limit=1,
        )

    def _is_in_restricted_hr_department(self):
        self.ensure_one()
        department = self._get_restricted_hr_department()
        if not department:
            return False
        employee_count = self.env["hr.employee"].sudo().search_count(
            [
                ("user_id", "=", self.id),
                ("department_id", "child_of", department.id),
            ]
        )
        return bool(employee_count)

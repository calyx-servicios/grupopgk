# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models, api


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

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        user = self.env.user

        # Si NO es HR Manager, solo ve su propia ficha
        if not user.has_group('hr.group_hr_manager'):
            args = args + [('user_id', '=', user.id)]

        return super().search(args, offset=offset, limit=limit, order=order, count=count)

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        user = self.env.user

        # Si NO es HR Manager, solo ve su propia ficha
        if not user.has_group('hr.group_hr_manager'):
            domain = domain + [('user_id', '=', user.id)]

        return super().read_group(
            domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy
        )

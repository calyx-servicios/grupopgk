# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import AccessError


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
    can_upload_digital_signature = fields.Boolean(
        compute="_compute_can_upload_digital_signature",
    )

    @api.depends("user_id", "digital_signature")
    def _compute_can_upload_digital_signature(self):
        user = self.env.user
        is_manager = user.has_group("hr.group_hr_manager")
        for employee in self:
            employee.can_upload_digital_signature = (
                not is_manager
                and employee.user_id == user
                and not employee.digital_signature
            )

    def write(self, vals):
        if not self.env.user.has_group("hr.group_hr_manager"):
            own_records = self.filtered(lambda e: e.user_id == self.env.user)
            other_records = self - own_records
            if other_records:
                raise AccessError(
                    _("No tiene permiso para modificar la ficha de otro empleado.")
                )
            if own_records:
                allowed_keys = {"digital_signature"}
                extra_keys = set(vals) - allowed_keys
                if extra_keys:
                    raise AccessError(
                        _("Solo puede cargar su firma digital desde el botón correspondiente.")
                    )
                if "digital_signature" in vals:
                    if any(employee.digital_signature for employee in own_records):
                        raise AccessError(
                            _("No puede modificar ni eliminar una firma digital ya registrada.")
                        )
                    if not vals.get("digital_signature"):
                        raise AccessError(
                            _("No puede eliminar su firma digital.")
                        )
        return super().write(vals)

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

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .project_task import UAT_OPERATION, uat_accessible_task_ids, uat_task_access_domain


class ProjectTaskUatApproval(models.Model):
    _name = "project.task.uat.approval"
    _description = "Aprobación de revisión de Mejora UAT"
    _order = "date desc, id desc"

    task_id = fields.Many2one("project.task", required=True, ondelete="restrict", index=True)
    approval_type = fields.Selection(
        [("client", "Cliente"), ("commercial", "Comercial")], required=True,
    )
    user_id = fields.Many2one("res.users", required=True, readonly=True)
    date = fields.Datetime(required=True, readonly=True)
    proposal_key = fields.Char(required=True, readonly=True)
    revision = fields.Integer(string="Revisión", readonly=True, required=True)
    proposal = fields.Text(string="Estimación aprobada", required=True, readonly=True)
    sale_line_id = fields.Many2one("sale.order.line", required=True, ondelete="restrict")
    description = fields.Text(string="Detalle de aprobación", required=True)
    attachment_ids = fields.Many2many("ir.attachment", string="Evidencia")
    uat_task_access = fields.Boolean(
        compute="_compute_uat_task_access", search="_search_uat_task_access",
    )

    def _compute_uat_task_access(self):
        allowed = set(uat_accessible_task_ids(self.env))
        for approval in self:
            approval.uat_task_access = approval.task_id.id in allowed

    def _search_uat_task_access(self, operator, value):
        return uat_task_access_domain(self.env, operator, value)

    _sql_constraints = [
        ("revision_type_unique", "unique(task_id, proposal_key, approval_type)",
         "Esta revisión ya tiene registrada esa aprobación."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("_uat_operation") is not UAT_OPERATION:
            raise AccessError(_("Registre la aprobación mediante las acciones de la Mejora."))
        for vals in vals_list:
            vals["user_id"] = self.env.uid
            vals["date"] = fields.Datetime.now()
        records = super().create(vals_list)
        for approval in records:
            if approval.approval_type == "client" and (
                not approval.attachment_ids or not approval.description.strip()
            ):
                raise ValidationError(_("La aprobación del cliente requiere detalle y evidencia."))
            approval.attachment_ids.check_access_rights("read")
            approval.attachment_ids.check_access_rule("read")
        return records

    def write(self, vals):
        raise AccessError(_("Las aprobaciones de Mejora son inmutables."))

    def unlink(self):
        raise AccessError(_("Las aprobaciones de Mejora no pueden eliminarse."))


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def _uat_is_evidence(self):
        if not self:
            return False
        return bool(
            self.env["project.task.uat.approval"].sudo().search_count([
                ("attachment_ids", "in", self.ids),
            ])
            or self.env["project.task.event"].sudo().search_count([
                ("event_type", "=", "uat"), ("attachment_ids", "in", self.ids),
            ])
        )

    def write(self, vals):
        protected = {"datas", "raw", "db_datas", "name", "res_model", "res_id", "res_field", "public"}
        changed = protected.intersection(vals)
        if changed and self._uat_is_evidence() and any(
            name not in ("res_model", "res_id") or any(
                attachment[name] != vals[name] for attachment in self
            ) for name in changed
        ):
            raise AccessError(_("La evidencia UAT registrada no puede alterarse."))
        return super().write(vals)

    def unlink(self):
        if self._uat_is_evidence():
            raise AccessError(_("La evidencia UAT registrada no puede eliminarse."))
        return super().unlink()

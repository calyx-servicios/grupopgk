from odoo import fields, models, api, _
from odoo.exceptions import UserError


class ProjectTaskHoursRequest(models.Model):
    """Request approval to allocate task margin to one work segment."""

    _name = 'project.task.hours.request'
    _inherit = ['mail.thread']
    _description = 'Solicitud de horas adicionales a Contratos'
    _order = 'request_date desc'

    name = fields.Char(
        string="Name",
        compute="_compute_name",
        store=True
    )
    task_id = fields.Many2one(
        string="Tarea",
        comodel_name="project.task",
        required=True,
        tracking=True
    )
    segment = fields.Selection(
        selection=[
            ("development", "Desarrollo"),
            ("deploy", "Deploy"),
            ("functional_test", "Funcional Pruebas"),
        ],
        string="Tramo",
        required=True,
        default="development",
        tracking=True,
    )
    margin_authorization = fields.Boolean(
        string="Autoriza uso del margen",
        default=False,
        readonly=True,
        copy=False,
    )
    project_id = fields.Many2one(
        string="Proyecto",
        comodel_name="project.project",
        related="task_id.project_id",
        store=True
    )
    previous_hours_cap = fields.Float(
        string="Tope de horas anterior",
        readonly=True
    )
    requested_hours = fields.Float(
        string="Horas solicitadas",
        required=True,
        tracking=True
    )
    new_hours_cap = fields.Float(
        string="Nuevo tope de horas",
        compute="_compute_new_hours_cap",
        store=True
    )
    reason = fields.Text(
        string="Motivo",
        required=True
    )
    state = fields.Selection(
        string="Estado",
        selection=[
            ("pending", "Pendiente"),
            ("approved", "Aprobada"),
            ("rejected", "Rechazada"),
            ("cancelled", "Cancelada"),
        ],
        default="pending",
        tracking=True
    )
    requested_by = fields.Many2one(
        string="Solicitado por",
        comodel_name="res.users",
        default=lambda self: self.env.user,
        readonly=True
    )
    request_date = fields.Datetime(
        string="Fecha de solicitud",
        default=fields.Datetime.now,
        readonly=True
    )
    approved_by = fields.Many2one(
        string="Resuelto por",
        comodel_name="res.users",
        readonly=True
    )
    approval_date = fields.Datetime(
        string="Fecha de resolución",
        readonly=True
    )
    can_approve = fields.Boolean(
        compute="_compute_can_approve"
    )
    can_cancel = fields.Boolean(
        compute="_compute_can_cancel"
    )

    @api.depends("task_id", "requested_hours")
    def _compute_name(self):
        for rec in self:
            rec.name = _("%(task)s (+%(hours)s hs)") % {
                "task": rec.task_id.name or "",
                "hours": rec.requested_hours,
            }

    @api.depends("previous_hours_cap", "requested_hours")
    def _compute_new_hours_cap(self):
        for rec in self:
            rec.new_hours_cap = rec.previous_hours_cap + rec.requested_hours

    def _compute_can_approve(self):
        is_contratos = self.env.user.has_group(
            "project_hours_request.group_project_hours_request_contratos"
        )
        for rec in self:
            rec.can_approve = rec.state == "pending" and is_contratos

    def _compute_can_cancel(self):
        user = self.env.user
        for rec in self:
            rec.can_cancel = (
                rec.state == "pending" and rec.requested_by == user
            )

    @api.model_create_multi
    def create(self, vals_list):
        """Create requests only after the selected planned cap is exhausted."""
        for vals in vals_list:
            if vals.get("state", "pending") != "pending":
                raise UserError(_(
                    "Las solicitudes nuevas deben quedar Pendientes."
                ))
            vals.update({
                "state": "pending",
                "requested_by": self.env.user.id,
                "approved_by": False,
                "approval_date": False,
                "margin_authorization": True,
            })
            if vals.get("requested_hours", 0) <= 0:
                raise UserError(_(
                    "Las horas solicitadas deben ser mayores a cero."
                ))
            if vals.get("task_id"):
                task = self.env["project.task"].browse(vals["task_id"])
                segment = vals.get("segment", "development")
                if not task.development_card:
                    raise UserError(_(
                        "Las horas de margen solo se autorizan en tarjetas "
                        "de Desarrollo."
                    ))
                if (
                    task._get_consumed_hours(segment)
                    < task._get_planned_hours(segment)
                ):
                    raise UserError(_(
                        "El tope planificado de %s todavía no fue alcanzado."
                    ) % task._get_segment_label(segment))
                vals["previous_hours_cap"] = task.hours_cap
        records = super().create(vals_list)
        contratos_group = self.env.ref(
            "project_hours_request.group_project_hours_request_contratos"
        )
        for rec in records:
            # Notifica a aprobadores y solicitante sobre cambios de estado.
            partners = (
                contratos_group.users.mapped("partner_id")
                | rec.requested_by.partner_id
            )
            if partners:
                rec.message_subscribe(partner_ids=partners.ids)
            rec.message_post(
                body=_(
                    "Nueva solicitud de horas adicionales para %(task)s: "
                    "+%(hours)s hs (tope actual: %(current)s hs). "
                    "Motivo: %(reason)s"
                ) % {
                    "task": rec.task_id.name,
                    "hours": rec.requested_hours,
                    "current": rec.previous_hours_cap,
                    "reason": rec.reason,
                }
            )
        return records

    def write(self, vals):
        """Protect workflow fields from direct changes."""
        workflow_fields = {
            "state",
            "requested_by",
            "approved_by",
            "approval_date",
            "previous_hours_cap",
            "margin_authorization",
        }
        if workflow_fields.intersection(vals) and not self.env.context.get(
            "hours_request_workflow"
        ):
            raise UserError(_(
                "El estado de la solicitud solo puede cambiarse con sus "
                "acciones."
            ))
        if not self.env.context.get("hours_request_workflow"):
            invalid_requests = self.filtered(
                lambda request: (
                    request.state != "pending"
                    or request.requested_by != self.env.user
                )
            )
            if invalid_requests:
                raise UserError(_(
                    "Solo el solicitante puede editar una solicitud pendiente."
                ))
        return super().write(vals)

    def action_approve(self):
        """Approve a request when enough unallocated margin remains."""
        for rec in self:
            if not rec.can_approve:
                raise UserError(_(
                    "No tenés permisos para aprobar esta solicitud."
                ))
            self.env.cr.execute(
                "SELECT id FROM project_task WHERE id = %s FOR UPDATE",
                [rec.task_id.id],
            )
            rec.invalidate_cache()
            if rec.state != "pending":
                raise UserError(_("La solicitud ya fue resuelta."))
            approved_margin = sum(
                rec.task_id.hours_request_ids.filtered(
                    lambda request: (
                        request.state == "approved"
                        and request.margin_authorization
                    )
                ).mapped("requested_hours")
            )
            requested_margin = approved_margin + rec.requested_hours
            if requested_margin > rec.task_id.margin_hours:
                raise UserError(_(
                    "La solicitud supera las horas de Margen disponibles."
                ))
            rec.task_id.hours_cap += rec.requested_hours
            rec.with_context(hours_request_workflow=True).write({
                "state": "approved",
                "approved_by": self.env.user.id,
                "approval_date": fields.Datetime.now(),
            })
            rec.message_post(
                body=_(
                    "Solicitud aprobada. Nuevo tope de horas: %s hs."
                ) % rec.new_hours_cap
            )

    def action_reject(self):
        for rec in self:
            if not rec.can_approve:
                raise UserError(_(
                    "No tenés permisos para rechazar esta solicitud."
                ))
            rec.with_context(hours_request_workflow=True).write({
                "state": "rejected",
                "approved_by": self.env.user.id,
                "approval_date": fields.Datetime.now(),
            })
            rec.message_post(body=_("Solicitud rechazada."))

    def action_cancel(self):
        for rec in self:
            if not rec.can_cancel:
                raise UserError(_("No podés cancelar esta solicitud."))
            rec.with_context(hours_request_workflow=True).write({
                "state": "cancelled"
            })
            rec.message_post(body=_("Solicitud cancelada por el solicitante."))

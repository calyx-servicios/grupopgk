from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class TimesheetReclassify(models.Model):
    _name = 'timesheet.reclassify'
    _description = 'timesheet.reclassify'
    _rec_name = "ticket_id"

    state = fields.Selection(
        string="Status",
        selection=[
            ("cancel", "Cancelled"),
            ("pending", "Pending"),
            ("done", "Done")
        ],
        default="pending"
    )
    ticket_id = fields.Many2one(
        string="Ticket",
        comodel_name="timesheet.sige"
    )
    line_ids = fields.One2many(
        string="Lines",
        comodel_name="timesheet.reclassify.line",
        inverse_name="reclassify_id"
    )
    approver_ids = fields.Many2many(
        string="Approvers",
        comodel_name="res.users",
        compute="_compute_approver_ids",
        store=True
    )
    user_id = fields.Many2one(
        string="Employee",
        comodel_name="res.users",
        related="ticket_id.employee_id.user_id"
    )
    can_cancel = fields.Boolean(
        compute="_compute_can_cancel"
    )

    def _compute_can_cancel(self):
        user = self.env.user.id
        for rec in self:
            rec.can_cancel = False
            if user in rec.approver_ids.ids:
                rec.can_cancel = True

    def _compute_approver_ids(self):
        for rec in self:
            rec.approver_ids = rec.approver_ids.ids if rec.approver_ids else False
            if rec.state not in ["cancel", "done"]:
                rec.approver_ids = rec.line_ids.mapped("approver_id").ids

    def cancel(self):
        user = self.env.user.id
        self = self.sudo()
        for rec in self:
            if rec.can_cancel:
                rec.state = "cancel"

    def action_force_done(self):
        """
        Forzar el paso de `pending` a `done` para registros que ya están aprobados,
        evitando que se queden destrabados por inconsistencias de interfaz/estado.
        Solo el Administrador puede ejecutarlo.
        """
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_("Solo el Administrador puede ejecutar esta acción."))

        for rec in self:
            if rec.state != "pending":
                continue

            approve_lines = rec.line_ids.filtered(lambda l: l.approver_id)
            required_lines = approve_lines if approve_lines else rec.line_ids

            if not required_lines:
                raise ValidationError(_("No existen líneas para validar en esta reclasificación."))

            not_approved = required_lines.filtered(lambda l: not l.approved)
            if not_approved:
                raise ValidationError(_(
                    "No se puede forzar 'Done'. Hay líneas sin aprobar (%s)."
                ) % len(not_approved))

            rec.state = "done"

    def action_mass_cancel(self):
        """Ajuste histórico puntual: pasa a `cancel` las reclasificaciones
        seleccionadas que estén en `pending`.

        A diferencia del botón `cancel`, ignora `can_cancel` (hay pendientes sin
        aprobador asignado que de otro modo quedan trabadas) y no toca las
        `account.analytic.line` relacionadas, por lo que las horas ya imputadas
        quedan tal cual están.

        Los registros en `done` o `cancel` se ignoran. Reservado a
        `base.group_system`: es una regularización, no parte del flujo.
        """
        if not self.env.user.has_group("base.group_system"):
            raise UserError(_("Solo el Administrador puede ejecutar esta acción."))

        to_cancel = self.filtered(lambda r: r.state == "pending")
        skipped = self - to_cancel
        if to_cancel:
            to_cancel.sudo().write({"state": "cancel"})

        message = _("Reclasificaciones canceladas: %s.") % len(to_cancel)
        if skipped:
            message += _(" Sin modificar (ya en Done/Cancelled): %s.") % len(skipped)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Cancelación masiva de reclasificaciones"),
                "message": message,
                "type": "success" if to_cancel else "warning",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def write(self, vals):
        to_process = self.env["timesheet.reclassify"]
        if vals.get("state") == "done":
            to_process = self.filtered(lambda r: r.state != "done")
        res = super().write(vals)
        if to_process:
            to_process._process_done()
        return res

    def _process_done(self):
        self = self.sudo()
        AAL = self.env["account.analytic.line"]
        for rec in self:
            for line in rec.line_ids:
                if line.analytic_line:
                    if line.unit_amount_reclassify:
                        line.analytic_line.unit_amount = line.unit_amount_reclassify
                    else:
                        line.analytic_line.unlink()
                else:
                    if line.unit_amount_reclassify:
                        new_aal = AAL.create({
                            "timesheet_id": rec.ticket_id.id,
                            "project_id": line.project_id.id,
                            "unit_amount": line.unit_amount_reclassify,
                            "user_id": rec.user_id.id if rec.user_id else False,
                            "employee_id": rec.user_id.employee_id.id if rec.user_id and rec.user_id.employee_id else False,
                            "name": line.name,
                        })
                        line.analytic_line = new_aal.id


class TimesheetReclassifyLine(models.Model):
    _name = 'timesheet.reclassify.line'
    _description = 'timesheet.reclassify.line'

    project_id = fields.Many2one(
        comodel_name="project.project",
        required=True,
        domain =[('allow_timesheets', '=', True)]
    )
    name = fields.Char(
        'Description',
        required=True
    )
    unit_amount = fields.Float(
        'Quantity',
        default=0.0
    )
    unit_amount_reclassify = fields.Float(
        'Quantity to reclasify',
        default=0.0
    )
    reclassify_id = fields.Many2one(
        comodel_name="timesheet.reclassify"
    )
    analytic_line = fields.Many2one(
        comodel_name="account.analytic.line"
    )
    approver_id = fields.Many2one(
        string="Approver",
        comodel_name="res.users",
        compute="_compute_approver_id",
        store=True
    )
    approved = fields.Boolean(
        string="Approved"
    )
    can_approve = fields.Boolean(
        compute="_compute_can_approve"
    )

    def _compute_can_approve(self):
        user = self.env.user
        # Permite aprobar cuando la línea no tiene `approver_id`:
        # - normalmente lo haría el usuario solicitante (`reclassify_id.user_id`)
        # - pero para facilitar pruebas/admin, también se permite a quien tiene
        #   "Ver Todas las Reclasificaciones".
        can_approve_view_all = user.has_group('timesheet_reclassify_odoo.group_timesheet_reclassify_view_all')
        for rec in self:
            rec.can_approve = False
            if rec.approved:
                continue
            if rec.reclassify_id.state != "pending":
                continue

            if rec.approver_id:
                rec.can_approve = rec.approver_id.id == user.id
            else:
                rec.can_approve = bool(
                    (rec.reclassify_id.user_id and rec.reclassify_id.user_id.id == user.id) or can_approve_view_all
                )

    def approve(self):
        self = self.sudo()
        for rec in self:
            rec.approved = True

    def write(self, vals):
        """
        Si se marca manualmente el checkbox `approved`, asegurar que el
        `state` del registro padre se recalcula también (Pending -> Done).
        """
        res = super().write(vals)
        if "approved" not in vals:
            return res

        reclassify_ids = self.mapped("reclassify_id")
        for reclassify in reclassify_ids:
            reclassify_sudo = reclassify.sudo()
            if reclassify_sudo.state != "pending":
                continue

            approve_lines = reclassify_sudo.line_ids.filtered(lambda l: l.approver_id)
            if approve_lines:
                if set(approve_lines.mapped("approved")) == {True}:
                    reclassify_sudo.state = "done"
            else:
                if reclassify_sudo.line_ids and set(reclassify_sudo.line_ids.mapped("approved")) == {True}:
                    reclassify_sudo.state = "done"

        return res

    @api.constrains("project_id")
    def _compute_approver_id(self):
        self = self.sudo()
        for rec in self:
            rec.approver_id = rec.approver_id.id if rec.approver_id else False
            if rec.reclassify_id.state not in ["cancel", "done"]:
                if rec.unit_amount_reclassify > rec.unit_amount:
                    rec.approver_id = rec.project_id.user_id.id
        self.mapped("reclassify_id")._compute_approver_ids()

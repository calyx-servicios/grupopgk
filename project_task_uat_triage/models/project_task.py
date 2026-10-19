import hashlib
import json

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare


# An RPC context cannot manufacture this capability.
UAT_OPERATION = object()
UAT_RESULTS = [
    ("bug", "Bug"),
    ("improvement", "Mejora"),
    ("misunderstanding", "Malentendido"),
]
PROTECTED_FIELDS = {
    "uat_origin_id", "uat_bug_event_id", "uat_version", "uat_revision",
}


def uat_accessible_task_ids(env):
    return env["project.task"].sudo(False).with_context(active_test=False).search([]).ids


def uat_task_access_domain(env, operator, value):
    if operator not in ("=", "!=") or value not in (True, False):
        raise UserError(_("Operador de acceso UAT no válido."))
    positive = bool(value) == (operator == "=")
    return [("task_id", "in" if positive else "not in", uat_accessible_task_ids(env))]


class ProjectTask(models.Model):
    _inherit = "project.task"

    uat_origin_id = fields.Many2one(
        "project.task", string="Tarea de origen UAT", copy=False,
        readonly=True, ondelete="restrict", index=True,
    )
    uat_improvement_ids = fields.One2many(
        "project.task", "uat_origin_id", string="Mejoras UAT",
    )
    uat_bug_event_id = fields.Many2one(
        "project.task.event", string="Ciclo Bug activo", copy=False,
        readonly=True, ondelete="restrict",
    )
    uat_version = fields.Integer(default=0, copy=False, readonly=True)
    uat_revision = fields.Integer(default=0, copy=False, readonly=True)
    can_validate_uat = fields.Boolean(compute="_compute_uat_actions")
    can_record_uat_client = fields.Boolean(compute="_compute_uat_actions")
    can_approve_uat_commercial = fields.Boolean(compute="_compute_uat_actions")
    uat_sale_line_id = fields.Many2one(
        "sale.order.line", string="Línea comercial de la Mejora", copy=False,
        tracking=True, ondelete="restrict",
        domain="[('is_service', '=', True), ('is_expense', '=', False)]",
    )
    uat_approval_ids = fields.One2many(
        "project.task.uat.approval", "task_id", string="Aprobaciones de Mejora",
    )
    uat_ready = fields.Boolean(
        string="Mejora habilitada", compute="_compute_uat_ready",
    )
    uat_last_result = fields.Selection(
        UAT_RESULTS, string="Último triage UAT", compute="_compute_uat_last_result",
    )
    can_create_uat_quotation = fields.Boolean(compute="_compute_uat_actions")

    _sql_constraints = [
        ("uat_sale_line_unique", "unique(uat_sale_line_id)",
         "La línea comercial ya pertenece a otra Mejora."),
    ]

    @api.depends("event_ids.event_type", "event_ids.uat_result", "event_ids.date")
    def _compute_uat_last_result(self):
        for task in self:
            events = task.event_ids.filtered(lambda e: e.event_type == "uat")
            task.uat_last_result = events.sorted(
                key=lambda e: (e.date, e.id), reverse=True,
            )[:1].uat_result if events else False

    @api.depends("stage_id", "project_id", "uat_origin_id", "uat_sale_line_id")
    @api.depends_context("uid")
    def _compute_uat_actions(self):
        for task in self:
            functional = task._uat_is_functional()
            task.can_validate_uat = (
                functional and task.task_type == "development"
                and task.stage_id == task._workflow_stage("stage_uat_cliente")
            )
            task.can_record_uat_client = bool(task.uat_origin_id and functional)
            task.can_approve_uat_commercial = bool(
                task.uat_origin_id and task.uat_sale_line_id
                and task.uat_sale_line_id.sudo().order_id.user_id == self.env.user
            )
            task.can_create_uat_quotation = bool(
                task.uat_origin_id and not task.uat_sale_line_id
                and self.env.user.has_group("sales_team.group_sale_salesman")
            )

    def _uat_is_functional(self):
        self.ensure_one()
        return bool(
            self.project_id
            and "functional" in self.project_id._get_user_workflow_roles()
        )

    def _uat_lock(self):
        self.check_access_rights("write")
        self.check_access_rule("write")
        self.flush()
        self.env["account.analytic.line"]._lock_tasks(self)
        self.invalidate_cache()

    def _uat_capability(self):
        return self.env.context.get("_uat_operation") is UAT_OPERATION

    def _uat_in_bug_rework(self):
        self.ensure_one()
        return bool(self.uat_bug_event_id) and self.stage_id.get_timesheet_stage_type() in (
            "development", "deploy", "functional_test",
        )

    def _uat_estimate(self):
        self.ensure_one()
        return {
            name: self[name] for name in sorted(self.ESTIMATED_HOURS_FIELDS)
        }

    def _uat_proposal_key(self):
        self.ensure_one()
        line = self.uat_sale_line_id.sudo()
        proposal = {
            "revision": self.uat_revision,
            "estimate": self._uat_estimate(),
            "line": line.id,
            "order": line.order_id.id,
            "seller": line.order_id.user_id.id,
            "partner": line.order_id.partner_id.id,
            "company": line.company_id.id,
            "product": line.product_id.id,
            "uom": line.product_uom.id,
            "hours": line.contrated_hours,
            "uat_hours": line.uat_support_hours,
            "quantity": line.product_uom_qty,
            "price": line.price_unit,
            "discount": line.discount,
            "taxes": line.tax_id.ids,
            "project": self.project_id.id,
        }
        return hashlib.sha256(
            json.dumps(proposal, sort_keys=True).encode()
        ).hexdigest()

    def _uat_check_commercial_scope(self):
        self.ensure_one()
        line = self.uat_sale_line_id.sudo()
        if not self.uat_origin_id or not line:
            raise UserError(_("La Mejora requiere su propia línea de cotización."))
        origin = self.uat_origin_id
        root = origin._get_calyx_uat_root()
        original_order = (root.sale_line_id or origin.sudo().sale_line_id).order_id
        if (
            not line.is_service or line.is_expense
            or line.order_id == original_order
            or line.company_id != self.company_id
            or line.order_id.partner_id.commercial_partner_id
            != self.partner_id.commercial_partner_id
            or line.project_id != self.project_id
            or line.order_id.user_id.share
            or not line.order_id.user_id
            or line.order_id.order_line.filtered(
                lambda item: not item.display_type and item != line
            )
        ):
            raise ValidationError(_(
                "Use una nueva cotización de servicio del mismo cliente y "
                "compañía, vinculada al proyecto y con responsable comercial."
            ))
        other_tasks = self.sudo().with_context(active_test=False).search([
            ("sale_line_id", "=", line.id), ("id", "!=", self.id),
            ("is_calyx_sale_root", "=", False),
        ])
        if other_tasks:
            raise ValidationError(_("La línea de la Mejora no puede financiar otras tareas."))
        if line.uat_quotation_task_id and line.uat_quotation_task_id != self:
            raise ValidationError(_("Esta línea está reservada para otra Mejora UAT."))

    def _uat_check_proposal(self):
        self._uat_check_commercial_scope()
        line = self.uat_sale_line_id.sudo()
        if line.order_id.state == "cancel":
            raise UserError(_("La orden de la Mejora está cancelada; no permite aprobar ni cargar horas."))
        estimates = self._uat_estimate()
        total = sum(estimates.values())
        if (
            total <= 0 or any(value < 0 for value in estimates.values())
            or float_compare(total, line.contrated_hours, precision_digits=2) > 0
            or float_compare(
                self.estimated_uat_support_hours, line.uat_support_hours,
                precision_digits=2,
            ) > 0
        ):
            raise ValidationError(_(
                "La estimación debe ser positiva y caber en las horas "
                "contratadas y la reserva UAT de la nueva línea."
            ))

    @api.depends(
        "uat_origin_id", "uat_sale_line_id", "uat_approval_ids", "uat_revision",
        "uat_sale_line_id.order_id.state",
        "uat_sale_line_id.order_id.user_id", "uat_sale_line_id.price_unit",
        "uat_sale_line_id.contrated_hours", "estimated_dev_hours",
        "estimated_deploy_hours", "estimated_functional_test_hours",
        "estimated_uat_support_hours", "margin_hours",
    )
    def _compute_uat_ready(self):
        for task in self:
            if not task.uat_origin_id or not task.uat_sale_line_id:
                task.uat_ready = False
                continue
            key = task._uat_proposal_key()
            approvals = task.uat_approval_ids.filtered(
                lambda approval: approval.proposal_key == key
            )
            task.uat_ready = bool(
                task.uat_sale_line_id.sudo().state in ("sale", "done")
                and {"client", "commercial"}.issubset(
                    set(approvals.mapped("approval_type"))
                )
            )

    def _uat_check_ready(self):
        for task in self.filtered("uat_origin_id"):
            task._uat_check_proposal()
            task.invalidate_cache(["uat_ready"])
            if not task.uat_ready:
                raise UserError(_(
                    "La Mejora requiere estimación, aprobación del cliente "
                    "con evidencia, aprobación comercial y orden confirmada."
                ))

    def _get_budget_timesheet_domain(self):
        return super()._get_budget_timesheet_domain() + [
            ("uat_rework_event_id", "=", False),
        ]

    def _uat_invalidate_proposal(self):
        for task in self.filtered("uat_origin_id"):
            task.with_context(_uat_operation=UAT_OPERATION).write({
                "uat_revision": task.uat_revision + 1,
            })
            task.message_post(body=_(
                "Propuesta de Mejora modificada. Deben obtenerse nuevamente "
                "las aprobaciones del cliente y de Comercial."
            ))

    def action_open_uat_wizard(self):
        self.ensure_one()
        if not self.can_validate_uat:
            raise AccessError(_("Solo el Funcional puede validar una tarea en UAT Cliente."))
        return {
            "type": "ir.actions.act_window", "name": _("Validar UAT"),
            "res_model": "project.task.uat.wizard", "view_mode": "form",
            "target": "new", "context": {"default_task_id": self.id},
        }

    def action_open_uat_client_approval(self):
        self.ensure_one()
        if not self.uat_origin_id or not self._uat_is_functional():
            raise AccessError(_("Solo el Funcional registra la aprobación del cliente."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Registrar aprobación del cliente"),
            "res_model": "project.task.uat.client.wizard",
            "view_mode": "form", "target": "new",
            "context": {"default_task_id": self.id},
        }

    def action_open_uat_quotation(self):
        self.ensure_one()
        if not self.can_create_uat_quotation:
            raise AccessError(_("Ventas debe crear la cotización dedicada para esta Mejora."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Cotizar Mejora UAT"),
            "res_model": "project.task.uat.quotation.wizard",
            "view_mode": "form", "target": "new",
            "context": {"default_task_id": self.id},
        }

    def action_approve_uat_commercial(self):
        self.ensure_one()
        self._uat_lock()
        self._uat_check_proposal()
        if self.uat_sale_line_id.order_id.user_id != self.env.user:
            raise AccessError(_("Solo el responsable comercial de la orden puede aprobar."))
        self._uat_record_approval("commercial")
        return True

    def _uat_record_approval(self, approval_type, attachments=None, description=None):
        self.ensure_one()
        self._uat_check_proposal()
        key = self._uat_proposal_key()
        if self.uat_approval_ids.filtered(
            lambda approval: approval.proposal_key == key
            and approval.approval_type == approval_type
        ):
            raise UserError(_("Esta revisión ya tiene registrada esa aprobación."))
        if attachments:
            attachments.write({"res_model": "project.task", "res_id": self.id})
        self.env["project.task.uat.approval"].with_context(
            _uat_operation=UAT_OPERATION,
        ).create({
            "task_id": self.id, "approval_type": approval_type,
            "proposal_key": key,
            "revision": self.uat_revision,
            "proposal": json.dumps(self._uat_estimate(), sort_keys=True),
            "sale_line_id": self.uat_sale_line_id.id,
            "description": description or _("Aprobación comercial"),
            "attachment_ids": [(6, 0, attachments.ids if attachments else [])],
        })
        self.message_post(
            body=Markup("<p>%s</p><p>%s</p>") % (
                _("Aprobación del cliente registrada") if approval_type == "client"
                else _("Mejora aprobada por Comercial"), description or "",
            ),
            attachment_ids=attachments.ids if attachments else [],
            subtype_xmlid="mail.mt_note",
        )

    @api.model_create_multi
    def create(self, vals_list):
        if not self._uat_capability() and any(
            PROTECTED_FIELDS.intersection(vals) for vals in vals_list
        ):
            raise AccessError(_("Los vínculos y ciclos UAT se generan mediante el triage."))
        parents = self.browse([vals["parent_id"] for vals in vals_list if vals.get("parent_id")])
        if parents.sudo().mapped("sale_line_id")._uat_dedicated_tasks() or parents.filtered("uat_origin_id"):
            raise UserError(_("La Mejora y su presupuesto dedicado no admiten subtareas."))
        tasks = super().create(vals_list)
        tasks._uat_check_structure()
        return tasks

    def _check_development_move(self, destination, vals):
        self.ensure_one()
        successful_path = (
            self._workflow_stage("stage_deploy_produccion")
            | self._workflow_stage("stage_deploy_failed_produccion")
            | self._workflow_stage("stage_revision_general_funcional")
            | self._workflow_stage("stage_finalizada_development")
        )
        if (
            self.stage_id == self._workflow_stage("stage_uat_cliente")
            and destination not in successful_path
            and not self._uat_capability()
        ):
            raise UserError(_("Registre el resultado mediante «Validar UAT» antes de volver a trabajar."))
        return super()._check_development_move(destination, vals)

    def write(self, vals):
        vals = dict(vals)
        if PROTECTED_FIELDS.intersection(vals) and not self._uat_capability():
            raise AccessError(_("Los vínculos y ciclos UAT no se pueden editar directamente."))
        relevant = (
            self.ESTIMATED_HOURS_FIELDS | {
                "stage_id", "uat_sale_line_id", "project_id", "parent_id",
                "task_type", "company_id", "partner_id", "sale_line_id",
            }
        )
        if relevant.intersection(vals):
            if vals.get("uat_sale_line_id"):
                (self.sudo().mapped("uat_sale_line_id") | self.env["sale.order.line"].sudo().browse(
                    vals["uat_sale_line_id"]
                ))._uat_lock_budget()
            self._uat_lock()
        if vals.get("parent_id"):
            parent = self.browse(vals["parent_id"])
            if parent.uat_origin_id or parent.sudo().sale_line_id._uat_dedicated_tasks():
                raise UserError(_("No puede insertar tareas en el presupuesto dedicado de una Mejora."))
        improvements = self.filtered("uat_origin_id")
        if improvements and vals.get("stage_id"):
            destination = self.env["project.task.type"].browse(vals["stage_id"])
            preparation = (
                self._workflow_stage("stage_estimacion")
                | self._workflow_stage("stage_desestimada")
                | self._get_pendiente_stage("development")
            )
            if destination not in preparation:
                improvements._uat_check_ready()
        structural = {"project_id", "parent_id", "task_type", "company_id", "partner_id", "sale_line_id"}.intersection(vals)
        if self.filtered(lambda task: (task.uat_bug_event_id or task.uat_improvement_ids) and any(
            task[name] != vals[name] if name == "task_type"
            else task[name].id != vals[name] for name in structural
            if name != "sale_line_id" or not task.uat_origin_id
        )):
            raise UserError(_("No puede cambiar la estructura de origen de un ciclo UAT trazado."))
        changed_proposals = improvements.filtered(lambda task: any(
            task[name] != vals[name] if name != "uat_sale_line_id"
            else task[name].id != vals[name]
            for name in (self.ESTIMATED_HOURS_FIELDS | {"uat_sale_line_id"}).intersection(vals)
        ))
        if changed_proposals and "sale_line_id" in vals:
            raise UserError(_("Use la línea comercial de la Mejora."))
        result = super().write(vals)
        self._uat_check_structure()
        if vals.get("uat_sale_line_id"):
            for task in improvements:
                task.uat_sale_line_id._uat_bind_quote(task)
        if vals.get("stage_id"):
            for task in self:
                internal_vals = {"uat_version": task.uat_version + 1}
                if (
                    task.stage_id == task._workflow_stage("stage_uat_cliente")
                    or task.stage_id.is_closed
                ):
                    internal_vals["uat_bug_event_id"] = False
                task.with_context(_uat_operation=UAT_OPERATION).write(internal_vals)
        if changed_proposals and not self._uat_capability():
            changed_proposals._uat_invalidate_proposal()
        return result

    @api.constrains(
        "uat_origin_id", "parent_id", "project_id", "task_type",
        "uat_sale_line_id", "sale_line_id", "partner_id",
    )
    def _uat_check_structure(self):
        for task in self:
            owners = task.sudo().sale_line_id._uat_dedicated_tasks()
            if owners and task not in owners and not task.is_calyx_sale_root:
                raise ValidationError(_("La línea comercial de una Mejora es exclusiva de esa tarea."))
        for task in self.filtered("uat_origin_id"):
            if (
                task.parent_id or task.task_type != "development"
                or task.project_id != task.uat_origin_id.project_id
                or task.company_id != task.uat_origin_id.company_id
                or task.partner_id != task.uat_origin_id.partner_id
                or task.sale_line_id != task.uat_sale_line_id
            ):
                raise ValidationError(_(
                    "La Mejora debe ser independiente, conservar proyecto y "
                    "cliente de origen y usar solo su línea comercial dedicada."
                ))
            if task.uat_sale_line_id:
                task._uat_check_commercial_scope()
                used = self.sudo().with_context(active_test=False).search_count([
                    ("uat_sale_line_id", "=", task.uat_sale_line_id.id),
                    ("id", "!=", task.id),
                ])
                if used:
                    raise ValidationError(_("La línea comercial ya pertenece a otra Mejora."))

    @api.depends(
        "uat_origin_id", "uat_sale_line_id", "commercial_partner_id",
        "parent_id.sale_line_id", "project_id.sale_line_id", "allow_billable",
    )
    def _compute_sale_line(self):
        improvements = self.filtered("uat_origin_id")
        super(ProjectTask, self - improvements)._compute_sale_line()
        for task in improvements:
            task.sale_line_id = task.uat_sale_line_id

    def unlink(self):
        if self.filtered(lambda t: t.uat_origin_id or t.event_ids.filtered(
            lambda e: e.event_type == "uat"
        )):
            raise UserError(_("Archive las tareas con trazabilidad UAT; no pueden eliminarse."))
        return super().unlink()

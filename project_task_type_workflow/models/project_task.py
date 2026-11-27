from typing import Any, Dict, List, Set

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .project_task_type import WORKFLOW_ROLES

# xmlids of the canonical "Pendiente" stage per task type (see
# data/project_task_type_data.xml), used to detect a backward move to it.
PENDIENTE_STAGE_XMLIDS = {
    "functional": "project_task_type_workflow.stage_pendiente_functional",
    "development": "project_task_type_workflow.stage_pendiente_development",
}


class ProjectTask(models.Model):
    """Classify tasks by type to restrict their available stages."""

    _inherit = "project.task"

    task_type = fields.Selection(
        selection=[
            ("unclassified", "Sin clasificar"),
            ("functional", "Gestión/Funcional"),
            ("development", "Desarrollo"),
        ],
        string="Tipo de tarea",
        default="unclassified",
        required=True,
        tracking=True,
        help="Determina el circuito de estados disponible y el responsable "
        "jerárquico máximo de la tarea.",
    )
    max_responsible_id = fields.Many2one(
        comodel_name="res.users",
        string="Responsable jerárquico máximo",
        compute="_compute_max_responsible_id",
        help="PM para tareas de Gestión/Funcional, Líder Técnico para tareas de Desarrollo.",
    )
    event_ids = fields.One2many(
        comodel_name="project.task.event",
        inverse_name="task_id",
        string="Historial de eventos",
        readonly=True,
    )
    event_count = fields.Integer(
        string="Cantidad de eventos",
        compute="_compute_event_count",
        store=True,
    )
    last_testing_failed_event_id = fields.Many2one(
        comodel_name="project.task.event",
        string="Último fallo de testing",
        compute="_compute_last_events",
        store=True,
    )
    last_testing_failed_error_target = fields.Selection(
        related="last_testing_failed_event_id.error_target",
        string="Tipo de último fallo",
        readonly=True,
    )
    can_mark_testing_failed = fields.Boolean(
        compute="_compute_can_event_actions",
    )
    can_suspend_task = fields.Boolean(
        compute="_compute_can_event_actions",
    )

    @api.depends("event_ids")
    def _compute_event_count(self):
        for task in self:
            task.event_count = len(task.event_ids)

    @api.depends("event_ids.event_type", "event_ids.date")
    def _compute_last_events(self):
        for task in self:
            failed_events = task.event_ids.filtered(lambda e: e.event_type == "testing_failed")
            if failed_events:
                sorted_events = sorted(
                    list(failed_events),
                    key=lambda e: (e.date or fields.Datetime.now(), (e._origin.id if hasattr(e, '_origin') and e._origin else (e.id or 0)) or 0),
                    reverse=True,
                )
                task.last_testing_failed_event_id = sorted_events[0]
            else:
                task.last_testing_failed_event_id = False

    @api.depends(
        "stage_id", "task_type", "project_id", "user_ids",
        "project_id.user_id", "project_id.technical_leader_id",
        "project_id.workflow_functional_ids",
    )
    @api.depends_context("uid")
    def _compute_can_event_actions(self):
        pruebas_stage = self._workflow_stage("stage_pruebas")
        desarrollo_stage = self._workflow_stage("stage_desarrollo")
        for task in self:
            roles = task.project_id._get_user_workflow_roles() if task.project_id else set()
            is_functional = bool(roles.intersection({"functional", "pm", "technical_leader"}))
            task.can_mark_testing_failed = bool(
                task.task_type == "development"
                and task.stage_id == pruebas_stage
                and is_functional
            )
            is_authorized_suspend = task._is_user_authorized_to_suspend()
            is_valid_stage_for_suspend = bool(
                desarrollo_stage
                and task.stage_id
                and task.stage_id.sequence <= desarrollo_stage.sequence
            )
            task.can_suspend_task = bool(
                task.task_type == "development"
                and is_valid_stage_for_suspend
                and is_authorized_suspend
            )

    def action_open_testing_failed_wizard(self):
        """Open the wizard to record a testing failed event and move the task."""
        self.ensure_one()
        roles = self.project_id._get_user_workflow_roles() if self.project_id else set()
        if "functional" not in roles and not roles.intersection({"pm", "technical_leader"}):
            raise UserError(_("Solo los usuarios con rol Funcional pueden marcar Testing Failed."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Registrar fallo de testing"),
            "res_model": "project.task.event.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_task_id": self.id,
                "default_event_type": "testing_failed",
            },
        }

    def action_open_suspend_wizard(self):
        """Open the wizard to suspend the task with a mandatory reason."""
        self.ensure_one()
        if not self._is_user_authorized_to_suspend():
            raise UserError(_(
                "Solo el PM, el Líder Técnico o un responsable actual "
                "sin rol Funcional pueden suspender la tarea. "
                "Estar asignado no habilita al Funcional para suspender."
            ))
        stage_desarrollo = self._workflow_stage("stage_desarrollo")
        if self.stage_id and stage_desarrollo and self.stage_id.sequence > stage_desarrollo.sequence:
            raise UserError(_(
                "El estado «Suspendida» solo está habilitado para tarjetas en estados "
                "hasta «Desarrollo» inclusive (no disponible desde Deploy a Staging en adelante)."
            ))
        return {
            "type": "ir.actions.act_window",
            "name": _("Suspender tarea"),
            "res_model": "project.task.event.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_task_id": self.id,
                "default_event_type": "suspended",
            },
        }

    def _is_user_authorized_to_suspend(self) -> bool:
        """Exclude functional assignees unless they are the project PM/leader."""
        self.ensure_one()
        roles = (
            self.project_id._get_user_workflow_roles()
            if self.project_id else set()
        )
        return bool(roles.intersection({"pm", "technical_leader"})) or (
            "functional" not in roles and self.env.user in self.user_ids
        )

    @api.onchange("project_id", "task_type")
    def _onchange_task_type_stage_domain(self):
        """Offer only stages enabled for the selected task type in the UI."""
        if not self._origin.id:
            pending = self._get_pendiente_stage(self.task_type)
            if pending:
                self.stage_id = pending
        domain = [("project_ids", "=", self.project_id.id)] if self.project_id else []
        domain += [("task_type_scope", "=", self.task_type)]
        return {"domain": {"stage_id": domain}}

    @api.onchange("parent_id")
    def _onchange_parent_workflow_project(self) -> None:
        """Show the parent's project in both native subtask project fields."""
        if self.parent_id:
            self.project_id = self.parent_id.project_id
            self.display_project_id = self.parent_id.project_id

    @api.model
    def _prepare_parent_project_values(
        self, values: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Keep the actual and visible project aligned with the parent."""
        prepared = dict(values)
        parent = self.browse(prepared.get("parent_id")).exists()
        if parent:
            prepared.update({
                "project_id": parent.project_id.id,
                "display_project_id": parent.project_id.id,
            })
        return prepared

    @api.model
    def default_get(self, fields_list: List[str]) -> Dict[str, Any]:
        """Default new classified tasks to their canonical pending stage."""
        values = super().default_get(fields_list)
        parent = self.browse(values.get(
            "parent_id", self.env.context.get("default_parent_id"),
        )).exists()
        if parent:
            for field_name in ("project_id", "display_project_id"):
                if field_name in fields_list:
                    values[field_name] = parent.project_id.id
        task_type = values.get(
            "task_type", self.env.context.get("default_task_type"),
        )
        if "stage_id" in fields_list:
            pending = self._get_pendiente_stage(task_type)
            if pending:
                values["stage_id"] = pending.id
        return values

    @api.model_create_multi
    def create(self, vals_list: List[Dict[str, Any]]) -> models.Model:
        """Apply type-specific defaults also to RPC and batch creation."""
        prepared = []
        for vals in vals_list:
            values = dict(vals)
            parent_id = values.get(
                "parent_id", self.env.context.get("default_parent_id"),
            )
            if parent_id:
                values["parent_id"] = parent_id
                values = self._prepare_parent_project_values(values)
            task_type = values.get(
                "task_type",
                self.env.context.get("default_task_type", "unclassified"),
            )
            if "stage_id" not in values:
                pending = self._get_pendiente_stage(task_type)
                if pending:
                    values["stage_id"] = pending.id
            prepared.append(values)
        return super().create(prepared)

    @api.depends("task_type", "project_id.user_id", "project_id.technical_leader_id")
    def _compute_max_responsible_id(self):
        """Identify the top hierarchical responsible according to the task type."""
        for task in self:
            if task.task_type == "functional":
                task.max_responsible_id = task.project_id.user_id
            elif task.task_type == "development":
                task.max_responsible_id = task.project_id.technical_leader_id
            else:
                task.max_responsible_id = False

    def _get_pendiente_stage(self, task_type):
        """Return the canonical "Pendiente" stage for a given task type."""
        xmlid = PENDIENTE_STAGE_XMLIDS.get(task_type)
        if not xmlid:
            return self.env["project.task.type"]
        return self.env.ref(xmlid, raise_if_not_found=False) or self.env["project.task.type"]

    def _get_authorized_users(self):
        """Return the project PM and technical leader allowed to reopen a task."""
        self.ensure_one()
        project = self.project_id
        if not project:
            return self.env["res.users"]
        return project._get_workflow_pm() | project.technical_leader_id

    def _check_reopen_to_pendiente(self, vals):
        """Block moving a started task back to "Pendiente" unless done by its PM."""
        if not vals.get("stage_id"):
            return
        new_stage = self.env["project.task.type"].browse(vals["stage_id"])
        blocked_tasks = self.env["project.task"]
        for task in self:
            if task.task_type != "functional" or new_stage == task.stage_id:
                continue
            pendiente_stage = task._get_pendiente_stage(task.task_type)
            if not pendiente_stage or new_stage != pendiente_stage:
                continue
            if task.stage_id.sequence <= pendiente_stage.sequence:
                continue
            if self.env.user not in task._get_authorized_users():
                blocked_tasks |= task
        if blocked_tasks:
            raise UserError(_(
                "Solo el PM o el Líder Técnico del proyecto pueden volver a "
                "mover a «Pendiente» "
                "las siguientes tareas ya iniciadas: %s"
            ) % ", ".join(blocked_tasks.mapped("name")))

    def _workflow_stage(self, xmlid: str) -> models.Model:
        """Resolve special stages by identity, never by translated names."""
        return self.env.ref(
            f"project_task_type_workflow.{xmlid}",
            raise_if_not_found=False,
        ) or self.env["project.task.type"]

    def _workflow_move_error(
        self, destination: models.Model, roles: Set[str],
    ) -> None:
        """Report the denied movement without mutating any task."""
        self.ensure_one()
        labels = ", ".join(
            _(label) for role, label in WORKFLOW_ROLES.items()
            if role in roles
        ) or _("Ningún rol configurado")
        raise UserError(_(
            "No tiene permiso para mover la tarea «%(task)s» desde "
            "«%(origin)s» hacia «%(destination)s». "
            "Roles habilitados: %(roles)s."
        ) % {
            "task": self.display_name,
            "origin": self.stage_id.name or _("Sin etapa"),
            "destination": destination.name or _("Sin etapa"),
            "roles": labels,
        })

    def _check_development_move(
        self, destination: models.Model, vals: Dict[str, Any],
    ) -> None:
        """Authorize one move against the original project and assignees."""
        self.ensure_one()
        target_type = vals.get("task_type", self.task_type)
        target_project = self.env["project.project"].browse(
            vals.get("project_id", self.project_id.id)
        )
        if not destination:
            self._workflow_move_error(destination, set())
        if (
            destination.task_type_scope != target_type
            or target_project not in destination.project_ids
        ):
            raise ValidationError(_(
                "La etapa de destino no está habilitada para el tipo "
                "de tarea y el proyecto seleccionados."
            ))

        roles = (
            self.project_id._get_user_workflow_roles()
            if self.project_id else set()
        )
        leaders = {"pm", "technical_leader"}
        if self.task_type != "development":
            if not roles.intersection(leaders):
                self._workflow_move_error(destination, leaders)
            return
        if destination == self._workflow_stage("stage_suspendida"):
            stage_desarrollo = self._workflow_stage("stage_desarrollo")
            if (
                self.stage_id
                and stage_desarrollo
                and self.stage_id.sequence > stage_desarrollo.sequence
            ):
                raise UserError(_(
                    "El estado «Suspendida» solo está habilitado para tarjetas "
                    "en estados hasta «Desarrollo» inclusive (no disponible desde "
                    "Deploy a Staging en adelante)."
                ))
            if not self._is_user_authorized_to_suspend():
                raise UserError(_(
                    "Solo el PM, el Líder Técnico o un responsable "
                    "actual sin rol Funcional pueden suspender la tarea "
                    "«%s». Estar asignado no habilita al Funcional "
                    "para suspender."
                ) % self.display_name)
            if not self.env.context.get("skip_event_check"):
                raise UserError(_(
                    "Para suspender la tarea debe utilizar el botón «Suspender» "
                    "para indicar el motivo correspondiente."
                ))
            return
        if destination == self._get_pendiente_stage("development"):
            if not roles.intersection(leaders):
                self._workflow_move_error(destination, leaders)
            return

        if self.stage_id == self._workflow_stage("stage_testing_failed"):
            dev_roles = {"developer", "technical_leader"}
            if not roles.intersection(dev_roles):
                self._workflow_move_error(destination, dev_roles)
            target_code_stage = self._workflow_stage("stage_desarrollo")
            target_deploy_stage = self._workflow_stage("stage_deploy_failed_staging")
            last_target = self.last_testing_failed_error_target
            if last_target == "code":
                if destination != target_code_stage:
                    raise UserError(_(
                        "El último fallo registrado indica un error de código. "
                        "El único destino habilitado desde Testing Failed es «Desarrollo»."
                    ))
            elif last_target == "deploy":
                if destination != target_deploy_stage:
                    raise UserError(_(
                        "El último fallo registrado indica un error de deploy. "
                        "El único destino habilitado desde Testing Failed es «Deploy Failed Staging»."
                    ))
            elif destination not in (target_code_stage | target_deploy_stage):
                raise UserError(_(
                    "Desde Testing Failed solo se puede mover a «Desarrollo» o «Deploy Failed Staging»."
                ))
            return

        permitted = (
            self.stage_id._get_workflow_roles()
            if self.stage_id else set()
        )
        if not roles.intersection(permitted):
            self._workflow_move_error(destination, permitted)
        if self.stage_id == self._workflow_stage("stage_pruebas"):
            testing_stages = (
                self._workflow_stage("stage_testing_ok")
                | self._workflow_stage("stage_testing_failed")
            )
            if destination not in testing_stages:
                raise UserError(_(
                    "Desde Pruebas solo se puede mover a Testing OK o "
                    "Testing Failed, salvo las excepciones de retorno "
                    "a Pendiente o pase a Suspendida."
                ))
        if destination == self._workflow_stage("stage_testing_failed"):
            if not self.env.context.get("skip_event_check"):
                raise UserError(_(
                    "Para mover la tarjeta a «Testing Failed» debe registrar el caso "
                    "utilizando el botón «Testing Failed», indicando la descripción y si "
                    "el error apunta a código o deploy."
                ))

    def _check_development_workflow(self, vals: Dict[str, Any]) -> None:
        """Validate the complete batch before any state is written."""
        for task in self:
            target_type = vals.get("task_type", task.task_type)
            if "development" not in (task.task_type, target_type):
                continue
            if (
                task.task_type == "development"
                and "project_id" in vals
                and vals["project_id"] != task.project_id.id
                and self.env.user not in task._get_authorized_users()
            ):
                raise UserError(_(
                    "Solo el PM o el Líder Técnico pueden cambiar el "
                    "proyecto de la tarea de Desarrollo «%s»."
                ) % task.display_name)
            if (
                task.task_type == "development"
                and target_type != "development"
                and self.env.user not in task._get_authorized_users()
            ):
                raise UserError(_(
                    "Solo el PM o el Líder Técnico pueden sacar la tarea "
                    "«%s» del circuito de Desarrollo."
                ) % task.display_name)
            if "stage_id" not in vals:
                continue
            destination = self.env["project.task.type"].browse(
                vals["stage_id"]
            ).exists()
            if destination == task.stage_id:
                continue
            task._check_development_move(destination, vals)

    def write(self, vals: Dict[str, Any]) -> bool:
        """Enforce development permissions and preserve functional reopening."""
        if "parent_id" in vals:
            vals = self._prepare_parent_project_values(vals)
        self._check_development_workflow(vals)
        self._check_reopen_to_pendiente(vals)
        result = super().write(vals)
        if "project_id" in vals:
            for task in self:
                children = task.with_context(active_test=False).child_ids
                inherited = children.filtered(
                    lambda child: (
                        child.project_id != task.project_id
                        or child.display_project_id != task.project_id
                    )
                )
                if inherited:
                    inherited.write({"parent_id": task.id})
        return result

    @api.constrains("task_type", "stage_id")
    def _check_stage_matches_task_type(self):
        """Block moving a task to a stage outside its task type's allowed set."""
        for task in self:
            if task.task_type == "unclassified" or not task.stage_id:
                continue
            if task.stage_id.task_type_scope != task.task_type:
                raise ValidationError(_(
                    "El estado «%(stage)s» no está habilitado para el tipo de "
                    "tarea «%(task_type)s»."
                ) % {
                    "stage": task.stage_id.name,
                    "task_type": dict(
                        task._fields["task_type"].selection
                    )[task.task_type],
                })

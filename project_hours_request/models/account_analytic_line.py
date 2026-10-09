from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class AccountAnalyticLine(models.Model):
    """Validate task timesheets against their stage and planned hours."""

    _inherit = "account.analytic.line"

    timesheet_segment = fields.Selection(
        selection=[
            ("development", "Desarrollo"),
            ("deploy", "Deploy"),
            ("functional_test", "Funcional Pruebas"),
            ("uat_support", "UAT/Soporte"),
        ],
        string="Tramo de la carga",
        readonly=True,
        copy=False,
    )

    @api.model
    def _lock_tasks(self, tasks):
        """Serialize cap checks for concurrent timesheet entries."""
        if tasks:
            self.env.cr.execute(
                "UPDATE project_task SET write_date = "
                "clock_timestamp() WHERE id IN %s",
                [tuple(sorted(tasks.ids))],
            )

    @api.model
    def _prepare_segment(self, vals):
        """Assign the current task stage segment to a timesheet value set."""
        task = self.env["project.task"].browse(vals.get("task_id"))
        if not task:
            if vals.get("timesheet_segment"):
                raise UserError(_("El tramo de horas requiere una tarea."))
            return vals
        stage_type = task.stage_id.get_timesheet_stage_type()
        if stage_type in ("pending", "done"):
            raise UserError(_(
                "No se pueden cargar horas en una tarea en estado %s."
            ) % task.stage_id.name)
        if task.task_type == "development":
            allowed_segments = {
                "development",
                "deploy",
                "functional_test",
                "uat_support",
            }
            if stage_type not in allowed_segments:
                raise UserError(_(
                    "La etapa de una tarjeta de Desarrollo debe tener un "
                    "tramo de horas configurado."
                ))
            if vals.get("timesheet_segment") not in (None, False, stage_type):
                raise UserError(_("El tramo debe coincidir con la etapa."))
            vals["timesheet_segment"] = stage_type
        elif stage_type == "uat_support" or vals.get("timesheet_segment"):
            raise UserError(_(
                "UAT/Soporte solo puede cargarse en tareas de Desarrollo."
            ))
        else:
            vals["timesheet_segment"] = False
        return vals

    def _validate_development_caps(self):
        """Ensure consumed hours do not exceed planned plus approved margin."""
        self.mapped("task_id")._validate_uat_hours()
        development_tasks = self.mapped("task_id").filtered(
            lambda task: (
                task.task_type == "development"
                and not task._get_global_hours_cap_root()
                and not (
                    "config_level" in task._fields
                    and task.config_level
                )
            )
        )
        for task in development_tasks:
            for segment in (
                "development",
                "deploy",
                "functional_test",
            ):
                consumed = task._get_consumed_hours(segment)
                allowed = (
                    task._get_planned_hours(segment)
                    + task._get_approved_margin_hours(segment)
                )
                if float_compare(
                    consumed,
                    allowed,
                    precision_digits=2,
                ) > 0:
                    raise UserError(_(
                        "La carga supera el tope de %(segment)s "
                        "(%(allowed)s hs). Solicite horas adicionales para "
                        "habilitar horas del margen."
                    ) % {
                        "segment": task._get_segment_label(segment),
                        "allowed": allowed,
                    })

    def _get_global_hours_cap_roots(self, tasks):
        """Return configured standalone roots represented by tasks."""
        roots = self.env["project.task"]
        for task in tasks:
            roots |= task._get_global_hours_cap_root()
        return roots

    def _lock_global_hours_cap_roots(self, tasks):
        """Serialize global-cap validations on standalone task trees."""
        self._lock_tasks(self._get_global_hours_cap_roots(tasks))

    def _validate_global_hours_caps(self):
        """Keep configured standalone task trees within their root cap."""
        roots = self._get_global_hours_cap_roots(self.mapped("task_id"))
        for root in roots:
            consumed = root._get_total_consumed_hours()
            if float_compare(
                consumed,
                root.hours_cap,
                precision_digits=2,
            ) > 0:
                raise UserError(_(
                    "La carga total supera el tope de %(cap)s hs de "
                    "%(task)s (consumido: %(consumed)s hs)."
                ) % {
                    "cap": root.hours_cap,
                    "task": root.display_name,
                    "consumed": consumed,
                })

    @api.model_create_multi
    def create(self, vals_list):
        """Validate and persist the segment of new timesheet lines."""
        tasks = self.env["project.task"].browse(
            [vals["task_id"] for vals in vals_list if vals.get("task_id")]
        )
        self._lock_tasks(tasks)
        self._lock_global_hours_cap_roots(tasks)
        prepared_vals = [self._prepare_segment(vals) for vals in vals_list]
        lines = super().create(prepared_vals)
        lines._validate_global_hours_caps()
        lines._validate_development_caps()
        return lines

    def write(self, vals):
        """Revalidate lines when their task or consumed hours change."""
        if "task_id" in vals and all(
            line.task_id.id == vals["task_id"] for line in self
        ):
            vals = dict(vals)
            vals.pop("task_id")
        if "timesheet_segment" in vals and "task_id" not in vals:
            if any(
                line.timesheet_segment != vals["timesheet_segment"]
                for line in self
            ):
                raise UserError(_("No puede cambiar el tramo histórico."))
        if "task_id" in vals and not vals["task_id"]:
            if self.filtered("timesheet_segment"):
                raise UserError(_(
                    "No puede quitar la tarea de una carga con tramo."
                ))
        if not {"task_id", "unit_amount"}.intersection(vals):
            return super().write(vals)

        tasks = self.mapped("task_id")
        if vals.get("task_id"):
            tasks |= self.env["project.task"].browse(vals["task_id"])
            target = self.env["project.task"].browse(vals["task_id"])
            if self.filtered(
                lambda line: line.timesheet_segment == "uat_support"
            ) and target.stage_id.get_timesheet_stage_type() != "uat_support":
                raise UserError(_(
                    "Una carga UAT no puede trasladarse a otra bolsa."
                ))
        self._lock_tasks(tasks)
        self._lock_global_hours_cap_roots(tasks)
        if vals.get("task_id"):
            vals = self._prepare_segment(vals)
        else:
            if "unit_amount" in vals:
                for line in self:
                    if (
                        line.task_id.stage_id.get_timesheet_stage_type()
                        == "uat_support"
                        and line.timesheet_segment != "uat_support"
                        and float_compare(
                            vals["unit_amount"], line.unit_amount,
                            precision_digits=2,
                        ) > 0
                    ):
                        raise UserError(_(
                            "Durante UAT no puede incrementar un parte de "
                            "otro tramo. Registre las nuevas horas en UAT."
                        ))
            for task in tasks:
                stage_type = task.stage_id.get_timesheet_stage_type()
                if stage_type in ("pending", "done"):
                    raise UserError(_(
                        "No se pueden modificar horas en una tarea en "
                        "estado %s."
                    ) % task.stage_id.name)
        result = super().write(vals)
        self._validate_global_hours_caps()
        self._validate_development_caps()
        return result

    def unlink(self):
        """Keep finalized tasks with their required consumed time."""
        done_tasks = self.mapped("task_id").filtered(
            lambda task: task.stage_id.get_timesheet_stage_type() == "done"
        )
        if done_tasks:
            raise UserError(_(
                "No se pueden eliminar horas de una tarea finalizada."
            ))
        return super().unlink()
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
                "SELECT id FROM project_task WHERE id IN %s FOR UPDATE",
                [tuple(sorted(tasks.ids))],
            )

    @api.model
    def _prepare_segment(self, vals):
        """Assign the current task stage segment to a timesheet value set."""
        task = self.env["project.task"].browse(vals.get("task_id"))
        if not task:
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
            }
            if stage_type not in allowed_segments:
                raise UserError(_(
                    "La etapa de una tarjeta de Desarrollo debe tener un "
                    "tramo de horas configurado."
                ))
            vals["timesheet_segment"] = stage_type
        return vals

    def _validate_development_caps(self):
        """Ensure consumed hours do not exceed planned plus approved margin."""
        development_tasks = self.mapped("task_id").filtered(
            lambda task: task.task_type == "development"
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

    @api.model_create_multi
    def create(self, vals_list):
        """Validate and persist the segment of new timesheet lines."""
        tasks = self.env["project.task"].browse(
            [vals["task_id"] for vals in vals_list if vals.get("task_id")]
        )
        self._lock_tasks(tasks)
        prepared_vals = [self._prepare_segment(vals) for vals in vals_list]
        lines = super().create(prepared_vals)
        lines._validate_development_caps()
        return lines

    def write(self, vals):
        """Revalidate lines when their task or consumed hours change."""
        if not {"task_id", "unit_amount"}.intersection(vals):
            return super().write(vals)

        tasks = self.mapped("task_id")
        if vals.get("task_id"):
            tasks |= self.env["project.task"].browse(vals["task_id"])
        self._lock_tasks(tasks)
        if vals.get("task_id"):
            vals = self._prepare_segment(vals)
        else:
            for task in tasks:
                stage_type = task.stage_id.get_timesheet_stage_type()
                if stage_type in ("pending", "done"):
                    raise UserError(_(
                        "No se pueden modificar horas en una tarea en "
                        "estado %s."
                    ) % task.stage_id.name)
        result = super().write(vals)
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
from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class AccountAnalyticLine(models.Model):
    """Enforce level-specific task timesheet caps."""

    _inherit = "account.analytic.line"

    def _get_configuration_roots(self, tasks):
        """Collect Configuraciones roots for the supplied tasks."""
        roots = self.env["project.task"]
        for task in tasks:
            roots |= task._get_configuration_root()
        return roots

    def _lock_configuration_roots(self, tasks):
        """Serialize cap checks across all branches of each root task."""
        roots = self._get_configuration_roots(tasks)
        if roots:
            self.env.cr.execute(
                "SELECT id FROM project_task WHERE id IN %s FOR UPDATE",
                [tuple(sorted(roots.ids))],
            )

    def _validate_configuration_caps(self):
        """Enforce the root cap and shared excess across level-three tasks."""
        roots = self._get_configuration_roots(self.mapped("task_id"))
        self._lock_configuration_roots(self.mapped("task_id"))
        for root in roots:
            consumed = root._get_total_consumed_hours()
            if float_compare(
                consumed,
                root.hours_cap,
                precision_digits=2,
            ) > 0:
                raise UserError(_(
                    "La carga supera el tope global de %(cap)s hs "
                    "(consumido: %(consumed)s hs)."
                ) % {"cap": root.hours_cap, "consumed": consumed})
            level_three = self.env["project.task"].search([
                ("id", "child_of", root.id),
                ("config_level", "=", 3),
            ])
            allocated = sum(level_three.mapped("hours_cap"))
            shared_allowance = max(root.hours_cap - allocated, 0.0)
            branch_overage = sum(
                max(task._get_total_consumed_hours() - task.hours_cap, 0.0)
                for task in level_three
            )
            if float_compare(
                branch_overage,
                shared_allowance,
                precision_digits=2,
            ) > 0:
                raise UserError(_(
                    "La carga excede el tope asignado de las tareas de nivel "
                    "3 y la bolsa adicional compartida."
                ))

    def _check_configuration_timesheet_targets(self, tasks):
        """Reject timesheets on the non-chargeable levels two and three."""
        blocked = tasks.filtered(lambda task: task.config_level in (2, 3))
        if blocked:
            raise UserError(_(
                "Las horas solo se pueden cargar en subtareas de nivel 4 de "
                "Configuraciones."
            ))

    @api.model_create_multi
    def create(self, vals_list):
        """Validate hierarchy levels before accepting timesheet values."""
        tasks = self.env["project.task"].browse(
            [values["task_id"] for values in vals_list if values.get("task_id")]
        )
        self._check_configuration_timesheet_targets(tasks)
        self._lock_configuration_roots(tasks)
        lines = super().create(vals_list)
        lines._validate_configuration_caps()
        return lines

    def write(self, values):
        """Recheck hierarchy caps when task or duration changes."""
        if not {"task_id", "unit_amount"}.intersection(values):
            return super().write(values)
        tasks = self.mapped("task_id")
        if values.get("task_id"):
            tasks |= self.env["project.task"].browse(values["task_id"])
        self._check_configuration_timesheet_targets(tasks)
        self._lock_configuration_roots(tasks)
        result = super().write(values)
        self._validate_configuration_caps()
        return result
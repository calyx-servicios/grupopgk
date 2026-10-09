from typing import Any, Dict, List

from odoo import _, api, models
from odoo.exceptions import UserError


class AccountAnalyticLine(models.Model):
    """Protect UAT reservations in every task-based timesheet entry path."""

    _inherit = "account.analytic.line"

    @api.model
    def _lock_tasks(self, tasks: Any) -> None:
        """Serialize the contractual roots before the task-level locks."""
        roots = tasks._get_calyx_uat_roots()
        super()._lock_tasks(roots)
        super()._lock_tasks(tasks - roots)

    @api.model
    def _prepare_segment(self, values: Dict[str, Any]) -> Dict[str, Any]:
        """Block UAT entries until the PM activates their reservation."""
        values = super()._prepare_segment(values)
        if values.get("timesheet_segment") == "uat_support":
            task = self.env["project.task"].browse(values["task_id"])
            root = task._get_calyx_uat_root()
            if root and root.calyx_uat_state != "active":
                raise UserError(_(
                    "El PM debe activar la reserva contractual UAT antes "
                    "de cargar horas."
                ))
        return values

    @api.model_create_multi
    def create(self, vals_list: List[Dict[str, Any]]) -> Any:
        """Enforce the reservation after the existing timesheet checks."""
        lines = super().create(vals_list)
        lines.mapped("task_id")._get_calyx_uat_roots().\
            _validate_calyx_uat_reservation()
        return lines

    def write(self, values: Dict[str, Any]) -> Any:
        """Keep previous and destination trees valid after corrections."""
        if "task_id" in values and all(
            line.task_id.id == values["task_id"] for line in self
        ):
            values = dict(values)
            values.pop("task_id")
        if not {"task_id", "unit_amount"}.intersection(values):
            return super().write(values)
        roots = self.mapped("task_id")._get_calyx_uat_roots()
        if "task_id" in values:
            target = self.env["project.task"].browse(values["task_id"])
            destination = target._get_calyx_uat_roots()
            if set(roots.ids) != set(destination.ids) and roots:
                raise UserError(_(
                    "No puede trasladar horas entre bolsas contractuales."
                ))
            if self.filtered(
                lambda line: line.timesheet_segment == "uat_support"
            ) and target.stage_id.get_timesheet_stage_type() != "uat_support":
                raise UserError(_(
                    "Una carga UAT no puede trasladarse a otra bolsa."
                ))
        result = super().write(values)
        roots |= self.mapped("task_id")._get_calyx_uat_roots()
        roots._validate_calyx_uat_reservation()
        return result

    def unlink(self) -> bool:
        """Recheck branch reservations after removing a timesheet."""
        tasks = self.mapped("task_id")
        roots = tasks._get_calyx_uat_roots()
        self._lock_tasks(tasks)
        result = super().unlink()
        roots._validate_calyx_uat_reservation()
        return result
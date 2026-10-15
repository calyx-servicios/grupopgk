from odoo import api, fields, models


FINAL_STAGE_XMLIDS = (
    "project_task_type_workflow.stage_finalizada_functional",
    "project_task_type_workflow.stage_finalizada_development",
)


class ProjectTask(models.Model):
    _inherit = "project.task"

    progress_total_items = fields.Integer(
        string="Ítems totales",
        compute="_compute_real_progress",
        store=True,
        recursive=True,
    )
    progress_completed_items = fields.Integer(
        string="Ítems completados",
        compute="_compute_real_progress",
        store=True,
        recursive=True,
    )
    progress = fields.Float(
        string="Avance real",
        compute="_compute_real_progress",
        store=True,
        recursive=True,
        group_operator="avg",
        help=(
            "Porcentaje de subtareas finalizadas y criterios de aceptación "
            "validados sobre el total de ítems de toda la jerarquía."
        ),
    )
    hours_consumption_percentage = fields.Float(
        string="Consumo de horas (%)",
        compute="_compute_hours_consumption_percentage",
        store=True,
        group_operator="avg",
        help=(
            "Porcentaje de horas dedicadas, incluidas las subtareas, sobre "
            "las horas planificadas. Puede superar el 100%."
        ),
    )

    @api.depends(
        "acceptance_criteria_ids.is_validated",
        "child_ids.active",
        "child_ids.stage_id",
        "child_ids.progress_total_items",
        "child_ids.progress_completed_items",
    )
    def _compute_real_progress(self):
        final_stage_ids = {
            self.env.ref(xmlid).id
            for xmlid in FINAL_STAGE_XMLIDS
        }
        for task in self:
            criteria = task.acceptance_criteria_ids
            total_items = len(criteria)
            completed_items = len(criteria.filtered("is_validated"))
            for child in task.child_ids:
                total_items += 1 + child.progress_total_items
                completed_items += (
                    int(child.stage_id.id in final_stage_ids)
                    + child.progress_completed_items
                )
            task.progress_total_items = total_items
            task.progress_completed_items = completed_items
            task.progress = (
                round(100.0 * completed_items / total_items, 2)
                if total_items
                else 0.0
            )

    @api.depends("effective_hours", "subtask_effective_hours", "planned_hours")
    def _compute_progress_hours(self):
        for task in self:
            total_hours = task.effective_hours + task.subtask_effective_hours
            task.overtime = max(total_hours - task.planned_hours, 0.0)

    @api.depends("total_hours_spent", "planned_hours")
    def _compute_hours_consumption_percentage(self):
        for task in self:
            task.hours_consumption_percentage = (
                round(100.0 * task.total_hours_spent / task.planned_hours, 2)
                if task.planned_hours > 0.0
                else 0.0
            )

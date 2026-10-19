from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import format_datetime

from .project_task import (
    UAT_OPERATION, UAT_RESULTS, uat_accessible_task_ids, uat_task_access_domain,
)


class ProjectTaskEvent(models.Model):
    _inherit = "project.task.event"

    event_type = fields.Selection(
        selection_add=[("uat", "UAT Cliente")], ondelete={"uat": "cascade"},
    )
    uat_result = fields.Selection(UAT_RESULTS, string="Resultado UAT", index=True)
    uat_improvement_id = fields.Many2one(
        "project.task", string="Mejora generada", ondelete="restrict",
    )
    uat_task_access = fields.Boolean(
        compute="_compute_uat_task_access", search="_search_uat_task_access",
    )

    def _compute_uat_task_access(self):
        allowed = set(uat_accessible_task_ids(self.env))
        for event in self:
            event.uat_task_access = event.task_id.id in allowed

    def _search_uat_task_access(self, operator, value):
        return uat_task_access_domain(self.env, operator, value)

    def name_get(self):
        uat_events = self.filtered(lambda e: e.event_type == "uat" and e.uat_result)
        names = dict(super(ProjectTaskEvent, self - uat_events).name_get())
        results = dict(UAT_RESULTS)
        for event in uat_events:
            names[event.id] = "%s UAT · %s" % (
                results[event.uat_result],
                format_datetime(self.env, event.date, dt_format="dd/MM/yyyy HH:mm"),
            )
        return [(event.id, names[event.id]) for event in self]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("event_type") == "uat":
                if self.env.context.get("_uat_operation") is not UAT_OPERATION:
                    raise AccessError(_("Use «Validar UAT» para registrar el triage."))
                vals["user_id"] = self.env.uid
                vals["date"] = fields.Datetime.now()
        return super().create(vals_list)

    @api.constrains("event_type", "uat_result", "description", "uat_improvement_id")
    def _check_uat_event(self):
        for event in self.filtered(lambda e: e.event_type == "uat"):
            if not event.uat_result or not (event.description or "").strip():
                raise ValidationError(_("El resultado UAT y la descripción son obligatorios."))
            if bool(event.uat_improvement_id) != (event.uat_result == "improvement"):
                raise ValidationError(_("Solo el triage Mejora genera una tarea nueva."))

    def write(self, vals):
        if self.filtered(lambda e: e.event_type == "uat") or vals.get("event_type") == "uat":
            raise AccessError(_("Los eventos UAT son inmutables."))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda e: e.event_type == "uat"):
            raise AccessError(_("Los eventos UAT no pueden eliminarse."))
        return super().unlink()

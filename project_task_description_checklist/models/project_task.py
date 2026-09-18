from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import html2plaintext


def _plain_text(description):
    return html2plaintext(description or "").strip()


class ProjectTask(models.Model):
    _inherit = "project.task"

    acceptance_criteria_ids = fields.One2many(
        comodel_name="project.task.acceptance.criteria",
        inverse_name="task_id",
        string="Criterio de aceptación",
    )
    acceptance_criteria_validated = fields.Boolean(
        string="Checklist de aceptación validado",
        compute="_compute_acceptance_criteria_validated",
        store=True,
    )

    @api.depends("acceptance_criteria_ids.is_validated")
    def _compute_acceptance_criteria_validated(self):
        for task in self:
            lines = task.acceptance_criteria_ids
            task.acceptance_criteria_validated = bool(lines) and all(
                lines.mapped("is_validated")
            )

    @api.model_create_multi
    def create(self, vals_list):
        # Tasks auto-generated from a sale order line (e.g. sale_project) get their
        # content from that line and are exempt from the manual description rule.
        for vals in vals_list:
            if vals.get("sale_line_id"):
                continue
            if not _plain_text(vals.get("description")):
                raise ValidationError(_(
                    "Debe cargar la Descripción (Contexto + Qué hay que desarrollar) "
                    "para poder guardar la tarea."
                ))
        return super().create(vals_list)

    def write(self, vals):
        if "description" in vals:
            new_text = _plain_text(vals.get("description"))
            has_sale_line_field = "sale_line_id" in self._fields
            old_descriptions = {task.id: task.description for task in self}
            for task in self:
                is_automated = has_sale_line_field and (
                    task.sale_line_id or vals.get("sale_line_id")
                )
                if not is_automated and not new_text:
                    raise ValidationError(_(
                        "Debe cargar la Descripción (Contexto + Qué hay que "
                        "desarrollar) para poder guardar la tarea."
                    ))
            result = super().write(vals)
            for task in self:
                old_description = old_descriptions.get(task.id)
                if _plain_text(old_description) != new_text:
                    task._log_description_change(old_description, vals.get("description"))
            return result
        return super().write(vals)

    def _log_description_change(self, old_description, new_description):
        self.ensure_one()
        # Description stays editable; changes are tracked in the chatter instead of blocked.
        self.message_post(
            body=_(
                "<p><b>Descripción modificada.</b></p>"
                "<p><i>Antes:</i></p>%(old)s"
                "<p><i>Después:</i></p>%(new)s"
            ) % {
                "old": old_description or _("<p><i>(vacía)</i></p>"),
                "new": new_description or _("<p><i>(vacía)</i></p>"),
            },
            subtype_xmlid="mail.mt_note",
        )

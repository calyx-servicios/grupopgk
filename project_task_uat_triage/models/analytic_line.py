from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.float_utils import float_compare


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    uat_rework_event_id = fields.Many2one(
        "project.task.event", string="Retrabajo interno UAT", readonly=True,
        copy=False, ondelete="restrict", index=True,
    )
    uat_budget_line_id = fields.Many2one(
        "sale.order.line", string="Contrato de Mejora al registrar horas",
        readonly=True, copy=False, ondelete="restrict", index=True,
    )

    def _uat_check_timesheet_target(self, tasks):
        tasks._uat_check_ready()
        for task in tasks:
            if task.is_calyx_sale_root and task.sudo().sale_line_id._uat_dedicated_tasks():
                raise UserError(_("Cargue las horas en la Mejora, no en su contenedor contractual."))
            if task.uat_origin_id and task.stage_id.get_timesheet_stage_type() not in (
                "development", "deploy", "functional_test", "uat_support",
            ):
                raise UserError(_("La Mejora debe estar en ejecución para cargar horas."))

    @api.model_create_multi
    def create(self, vals_list):
        if any({"uat_rework_event_id", "uat_budget_line_id"}.intersection(vals) for vals in vals_list):
            raise AccessError(_("El tratamiento interno UAT lo determina el ciclo de la tarea."))
        vals_list = [dict(vals) for vals in vals_list]
        tasks = self.env["project.task"].browse([
            vals["task_id"] for vals in vals_list if vals.get("task_id")
        ])
        self._lock_tasks(tasks)
        tasks.invalidate_cache()
        self._uat_check_timesheet_target(tasks)
        for vals in vals_list:
            task = self.env["project.task"].browse(vals.get("task_id"))
            if vals.get("so_line") and vals.get("project_id"):
                owners = self.env["sale.order.line"].sudo().browse(
                    vals["so_line"]
                )._uat_dedicated_tasks()
                if owners and task not in owners:
                    raise UserError(_("El contrato de una Mejora solo admite horas de esa tarea."))
            if task.uat_origin_id:
                vals["uat_budget_line_id"] = task.uat_sale_line_id.id
                if vals.get("so_line") not in (None, False, task.uat_sale_line_id.id):
                    raise UserError(_("La Mejora solo puede usar su contrato dedicado."))
            if task and task.uat_bug_event_id and task.stage_id.get_timesheet_stage_type() in (
                "development", "deploy", "functional_test",
            ):
                if vals.get("so_line"):
                    raise UserError(_("El retrabajo Bug UAT no puede facturarse."))
                vals["uat_rework_event_id"] = task.uat_bug_event_id.id
                vals["so_line"] = False
        lines = super().create(vals_list)
        lines._uat_validate_budgets()
        return lines

    def write(self, vals):
        if {"uat_rework_event_id", "uat_budget_line_id"}.intersection(vals):
            raise AccessError(_("No puede cambiar el tratamiento histórico de un parte UAT."))
        internal = self.filtered("uat_rework_event_id")
        if "project_id" in vals and any(
            line.uat_budget_line_id and line.project_id.id != vals["project_id"]
            for line in self
        ):
            raise UserError(_("No puede cambiar el proyecto de un parte de Mejora."))
        if internal and (
            vals.get("so_line")
            or ("task_id" in vals and any(line.task_id.id != vals["task_id"] for line in internal))
            or ("project_id" in vals and any(line.project_id.id != vals["project_id"] for line in internal))
        ):
            raise UserError(_("El retrabajo interno no puede facturarse ni trasladarse a otra tarea."))
        tasks = self.mapped("task_id")
        if vals.get("task_id"):
            tasks |= self.env["project.task"].browse(vals["task_id"])
        if {"task_id", "project_id", "unit_amount", "so_line"}.intersection(vals):
            self._lock_tasks(tasks)
            tasks.invalidate_cache()
            if vals.get("so_line"):
                owners = self.env["sale.order.line"].sudo().browse(
                    vals["so_line"]
                )._uat_dedicated_tasks()
                if owners and any(
                    line.project_id and line.task_id not in owners for line in self
                ):
                    raise UserError(_("El contrato de una Mejora es exclusivo de su tarea."))
            if vals.get("task_id") or "unit_amount" in vals:
                for line in self:
                    increasing = "unit_amount" in vals and vals["unit_amount"] > line.unit_amount
                    moved = vals.get("task_id") and vals["task_id"] != line.task_id.id
                    if increasing or moved:
                        target = self.env["project.task"].browse(vals["task_id"]) if moved else line.task_id
                        self._uat_check_timesheet_target(target)
                        if (
                            target.uat_bug_event_id and not line.uat_rework_event_id
                            and target.stage_id.get_timesheet_stage_type() != "uat_support"
                        ):
                            raise UserError(_("Registre la corrección Bug UAT en un nuevo parte interno."))
            for line in self.filtered(lambda l: l.task_id.uat_origin_id and not l.uat_rework_event_id):
                if "so_line" in vals and vals["so_line"] != (
                    line.uat_budget_line_id.id or line.so_line.id
                ):
                    raise UserError(_("No puede cambiar la línea histórica de una Mejora."))
            if "task_id" in vals and any(
                line.task_id.id != vals["task_id"] and (
                    line.uat_budget_line_id
                    or self.env["project.task"].browse(vals["task_id"]).uat_origin_id
                ) for line in self
            ):
                raise UserError(_("No puede trasladar partes hacia o desde una Mejora independiente."))
        result = super().write(vals)
        self._uat_validate_budgets()
        return result

    @api.depends(
        "task_id.sale_line_id", "project_id.sale_line_id", "employee_id",
        "project_id.allow_billable", "uat_rework_event_id",
        "uat_budget_line_id",
    )
    def _compute_so_line(self):
        internal = self.filtered("uat_rework_event_id")
        historical = (self - internal).filtered("uat_budget_line_id")
        super(AccountAnalyticLine, self - internal - historical)._compute_so_line()
        for line in historical:
            line.so_line = line.uat_budget_line_id
        internal.so_line = False

    def _timesheet_determine_sale_line(self):
        self.ensure_one()
        if self.uat_rework_event_id:
            return self.env["sale.order.line"]
        if self.task_id.uat_origin_id:
            return self.task_id.uat_sale_line_id
        return super()._timesheet_determine_sale_line()

    def _uat_validate_budgets(self):
        lines = self.sudo().mapped("uat_budget_line_id") | self.sudo().mapped("task_id.uat_sale_line_id") | self.sudo().mapped("so_line").filtered(
            lambda line: line._uat_dedicated_tasks()
        )
        for line in lines.sudo():
            line._uat_lock_budget()
            entries = self.sudo().search([
                "|", ("so_line", "=", line.id), ("uat_budget_line_id", "=", line.id),
                ("uat_rework_event_id", "=", False),
                ("task_id", "!=", False),
            ])
            consumed = sum(entries.mapped("unit_amount"))
            non_uat = sum(entries.filtered(
                lambda entry: entry.timesheet_segment != "uat_support"
            ).mapped("unit_amount"))
            if (
                float_compare(consumed, line.contrated_hours, precision_digits=2) > 0
                or float_compare(
                    non_uat, line.contrated_hours - line.uat_support_hours,
                    precision_digits=2,
                ) > 0
            ):
                raise UserError(_("La carga supera el presupuesto propio de la Mejora o invade su reserva UAT."))

    @api.model
    def _lock_tasks(self, tasks):
        lines = tasks.sudo().mapped("uat_sale_line_id") | tasks.sudo().mapped("sale_line_id").filtered(
            lambda line: line._uat_dedicated_tasks()
        )
        lines._uat_lock_budget()
        return super()._lock_tasks(tasks)

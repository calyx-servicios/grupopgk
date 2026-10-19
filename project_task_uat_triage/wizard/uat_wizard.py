from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from ..models.project_task import UAT_OPERATION, UAT_RESULTS


class ProjectTaskUatWizard(models.TransientModel):
    _name = "project.task.uat.wizard"
    _description = "Validación de UAT Cliente no exitosa"

    task_id = fields.Many2one("project.task", required=True, readonly=True)
    result = fields.Selection(UAT_RESULTS, string="Resultado")
    description = fields.Text(string="Descripción / aclaración", required=True)
    attachment_ids = fields.Many2many("ir.attachment", string="Adjuntos")
    task_version = fields.Integer(readonly=True)
    event_id = fields.Many2one("project.task.event", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if {"task_version", "event_id"}.intersection(vals):
                raise AccessError(_("El estado del asistente lo determina el servidor."))
            vals.setdefault("task_id", self.env.context.get("default_task_id"))
            task = self.env["project.task"].browse(vals.get("task_id"))
            task.check_access_rights("read")
            task.check_access_rule("read")
            vals["task_version"] = task.uat_version
        return super().create(vals_list)

    def write(self, vals):
        if {"task_id", "task_version", "event_id"}.intersection(vals):
            if self.env.context.get("_uat_operation") is not UAT_OPERATION:
                raise AccessError(_("No puede cambiar la tarea o el estado del asistente."))
        return super().write(vals)

    def action_confirm(self):
        self.ensure_one()
        self.check_access_rule("write")
        self.flush()
        self.env.cr.execute(
            "UPDATE project_task_uat_wizard SET write_date = clock_timestamp() "
            "WHERE id = %s", [self.id],
        )
        self.invalidate_cache()
        task = self.task_id
        task._uat_lock()
        if self.event_id:
            raise UserError(_("Este triage ya fue registrado."))
        if not task.can_validate_uat or task.uat_version != self.task_version:
            raise UserError(_("La tarea ya no está disponible para este triage. Abra un nuevo asistente."))
        if not self.result or not (self.description or "").strip():
            raise UserError(_("Seleccione Bug, Mejora o Malentendido y complete la descripción."))
        self.attachment_ids.check_access_rights("read")
        self.attachment_ids.check_access_rule("read")
        self.attachment_ids.write({"res_model": "project.task", "res_id": task.id})
        improvement = self.env["project.task"]
        if self.result == "improvement":
            improvement = self.env["project.task"].with_context(
                _uat_operation=UAT_OPERATION,
            ).create({
                "name": _("Mejora UAT: %s") % task.name,
                "description": Markup("<p>%s</p>") % self.description.strip(),
                "project_id": task.project_id.id,
                "company_id": task.company_id.id,
                "partner_id": task.partner_id.id,
                "task_type": "development",
                "stage_id": task._workflow_stage("stage_estimacion").id,
                "parent_id": False, "sale_line_id": False,
                "uat_origin_id": task.id,
            })
        destination = (
            task._workflow_stage("stage_desarrollo")
            if self.result == "bug" else task.stage_id
        )
        event = self.env["project.task.event"].with_context(
            _uat_operation=UAT_OPERATION,
        ).create({
            "task_id": task.id, "event_type": "uat", "uat_result": self.result,
            "description": self.description.strip(),
            "attachment_ids": [(6, 0, self.attachment_ids.ids)],
            "origin_stage_id": task.stage_id.id,
            "destination_stage_id": destination.id,
            "uat_improvement_id": improvement.id,
        })
        vals = {"uat_version": task.uat_version + 1}
        if self.result == "bug":
            vals.update(stage_id=destination.id, uat_bug_event_id=event.id)
        task.with_context(_uat_operation=UAT_OPERATION).write(vals)
        body = Markup("<p><b>UAT Cliente: %s</b></p><p>%s</p>") % (
            dict(UAT_RESULTS)[self.result], self.description.strip(),
        )
        if improvement:
            body += Markup('<p><a href="#" data-oe-model="project.task" data-oe-id="%s">%s</a></p>') % (
                improvement.id, improvement.display_name,
            )
            improvement.message_post(
                body=Markup("<p>%s</p>") % (_("Derivada de UAT: %s") % task.display_name),
                subtype_xmlid="mail.mt_note",
            )
        task.message_post(
            body=body, attachment_ids=self.attachment_ids.ids,
            subtype_xmlid="mail.mt_note",
        )
        self.with_context(_uat_operation=UAT_OPERATION).write({"event_id": event.id})
        return {"type": "ir.actions.act_window_close"}


class ProjectTaskUatQuotationWizard(models.TransientModel):
    _name = "project.task.uat.quotation.wizard"
    _description = "Cotización dedicada de Mejora UAT"

    task_id = fields.Many2one("project.task", required=True, readonly=True)
    product_id = fields.Many2one(
        "product.product", string="Servicio", required=True,
        domain="[('type', '=', 'service'), ('service_tracking', 'in', ['project_only', 'task_in_project'])]",
    )
    price_unit = fields.Float(string="Precio", required=True)
    user_id = fields.Many2one(
        "res.users", string="Responsable comercial", required=True,
        default=lambda self: self.env.user, domain=[("share", "=", False)],
    )

    @api.onchange("product_id")
    def _onchange_product(self):
        self.price_unit = self.product_id.lst_price

    def action_confirm(self):
        self.ensure_one()
        task = self.task_id
        task._uat_lock()
        if not task.can_create_uat_quotation:
            raise AccessError(_("Solo Ventas puede cotizar una Mejora sin línea comercial."))
        total = sum(task._uat_estimate().values())
        if total <= 0:
            raise UserError(_("Complete la estimación antes de cotizar la Mejora."))
        if (
            self.product_id.type != "service"
            or self.product_id.service_tracking not in ("project_only", "task_in_project")
            or self.user_id.share or self.price_unit < 0
        ):
            raise UserError(_("Seleccione un servicio válido, precio no negativo y comercial interno."))
        hour_uom = self.env.ref("uom.product_uom_hour")
        if self.product_id.uom_id.category_id != hour_uom.category_id:
            raise UserError(_("El servicio cotizado debe usar una unidad de medida de tiempo."))
        project = task.project_id
        order_vals = {
            "partner_id": task.partner_id.id, "company_id": task.company_id.id,
            "user_id": self.user_id.id,
            "calyx_project_manager_id": project._get_workflow_pm().id,
            "client_order_ref": task.display_name,
        }
        if "date_of_issue" in self.env["sale.order"]._fields:
            order_vals["date_of_issue"] = fields.Datetime.now()
        if "partner" in self.env["sale.order"]._fields:
            order_vals["partner"] = project._get_workflow_pm().id
        order = self.env["sale.order"].with_company(task.company_id).create(order_vals)
        line = self.env["sale.order.line"].with_company(task.company_id).with_context(
            _uat_operation=UAT_OPERATION,
        ).create({
            "order_id": order.id, "product_id": self.product_id.id,
            "product_uom_qty": hour_uom._compute_quantity(total, self.product_id.uom_id),
            "product_uom": self.product_id.uom_id.id,
            "price_unit": self.price_unit, "name": task.display_name,
            "project_id": project.id, "project_name": project.name,
            "analytic_account_id": (
                project.analytic_account_id.parent_id or project.analytic_account_id
            ).id,
            "contrated_hours": total,
            "uat_support_hours": task.estimated_uat_support_hours,
            "uat_quotation_task_id": task.id,
        })
        task.write({"uat_sale_line_id": line.id})
        return {
            "type": "ir.actions.act_window", "res_model": "sale.order",
            "res_id": order.id, "view_mode": "form",
        }


class ProjectTaskUatClientWizard(models.TransientModel):
    _name = "project.task.uat.client.wizard"
    _description = "Registrar aprobación de Mejora por el cliente"

    task_id = fields.Many2one("project.task", required=True, readonly=True)
    description = fields.Text(string="Detalle de aprobación", required=True)
    attachment_ids = fields.Many2many("ir.attachment", string="Evidencia", required=True)
    proposal_key = fields.Char(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "proposal_key" in vals:
                raise AccessError(_("La revisión la determina el servidor."))
            task = self.env["project.task"].browse(vals.get("task_id"))
            task.check_access_rule("read")
            vals["proposal_key"] = task._uat_proposal_key()
        return super().create(vals_list)

    def write(self, vals):
        if {"task_id", "proposal_key"}.intersection(vals):
            raise AccessError(_("No puede cambiar la propuesta del asistente."))
        return super().write(vals)

    def action_confirm(self):
        self.ensure_one()
        task = self.task_id
        task._uat_lock()
        if not task._uat_is_functional():
            raise AccessError(_("Solo el Funcional registra la aprobación del cliente."))
        if task._uat_proposal_key() != self.proposal_key:
            raise UserError(_("La propuesta cambió. Abra un nuevo asistente de aprobación."))
        if not (self.description or "").strip() or not self.attachment_ids:
            raise UserError(_("Complete el detalle y adjunte la evidencia de aprobación."))
        task._uat_record_approval("client", self.attachment_ids, self.description.strip())
        return {"type": "ir.actions.act_window_close"}

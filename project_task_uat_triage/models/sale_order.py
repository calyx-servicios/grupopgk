from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .project_task import UAT_OPERATION


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    uat_improvement_ids = fields.One2many("project.task", "uat_sale_line_id")
    uat_quotation_task_id = fields.Many2one(
        "project.task", string="Cotización de Mejora UAT", readonly=True,
        copy=False, ondelete="restrict",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if any("uat_quotation_task_id" in vals for vals in vals_list):
            if self.env.context.get("_uat_operation") is not UAT_OPERATION:
                raise AccessError(_("Use «Cotizar Mejora» para generar su línea dedicada."))
        return super().create(vals_list)

    def _should_sync_project_amount(self):
        self.ensure_one()
        return (
            not self.uat_quotation_task_id
            and not self.with_context(active_test=False).uat_improvement_ids
            and super()._should_sync_project_amount()
        )

    def _uat_dedicated_tasks(self):
        lines = self.with_context(active_test=False)
        return lines.mapped("uat_improvement_ids") | lines.mapped("uat_quotation_task_id")

    def _uat_bind_quote(self, task):
        self.ensure_one()
        if self.order_id.state == "cancel":
            raise UserError(_("No puede vincular una cotización cancelada."))
        if self.uat_quotation_task_id and self.uat_quotation_task_id != task:
            raise UserError(_("La línea está reservada para otra Mejora."))
        if not self.uat_quotation_task_id:
            super().write({"uat_quotation_task_id": task.id})

    def _uat_lock_budget(self):
        if self:
            self.flush()
            self.env.cr.execute(
                "UPDATE sale_order_line SET write_date = clock_timestamp() WHERE id IN %s",
                [tuple(sorted(self.ids))],
            )

    def write(self, vals):
        if "uat_quotation_task_id" in vals:
            raise AccessError(_("El origen de la cotización UAT no se puede alterar."))
        improvements = self.with_context(active_test=False).mapped("uat_improvement_ids")
        protected = {
            "product_id", "contrated_hours", "uat_support_hours",
            "product_uom_qty", "product_uom", "price_unit", "discount", "tax_id",
            "project_id", "order_id",
        }
        changed = protected.intersection(vals) - (
            {"project_id"} if "project_id" in vals and all(
                line.project_id.id == vals["project_id"] for line in self
            ) else set()
        )
        if changed and improvements:
            improvements._uat_lock()
        result = super().write(vals)
        if changed and improvements:
            improvements._uat_invalidate_proposal()
            improvements.timesheet_ids._uat_validate_budgets()
        return result

    def unlink(self):
        if self._uat_dedicated_tasks():
            raise UserError(_("No puede eliminar una línea vinculada a una Mejora UAT."))
        return super().unlink()


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        improvements = self.order_line.with_context(active_test=False).mapped("uat_improvement_ids")
        for task in improvements:
            task._uat_lock()
            task._uat_check_proposal()
            key = task._uat_proposal_key()
            types = set(task.uat_approval_ids.filtered(
                lambda approval: approval.proposal_key == key
            ).mapped("approval_type"))
            if not {"client", "commercial"}.issubset(types):
                raise UserError(_("La cotización de Mejora requiere aprobación del cliente y de Comercial."))
        return super().action_confirm()

    def write(self, vals):
        improvements = self.order_line.with_context(active_test=False).mapped("uat_improvement_ids")
        changes = {"user_id", "partner_id", "company_id", "currency_id", "fiscal_position_id"}
        if changes.intersection(vals) or vals.get("state") == "cancel":
            improvements._uat_lock()
        result = super().write(vals)
        if changes.intersection(vals) or vals.get("state") == "cancel":
            improvements._uat_invalidate_proposal()
        return result

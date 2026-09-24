from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare


class SaleOrder(models.Model):
    """Genera proyectos Calyx desde órdenes de venta directas."""

    _inherit = "sale.order"

    calyx_project_manager_id = fields.Many2one(
        comodel_name="res.users",
        string="PM del proyecto",
        copy=False,
        domain=[("share", "=", False), ("active", "=", True)],
    )
    calyx_sale_project_from_order_enabled = fields.Boolean(
        related="company_id.calyx_sale_project_from_order_enabled",
        readonly=True,
    )
    calyx_is_quotation = fields.Boolean(
        compute="_compute_calyx_is_quotation",
    )

    def _compute_calyx_is_quotation(self):
        """Indica si la orden pertenece al Cotizador, sin depender de ese módulo."""
        has_field = "is_quotation" in self._fields
        for order in self:
            order.calyx_is_quotation = bool(has_field and order.is_quotation)

    def action_confirm(self):
        """Valida y sincroniza proyectos Calyx al confirmar la OV."""
        managed_orders = self.filtered(
            lambda order: order._calyx_uses_sale_project_flow()
        )
        managed_orders._calyx_validate_sale_project_flow()
        result = super().action_confirm()
        managed_orders._calyx_sync_sale_projects()
        return result

    def _calyx_uses_sale_project_flow(self):
        """Indica si la orden debe usar el flujo Calyx desde ventas."""
        self.ensure_one()
        return bool(
            self.company_id.calyx_sale_project_from_order_enabled
            and not self.calyx_is_quotation
        )

    def _calyx_managed_sale_lines(self):
        """Devuelve las líneas de servicio que deben generar proyecto."""
        self.ensure_one()
        return self.order_line.filtered(
            lambda line: line._calyx_uses_sale_project_flow()
        )

    def _calyx_validate_sale_project_flow(self):
        """Valida datos obligatorios antes de confirmar la OV Calyx."""
        for order in self:
            lines = order._calyx_managed_sale_lines()
            if not lines:
                continue
            if not order.calyx_project_manager_id:
                raise ValidationError(
                    _("Indique el PM del proyecto antes de confirmar la orden.")
                )
            for line in lines:
                line._calyx_validate_sale_project_line()

    def _calyx_sync_sale_projects(self):
        """Crea un proyecto por OV y una tarea raíz por cada línea gestionada."""
        for order in self:
            project = order._calyx_get_or_create_sale_project()
            for line in order._calyx_managed_sale_lines():
                line._calyx_create_root_task(project)

    def _calyx_project_name(self):
        """Construye el nombre del proyecto único de la OV Calyx."""
        self.ensure_one()
        first_line = self._calyx_managed_sale_lines()[:1]
        if first_line:
            return first_line._get_sequence_name()
        sequence = self.env.ref("project_for_each_sol.seq_project")
        return "%s-%s-%s | %s - %s" % (
            fields.Datetime.now().year,
            self.partner_id.id,
            sequence.get_next_char(sequence.number_next),
            self.name,
            self.partner_id.name,
        )

    def _calyx_get_or_create_sale_project(self):
        """Devuelve el proyecto único de la OV o lo crea si no existe."""
        self.ensure_one()
        existing_project = self._calyx_managed_sale_lines().mapped("project_id")[:1]
        if existing_project:
            return existing_project
        first_line = self._calyx_managed_sale_lines()[:1]
        first_line._calyx_validate_sale_project_line()
        project_name = self._calyx_project_name()
        account = self.env["account.analytic.account"].sudo().create(
            first_line._calyx_prepare_analytic_values(project_name)
        )
        project = self.env["project.project"].sudo().with_context(
            calyx_sale_project_generation=True
        ).create(self._calyx_prepare_project_values(account, project_name, first_line))
        first_line.sudo()._set_next_number()
        return project

    def _calyx_prepare_project_values(self, account, project_name, sale_line):
        """Prepara valores del proyecto único generado desde la OV."""
        self.ensure_one()
        values = {
            "name": project_name,
            "analytic_account_id": account.id,
            "partner_id": self.partner_id.id,
            "sale_line_id": sale_line.id,
            "active": True,
            "company_id": self.company_id.id,
            "allow_billable": True,
            "user_id": self.calyx_project_manager_id.id,
            "calyx_project_manager_id": self.calyx_project_manager_id.id,
        }
        if "project_manager" in self.env["project.project"]._fields:
            values["project_manager"] = self.calyx_project_manager_id.name
        if "partner" in self.env["project.project"]._fields and self.partner:
            values["partner"] = self.partner.id
        return values


class SaleOrderLine(models.Model):
    """Controla la generación Calyx por línea de venta."""

    _inherit = "sale.order.line"

    def _calyx_uses_sale_project_flow(self):
        """Indica si la línea pertenece al flujo Calyx directo desde ventas."""
        self.ensure_one()
        return bool(
            self.order_id.company_id.calyx_sale_project_from_order_enabled
            and not self.order_id.calyx_is_quotation
            and self.is_service
            and self.product_id.service_tracking in ("project_only", "task_in_project")
        )

    def _calyx_validate_sale_project_line(self):
        """Valida una línea antes de crear proyecto y raíz contractual."""
        self.ensure_one()
        if self.project_id:
            return
        if not self.project_name:
            raise ValidationError(
                _("Indique el nombre del proyecto en la línea %s.") % self.name
            )
        if not self.analytic_account_id:
            raise ValidationError(
                _("Indique la cuenta analítica en la línea %s.") % self.name
            )
        if float_compare(self.contrated_hours, 0.0, precision_digits=2) <= 0:
            raise ValidationError(
                _("Las horas contratadas de la línea %s deben ser mayores que cero.")
                % self.name
            )

    def _calyx_prepare_analytic_values(self, project_name):
        """Prepara la cuenta analítica hija del proyecto Calyx."""
        self.ensure_one()
        account_model = self.env["account.analytic.account"]
        company_field = account_model._fields["company_id"]
        company_value = self.order_id.company_id.id
        if company_field.type == "many2many":
            company_value = [(6, 0, self.order_id.company_id.ids)]
        return {
            "name": project_name,
            "code": self.order_id.client_order_ref,
            "company_id": company_value,
            "partner_id": self.order_id.partner_id.id,
            "parent_id": self.analytic_account_id.id,
            "group_id": self.analytic_account_id.group_id.id,
        }

    def _calyx_prepare_root_task_values(self, project):
        """Prepara la tarea raíz protegida de la línea."""
        self.ensure_one()
        title = (self.name or self.product_id.display_name).split("\n")[0]
        return {
            "name": title,
            "description": _(
                "Bolsa contractual de horas generada desde la línea de venta."
            ),
            "planned_hours": self.contrated_hours,
            "calyx_budget_hours": self.contrated_hours,
            "partner_id": self.order_id.partner_id.id,
            "email_from": self.order_id.partner_id.email,
            "project_id": project.id,
            "sale_line_id": self.id,
            "sale_order_id": self.order_id.id,
            "company_id": project.company_id.id,
            "analytic_account_id": project.analytic_account_id.id,
            "is_calyx_sale_root": True,
            "user_ids": [(6, 0, [self.order_id.calyx_project_manager_id.id])],
        }

    def _calyx_create_root_task(self, project):
        """Crea la tarea raíz de la línea dentro del proyecto de la OV."""
        self.ensure_one()
        if not self._calyx_uses_sale_project_flow() or self.task_id:
            return self.task_id
        self._calyx_validate_sale_project_line()
        root_task = self.env["project.task"].sudo().with_context(
            calyx_sale_project_generation=True
        ).create(self._calyx_prepare_root_task_values(project))
        self.with_context(calyx_sale_project_sync=True).write(
            {
                "project_id": project.id,
                "task_id": root_task.id,
            }
        )
        return root_task

    @api.model_create_multi
    def create(self, vals_list):
        """Crea la tarea de la línea al agregarla a una OV ya confirmada."""
        lines = super().create(vals_list)
        for line in lines:
            if line.state == "sale" and line._calyx_uses_sale_project_flow():
                project = line.order_id._calyx_get_or_create_sale_project()
                line._calyx_create_root_task(project)
        return lines

    def write(self, values):
        """Protege horas/base contractual después de confirmar la orden."""
        protected = {"contrated_hours", "analytic_account_id", "product_id"}
        frozen = self.filtered(
            lambda line: line._calyx_uses_sale_project_flow()
            and line.order_id.state in ("sale", "done")
        )
        if (
            frozen
            and protected.intersection(values)
            and not self.env.context.get("calyx_sale_project_sync")
        ):
            raise ValidationError(
                _(
                    "No puede cambiar producto, cuenta analítica u horas contratadas "
                    "después de confirmar la orden Calyx."
                )
            )
        return super().write(values)

    def unlink(self):
        """Impide borrar líneas contractuales Calyx confirmadas."""
        frozen = self.filtered(
            lambda line: line._calyx_uses_sale_project_flow()
            and line.order_id.state in ("sale", "done")
        )
        if frozen:
            raise ValidationError(_("Las líneas Calyx confirmadas no pueden eliminarse."))
        return super().unlink()

    def _create_project_for_each(self, line):
        """Evita que project_for_each_sol duplique proyectos Calyx."""
        if line._calyx_uses_sale_project_flow():
            return False
        return super()._create_project_for_each(line)

    def _set_next_number(self):
        """Evita consumir secuencia en el flujo anterior para líneas Calyx."""
        unmanaged = self.filtered(
            lambda line: not line._calyx_uses_sale_project_flow()
        )
        if unmanaged:
            return super(SaleOrderLine, unmanaged)._set_next_number()
        return None

    def _timesheet_service_generation(self):
        """Evita que sale_project genere proyectos duplicados para Calyx."""
        unmanaged = self.filtered(
            lambda line: not line._calyx_uses_sale_project_flow()
        )
        if unmanaged:
            return super(SaleOrderLine, unmanaged)._timesheet_service_generation()
        return None

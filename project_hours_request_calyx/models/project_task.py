from typing import Any, Dict, List

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare


class ProjectTask(models.Model):
    """Distribute and enforce a commercial UAT reservation per Calyx root."""

    _inherit = "project.task"

    calyx_uat_budget_hours = fields.Float(
        string="UAT/Soporte contractual", copy=False,
    )
    calyx_uat_quote_snapshot = fields.Boolean(
        string="Previsión UAT desde cotización", readonly=True, copy=False,
    )
    calyx_uat_state = fields.Selection(
        [("preparation", "En preparación"), ("active", "Activa")],
        string="Reserva UAT/Soporte", default="preparation",
        readonly=True, copy=False,
    )
    calyx_uat_allocated_hours = fields.Float(
        string="UAT/Soporte asignadas", compute="_compute_calyx_uat_hours",
        recursive=True,
    )
    calyx_uat_unallocated_hours = fields.Float(
        string="UAT/Soporte sin asignar", compute="_compute_calyx_uat_hours",
    )
    can_manage_calyx_uat = fields.Boolean(
        compute="_compute_can_manage_calyx_uat",
    )

    @api.depends_context("uid")
    def _compute_can_manage_calyx_uat(self) -> None:
        """Expose preparation and activation only to the project PM."""
        for task in self:
            task.can_manage_calyx_uat = (
                self.env.su
                or self._get_project_pm(task.project_id) == self.env.user
            )

    def _get_calyx_uat_root(self) -> Any:
        """Resolve a line's contractual root, including archived parents."""
        self.ensure_one()
        task = self.sudo().with_context(active_test=False)
        while task and not task.is_calyx_sale_root:
            task = task.parent_id
        return task

    def _get_calyx_uat_roots(self) -> Any:
        """Collect independent commercial roots for a task recordset."""
        roots = self.env["project.task"].sudo()
        for task in self:
            roots |= task._get_calyx_uat_root()
        return roots

    def _get_calyx_uat_tree(self) -> Any:
        """Include archived allocations and every descendant exactly once."""
        self.ensure_one()
        return self.env["project.task"].sudo().with_context(
            active_test=False,
        ).search([("id", "child_of", self.id)])

    @api.depends(
        "calyx_uat_budget_hours", "estimated_uat_support_hours",
        "child_ids", "child_ids.estimated_uat_support_hours",
        "child_ids.calyx_uat_allocated_hours",
    )
    def _compute_calyx_uat_hours(self) -> None:
        """Show allocation separately from each task's own UAT cupo."""
        for root in self:
            allocated = sum(
                root._get_calyx_uat_tree().mapped(
                    "estimated_uat_support_hours"
                )
            )
            root.calyx_uat_allocated_hours = allocated
            root.calyx_uat_unallocated_hours = (
                root.calyx_uat_budget_hours - allocated
            )

    def _get_calyx_non_uat_consumed(self) -> float:
        """Keep historical unclassified hours in the non-UAT consumption."""
        self.ensure_one()
        lines = self.env["account.analytic.line"].sudo().search([
            ("task_id", "child_of", self.id),
            "|", ("timesheet_segment", "=", False),
            ("timesheet_segment", "!=", "uat_support"),
        ])
        return sum(lines.mapped("unit_amount"))

    def _get_calyx_uat_total_cap(self) -> float:
        """Use the live global cap, falling back to the contract snapshot."""
        self.ensure_one()
        if self.hours_cap or (
            "config_level" in self._fields and self.config_level
        ):
            return self.hours_cap
        return self.calyx_budget_hours

    def _validate_calyx_uat_reservation(
        self, activating: bool = False,
    ) -> None:
        """Prevent allocation or normal work from borrowing reserved UAT."""
        for root in self.sudo():
            if not root.is_calyx_sale_root:
                continue
            reserve = root.calyx_uat_budget_hours
            if reserve < 0 or float_compare(
                reserve, root.calyx_budget_hours, precision_digits=2,
            ) > 0:
                raise ValidationError(_(
                    "La reserva UAT debe estar dentro del total contratado."
                ))
            tree = root._get_calyx_uat_tree()
            if tree.filtered(
                lambda task: task.project_id != root.project_id
                or task.company_id != root.company_id
            ):
                raise ValidationError(_(
                    "El árbol contractual debe pertenecer al mismo "
                    "proyecto y compañía."
                ))
            allocations = tree.filtered("estimated_uat_support_hours")
            for task in allocations:
                if (
                    task == root or task.task_type != "development"
                    or task.project_id != root.project_id
                    or task.company_id != root.company_id
                    or ("config_level" in task._fields
                        and task.config_level in (1, 2, 3))
                ):
                    raise ValidationError(_(
                        "Los cupos UAT solo se asignan a tareas Desarrollo "
                        "cobrables del mismo proyecto y compañía."
                    ))
            allocated = sum(allocations.mapped("estimated_uat_support_hours"))
            if float_compare(allocated, reserve, precision_digits=2) > 0:
                raise ValidationError(_(
                    "Los cupos UAT asignados (%s hs) superan la reserva "
                    "contractual (%s hs)."
                ) % (allocated, reserve))
            if root.calyx_uat_state != "active" and not activating:
                continue
            if (
                not root.sale_line_id
                or root.sale_line_id.task_id != root
                or root.sale_line_id.project_id != root.project_id
            ):
                raise ValidationError(_(
                    "La reserva UAT requiere su línea contractual Calyx."
                ))
            tree._validate_uat_hours()
            available = root._get_calyx_uat_total_cap() - reserve
            consumed = root._get_calyx_non_uat_consumed()
            if available < 0 or float_compare(
                consumed, available, precision_digits=2,
            ) > 0:
                raise UserError(_(
                    "El consumo no UAT (%s hs) invade la reserva UAT. "
                    "Su tope disponible es %s hs."
                ) % (consumed, available))
            if float_compare(
                root._get_total_consumed_hours(),
                root._get_calyx_uat_total_cap(), precision_digits=2,
            ) > 0:
                raise UserError(_("La carga supera el total contractual."))
            root._validate_calyx_uat_branches(tree)

    def _validate_calyx_uat_branches(self, tree: Any) -> None:
        """Exclude branch reservations from Configuraciones shared excess."""
        if "config_level" not in self._fields or not self.config_level:
            return
        capacities = []
        overages = []
        for branch in tree.filtered(lambda task: task.config_level == 3):
            reserve = sum(branch._get_calyx_uat_tree().mapped(
                "estimated_uat_support_hours"
            ))
            available = branch.hours_cap - reserve
            if float_compare(available, 0.0, precision_digits=2) < 0:
                raise ValidationError(_(
                    "Los cupos UAT de una actividad superan su tope."
                ))
            capacities.append(available)
            overages.append(max(
                branch._get_calyx_non_uat_consumed() - available, 0.0,
            ))
        shared = max(
            self._get_calyx_uat_total_cap() - self.calyx_uat_budget_hours
            - sum(capacities), 0.0,
        )
        if float_compare(sum(overages), shared, precision_digits=2) > 0:
            raise UserError(_(
                "El exceso compartido no puede utilizar la reserva UAT."
            ))

    def action_activate_calyx_uat(self) -> bool:
        """Atomically validate preparation and enable the strict reserve."""
        self.ensure_one()
        if not self.is_calyx_sale_root or (
            not self.env.su
            and self._get_project_pm(self.project_id) != self.env.user
        ):
            raise AccessError(_("Solo el PM puede activar la reserva UAT."))
        self.env["account.analytic.line"]._lock_tasks(self)
        self._validate_calyx_uat_reservation(activating=True)
        super().write({"calyx_uat_state": "active"})
        self.message_post(body=_("Reserva UAT/Soporte activada por el PM."))
        return True

    @api.model_create_multi
    def create(self, vals_list: List[Dict[str, Any]]) -> Any:
        """Serialize allocation before adding tasks to a commercial tree."""
        if any(vals.get("calyx_uat_state", "preparation") != "preparation"
               for vals in vals_list):
            raise AccessError(_("La reserva UAT requiere activación del PM."))
        if any(vals.get("calyx_uat_quote_snapshot") for vals in vals_list):
            if not (
                self.env.su
                and self.env.context.get("calyx_sale_project_generation")
            ):
                raise AccessError(_(
                    "La previsión cotizada solo se copia al generar la raíz."
                ))
        parents = self.browse([
            vals["parent_id"] for vals in vals_list if vals.get("parent_id")
        ])
        self.env["account.analytic.line"]._lock_tasks(parents)
        tasks = super().create(vals_list)
        tasks._get_calyx_uat_roots()._validate_calyx_uat_reservation()
        tasks._validate_uat_hours()
        return tasks

    def write(self, values: Dict[str, Any]) -> Any:
        """Validate both roots when allocations or task structure change."""
        if {
            "calyx_uat_state", "calyx_uat_quote_snapshot",
        }.intersection(values):
            raise AccessError(_("Use la acción de activación de reserva UAT."))
        if "calyx_uat_budget_hours" in values:
            for root in self:
                if (
                    not root.is_calyx_sale_root
                    or root.calyx_uat_state == "active"
                    or root.calyx_uat_quote_snapshot
                    or (not self.env.su and self._get_project_pm(
                        root.project_id
                    ) != self.env.user)
                ):
                    raise AccessError(_(
                        "Solo el PM puede preparar UAT de raíces existentes "
                        "sin previsión cotizada. La reserva cotizada o activa "
                        "no puede modificarse."
                    ))
        relevant = {
            "estimated_uat_support_hours", "calyx_uat_budget_hours",
            "parent_id", "project_id", "task_type", "active", "hours_cap",
            "company_id", "is_calyx_sale_root", "sale_line_id",
        }
        if not relevant.intersection(values):
            return super().write(values)
        roots = self._get_calyx_uat_roots()
        target = self.browse(values.get("parent_id"))
        self.env["account.analytic.line"]._lock_tasks(self | target)
        if {"parent_id", "project_id", "company_id"}.intersection(values):
            for task in self:
                origin = task._get_calyx_uat_root()
                destination = (
                    target._get_calyx_uat_roots()
                    if "parent_id" in values else origin
                )
                changes_project = (
                    values.get("project_id", task.project_id.id)
                    != task.project_id.id
                    or values.get("company_id", task.company_id.id)
                    != task.company_id.id
                )
                if origin and (origin != destination or changes_project) and (
                    task._get_total_consumed_hours()
                ):
                    raise UserError(_(
                        "No puede trasladar fuera de su imputación "
                        "contractual una tarea con horas cargadas."
                    ))
        result = super().write(values)
        roots |= self._get_calyx_uat_roots()
        roots._validate_calyx_uat_reservation()
        if "calyx_uat_budget_hours" in values:
            for root in self:
                root.message_post(body=_(
                    "Previsión contractual UAT preparada: %s hs."
                ) % root.calyx_uat_budget_hours)
            roots.invalidate_cache([
                "calyx_uat_allocated_hours", "calyx_uat_unallocated_hours",
            ])
        return result

    def unlink(self) -> bool:
        """Do not delete consumption to silently release a UAT reserve."""
        roots = self._get_calyx_uat_roots()
        self.env["account.analytic.line"]._lock_tasks(self)
        if roots and any(task._get_total_consumed_hours() for task in self):
            raise UserError(_(
                "No puede eliminar una tarea con horas cargadas."
            ))
        result = super().unlink()
        roots.exists()._validate_calyx_uat_reservation()
        return result
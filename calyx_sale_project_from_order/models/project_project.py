from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProjectProject(models.Model):
    """Protege la creación manual de proyectos en compañías Calyx activas."""

    _inherit = "project.project"

    calyx_project_manager_id = fields.Many2one(
        comodel_name="res.users",
        string="PM del proyecto",
        copy=False,
        domain=[("share", "=", False), ("active", "=", True)],
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Permite crear proyectos Calyx solo desde el flujo técnico de venta."""
        for values in vals_list:
            company = self.env["res.company"].browse(
                values.get("company_id") or self.env.company.id
            )
            if not company.calyx_sale_project_from_order_enabled:
                continue
            allowed = bool(
                self.env.su
                and self.env.context.get("calyx_sale_project_generation")
            ) or self.env.user.has_group(
                "calyx_sale_project_from_order.group_contracts_project_creation_allowed"
            )
            if not allowed:
                raise ValidationError(
                    "Los proyectos de Calyx deben originarse desde una orden "
                    "de venta confirmada o ser creados por un usuario de "
                    "Contratos autorizado."
                )
            manager_id = values.get("calyx_project_manager_id")
            if manager_id:
                values.setdefault("user_id", manager_id)
                if "project_manager" in self._fields:
                    manager = self.env["res.users"].browse(manager_id)
                    values.setdefault("project_manager", manager.name)
        return super().create(vals_list)

    def write(self, values):
        """Mantiene sincronizado el PM Calyx con los campos de proyecto existentes."""
        if "calyx_project_manager_id" in values:
            manager = self.env["res.users"].browse(
                values.get("calyx_project_manager_id")
            )
            values = dict(values)
            values["user_id"] = manager.id if manager else False
            if "project_manager" in self._fields:
                values["project_manager"] = manager.name if manager else False
        return super().write(values)


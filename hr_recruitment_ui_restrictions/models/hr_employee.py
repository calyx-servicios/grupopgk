# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo import _, api, models
from odoo.exceptions import AccessError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def _is_restricted_department_user(self):
        return self.env.user._is_in_restricted_hr_department()

    @api.model
    def fields_view_get(self, view_id=None, view_type="form", toolbar=False, submenu=False):
        result = super().fields_view_get(
            view_id=view_id,
            view_type=view_type,
            toolbar=toolbar,
            submenu=submenu,
        )
        if not self._is_restricted_department_user() or view_type not in {
            "tree",
            "form",
            "kanban",
        }:
            return result
        arch = result.get("arch")
        if not arch:
            return result
        root = etree.fromstring(arch)
        if root.tag in {"tree", "form", "kanban"}:
            root.set("create", "0")
            if root.tag == "kanban":
                root.set("quick_create", "0")
            result["arch"] = etree.tostring(root, encoding="unicode")
        return result

    @api.model_create_multi
    def create(self, vals_list):
        if self._is_restricted_department_user():
            raise AccessError(
                _(
                    "No tiene permisos para crear empleados desde este perfil."
                )
            )
        return super().create(vals_list)


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    def _is_restricted_department_user(self):
        return self.env.user._is_in_restricted_hr_department()

    @api.model
    def fields_view_get(self, view_id=None, view_type="form", toolbar=False, submenu=False):
        result = super().fields_view_get(
            view_id=view_id,
            view_type=view_type,
            toolbar=toolbar,
            submenu=submenu,
        )
        if not self._is_restricted_department_user() or view_type not in {
            "tree",
            "form",
            "kanban",
        }:
            return result
        arch = result.get("arch")
        if not arch:
            return result
        root = etree.fromstring(arch)
        if root.tag in {"tree", "form", "kanban"}:
            root.set("create", "0")
            if root.tag == "kanban":
                root.set("quick_create", "0")
            result["arch"] = etree.tostring(root, encoding="unicode")
        return result

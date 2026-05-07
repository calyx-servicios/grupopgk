# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    def _load_menus_blacklist(self):
        res = super()._load_menus_blacklist()
        if not self.env.user._is_in_restricted_hr_department():
            return res
        for xmlid in (
            "hr.menu_hr_department_kanban",
            "hr.menu_human_resources_configuration",
        ):
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if menu:
                res.append(menu.id)
        return res

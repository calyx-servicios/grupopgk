from odoo import api, models, tools

RESTRICTED_GROUP_XMLID = (
    "project_restricted_task_access.group_project_task_restricted"
)
ALLOWED_MENU_XMLID = "project_restricted_task_access.menu_restricted_my_tasks"


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    # No type hints here: ormcache rebuilds the signature from source text.
    @api.model
    @tools.ormcache("frozenset(self.env.user.groups_id.ids)", "debug")
    def _visible_menu_ids(self, debug=False):
        """Hide every Project submenu except the restricted task shortcut.

        Menu groups can't exclude a group, so filtering is done here.
        """
        visible_ids = super()._visible_menu_ids(debug)
        if not self.env.user.has_group(RESTRICTED_GROUP_XMLID):
            return visible_ids
        root = self.env.ref("project.menu_main_pm", raise_if_not_found=False)
        if not root:
            return visible_ids
        allowed = self.env.ref(ALLOWED_MENU_XMLID, raise_if_not_found=False)
        project_menus = (
            self.sudo()
            .with_context(
                **{"ir.ui.menu.full_list": True, "active_test": False}
            )
            .search([("id", "child_of", root.id)])
        )
        hidden_ids = set(project_menus.ids) - {root.id}
        if allowed:
            hidden_ids.discard(allowed.id)
        # The parent's result is cached, so never mutate it in place.
        return visible_ids - hidden_ids

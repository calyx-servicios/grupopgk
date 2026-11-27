import json

from lxml import etree

from odoo import api, models

from .ir_ui_menu import RESTRICTED_GROUP_XMLID

# Hours, amount, billing, deviation, cost and margin fields of the project.
SENSITIVE_FIELDS = (
    "contrated_hours",
    "total_project_amount",
    "project_currency_id",
    "teorical_billing",
    "real_billing",
    "billing_multyply_advance",
    "billing_deviation",
    "remaining_hours",
    "left_hours",
    "billing_hours",
    "hours_multiply_advance",
    "advance_deviation",
    "advance_deviation_pgk",
    "advance_billing",
    "cost",
    "overbilling_cost_rate",
    "achievement_rate",
    "deviation_project_hours",
    "delivery_time_deviation",
    "teorical_advance",
    "real_advance",
    "forward_deviation",
    "analytic_account_id",
    "sale_line_id",
    "sale_order_id",
)

HIDDEN_NODES_XPATH = (
    "//div[@name='button_box']"
    " | //notebook/page[not(@name='description')]"
    " | //field[{}]".format(
        " or ".join("@name='%s'" % name for name in SENSITIVE_FIELDS)
    )
)


class ProjectProject(models.Model):
    _inherit = "project.project"

    @api.model
    def fields_view_get(
        self, view_id=None, view_type="form", toolbar=False, submenu=False
    ):
        """Hide sensitive project data from restricted users' form view.

        Done in Python because several of these fields/pages come from
        modules that may not be installed, which XML xpaths can't tolerate.
        """
        res = super().fields_view_get(
            view_id=view_id,
            view_type=view_type,
            toolbar=toolbar,
            submenu=submenu,
        )
        if view_type == "form" and self.env.user.has_group(
            RESTRICTED_GROUP_XMLID
        ):
            res["arch"] = self._hide_sensitive_nodes(res["arch"])
        return res

    @api.model
    def _hide_sensitive_nodes(self, arch):
        """Return the form arch with sensitive nodes made invisible."""
        doc = etree.XML(arch)
        for node in doc.xpath(HIDDEN_NODES_XPATH):
            node.set("invisible", "1")
            modifiers = json.loads(node.get("modifiers") or "{}")
            modifiers["invisible"] = True
            node.set("modifiers", json.dumps(modifiers))
        return etree.tostring(doc, encoding="unicode")

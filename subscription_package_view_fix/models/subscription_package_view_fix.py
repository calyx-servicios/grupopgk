# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, models


class SubscriptionPackageViewFix(models.AbstractModel):
    _name = "subscription.package.view.fix"
    _description = "Subscription Package Legacy View Fix"

    @api.model
    def run_view_fix(self) -> bool:
        """Normalize problematic views before subscription_package upgrades.

        The main failure seen in this repository is usually triggered by a
        legacy inherited view of ``account_multicompany_ux`` that anchors on
        ``property_account_income_id``. In some DB states that anchor is no
        longer available and module upgrades fail with ParseError.
        """
        self._fix_subscription_legacy_view()
        self._fix_account_multicompany_view()
        self._disable_legacy_purchase_salary_view()
        self.env["ir.ui.view"].clear_caches()
        return True

    def _fix_subscription_legacy_view(self) -> None:
        """Normalize the legacy subscription view, if needed."""
        view = self.env.ref(
            "subscription_package.product_inherit_subscription",
            raise_if_not_found=False,
        )
        parent = self.env.ref("product.product_normal_form_view")
        if not view:
            return

        desired_arch = self._build_subscription_arch()
        if (
            view.model == "product.product"
            and view.inherit_id.id == parent.id
            and view.arch_db == desired_arch
        ):
            return

        self._update_view_sql(
            view_id=view.id,
            name="Inherit Product Product: Is Subscription Product",
            model="product.product",
            parent_id=parent.id,
            desired_arch=desired_arch,
        )

    def _fix_account_multicompany_view(self) -> None:
        """Replace fragile field anchors in account_multicompany_ux view."""
        view = self.env.ref(
            "account_multicompany_ux.product_template_form_view",
            raise_if_not_found=False,
        )
        parent = self.env.ref("account.product_template_form_view")
        if not view:
            return

        desired_arch = self._build_account_multicompany_arch()
        if (
            view.model == "product.template"
            and view.inherit_id.id == parent.id
            and view.arch_db == desired_arch
        ):
            return

        self._update_view_sql(
            view_id=view.id,
            name="product.template.form",
            model="product.template",
            parent_id=parent.id,
            desired_arch=desired_arch,
        )

    def _build_subscription_arch(self) -> str:
        """Return normalized XML architecture for legacy subscription view."""
        return (
            "<xpath expr=\"//page[@name='sales']\" position=\"after\">"
            "<page name=\"subscription\" string=\"Subscription\">"
            "<group><group name=\"subscription\" string=\"Subscription\">"
            "<field name=\"is_subscription\"/>"
            "<field name=\"subscription_plan_id\" "
            "attrs=\"{'required': [('is_subscription', '=', True)],"
            " 'invisible': [('is_subscription', '!=', True)],}\"/>"
            "</group></group></page></xpath>"
        )

    def _build_account_multicompany_arch(self) -> str:
        """Return robust XML architecture for account_multicompany_ux view."""
        return (
            "<xpath expr=\"//page[@name='invoicing']//group[@name='properties']\" "
            "position=\"inside\">"
            "<group string=\"Receivables (Multi-company)\">"
            "<field name=\"property_account_income_ids\" "
            "widget=\"many2many_tags\" class=\"oe_inline\" "
            "context=\"{'active_model': 'product.template', 'active_id': id,"
            " 'property_field': 'property_account_income_id'}\"/>"
            "<button name=\"action_company_properties\" string=\"(edit)\" "
            "class=\"oe_link\" type=\"object\" "
            "context=\"{'property_field': 'property_account_income_id',"
            " 'property_domain': [('internal_type','=','other'),"
            " ('deprecated','=',False)]}\"/>"
            "</group>"
            "<group string=\"Payables (Multi-company)\">"
            "<field name=\"property_account_expense_ids\" "
            "widget=\"many2many_tags\" class=\"oe_inline\" "
            "context=\"{'active_model': 'product.template', 'active_id': id,"
            " 'property_field': 'property_account_expense_id'}\"/>"
            "<button name=\"action_company_properties\" string=\"(edit)\" "
            "class=\"oe_link\" type=\"object\" "
            "context=\"{'property_field': 'property_account_expense_id',"
            " 'property_domain': [('internal_type','=','other'),"
            " ('deprecated','=',False)]}\"/>"
            "</group>"
            "</xpath>"
        )

    def _disable_legacy_purchase_salary_view(self) -> None:
        """Disable obsolete purchase.order salary view from labor_cost_employee.

        Older databases may keep ``labor_cost_employee.view_purchase_order_form_salary``
        even when the module no longer defines a ``salary`` field on
        ``purchase.order``. When Odoo recomputes inherited views, that stale
        record breaks validation.
        """
        legacy_view = self.env.ref(
            "labor_cost_employee.view_purchase_order_form_salary",
            raise_if_not_found=False,
        )
        if not legacy_view or not legacy_view.active:
            return

        self.env.cr.execute(
            """
            UPDATE ir_ui_view
               SET active = FALSE
             WHERE id = %s
            """,
            (legacy_view.id,),
        )

    def _update_view_sql(
        self,
        view_id: int,
        name: str,
        model: str,
        parent_id: int,
        desired_arch: str,
    ) -> None:
        """Apply the fixed model/parent/arch directly on ``ir_ui_view``."""
        self.env.cr.execute(
            """
            UPDATE ir_ui_view
               SET name = %s,
                   model = %s,
                   inherit_id = %s,
                   arch_db = %s
             WHERE id = %s
            """,
            (
                name,
                model,
                parent_id,
                desired_arch,
                view_id,
            ),
        )

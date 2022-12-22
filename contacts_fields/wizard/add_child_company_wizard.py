from odoo import fields, models


class AddChildCompanyWizard(models.TransientModel):
    _name = "add.child.company.wizard"
    _description = "Add Child Company Wizard"

    company_id = fields.Many2one(
        "res.partner",
        string="Company",
        required=True,
        ondelete="cascade",
        domain=[("is_company", "=", True)],
    )

    def confirm_child_company(self):
        company = self.env["res.partner"].browse(self._context.get("active_id"))
        if self.company_id:
            self.company_id.write({"parent_id": company.id})
        return True

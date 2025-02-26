from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class ProjectIncomeReclassifyWizard(models.TransientModel):
    _name = 'project.income.reclassify.wizard'
    _description = 'Project Income Reclassify Wizard'

    @api.model
    def _get_project_domain(self):
        in_progress = self.env.ref("project.project_project_stage_0").id
        return [
            ("stage_id", "=", in_progress)
        ]

    @api.onchange("project_id")
    def _compute_inputed_incomes_domain(self):
        self.inputed_incomes_id = False
        return {'domain': {'inputed_incomes_id': self._get_incomes_domain()}}

    def _get_incomes_domain(self):
        def null():
            return [("id", "=", -1)]
        if not self.project_id:
            return null()
        else:
            account = self.project_id.analytic_account_id
            if not account:
                return null()
            else:
                aal = self.env["account.analytic.line"].sudo()
                lines = aal.search([
                    ("account_id", "=", account.id),
                    ("move_id.move_id.move_type", "in", ["out_invoice", "out_refund"])
                ])
                return [("id", "in", lines.ids)]

    project_id = fields.Many2one(
        string="Project",
        comodel_name="project.project",
        domain=_get_project_domain,
        required=True
    )
    inputed_incomes_id = fields.Many2one(
        string="Inputed incomes",
        comodel_name="account.analytic.line",
        required=True
    )
    reclassify_project_ids = fields.Many2many(
        string="Projects to reclassify",
        comodel_name="project.project",
        domain=_get_project_domain,
        required=True
    )
    reclassify_ids = fields.One2many(
        string="Reclassify recs",
        comodel_name="project.income.reclassify.wizard.line",
        inverse_name="reclassify_id"
    )

    def has_access(self):
        user = self.env.user
        is_partner = user.is_partner
        is_admin = user.has_group("custom_access_permissions.group_profile_administrator")
        is_manager = user.has_group("custom_access_permissions.group_profile_manager")
        return is_partner or is_admin or is_manager

    def onchange(self, values, field_name, field_onchange):
        if not self.has_access():
            raise ValidationError(
                "You dont have access to this menu"
            )
        return super().onchange(values, field_name, field_onchange)

    @api.onchange("project_id", "inputed_incomes_id","reclassify_project_ids")
    def _set_reclassify_ids(self):
        self = self.sudo()
        LINE = self.env["project.income.reclassify.wizard.line"]
        self.reclassify_ids = False
        if self.inputed_incomes_id and self.reclassify_project_ids:
            currency_id = self.inputed_incomes_id.currency_id.id
            r = self.inputed_incomes_id
            display_name = r.move_id.display_name if r.move_id else r.display_name
            LINE.create({
                "reclassify_id": self.id,
                "name": f"{display_name} - ${r.amount}",
                "currency_id": currency_id,
                "amount": r.amount,
                "is_reclassify_line": True,
                "line_id": self.inputed_incomes_id.id,
                "project_id": self.project_id.id
            })
            for project in self.reclassify_project_ids:
                LINE.create({
                    "reclassify_id": self.id,
                    "name": project.name,
                    "currency_id": currency_id,
                    "project_id": project.id.origin
                })

    def reclassify(self):
        amounts = self.reclassify_ids.mapped("amount_reclassify")
        income_line = self.reclassify_ids.filtered(lambda r: r.is_reclassify_line == True)
        reclassify_lines = self.reclassify_ids.filtered(lambda r: r.is_reclassify_line == False)

        if income_line.amount_reclassify < 0:
            raise ValidationError(
                "Los montos deben ser positivos"
            )
        for amount in reclassify_lines.mapped("amount_reclassify"):
            if amount <= 0:
                raise ValidationError(
                    "Los montos deben ser positivos"
                )
        if income_line.amount <= income_line.amount_reclassify:
            raise ValidationError(
                "El monto a reclasificar debe ser menor al monto inicial del apunte contable"
            )
        if income_line.amount != sum(amounts):
            raise ValidationError(
                "La suma de montos a reclasificar debe ser igual al monto de origen"
            )

        approver_id = income_line.project_id.user_id.id
        user_id = self.env.user.id
        PIR = self.env["project.income.reclassify"]
        PIRL = self.env["project.income.reclassify.line"]
        recl = PIR.create({
            "approver_id": approver_id,
            "user_id": user_id
        })
        for line in self.reclassify_ids:
            PIRL.create({
                "name": line.name,
                "project_id": line.project_id.id,
                "line_id": line.line_id.id if line.line_id else False,
                "amount": line.amount,
                "amount_reclassify": line.amount_reclassify,
                "currency_id": line.currency_id.id if line.currency_id else False,
                "is_reclassify_line": line.is_reclassify_line,
                "reclassify_id": recl.id
            })


class ProjectIncomeReclassifyWizardLine(models.TransientModel):
    _name = 'project.income.reclassify.wizard.line'
    _description = 'Project Income Reclassify Wizard Line'

    name = fields.Char(
        string="Name",
        required=True
    )
    project_id = fields.Many2one(
        comodel_name="project.project"
    )
    line_id = fields.Many2one(
        comodel_name="account.analytic.line"
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        required=True
    )
    amount = fields.Monetary(
        string="Amount",
        currency_field="currency_id"
    )
    amount_reclassify = fields.Monetary(
        string="Amount to reclassify",
        currency_field="currency_id"
    )
    reclassify_id = fields.Many2one(
        comodel_name="project.income.reclassify.wizard"
    )
    is_reclassify_line = fields.Boolean()

from odoo import fields, models, api, _


class ProjectIncomeReclassify(models.Model):
    _name = 'project.income.reclassify'
    _description = 'project.income.reclassify'

    state = fields.Selection(
        string="Status",
        selection=[
            ("cancel", "Cancelled"),
            ("pending", "Pending"),
            ("done", "Done")
        ],
        default="pending"
    )
    name = fields.Char(
        string="Name",
        compute="_compute_name"
    )
    line_ids = fields.One2many(
        string="Lines",
        comodel_name="project.income.reclassify.line",
        inverse_name="reclassify_id"
    )
    approver_id = fields.Many2one(
        string="Approver",
        comodel_name="res.users",
    )
    user_id = fields.Many2one(
        string="Requested by",
        comodel_name="res.users",
    )
    can_cancel = fields.Boolean(
        compute="_compute_can_cancel"
    )
    can_approve = fields.Boolean(
        compute="_compute_can_approve"
    )
    analytic_lines = fields.One2many(
        string="Analytic lines",
        comodel_name="account.analytic.line",
        inverse_name="project_income_reclassify_id"
    )

    def _compute_can_cancel(self):
        user = self.env.user.id
        for rec in self:
            rec.can_cancel = False
            if rec.user_id.id == user or rec.approver_id.id == user:
                rec.can_cancel = True

    def _compute_can_approve(self):
        user = self.env.user.id
        for rec in self:
            rec.can_approve = False
            if rec.approver_id.id == user:
                rec.can_approve = True

    def cancel(self):
        user = self.env.user.id
        self = self.sudo()
        for rec in self:
            if rec.can_cancel:
                rec.state = "cancel"

    def approve(self):
        user = self.env.user.id
        self = self.sudo()
        AAL = self.env["account.analytic.line"]
        for rec in self:
            if rec.can_approve:
                line_ids = rec.line_ids
                income_line = line_ids.filtered(lambda r: r.is_reclassify_line == True)
                non_income_lines = line_ids.filtered(lambda r: r.is_reclassify_line == False)
                AAL.create({
                    "name": rec.name,
                    "account_id": income_line.project_id.analytic_account_id.id,
                    "project_id": income_line.project_id.id,
                    "unit_amount": 1,
                    "project_income_reclassify_id": rec.id
                }).write({
                    "amount": -(income_line.amount - income_line.amount_reclassify)
                })
                for line in non_income_lines:
                    AAL.create({
                        "name": rec.name,
                        "account_id": line.project_id.analytic_account_id.id,
                        "unit_amount": 1,
                        "project_id": line.project_id.id,
                        "project_income_reclassify_id": rec.id
                    }).write({"amount": line.amount_reclassify})
                rec.state = "done"

    def _compute_name(self):
        for rec in self:
            line_ids = rec.line_ids
            income_line = line_ids.filtered(lambda r: r.is_reclassify_line == True)
            non_income_lines = line_ids.filtered(lambda r: r.is_reclassify_line == False)
            rec.name = f"{income_line.project_id.name} => {', '.join(non_income_lines.mapped('project_id.name'))}"


class ProjectIncomeReclassifyLine(models.Model):
    _name = 'project.income.reclassify.line'
    _description = 'project.income.reclassify.line'

    project_id = fields.Many2one(
        comodel_name="project.project",
        required=True,
    )
    name = fields.Char(
        'Name',
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
        comodel_name="project.income.reclassify"
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        required=True
    )
    project_id = fields.Many2one(
        comodel_name="project.project"
    )
    line_id = fields.Many2one(
        comodel_name="account.analytic.line"
    )
    is_reclassify_line = fields.Boolean()

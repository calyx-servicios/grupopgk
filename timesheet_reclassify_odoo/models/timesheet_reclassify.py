from odoo import fields, models, api, _


class TimesheetReclassify(models.Model):
    _name = 'timesheet.reclassify'
    _description = 'timesheet.reclassify'
    _rec_name = "ticket_id"

    state = fields.Selection(
        string="Status",
        selection=[
            ("cancel", "Cancelled"),
            ("pending", "Pending"),
            ("done", "Done")
        ],
        default="pending"
    )
    ticket_id = fields.Many2one(
        string="Ticket",
        comodel_name="timesheet.sige"
    )
    line_ids = fields.One2many(
        string="Lines",
        comodel_name="timesheet.reclassify.line",
        inverse_name="reclassify_id"
    )
    approver_ids = fields.Many2many(
        string="Approvers",
        comodel_name="res.users"
    )

    def cancel(self):
        self = self.sudo()
        for rec in self:
            rec.state = "cancel"

    @api.constrains("state")
    def _onchange_state(self):
        self = self.sudo()
        AAL = self.env["account.analytic.line"]
        for rec in self:
            if rec.state == "done":
                for line in rec.line_ids:
                    if line.analytic_line:
                        if line.unit_amount_reclassify:
                            line.analytic_line.unit_amount = line.unit_amount_reclassify
                        else:
                            line.analytic_line.unlink()
                    else:
                        if line.unit_amount_reclassify:
                            AAL.create({
                                "timesheet_id": rec.ticket_id.id,
                                "project_id": line.project_id.id,
                                "unit_amount": line.unit_amount_reclassify,
                                "name": line.name,
                            })


class TimesheetReclassifyLine(models.Model):
    _name = 'timesheet.reclassify.line'
    _description = 'timesheet.reclassify.line'

    project_id = fields.Many2one(
        comodel_name="project.project",
        required=True,
        domain =[('allow_timesheets', '=', True)]
    )
    name = fields.Char(
        'Description',
        required=True
    )
    unit_amount = fields.Float(
        'Quantity',
        default=0.0
    )
    unit_amount_reclassify = fields.Float(
        'Quantity to reclasify',
        default=0.0
    )
    reclassify_id = fields.Many2one(
        comodel_name="timesheet.reclassify"
    )
    analytic_line = fields.Many2one(
        comodel_name="account.analytic.line"
    )
    approver_id = fields.Many2one(
        string="Approver",
        comodel_name="res.users"
    )
    state = fields.Selection(
        string="Status",
        selection=[
            ("to_approve", "To Approve"),
            ("approved", "approved"),
        ],
        default="to_approve"
    )
    approved = fields.Boolean(
        string="Approved"
    )
    can_approve = fields.Boolean(
        compute="_compute_can_approve"
    )

    def _compute_can_approve(self):
        user = self.env.user
        for rec in self:
            rec.can_approve = False
            if rec.approver_id and rec.approved == False and rec.approver_id.id == user.id:
                if rec.reclassify_id.state == "pending":
                    rec.can_approve = True

    def approve(self):
        self = self.sudo()
        for rec in self:
            rec.approved = True
        reclassify_ids = self.mapped("reclassify_id")
        for reclassify in reclassify_ids:
            approve_lines = reclassify.line_ids.filtered(lambda l: l.approver_id)
            if set(approve_lines.mapped("approved")) == {True}:
                reclassify.state = "done"

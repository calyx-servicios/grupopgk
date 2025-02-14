from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class TimesheetReclassifyWizard(models.TransientModel):
    _name = 'timesheet.reclassify.wizard'
    _description = 'Timesheet Reclassify Wizard'

    reclassify_id = fields.Many2one(
        string="Reclassify",
        comodel_name="account.analytic.line"
    )
    reclassify_ids = fields.One2many(
        string="Reclassify recs",
        comodel_name="timesheet.line.reclassify.wizard",
        inverse_name="reclassify_id"
    )
    analytic_lines = fields.Text(
        compute="_compute_analytic_lines"
    )

    @api.depends("reclassify_ids")
    def _compute_analytic_lines(self):
        for rec in self:
            rec.analytic_lines = False
            if rec.reclassify_ids:
                rec.analytic_lines = rec.reclassify_ids.mapped("analytic_line").ids

    @api.onchange("reclassify_id")
    def _onchange_reclassify_id(self):
        TLRW = self.env["timesheet.line.reclassify.wizard"]
        for rec in self:
            if rec.reclassify_id:
                TLRW.create({
                    "project_id": rec.reclassify_id.project_id.id if rec.reclassify_id.project_id else False,
                    "name": rec.reclassify_id.name,
                    "unit_amount": rec.reclassify_id.unit_amount,
                    "reclassify_id": rec.id,
                    "analytic_line": rec.reclassify_id.id
                })
                rec.reclassify_id = False

    def reclassify(self):
        sum_unit_amount = sum(self.mapped("reclassify_ids.unit_amount"))
        sum_unit_amount_reclassify = sum(self.mapped("reclassify_ids.unit_amount_reclassify"))
        if not len(self.reclassify_ids):
            raise ValidationError(_(
                "There are not lines to reclassify"
            ))
        if sum_unit_amount != sum_unit_amount_reclassify:
            raise ValidationError(_(
                "The quantity of hours to reclassify must be equal to the quantity of hours"
            ))
        TR = self.env["timesheet.reclassify"].sudo()
        TRL = self.env["timesheet.reclassify.line"].sudo()
        ticket_id = self.env.context.get("active_id")
        reclassify_count = TR.search_count([
            ("state", "=", "pending"),
            ("ticket_id", "=", ticket_id)
        ])
        if reclassify_count > 0:
            raise ValidationError(_(
                "There is a pending reclassification"
            ))
        reclassify_id = TR.create({
            "ticket_id": ticket_id,
        })
        for rec in self.reclassify_ids:
            approv_id = False
            if rec.unit_amount_reclassify > rec.unit_amount:
                approv_id = rec.project_id.user_id.id
            TRL.create({
                "project_id": rec.project_id.id,
                "name": rec.name,
                "unit_amount": rec.unit_amount,
                "unit_amount_reclassify": rec.unit_amount_reclassify,
                "reclassify_id": reclassify_id.id,
                "analytic_line": rec.analytic_line.id if rec.analytic_line else False
            })

    def onchange(self, values, field_name, field_onchange):
        TR = self.env["timesheet.reclassify"].sudo()
        ticket_id = self.env.context.get("active_id")
        reclassify_count = TR.search_count([
            ("state", "=", "pending"),
            ("ticket_id", "=", ticket_id)
        ])
        if reclassify_count > 0:
            raise ValidationError(_(
                "There is a pending reclassification"
            ))
        return super().onchange(values, field_name, field_onchange)


class TimesheetLineReclassifyWizard(models.TransientModel):
    _name = 'timesheet.line.reclassify.wizard'
    _description = 'Timesheet Line Reclassify Wizard'

    project_id = fields.Many2one(
        comodel_name="project.project",
        required=True,
        domain =[('allow_timesheets', '=', True)]
    )
    project_no_facturable = fields.Boolean(
        compute='_compute_no_facturable'
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
        comodel_name="timesheet.reclassify.wizard"
    )
    analytic_line = fields.Many2one(
        comodel_name="account.analytic.line"
    )

    @api.depends('project_id')
    def _compute_no_facturable(self):
        for record in self:
            if record.project_id and record.project_id.name and 'no facturable' in record.project_id.name.lower():
                record.project_no_facturable = True
            else:
                record.project_no_facturable = False

    @api.constrains('unit_amount_reclassify')
    def _check_timesheet_line(self):
        for record in self:
            if record.unit_amount_reclassify < 0 or record.unit_amount_reclassify % 0.5 != 0:
                raise ValidationError(_("Hours cant be less than zero and multiple of 0.5."))

from odoo import fields, models, _, api
from datetime import date, datetime
from dateutil.relativedelta import relativedelta


class LaborCostEmployeeWizard(models.TransientModel):
    _name = "labor.cost.employee.wizard"
    _description = _("Calculate labor cost wizard")

    def get_years():
        year_list = []
        for i in range(2000, 2100):
            year_list.append((str(i), str(i)))
        return year_list

    month = fields.Selection([
        ("1", 'January'), 
        ("2", 'February'), 
        ("3", 'March'), 
        ("4", 'April'),
        ("5", 'May'), 
        ("6", 'June'), 
        ("7", 'July'), 
        ("8", 'August'), 
        ("9", 'September'), 
        ("10", 'October'), 
        ("11", 'November'), 
        ("12", 'December'), 
    ], string='Month', default=str(date.today().month))
    year = fields.Selection(get_years(), string='Year', default=str(date.today().year))
    name = fields.Char("Period", compute="_compute_period")
    file_cost = fields.Binary("Attach")
    invoice_ids = fields.Many2many("account.move", string="Invoices")

    @api.depends("month", "year")
    def _compute_period(self):
        if self.month and self.year:
            month = _(dict(self.fields_get(allfields=['month'])['month']['selection'])[self.month])
            self.name = month + " " + self.year
        else:
            self.name = "/"

    @api.onchange("name")
    def onchange_period(self):
        if self.month and self.year:
            date_act = date.today().replace(month=int(self.month), year=int(self.year))
            date_from = date_act.replace(day=1)
            date_to = date_act + relativedelta(day=31)
            partners = self.env['hr.employee'].search([]).filtered(lambda emp: emp.user_partner_id != False).mapped("user_partner_id")
            if partners:
                domain = [
                    ('invoice_date', '>=', date_from),
                    ('invoice_date', '<=', date_to),
                    ('move_type','in',['in_invoice','in_refund']),
                    ('partner_id', 'in', partners.ids)
                ]
                return {'domain': {'invoice_ids': domain }}
    
    def calculate_labor_cost(self):
        pass


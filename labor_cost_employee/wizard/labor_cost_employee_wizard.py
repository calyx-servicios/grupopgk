from odoo import fields, models, _, api
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import base64


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
    period_sige = fields.Char("Period Sige")
    file_cost = fields.Binary("Attach")
    invoice_ids = fields.Many2many("account.move", string="Invoices")

    @api.depends("month", "year")
    def _compute_period(self):
        if self.month and self.year:
            month = _(dict(self.fields_get(allfields=['month'])['month']['selection'])[self.month])
            self.name = month + " " + self.year
            self.period_sige = self.year + self.month.zfill(2)
        else:
            self.name = "/"
            self.period_sige = "/"

    @api.onchange("name")
    def onchange_period(self):
        if self.month and self.year:
            date_act = date.today().replace(month=int(self.month), year=int(self.year))
            date_from = date_act.replace(day=1)
            date_to = date_act + relativedelta(day=31)
            partners = self.env['hr.employee'].search([]).filtered(lambda emp: emp.user_partner_id != False).mapped("user_partner_id")
            if partners:
                self.invoice_ids = False
                domain = [
                    ('invoice_date', '>=', date_from),
                    ('invoice_date', '<=', date_to),
                    ('move_type','in',['in_invoice','in_refund']),
                    ('partner_id', 'in', partners.ids),
                    ('salary', '=', True)
                ]
                invoices = self.env['account.move'].search(domain)
                if invoices:
                    self.invoice_ids = [(6, 0, invoices.ids)]

    def calculate_labor_cost(self):
        tm_sige_obj = self.env['timesheet.sige']
        lce_obj = self.env['labor.cost.employee']
        values = []
        cost = []
        data_str = base64.b64decode(self.file_cost).decode('UTF-8')
        for line in data_str.split('\n'):
            if line != '':
                data = line.split(';')
                if len(data) >= 1:
                    exist = list(filter(lambda e: e['employee_id'] == data[0], cost))
                    if len(exist) != 0:
                        index_obj = cost.index(exist[0])
                        cost[index_obj]['amount'] = cost[index_obj]['amount'] + float(data[1])
                        cost[index_obj]['calculation'] = cost[index_obj]['calculation'] + (_('Salary: {}'.format(str(data[1]))))
                    else:
                        cost.append({'employee_id': data[0], 'amount': float(data[1]), 'calculation': _('Salary: {}'.format(str(data[1])))})

        if self.invoice_ids:
            txt_invoice = _('Total amount invoiced: ')
            for invoice in self.invoice_ids:
                exist_inv = list(filter(lambda e: e['employee_id'] == invoice.partner_id.vat, cost))
                if len(exist_inv) != 0:
                    index_obj = cost.index(exist_inv[0])
                    cost[index_obj]['amount'] = cost[index_obj]['amount'] + invoice.amount_total
                else:
                    cost.append({'employee_id': invoice.partner_id.vat, 'amount': invoice.amount_total, 'calculation': f'{txt_invoice}+ {invoice.amount_total}'})


        employees = self.env['hr.employee'].search([]).filtered(lambda emp: emp.user_partner_id != False)
        date_act = date.today().replace(month=int(self.month), year=int(self.year))
        start_of_period = date_act.replace(day=1)
        end_of_period = date_act + relativedelta(day=31)
        for employee in employees:
            tm_sige_emp = tm_sige_obj.search([('employee_id', '=', employee.id), ('state','=','close'), ('start_of_period', '=', start_of_period),('end_of_period','=', end_of_period)], limit=1)
            exist_emp = list(filter(lambda e: e['employee_id'] == employee.user_partner_id.vat, cost))
            if len(exist_emp) != 0 and tm_sige_emp:
                index_obj = cost.index(exist_emp[0])
                amount = cost[index_obj].pop('amount')
                labor_cost = amount / tm_sige_emp.register_hours
                cost[index_obj]['cost'] = labor_cost
                cost[index_obj]['employee_id'] = employee.id
                cost[index_obj]['name'] = self.name
                cost[index_obj]['calculation'] += _('\n Amount(Salary + Invoiced Amount) {} / {} (Register Hours) = {} (Labor cost)'.format(amount, tm_sige_emp.register_hours, labor_cost))
                employee.timesheet_cost = labor_cost
                tm_sige_emp.timesheet_ids.write({'amount': labor_cost})

        lce_obj.create(cost)

        action = self.env.ref("labor_cost_employee.action_window_labor_cost").read()[0]
        return action

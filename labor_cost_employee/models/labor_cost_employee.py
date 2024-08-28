from odoo import fields, models, api, _

class LaborCostEmployee(models.Model):
    _name = "labor.cost.employee"
    _description = _("Labor cost per employee")

    def get_years():
        year_list = []
        for i in range(2000, 2100):
            year_list.append((str(i), str(i)))
        return year_list

    name = fields.Char("Period")
    employee_id = fields.Many2one("hr.employee", string="Employee")
    cost = fields.Float(string="Cost", digits=(16,2))
    calculation = fields.Text(string="Calculation") 
    date = fields.Date(string='Date', compute='_compute_date', store=True)
    year = fields.Selection(get_years(), string='Year', default=str(fields.Date.today().year))
    amount = fields.Char(string="Amount", digits=(16,2))

    @api.depends('name')
    def _compute_date(self):
        for record in self:
            month_str, year_str = record.name.split()
            month_dict = {
                _('January'): '01',
                _('February'): '02',
                _('March'): '03',
                _('April'): '04',
                _('May'): '05',
                _('June'): '06',
                _('July'): '07',
                _('August'): '08',
                _('September'): '09',
                _('October'): '10',
                _('November'): '11',
                _('December'): '12',
            }
            month_num = month_dict[month_str.capitalize()]
            date_str = f'{year_str}-{month_num}-01'
            record.date = fields.Date.from_string(date_str)

    def open_labor_cost_form(self):
        return {
            'name': self._description,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'labor.cost.employee',
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }
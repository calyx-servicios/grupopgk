from odoo import api, fields, models, _
from datetime import date, timedelta, datetime
import base64, calendar, xlsxwriter
from io import BytesIO



class AccountConsolidationReport(models.Model):
    _name = 'account.consolidation.report'
    _description = 'Export consolidation report'

    year = fields.Integer(default=lambda self: self._default_year(), help='Year of the period', string='Year')
    month = fields.Integer(default=lambda self: self._default_month(), help='Month of the period', string='Month')
    period = fields.Char(compute="_compute_period", string='Period')
    date_from = fields.Date('From', readonly=True, compute="_compute_dates")
    date_to = fields.Date('To', readonly=True, compute="_compute_dates")
    currency_id = fields.Many2one(
        'res.currency', string='Currency Origin')
    new_currency = fields.Many2one(
        'res.currency', string='New Currency')
    amount_rate = fields.Float(string='Amount rate')
    export_consolidation_data = fields.Text('File content')
    export_consolidation_file = fields.Binary('Download File', compute="_compute_files", readonly=True)
    export_consolidation_filename = fields.Char('File consolidation', compute="_compute_files", readonly=True)
    company_id = fields.Many2one('res.company')
    consolidation_key = fields.Char(compute='_compute_consolidation_key', store=True)

    @api.depends('year', 'month', 'company_id')
    def _compute_consolidation_key(self):
        for record in self:
            companies = record.company_id.mapped('name')
            if companies:
                companies_str = ', '.join(companies)
            else:
                companies_str = 'all'
            record.consolidation_key = '%d/%02d (%s)' % (record.year, record.month, companies_str)

    _sql_constraints = [
        ('consolidation_key_unique', 'unique(consolidation_key)', 'A report already exists for this period and companies.')
    ]

    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, '%s%.2d' % (rec.year, rec.month)))
        return res

    @staticmethod
    def _last_month():
        today = date.today()
        first = today.replace(day=1)
        return first - timedelta(days=1)

    def _default_year(self):
        return self._last_month().year

    def _default_month(self):
        return self._last_month().month

    @api.onchange('year', 'month')
    def _compute_period(self):
        for reg in self:
            reg.period = '%s/%s' % (reg.year, reg.month)

    @api.onchange('year', 'month')
    def _compute_dates(self):
        for rec in self:
            month = rec.month
            year = int(rec.year)
            first_day = datetime(year=year, month=month, day=1).date()
            last_day = datetime(year=year, month=month, day=calendar.monthrange(year, month)[1]).date()
            rec.date_from = first_day
            rec.date_to = last_day
    
    def compute_consolidation_data(self):
        data = {
            'vals': []
        }
        for record in self:
            if not record.company_id:
                domain = [
                ('date', '>=', record.date_from),
                ('date', '<=', record.date_to)
                ]
            else:
                domain = [
                ('date', '>=', record.date_from),
                ('date', '<=', record.date_to),
                ('company_id', '=', record.company_id.id)
                ]
            analytic_lines = self.env['account.analytic.line'].search(domain)

            for line in analytic_lines:
                line.update_currency_id()

            lines_matches = analytic_lines.filtered(lambda x: x.currency_id.id == record.currency_id.id)
            for line in lines_matches:
                if line.account_id:
                    account_code = line.account_id.name
                else:
                    account_code = ''

                company_names = ', '.join(line.mapped('company_id.name'))

                data['vals'].append({
                    'description': line.name or '',
                    'account_id': account_code,
                    'company': company_names,
                    'amount': line.amount * record.amount_rate or 0.0,
                    'currency': record.new_currency.symbol or ''
                })

            # Create Excel file
            output = BytesIO()
            workbook = xlsxwriter.Workbook(output)
            worksheet = workbook.add_worksheet(_('Consolidated Report'))

            # Add headers
            bold = workbook.add_format({
            'bold': True,
            'align': 'center',
            })
            headers = [_('Description'), _('Account Name'), _('Companies'), _('Amount'), _('Currency')]
            for i, header in enumerate(headers):
                worksheet.write(0, i, header, bold)

            # Add data
            for row, vals in enumerate(data['vals']):
                worksheet.write(row+1, 0, vals['description'])
                worksheet.write(row+1, 1, vals['account_id'])
                worksheet.write(row+1, 2, vals['company'])
                worksheet.write(row+1, 3, vals['amount'])
                worksheet.write(row+1, 4, vals['currency'])

            # Save and encode file
            workbook.close()
            output.seek(0)
            file_data = output.read()
            encoded_file = base64.encodebytes(file_data)

            # Set values on model
            record.export_consolidation_data = encoded_file

    @api.depends('export_consolidation_data')
    def _compute_files(self):
        for record in self:
            filename = _('Consolidation-%s-%s.xls') % (record.date_from, record.date_to)
            record.export_consolidation_filename = filename
            if record.export_consolidation_data:
                record.export_consolidation_file = record.export_consolidation_data
            else:
                record.export_consolidation_file = False

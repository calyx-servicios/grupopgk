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
    consolidation_companies = fields.One2many('account.consolidation.company', 'account_consolidation_report_id', string='Companies and currencies')
    export_consolidation_data = fields.Text('File content')
    export_consolidation_file = fields.Binary('Download File', compute="_compute_files", readonly=True)
    export_consolidation_filename = fields.Char('File consolidation', compute="_compute_files", readonly=True)
    consolidation_key = fields.Char(compute='_compute_consolidation_key', store=True)

    @api.depends('year', 'month', 'consolidation_companies')
    def _compute_consolidation_key(self):
        for record in self:
            companies = record.consolidation_companies.mapped('company_id').mapped('name')
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
        for record in self:
            data = {
                'vals': []
            }
            if record.consolidation_companies:
                for company in record.consolidation_companies:
                    domain = [
                    ('date', '>=', record.date_from),
                    ('date', '<=', record.date_to),
                    ('company_id', '=', company.company_id.id),
                    ('currency_id', '=', company.currency_id.id),
                    ]
                    analytic_lines = self.env['account.analytic.line'].search(domain)

                    for line in analytic_lines:
                        line.update_currency_id()

                    lines_matches = analytic_lines.filtered(lambda x: x.currency_id.id == company.currency_id.id)
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
                            'currency_origin': company.currency_id.symbol or '',
                            'currency': company.new_currency.symbol or '',
                            'rate': company.rate,
                            'amount': line.amount * company.rate or 0.0,
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
                headers = [_('Description'), _('Account Name'), _('Companies'), _('Currency Origin'), _('Currency'), _('Rate'), _('Amount')]

                worksheet.set_column('A:A', 1)
                worksheet.set_column('A:A', 50)
                worksheet.set_column('B:B', 1)
                worksheet.set_column('B:B', 30)
                worksheet.set_column('C:C', 1)
                worksheet.set_column('C:C', 18)
                worksheet.set_column('D:D', 1)
                worksheet.set_column('D:D', 18)
                worksheet.set_column('E:E', 1)
                worksheet.set_column('E:E', 18)
                worksheet.set_column('F:F', 1)
                worksheet.set_column('F:F', 18)
                worksheet.set_column('G:G', 1)
                worksheet.set_column('G:G', 18)

                for i, header in enumerate(headers):
                    worksheet.write(0, i, header, bold)

                # Add data
                for row, vals in enumerate(data['vals']):
                    worksheet.write(row+1, 0, vals['description'])
                    worksheet.write(row+1, 1, vals['account_id'])
                    worksheet.write(row+1, 2, vals['company'])
                    worksheet.write(row+1, 3, vals['currency_origin'])
                    worksheet.write(row+1, 4, vals['currency'])
                    worksheet.write(row+1, 5, vals['rate'])
                    worksheet.write(row+1, 6, vals['amount'])

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

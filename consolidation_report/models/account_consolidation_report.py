from odoo import api, fields, models, _
import base64, xlsxwriter
from io import BytesIO


class AccountConsolidationReport(models.Model):
    _name = 'account.consolidation.report'
    _description = 'Export consolidation report'


    name = fields.Char(string='Name')
    period = fields.Char(compute="_compute_period", string='Period')
    consolidation_period = fields.Many2one('account.consolidation.period', string='Select a period')
    export_consolidation_data = fields.Text('File content')
    export_consolidation_file = fields.Binary('Download File', compute="_compute_files", readonly=True)
    export_consolidation_filename = fields.Char('File consolidation', compute="_compute_files", readonly=True)
    
    @api.depends('consolidation_period')
    def _compute_period(self):
        for record in self:
            if record.consolidation_period:
                record.period = record.consolidation_period.period
            else:
                record.period = '/'

    @api.onchange('consolidation_period')
    def _onchange_consolidation_period(self):
        for record in self:
            if record.consolidation_period:
                record.name =  _('Consolidation Report: ') + str(record.consolidation_period.date_from) +  ' ' + str(record.consolidation_period.date_to)
            else:
                record.name = '/'

    def compute_consolidation_data(self):
        for record in self:
            data = {}
            if record.consolidation_period.consolidation_companies:
                data = record.prepare_excel_data()
                # Create Excel file
                output = BytesIO()
                workbook = xlsxwriter.Workbook(output)
                worksheet = workbook.add_worksheet(_('Consolidated Report'))

                # Add headers
                bold = workbook.add_format({
                'bold': True,
                'align': 'center',
                })
                merge_format = workbook.add_format(
                {
                    "bold": 1,
                    "border": 1,
                    "align": "left",
                    "valign": "vleft",
                    "fg_color": "gray",
                })
                headers = [_('Description'), _('Account Name'), _('Companies'), _('Currency Origin'), _('Currency'), _('Rate'), _('Amount'), _('Total')]

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
                worksheet.set_column('H:H', 1)
                worksheet.set_column('H:H', 18)

                for i, header in enumerate(headers):
                    worksheet.write(0, i, header, bold)

                row = 1
                for grandfather_group, mother_groups in data.items():
                    for mother_group, grandmother_accounts in mother_groups.items():
                        for grandmother_account, mother_accounts in grandmother_accounts.items():
                            for mother_account, daughter_accounts in mother_accounts.items():
                                for daughter_account, vals in daughter_accounts.items():
                                    worksheet.merge_range(row, 0, row, 7, grandfather_group, merge_format)
                                    row += 1
                                    worksheet.merge_range(row, 0, row, 7, grandfather_group + ' / ' + mother_group, merge_format)
                                    row += 1
                                    worksheet.merge_range(row, 0, row, 7, grandfather_group + ' / ' + mother_group + ' / ' + grandmother_account, merge_format)
                                    row += 1
                                    worksheet.merge_range(row, 0, row, 7, grandfather_group + ' / ' + mother_group + ' / ' + grandmother_account + ' / ' + mother_account, merge_format)
                                    row += 1
                                    worksheet.merge_range(row, 0, row, 7, grandfather_group + ' / ' + mother_group + ' / ' + grandmother_account + ' / ' + mother_account + '/' + daughter_account, merge_format)
                                    row += 1
                                    total = 0
                                    for val in vals:
                                        worksheet.write(row, 0, val['description'])
                                        worksheet.write(row, 1, val['account_id'])
                                        worksheet.write(row, 2, val['company'])
                                        worksheet.write(row, 3, val['currency_origin'])
                                        worksheet.write(row, 4, val['currency'])
                                        worksheet.write(row, 5, val['rate'])
                                        worksheet.write(row, 6, val['amount'])
                                        total += val['amount']
                                        row += 1
                                    worksheet.write(row, 7, total)
                                    row += 1

                # Save and encode file
                workbook.close()
                output.seek(0)
                file_data = output.read()
                encoded_file = base64.encodebytes(file_data)

                # Set values on model
                record.export_consolidation_data = encoded_file

    def prepare_excel_data(self):

        for record in self:
            data = {}

            if record.consolidation_period.consolidation_companies:
                grandfather_groups = self.env['account.analytic.group'].search([('parent_id', '=', False)])
                domain = [('date', '>=', record.consolidation_period.date_from), ('date', '<=', record.consolidation_period.date_to)]
                analytic_lines = self.env['account.analytic.line'].search(domain)
                if analytic_lines:
                    for line in analytic_lines:
                        grandfather_group = line.account_id.group_id.parent_id.name or 'Undefined'
                        mother_group = line.account_id.group_id.name or 'Undefined'
                        grandmother_account = line.account_id.parent_id.parent_id.name or 'Undefined'
                        mother_account = line.account_id.parent_id.name or 'Undefined'
                        daughter_account = line.account_id.name or 'Undefined'

                        if grandfather_group not in data:
                            data[grandfather_group] = {}
                        if mother_group not in data[grandfather_group]:
                            data[grandfather_group][mother_group] = {}
                        if grandmother_account not in data[grandfather_group][mother_group]:
                            data[grandfather_group][mother_group][grandmother_account] = {}
                        if mother_account not in data[grandfather_group][mother_group][grandmother_account]:
                            data[grandfather_group][mother_group][grandmother_account][mother_account] = {}

                        # _logger.info('witchcraft: {} - '.format(data))
                        rate = None
                        new_currency = None
                        currency_origin = None
                        if line.move_id.company_id in record.consolidation_period.consolidation_companies.mapped('company_id'):
                            consolidation_period = record.consolidation_period.consolidation_companies.filtered(lambda x: x.company_id == line.move_id.company_id)
                            if consolidation_period:
                                currency_origin = consolidation_period.currency_id.symbol
                                new_currency = consolidation_period.new_currency.symbol
                                if consolidation_period.historical_rate:
                                    if line.move_id.move_id.l10n_ar_currency_rate:
                                        rate = line.move_id.move_id.l10n_ar_currency_rate
                                    else:
                                        date = line.move_id.date
                                        rate = line.move_id.currency_id.with_context(date=date).rate
                                else:
                                    rate = consolidation_period.rate

                        data[grandfather_group][mother_group][grandmother_account][mother_account].setdefault(daughter_account, []).append({
                            'account_id': line.account_id.code,
                            'company': line.move_id.company_id.name,
                            'currency_origin': currency_origin if currency_origin else'',
                            'currency': new_currency if new_currency else '',
                            'rate': rate if rate else 1,
                            'description': line.name or '',
                            'amount': line.amount * rate if rate else line.amount,
                        })

            return data

    @api.depends('export_consolidation_data', 'period')
    def _compute_files(self):
        for record in self:
            filename = _('Consolidation-%s.xls') % (record.period)
            record.export_consolidation_filename = filename
            if record.export_consolidation_data:
                record.export_consolidation_file = record.export_consolidation_data
            else:
                record.export_consolidation_file = False

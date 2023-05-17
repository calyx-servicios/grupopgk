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
            totals = {}
            if record.consolidation_period.consolidation_companies:
                data = record.prepare_excel_data()
                totals = record.get_totals(data)
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
                total_format = workbook.add_format(
                {
                    "bold": 1,
                    "border": 1,
                    "align": "left",
                    "valign": "vleft",
                    "fg_color": "gray",
                    "num_format": "$#,##0.00",
                })
                currency_format = workbook.add_format({'num_format': '$#,##0.00'})
                headers = [_('Description'), _('Account Name'), _('Companies'), _('Target Currency'), _('Currency'), _('Rate'), _('Amount'), _('Total')]

                worksheet.set_column('A:A', 1)
                worksheet.set_column('A:A', 50)
                worksheet.set_column('B:B', 1)
                worksheet.set_column('B:B', 30)
                worksheet.set_column('C:C', 1)
                worksheet.set_column('C:C', 18)
                worksheet.set_column('D:D', None, None, {'hidden': True})
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
                            for mother_account, companies in mother_accounts.items():
                                for company, daughter_accounts in companies.items():
                                    for daughter_account, vals in daughter_accounts.items():
                                        worksheet.merge_range(row, 0, row, 6, grandfather_group, merge_format)
                                        worksheet.write(row, 7, totals[grandfather_group]['total'], total_format)
                                        row += 1
                                        worksheet.merge_range(row, 0, row, 6, grandfather_group + ' / ' + mother_group, merge_format)
                                        worksheet.write(row, 7, totals[grandfather_group][mother_group]['total'], total_format)
                                        row += 1
                                        worksheet.merge_range(row, 0, row, 6, grandfather_group + ' / ' + mother_group + ' / ' + grandmother_account, merge_format)
                                        worksheet.write(row, 7, totals[grandfather_group][mother_group][grandmother_account]['total'], total_format)
                                        row += 1
                                        worksheet.merge_range(row, 0, row, 6, grandfather_group + ' / ' + mother_group + ' / ' + grandmother_account + ' / ' + mother_account, merge_format)
                                        worksheet.write(row, 7, totals[grandfather_group][mother_group][grandmother_account][mother_account]['total'], total_format)
                                        row += 1
                                        worksheet.merge_range(row, 0, row, 6, grandfather_group + ' / ' + mother_group + ' / ' + grandmother_account + ' / ' + mother_account + '/' + company, merge_format)
                                        worksheet.write(row, 7, totals[grandfather_group][mother_group][grandmother_account][mother_account][company]['total'], total_format)
                                        row += 1
                                        worksheet.merge_range(row, 0, row, 6, grandfather_group + ' / ' + mother_group + ' / ' + grandmother_account + ' / ' + mother_account + '/' + company + '/' + daughter_account, merge_format)
                                        row += 1
                                        for val in vals:
                                            worksheet.write(row, 0, val['description'])
                                            worksheet.write(row, 1, val['account_id'])
                                            worksheet.write(row, 2, val['company'])
                                            worksheet.write(row, 3, val['currency_origin'])
                                            worksheet.write(row, 4, val['currency'])
                                            worksheet.write(row, 5, val['rate'])
                                            worksheet.write(row, 6, val['amount'], currency_format)
                                            row += 1

                # Save and encode file
                workbook.close()
                output.seek(0)
                file_data = output.read()
                encoded_file = base64.encodebytes(file_data)

                # Set values on model
                record.export_consolidation_data = encoded_file

    def prepare_excel_data(self):
        data = {}

        analytic_lines = self.env['account.analytic.line'].search([
            ('date', '>=', self.consolidation_period.date_from),
            ('date', '<=', self.consolidation_period.date_to)
        ])

        for analytic_line in analytic_lines:
            analytic_line.update_currency_id()

            group_key = analytic_line.account_id.group_id.parent_id.name or 'Undefined'
            mother_key = analytic_line.account_id.group_id.name or 'Undefined'
            grandmother_key = analytic_line.account_id.parent_id.parent_id.name or 'Undefined'
            mother_account_key = analytic_line.account_id.parent_id.name or 'Undefined'
            daughter_account_key = analytic_line.account_id.name or 'Undefined'
            company = analytic_line.move_id.company_id.name or 'Undefined'

            consolidation_period = self.consolidation_period.consolidation_companies.filtered(lambda x: x.company_id == analytic_line.move_id.company_id)
            currency_origin = consolidation_period.currency_id.symbol if consolidation_period else analytic_line.currency_id.symbol
            new_currency = consolidation_period.new_currency.symbol if consolidation_period else analytic_line.currency_id.symbol
            rate = consolidation_period.rate if consolidation_period and not consolidation_period.historical_rate else 1

            daughter_account = data.setdefault(group_key, {}).setdefault(mother_key, {}).setdefault(grandmother_key, {}).setdefault(mother_account_key, {}).setdefault(company, {}).setdefault(daughter_account_key, [])

            daughter_account.append({
                'account_id': analytic_line.general_account_id.code,
                'company': company,
                'currency_origin': currency_origin if currency_origin else '',
                'currency': new_currency if new_currency else '',
                'rate': rate,
                'description': analytic_line.name or '',
                'amount': analytic_line.amount * rate if not consolidation_period or not consolidation_period.historical_rate else analytic_line.amount,
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

    def get_totals(self, data):
        totals = {}

        for group_key, group_value in data.items():
            group_total = 0
            group_dict = {'total': group_total}

            for mother_key, mother_value in group_value.items():
                mother_dict = self.calculate_mother_totals(mother_value)
                group_total += mother_dict['total']
                group_dict[mother_key] = mother_dict

            group_dict['total'] = group_total
            totals[group_key] = group_dict

        return totals

    def calculate_mother_totals(self, mother_value):
        mother_total = 0
        mother_dict = {'total': mother_total}

        for grandmother_key, grandmother_value in mother_value.items():
            grandmother_dict = self.calculate_grandmother_totals(grandmother_value)
            mother_total += grandmother_dict['total']
            mother_dict[grandmother_key] = grandmother_dict

        mother_dict['total'] = mother_total
        return mother_dict

    def calculate_grandmother_totals(self, grandmother_value):
        grandmother_total = 0
        grandmother_dict = {'total': grandmother_total}

        for mother_account_key, mother_account_value in grandmother_value.items():
            mother_account_dict = self.calculate_mother_account_totals(mother_account_value)
            grandmother_total += mother_account_dict['total']
            grandmother_dict[mother_account_key] = mother_account_dict

        grandmother_dict['total'] = grandmother_total
        return grandmother_dict

    def calculate_mother_account_totals(self, mother_account_value):
        mother_account_total = 0
        mother_account_dict = {'total': mother_account_total}

        for daughter_account_key, daughter_account_value in mother_account_value.items():
            daughter_account_dict = self.calculate_daughter_account_totals(daughter_account_value)
            mother_account_total += daughter_account_dict['total']
            mother_account_dict[daughter_account_key] = daughter_account_dict

        mother_account_dict['total'] = mother_account_total
        return mother_account_dict

    def calculate_daughter_account_totals(self, daughter_account_value):
        daughter_account_total = 0
        daughter_account_dict = {'total': daughter_account_total}

        for company_key, company_value in daughter_account_value.items():
            company_total = sum(entry['amount'] for entry in company_value)
            daughter_account_total += company_total
            company_dict = {'entry': {'total': company_total}}
            daughter_account_dict[company_key] = company_dict

        daughter_account_dict['total'] = daughter_account_total
        return daughter_account_dict


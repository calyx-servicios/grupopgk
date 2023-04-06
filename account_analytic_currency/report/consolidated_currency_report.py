from odoo import models, _
import wdb

class ConsolidatedCurrencyReportXls(models.AbstractModel):
    _name = "report.account_analytic_currency.consolidated_report_xls"
    _inherit = "report.report_xlsx.abstract"
    _description= "Consolidated Currency Report XLs"
    
    def generate_xlsx_report(self, workbook, data, obj):
        sheet = workbook.add_worksheet(_('Consolidated Report'))
        bold = workbook.add_format({
            'bold': True,
            'align': 'center',
        })
        columns = [
            ('A', 50, _('Descriptions')),
            ('B', 18, _('Account Analytic')),
            ('C', 18, _('Company')),
            ('D', 18, _('Amount')),
            ('E', 18, _('Currency'))
        ]
        for col, width, label in columns:
            sheet.set_column(f'{col}:{col}', width)
            sheet.write(f'{col}1', label, bold)
        row = 2
        for record in data['vals']:
            sheet.write(f'A{row}', record.get('description', ''))
            sheet.write(f'B{row}', record.get('account_id', ''))
            sheet.write(f'C{row}', record.get('company', ''))
            sheet.write(f'D{row}', record.get('amount', 0.0))
            sheet.write(f'E{row}', record.get('currency', []))
            
            row += 1
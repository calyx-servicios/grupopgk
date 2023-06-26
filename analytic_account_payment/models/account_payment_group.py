from odoo import models, api, _
from odoo.exceptions import ValidationError


class AccountPaymentGroup(models.Model):
    _inherit = 'account.payment.group'


    def post(self):

        # Objects
        lines_with_account_required = self.move_line_ids.filtered(lambda line: line.account_id.analytic_account_required == 'required')
        sorted_lines = sorted(self.to_pay_move_line_ids, key=lambda line: (line.date, line.balance), reverse=True)

        latest_highest = None
        if sorted_lines:
            latest_highest = sorted_lines[0]

        if latest_highest and lines_with_account_required:
            move_id = latest_highest.move_id
            invoice_line_ids = move_id.invoice_line_ids
            analytic_account_ids = invoice_line_ids.mapped('analytic_account_id')

            for line in lines_with_account_required:
                lines_without_analytic = line.move_id.line_ids.filtered(lambda x: x.account_id.analytic_account_required == 'required' and not x.analytic_account_id)
                for line_without_analytic in lines_without_analytic:
                    try:
                        line_without_analytic.analytic_account_id = analytic_account_ids[0].id
                    except Exception as e:
                        raise ValidationError(_('Error when assigning the analytical account in the accounting entry.\n {}'.format(e)))

        res = super(AccountPaymentGroup, self).post()
        return res

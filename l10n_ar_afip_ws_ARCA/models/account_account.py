from odoo import api, fields, models
from collections import defaultdict
from bisect import bisect_left


class AccountAccount(models.Model):
    _inherit = "account.account"

    account_type = fields.Selection(
        selection=[
            ("asset_receivable", "Receivable"),
            ("asset_cash", "Bank and Cash"),
            ("asset_current", "Current Assets"),
            ("asset_non_current", "Non-current Assets"),
            ("asset_prepayments", "Prepayments"),
            ("asset_fixed", "Fixed Assets"),
            ("liability_payable", "Payable"),
            ("liability_credit_card", "Credit Card"),
            ("liability_current", "Current Liabilities"),
            ("liability_non_current", "Non-current Liabilities"),
            ("equity", "Equity"),
            ("equity_unaffected", "Current Year Earnings"),
            ("income", "Income"),
            ("income_other", "Other Income"),
            ("expense", "Expenses"),
            ("expense_depreciation", "Depreciation"),
            ("expense_direct_cost", "Cost of Revenue"),
            ("off_balance", "Off-Balance Sheet"),
        ],
        string="Type", tracking=True,
        required=True,
        compute='_compute_account_type', store=True, readonly=False, precompute=True, index=True,
        help="Account Type is used for information purpose, to generate country-specific legal reports, and set the rules to close a fiscal year and generate opening entries."
    )

    @api.depends('code')
    def _compute_account_type(self):
        """ Compute the account type based on the account code.
        Search for the closest parent account code and sets the account type according to the parent.
        If there is no parent (e.g. the account code is lower than any other existing account code),
        the account type will be set to 'asset_current'.
        """
        accounts_to_process = self.filtered(lambda r: r.code and not r.account_type)
        all_accounts = self.search_read(
            domain=[('company_id', 'in', accounts_to_process.company_id.ids)],
            fields=['code', 'account_type', 'company_id'],
            order='code',
        )
        accounts_with_codes = defaultdict(dict)
        # We want to group accounts by company to only search for account codes of the current company
        for account in all_accounts:
            accounts_with_codes[account['company_id'][0]][account['code']] = account['account_type']
        for account in accounts_to_process:
            codes_list = list(accounts_with_codes[account.company_id.id].keys())
            closest_index = bisect_left(codes_list, account.code) - 1
            account.account_type = accounts_with_codes[account.company_id.id][codes_list[closest_index]] if closest_index != -1 else 'asset_current'
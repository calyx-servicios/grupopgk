from odoo.addons.account_withholding.models.account_payment import (
    AccountPayment as AccountPaymentOriginal,
)


def _get_valid_liquidity_accounts(self):
    """Include the withholding account as an Odoo recordset."""
    accounts = super(
        AccountPaymentOriginal, self
    )._get_valid_liquidity_accounts()
    if self.tax_withholding_id:
        accounts |= self._get_withholding_repartition_line().account_id
    return accounts


AccountPaymentOriginal._get_valid_liquidity_accounts = (
    _get_valid_liquidity_accounts
)

import logging

from odoo import models


_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    """Defensive patch for liquidity accounts union on withholdings.

    Some inherited chains can return tuples instead of recordsets from
    `_get_valid_liquidity_accounts`. This patch normalizes the result into
    an `account.account` recordset before applying the same union logic.
    """

    _inherit = "account.payment"

    def _get_valid_liquidity_accounts(self):
        """Return liquidity accounts preserving original behavior.

        The method keeps the original logic but ensures the variable used by
        `|=` is always a recordset, avoiding type errors in mixed inheritance.
        """
        try:
            res = super()._get_valid_liquidity_accounts()
        except Exception:
            # Fallback defensivo para no cortar la creación del pago si algún
            # override en la cadena de herencia rompe el tipo de retorno.
            _logger.exception(
                "Error ejecutando super() en _get_valid_liquidity_accounts. "
                "Se usa fallback base."
            )
            
            res = (
                self.journal_id.default_account_id |
                self.payment_method_line_id.payment_account_id |
                self.journal_id.company_id.account_journal_payment_debit_account_id |
                self.journal_id.company_id.account_journal_payment_credit_account_id |
                self.journal_id.inbound_payment_method_line_ids.payment_account_id |
                self.journal_id.outbound_payment_method_line_ids.payment_account_id
            )

        if not isinstance(res, models.BaseModel):
            account_ids = []
            for item in (res or []):
                if isinstance(item, models.BaseModel):
                    account_ids.extend(item.ids)
                elif isinstance(item, int):
                    account_ids.append(item)
            res = self.env["account.account"].browse(account_ids)

        if self.tax_withholding_id:
            rep_line = self._get_withholding_repartition_line()
            if rep_line.account_id:
                res |= rep_line.account_id

        return res

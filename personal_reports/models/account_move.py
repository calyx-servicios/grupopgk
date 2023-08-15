import logging

from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_post(self):
        multiple_iva_moves = self.filtered(
            lambda move: len(
                set(
                    move.invoice_line_ids.mapped("tax_ids")
                    .filtered(lambda tax: "IVA" in tax.name)
                    .ids
                )
            )
            > 1
        )
        # ignore moves with multiple ivas
        return super(AccountMove, self - multiple_iva_moves).action_post()

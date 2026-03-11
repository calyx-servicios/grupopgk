# -*- coding: utf-8 -*-
# Copyright 2024 Grupo PGK
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.exceptions import RedirectWarning


class ResCompany(models.Model):
    _inherit = "res.company"

    def _validate_fiscalyear_lock(self, values):
        """
        Override para eliminar la validación de asientos en borrador
        tanto del módulo base como del módulo OCA account_lock_to_date.

        Se mantiene únicamente la validación de líneas de extracto bancario
        no conciliadas del módulo base.

        Validaciones ELIMINADAS:
        - Módulo base: búsqueda de draft entries con date <= fiscalyear_lock_date
        - Módulo OCA: búsqueda de draft entries con date >= fiscalyear_lock_to_date
        """
        # Validación del módulo base para fiscalyear_lock_date
        # SOLO se mantiene la validación de extractos bancarios no conciliados
        if values.get('fiscalyear_lock_date'):
            unreconciled_statement_lines = self.env['account.bank.statement.line'].search([
                ('company_id', 'in', self.ids),
                ('is_reconciled', '=', False),
                ('date', '<=', values['fiscalyear_lock_date']),
                ('move_id.state', 'in', ('draft', 'posted')),
            ])
            if unreconciled_statement_lines:
                error_msg = _(
                    "There are still unreconciled bank statement lines in the period "
                    "you want to lock. You should either reconcile or delete them."
                )
                action_error = {
                    'type': 'ir.actions.client',
                    'tag': 'bank_statement_reconciliation_view',
                    'context': {
                        'statement_line_ids': unreconciled_statement_lines.ids,
                        'company_ids': self.ids
                    },
                }
                raise RedirectWarning(
                    error_msg,
                    action_error,
                    _('Show Unreconciled Bank Statement Line')
                )

        # NOTA: Se omite intencionalmente la validación de borradores para
        # fiscalyear_lock_to_date del módulo OCA account_lock_to_date

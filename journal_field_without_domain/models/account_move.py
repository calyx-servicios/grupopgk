from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"
    
    @api.onchange('move_type')
    def _onchange_move_type_domain(self):
        for rec in self:
            if rec.move_type == 'entry':
                return {'domain': {'journal_id': []}}
            else:
                return {'domain': {'journal_id': [('id', 'in', rec.suitable_journal_ids.ids)]}}
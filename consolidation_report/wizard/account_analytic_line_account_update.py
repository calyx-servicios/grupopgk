from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountAnalyticLineAccountUpdate(models.TransientModel):
    _name = 'account.analytic.line.account.update'
    _description = 'Analytic Line Account Update'

    target_account_id_int = fields.Integer(string='Target Analytic Account ID')
    target_account_id = fields.Many2one(
        'account.analytic.account',
        string='Target Account',
        compute='_compute_target_account_id'
    )

    @api.depends('target_account_id_int')
    def _compute_target_account_id(self):
        account_obj = self.env['account.analytic.account']
        for wizard in self:
            wizard.target_account_id = account_obj.browse(wizard.target_account_id_int).exists()

    def action_confirm(self):
        self.ensure_one()
        if not self.target_account_id:
            raise UserError(
                _("There is no analytic account with ID %s.") % self.target_account_id_int
            )
        lines = self.env['account.analytic.line'].browse(self.env.context.get('active_ids', []))
        if len(lines.account_id) > 1:
            raise UserError(_("The selected lines belong to different analytic accounts."))
        lines._update_analytic_account(self.target_account_id)
        return {'type': 'ir.actions.act_window_close'}

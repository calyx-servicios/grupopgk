from odoo import models, fields, api
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    state_approve = fields.Selection(
        selection=[
            ("to_approve", "To Approve"),
            ("approved", "Approved"),
            ("none", "None"),
        ],
        string='state_approve', default='none'
    )

    user_is_partner = fields.Boolean(
        string='User is Partner',
        compute='_compute_user_is_partner',
    )

    @api.depends('partner') # Lo hago depender de aqui solo para que lo calcule cuando hacemos click en crear
    def _compute_user_is_partner(self):
        for move in self:
            user = move.env.user
            move.user_is_partner = user.is_partner
    
    def action_to_approve(self):
        self.write({'state_approve': 'to_approve'})
    

    def action_approved(self):
        self.write({'state_approve': 'approved'})
    
    def button_cancel(self):
        for move in self:
            if move.state_approve and move.state_approve == 'approved':
                if not self.env.user.is_partner:
                    raise UserError('Solo los socios pueden cancelar este movimiento que ya esta aprovado.')
                else:
                    self.write({'state_approve': 'none'})
        # Llamar a la funcionalidad original de cancelación si la condición se cumple
        return super(AccountMove, self).button_cancel()

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        if domain is None:
            domain = []
        # Obtener el ID del partner actual
        partner_id = self.env.user.id
        # Modificar el dominio para incluir la restricción adicional
        domain += [
            '|',
            ('state_approve', '!=', 'to_approve'),
            '&',
            ('state_approve', '=', 'to_approve'),
            ('partner', '=', partner_id)
        ]
        return super(AccountMove, self).search_read(domain=domain, fields=fields, offset=offset, limit=limit, order=order)
    
    def action_post(self):
        for move in self:
            # Obtener el usuario actual
            current_user = self.env.user
            # Chequear si el move_type es 'out_refund'
            selected_partner = move.partner.name
            if move.move_type == 'out_refund' and move.state_approve == 'none' and not current_user.is_partner:
                raise UserError(f"No puedes confirmar este movimiento. Primero debes pedir aprobación al socio {selected_partner}.")
            elif move.move_type == 'out_refund' and move.state_approve == 'to_approve' and not current_user.is_partner:
                raise UserError(f"No puedes confirmar este movimiento, primero debe ser aprobado por el socio {selected_partner}.")
        # Lógica original del método action_post
        super(AccountMove, self).action_post()
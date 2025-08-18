from odoo import models, fields, api, _
from .utils import cuit_alias

class ResPartnerNormalized(models.Model):
    _name = 'normalized.text'
    _description = "Normalized Text"
    _sql_constraints = [
        ('unique_res_partner_id', 'unique(res_partner_id)', 'Cada partner solo puede tener un registro normalizado.'),
        ('unique_res_company_id', 'unique(res_company_id)', 'Cada compañia solo puede tener un registro normalizado.'),
        ('unique_account_journal_id', 'unique(account_journal_id)', 'Cada diario solo puede tener un registro normalizado.')
    ]
    
    res_partner_id = fields.Many2one('res.partner', string=_('Partner'))
    res_company_id = fields.Many2one('res.company', string=_('Company'))
    account_journal_id = fields.Many2one('account.journal', string=_('Journal'))
    items_ids = fields.One2many('normalized.text.items', 'normalized_id', string="itemses")

class ResPartnerNormalizeditems(models.Model):
    _name = 'normalized.text.items'
    _description = "Normalized Text Items"
    """_sql_constraints = [
        (
            'unique_name_per_normalized',
            'unique(name, normalized_id)',
            'Cada nombre debe ser único dentro del conjunto normalizado.'
        )
    ] """

    name = fields.Char(string=_('items Name'), required=True)
    normalized_name = fields.Char(
        string='Normalized Name',
        #compute='_compute_normalized_name',
        #store=True,
        index=True,
    )
    normalized_id = fields.Many2one('normalized.text', string="Normalized Partner")
    is_real_name = fields.Boolean(string=_('It is Real Name?'))

    """ def _compute_normalized_name(self):
        for rec in self:
            rec.normalized_name = self._normalize_string(rec.name or '') """
    
    def _normalize_string(self, text):
        text = text.replace('.', '')  # Eliminar todos los puntos
        return text

    @api.model
    def create(self, vals):
        if 'name' in vals:
            new_name = self._normalize_string(vals['name'])
            vals['normalized_name'] = cuit_alias.normalize_text(new_name)
        return super().create(vals)

    def write(self, vals):
        if 'name' in vals:
            new_name = self._normalize_string(vals['name'])
            vals['normalized_name'] = cuit_alias.normalize_text(new_name)
        return super().write(vals)

from odoo import models, fields, api, _
from ..utils import cuit_alias

class ResPartnerNormalized(models.Model):
    _name = 'normalized.text'
    _description = "Normalized Text"
    _sql_constraints = [
        ('unique_res_partner_id', 'unique(res_partner_id)', _('Each partner can only have one normalized record.')),
        ('unique_res_company_id', 'unique(res_company_id)', _('Each company can only have one normalized record.')),
        ('unique_account_journal_id', 'unique(account_journal_id)', _('Each journal can only have one normalized record.'))
    ]
    
    res_partner_id = fields.Many2one('res.partner', string=_('Partner'))
    res_company_id = fields.Many2one('res.company', string=_('Company'))
    account_journal_id = fields.Many2one('account.journal', string=_('Journal'))
    items_ids = fields.One2many('normalized.text.items', 'normalized_id', string=_('Items'))

class ResPartnerNormalizeditems(models.Model):
    _name = 'normalized.text.items'
    _description = "Normalized Text Items"
    """_sql_constraints = [
        (
            'unique_name_per_normalized',
            'unique(name, normalized_id)',
            _('Each name must be unique within the normalized set.')
        )
    ] """

    name = fields.Char(string=_('Item Name'), required=True)
    normalized_name = fields.Char(
        string=_('Normalized Name'),
        #compute='_compute_normalized_name',
        #store=True,
        index=True,
    )
    normalized_id = fields.Many2one('normalized.text', string=_('Normalized Partner'))
    is_real_name = fields.Boolean(string=_('Is Real Name?'))

    """ def _compute_normalized_name(self):
        for rec in self:
            rec.normalized_name = self._normalize_string(rec.name or '') """
    
    def _normalize_string(self, text):
        text = text.replace('.', '')  # Remove all dots
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

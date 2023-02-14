from odoo import fields, models

class Partner(models.Model):
    _inherit = "res.partner"
    
    vat = fields.Char(string='VAT', index=True, 
        help="The Tax Identification Number. Complete it if the contact is subjected to government taxes. Used in some legal statements.",
        required=True, copy=False, tracking=5)


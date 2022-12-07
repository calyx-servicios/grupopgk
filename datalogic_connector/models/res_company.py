from odoo import fields, models, api, _

class resCompany(models.Model):
    _inherit = "res.company"
    
    empcod = fields.Char("Codigo")
    url_key=fields.Text("Url Privada")
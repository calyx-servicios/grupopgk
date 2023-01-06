from odoo import fields, models, api, _

class resCompany(models.Model):
    _inherit = "res.company"
    
    empcod = fields.Char("Codigo")
    url_key=fields.Text("Url Privada")

    def _localization_use_documents(self):
        """ Argentina and uruguay localization use documents """
        self.ensure_one()
        return self.account_fiscal_country_id.code == "AR" or "UY" or super()._localization_use_documents()
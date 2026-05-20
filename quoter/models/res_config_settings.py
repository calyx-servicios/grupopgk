# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    quoter_default_pricelist_id = fields.Many2one(
        comodel_name="product.pricelist",
        string="Tarifa por defecto (cotizador)",
        config_parameter="quoter.default_pricelist_id",
    )
    quoter_default_payment_term_id = fields.Many2one(
        comodel_name="account.payment.term",
        string="Plazo de pago por defecto (cotizador)",
        config_parameter="quoter.default_payment_term_id",
    )
    quoter_default_team_id = fields.Many2one(
        comodel_name="crm.team",
        string="Equipo de ventas por defecto (cotizador)",
        config_parameter="quoter.default_team_id",
    )

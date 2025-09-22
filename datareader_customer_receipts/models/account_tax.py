from odoo import models,fields, api, _
from odoo.exceptions import ValidationError


class AccountTax(models.Model):
    _inherit = "account.tax"

    _CUSTOM_IDENTIFIER_SELECTION = [
        ('IVA', 'IVA'),
        ('GANANCIAS', 'Ganancias'),
        ('SUSS', 'SUSS'),
        ('IIBB', 'IIBB'),
        ('IIBB_ARBA', 'IIBB Arba'),
        ('IIBB_CABA', 'IIBB CABA'),
        ('IIBB_BS_AS', 'IIBB Buenos Aires'),
        ('IIBB_CATAMARCA', 'IIBB Catamarca'),
        ('IIBB_CHACO', 'IIBB Chaco'),
        ('IIBB_CHUBUT', 'IIBB Chubut'),
        ('IIBB_CORDOBA', 'IIBB Córdoba'),
        ('IIBB_CORRIENTES', 'IIBB Corrientes'),
        ('IIBB_ENTRE_RIOS', 'IIBB Entre Ríos'),
        ('IIBB_FORMOSA', 'IIBB Formosa'),
        ('IIBB_JUJUY', 'IIBB Jujuy'),
        ('IIBB_LA_PAMPA', 'IIBB La Pampa'),
        ('IIBB_LA_RIOJA', 'IIBB La Rioja'),
        ('IIBB_MENDOZA', 'IIBB Mendoza'),
        ('IIBB_MISIONES', 'IIBB Misiones'),
        ('IIBB_NEUQUEN', 'IIBB Neuquén'),
        ('IIBB_RIO_NEGRO', 'IIBB Río Negro'),
        ('IIBB_SALTA', 'IIBB Salta'),
        ('IIBB_SAN_JUAN', 'IIBB San Juan'),
        ('IIBB_SAN_LUIS', 'IIBB San Luis'),
        ('IIBB_SANTA_CRUZ', 'IIBB Santa Cruz'),
        ('IIBB_SANTA_FE', 'IIBB Santa Fe'),
        ('IIBB_SANTIAGO_DEL_ESTERO', 'IIBB Santiago del Estero'),
        ('IIBB_TUCUMAN', 'IIBB Tucumán'),
        ('IIBB_TIERRA_DEL_FUEGO', 'IIBB Tierra del Fuego')
    ]
    
    datareader_custom_identifier = fields.Selection(selection=_CUSTOM_IDENTIFIER_SELECTION, string='DataReader Custom Identifier')

    @api.constrains('datareader_custom_identifier', 'company_id')
    def _check_unique_custom_identifier(self):
        for record in self:
            if record.datareader_custom_identifier and record.company_id:
                existing_records = self.env['account.tax'].search([
                    ('datareader_custom_identifier', '=', record.datareader_custom_identifier),
                    ('company_id', '=', record.company_id.id),
                    ('id', '!=', record.id)
                ])

                if existing_records:
                    raise ValidationError(_('There can be only one record with the custom identifier {} for the same company.'.format(record.datareader_custom_identifier)))

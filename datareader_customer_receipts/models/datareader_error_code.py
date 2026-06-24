from odoo import fields, models


class DatareaderErrorCode(models.Model):
    _name = 'datareader.error.code'
    _description = 'DataReader Error Code'
    _rec_name = 'code'

    code = fields.Char(string='Codigo de Error', required=True, index=True)
    description = fields.Char(string='Descripcion', required=True)
    requires_review = fields.Boolean(string='Requiere revision?', default=False)
    active = fields.Boolean(string='Activo', default=True)

    _sql_constraints = [
        ('datareader_error_code_unique', 'unique(code)', 'El codigo de error debe ser unico.'),
    ]

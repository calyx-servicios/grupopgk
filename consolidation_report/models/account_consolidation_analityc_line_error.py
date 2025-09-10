from odoo import fields, models, _

class ConsolidationAnalyticLineError(models.Model):
    _name = 'consolidation.analytic.line.error'
    _description = 'Errores en Líneas Analíticas en el Informe de Consolidación'

    line_id = fields.Many2one(
        'account.analytic.line',
        string='Línea Analítica Original',
        required=True
    )
    consolidation_id = fields.Many2one(
        'account.consolidation.report',
        string='Mes de Consolidación',
    )
    error_type = fields.Selection([
        ('sign', 'Diferencia de signo'),
        ('amount', 'Diferencia de monto'),
        ('zero', 'Línea con monto cero'),
        ('zero_dif', 'Copia de un monto cero'),
        ('no_project', 'No hay proyecto'),
        ('other', 'Otro'),
    ], string='Tipo de Error', required=True)

    amount_origin = fields.Float('Monto Original')
    amount_consolidated = fields.Float('Monto Consolidado')
    description = fields.Char('Detalle del Error')

    def open_line_analytic_form(self):
        self.ensure_one()
        line_analytic_id = self.line_id
        if line_analytic_id:
            return {
                'name': 'Line Analytic Form',
                'type': 'ir.actions.act_window',
                'res_model': 'account.analytic.line',
                'res_id': line_analytic_id.id,
                'view_mode': 'form',
            }
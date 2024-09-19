from odoo import models, fields, api, _


class HrApplicant(models.Model):
    _inherit = "hr.applicant"

    vat = fields.Char(string='CUIL')

    old_postulation = fields.Boolean(string='Postulación antigua')
    
    def create_employee_from_applicant(self):
        dict_act_window = super(HrApplicant, self).create_employee_from_applicant()
        for applicant in self:
            # Ensure partner_id and employee_data contain the new fields
            if applicant.partner_id and 'default_address_home_id' in dict_act_window.get('context', {}):
                applicant.partner_id.write({
                    'vat': applicant.vat, 
                })
                
                dict_act_window['context'].update({
                    'default_identification_id': applicant.vat,
                })
        return dict_act_window


    @api.model
    def create(self, vals):
        # Verificar si el campo 'cuil' está en los valores
        if 'vat' in vals:
            # Buscar en la base de datos si ya existe un registro con ese 'cuil'
            existing_applicant = self.with_context(active_test=False).search([('vat', '=', vals['vat'])], limit=1)
            if existing_applicant:
                # Agregar 'old_postulation' al vals
                vals['old_postulation'] = True

        # Crear el nuevo registro
        res = super(HrApplicant, self).create(vals)
        return res
    
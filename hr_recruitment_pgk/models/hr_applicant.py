from odoo import models, fields, api, _


class HrApplicant(models.Model):
    _inherit = "hr.applicant"

    vat = fields.Char(string='CUIL')
    
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
    
from odoo import fields, models, _
from odoo.exceptions import ValidationError

class HrEmployee(models.Model):
    _inherit = "hr.employee"
    
    def send_notify(self):
        self.ensure_one()
        template_id = self.env.ref('timesheet_odoo.email_template_charge_sige').id or False
        lang = self.env.context.get('lang')
        template = self.env['mail.template'].browse(template_id)
        if template.lang:
            lang = template._render_lang(self.ids)[self.id]

        period_active = self.env["period.sige"].search([("state","=","open")],limit=1)
        if period_active:
            timesheet = self.env["timesheet.sige"].search([("employee_id","=",self.id),("state","=","open"),("period_id","=",period_active.id)])
            action_id = self.env.ref("timesheet_odoo.timessheet_sige_action_window").id
            if timesheet and action_id:
                url = "/web#id=%s&action=%s&model=%s&view_type=form" % (timesheet.id, action_id, "timesheet.sige")
                ctx = {
                    'default_model': 'hr.employee',
                    'default_res_id': self.id,
                    'default_use_template': bool(template_id),
                    'default_template_id': template_id,
                    'default_composition_mode': 'comment',
                    'force_email': True,
                    'url_timesheet': url
                }
                return {
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'res_model': 'mail.compose.message',
                    'views': [(False, 'form')],
                    'view_id': False,
                    'target': 'new',
                    'context': ctx,
                }
            else:
                raise ValidationError(_("There is no timesheet for this period and employee!"))
        else:
            raise ValidationError(_("There is no active period!"))


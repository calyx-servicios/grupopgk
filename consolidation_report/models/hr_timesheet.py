from odoo import api, models, _
from odoo.exceptions import UserError
from collections import defaultdict


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    @api.model_create_multi
    def create(self, vals_list):
        default_user_id = self._default_user()
        user_ids = list(map(lambda x: x.get('user_id', default_user_id), filter(lambda x: not x.get('employee_id') and x.get('project_id'), vals_list)))

        for vals in vals_list:
            if vals.get('project_id') and not vals.get('name'):
                vals['name'] = '/'
            vals.update(self._timesheet_preprocess(vals))

        employee_domain = [('user_id', 'in', user_ids)]
        if self.env.context.get('only_active_employees', False):
            employee_domain.append(('active', '=', True))

        employees = self.env['hr.employee'].sudo().search(employee_domain)
        employee_for_user_company = defaultdict(dict)
        for employee in employees:
            employee_for_user_company[employee.user_id.id][employee.company_id.id] = employee.id

        employee_ids = set()
        for vals in vals_list:
            if not vals.get('employee_id') and vals.get('project_id'):
                employee_for_company = employee_for_user_company.get(vals.get('user_id', default_user_id), False)
                if not employee_for_company:
                    continue
                company_id = list(employee_for_company)[0] if len(employee_for_company) == 1 else self.env.company.id
                vals['employee_id'] = employee_for_company.get(company_id, False)
            elif vals.get('employee_id'):
                employee_ids.add(vals['employee_id'])

        if not self.env.context.get('only_active_employees', False):
            if any(not emp.active for emp in self.env['hr.employee'].browse(list(employee_ids))):
                raise UserError(_('Timesheets must be created with an active employee.'))

        lines = super(AccountAnalyticLine, self).create(vals_list)
        for line, values in zip(lines, vals_list):
            if line.project_id:
                line._timesheet_postprocess(values)
        return lines
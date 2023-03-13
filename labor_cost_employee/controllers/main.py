from odoo import http
from odoo.http import request

class CalculateLaborCost(http.Controller):
    
    @http.route('/get_action_labor', auth="user", type='json')
    def get_action_labor(self, **kw):
        action = request.env.ref('labor_cost_employee.action_labor_cost_employee_wizard').read()[0]
        return action


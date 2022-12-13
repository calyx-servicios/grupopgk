from odoo import api, fields, models, _
from datetime import datetime

class SaleOrder(models.Model):
    _inherit = "sale.order"

    project_ids = fields.Many2many('project.project', compute="_compute_project_ids", string='Projects', copy=False, groups="project.group_project_manager", help="Projects used in this sales order.")

    def action_confirm(self):
        for rec in self:
            if not rec.project_id:
                for line in rec.order_line:
                    if len(self.company_id) == 1:
                        line._create_project_for_each(line, rec.company_id)
                    else:
                        line._create_project_for_each(line, line.line.company_id)
                    line._set_next_number()
        return super(SaleOrder, self).action_confirm()

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.model_create_multi
    def create(self, values):
        res = super(SaleOrderLine, self).create(values)
        for line in res:
            if line.state == 'sale' and line.is_service:
                if len(self.company_id) == 1:
                    self._create_project_for_each(line, res.company_id)
                else:
                    self._create_project_for_each(line, line.company_id)
                line._set_next_number()
        return res

    def _create_project_for_each(self, line, id_company):
        try:
            if line.product_id.service_tracking == 'task_in_project' and line.is_service:
                if not line.project_id:
                    project = line.sudo().with_company(id_company)._timesheet_create_project()
                    project.write(
                        {
                        'name': line._get_sequence_name(project.partner_id.id),
                        }
                    )
                    if not line.task_id:
                        line.sudo().with_company(id_company)._timesheet_create_task(project)
            elif line.product_id.service_tracking == 'project_only' and line.is_service:
                if not line.project_id:
                    project = line.sudo().with_company(id_company)._timesheet_create_project()
        except Exception as e:
            raise Exception(_('Failed to create project (ERROR: {})').format(e))

    def _get_sequence_name(self, id_partner):
        seq_obj = self.env.ref('project_for_each_sol.seq_project')
        seq_name = '{}-{}-{}'.format(datetime.now().year, id_partner, seq_obj.get_next_char(seq_obj.number_next))
        return seq_name

    def _set_next_number(self):
        seq_obj = self.env.ref('project_for_each_sol.seq_project')
        seq_obj.number_next_actual += seq_obj.number_increment
        seq_obj._set_number_next_actual()
from odoo import api, fields, models, _

class SaleOrder(models.Model):
    _inherit = "sale.order"

    project_ids = fields.Many2many('project.project', compute="_compute_project_ids", string='Projects', copy=False, groups="project.group_project_manager", help="Projects used in this sales order.")

    def action_confirm(self):
        for rec in self:
            for line in rec.order_line:
                line._create_project_for_each()
        return super(SaleOrder, self).action_confirm()

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.model_create_multi
    def create(self, values):
        res = super(SaleOrderLine, self).create(values)
        for line in res:
            if line.state == 'sale' and line.is_service:
                line._create_project_for_each()
        return res

    def _create_project_for_each(line):
        try:
            if line.product_id.service_tracking == 'task_in_project' and line.is_service:
                if not line.project_id:
                    project = line._timesheet_create_project() 
                    if not line.task_id:
                        line._timesheet_create_task(project)
            elif line.product_id.service_tracking == 'project_only' and line.is_service:
                if not line.project_id:
                    project = line._timesheet_create_project()
        except Exception as e:
            raise Exception(_('Failed to create project (ERROR: {})').format(e))
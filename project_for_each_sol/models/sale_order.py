from odoo import api, fields, models, _
from datetime import datetime

class SaleOrder(models.Model):
    _inherit = "sale.order"

    project_ids = fields.Many2many('project.project', compute="_compute_project_ids", string='Projects', copy=False, groups="project.group_project_manager", help="Projects used in this sales order.")

    @api.onchange('project_id')
    def _onchange_project_id(self):
        for record in self:
            for line in record.order_line:
                line.project_name = record.project_id.display_name
                line.analytic_account_id = record.project_id.analytic_account_id
    
    def action_confirm(self):
        for rec in self:
            if not rec.project_id:
                for line in rec.order_line:
                    if len(rec.company_id) == 1:
                        line.with_company(rec.company_id)._create_project_for_each(line)
                    else:
                        line.with_company(line.company_id)._create_project_for_each(line)
                    line.sudo()._set_next_number()
        return super(SaleOrder, self).action_confirm()

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"


    project_name = fields.Char(string='Project name')
    is_project = fields.Boolean('is project?', default=False, compute='_compute_is_project')

    @api.onchange('product_id')
    def _onchange_product_id_values(self):
        for rec in self:
            if rec.order_id.project_id:
                rec.project_name = rec.order_id.project_id.display_name
                rec.analytic_account_id = rec.order_id.project_id.analytic_account_id.id

    @api.depends('product_id')
    def _compute_is_project(self):
        for rec in self:
            if rec.product_id.detailed_type == 'service' and rec.product_id.service_tracking in ['project_only', 'task_in_project']:
                rec.is_project = True
            else:
                rec.is_project = False

    @api.model_create_multi
    def create(self, values):
        res = super(SaleOrderLine, self).create(values)
        for line in res:
            if line.state == 'sale' and line.is_service:
                if len(line.order_id.company_id) == 1:
                    self.with_company(line.order_id.company_id)._create_project_for_each(line)
                else:
                    self.with_company(line.company_id)._create_project_for_each(line)
                line.sudo()._set_next_number()
        return res

    def analytic_values(self): 
        if len(self.analytic_account_id.company_id) > 1:
            company_val = [(6, 0, self.analytic_account_id.company_id.ids)]         
        else:
            company_val = self.analytic_account_id.company_id.id
        return {
            'name': '{}'.format(self._get_sequence_name()),
            'code': self.order_id.client_order_ref,
            'company_id': company_val,
            'partner_id': self.order_id.partner_id.id,
            'parent_id': self.analytic_account_id.id,
            'group_id': self.analytic_account_id.group_id.id,
        }

    def _project_values(self):
        account = None
        if not account:
            acc_vals = self.analytic_values()
            account = self.env['account.analytic.account'].create(acc_vals)

        return {
            'name': self._get_sequence_name(),
            'analytic_account_id': account.id,
            'partner_id': self.order_id.partner_id.id,
            'sale_line_id': self.id,
            'active': True,
            'company_id': self.env.company.id,
        }

    def create_project(self):
        vals = self._project_values()
        if self.product_id.service_policy == 'delivered_timesheet':
            vals['allow_billable'] = True
        if self.product_id.project_template_id:
            vals['name'] = "%s - %s" % (vals['name'], self.product_id.project_template_id.name)
            project = self.product_id.project_template_id.copy(vals)
            project.tasks.write({
                'sale_line_id': self.id,
                'partner_id': self.order_id.partner_id.id,
                'email_from': self.order_id.partner_id.email,
            })
            project.tasks.filtered(lambda task: task.parent_id != False).write({
                'sale_line_id': self.id,
                'sale_order_id': self.order_id,
            })
        else:
            project = self.env['project.project'].create(vals)

        self.write({
            'project_id': project.id,
        })
        return project

    def _prepare_task_values(self, project):
        planned_hours = self._convert_qty_company_hours(self.company_id)
        sale_line_name_parts = self.name.split('\n')
        title = sale_line_name_parts[0] or self.product_id.name
        description = '<br/>'.join(sale_line_name_parts[1:])
        values = {
            'name': title if project.sale_line_id else '%s: %s' % (self.order_id.name or '', title),
            'planned_hours': planned_hours,
            'partner_id': self.order_id.partner_id.id,
            'email_from': self.order_id.partner_id.email,
            'description': description,
            'project_id': project.id,
            'sale_line_id': self.id,
            'sale_order_id': self.order_id.id,
            'company_id': project.company_id.id,
            'analytic_account_id': project.analytic_account_id.id,
            'user_ids': False,
        }
        return values

    def _create_task(self, project):
        values = self._prepare_task_values(project)
        task = self.env['project.task'].create(values)
        self.write({
            'task_id': task.id,
        })
        return task

    def _create_project_for_each(self, line):
        try:
            project = None
            if line.product_id.service_tracking == 'task_in_project' and line.is_service:
                if not line.order_id.project_id:
                    project = line.create_project()
                    if project.analytic_account_id:
                        self.analytic_account_id = project.analytic_account_id.id
                    if not line.task_id:
                        line._create_task(project)
            elif line.product_id.service_tracking == 'project_only' and line.is_service:
                if not line.order_id.project_id:
                    project = line.create_project()
                    if project.analytic_account_id:
                        self.analytic_account_id = project.analytic_account_id.id

        except Exception as e:
            raise Exception(_('Failed to create project (ERROR: {})').format(e))

    def _prepare_sequence_name(self, obj):
        name = '{}-{}-{} | {} - {}'.format(datetime.now().year, self.order_id.partner_id.id, obj.get_next_char(obj.number_next), self.project_name, self.order_id.partner_id.name)
        return name

    def _get_sequence_name(self):
        seq_obj = self.env.ref('project_for_each_sol.seq_project')
        return self._prepare_sequence_name(seq_obj)

    def _set_next_number(self):
        seq_obj = self.env.ref('project_for_each_sol.seq_project')
        seq_obj.number_next_actual += seq_obj.number_increment
        seq_obj._set_number_next_actual()
from odoo import models, api, fields, _
from odoo.exceptions import UserError
from datetime import datetime


class MergeProjectWizard(models.TransientModel):
    _name = 'merge.project.wizard'
    _description = 'Merge Projects Wizard'

    # Fields
    projects_ids = fields.Many2many('project.project', string='Projects')
    partner_id = fields.Many2one('res.partner', string='Customer')
    partner = fields.Many2one('res.users', string='Partner')
    company_id = fields.Many2one('res.company', string='Company')
    is_same_partner = fields.Boolean(compute='_compute_is_same_partner', string='Are they from the same customer?')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Account Analytic Mother')
    project_name = fields.Char(string='Project name')
    new_project_name = fields.Char(compute='_compute_new_project_name', string='New name for project')

    # Compute Fields
    @api.depends('project_name', 'partner_id')
    def _compute_new_project_name(self):
        self.new_project_name = self._get_sequence_name()

    @api.depends('projects_ids')
    def _compute_is_same_partner(self):
        customers = self.projects_ids.mapped('partner_id')
        if len(customers) == 1:
            self.partner_id = customers[0].id
            self.is_same_partner = True
        else:
            mother_contacts =  self.get_parent_contact(customers)
            if len(mother_contacts) == 1:
                self.partner_id = mother_contacts[0].id
                self.is_same_partner = True
            else:   
                self.is_same_partner = False

    def get_parent_contact(self, contacts):
        mother_contacts = self.env['res.partner']
        for contact in contacts:
            if not contact.parent_id:
                if not contact.id in mother_contacts.ids:
                    mother_contacts += contact
            else:
                if not contact.parent_id.id in mother_contacts.ids:
                    mother_contacts += contact.parent_id
        return mother_contacts

    # Button Action Wizard
    def merge(self):
        """Create the destination project and migrate historical records."""
        if not self.is_same_partner:
            raise UserError(_('You cannot merge projects for different clients or parent contacts'))

        try:
            new_project = self.create_project()
            self._set_next_number()

            for project in self.projects_ids:
                try:
                    self.update_project_references(project, new_project)
                    project.write({'active': False})
                except Exception as e:
                    raise UserError(_('Error on merge values: {}'.format(e)))
        except Exception as e:
            raise UserError(_('Error: {}'.format(e)))

    def update_project_references(self, old_project, new_project):
        """Move the historical records used by project KPIs to the new project."""
        self._reassign_sale_lines(old_project, new_project)
        self._reassign_tasks(old_project, new_project)
        self._reassign_analytic_lines(old_project, new_project)
        self._reassign_move_lines(old_project, new_project)

    def _reassign_sale_lines(self, old_project, new_project):
        """Move sale order lines that point to the source project."""
        sale_lines = old_project.sale_line_id.sudo()
        if sale_lines:
            sale_lines.write({'project_id': new_project.id})

    def _reassign_tasks(self, old_project, new_project):
        """Move tasks and align them with the destination analytic account."""
        tasks = old_project.task_ids.sudo()
        if tasks:
            tasks.write({
                'project_id': new_project.id,
                'analytic_account_id': new_project.analytic_account_id.id,
            })

    def _reassign_analytic_lines(self, old_project, new_project):
        """Move analytic lines and their project link when the model supports it."""
        analytic_lines = old_project.analytic_account_id.line_ids.sudo()
        if not analytic_lines:
            return

        for analytic_line in analytic_lines:
            vals = {'account_id': new_project.analytic_account_id.id}
            if (
                'project_id' in analytic_line._fields
                and analytic_line.project_id.id == old_project.id
            ):
                vals['project_id'] = new_project.id
            analytic_line.write(vals)

    def _reassign_move_lines(self, old_project, new_project):
        """Move posted and draft invoice lines to keep billing KPIs consolidated."""
        if not old_project.analytic_account_id:
            return

        move_lines = self.env['account.move.line'].sudo().search([
            ('analytic_account_id', '=', old_project.analytic_account_id.id),
        ])
        if move_lines:
            move_lines.with_context(check_move_validity=False).write({
                'analytic_account_id': new_project.analytic_account_id.id,
            })

    # Wizard
    def merge_projects(self, window_title, ids):
        wiz = self.create({
            'projects_ids': ids,
        })
        return wiz.open_wizard(window_title)

    def open_wizard(self, title):
        view = self.env.ref('merge_projects.merge_project_wizard_form')
        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': self._name,
            'target': 'new',
            'view_id': view.id,
            'view_mode': 'form',
            'res_id': self.id,
            'context': self.env.context,
        }

    # Create Project
    def create_project(self):
        vals = self._project_values()
        project = self.env['project.project'].sudo().create(vals)
        return project

    # Prepare values for creation
    def analytic_values(self):
        if len(self.analytic_account_id.company_id) > 1:
            company_val = [(6, 0, self.analytic_account_id.company_id.ids)]
        else:
            company_val = self.analytic_account_id.company_id.id
        return {
            'name': '{}'.format(self._get_sequence_name()),
            'company_id': company_val,
            'partner_id': self.partner_id.id,
            'parent_id': self.analytic_account_id.id,
            'group_id': self.analytic_account_id.group_id.id,
        }

    def _project_values(self):
        project_fields = self.env['project.project']._fields

        # Creation of Project with Values
        account = None
        if not account:
            acc_vals = self.analytic_values()
            account = self.env['account.analytic.account'].create(acc_vals)
        vals = {
            'name': self.new_project_name,
            'partner': self.partner.id,
            'analytic_account_id': account.id,
            'partner_id': self.partner_id.id,
            'active': True,
            'company_id': self.company_id.id,
        }
        if 'allow_billable' in project_fields:
            vals['allow_billable'] = True

        # Sum all numeric fields (Float, Integer, Monetary) from merged projects
        numeric_fields = []
        if self.projects_ids:
            project_fields = self.projects_ids[0]._fields
            for field_name, field in project_fields.items():
                # Get Float, Integer, and Monetary fields that are not computed
                if field.type in ('integer', 'float', 'monetary') and not field.compute:
                    numeric_fields.append(field_name)

        # Sum numeric fields from all projects
        for project in self.projects_ids:
            for field_name in numeric_fields:
                if hasattr(project, field_name):
                    value = project[field_name]
                    # Only sum if value is truthy (not 0, False, or None)
                    if value:
                        if field_name in vals:
                            vals[field_name] += value
                        else:
                            vals[field_name] = value

        return vals

    # Sequence
    def _prepare_sequence_name(self, obj):
        name = '{}-{}-{} | {} - {}'.format(datetime.now().year, self.partner_id.id, obj.get_next_char(obj.number_next), self.project_name, self.partner_id.name)
        return name

    def _get_sequence_name(self):
        seq_obj = self.env.ref('project_for_each_sol.seq_project')
        return self._prepare_sequence_name(seq_obj)

    def _set_next_number(self):
        seq_obj = self.env.ref('project_for_each_sol.seq_project')
        seq_obj.number_next_actual += seq_obj.number_increment
        seq_obj._set_number_next_actual()

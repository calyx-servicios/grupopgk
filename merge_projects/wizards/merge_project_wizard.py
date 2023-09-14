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
        # Change on SOL project related
        for sale_line in old_project.sale_line_id:
            sale_line.sudo().write({
                'project_id': new_project.id,
            })

        # Change on task project info and acc
        for task in old_project.task_ids:
            task.sudo().write({
                'project_id': new_project.id,
                'analytic_account_id': self.analytic_account_id.id,
            })

        #  Change for lines
        for analytic_lines in old_project.analytic_account_id.line_ids:
            analytic_lines.sudo().write({
                'account_id': new_project.analytic_account_id.id
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

        # Creation of Project with Values
        account = None
        if not account:
            acc_vals = self.analytic_values()
            account = self.env['account.analytic.account'].create(acc_vals)
        return {
            'name': self.new_project_name,
            'partner': self.partner.id,
            'analytic_account_id': account.id,
            'partner_id': self.partner_id.id,
            'active': True,
            'company_id': self.company_id.id,
            'allow_billable': True
        }

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

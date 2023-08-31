from odoo import models, _


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def merge_project_action(self):
        merge_project_obj = self.env['merge.project.wizard']

        return merge_project_obj.merge_projects(_('Merge Projects'), self.ids)

# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ProjectProject(models.Model):
    _inherit = 'project.project'

    contrated_hours = fields.Float(
        string='Contrated Hours',
        readonly=True
    )
    total_project_amount = fields.Monetary(
        string='Total Project Amount',
        readonly=True
    )

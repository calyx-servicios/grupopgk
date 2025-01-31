# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ProjectProject(models.Model):
    _inherit = 'project.project'

    contrated_hours = fields.Float('Contrated Hours', readonly=True)
    total_project_amount = fields.Monetary('Total Project Amount', readonly=True)

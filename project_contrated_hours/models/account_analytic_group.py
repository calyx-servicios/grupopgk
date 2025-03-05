# -*- coding: utf-8 -*-
from odoo import models, fields


class AccountAnalyticGroup(models.Model):
    _inherit = 'account.analytic.group'

    visible_fields_project = fields.Boolean(
        string="Make visible fields in project?",
        default=False
    )

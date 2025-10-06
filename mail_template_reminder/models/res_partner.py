# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    reminder_email = fields.Char(
        string=_('Reminder Email'),
        help=_('Email address to use specifically for overdue invoice reminders. If not set, the main email will be used.')
    )
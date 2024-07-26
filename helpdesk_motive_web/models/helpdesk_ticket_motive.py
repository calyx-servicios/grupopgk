from odoo import fields, models


class HelpdeskMotive(models.Model):
    _inherit = "helpdesk.ticket.motive"

    line_ids = fields.One2many('helpdesk.ticket.motive.line', 'motive_id', string="Lines")


class HepdeskMotiveLine(models.Model):
    _name = "helpdesk.ticket.motive.line"
    _description = "Helpdesk Motive Lines"
    
    description = fields.Char(string="Descripcion", store=True)
    required_field = fields.Boolean(string="Mostrar en portal", store=True)
    motive_id = fields.Many2one('helpdesk.ticket.motive', string="Motive", ondelete='cascade')
    team_id = fields.Many2one('helpdesk.ticket.team', related="motive_id.team_id", readonly=True)

from odoo import api, fields, models
from lxml import etree


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    user_id_domain = fields.Binary(compute='_compute_hr_field_domains')
    partner_ids_domain = fields.Binary(compute='_compute_hr_field_domains')

    @api.depends('user_id')
    @api.depends_context('uid')
    def _compute_hr_field_domains(self):
        user = self.env.user
        restricted = not user.has_group('hr.group_hr_manager')
        for record in self:
            record.user_id_domain = (
                [('id', '=', user.id)] if restricted else []
            )
            record.partner_ids_domain = (
                [('type', '!=', 'private'), ('id', '=', user.partner_id.id)]
                if restricted
                else [('type', '!=', 'private')]
            )

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        result = super().fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu,
        )
        user = self.env.user
        if (
            view_type == 'calendar'
            and user.has_group('hr.group_hr_user')
            and not user.has_group('hr.group_hr_manager')
        ):
            doc = etree.fromstring(result['arch'])
            for node in doc.xpath("//field[@name='partner_ids'][@filters='1']"):
                node.getparent().remove(node)
            result['arch'] = etree.tostring(doc, encoding='unicode')
        return result

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        user = self.env.user

        if not user.has_group('hr.group_hr_manager'):
            args = args + [('user_id', '=', user.id)]

        return super().search(args, offset=offset, limit=limit, order=order, count=count)

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        user = self.env.user

        if not user.has_group('hr.group_hr_manager'):
            domain = domain + [('user_id', '=', user.id)]

        return super().read_group(
            domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy,
        )

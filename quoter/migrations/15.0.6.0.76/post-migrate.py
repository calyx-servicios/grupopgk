# pylint: disable=missing-module-docstring
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = env['sale.order.line'].search([('quoter_is_adjustment_line', '=', True), ('quoter_adjustment_parent_line_id', '!=', False)])
    for line in lines:
        parent = line.quoter_adjustment_parent_line_id
        if line.sequence <= parent.sequence:
            line.sequence = parent.sequence + 1

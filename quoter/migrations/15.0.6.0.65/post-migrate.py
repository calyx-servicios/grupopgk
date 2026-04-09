# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Quita dominios que referencian is_quoter_pricelist (campo eliminado del modelo)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    for act in env["ir.actions.act_window"].search(
        [("domain", "ilike", "is_quoter_pricelist")]
    ):
        act.write({"domain": "[]"})
    for filt in env["ir.filters"].search(
        [("domain", "ilike", "is_quoter_pricelist")]
    ):
        filt.write({"domain": "[]"})

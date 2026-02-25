# -*- coding: utf-8 -*-
from odoo import api, models


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model_create_multi
    def create(self, vals_list):
        """Si se crea partner dentro del flujo (ej. sin partner_id), que lleve contexto."""
        return super(
            ResUsers, self.with_context(partner_identification_required_skip=True)
        ).create(vals_list)

    def copy(self, default=None):
        """Al duplicar usuario, duplicar el contacto con contexto para no exigir VAT."""
        default = dict(default or {})
        if "partner_id" not in default and self.partner_id:
            new_partner = self.partner_id.with_context(
                partner_identification_required_skip=True
            ).copy()
            default["partner_id"] = new_partner.id
        return super().copy(default)

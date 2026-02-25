# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Tipos que permiten contacto sin número (ej: consumidor final sin identificar)
    IDENTIFICATION_TYPES_ALLOWING_EMPTY = ("Sigd", "Unknown", "Otros")

    @api.constrains("vat", "l10n_latam_identification_type_id")
    def _check_identification_number_required(self):
        for partner in self:
            if partner.user_ids:
                continue
            if self.env.context.get("partner_identification_required_skip"):
                continue
            id_type = partner.l10n_latam_identification_type_id
            if not id_type:
                continue
            if id_type.name in self.IDENTIFICATION_TYPES_ALLOWING_EMPTY:
                continue
            vat = (partner.vat or "").strip()
            if not vat:
                raise ValidationError(
                    _(
                        "Debe ingresar el número de identificación cuando "
                        "el tipo de documento es '%s'."
                    )
                    % id_type.name
                )

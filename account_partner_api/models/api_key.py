# -*- coding: utf-8 -*-
import hashlib
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ApiKey(models.Model):
    """
    Internal API Key management model.

    Stores hashed API keys used to authenticate external services.
    The plain text key is never persisted; only its SHA-256 hash is kept.
    """

    _name = "api.key"
    _description = "API Key"
    _order = "created_at desc"

    client_name = fields.Char(
        string="Nombre del cliente",
        required=True,
        help="Nombre del sistema o servicio consumidor de la API.",
    )
    key_hash = fields.Char(
        string="Hash de la clave",
        readonly=True,
        copy=False,
        help=(
            "SHA-256 del valor de la API Key. "
            "La clave en texto plano nunca se almacena."
        ),
    )
    key_plain = fields.Char(
        string="Clave API (ingresar para establecer)",
        compute="_compute_key_plain",
        inverse="_inverse_key_plain",
        store=False,
        copy=False,
        help=(
            "Ingrese aquí la clave deseada y guarde el registro. "
            "El valor se hasheará automáticamente y no se mostrará "
            "al reabrir el formulario."
        ),
    )
    is_active = fields.Boolean(
        string="Activa",
        default=True,
        help="Desactivar para revocar el acceso sin eliminar el registro.",
    )
    created_at = fields.Datetime(
        string="Creada el",
        default=fields.Datetime.now,
        readonly=True,
    )
    last_used_at = fields.Datetime(
        string="Último uso",
        readonly=True,
    )

    def _compute_key_plain(self):
        """
        Never expose the stored hash as plain text.

        The field is always empty when read so the hash
        is never accidentally revealed through the UI.
        """
        for rec in self:
            rec.key_plain = False

    def _inverse_key_plain(self):
        """
        Hash the plain text key and persist the digest.

        Called automatically by Odoo when a value is written
        to ``key_plain``. Empty values are ignored so an accidental
        blank save does not overwrite an existing valid hash.
        """
        for rec in self:
            if rec.key_plain:
                rec.key_hash = hashlib.sha256(
                    rec.key_plain.encode("utf-8")
                ).hexdigest()

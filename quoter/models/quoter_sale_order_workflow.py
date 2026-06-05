# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

QUOTER_WORKFLOW_STATE_SELECTION = [
    ("en_preparacion", "En preparación"),
    ("en_aprobacion", "En aprobación"),
    ("aprobado_interno", "Aprobado interno"),
    ("enviado_cliente", "Enviado cliente"),
    ("aprobado_cliente", "Aprobado cliente"),
    ("rechazado_cliente", "Rechazado cliente"),
]

QUOTER_WORKFLOW_TRANSITION_FIELDS = frozenset(
    {
        "quoter_workflow_state",
        "quoter_rejection_reason",
        "message_follower_ids",
        "access_token",
    }
)

QUOTER_WORKFLOW_APROBADOR_BLOCK_FIELDS = frozenset(
    {
        "global_discount_amount",
        "global_surcharge_amount",
    }
)


class SaleOrderQuoterWorkflow(models.Model):
    _inherit = "sale.order"

    quoter_workflow_state = fields.Selection(
        selection=QUOTER_WORKFLOW_STATE_SELECTION,
        string="Estado cotización",
        default="en_preparacion",
        copy=False,
        tracking=True,
        help="Flujo interno de aprobación de la cotización profesional.",
    )
    quoter_rejection_reason = fields.Text(
        string="Motivo de rechazo",
        copy=False,
        tracking=True,
        help="Obligatorio al rechazar la cotización; la cotización vuelve a En preparación.",
    )
    quoter_workflow_can_edit_content = fields.Boolean(
        compute="_compute_quoter_workflow_permissions",
    )
    quoter_workflow_can_edit_adjustments = fields.Boolean(
        compute="_compute_quoter_workflow_permissions",
    )
    quoter_workflow_can_transition = fields.Boolean(
        compute="_compute_quoter_workflow_permissions",
    )
    quoter_user_is_cotizador_profile = fields.Boolean(
        compute="_compute_quoter_workflow_permissions",
    )
    quoter_user_is_aprobador_profile = fields.Boolean(
        compute="_compute_quoter_workflow_permissions",
    )
    quoter_user_is_contratos_profile = fields.Boolean(
        compute="_compute_quoter_workflow_permissions",
    )

    @api.model
    def _quoter_workflow_state_label(self, state):
        return dict(QUOTER_WORKFLOW_STATE_SELECTION).get(state, state or "")

    def _quoter_workflow_is_admin(self):
        return self.env.user.has_group("base.group_system")

    def _quoter_workflow_has_group(self, xml_id):
        return self.env.user.has_group(xml_id)

    def _quoter_user_is_cotizador_profile(self):
        user = self.env.user
        if user.has_group("base.group_system"):
            return True
        if user.has_group("quoter.group_quoter_cotizador"):
            return True
        return bool(
            user.has_group("quoter.group_quoter_manager")
            or user.has_group("quoter.group_quoter_director")
            or user.has_group("quoter.group_quoter_partner")
        )

    def _quoter_user_is_aprobador_profile(self):
        user = self.env.user
        if user.has_group("base.group_system"):
            return True
        return user.has_group("quoter.group_quoter_aprobador")

    def _quoter_user_is_contratos_profile(self):
        user = self.env.user
        if user.has_group("base.group_system"):
            return True
        return user.has_group("quoter.group_quoter_contratos")

    @api.depends(
        "is_quotation",
        "quoter_workflow_state",
        "quoter_manager_id",
        "quoter_partner_id",
    )
    def _compute_quoter_workflow_permissions(self):
        for order in self:
            if not order.is_quotation:
                order.quoter_workflow_can_edit_content = True
                order.quoter_workflow_can_edit_adjustments = True
                order.quoter_workflow_can_transition = True
                order.quoter_user_is_cotizador_profile = False
                order.quoter_user_is_aprobador_profile = False
                order.quoter_user_is_contratos_profile = False
                continue
            is_cotizador = order._quoter_user_is_cotizador_profile()
            is_aprobador = order._quoter_user_is_aprobador_profile()
            is_contratos = order._quoter_user_is_contratos_profile()
            state = order.quoter_workflow_state or "en_preparacion"
            order.quoter_user_is_cotizador_profile = is_cotizador
            order.quoter_user_is_aprobador_profile = is_aprobador
            order.quoter_user_is_contratos_profile = is_contratos
            order.quoter_workflow_can_edit_content = bool(
                is_cotizador and state == "en_preparacion"
            )
            order.quoter_workflow_can_edit_adjustments = bool(
                is_aprobador and state in ("en_aprobacion", "aprobado_interno")
            )
            order.quoter_workflow_can_transition = bool(
                is_cotizador or is_aprobador or is_contratos
            )

    def _quoter_workflow_only_transition_vals(self, vals):
        return set(vals.keys()).issubset(QUOTER_WORKFLOW_TRANSITION_FIELDS)

    def _quoter_workflow_only_adjustment_vals(self, vals):
        allowed_top = {
            "quoter_area_block_ids",
            "message_follower_ids",
            "access_token",
        }
        keys = set(vals.keys())
        if not keys.issubset(allowed_top):
            return False
        if "quoter_area_block_ids" not in vals:
            return True
        return self._quoter_workflow_block_commands_only_adjustments(
            vals["quoter_area_block_ids"]
        )

    @api.model
    def _quoter_workflow_block_commands_only_adjustments(self, commands):
        if not commands:
            return True
        for cmd in commands:
            if not isinstance(cmd, (list, tuple)) or len(cmd) < 1:
                continue
            op = cmd[0]
            if op == 0:
                values = cmd[2] if len(cmd) > 2 else {}
                if set(values.keys()) - QUOTER_WORKFLOW_APROBADOR_BLOCK_FIELDS:
                    return False
            elif op == 1:
                values = cmd[2] if len(cmd) > 2 else {}
                if set(values.keys()) - QUOTER_WORKFLOW_APROBADOR_BLOCK_FIELDS:
                    return False
            elif op in (2, 3, 4, 5, 6):
                return False
        return True

    def _quoter_validate_workflow_write_access(self, vals):
        self.ensure_one()
        if not self.is_quotation or not isinstance(self.id, int):
            return
        if self._quoter_workflow_is_admin():
            return
        if self.env.context.get("quoter_workflow_transition"):
            if not self._quoter_workflow_only_transition_vals(vals):
                raise AccessError(
                    _("Solo puede cambiar el estado de la cotización en esta acción.")
                )
            return
        state = self.quoter_workflow_state or "en_preparacion"
        if self._quoter_user_is_contratos_profile() and not self._quoter_user_is_cotizador_profile() and not self._quoter_user_is_aprobador_profile():
            raise AccessError(
                _("El perfil Contratos solo puede cambiar el estado de la cotización mediante los botones de acción.")
            )
        if self._quoter_workflow_can_edit_content():
            return
        if (
            state in ("en_aprobacion", "aprobado_interno")
            and self._quoter_user_is_aprobador_profile()
            and self._quoter_workflow_only_adjustment_vals(vals)
        ):
            return
        raise AccessError(
            _(
                "No puede modificar esta cotización en el estado «%s» con su perfil actual."
            )
            % self._quoter_workflow_state_label(state)
        )

    def _quoter_workflow_can_edit_content(self):
        self.ensure_one()
        return self.quoter_workflow_can_edit_content

    def _quoter_workflow_transition(self, new_state, rejection_reason=None, chatter_body=None):
        self.ensure_one()
        if not self.is_quotation:
            raise UserError(_("Esta acción solo aplica a cotizaciones profesionales."))
        vals = {"quoter_workflow_state": new_state}
        if rejection_reason is not None:
            vals["quoter_rejection_reason"] = rejection_reason
        old_state = self.quoter_workflow_state
        self.with_context(quoter_workflow_transition=True).write(vals)
        body_parts = [
            _(
                "Estado de cotización: %(old)s → %(new)s"
            )
            % {
                "old": self._quoter_workflow_state_label(old_state),
                "new": self._quoter_workflow_state_label(new_state),
            }
        ]
        if rejection_reason:
            body_parts.append(
                _("<b>Motivo:</b> %s") % (rejection_reason or "").strip()
            )
        if chatter_body:
            body_parts.append(chatter_body)
        self._quoter_message_post("<br/>".join(body_parts))

    def action_quoter_submit_for_approval(self):
        for order in self:
            if order.quoter_workflow_state != "en_preparacion":
                raise UserError(_("Solo puede enviar a aprobación desde En preparación."))
            if not order._quoter_user_is_cotizador_profile():
                raise AccessError(_("Solo el perfil Cotizador puede enviar a aprobación."))
            order._quoter_workflow_transition("en_aprobacion")
        return True

    def action_quoter_internal_approve(self):
        for order in self:
            if order.quoter_workflow_state != "en_aprobacion":
                raise UserError(_("Solo puede aprobar internamente desde En aprobación."))
            if not order._quoter_user_is_aprobador_profile():
                raise AccessError(_("Solo el perfil Aprobador puede aprobar internamente."))
            order._quoter_workflow_transition("aprobado_interno")
        return True

    def action_quoter_send_to_client(self):
        for order in self:
            if order.quoter_workflow_state != "aprobado_interno":
                raise UserError(
                    _("Solo puede enviar al cliente desde Aprobado interno.")
                )
            if not order._quoter_user_is_contratos_profile():
                raise AccessError(_("Solo el perfil Contratos puede enviar al cliente."))
            order._quoter_workflow_transition("enviado_cliente")
        return True

    def action_quoter_client_approved(self):
        for order in self:
            if order.quoter_workflow_state != "enviado_cliente":
                raise UserError(_("Solo puede marcar aprobación del cliente desde Enviado cliente."))
            if not order._quoter_user_is_contratos_profile():
                raise AccessError(_("Solo el perfil Contratos puede registrar la aprobación del cliente."))
            order._quoter_workflow_transition("aprobado_cliente")
        return True

    def action_quoter_open_reject_wizard(self):
        self.ensure_one()
        state = self.quoter_workflow_state
        if state in ("en_aprobacion", "aprobado_interno"):
            if not self._quoter_user_is_aprobador_profile():
                raise AccessError(_("Solo el perfil Aprobador puede rechazar en esta etapa."))
            reject_mode = "internal"
        elif state == "enviado_cliente":
            if not self._quoter_user_is_contratos_profile():
                raise AccessError(_("Solo el perfil Contratos puede registrar rechazo del cliente."))
            reject_mode = "client"
        else:
            raise UserError(_("No puede rechazar la cotización en el estado actual."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Rechazar cotización"),
            "res_model": "quoter.rejection.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_order_id": self.id,
                "default_reject_mode": reject_mode,
            },
        }

    def action_quoter_resume_preparation(self):
        for order in self:
            if order.quoter_workflow_state != "rechazado_cliente":
                raise UserError(
                    _("Solo puede retomar la preparación desde Rechazado cliente.")
                )
            if not order._quoter_user_is_cotizador_profile():
                raise AccessError(_("Solo el perfil Cotizador puede retomar la preparación."))
            reason = (order.quoter_rejection_reason or "").strip()
            if not reason:
                raise UserError(_("Indique el motivo de rechazo antes de retomar."))
            order._quoter_workflow_transition(
                "en_preparacion",
                rejection_reason=reason,
                chatter_body=_("Cotización retomada en preparación."),
            )
        return True

    def _check_quoter_partner_adjustment_write_access(self):
        """Descuento/recargo % por área: perfil Aprobador en estados de aprobación."""
        self.ensure_one()
        if self.env.user.has_group("base.group_system"):
            return
        if self.quoter_workflow_state not in ("en_aprobacion", "aprobado_interno"):
            raise UserError(
                _(
                    "Solo puede editar descuentos y recargos en los estados "
                    "«En aprobación» o «Aprobado interno»."
                )
            )
        if not self._quoter_user_is_aprobador_profile():
            raise UserError(
                _("Solo usuarios del perfil Aprobador pueden editar descuentos y recargos.")
            )

# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, fields, models
from odoo.exceptions import UserError


class QuoterRejectionWizard(models.TransientModel):
    _name = "quoter.rejection.wizard"
    _description = "Rechazo de cotización con comentarios"

    order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Cotización",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    reject_mode = fields.Selection(
        selection=[
            ("internal", "Rechazo interno (Aprobador)"),
            ("client", "Rechazo del cliente (Contratos)"),
        ],
        string="Tipo de rechazo",
        required=True,
        readonly=True,
    )
    rejection_reason = fields.Text(
        string="Comentarios",
        required=True,
        help="Motivo del rechazo. La cotización volverá a En preparación o quedará en Rechazado cliente.",
    )

    def action_confirm(self):
        self.ensure_one()
        order = self.order_id
        reason = (self.rejection_reason or "").strip()
        if not reason:
            raise UserError(_("Debe indicar comentarios de rechazo."))
        if self.reject_mode == "internal":
            if order.quoter_workflow_state not in ("en_aprobacion", "aprobado_interno"):
                raise UserError(_("La cotización ya no está en etapa de aprobación interna."))
            order._quoter_workflow_transition(
                "en_preparacion",
                rejection_reason=reason,
                chatter_body=_("Rechazo interno por Aprobador."),
            )
        else:
            if order.quoter_workflow_state != "enviado_cliente":
                raise UserError(_("La cotización no está en estado Enviado cliente."))
            order._quoter_workflow_transition(
                "rechazado_cliente",
                rejection_reason=reason,
                chatter_body=_("Rechazo registrado por el cliente."),
            )
        return {"type": "ir.actions.act_window_close"}

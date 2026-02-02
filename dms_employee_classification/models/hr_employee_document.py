# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrEmployeeDocument(models.Model):
    _name = "hr.employee.document"
    _description = "Employee Document"
    _order = "classification_date desc, id desc"

    employee_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Empleado",
        required=True,
        ondelete="cascade",
        index=True,
    )
    classification_date = fields.Date(
        string="Fecha",
        required=True,
    )
    dms_file_id = fields.Many2one(
        comodel_name="dms.file",
        string="Archivo DMS",
        ondelete="cascade",
    )
    receipt_name = fields.Char(
        string="Nombre del Recibo",
        related="dms_file_id.name",
        store=True,
        readonly=True,
    )
    viewed = fields.Boolean(
        string="Visto",
        default=False,
    )
    signed = fields.Boolean(
        string="Firmado",
        compute="_compute_signed",
        store=True,
        readonly=True,
    )
    sign_request_id = fields.Many2one(
        comodel_name="sign.oca.request",
        string="Solicitud de Firma",
        ondelete="set null",
    )
    sign_request_state = fields.Selection(
        related="sign_request_id.state",
        string="Estado de Firma",
        readonly=True,
    )
    can_sign = fields.Boolean(
        string="Puede Firmar",
        compute="_compute_can_sign",
        help="Indica si el usuario actual puede firmar este documento",
    )

    @api.depends("sign_request_id", "sign_request_id.signer_ids", "sign_request_id.state")
    @api.depends_context("uid")
    def _compute_can_sign(self):
        """Determina si el usuario actual puede firmar este documento."""
        user = self.env.user
        for record in self:
            if not record.sign_request_id or record.sign_request_id.state != 'sent':
                record.can_sign = False
                continue

            # Verificar si existe un signer para el usuario actual
            user_signer = record.sign_request_id.signer_ids.filtered(
                lambda s: s.partner_id == user.partner_id.commercial_partner_id
                and not s.signed_on
            )
            record.can_sign = bool(user_signer)

    @api.depends("sign_request_id", "sign_request_id.state")
    def _compute_signed(self):
        """El documento está firmado si la solicitud de firma está en estado 'signed'."""
        for record in self:
            record.signed = (
                record.sign_request_id
                and record.sign_request_id.state == "signed"
            )

    def action_download(self):
        """Descarga el PDF y marca como visto.

        Si existe una solicitud de firma completada, descarga el PDF firmado.
        Sino, descarga el PDF original del DMS.
        """
        self.ensure_one()
        self.viewed = True

        # Si hay solicitud de firma firmada, descargar el PDF con las firmas
        if self.sign_request_id and self.sign_request_id.state == 'signed':
            url = (
                f'/web/content/sign.oca.request/{self.sign_request_id.id}/'
                f'data?download=true&filename={self.receipt_name}'
            )
            return {
                'type': 'ir.actions.act_url',
                'url': url,
                'target': 'new',
            }

        # Sino, descargar el PDF original del DMS
        if not self.dms_file_id:
            return
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/dms.file/{self.dms_file_id.id}/content?download=true',
            'target': 'new',
        }

    def action_sign(self):
        """Abre la solicitud de firma como si se hubiera clickeado el botón 'sign'."""
        self.ensure_one()

        if not self.sign_request_id:
            return

        # Llamar directamente al método sign() del request
        # (la validación de digital_signature ya se hace en sign.oca.request)
        return self.sign_request_id.sign()

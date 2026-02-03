# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models
from odoo.exceptions import UserError


class SignOcaRequest(models.Model):
    _inherit = "sign.oca.request"

    @api.depends("signer_ids", "signer_ids.is_allow_signature", "state")
    @api.depends_context("uid")
    def _compute_to_sign(self):
        """
        Override to fix context-dependent calculation.

        Calculate to_sign directly from signer_ids instead of relying on
        the stored signer_id field, which may have been calculated in a
        different user context.
        """
        user = self.env.user
        for record in self:
            # Find signer for current user
            user_signer = record.signer_ids.filtered(
                lambda s: s.partner_id == user.partner_id.commercial_partner_id
                and s.is_allow_signature
            )
            record.to_sign = bool(user_signer and record.state == 'sent')

    def sign(self):
        """
        Override to fix context-dependent signer_id issue and validate digital signature.

        Find the correct signer for the current user instead of relying
        on the stored signer_id field. Also validates that the employee
        has a digital signature configured if the request is linked to an employee.
        """
        self.ensure_one()
        user = self.env.user

        # Validar firma digital si el record_ref es un empleado
        if self.record_ref and self.record_ref._name == 'hr.employee':
            employee = self.record_ref
            if not employee.digital_signature:
                raise UserError(
                    "El empleado no tiene una firma digital configurada.\n"
                    "Por favor, complete la firma en la pestaña 'Firma digital' "
                    "del empleado antes de firmar documentos."
                )

        # Find signer for current user
        user_signer = self.signer_ids.filtered(
            lambda s: s.partner_id == user.partner_id.commercial_partner_id
        )

        if not user_signer:
            return self.get_formview_action()

        # Return the first matching signer's sign action
        return user_signer[0].sign()

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        user = self.env.user
        # Si el usuario tiene solo el grupo básico (no es manager ni admin)
        if (
            user.has_group('sign_oca.sign_oca_group_user')
            and not user.has_group('sign_oca.sign_oca_group_manager')
            and not user.has_group('sign_oca.sign_oca_group_admin')
        ):
            # Filtrar solo solicitudes donde es responsable
            args += [("user_id", "=", user.id)]
        return super().search(args, offset=offset, limit=limit, order=order, count=count)

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        user = self.env.user
        # Si el usuario tiene solo el grupo básico (no es manager ni admin)
        if (
            user.has_group('sign_oca.sign_oca_group_user')
            and not user.has_group('sign_oca.sign_oca_group_manager')
            and not user.has_group('sign_oca.sign_oca_group_admin')
        ):
            # Filtrar solo solicitudes donde es responsable
            domain = domain + [("user_id", "=", user.id)]
        return super().read_group(
            domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy
        )

# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models
from odoo.exceptions import UserError


class SignOcaRequestSigner(models.Model):
    """Extend sign.oca.request.signer to include employee digital signature."""

    _inherit = "sign.oca.request.signer"

    def get_info(self, access_token=False):
        """Override to include employee's digital signature as default."""
        res = super().get_info(access_token=access_token)

        # Si la solicitud está vinculada a un empleado, agregar su firma digital
        if (
            self.request_id.record_ref
            and self.request_id.record_ref._name == "hr.employee"
        ):
            employee = self.request_id.record_ref
            if employee.digital_signature:
                # Agregar la firma digital del empleado al diccionario partner
                res["partner"]["digital_signature"] = employee.digital_signature

        return res

    def sign(self):
        """
        Override to validate that employee has digital signature configured.
        """
        # Validar firma digital si el record_ref es un empleado
        if (
            self.request_id.record_ref
            and self.request_id.record_ref._name == "hr.employee"
        ):
            employee = self.request_id.record_ref
            if not employee.digital_signature:
                raise UserError(
                    "El empleado no tiene una firma digital configurada.\n"
                    "Por favor, complete la firma en la pestaña 'Firma digital' "
                    "del empleado antes de firmar documentos."
                )

        return super().sign()

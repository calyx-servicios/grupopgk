# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models
from odoo.exceptions import ValidationError


class WizardSignatureControl(models.TransientModel):
    _name = "wizard.signature.control"
    _description = "Wizard for Signature Control Report"

    date_from = fields.Date(
        string="Fecha Inicial",
        required=True,
    )
    date_to = fields.Date(
        string="Fecha Final",
        required=True,
    )

    def action_export_excel(self):
        """Export signature control report to Excel."""
        self.ensure_one()

        if self.date_from > self.date_to:
            raise ValidationError(
                "La Fecha Inicial no puede ser mayor que la Fecha Final."
            )

        return self.env.ref(
            'dms_employee_classification.signature_control_report'
        ).report_action(self)

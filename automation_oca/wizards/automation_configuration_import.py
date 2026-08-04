# Copyright 2026 Dixmit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.exceptions import ValidationError


class AutomationConfigurationImport(models.TransientModel):
    """Import an automation configuration from an exported JSON file."""

    _name = "automation.configuration.import"
    _description = "Automation Configuration Import"

    file_name = fields.Char()
    file_content = fields.Binary(required=True)

    def action_import(self):
        """Create a configuration record from an uploaded exported document."""
        self.ensure_one()
        if not self.file_content:
            raise ValidationError(_("Please upload a file before importing."))
        return self.env["automation.configuration"].create_document_from_attachment(
            self.file_content
        )

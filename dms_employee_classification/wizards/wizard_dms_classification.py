# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import re

from odoo import api, fields, models


class WizardDmsClassification(models.TransientModel):
    _inherit = "wizard.dms.classification"

    classification_date = fields.Date(
        string="Fecha de Clasificación",
        required=True,
        default=fields.Date.context_today,
    )
    global_directory_id = fields.Many2one(
        comodel_name="dms.directory",
        string="Directorio Global",
        help="Si se selecciona, todos los archivos se clasificarán en este directorio",
    )

    @api.onchange('global_directory_id')
    def _onchange_global_directory_id(self):
        """Cuando se selecciona un directorio global, aplicarlo a todos los detalles."""
        if self.global_directory_id:
            for detail in self.detail_ids:
                detail.directory_id = self.global_directory_id

    def _prepare_detail_vals(self, full_path, data_file):
        """Override to add employee-based filename renaming."""
        vals = super()._prepare_detail_vals(full_path, data_file)

        # Extract filename from full_path
        filename = full_path
        if "/" in filename:
            filename = filename.split("/")[-1]

        # Use the filename_pattern from template to extract legajo
        # The pattern should have a capture group () with the legajo number
        filename_pattern = self.template_id.filename_pattern
        if filename_pattern:
            match = re.search(filename_pattern, filename)
            if match and match.groups():
                # Extract the first captured group (should be the legajo)
                try:
                    legajo = int(match.group(1))
                    # Search for employee with this legajo
                    employee = self.env['hr.employee'].search([('legajo', '=', legajo)], limit=1)

                    if employee:
                        # Get file extension
                        extension = ""
                        if "." in filename:
                            extension = "." + filename.split(".")[-1]

                        # Format date as DD-MM-YYYY
                        date_str = self.classification_date.strftime('%d-%m-%Y')

                        # Use employee name as-is (with spaces)
                        clean_name = employee.name

                        # Create new filename: EMPLOYEE NAME DATE.pdf
                        new_filename = f"{clean_name} {date_str}{extension}"

                        # Store the new filename in vals
                        vals['new_filename'] = new_filename
                        vals['employee_id'] = employee.id
                except (ValueError, IndexError):
                    # If conversion to int fails or no groups, skip employee matching
                    pass

        return vals


class WizardDmsClassificationDetail(models.TransientModel):
    _inherit = "wizard.dms.classification.detail"

    new_filename = fields.Char(
        string="Nombre de Archivo",
        readonly=True,
    )
    employee_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Empleado",
        readonly=True,
    )

    @api.depends("new_filename", "file_name")
    def _compute_file_name(self):
        """Override to use new_filename if available."""
        super()._compute_file_name()
        for item in self:
            if item.new_filename:
                item.file_name = item.new_filename

    def _create_dms_file(self):
        """Override to create hr.employee.document after creating dms.file."""
        res = super()._create_dms_file()
        # Si hay empleado asociado, crear el registro de documento
        if self.employee_id and self.file_id:
            self.env['hr.employee.document'].create({
                'employee_id': self.employee_id.id,
                'classification_date': self.parent_id.classification_date,
                'dms_file_id': self.file_id.id,
            })
        return res

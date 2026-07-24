# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError


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
        """Cuando se selecciona un directorio global, asignar destino según el tipo de storage."""
        if not self.global_directory_id:
            # Si se borra el directorio global, limpiar los directorios de las líneas
            for detail in self.detail_ids:
                detail.directory_id = False
            return

        # Verificar el tipo de storage
        save_type = self.global_directory_id.storage_id.save_type

        if save_type == 'attachment':
            # Para attachment: buscar/crear subcarpetas por empleado
            for detail in self.detail_ids:
                if detail.employee_id:
                    employee_directory = self.env['dms.directory'].search([
                        ('res_model', '=', 'hr.employee'),
                        ('res_id', '=', detail.employee_id.id),
                        ('parent_id', '=', self.global_directory_id.id),
                    ], limit=1)

                    # Si existe la subcarpeta, asignarla. Si no, dejar vacío
                    detail.directory_id = employee_directory if employee_directory else False
                else:
                    # Si no hay empleado, dejar vacío
                    detail.directory_id = False
        else:
            # Para otros tipos (database, file): usar el directorio global directamente
            for detail in self.detail_ids:
                detail.directory_id = self.global_directory_id

        # Forzar recálculo de campos dependientes (file_id, state, etc)
        if self.detail_ids:
            self.detail_ids._compute_file_id()
            self.detail_ids._compute_state()

    def _get_directory_from_pattern(self, pattern, directories):
        """Override para manejar patrones vacíos o inválidos."""
        # Si hay directorio global, usarlo directamente
        if self.global_directory_id:
            return self.global_directory_id

        # Si no hay patrón, retornar False
        if not pattern:
            return False

        # Escapar el patrón para que sea un regex literal válido
        # Esto convierte "Juan Pérez" en "Juan\ Pérez" que es un regex válido
        import re as re_module
        escaped_pattern = re_module.escape(pattern)

        # Proteger contra cualquier otro error
        try:
            directory = False
            for d in directories:
                if re_module.search(escaped_pattern, d.complete_name):
                    directory = d
                    break
            return directory
        except Exception:
            return False

    def _action_classify(self):
        """Override to validate template and create signature requests."""
        # Validar que haya plantilla de firma configurada
        if (self.template_id and
                not self.template_id.signature_template_id):
            raise UserError(
                "La plantilla de clasificación no tiene configurada "
                "una plantilla de firma. Por favor configure la plantilla "
                "de firma en la plantilla de clasificación."
            )

        # Clasificar archivos normalmente
        if (self.global_directory_id and
                self.global_directory_id.storage_id.save_type == 'attachment'):
            for detail in self.detail_ids.filtered(
                    lambda x: x.state == "to_classify"):
                detail._create_dms_file()
        else:
            super()._action_classify()

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
                    # Search for employee with this legajo, filtered by the
                    # template's company to avoid ambiguity between companies
                    domain = [('legajo', '=', legajo)]
                    if self.template_id.company_id:
                        domain.append(
                            ('company_id', '=', self.template_id.company_id.id)
                        )
                    employee = self.env['hr.employee'].search(domain, limit=1)

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

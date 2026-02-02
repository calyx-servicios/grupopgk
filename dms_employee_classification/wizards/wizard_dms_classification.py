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

    # Campo para mostrar correctamente el registro referenciado
    display_record_ref = fields.Char(
        string="Registro Referenciado",
        compute="_compute_display_record_ref",
        readonly=True,
    )

    @api.depends('directory_id', 'directory_id.storage_id', 'directory_id.storage_id.save_type',
                 'record_ref', 'employee_id', 'employee_id.name')
    def _compute_display_record_ref(self):
        """Compute que muestra el record_ref solo cuando corresponde."""
        for record in self:
            # Solo mostrar si es attachment y tiene record_ref
            if (record.directory_id and
                record.directory_id.storage_id and
                record.directory_id.storage_id.save_type == 'attachment' and
                record.record_ref):
                # Formatear bonito: "hr.employee,123" -> "Empleado: Juan Pérez"
                if record.employee_id:
                    record.display_record_ref = record.employee_id.name
                else:
                    record.display_record_ref = str(record.record_ref)
            else:
                record.display_record_ref = ""

    def _compute_directory_id(self):
        """Override para escapar el patrón antes de usarlo como regex."""
        # Si el wizard padre tiene directorio global, usarlo
        # (solo en estado 'done', en 'draft' no existe este campo)
        if (hasattr(self.parent_id, 'global_directory_id') and
                self.parent_id.global_directory_id):
            for item in self:
                item.directory_id = self.parent_id.global_directory_id
        else:
            # Sino, usar el comportamiento normal
            super()._compute_directory_id()

    @api.depends("new_filename", "file_name")
    def _compute_file_name(self):
        """Override to use new_filename if available."""
        super()._compute_file_name()
        for item in self:
            if item.new_filename:
                item.file_name = item.new_filename

    def _create_dms_file(self):
        """Override to create hr.employee.document after creating dms.file."""
        # CRÍTICO: Si hay empleado y directorio global attachment,
        # ASEGURAR que directory_id esté asignado ANTES de llamar a super()
        if self.employee_id and self.parent_id.global_directory_id:
            parent_dir = self.parent_id.global_directory_id

            # Solo crear subcarpetas si el storage es de tipo attachment
            if parent_dir.storage_id.save_type == 'attachment':
                # Si directory_id está vacío, buscar/crear la subcarpeta
                if not self.directory_id:
                    # Buscar si ya existe un subdirectorio para este empleado
                    employee_directory = self.env['dms.directory'].search([
                        ('res_model', '=', 'hr.employee'),
                        ('res_id', '=', self.employee_id.id),
                        ('parent_id', '=', parent_dir.id),
                    ], limit=1)

                    # Si no existe, crearlo como SUBCARPETA del directorio global
                    if not employee_directory:
                        employee_directory = self.env['dms.directory'].create({
                            'name': self.employee_id.name,
                            'parent_id': parent_dir.id,
                            'res_model': 'hr.employee',
                            'res_id': self.employee_id.id,
                        })

                    # Usar el subdirectorio del empleado
                    self.directory_id = employee_directory

        # Ahora SÍ llamar al super() con directory_id asignado
        res = super()._create_dms_file()

        # Si hay empleado asociado, crear el registro de documento
        if self.employee_id and self.file_id:
            # Crear solicitud de firma primero
            sign_request = self._create_signature_request()

            # Crear el documento del empleado con la referencia a la solicitud
            self.env['hr.employee.document'].create({
                'employee_id': self.employee_id.id,
                'classification_date': self.parent_id.classification_date,
                'dms_file_id': self.file_id.id,
                'sign_request_id': sign_request.id if sign_request else False,
            })

        return res

    def _create_signature_request(self):
        """Create signature request for the employee document."""
        self.ensure_one()

        # Obtener plantilla desde la plantilla de clasificación
        template = self.parent_id.template_id.signature_template_id
        if not template or not template.exists():
            return

        # Obtener usuario del empleado
        user = self.employee_id.user_id
        if not user:
            return

        # Obtener TODOS los roles (sin filtrar por partner_type)
        roles = template.item_ids.mapped('role_id')
        if not roles:
            return

        # Crear solicitud de firma
        request_vals = {
            'name': f"{self.employee_id.name} - {self.parent_id.classification_date}",
            'template_id': template.id,
            'data': self.data_file,  # PDF del recibo del empleado
            'record_ref': f'hr.employee,{self.employee_id.id}',
            'signatory_data': template._get_signatory_data(),
            'user_id': user.id,  # Responsable = el empleado
            'signer_ids': [
                (0, 0, {
                    'partner_id': user.partner_id.id,  # Firmante = partner del empleado
                    'role_id': role.id,
                })
                for role in roles
            ],
        }

        request = self.env['sign.oca.request'].create(request_vals)
        # Enviar solicitud automáticamente
        request.action_send()

        return request

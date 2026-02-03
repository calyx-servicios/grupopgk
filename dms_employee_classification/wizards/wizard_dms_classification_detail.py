# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError


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
            if (
                record.directory_id
                and record.directory_id.storage_id
                and record.directory_id.storage_id.save_type == 'attachment'
                and record.record_ref
            ):
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
        request.message_subscribe(partner_ids=[user.partner_id.id])
        # Enviar solicitud automáticamente
        request.action_send()

        return request

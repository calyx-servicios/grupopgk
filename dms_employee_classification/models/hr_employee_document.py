# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


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
        default=False,
    )

    def action_download(self):
        """Descarga el PDF y marca como visto."""
        self.ensure_one()
        self.viewed = True
        if not self.dms_file_id:
            return
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/dms.file/{self.dms_file_id.id}/content?download=true',
            'target': 'new',
        }

    def action_sign(self):
        """Marca el documento como firmado."""
        self.ensure_one()
        self.signed = True

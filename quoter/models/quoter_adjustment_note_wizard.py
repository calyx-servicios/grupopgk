# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, fields, models
from odoo.exceptions import ValidationError


class QuoterAdjustmentNoteWizard(models.TransientModel):
    _name = "quoter.adjustment.note.wizard"
    _description = "Asistente de observacion para linea de ajuste"

    sale_line_id = fields.Many2one(
        comodel_name="sale.order.line",
        string="Linea base",
        required=True,
        readonly=True,
    )
    note = fields.Char(
        string="Observacion ajuste",
        required=True,
        help="Justificacion obligatoria para crear la linea de ajuste.",
    )

    def action_confirm(self):
        self.ensure_one()
        note = (self.note or "").strip()
        if not note:
            raise ValidationError(_("La observacion es obligatoria en lineas de ajuste."))
        self.sale_line_id._quoter_create_adjustment_line(note)
        return {"type": "ir.actions.act_window_close"}

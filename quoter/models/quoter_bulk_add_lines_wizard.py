# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import UserError

SIN_ETIQUETA_LABEL = "Sin Etiqueta"
# Índice reservado en el asistente para «Sin Etiqueta» (negro en el front).
SIN_ETIQUETA_COLOR = -1


class QuoterBulkAddLinesWizard(models.TransientModel):
    _name = "quoter.bulk.add.lines.wizard"
    _description = "Agregar múltiples líneas al bloque de cotización"

    block_id = fields.Many2one(
        comodel_name="quoter.sale.order.area",
        string="Bloque",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    select_all = fields.Boolean(
        string="Seleccionar todos",
        default=True,
        help="Solo uso interno del asistente; no usar onchange en líneas.",
    )
    line_ids = fields.One2many(
        comodel_name="quoter.bulk.add.lines.wizard.line",
        inverse_name="wizard_id",
        string="Productos disponibles",
    )

    def write(self, vals):
        """Solo «Seleccionar todos» del encabezado: propaga a todas las líneas."""
        if "select_all" in vals and not self.env.context.get(
            "quoter_skip_select_all_sync"
        ):
            selected = bool(vals["select_all"])
            for wizard in self:
                wizard.line_ids.with_context(
                    quoter_skip_select_all_sync=True
                ).write({"selected": selected})
        return super().write(vals)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        block_id = self.env.context.get("default_block_id") or self.env.context.get(
            "active_id"
        )
        block = self.env["quoter.sale.order.area"].browse(block_id).exists()
        if not block:
            return res
        res["block_id"] = block.id
        if "line_ids" in fields_list:
            res["line_ids"] = block._quoter_bulk_add_wizard_line_commands()
        if "select_all" in fields_list:
            res["select_all"] = True
        return res

    def action_confirm(self):
        self.ensure_one()
        selected = self.line_ids.filtered("selected").mapped("product_id").ids
        if not selected:
            raise UserError(_("Seleccione al menos un producto."))
        allowed = set(self.line_ids.mapped("product_id").ids)
        product_ids = [pid for pid in selected if pid in allowed]
        if not product_ids:
            raise UserError(_("Seleccione al menos un producto."))
        self.block_id.action_quoter_bulk_add_lines(product_ids)
        return {"type": "ir.actions.client", "tag": "reload"}


class QuoterBulkAddLinesWizardLine(models.TransientModel):
    _name = "quoter.bulk.add.lines.wizard.line"
    _description = "Línea del asistente de carga múltiple"
    _order = "section_sort, product_name, id"

    wizard_id = fields.Many2one(
        comodel_name="quoter.bulk.add.lines.wizard",
        required=True,
        ondelete="cascade",
    )
    selected = fields.Boolean(string="Incluir", default=True)
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Producto",
        required=True,
        readonly=True,
    )
    product_name = fields.Char(string="Descripción", readonly=True)
    separator_tag_id = fields.Many2one(
        comodel_name="quoter.line.separator.tag",
        string="Etiqueta separadora",
        readonly=True,
    )
    section_label = fields.Char(string="Sección", readonly=True)
    separator_color = fields.Integer(
        string="Color de sección",
        readonly=True,
        default=SIN_ETIQUETA_COLOR,
    )
    section_sort = fields.Char(string="Orden de sección", readonly=True)

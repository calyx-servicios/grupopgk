# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class QuoterGenericProductWizard(models.TransientModel):
    _name = "quoter.generic.product.wizard"
    _description = "Crear producto genérico del cotizador (catálogo)"

    name = fields.Char(string="Nombre", required=True)

    def action_create_product(self):
        self.ensure_one()
        tmpl = self.env["product.template"].quoter_create_generic_product(self.name)
        return {
            "type": "ir.actions.act_window",
            "name": _("Producto genérico"),
            "res_model": "product.template",
            "view_mode": "form",
            "res_id": tmpl.id,
            "target": "current",
        }


class QuoterAddGenericToAreaWizard(models.TransientModel):
    _name = "quoter.add.generic.to.area.wizard"
    _description = "Agregar producto genérico a un área"

    area_id = fields.Many2one(
        comodel_name="quoter.professional.area",
        string="Área",
        required=True,
        ondelete="cascade",
    )
    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Producto genérico existente",
        domain=[("is_quoter_generic_product", "=", True)],
        ondelete="cascade",
    )
    new_generic_name = fields.Char(
        string="Nombre del producto genérico nuevo",
        help="Si no encuentra el producto en la lista, créelo aquí (igual que en el menú Productos).",
    )
    separator_tag_id = fields.Many2one(
        comodel_name="quoter.line.separator.tag",
        string="Sección de cotizador",
        ondelete="set null",
    )
    is_default_product = fields.Boolean(string="Producto predeterminado", default=False)
    manual_load = fields.Boolean(string="Carga manual", default=False)
    manual_total_load = fields.Boolean(string="Horas totales manual", default=False)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        area_id = self.env.context.get("default_area_id") or self.env.context.get("active_id")
        if area_id and "area_id" in fields_list:
            res["area_id"] = area_id
        return res

    def _quoter_resolve_generic_template(self):
        """Producto existente o recién creado a partir del nombre nuevo."""
        self.ensure_one()
        name = (self.new_generic_name or "").strip()
        if name:
            return self.env["product.template"].quoter_create_generic_product(name)
        if self.product_tmpl_id:
            return self.product_tmpl_id
        raise UserError(
            _("Seleccione un producto genérico existente o indique un nombre para crear uno nuevo.")
        )

    def action_create_generic_product(self):
        """Crea el producto genérico y lo deja seleccionado (mismo flujo que el menú Productos)."""
        self.ensure_one()
        tmpl = self._quoter_resolve_generic_template()
        self.write({"product_tmpl_id": tmpl.id, "new_generic_name": False})
        return {
            "type": "ir.actions.act_window",
            "name": _("Agregar producto genérico"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": dict(self.env.context, default_area_id=self.area_id.id),
        }

    def action_add_to_area(self):
        self.ensure_one()
        area = self.area_id
        tmpl = self._quoter_resolve_generic_template()
        if not area or not tmpl:
            raise UserError(_("Seleccione área y producto genérico."))
        if not tmpl.is_quoter_generic_product:
            raise UserError(_("El producto elegido no es un producto genérico del cotizador."))
        ServiceLine = self.env["quoter.service.line"]
        existing = ServiceLine.search(
            [("area_id", "=", area.id), ("product_tmpl_id", "=", tmpl.id)], limit=1
        )
        if existing:
            raise UserError(
                _("El producto «%s» ya está en la lista del área «%s».")
                % (tmpl.display_name, area.display_name)
            )
        ServiceLine.with_context(quoter_skip_line_product_resync=True).create(
            {
                "area_id": area.id,
                "name": tmpl.name,
                "product_tmpl_id": tmpl.id,
                "product_id": tmpl.product_variant_ids[:1].id if tmpl.product_variant_ids else False,
                "separator_tag_id": self.separator_tag_id.id if self.separator_tag_id else False,
                "is_default_product": self.is_default_product,
                "manual_load": self.manual_load,
                "manual_total_load": self.manual_total_load,
            }
        )
        return {"type": "ir.actions.act_window_close"}

# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class QuoterGenericProductWizard(models.TransientModel):
    _name = "quoter.generic.product.wizard"
    _description = "Crear producto genérico del cotizador (catálogo)"

    name = fields.Char(string="Nombre", required=True)

    def _quoter_general_category(self):
        return self.env.ref("quoter.product_category_quoter_general", raise_if_not_found=False)

    def action_create_product(self):
        self.ensure_one()
        general_categ = self._quoter_general_category()
        if not general_categ:
            raise UserError(_("No está configurada la categoría General (Cotizador)."))
        name = (self.name or "").strip()
        if not name:
            raise UserError(_("Indique un nombre para el producto."))
        Template = self.env["product.template"]
        if Template.search(
            [("is_quoter_generic_product", "=", True), ("name", "=", name)], limit=1
        ):
            raise UserError(_("Ya existe un producto genérico con ese nombre."))
        uom_unit = self.env.ref("uom.product_uom_unit", raise_if_not_found=False)
        tmpl_vals = {
            "name": name,
            "type": "service",
            "sale_ok": True,
            "purchase_ok": False,
            "default_code": "QR-G-%s" % (name[:40].replace(" ", "-") or "GEN"),
            "is_quoter_product": True,
            "is_quoter_generic_product": True,
            "quoter_area_id": False,
            "quoter_service_line_id": False,
            "categ_id": general_categ.id,
        }
        if uom_unit:
            tmpl_vals["uom_id"] = uom_unit.id
            tmpl_vals["uom_po_id"] = uom_unit.id
        tmpl = Template.create(tmpl_vals)
        Template.quoter_apply_default_sale_taxes(tmpl)
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
        string="Producto genérico",
        required=True,
        domain=[("is_quoter_generic_product", "=", True)],
        ondelete="cascade",
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

    def action_add_to_area(self):
        self.ensure_one()
        area = self.area_id
        tmpl = self.product_tmpl_id
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

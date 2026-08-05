# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_quoter_range_rate_product = fields.Boolean(
        string="Producto tarifa lista (hora/rango)",
        index=True,
        help="Producto técnico por combinación área + rango: precio por hora vía reglas estándar "
        "de la lista de precios. No se ofrece como producto de servicio en el cotizador.",
    )
    quoter_range_rate_area_id = fields.Many2one(
        comodel_name="quoter.professional.area",
        string="Área (tarifa/h)",
        ondelete="cascade",
        index=True,
        copy=False,
    )
    quoter_range_rate_range_id = fields.Many2one(
        comodel_name="quoter.area.complexity.range",
        string="Rango (tarifa/h)",
        ondelete="restrict",
        index=True,
        copy=False,
    )

    @api.constrains("is_quoter_range_rate_product", "is_quoter_product")
    def _check_quoter_range_rate_vs_service(self):
        for rec in self:
            if rec.is_quoter_range_rate_product and rec.is_quoter_product:
                raise ValidationError(
                    _("Un producto no puede ser a la vez «del cotizador» y «tarifa lista por rango».")
                )

    @api.constrains(
        "is_quoter_range_rate_product",
        "quoter_range_rate_area_id",
        "quoter_range_rate_range_id",
    )
    def _check_range_rate_refs(self):
        for rec in self.filtered("is_quoter_range_rate_product"):
            if not rec.quoter_range_rate_area_id or not rec.quoter_range_rate_range_id:
                raise ValidationError(
                    _("Los productos de tarifa por rango requieren área y rango.")
                )
            area = rec.quoter_range_rate_area_id
            if rec.quoter_range_rate_range_id not in area.area_range_ids:
                raise ValidationError(_("El rango debe estar entre los rangos del área indicada."))

    @api.constrains(
        "quoter_range_rate_area_id",
        "quoter_range_rate_range_id",
        "is_quoter_range_rate_product",
    )
    def _check_unique_quoter_range_rate_template(self):
        for rec in self.filtered("is_quoter_range_rate_product"):
            dup = self.search_count(
                [
                    ("id", "!=", rec.id),
                    ("is_quoter_range_rate_product", "=", True),
                    ("quoter_range_rate_area_id", "=", rec.quoter_range_rate_area_id.id),
                    ("quoter_range_rate_range_id", "=", rec.quoter_range_rate_range_id.id),
                ]
            )
            if dup:
                raise ValidationError(
                    _("Ya existe un producto tarifa/h para este área y rango.")
                )


class ProductProduct(models.Model):
    _inherit = "product.product"

    is_quoter_range_rate_product = fields.Boolean(
        related="product_tmpl_id.is_quoter_range_rate_product",
        store=True,
        readonly=True,
        index=True,
    )
    quoter_range_rate_area_id = fields.Many2one(
        related="product_tmpl_id.quoter_range_rate_area_id",
        store=True,
        readonly=True,
        index=True,
    )
    quoter_range_rate_range_id = fields.Many2one(
        related="product_tmpl_id.quoter_range_rate_range_id",
        store=True,
        readonly=True,
        index=True,
    )


# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class QuoterServiceProductLine(models.Model):
    _name = "quoter.service.product.line"
    _description = "Quoter Service Product Line"
    _order = "service_id, sequence, product_id"

    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Sequence for ordering lines"
    )

    service_id = fields.Many2one(
        comodel_name="quoter.service.config",
        string="Service",
        required=True,
        ondelete="cascade",
        help="Service this product line belongs to"
    )
    
    task_category = fields.Selection(
        selection=[
            ("audit", "Auditoría"),
            ("complementary", "Tareas Complementarias"),
            ("other", "Otras Tareas"),
        ],
        string="Categoría de Tarea",
        default="audit",
        required=True,
        help="Categoría de la tarea para organización"
    )
    
    task_description = fields.Text(
        string="Descripción de la Tarea",
        help="Detalle de los procedimientos incluidos en esta tarea"
    )
    
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
        required=True,
        domain="[('sale_ok', '=', True), ('is_quoter_range_rate_product', '=', False)]",
        help="Product to be quoted"
    )
    
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Unit of Measure",
        related="product_id.uom_id",
        readonly=True
    )
    
    ae_hours = fields.Float(
        string="AE Hours",
        default=0.0,
        help="Experienced Assistant hours"
    )
    
    sr_hours = fields.Float(
        string="SR Hours",
        default=0.0,
        help="Senior hours"
    )
    
    mg_hours = fields.Float(
        string="MG Hours",
        default=0.0,
        help="Manager hours"
    )
    
    partner_hours = fields.Float(
        string="Partner Hours",
        default=0.0,
        help="Partner hours"
    )
    
    total_hours = fields.Float(
        string="Total Hours",
        compute="_compute_total_hours",
        store=True,
        help="Sum of all role hours"
    )
    
    price_unit = fields.Monetary(
        string="Unit Price",
        compute="_compute_price_unit",
        store=True,
        currency_field="currency_id",
        help="Unit price from pricelist"
    )
    
    amount = fields.Monetary(
        string="Amount",
        compute="_compute_amount",
        store=True,
        currency_field="currency_id",
        help="Total amount (total_hours * price_unit)"
    )
    
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        related="service_id.currency_id",
        store=True,
        readonly=True
    )
    
    pricelist_id = fields.Many2one(
        comodel_name="product.pricelist",
        string="Price List",
        related="service_id.pricelist_id",
        store=True,
        readonly=True
    )
    
    hours_percentage = fields.Float(
        string="% del Total",
        compute="_compute_hours_percentage",
        store=True,
        digits=(5, 2),
        help="Porcentaje de horas sobre el total del servicio"
    )

    _sql_constraints = [
        (
            "check_hours_positive",
            "CHECK(ae_hours >= 0 AND sr_hours >= 0 AND mg_hours >= 0 AND partner_hours >= 0)",
            "Hours must be positive or zero!"
        ),
    ]

    @api.depends("ae_hours", "sr_hours", "mg_hours", "partner_hours")
    def _compute_total_hours(self):
        """Compute total hours as sum of all role hours."""
        for line in self:
            line.total_hours = (
                line.ae_hours + line.sr_hours + line.mg_hours + line.partner_hours
            )
            

    @api.depends("product_id", "pricelist_id")
    def _compute_price_unit(self):
        """Compute unit price from pricelist."""
        for line in self:
            if line.product_id and line.pricelist_id:
                line.price_unit = line.pricelist_id.get_product_price(
                    product=line.product_id,
                    quantity=1.0,
                    partner=None,
                    date=fields.Date.today(),
                    uom_id=line.product_uom_id.id
                )
            else:
                line.price_unit = 0.0

    @api.depends("total_hours", "price_unit")
    def _compute_amount(self):
        """Compute amount as total_hours * price_unit."""
        for line in self:
            line.amount = line.total_hours * line.price_unit

    @api.depends("total_hours", "service_id.total_hours")
    def _compute_hours_percentage(self):
        """Calcular porcentaje de horas."""
        for line in self:
            if line.service_id and line.service_id.total_hours > 0:
                line.hours_percentage = (
                    (line.total_hours / line.service_id.total_hours) * 100
                )
            else:
                line.hours_percentage = 0.0

    @api.constrains("ae_hours", "sr_hours", "mg_hours", "partner_hours")
    def _check_at_least_one_hour(self):
        """Validate that at least one hour field has a value greater than zero."""
        for line in self:
            if line.total_hours <= 0:
                raise ValidationError(
                    _("At least one role must have hours greater than zero.")
                )

    @api.constrains("product_id", "service_id")
    def _check_unique_product_per_service(self):
        """Validate that product is unique within the service."""
        for line in self:
            if line.product_id and line.service_id:
                duplicate = self.search([
                    ("id", "!=", line.id),
                    ("service_id", "=", line.service_id.id),
                    ("product_id", "=", line.product_id.id),
                ])
                if duplicate:
                    raise ValidationError(
                        _("Product '%s' is already added to this service.") % 
                        line.product_id.name
                    )

    def name_get(self):
        """Custom name display."""
        result = []
        for line in self:
            name = f"{line.product_id.name} ({line.total_hours}h)"
            result.append((line.id, name))
        return result

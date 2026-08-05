# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class QuoterServiceConfig(models.Model):
    _name = "quoter.service.config"
    _description = "Quoter Service Configuration"
    _order = "name"

    name = fields.Char(
        string="Service Name",
        required=True,
        help="Name of the service to be quoted"
    )
    
    # Client Information
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Cliente",
        required=True,
        domain="[('customer_rank', '>', 0)]",
        help="Cliente para esta cotización"
    )

    contact_id = fields.Many2one(
        comodel_name="res.partner",
        string="Contacto",
        domain="[('parent_id', '=', partner_id), ('type', '=', 'contact')]",
        help="Persona de contacto del cliente"
    )
    
    # Responsible persons
    manager_id = fields.Many2one(
        comodel_name="res.users",
        string="Gerente a Cargo",
        help="Gerente responsable del servicio"
    )

    partner_responsible_id = fields.Many2one(
        comodel_name="res.users",
        string="Socio Responsable",
        help="Socio responsable del servicio"
    )
    
    # Audit configuration
    risk_level = fields.Selection(
        selection=[
            ("low", "Bajo"),
            ("medium", "Medio"),
            ("high", "Alto"),
        ],
        string="Nivel de Riesgo",
        required=True,
        default="medium",
        help="Nivel de riesgo de auditoría. Alto para primeras auditorías o clientes con hallazgos previos"
    )
    
    complexity = fields.Selection(
        selection=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
        ],
        string="Complexity",
        required=True,
        default="medium",
        help="Service complexity level"
    )
    
    pricelist_id = fields.Many2one(
        comodel_name="product.pricelist",
        string="Price List",
        required=True,
        help="Price list to calculate service amounts"
    )
    
    proposal_date = fields.Date(
        string="Fecha de Propuesta",
        default=fields.Date.today,
        required=True,
        help="Fecha de referencia de la propuesta"
    )

    previous_proposal_date = fields.Date(
        string="Fecha Propuesta Anterior",
        help="Fecha de la última propuesta previa"
    )

    previous_amount = fields.Monetary(
        string="Honorarios Propuesta Anterior",
        currency_field="currency_id",
        help="Monto de la propuesta anterior"
    )
    
    # Billing conditions
    billing_type = fields.Selection(
        selection=[
            ("monthly_retainer", "Abono Mensual"),
            ("one_time", "Puntual"),
            ("installments", "Cuotas"),
        ],
        string="Tipo de Facturación",
        help="Condiciones de facturación del servicio"
    )

    installments_count = fields.Integer(
        string="Cantidad de Cuotas",
        help="Número de cuotas si aplica"
    )

    adjustment_method = fields.Char(
        string="Forma de Actualización",
        help="Método de actualización de honorarios (ej: USD, acuerdo comercial, etc.)"
    )
    
    other_considerations = fields.Text(
        string="Otras Consideraciones",
        help="Documentar consideraciones especiales que modifiquen valores predeterminados"
    )
    
    # Hours by category
    total_ae_hours = fields.Float(
        string="Total Horas AE",
        compute="_compute_hours_by_category",
        store=True,
        help="Suma de horas de Asistente Experimentado"
    )

    total_sr_hours = fields.Float(
        string="Total Horas SR",
        compute="_compute_hours_by_category",
        store=True,
        help="Suma de horas de Senior"
    )

    total_gte_hours = fields.Float(
        string="Total Horas GTE",
        compute="_compute_hours_by_category",
        store=True,
        help="Suma de horas de Gerente"
    )

    total_partner_hours = fields.Float(
        string="Total Horas Socio",
        compute="_compute_hours_by_category",
        store=True,
        help="Suma de horas de Socio"
    )

    average_hour_rate = fields.Monetary(
        string="Valor Promedio Hora",
        compute="_compute_average_hour_rate",
        store=True,
        currency_field="currency_id",
        help="Total Amount / Total Hours"
    )
    
    product_line_ids = fields.One2many(
        comodel_name="quoter.service.product.line",
        inverse_name="service_id",
        string="Product Lines",
        help="Products included in this service with hours per role"
    )
    
    total_hours = fields.Float(
        string="Total Hours",
        compute="_compute_total_hours",
        store=True,
        help="Sum of all hours from all product lines"
    )
    
    total_amount = fields.Monetary(
        string="Total Amount",
        compute="_compute_total_amount",
        store=True,
        currency_field="currency_id",
        help="Total amount based on pricelist"
    )
    
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        related="pricelist_id.currency_id",
        store=True,
        readonly=True
    )
    
    product_line_count = fields.Integer(
        string="Product Lines Count",
        compute="_compute_product_line_count"
    )

    _sql_constraints = [
        (
            "name_unique",
            "UNIQUE(name)",
            "Service name must be unique!"
        ),
    ]

    @api.depends("product_line_ids.total_hours")
    def _compute_total_hours(self):
        """Compute total hours from all product lines."""
        for record in self:
            record.total_hours = sum(
                record.product_line_ids.mapped("total_hours")
            )

    @api.depends("product_line_ids.amount")
    def _compute_total_amount(self):
        """Compute total amount from all product lines."""
        for record in self:
            record.total_amount = sum(
                record.product_line_ids.mapped("amount")
            )

    @api.depends("product_line_ids")
    def _compute_product_line_count(self):
        """Compute number of product lines."""
        for record in self:
            record.product_line_count = len(record.product_line_ids)

    @api.depends("product_line_ids.ae_hours", "product_line_ids.sr_hours", 
                 "product_line_ids.mg_hours", "product_line_ids.partner_hours")
    def _compute_hours_by_category(self):
        """Calcular totales por categoría."""
        for record in self:
            record.total_ae_hours = sum(record.product_line_ids.mapped("ae_hours"))
            record.total_sr_hours = sum(record.product_line_ids.mapped("sr_hours"))
            record.total_gte_hours = sum(record.product_line_ids.mapped("mg_hours"))
            record.total_partner_hours = sum(record.product_line_ids.mapped("partner_hours"))

    @api.depends("total_amount", "total_hours")
    def _compute_average_hour_rate(self):
        """Calcular tarifa promedio por hora."""
        for record in self:
            if record.total_hours > 0:
                record.average_hour_rate = record.total_amount / record.total_hours
            else:
                record.average_hour_rate = 0.0

    @api.constrains("product_line_ids")
    def _check_product_lines(self):
        """Validate that service has at least one product line."""
        for record in self:
            if not record.product_line_ids:
                raise ValidationError(
                    _("Service must have at least one product line.")
                )

    def action_apply_audit_rules(self):
        """
        Aplicar reglas de auditoría:
        - SR = 50% de AE
        - GTE = 30% de SR  
        - Socio = 10-20% de GTE según riesgo (mínimo 1 hora)
        """
        for record in self:
            # Determinar porcentaje de socio según riesgo
            if record.risk_level == "low":
                partner_percentage = 0.10
            elif record.risk_level == "medium":
                partner_percentage = 0.15
            else:  # high
                partner_percentage = 0.20
            
            for line in record.product_line_ids:
                # SR = 50% AE
                line.sr_hours = line.ae_hours * 0.5
                
                # GTE = 30% SR
                line.mg_hours = line.sr_hours * 0.3
                
                # Socio según riesgo (mínimo 1 hora)
                calculated_partner = line.mg_hours * partner_percentage
                line.partner_hours = max(calculated_partner, 1.0) if calculated_partner > 0 else 0.0

    def name_get(self):
        """Custom name display."""
        result = []
        for record in self:
            name = f"[{record.complexity.upper()}] {record.name}"
            result.append((record.id, name))
        return result

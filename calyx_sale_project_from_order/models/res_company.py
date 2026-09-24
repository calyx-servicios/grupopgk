from odoo import fields, models


class ResCompany(models.Model):
    """Configura por compañía la generación de proyectos desde ventas."""

    _inherit = "res.company"

    calyx_sale_project_from_order_enabled = fields.Boolean(
        string="Generar proyectos desde órdenes de venta",
        help=(
            "Crea un proyecto por OV y una tarea por cada línea de servicio "
            "al confirmar una orden de venta directa."
        ),
    )

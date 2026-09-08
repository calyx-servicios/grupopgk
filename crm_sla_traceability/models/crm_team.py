from odoo import fields, models


class CrmTeam(models.Model):
    """Add the traceability and SLA configuration to sales teams."""

    _inherit = "crm.team"

    sla_traceability_enabled = fields.Boolean(
        string="Activar trazabilidad y SLA",
        default=False,
    )
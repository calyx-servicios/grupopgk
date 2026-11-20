# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import _, fields, models


class ProjectManagementReportCalyxWizard(models.TransientModel):
    """Mismo asistente que el informe PGK (filtros, validaciones y encabezado).

    Los Many2many se redefinen con tablas de relación propias: al heredar por
    prototipo no pueden compartir las del asistente PGK.
    """

    _name = "project.management.report.calyx.wizard"
    _inherit = "project.management.report.wizard"
    _description = "Asistente Informe Gestión de Proyectos CALYX"

    _report_model = "project.management.report.calyx"

    company_ids = fields.Many2many(
        "res.company",
        "project_mgmt_report_calyx_wizard_company_rel",
        "wizard_id",
        "company_id",
        string="Compañías",
        domain=lambda self: [("id", "in", self.env.user.company_ids.ids)],
        help="Vacío: todas las compañías permitidas para el usuario.",
    )
    parent_analytic_account_ids = fields.Many2many(
        "account.analytic.account",
        "project_mgmt_report_calyx_wizard_parent_account_rel",
        "wizard_id",
        "account_id",
        string="Cuenta analítica madre",
        domain=[("child_ids", "!=", False)],
    )
    partner_ids = fields.Many2many(
        "res.partner",
        "project_mgmt_report_calyx_wizard_partner_rel",
        "wizard_id",
        "partner_id",
        string="Cliente",
    )
    stage_ids = fields.Many2many(
        "project.project.stage",
        "project_mgmt_report_calyx_wizard_stage_rel",
        "wizard_id",
        "stage_id",
        string="Etapa",
        default=lambda self: self._default_stage_ids(),
        help="Vacío: todas las etapas.",
    )

    def _get_currency_note(self):
        return _("Montos en PES, salvo Importe total proyecto (moneda del proyecto).")

# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import base64

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression


class ProjectManagementReportWizard(models.TransientModel):
    _name = "project.management.report.wizard"
    _description = "Asistente Informe Gestión de Proyectos PGK"

    date_mode = fields.Selection(
        [
            ("all", "Sin filtro de fechas (acumulado total)"),
            ("range", "Rango de fechas"),
        ],
        string="Fechas",
        default="all",
        required=True,
    )
    date_from = fields.Date(string="Fecha desde")
    date_to = fields.Date(string="Fecha hasta")
    company_ids = fields.Many2many(
        "res.company",
        "project_mgmt_report_wizard_company_rel",
        "wizard_id",
        "company_id",
        string="Compañías",
        domain=lambda self: [("id", "in", self.env.user.company_ids.ids)],
        help="Vacío: todas las compañías permitidas para el usuario.",
    )
    parent_analytic_account_ids = fields.Many2many(
        "account.analytic.account",
        "project_mgmt_report_wizard_parent_account_rel",
        "wizard_id",
        "account_id",
        string="Cuenta analítica madre",
        domain=[("child_ids", "!=", False)],
    )
    partner_ids = fields.Many2many(
        "res.partner",
        "project_mgmt_report_wizard_partner_rel",
        "wizard_id",
        "partner_id",
        string="Cliente",
    )
    stage_ids = fields.Many2many(
        "project.project.stage",
        "project_mgmt_report_wizard_stage_rel",
        "wizard_id",
        "stage_id",
        string="Etapa",
        default=lambda self: self._default_stage_ids(),
        help="Vacío: todas las etapas.",
    )
    consider_billable = fields.Boolean(string="Facturable", default=True)
    consider_non_billable = fields.Boolean(string="No facturable", default=True)
    consider_timesheet = fields.Boolean(
        string="Parte de horas",
        default=True,
        help="Proyectos con parte de horas que no son Facturable ni No facturable.",
    )
    file_format = fields.Selection(
        [("xlsx", "Excel (XLSX)"), ("csv", "CSV")],
        string="Formato",
        default="xlsx",
        required=True,
    )
    file_data = fields.Binary(string="Archivo", readonly=True, attachment=False)
    file_name = fields.Char(string="Nombre de archivo", readonly=True)

    @api.model
    def _default_stage_ids(self):
        # "En progreso" en esta base es la etapa base "To Do"
        stage = self.env.ref("project.project_project_stage_0", raise_if_not_found=False)
        return stage.ids if stage else []

    # ------------------------------------------------------------------
    # Validaciones y filtros
    # ------------------------------------------------------------------
    def _check_values(self):
        self.ensure_one()
        if self.date_mode == "range":
            if not self.date_from or not self.date_to:
                raise UserError(_("Indique la Fecha desde y la Fecha hasta."))
            if self.date_from > self.date_to:
                raise UserError(_("La Fecha desde no puede ser posterior a la Fecha hasta."))
        if not (self.consider_billable or self.consider_non_billable
                or self.consider_timesheet):
            raise UserError(_("Seleccione al menos una opción en Considerar."))

    def _get_date_range(self):
        self.ensure_one()
        if self.date_mode == "range":
            return self.date_from, self.date_to
        return None, None

    def _get_allowed_companies(self):
        allowed = self.env.user.company_ids
        if self.company_ids:
            return self.company_ids & allowed
        return allowed

    def _get_project_domain(self):
        self.ensure_one()
        domain = [("company_id", "in", self._get_allowed_companies().ids)]
        if self.parent_analytic_account_ids:
            domain.append(
                ("analytic_account_id.parent_id", "in", self.parent_analytic_account_ids.ids)
            )
        if self.partner_ids:
            domain.append(("partner_id", "in", self.partner_ids.ids))
        if self.stage_ids:
            domain.append(("stage_id", "in", self.stage_ids.ids))
        if not (self.consider_billable and self.consider_non_billable
                and self.consider_timesheet):
            options = []
            if self.consider_billable:
                options.append([("allow_billable", "=", True)])
            if self.consider_non_billable:
                options.append([("is_non_billable", "=", True)])
            if self.consider_timesheet:
                options.append([
                    ("allow_timesheets", "=", True),
                    ("allow_billable", "=", False),
                    ("is_non_billable", "=", False),
                ])
            domain = expression.AND([domain, expression.OR(options)])
        return domain

    def _get_projects(self):
        """Proyectos a informar.

        Se leen con todas las compañías permitidas del usuario (no solo las
        activas en el selector), así las líneas de otras compañías del grupo
        cuentan igual que en los campos de Odoo. El filtro de compañía del
        asistente se aplica solo sobre el proyecto.
        """
        self.ensure_one()
        Project = self.env["project.project"].with_context(
            allowed_company_ids=self.env.user.company_ids.ids
        )
        return Project.search(
            self._get_project_domain(), order="company_id, name, id"
        )

    def _get_header_lines(self):
        """Líneas del encabezado con el rango de fechas y los filtros aplicados."""
        self.ensure_one()

        def names(records):
            return ", ".join(records.mapped("display_name")) if records else _("Todos")

        lang = self.env["res.lang"]._lang_get(self.env.user.lang or "es_AR")
        date_format = (lang and lang.date_format) or "%d/%m/%Y"
        if self.date_mode == "range":
            dates = _(
                "Fechas: desde %(from)s hasta %(to)s. Costos y Dist. Gtos. "
                "por períodos de consolidación cuyo mes comienza en el rango."
            ) % {
                "from": self.date_from.strftime(date_format),
                "to": self.date_to.strftime(date_format),
            }
        else:
            dates = _("Fechas: sin filtro (acumulado total desde el inicio)")
        consider = []
        if self.consider_billable:
            consider.append(_("Facturable"))
        if self.consider_non_billable:
            consider.append(_("No facturable"))
        if self.consider_timesheet:
            consider.append(_("Parte de horas"))
        now = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        return [
            dates,
            _("Compañía: %s") % (
                names(self.company_ids & self.env.user.company_ids)
                if self.company_ids else _("Todas las permitidas")
            ),
            _("Cuenta analítica madre: %s") % (
                names(self.parent_analytic_account_ids)
                if self.parent_analytic_account_ids else _("Todas")
            ),
            _("Cliente: %s") % names(self.partner_ids),
            _("Etapa: %s") % (names(self.stage_ids) if self.stage_ids else _("Todas")),
            _("Considerar: %s") % ", ".join(consider),
            _("Montos en PES, salvo Importe total proyecto y Facturación por "
              "avance - PGK (moneda del proyecto)."),
            _("Emitido el %(date)s por %(user)s") % {
                "date": now.strftime(date_format + " %H:%M"),
                "user": self.env.user.name,
            },
        ]

    # ------------------------------------------------------------------
    # Acción
    # ------------------------------------------------------------------
    def action_export(self):
        self.ensure_one()
        self._check_values()
        content, file_name = self.env["project.management.report"]._generate_file(self)
        self.write({
            "file_data": base64.b64encode(content),
            "file_name": file_name,
        })
        return {
            "type": "ir.actions.act_url",
            "url": (
                "/web/content/?model=%s&id=%s&field=file_data"
                "&filename_field=file_name&download=true"
            ) % (self._name, self.id),
            "target": "self",
        }

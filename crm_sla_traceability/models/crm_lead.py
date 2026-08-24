from collections import defaultdict
from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_compare

# Reglas de negocio del SLA y las aprobaciones.
PRESALES_MAX_HOURS = 8
COMPLEX_SLA_HOURS = 72
COMMITTED_MAX_DAYS = 5
REMINDER_HOURS = 48
SLA_WARNING_RATIO = 0.75

# Valores del semáforo SLA.
SLA_ON_TIME = "on_time"
SLA_WARNING = "warning"
SLA_OVERDUE = "overdue"

# Campos obligatorios para poder avanzar de la etapa inicial.
INITIAL_STAGE_FIELDS = (
    "opportunity_type_id",
    "classification_id",
    "request_origin_id",
)

SATURDAY = 5


class CrmLead(models.Model):
    _inherit = "crm.lead"

    # ------------------------------------------------------------------
    # Catálogos maestros
    # ------------------------------------------------------------------
    opportunity_type_id = fields.Many2one(
        comodel_name="crm.opportunity.type",
        string="Opportunity Type",
        tracking=True,
    )
    classification_id = fields.Many2one(
        comodel_name="crm.classification",
        string="Classification",
        tracking=True,
    )
    request_origin_id = fields.Many2one(
        comodel_name="crm.request.origin",
        string="Traceability Origin",
        tracking=True,
    )

    # ------------------------------------------------------------------
    # SLA
    # ------------------------------------------------------------------
    sla_deadline = fields.Datetime(
        string="SLA Deadline",
        tracking=True,
        help="Automatically computed when choosing the classification (business hours, "
        "Mon-Fri). It can be edited manually for commercial reasons.",
    )
    sla_status = fields.Selection(
        selection=[
            (SLA_ON_TIME, "On Time"),
            (SLA_WARNING, "Due Soon"),
            (SLA_OVERDUE, "Overdue"),
        ],
        string="SLA Status",
        readonly=True,
        tracking=True,
        help="Periodically recalculated based on the % of progress between the creation "
        "date and the SLA deadline.",
    )
    waiting_customer = fields.Boolean(
        string="Waiting for Customer",
        tracking=True,
        help="When checked, it pauses the SLA countdown.",
    )
    waiting_customer_date = fields.Datetime(
        string="Waiting for Customer Date",
        tracking=True,
    )
    committed_date = fields.Date(
        string="Date Committed to Customer",
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Preventa DC
    # ------------------------------------------------------------------
    presales_effort_hours = fields.Float(
        string="DC Presales Effort (h)",
        tracking=True,
    )
    presales_approval_date = fields.Datetime(
        string="DC Presales Approval",
        readonly=True,
    )
    presales_approval_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Approved by (DC presales)",
        readonly=True,
    )

    # ------------------------------------------------------------------
    # Estimación
    # ------------------------------------------------------------------
    estimated_hours_lt = fields.Float(
        string="Estimated Hours (LT)",
        tracking=True,
    )
    estimation_validity_date = fields.Date(
        string="Estimate Validity",
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Aprobación DC
    # ------------------------------------------------------------------
    dc_approval_date = fields.Datetime(
        string="DC Approval",
        readonly=True,
    )
    dc_approval_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Approved by (DC)",
        readonly=True,
    )

    # ------------------------------------------------------------------
    # Helpers de UI (no almacenados)
    # ------------------------------------------------------------------
    user_is_partner = fields.Boolean(
        string="Connected User is Partner",
        compute="_compute_user_is_partner",
    )
    stage_is_estimation = fields.Boolean(
        string="Estimation Stage",
        related="stage_id.is_estimation_stage",
    )
    stage_is_approval = fields.Boolean(
        string="Approval Stage",
        related="stage_id.is_approval_stage",
    )

    # Controla la cadencia del recordatorio; lo escribe el cron, el usuario solo lo consulta.
    waiting_reminder_last_date = fields.Datetime(
        string="Last Waiting Reminder",
        readonly=True,
        copy=False,
    )

    @api.depends_context("uid")
    def _compute_user_is_partner(self):
        is_partner = self.env.user.is_partner
        for lead in self:
            lead.user_is_partner = is_partner

    # ==================================================================
    # Utilidades de horas / días hábiles (lunes a viernes, feriados fuera de alcance)
    # ==================================================================
    @staticmethod
    def _next_midnight(moment):
        """Devuelve la medianoche siguiente a `moment`."""
        return (moment + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    @staticmethod
    def _add_business_hours(start_dt, hours):
        """Avanza `hours` desde `start_dt` contando solo tiempo de lun-vier
        (cada día hábil = 24h completas), salteando sábados y domingos."""
        remaining = float(hours)
        current = start_dt
        while remaining > 0:
            if current.weekday() >= SATURDAY:
                days_to_monday = 7 - current.weekday()
                current = (current + timedelta(days=days_to_monday)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                continue
            end_of_day = CrmLead._next_midnight(current)
            available = (end_of_day - current).total_seconds() / 3600.0
            if remaining <= available:
                current = current + timedelta(hours=remaining)
                remaining = 0.0
            else:
                remaining -= available
                current = end_of_day
        return current

    @staticmethod
    def _add_business_days(start_date, days):
        """Suma `days` días hábiles (lun-vier) a una fecha (date)."""
        current = start_date
        added = 0
        while added < days:
            current = current + timedelta(days=1)
            if current.weekday() < SATURDAY:
                added += 1
        return current

    @staticmethod
    def _business_hours_between(start_dt, end_dt):
        """Cuenta las horas hábiles (lun-vier) transcurridas entre dos datetimes."""
        if not start_dt or not end_dt or end_dt <= start_dt:
            return 0.0
        total = 0.0
        current = start_dt
        while current < end_dt:
            segment_end = min(CrmLead._next_midnight(current), end_dt)
            if current.weekday() < SATURDAY:
                total += (segment_end - current).total_seconds() / 3600.0
            current = segment_end
        return total

    # ==================================================================
    # Cálculo de SLA
    # ==================================================================
    def _get_sla_deadline_value(self):
        """Calcula la fecha límite SLA desde la creación usando las horas de la clasificación."""
        self.ensure_one()
        if not self.classification_id:
            return False
        base = self.create_date or fields.Datetime.now()
        return self._add_business_hours(base, self.classification_id.sla_hours)

    def _get_sla_status_value(self, now=None, deadline=None):
        """Devuelve el estado del semáforo según el % de avance hacia la fecha límite."""
        self.ensure_one()
        deadline = deadline or self.sla_deadline
        if not deadline or not self.create_date:
            return False
        now = now or fields.Datetime.now()
        total = (deadline - self.create_date).total_seconds()
        elapsed = (now - self.create_date).total_seconds()
        # total <= 0 evita dividir por cero y ya implica un plazo agotado.
        if total <= 0 or elapsed >= total:
            return SLA_OVERDUE
        if elapsed / total >= SLA_WARNING_RATIO:
            return SLA_WARNING
        return SLA_ON_TIME

    @api.model
    def _get_open_opportunity_domain(self):
        """Oportunidades vigentes: ni archivadas (perdidas) ni en una etapa ganada."""
        return [
            ("active", "=", True),
            ("stage_id.is_won", "=", False),
            ("type", "=", "opportunity"),
        ]

    # ==================================================================
    # Onchange / create / write
    # ==================================================================
    @api.onchange("classification_id")
    def _onchange_classification_id(self):
        if self.classification_id:
            self.sla_deadline = self._get_sla_deadline_value()

    @api.onchange("waiting_customer")
    def _onchange_waiting_customer(self):
        self.waiting_customer_date = (
            fields.Datetime.now() if self.waiting_customer else False
        )

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        for lead in leads:
            lead_vals = {}
            if lead.classification_id and not lead.sla_deadline:
                lead_vals["sla_deadline"] = lead._get_sla_deadline_value()
            deadline = lead_vals.get("sla_deadline") or lead.sla_deadline
            if deadline:
                lead_vals["sla_status"] = lead._get_sla_status_value(deadline=deadline)
            if lead_vals:
                lead.write(lead_vals)
        return leads

    def write(self, vals):
        if "waiting_customer" in vals:
            vals = dict(vals, waiting_reminder_last_date=False)
            vals.setdefault(
                "waiting_customer_date",
                fields.Datetime.now() if vals["waiting_customer"] else False,
            )
        res = super().write(vals)
        if self.env.context.get("sla_skip_refresh"):
            return res
        # Solo se valida al entrar a la etapa, no en cada edición del esfuerzo.
        if "stage_id" in vals:
            self._check_estimation_stage_approval()
        # La fecha límite se recalcula al cambiar la clasificación, salvo que
        # el mismo guardado ya traiga una fecha editada a mano.
        recompute_deadline = "classification_id" in vals and "sla_deadline" not in vals
        if recompute_deadline or "sla_deadline" in vals:
            self._refresh_sla(recompute_deadline)
        return res

    def _refresh_sla(self, recompute_deadline):
        """Actualiza fecha límite y estado en una sola escritura por registro."""
        for lead in self:
            lead_vals = {}
            if recompute_deadline and lead.classification_id:
                lead_vals["sla_deadline"] = lead._get_sla_deadline_value()
            deadline = lead_vals.get("sla_deadline") or lead.sla_deadline
            if deadline:
                lead_vals["sla_status"] = lead._get_sla_status_value(deadline=deadline)
            if lead_vals:
                lead.with_context(sla_skip_refresh=True).write(lead_vals)

    # ==================================================================
    # Botones de aprobación
    # ==================================================================
    def _register_approval(self, date_field, user_field, body):
        """Sella una aprobación con el usuario conectado y la deja en el chatter."""
        self.ensure_one()
        self.write({
            date_field: fields.Datetime.now(),
            user_field: self.env.user.id,
        })
        self.message_post(body=body)

    def action_approve_presales(self):
        self.ensure_one()
        if not self.env.user.is_partner:
            raise UserError(_("Only a partner can approve the DC presales."))
        if float_compare(self.presales_effort_hours, 0, precision_digits=2) <= 0:
            raise UserError(_("Enter the DC presales effort before approving it."))
        self._register_approval(
            "presales_approval_date",
            "presales_approval_user_id",
            _("DC presales approved by %s.", self.env.user.name),
        )

    def action_approve_dc(self):
        self.ensure_one()
        self._register_approval(
            "dc_approval_date",
            "dc_approval_user_id",
            _("DC approval performed by %s.", self.env.user.name),
        )

    # ==================================================================
    # Validaciones (backend, no solo UI)
    # ==================================================================
    def _check_estimation_stage_approval(self):
        """Impide entrar a Estimación con esfuerzo alto sin aprobación de preventa DC."""
        for lead in self:
            over_threshold = float_compare(
                lead.presales_effort_hours, PRESALES_MAX_HOURS, precision_digits=2
            ) > 0
            if (
                lead.stage_id.is_estimation_stage
                and over_threshold
                and not lead.presales_approval_date
            ):
                raise ValidationError(
                    _(
                        "The DC presales effort exceeds %sh: DC presales approval is "
                        "required to move to the Estimation stage.",
                        PRESALES_MAX_HOURS,
                    )
                )

    @api.constrains("stage_id", *INITIAL_STAGE_FIELDS)
    def _check_new_stage_required_fields(self):
        advanced = self.filtered(
            lambda lead: lead.type == "opportunity"
            and lead.stage_id
            and not lead.stage_id.is_new_stage
        )
        # Solo se aplica si el administrador configuró alguna etapa como inicial.
        if not advanced or not self.env["crm.stage"].search_count(
            [("is_new_stage", "=", True)]
        ):
            return
        # fields_get devuelve las etiquetas ya traducidas al idioma del usuario;
        labels = self.fields_get(INITIAL_STAGE_FIELDS, ["string"])
        for lead in advanced:
            missing = [
                labels[field_name]["string"]
                for field_name in INITIAL_STAGE_FIELDS
                if not lead[field_name]
            ]
            if missing:
                raise ValidationError(
                    _(
                        "The stage cannot be advanced without completing: %s.",
                        ", ".join(missing),
                    )
                )

    def _committed_date_is_required(self):
        """La fecha comprometida se exige en clasificaciones complejas de SLA alto
        o cuando el esfuerzo aprobado excede el SLA de la clasificación."""
        self.ensure_one()
        classification = self.classification_id
        if not classification:
            return False
        if (
            classification.complexity == "compleja"
            and classification.sla_hours > COMPLEX_SLA_HOURS
        ):
            return True
        return bool(self.presales_approval_date) and float_compare(
            self.presales_effort_hours, classification.sla_hours, precision_digits=2
        ) > 0

    @api.constrains(
        "committed_date",
        "classification_id",
        "presales_effort_hours",
        "presales_approval_date",
    )
    def _check_committed_date(self):
        for lead in self.filtered(lambda rec: rec.type == "opportunity"):
            if lead._committed_date_is_required() and not lead.committed_date:
                raise ValidationError(
                    _(
                        "The date committed to the customer is mandatory for this "
                        "Classification/DC presales effort."
                    )
                )
            if lead.committed_date and lead.create_date:
                max_date = lead._add_business_days(
                    lead.create_date.date(), COMMITTED_MAX_DAYS
                )
                if lead.committed_date > max_date:
                    raise ValidationError(
                        _(
                            "The committed date cannot exceed %s business days from "
                            "creation (maximum %s).",
                            COMMITTED_MAX_DAYS,
                            max_date.strftime("%d-%m-%Y"),
                        )
                    )

    # ==================================================================
    # Crons
    # ==================================================================
    @api.model
    def _cron_update_sla_status(self):
        """Recalcula el semáforo SLA de las oportunidades abiertas no en espera."""
        now = fields.Datetime.now()
        leads = self.search(
            self._get_open_opportunity_domain()
            + [("waiting_customer", "=", False), ("sla_deadline", "!=", False)]
        )
        ids_by_status = defaultdict(list)
        for lead in leads:
            status = lead._get_sla_status_value(now)
            if status and lead.sla_status != status:
                ids_by_status[status].append(lead.id)
        for status, lead_ids in ids_by_status.items():
            self.browse(lead_ids).write({"sla_status": status})

    @api.model
    def _cron_waiting_customer_reminder(self):
        """Avisa al comercial apenas la oportunidad queda en espera de cliente y
        luego repite el recordatorio cada 48h hábiles mientras siga en espera."""
        view = self.env.ref(
            "crm_sla_traceability.message_waiting_customer_reminder",
            raise_if_not_found=False,
        )
        if not view:
            return
        now = fields.Datetime.now()
        leads = self.search(
            self._get_open_opportunity_domain()
            + [("waiting_customer", "=", True), ("user_id", "!=", False)]
        )
        model_description = self.env["ir.model"]._get(self._name).display_name
        render_mixin = self.env["mail.render.mixin"]
        for lead in leads:
            last = lead.waiting_reminder_last_date
            if last and lead._business_hours_between(last, now) < REMINDER_HOURS:
                continue
            body = view._render(
                {
                    "object": lead,
                    "access_link": lead._notify_get_action_link("view"),
                },
                engine="ir.qweb",
                minimal_qcontext=True,
            )
            message = lead.message_notify(
                subject=_("Opportunity waiting for customer: %s", lead.name),
                body=render_mixin._replace_local_links(body),
                partner_ids=lead.user_id.partner_id.ids,
                record_name=lead.display_name,
                email_layout_xmlid="mail.mail_notification_light",
                model_description=model_description,
            )
            message.sudo().mail_ids.send()
            lead.waiting_reminder_last_date = now

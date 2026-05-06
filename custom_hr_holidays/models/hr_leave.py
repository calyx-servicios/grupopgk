from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
import calendar
from datetime import timedelta, datetime, date
from dateutil.relativedelta import relativedelta


class HrLeave(models.Model):
    _inherit = "hr.leave"

    job_id = fields.Many2one(
        "hr.job",
        related="employee_id.job_id",
        string="Job Position",
        readonly=True,
        store=True,
        tracking=True,
    )

    days_remaining = fields.Float(related="holiday_status_id.virtual_remaining_leaves", string="Days Remaining")

    today = fields.Date(
        string="Today", default=lambda self: fields.Date.today(), readonly=True
    )

    @api.depends("date_from", "date_to", "employee_id")
    def _compute_number_of_days(self):
        super(HrLeave, self)._compute_number_of_days()
        for holiday in self:
            if holiday.date_from and holiday.date_to:
                # Verificar si consecutive_days es True
                if holiday.holiday_status_id.consecutive_days:
                    delta = holiday.date_to - holiday.date_from
                    holiday.number_of_days = (
                        delta.days + 1
                    )  # +1 para incluir ambos días
                else:
                    pass
            else:
                pass

    @api.model_create_multi
    def create(self, vals_list):
        should_check_mudanza_quota = not self.env.user.has_group(
            "hr_holidays.group_hr_holidays_manager"
        )
        if not self.env.user.has_group("hr_holidays.group_hr_holidays_manager"):
            for vals in vals_list:
                holiday_status_id = vals.get("holiday_status_id")
                if not holiday_status_id:
                    continue
                holiday_status = self.env["hr.leave.type"].browse(holiday_status_id)
                # Reglas personalizadas solo para vacaciones.
                if not self._is_vacation_leave_type(holiday_status):
                    continue
                self.check_date_range([vals])
                self.check_start_day([vals])
        leaves = super(HrLeave, self).create(vals_list)
        leaves._check_mudanza_company_context()
        if should_check_mudanza_quota:
            leaves._check_mudanza_available_days()
        return leaves

    def write(self, vals):
        should_check_mudanza_quota = not self.env.user.has_group(
            "hr_holidays.group_hr_holidays_manager"
        )
        result = super(HrLeave, self).write(vals)
        self._check_mudanza_company_context()
        if should_check_mudanza_quota:
            self._check_mudanza_available_days()
        return result

    def _is_vacation_leave_type(self, holiday_status):
        name = (holiday_status.name or "").lower()
        return holiday_status.time_type == "other" and "vacacion" in name

    def _is_mudanza_leave(self):
        self.ensure_one()
        name = (self.holiday_status_id.name or "").lower()
        return self.holiday_status_id.requires_allocation == "no" and "mudanza" in name

    def _check_mudanza_company_context(self):
        allowed_company_ids = set(
            self.env.context.get("allowed_company_ids") or self.env.companies.ids
        )
        for leave in self:
            if (
                leave.holiday_type != "employee"
                or not leave.employee_id
                or not leave._is_mudanza_leave()
            ):
                continue

            employee_company = leave.employee_id._get_holidays_reference_company()
            if not employee_company:
                continue

            if not leave.employee_id._is_holidays_company_allowed(employee_company):
                raise ValidationError(
                    _(
                        "El empleado no pertenece a la empresa configurada para esta ausencia."
                    )
                )

            if employee_company.id not in allowed_company_ids:
                raise ValidationError(
                    _(
                        "No puede registrar días de mudanza fuera de la empresa del empleado."
                    )
                )

            if (
                leave.holiday_status_id.company_id
                and leave.holiday_status_id.company_id != employee_company
            ):
                raise ValidationError(
                    _(
                        "El tipo de ausencia de mudanza no pertenece a la empresa del empleado."
                    )
                )

    def _check_mudanza_available_days(self):
        for leave in self:
            if (
                leave.holiday_type != "employee"
                or not leave.employee_id
                or leave.state not in ["confirm", "validate1", "validate"]
                or not leave._is_mudanza_leave()
            ):
                continue

            employee_company = leave.employee_id._get_holidays_reference_company()
            if not employee_company:
                continue

            leave_date = leave.date_from.date() if leave.date_from else fields.Date.context_today(self)
            year_start = leave_date.replace(month=1, day=1)
            year_end = leave_date.replace(month=12, day=31)
            next_year_start = year_end + timedelta(days=1)

            consumed_days = self.env["hr.leave"].search(
                [
                    ("id", "!=", leave.id),
                    ("employee_id", "=", leave.employee_id.id),
                    ("employee_id.company_id", "=", employee_company.id),
                    ("holiday_status_id", "=", leave.holiday_status_id.id),
                    ("holiday_status_id.company_id", "in", [False, employee_company.id]),
                    ("state", "in", ["confirm", "validate1", "validate"]),
                    ("date_from", ">=", fields.Datetime.to_datetime(year_start)),
                    ("date_from", "<", fields.Datetime.to_datetime(next_year_start)),
                ]
            ).mapped("number_of_days")
            available_days = max(2.0 - sum(consumed_days), 0.0)
            if leave.number_of_days > available_days:
                raise ValidationError(
                    _(
                        "Solo dispone de %s día(s) de mudanza en el año."
                    )
                    % round(available_days, 2)
                )

    def check_start_day(self, vals_list):
        # Mapeo de los días de la semana de inglés a español
        day_map = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        for vals in vals_list:
            holiday_status_id = vals.get("holiday_status_id")
            date_from = vals.get("date_from")

            holiday_status = self.env["hr.leave.type"].search(
                [
                    ("id", "=", holiday_status_id),
                    ("time_type", "=", "other"),
                ]
            )
            if holiday_status and date_from:
                start_date = holiday_status.assign_start_date

                # Obtener el día de la semana de date_from (0=Monday, 6=Sunday)
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d %H:%M:%S").date()
                day_of_week = date_from_obj.weekday()

                assign_start_day = day_map[start_date.lower()]

                result = self.check_date_from(date_from)
                # Verificar si el día de inicio es el mismo que assign_start_date
                day = start_date.capitalize()
                if not result and day_of_week != assign_start_day:
                    raise ValidationError(_('The start date of the holiday must be a {}.'.format(day)))
                else:
                    pass

    def check_date_range(self, vals_list):
        for vals in vals_list:
            holiday_status_id = vals.get("holiday_status_id", False)
            holiday_status = self.env["hr.leave.type"].browse(holiday_status_id)
            date_from = vals.get("date_from", False)
            date_from_obj = datetime.strptime(date_from, "%Y-%m-%d %H:%M:%S").date()
            date_to = vals.get("date_to", False)
            date_to_obj = datetime.strptime(date_to, "%Y-%m-%d %H:%M:%S").date()
            employee_id = vals.get("employee_id", False)
            number_of_days = vals.get("number_of_days", False)

            correct_allocation = self.check_correct_allocation(
                holiday_status_id, employee_id
            )

            allocation = self.env["hr.leave.allocation"].search(
                [
                    ("holiday_status_id", "=", holiday_status_id),
                    ("employee_id", "=", employee_id),
                    ("state", "=", "validate"),
                ]
            )
            if allocation:
                for alloc in allocation:
                    alloc_date_from = alloc.date_from
                    alloc_date_to = alloc.date_to

                    if (
                        alloc_date_from
                        and alloc_date_to
                        and date_from_obj
                        and date_to_obj
                    ):
                        if (
                            date_from_obj >= alloc_date_from
                            and date_to_obj <= alloc_date_to
                        ):
                            # Verificar que la cantidad de dias pedidos no son mas que los asignados
                            if number_of_days <= alloc.number_of_days:
                                # Verificar si el número de días solicitados es un múltiplo de 7
                                if alloc.number_of_days >= 14:
                                    if int(number_of_days) not in range(
                                        7, int(alloc.number_of_days) + 1, 7
                                    ):
                                        raise ValidationError(
                                            "Los días solicitados deben ser en bloques de 7 días"
                                        )
                                elif number_of_days != alloc.number_of_days:
                                    raise ValidationError(
                                        _("Debe tomar exactamente %s días.")
                                        % int(alloc.number_of_days)
                                    )
                            else:
                                raise ValidationError(
                                    _("Superó los %s días que tiene disponibles.")
                                    % int(alloc.number_of_days)
                                )
                        else:
                            raise ValidationError(
                                _("El rango de fechas debe estar entre %s y %s.")
                                % (alloc_date_from, alloc_date_to)
                            )
                    else:
                        pass
            else:
                raise ValidationError(_("No validated assignments found"))

    def check_correct_allocation(self, holiday_status_id, employee_id):
        all_allocation = self.env["hr.leave.allocation"].search(
            [("employee_id", "=", employee_id), ("state", "=", "validate")]
        )

        # Filtrar la asignación que tiene first_end en True
        correct_allocation = next(
            (
                alloc
                for alloc in all_allocation
                if alloc.holiday_status_id.first_end
                and alloc.holiday_status_id.virtual_remaining_leaves > 0
            ),
            None,
        )

        if (
            correct_allocation
            and correct_allocation.holiday_status_id.id != holiday_status_id
        ):
            raise ValidationError(
                f"Usted tiene {correct_allocation.holiday_status_id.name} antes que las seleccionadas."
            )

        else:
            pass

    def check_date_from(self, date_from):
        # Verificamos que la fecha de inicio si no es lunes que se fije que ese lunes no es feriado.
        # Por ejemplo la fecha de inicio es un martes y el lunes anterior es feriado, en ese caso debe dejar cargar vacaciones
        calendar_holidays = self.env["calendar.holidays.timesheets"].search([])
        date_from_obj = datetime.strptime(
            date_from, "%Y-%m-%d %H:%M:%S"
        ).date() - timedelta(days=1)
        all_holiday_dates = []
        for holiday in calendar_holidays:
            holiday_start_date = (
                holiday.start_date.date()
                if isinstance(holiday.start_date, datetime)
                else holiday.start_date
            )
            if holiday_start_date == date_from_obj:
                return True

        return False



from datetime import timedelta

from odoo import _, api, fields, models


class HrLeaveType(models.Model):
    _inherit = "hr.leave.type"

    assign_start_date = fields.Selection([
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday')
    ], string="Assign Start Date")

    consecutive_days = fields.Boolean(string="Consecutive Days", default=True)
    first_end = fields.Boolean(string="First end", default=False)

    def _format_display_value(self, value):
        return ("%.2f" % value).rstrip("0").rstrip(".")

    def _get_manual_balance_date(self):
        return (
            fields.Date.to_date(self.env.context.get("default_date_from"))
            or fields.Date.context_today(self)
        )

    def _get_leave_period(self, leave):
        return fields.Date.to_date(leave.date_from), fields.Date.to_date(leave.date_to)

    def _periods_overlap(self, start_date, end_date, period_start, period_end):
        return start_date <= period_end and end_date >= period_start

    def _empty_leave_metrics(self):
        return {
            "max_leaves": 0.0,
            "leaves_taken": 0.0,
            "remaining_leaves": 0.0,
            "virtual_remaining_leaves": 0.0,
            "virtual_leaves_taken": 0.0,
        }

    def _uses_period_balance(self):
        self.ensure_one()
        return (
            self.requires_allocation == "no"
            or "estudio" in (self.name or "").lower()
        )

    def _get_employee_balance_metrics(self, employee_id, balance_date=None):
        self.ensure_one()
        balance_date = fields.Date.to_date(balance_date)
        context = {"employee_id": employee_id}
        if balance_date:
            context["default_date_from"] = balance_date

        leave_type = self.with_context(**context)
        manual_metrics = leave_type._get_manual_allocation_metrics(employee_id).get(self.id)
        if manual_metrics:
            return manual_metrics

        data_days = leave_type.get_employees_days([employee_id], date=balance_date)
        return data_days.get(employee_id, {}).get(self.id, self._empty_leave_metrics())

    def _get_manual_allocation_metrics(self, employee_id):
        """Compute period balances for leave types handled by PGK rules.

        This is used to display balances in dashboard and leave type selector
        when business rules need annual allocation-period balances.
        """
        if not employee_id or not self:
            return {}

        employee = self.env["hr.employee"].browse(employee_id)
        employee_company = employee._get_holidays_reference_company()
        if not employee_company:
            return {}

        allowed_company_ids = set(
            self.env.context.get("allowed_company_ids") or self.env.companies.ids
        )
        if employee_company.id not in allowed_company_ids:
            return {}

        leave_types = self.filtered(
            lambda lt: not lt.company_id or lt.company_id == employee_company
        )
        leave_types = leave_types.filtered(lambda lt: lt._uses_period_balance())
        if not leave_types:
            return {}

        balance_date = self._get_manual_balance_date()
        year_start = balance_date.replace(month=1, day=1)
        year_end = balance_date.replace(month=12, day=31)
        next_year_start = year_end + timedelta(days=1)

        allocation_domain = [
            ("holiday_status_id", "in", leave_types.ids),
            ("holiday_status_id.company_id", "in", [False, employee_company.id]),
            ("employee_id", "=", employee_id),
            ("employee_id.company_id", "=", employee_company.id),
            ("state", "=", "validate"),
            ("active", "=", True),
            ("date_from", "<=", year_end),
            "|",
            ("date_to", "=", False),
            ("date_to", ">=", year_start),
        ]
        allocations = self.env["hr.leave.allocation"].search(allocation_domain)

        fallback_quota_by_type = {}
        for leave_type in leave_types.filtered(lambda lt: lt.requires_allocation == "no"):
            # Regla de negocio PGK: mudanza tiene 2 dias por anio aunque no haya asignacion.
            if "mudanza" in (leave_type.name or "").lower():
                fallback_quota_by_type[leave_type.id] = 2.0

        allocations_by_type = {}
        max_by_type = {}
        for allocation in allocations:
            leave_type_id = allocation.holiday_status_id.id
            allocations_by_type.setdefault(leave_type_id, self.env["hr.leave.allocation"])
            allocations_by_type[leave_type_id] |= allocation
            max_by_type[leave_type_id] = (
                max_by_type.get(leave_type_id, 0.0) + allocation.number_of_days
            )
        for leave_type_id, fallback_quota in fallback_quota_by_type.items():
            max_by_type.setdefault(leave_type_id, fallback_quota)

        if not max_by_type:
            return {}

        leave_domain_common = [
            ("holiday_status_id", "in", list(max_by_type)),
            ("holiday_status_id.company_id", "in", [False, employee_company.id]),
            ("employee_id", "=", employee_id),
            ("employee_id.company_id", "=", employee_company.id),
            ("date_from", "<", fields.Datetime.to_datetime(next_year_start)),
            ("date_to", ">=", fields.Datetime.to_datetime(year_start)),
        ]

        virtual_leaves = self.env["hr.leave"].search(
            leave_domain_common + [("state", "in", ["confirm", "validate1", "validate"])],
        )
        taken_leaves = self.env["hr.leave"].search(
            leave_domain_common + [("state", "=", "validate")],
        )

        virtual_taken_by_type = self._sum_manual_leaves_by_type(
            virtual_leaves, allocations_by_type, year_start, year_end
        )
        taken_by_type = self._sum_manual_leaves_by_type(
            taken_leaves, allocations_by_type, year_start, year_end
        )

        metrics = {}
        for leave_type_id, max_leaves in max_by_type.items():
            virtual_taken = virtual_taken_by_type.get(leave_type_id, 0.0)
            leaves_taken = taken_by_type.get(leave_type_id, 0.0)
            virtual_remaining = max(max_leaves - virtual_taken, 0.0)
            remaining = max(max_leaves - leaves_taken, 0.0)
            metrics[leave_type_id] = {
                "max_leaves": max_leaves,
                "virtual_leaves_taken": virtual_taken,
                "leaves_taken": leaves_taken,
                "virtual_remaining_leaves": virtual_remaining,
                "remaining_leaves": remaining,
            }
        return metrics

    def _sum_manual_leaves_by_type(
        self, leaves, allocations_by_type, year_start, year_end
    ):
        taken_by_type = {}
        for leave in leaves:
            leave_type_id = leave.holiday_status_id.id
            allocation_periods = allocations_by_type.get(leave_type_id)
            leave_start, leave_end = self._get_leave_period(leave)

            if allocation_periods:
                has_matching_period = any(
                    self._periods_overlap(
                        leave_start,
                        leave_end,
                        allocation.date_from,
                        allocation.date_to or year_end,
                    )
                    for allocation in allocation_periods
                )
            else:
                has_matching_period = self._periods_overlap(
                    leave_start, leave_end, year_start, year_end
                )

            if has_matching_period:
                taken_by_type[leave_type_id] = (
                    taken_by_type.get(leave_type_id, 0.0) + leave.number_of_days
                )

        return taken_by_type

    def _manual_days_request_data(self, values):
        self.ensure_one()
        return {
            "remaining_leaves": self._format_display_value(values["remaining_leaves"]),
            "usable_remaining_leaves": self._format_display_value(values["virtual_remaining_leaves"]),
            "virtual_remaining_leaves": self._format_display_value(values["virtual_remaining_leaves"]),
            "max_leaves": self._format_display_value(values["max_leaves"]),
            "leaves_taken": self._format_display_value(values["leaves_taken"]),
            "virtual_leaves_taken": self._format_display_value(values["virtual_leaves_taken"]),
            "request_unit": self.request_unit,
            "icon": self.sudo().icon_id.url,
        }

    @api.model
    def get_days_all_request(self):
        result = super().get_days_all_request()
        employee_id = self._get_contextual_employee_id()
        if not employee_id:
            return result

        employee = self.env["hr.employee"].browse(employee_id)
        employee_company = employee._get_holidays_reference_company()
        if not employee_company:
            return result

        allowed_company_ids = set(
            self.env.context.get("allowed_company_ids") or self.env.companies.ids
        )
        if employee_company.id not in allowed_company_ids:
            return []

        all_types = self.search([
            "|",
            ("company_id", "=", False),
            ("company_id", "=", employee_company.id),
        ])
        manual_metrics = all_types._get_manual_allocation_metrics(employee_id)

        merged = {item[3]: item for item in result if item[3] in all_types.ids}
        for leave_type in all_types:
            metrics = manual_metrics.get(leave_type.id)
            if metrics:
                merged[leave_type.id] = (
                    leave_type.name,
                    leave_type._manual_days_request_data(metrics),
                    "yes",
                    leave_type.id,
                )
            elif leave_type.id not in merged:
                merged[leave_type.id] = leave_type._get_days_request()

        ordered_types = sorted(all_types, key=self._model_sorting_key, reverse=True)
        return [merged[leave_type.id] for leave_type in ordered_types if leave_type.id in merged]

    def name_get(self):
        names = dict(super().name_get())
        employee_id = self._context.get("employee_id") or self._context.get("default_employee_id")
        if not employee_id:
            return [(record.id, names.get(record.id, record.name)) for record in self]

        employee = self.env["hr.employee"].browse(employee_id)
        employee_company = employee._get_holidays_reference_company()
        if not employee_company:
            return []

        allowed_company_ids = set(
            self.env.context.get("allowed_company_ids") or self.env.companies.ids
        )
        if employee_company.id not in allowed_company_ids:
            return []

        allowed_records = self.filtered(
            lambda record: not record.company_id or record.company_id == employee_company
        )

        manual_metrics = allowed_records._get_manual_allocation_metrics(employee_id)
        for record in allowed_records:
            metrics = manual_metrics.get(record.id)
            if not metrics or self._context.get("from_manager_leave_form"):
                continue

            names[record.id] = "%(name)s (%(count)s)" % {
                "name": record.name,
                "count": _("%g remaining out of %g")
                % (
                    round(metrics["virtual_remaining_leaves"], 2) or 0.0,
                    round(metrics["max_leaves"], 2) or 0.0,
                )
                + (_(" hours") if record.request_unit == "hour" else _(" days")),
            }

        return [(record.id, names.get(record.id, record.name)) for record in self]

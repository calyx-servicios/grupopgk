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

    def _get_manual_allocation_metrics(self, employee_id):
        """Compute per-type allocation balances for leave types without allocation requirement.

        This is used to display balances in dashboard and leave type selector
        (eg. mudanza) when business rules still use annual allocations.
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
        if not leave_types:
            return {}

        today = fields.Date.context_today(self)
        year_start = today.replace(month=1, day=1)
        year_end = today.replace(month=12, day=31)
        next_year_start = year_end + timedelta(days=1)

        allocation_domain = [
            ("holiday_status_id", "in", leave_types.ids),
            ("holiday_status_id.requires_allocation", "=", "no"),
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
        grouped_allocations = self.env["hr.leave.allocation"].read_group(
            allocation_domain,
            ["holiday_status_id", "number_of_days:sum"],
            ["holiday_status_id"],
            lazy=False,
        )

        fallback_quota_by_type = {}
        for leave_type in leave_types.filtered(lambda lt: lt.requires_allocation == "no"):
            # Regla de negocio PGK: mudanza tiene 2 dias por anio aunque no haya asignacion.
            if "mudanza" in (leave_type.name or "").lower():
                fallback_quota_by_type[leave_type.id] = 2.0

        max_by_type = {
            group["holiday_status_id"][0]: group["number_of_days"]
            for group in grouped_allocations
            if group.get("holiday_status_id")
        }
        for leave_type_id, fallback_quota in fallback_quota_by_type.items():
            max_by_type.setdefault(leave_type_id, fallback_quota)

        if not max_by_type:
            return {}

        leave_domain_common = [
            ("holiday_status_id", "in", list(max_by_type)),
            ("holiday_status_id.company_id", "in", [False, employee_company.id]),
            ("employee_id", "=", employee_id),
            ("employee_id.company_id", "=", employee_company.id),
            ("date_from", ">=", fields.Datetime.to_datetime(year_start)),
            ("date_from", "<", fields.Datetime.to_datetime(next_year_start)),
        ]

        grouped_virtual_taken = self.env["hr.leave"].read_group(
            leave_domain_common + [("state", "in", ["confirm", "validate1", "validate"])],
            ["holiday_status_id", "number_of_days:sum"],
            ["holiday_status_id"],
            lazy=False,
        )
        grouped_taken = self.env["hr.leave"].read_group(
            leave_domain_common + [("state", "=", "validate")],
            ["holiday_status_id", "number_of_days:sum"],
            ["holiday_status_id"],
            lazy=False,
        )

        virtual_taken_by_type = {
            group["holiday_status_id"][0]: group["number_of_days"]
            for group in grouped_virtual_taken
            if group.get("holiday_status_id")
        }
        taken_by_type = {
            group["holiday_status_id"][0]: group["number_of_days"]
            for group in grouped_taken
            if group.get("holiday_status_id")
        }

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
        if not manual_metrics:
            return [item for item in result if item[3] in all_types.ids]

        merged = {item[3]: item for item in result if item[3] in all_types.ids}
        for leave_type in all_types:
            metrics = manual_metrics.get(leave_type.id)
            if not metrics:
                continue
            merged[leave_type.id] = (
                leave_type.name,
                leave_type._manual_days_request_data(metrics),
                "yes",
                leave_type.id,
            )

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

        return [(record.id, names.get(record.id, record.name)) for record in allowed_records]

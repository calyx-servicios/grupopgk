from datetime import datetime

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("custom_hr_holidays", "post_install", "-at_install")
class TestLeaveTypeBalances(TransactionCase):

    def setUp(self):
        super().setUp()
        self.employee = self.env["hr.employee"].create({
            "name": "Cartolin Diaz Jorge Alexander",
            "company_id": self.env.company.id,
        })

    def _create_leave_type(self, name, requires_allocation="no"):
        return self.env["hr.leave.type"].create({
            "name": name,
            "requires_allocation": requires_allocation,
            "leave_validation_type": "hr",
            "company_id": self.env.company.id,
        })

    def _create_allocation(self, leave_type, days, date_from, date_to):
        return self.env["hr.leave.allocation"].create({
            "name": leave_type.name,
            "employee_id": self.employee.id,
            "holiday_status_id": leave_type.id,
            "number_of_days": days,
            "state": "validate",
            "date_from": date_from,
            "date_to": date_to,
        })

    def _create_leave(self, leave_type, date_from, date_to, days):
        return self.env["hr.leave"].create({
            "name": leave_type.name,
            "holiday_type": "employee",
            "employee_id": self.employee.id,
            "holiday_status_id": leave_type.id,
            "date_from": date_from,
            "date_to": date_to,
            "number_of_days": days,
            "state": "validate",
        })

    def test_study_leave_balance_uses_selected_year_and_allocation_period(self):
        study_leave_type = self._create_leave_type(
            "Dia de estudio (EA)", requires_allocation="yes"
        )
        allocation = self._create_allocation(
            study_leave_type,
            10,
            "2026-02-05",
            "2026-12-31",
        )
        self._create_leave(
            study_leave_type,
            datetime(2025, 9, 8, 0, 0, 0),
            datetime(2025, 9, 11, 23, 59, 59),
            4,
        )
        leave_2026 = self._create_leave(
            study_leave_type,
            datetime(2026, 9, 8, 0, 0, 0),
            datetime(2026, 9, 11, 23, 59, 59),
            4,
        )

        study_leave_type = study_leave_type.with_context(
            employee_id=self.employee.id,
            default_date_from="2026-01-01",
        )
        metrics = study_leave_type._get_manual_allocation_metrics(self.employee.id)[study_leave_type.id]

        self.assertEqual(metrics["max_leaves"], 10)
        self.assertEqual(metrics["leaves_taken"], 4)
        self.assertEqual(metrics["virtual_remaining_leaves"], 6)
        self.assertEqual(allocation.days_remaining, 6)
        self.assertEqual(leave_2026.days_remaining, 6)

        dashboard_item = next(
            item for item in study_leave_type.get_days_all_request()
            if item[3] == study_leave_type.id
        )
        self.assertEqual(dashboard_item[1]["max_leaves"], "10")
        self.assertEqual(dashboard_item[1]["virtual_leaves_taken"], "4")
        self.assertEqual(dashboard_item[1]["virtual_remaining_leaves"], "6")
        self.assertEqual(dashboard_item[2], "yes")

    def test_mudanza_fallback_quota_still_uses_selected_year(self):
        moving_leave_type = self._create_leave_type("Dia de Mudanza (EA)")
        self._create_leave(
            moving_leave_type,
            datetime(2025, 6, 2, 0, 0, 0),
            datetime(2025, 6, 2, 23, 59, 59),
            1,
        )
        self._create_leave(
            moving_leave_type,
            datetime(2026, 6, 2, 0, 0, 0),
            datetime(2026, 6, 2, 23, 59, 59),
            1,
        )

        metrics = moving_leave_type.with_context(
            employee_id=self.employee.id,
            default_date_from="2026-01-01",
        )._get_manual_allocation_metrics(self.employee.id)[moving_leave_type.id]

        self.assertEqual(metrics["max_leaves"], 2)
        self.assertEqual(metrics["leaves_taken"], 1)
        self.assertEqual(metrics["virtual_remaining_leaves"], 1)
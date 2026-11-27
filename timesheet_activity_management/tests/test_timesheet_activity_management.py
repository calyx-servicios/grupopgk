import base64
from datetime import datetime

import pytz

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTimesheetActivityManagement(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env["hr.employee"].create({
            "name": "Management report worker",
            "company_id": cls.env.company.id,
        })
        cls.project = cls.env["project.project"].create({
            "name": "Management report project",
            "allow_timesheets": True,
            "privacy_visibility": "employees",
            "partner_id": cls.env["res.partner"].create({
                "name": "Management report client",
            }).id,
        })
        cls.management_type = cls.env.ref(
            "timesheet_activity_management.hour_type_management"
        )
        cls.support_type = cls.env.ref(
            "timesheet_activity_management.hour_type_support"
        )

    def _create_line(self, **overrides):
        values = {
            "name": "Internal coordination",
            "project_id": self.project.id,
            "employee_id": self.employee.id,
            "unit_amount": 1.0,
            "hour_type_id": self.management_type.id,
            "activity_date": fields.Date.today(),
        }
        values.update(overrides)
        return self.env["account.analytic.line"].sudo().create(values)

    def test_new_hours_require_type_and_activity_date(self):
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self._create_line(hour_type_id=False)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self._create_line(activity_date=False)

    def test_management_hours_require_meaningful_description(self):
        for name in (False, "", "   ", "/"):
            with self.subTest(name=name):
                with self.assertRaises(ValidationError), self.env.cr.savepoint():
                    self._create_line(name=name)

    def test_support_hours_do_not_require_management_justification(self):
        line = self._create_line(
            name="/",
            hour_type_id=self.support_type.id,
        )
        self.assertEqual(line.hour_type_id, self.support_type)

    def test_negative_adjustments_are_classified_and_reported(self):
        line = self._create_line(unit_amount=-0.5)
        report_line = self.env["timesheet.management.report"].sudo().search([
            ("id", "=", line.id),
        ])
        self.assertEqual(report_line.unit_amount, -0.5)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self._create_line(unit_amount=-0.5, hour_type_id=False)

    def test_historical_metadata_can_be_completed_by_editing(self):
        line = self._create_line()
        line.write({"name": "Corrected activity description"})
        self.assertEqual(line.name, "Corrected activity description")

    def test_archived_type_cannot_be_selected_for_a_new_line(self):
        self.support_type.active = False
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self._create_line(hour_type_id=self.support_type.id)

    def test_report_exposes_current_project_dimensions_without_duplicate_rows(self):
        functional = self.env["res.users"].create({
            "name": "Functional reviewer",
            "login": "management_functional_reviewer",
            "groups_id": [(6, 0, self.env.ref("base.group_user").ids)],
        })
        self.project.workflow_functional_ids = [(6, 0, functional.ids)]
        self.project.technical_leader_id = self.env.user
        line = self._create_line()
        report = self.env["timesheet.management.report"].sudo().search([
            ("id", "=", line.id),
        ])
        self.assertEqual(len(report), 1)
        self.assertEqual(report.project_id, self.project)
        self.assertEqual(report.client_id, self.project.partner_id)
        self.assertIn(functional, report.functional_user_ids)
        self.assertEqual(report.unit_amount, line.unit_amount)
        filtered_report = self.env["timesheet.management.report"].sudo().search([
            ("functional_user_ids", "in", functional.id),
        ])
        self.assertIn(line.id, filtered_report.ids)

    def test_week_range_is_previous_local_monday_to_sunday(self):
        local_now = pytz.timezone(
            "America/Argentina/Buenos_Aires"
        ).localize(datetime(2026, 10, 14, 12, 0))
        self.assertEqual(
            self.env["timesheet.management.weekly.run"]._previous_week_range(
                local_now
            ),
            (
                fields.Date.to_date("2026-10-05"),
                fields.Date.to_date("2026-10-11"),
            ),
        )

    def test_excel_is_generated_as_an_xlsx_attachment(self):
        line = self._create_line()
        report_line = self.env["timesheet.management.report"].sudo().browse(
            line.id
        )
        filename, content = (
            self.env["timesheet.management.weekly.run"].sudo()._render_xlsx(
                report_line,
                fields.Date.today(),
                fields.Date.today(),
            )
        )
        self.assertTrue(filename.endswith(".xlsx"))
        self.assertTrue(base64.b64decode(content).startswith(b"PK"))

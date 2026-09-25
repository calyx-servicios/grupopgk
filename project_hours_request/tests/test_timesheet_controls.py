from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install")
class TestTimesheetControls(TransactionCase):
    """Verify task-stage and planned-hour timesheet controls."""

    @classmethod
    def setUpClass(cls):
        """Create users, stages, a project, and controlled tasks."""
        super().setUpClass()
        cls.tech_lead = new_test_user(
            cls.env,
            login="hours_tech_lead",
            groups=(
                "project.group_project_user,"
                "hr_timesheet.group_hr_timesheet_user"
            ),
        )
        cls.worker = new_test_user(
            cls.env,
            login="hours_worker",
            groups=(
                "project.group_project_user,"
                "hr_timesheet.group_hr_timesheet_user,hr.group_hr_user"
            ),
        )
        cls.approver = new_test_user(
            cls.env,
            login="hours_approver",
            groups=(
                "project.group_project_user,"
                "project_hours_request.group_project_hours_request_contratos"
            ),
        )
        cls.employee = cls.env["hr.employee"].create({
            "name": "Hours Worker",
            "user_id": cls.worker.id,
        })
        cls.project = cls.env["project.project"].create({
            "name": "Timesheet Controls",
            "allow_timesheets": True,
            "privacy_visibility": "employees",
            "technical_leader_id": cls.tech_lead.id,
        })
        cls.pending_stage = cls._create_stage("Pendiente", "pending")
        cls.dev_stage = cls._create_stage("Desarrollo", "development")
        cls.staging_stage = cls._create_stage("Deploy Staging", "deploy")
        cls.production_stage = cls._create_stage(
            "Deploy Producción",
            "deploy",
        )
        cls.test_stage = cls._create_stage("Pruebas", "functional_test")
        cls.done_stage = cls._create_stage("Finalizada", "done")
        cls.task = cls.env["project.task"].with_user(cls.tech_lead).create({
            "name": "Development card",
            "description": "Context and development acceptance criteria.",
            "project_id": cls.project.id,
            "stage_id": cls.dev_stage.id,
            "task_type": "development",
            "estimated_dev_hours": 2.0,
            "estimated_deploy_hours": 1.0,
            "estimated_functional_test_hours": 1.0,
            "margin_hours": 1.0,
        })

    @classmethod
    def _create_stage(cls, name, stage_type):
        """Create a stage explicitly classified for timesheet controls."""
        return cls.env["project.task.type"].create({
            "name": name,
            "timesheet_stage_type": stage_type,
            "task_type_scope": "development",
            "project_ids": [(6, 0, cls.project.ids)],
        })

    def _create_timesheet(self, task, hours):
        """Create a worker timesheet line on the supplied task."""
        return self.env["account.analytic.line"].with_user(
            self.worker
        ).create({
            "name": "Controlled work",
            "project_id": self.project.id,
            "task_id": task.id,
            "employee_id": self.employee.id,
            "unit_amount": hours,
        })

    def test_pending_and_done_stages_block_timesheets(self):
        """Pending and finalized tasks reject new timesheet lines."""
        self.task.stage_id = self.pending_stage
        with self.assertRaises(UserError):
            self._create_timesheet(self.task, 0.5)

    def test_request_wizard_opens_when_task_has_no_stage(self):
        """A missing task stage leaves the request segment unselected."""
        self.task.stage_id = False

        action = self.task.action_open_hours_request_wizard()

        self.assertFalse(action["context"]["default_segment"])
        self.assertEqual(
            action["res_model"],
            "project.task.hours.request.wizard",
        )

        self.task.stage_id = self.dev_stage
        self._create_timesheet(self.task, 0.5)
        self.task.stage_id = self.done_stage
        with self.assertRaises(UserError):
            self._create_timesheet(self.task, 0.5)

    def test_additional_hours_request_only_from_parent_task(self):
        """Subtasks cannot open or create additional-hours requests."""
        subtask = self.env["project.task"].with_user(
            self.tech_lead
        ).create({
            "name": "Development subtask",
            "description": "Child task used to verify request blocking.",
            "project_id": self.project.id,
            "parent_id": self.task.id,
            "stage_id": self.dev_stage.id,
            "task_type": "development",
            "estimated_dev_hours": 1.0,
            "margin_hours": 1.0,
        })

        with self.assertRaises(UserError):
            subtask.action_open_hours_request_wizard()
        with self.assertRaises(UserError):
            self.env["project.task.hours.request"].create({
                "task_id": subtask.id,
                "segment": "development",
                "requested_hours": 0.5,
                "reason": "Subtask request must be blocked",
            })

    def test_parent_estimates_are_sum_of_subtasks(self):
        """Parent estimate and margin fields follow their subtask totals."""
        first_subtask = self.env["project.task"].with_user(
            self.tech_lead
        ).create({
            "name": "First development subtask",
            "description": "First child task with controlled estimates.",
            "project_id": self.project.id,
            "parent_id": self.task.id,
            "stage_id": self.dev_stage.id,
            "task_type": "development",
            "estimated_dev_hours": 1.0,
            "estimated_deploy_hours": 0.5,
            "estimated_functional_test_hours": 0.25,
            "margin_hours": 0.75,
        })
        self.env["project.task"].with_user(self.tech_lead).create({
            "name": "Second development subtask",
            "description": "Second child task with controlled estimates.",
            "project_id": self.project.id,
            "parent_id": self.task.id,
            "stage_id": self.dev_stage.id,
            "task_type": "development",
            "estimated_dev_hours": 2.0,
            "estimated_deploy_hours": 1.5,
            "estimated_functional_test_hours": 1.25,
            "margin_hours": 0.25,
        })

        self.assertEqual(self.task.estimated_dev_hours, 3.0)
        self.assertEqual(self.task.estimated_deploy_hours, 2.0)
        self.assertEqual(self.task.estimated_functional_test_hours, 1.5)
        self.assertEqual(self.task.margin_hours, 1.0)

        first_subtask.estimated_dev_hours = 4.0
        self.assertEqual(self.task.estimated_dev_hours, 6.0)

    def test_development_cap_requires_approved_margin(self):
        """Only approved segment margin permits work above its planned cap."""
        self._create_timesheet(self.task, 2.0)
        with self.assertRaises(UserError):
            self._create_timesheet(self.task, 0.5)

        request = self.env["project.task.hours.request"].create({
            "task_id": self.task.id,
            "segment": "development",
            "requested_hours": 0.5,
            "reason": "Additional correction",
        })
        with self.assertRaises(UserError):
            self._create_timesheet(self.task, 0.5)
        request.with_user(self.approver).action_approve()
        self._create_timesheet(self.task, 0.5)

    def test_request_workflow_and_margin_are_protected(self):
        """Direct approval and authorization above margin are rejected."""
        self._create_timesheet(self.task, 2.0)
        request = self.env["project.task.hours.request"].create({
            "task_id": self.task.id,
            "segment": "development",
            "requested_hours": 1.5,
            "reason": "Too many additional hours",
        })
        with self.assertRaises(UserError):
            request.write({"state": "approved"})
        with self.assertRaises(UserError):
            request.with_user(self.approver).action_approve()

    def test_deploy_stages_share_one_cap(self):
        """Staging and production consume the same planned field."""
        self.task.stage_id = self.staging_stage
        staging_line = self._create_timesheet(self.task, 0.5)
        self.task.stage_id = self.production_stage
        production_line = self._create_timesheet(self.task, 0.5)

        self.assertEqual(staging_line.timesheet_segment, "deploy")
        self.assertEqual(production_line.timesheet_segment, "deploy")
        with self.assertRaises(UserError):
            self._create_timesheet(self.task, 0.5)

    def test_only_technical_leader_edits_estimates(self):
        """A project member cannot change controlled estimate fields."""
        with self.assertRaises(UserError):
            self.task.with_user(self.worker).estimated_dev_hours = 3.0
        self.task.with_user(self.tech_lead).estimated_dev_hours = 3.0
        self.assertEqual(self.task.estimated_dev_hours, 3.0)

    def test_task_without_consumed_hours_cannot_be_finalized(self):
        """Finalization requires a positive timesheet balance."""
        empty_task = self.env["project.task"].create({
            "name": "Empty task",
            "description": "Task used to verify finalization controls.",
            "project_id": self.project.id,
            "stage_id": self.dev_stage.id,
        })
        with self.assertRaises(UserError):
            empty_task.stage_id = self.done_stage

        self._create_timesheet(self.task, 0.5)
        self.task.stage_id = self.done_stage
        self.assertEqual(self.task.stage_id, self.done_stage)
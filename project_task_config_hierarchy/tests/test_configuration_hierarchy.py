from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install")
class TestConfigurationHierarchy(TransactionCase):
    """Check task depth, global caps, and timesheet allocation rules."""

    @classmethod
    def setUpClass(cls):
        """Create users, a project, stages, and a contracted root task."""
        super().setUpClass()
        cls.pm = new_test_user(
            cls.env,
            login="config_hierarchy_pm",
            groups="project.group_project_user,hr_timesheet.group_hr_timesheet_user",
        )
        cls.worker = new_test_user(
            cls.env,
            login="config_hierarchy_worker",
            groups=(
                "project.group_project_user,hr_timesheet.group_hr_timesheet_user,"
                "hr.group_hr_user"
            ),
        )
        cls.approver = new_test_user(
            cls.env,
            login="config_hierarchy_approver",
            groups=(
                "project.group_project_user,"
                "project_hours_request.group_project_hours_request_contratos"
            ),
        )
        cls.employee = cls.env["hr.employee"].create({
            "name": "Configuration Timesheet Worker",
            "user_id": cls.worker.id,
        })
        cls.project = cls.env["project.project"].create({
            "name": "Configuration Hierarchy",
            "allow_timesheets": True,
            "privacy_visibility": "employees",
            "user_id": cls.pm.id,
            "calyx_project_manager_id": cls.pm.id,
        })
        cls.functional_stage = cls.env["project.task.type"].create({
            "name": "Gestión funcional",
            "timesheet_stage_type": "unrestricted",
            "task_type_scope": "functional",
            "project_ids": [(6, 0, cls.project.ids)],
        })
        cls.done_stage = cls.env["project.task.type"].create({
            "name": "Finalizada",
            "timesheet_stage_type": "done",
            "project_ids": [(6, 0, cls.project.ids)],
        })
        cls.root = cls._create_task(
            "Bolsa de Configuraciones",
            is_calyx_sale_root=True,
            calyx_budget_hours=4.0,
            hours_cap=4.0,
        )

    @classmethod
    def _create_task(cls, name, **values):
        """Create a task with the project checklist's required description."""
        defaults = {
            "name": name,
            "description": "Task created by the hierarchy test suite.",
            "project_id": cls.project.id,
        }
        defaults.update(values)
        return cls.env["project.task"].create(defaults)

    def _create_branch(self, suffix, cap=1.0):
        """Create one module, level-three task, and functional child task."""
        module = self._create_task(
            "Módulo " + suffix,
            parent_id=self.root.id,
        )
        activity = self._create_task(
            "Actividad " + suffix,
            parent_id=module.id,
            hours_cap=cap,
        )
        functional = self._create_task(
            "Subtarea funcional " + suffix,
            parent_id=activity.id,
            task_type="functional",
            stage_id=self.functional_stage.id,
        )
        return module, activity, functional

    def _create_timesheet(self, task, hours):
        """Create a worker timesheet line on a hierarchy task."""
        return self.env["account.analytic.line"].with_user(self.worker).create({
            "name": "Functional configuration work",
            "project_id": self.project.id,
            "task_id": task.id,
            "employee_id": self.employee.id,
            "unit_amount": hours,
        })

    def test_root_builds_four_levels_and_rejects_level_five(self):
        """The Calyx root accepts exactly three nested task levels."""
        module, activity, functional = self._create_branch("A", cap=1.0)

        self.assertEqual(self.root.config_level, 1)
        self.assertEqual(module.config_level, 2)
        self.assertEqual(activity.config_level, 3)
        self.assertEqual(functional.config_level, 4)
        with self.assertRaises(ValidationError):
            self._create_task("Forbidden fifth level", parent_id=functional.id)

    def test_level_three_cap_is_required_and_manager_gated(self):
        """Only the PM can create modules and activities with valid caps."""
        with self.assertRaises(AccessError):
            self.env["project.task"].with_user(self.worker).create({
                "name": "Unapproved module",
                "description": "A non-PM must not create a module.",
                "project_id": self.project.id,
                "parent_id": self.root.id,
            })
        module = self._create_task("Módulo B", parent_id=self.root.id)
        with self.assertRaises(ValidationError):
            self._create_task("Actividad sin tope", parent_id=module.id)

    def test_only_level_four_accepts_hours_and_root_request_shares_excess(self):
        """One approved root request unlocks shared branch excess."""
        _, first_activity, first_child = self._create_branch("A", cap=1.0)
        _, second_activity, second_child = self._create_branch("B", cap=1.0)

        with self.assertRaises(UserError):
            self._create_timesheet(first_activity, 0.5)
        self._create_timesheet(first_child, 2.0)
        self._create_timesheet(second_child, 2.0)

        request = self.env["project.task.hours.request"].create({
            "task_id": self.root.id,
            "requested_hours": 1.0,
            "reason": "Ampliación única de la bolsa contractual",
        })
        request.with_user(self.approver).action_approve()
        self.assertEqual(self.root.hours_cap, 5.0)
        self.assertEqual(first_activity.hours_cap, 1.0)
        self.assertEqual(second_activity.hours_cap, 1.0)

        self._create_timesheet(first_child, 1.0)
        with self.assertRaises(UserError):
            self._create_timesheet(second_child, 0.5)

    def test_finalization_counts_descendant_hours_for_levels_one_to_three(self):
        """A parent can finish when its descendant owns the timesheet hours."""
        _, _, child = self._create_branch("Finalization", cap=2.0)
        with self.assertRaises(UserError):
            self.root.stage_id = self.done_stage

        self._create_timesheet(child, 0.5)
        self.root.stage_id = self.done_stage
        self.assertEqual(self.root.stage_id, self.done_stage)
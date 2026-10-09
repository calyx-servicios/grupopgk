from typing import Any, Callable, Tuple, Type

from psycopg2.errors import SerializationFailure

from odoo import SUPERUSER_ID, api
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import new_test_user
from odoo.addons.calyx_sale_project_from_order.tests.\
    test_calyx_sale_project_from_order import TestCalyxSaleProjectFromOrder


@tagged("post_install", "-at_install")
class TestUatReservations(TestCalyxSaleProjectFromOrder):
    """Exercise UAT reservations using the real Calyx sales fixtures."""

    @classmethod
    def setUpClass(cls) -> None:
        """Add a worker and employee to the existing sales fixtures."""
        super().setUpClass()
        cls.worker = new_test_user(
            cls.env, login="uat_reservation_worker",
            groups=("project.group_project_user,"
                    "hr_timesheet.group_hr_timesheet_user,hr.group_hr_user"),
        )
        cls.employee = cls.env["hr.employee"].create({
            "name": "UAT Reservation Worker", "user_id": cls.worker.id,
        })

    def _prepare_reservation(self) -> Tuple[Any, Any, Any, Any]:
        """Quote twenty hours with four included UAT hours and two tasks."""
        order, line = self._create_order()
        line.write({"contrated_hours": 20.0, "uat_support_hours": 4.0})
        amount = order.amount_total
        order.action_confirm()
        self.assertEqual(order.amount_total, amount)
        root = line.task_id
        root.project_id.write({
            "allow_timesheets": True, "privacy_visibility": "employees",
            "technical_leader_id": self.env.user.id,
        })
        self.uat_stage = self.env["project.task.type"].create({
            "name": "UAT Cliente", "task_type_scope": "development",
            "workflow_allow_technical_leader": True,
            "project_ids": [(6, 0, root.project_id.ids)],
        })
        self.dev_stage = self.env["project.task.type"].create({
            "name": "Desarrollo", "task_type_scope": "development",
            "workflow_allow_technical_leader": True,
            "project_ids": [(6, 0, root.project_id.ids)],
        })
        self.functional_stage = self.env["project.task.type"].create({
            "name": "Gestión UAT test", "task_type_scope": "functional",
            "project_ids": [(6, 0, root.project_id.ids)],
        })
        parent = root
        if "config_level" in root._fields:
            module = self._new_task(root, "Module", task_type=False)
            parent = self._new_task(
                module, "Activity", task_type=False, hours_cap=20.0,
            )
        first = self._new_task(parent, "First UAT", 2.0)
        second = self._new_task(parent, "Second UAT", 2.0)
        return line, root, first, second

    def _new_task(
        self, parent: Any, name: str, cupo: float = 0.0, **values: Any,
    ) -> Any:
        """Create a task in either the plain or four-level Calyx tree."""
        defaults = {
            "name": name, "description": "UAT reservation acceptance test.",
            "project_id": parent.project_id.id, "parent_id": parent.id,
            "task_type": "development", "stage_id": self.uat_stage.id,
            "estimated_uat_support_hours": cupo,
        }
        if "task_type" in values and not values["task_type"]:
            defaults["stage_id"] = False
        defaults.update(values)
        if not defaults["task_type"]:
            defaults.pop("task_type")
        return self.env["project.task"].create(defaults)

    def _charge(self, task: Any, hours: float) -> Any:
        """Charge task-based hours through the common timesheet ORM."""
        return self.env["account.analytic.line"].with_user(
            self.worker,
        ).create({
            "name": "UAT test work", "task_id": task.id,
            "project_id": task.project_id.id,
            "employee_id": self.employee.id, "unit_amount": hours,
        })

    def test_quotation_snapshot_allocation_and_exact_limit(self) -> None:
        """UAT keeps its own cupo and cannot spend other available hours."""
        line, root, first, second = self._prepare_reservation()
        self.assertEqual(root.calyx_uat_budget_hours, 4.0)
        self.assertEqual(root.calyx_budget_hours, 20.0)
        self.assertEqual(root.calyx_uat_allocated_hours, 4.0)
        self.assertEqual(root.estimated_uat_support_hours, 0.0)
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            root.calyx_uat_budget_hours = 3.0
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self._charge(first, 0.5)
        root.with_user(self.pm).action_activate_calyx_uat()
        self._charge(first, 2.0)
        self._charge(second, 2.0)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self._charge(first, 0.5)
        self.assertEqual(first._get_consumed_hours("functional_test"), 0)
        self.assertEqual(first._get_consumed_hours("development"), 0)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            line.uat_support_hours = 5.0
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            root.calyx_uat_budget_hours = 5.0

    def test_normal_work_cannot_spend_reserved_hours(self) -> None:
        """Sixteen normal hours exhaust the normal part of a 20/4 contract."""
        _, root, first, _ = self._prepare_reservation()
        root.action_activate_calyx_uat()
        first.stage_id = self.dev_stage
        first.estimated_dev_hours = 30.0
        self._charge(first, 16.0)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self._charge(first, 0.5)
        self.assertEqual(first._get_consumed_hours("uat_support"), 0)

    def test_unallocated_reserve_is_not_available_for_normal_work(
        self,
    ) -> None:
        """Reducing cupos does not return reserved hours to normal work."""
        _, root, first, second = self._prepare_reservation()
        second.estimated_uat_support_hours = 0.0
        self.assertEqual(root.calyx_uat_unallocated_hours, 2.0)
        root.action_activate_calyx_uat()
        first.stage_id = self.dev_stage
        first.estimated_dev_hours = 30.0
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self._charge(first, 16.5)

    def test_allocation_cannot_exceed_quote_or_disappear_by_archive(
        self,
    ) -> None:
        """Archived tasks retain their assigned cupo and consumed hours."""
        _, root, first, second = self._prepare_reservation()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            first.estimated_uat_support_hours = 2.5
        second.active = False
        self.assertEqual(root.calyx_uat_allocated_hours, 4.0)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            first.estimated_uat_support_hours = 3.0
        copied = first.copy({"name": "Copy without UAT allocation"})
        self.assertEqual(copied.estimated_uat_support_hours, 0)

    def test_history_and_deficit_block_activation_without_reclassification(
        self,
    ) -> None:
        """Pre-existing normal consumption is never converted into UAT."""
        _, root, first, _ = self._prepare_reservation()
        first.stage_id = self.dev_stage
        first.estimated_dev_hours = 30.0
        old_line = self._charge(first, 16.5)
        first.stage_id = self.uat_stage
        with self.assertRaises(UserError), self.env.cr.savepoint():
            root.action_activate_calyx_uat()
        self.assertEqual(root.calyx_uat_state, "preparation")
        self.assertEqual(old_line.timesheet_segment, "development")
        root.hours_cap = 21.0
        root.action_activate_calyx_uat()
        self.assertEqual(old_line.timesheet_segment, "development")

    def test_activation_and_preparation_are_pm_only(self) -> None:
        """Workers cannot change commercial reserve or activate via RPC."""
        _, root, _, _ = self._prepare_reservation()
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            root.with_user(self.worker).action_activate_calyx_uat()
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            root.with_user(self.worker).write({"calyx_uat_budget_hours": 5})
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            root.write({"calyx_uat_state": "active"})

    def test_existing_root_allows_audited_preparation_before_activation(
        self,
    ) -> None:
        """A legacy root without a quotation snapshot permits PM backfill."""
        _, root, first, _ = self._prepare_reservation()
        self.env.cr.execute(
            "UPDATE project_task SET calyx_uat_quote_snapshot = false "
            "WHERE id = %s", [root.id],
        )
        root.invalidate_cache(["calyx_uat_quote_snapshot"])
        first.estimated_uat_support_hours = 1.0
        root.with_user(self.pm).write({"calyx_uat_budget_hours": 3.0})
        self.assertEqual(root.calyx_uat_unallocated_hours, 0.0)
        root.with_user(self.pm).action_activate_calyx_uat()
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            root.with_user(self.pm).write({"calyx_uat_budget_hours": 4.0})

    def test_history_survives_stage_changes_and_segment_spoofing(self) -> None:
        """Keep historical UAT in its segment during stage changes."""
        _, root, first, second = self._prepare_reservation()
        root.action_activate_calyx_uat()
        line = self._charge(first, 1.0)
        first.stage_id = self.dev_stage
        self.assertEqual(line.timesheet_segment, "uat_support")
        second.stage_id = self.dev_stage
        with self.assertRaises(UserError), self.env.cr.savepoint():
            line.write({"task_id": second.id})
        with self.assertRaises(UserError), self.env.cr.savepoint():
            line.write({"timesheet_segment": "development"})
        with self.assertRaises(UserError), self.env.cr.savepoint():
            first.unlink()

    def test_quote_validates_uat_within_total_without_repricing(self) -> None:
        """The reservation is included in the total, not sold twice."""
        order, line = self._create_order()
        amount = order.amount_total
        line.uat_support_hours = 4.0
        self.assertEqual(order.amount_total, amount)
        self.assertEqual(line.contrated_hours, 12.0)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            line.uat_support_hours = 12.5
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            line.uat_support_hours = -1.0

    def test_uat_cannot_be_added_to_a_historical_development_line(
        self,
    ) -> None:
        """An increase during UAT must be a new UAT line, not old Dev work."""
        _, root, first, _ = self._prepare_reservation()
        first.stage_id = self.dev_stage
        first.estimated_dev_hours = 20.0
        line = self._charge(first, 1.0)
        first.stage_id = self.uat_stage
        root.action_activate_calyx_uat()
        with self.assertRaises(UserError), self.env.cr.savepoint():
            line.write({"unit_amount": 1.5})
        line.write({"unit_amount": 0.5})
        self.assertEqual(line.timesheet_segment, "development")
        self.assertEqual(self._charge(first, 0.5).timesheet_segment,
                         "uat_support")

    def test_uat_stage_is_configured_on_upgrade(self) -> None:
        """Canonical UAT stages have the explicit UAT segment after upgrade."""
        stage = self.env.ref("project_task_type_workflow.stage_uat_cliente")
        self.assertEqual(stage.timesheet_stage_type, "uat_support")

    def test_hierarchy_shared_excess_cannot_borrow_uat_reservation(
        self,
    ) -> None:
        """Reserved UAT reduces both branch caps and the shared allowance."""
        if "config_level" not in self.env["project.task"]._fields:
            self.skipTest("Configurations hierarchy is not installed")
        _, root, first, second = self._prepare_reservation()
        activity = first.parent_id
        activity.hours_cap = 8.0
        other = self._new_task(
            activity.parent_id, "Second activity", task_type=False,
            hours_cap=8.0,
        )
        second.parent_id = other
        root.action_activate_calyx_uat()
        first.stage_id = self.dev_stage
        first.estimated_dev_hours = 30.0
        self._charge(first, 10.0)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self._charge(first, 0.5)

    def test_reparenting_cupos_checks_destination_reserve(self) -> None:
        """Moving a cupo into another full reservation must roll back."""
        _, _, first, _ = self._prepare_reservation()
        _, _, destination, _ = self._prepare_reservation()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            first.parent_id = destination.parent_id


def check_concurrent_allocations(env: Any) -> None:
    """Check real cursors in a disposable uat_test database, not TestCursor."""
    if "uat_test" not in env.cr.dbname:
        raise UserError("Concurrency checks require a disposable uat_test DB")
    project = env["project.project"].sudo().with_context(
        calyx_sale_project_generation=True,
    ).create({
        "name": "UAT concurrent reservation test",
        "allow_timesheets": True,
        "user_id": env.user.id, "technical_leader_id": env.user.id,
        "calyx_project_manager_id": env.user.id,
    })
    stage = env["project.task.type"].create({
        "name": "UAT Cliente", "task_type_scope": "development",
        "project_ids": [(6, 0, project.ids)],
    })
    task_model = env["project.task"].sudo()

    def create_task(name: str, **values: Any) -> Any:
        """Create a disposable task with the mandatory description."""
        return task_model.create(dict({
            "name": name, "description": "Concurrent UAT cupo test.",
            "project_id": project.id,
        }, **values))

    root = create_task(
        "Concurrent root", is_calyx_sale_root=True,
        calyx_budget_hours=20.0, hours_cap=20.0,
        calyx_uat_budget_hours=4.0,
    )
    parent = root
    if "config_level" in task_model._fields:
        module = create_task("Concurrent module", parent_id=root.id)
        parent = create_task(
            "Concurrent activity", parent_id=module.id, hours_cap=20.0,
        )
    first = create_task(
        "Concurrent first", parent_id=parent.id, task_type="development",
        stage_id=stage.id, estimated_uat_support_hours=2.0,
    )
    second = create_task(
        "Concurrent second", parent_id=parent.id, task_type="development",
        stage_id=stage.id,
    )
    standalone = create_task(
        "Concurrent timesheet task", task_type="development",
        stage_id=stage.id, estimated_uat_support_hours=1.0,
    )
    employee = env["hr.employee"].sudo().search([
        ("user_id", "=", env.user.id),
        ("company_id", "=", project.company_id.id),
    ], limit=1)
    created_employee = not employee
    if created_employee:
        employee = env["hr.employee"].sudo().create({
            "name": "Concurrent UAT worker", "user_id": env.user.id,
            "company_id": project.company_id.id,
        })
    root_id, first_id, second_id = root.id, first.id, second.id
    env.cr.commit()

    def check_race(
        first_change: Callable[[Any], Any],
        other_change: Callable[[Any], Any],
        rejection: Type[Exception],
    ) -> None:
        """Force a stale snapshot, then retry against the committed budget."""
        with env.registry.cursor() as first_cr, \
            env.registry.cursor() as other_cr:
            first_env = api.Environment(first_cr, SUPERUSER_ID, {})
            other_env = api.Environment(other_cr, SUPERUSER_ID, {})
            other_env["project.task"].browse(root_id).read([
                "calyx_uat_budget_hours",
            ])
            first_change(first_env)
            first_cr.commit()
            try:
                other_change(other_env)
            except SerializationFailure:
                other_cr.rollback()
            else:
                raise AssertionError("Stale transaction was not serialized")
        with env.registry.cursor() as retry_cr:
            retry_env = api.Environment(retry_cr, SUPERUSER_ID, {})
            try:
                other_change(retry_env)
            except rejection:
                retry_cr.rollback()
            else:
                raise AssertionError("Retry exceeded its UAT budget")

    def charge(cursor_env: Any, hours: float) -> Any:
        """Charge the standalone task through the common timesheet model."""
        return cursor_env["account.analytic.line"].create({
            "name": "Concurrent UAT work", "task_id": standalone.id,
            "project_id": project.id, "employee_id": employee.id,
            "unit_amount": hours,
        })

    try:
        check_race(
            lambda cursor_env: cursor_env["project.task"].browse(
                first_id,
            ).write({"estimated_uat_support_hours": 3.0}),
            lambda cursor_env: cursor_env["project.task"].browse(
                second_id,
            ).write({"estimated_uat_support_hours": 2.0}),
            ValidationError,
        )
        check_race(
            lambda cursor_env: charge(cursor_env, 1.0),
            lambda cursor_env: charge(cursor_env, 0.5), UserError,
        )
    finally:
        env.clear()
        env["account.analytic.line"].sudo().search([
            ("task_id", "=", standalone.id),
        ]).unlink()
        standalone.unlink()
        tree = task_model.with_context(active_test=False).search(
            [("id", "child_of", root_id)], order="id desc",
        )
        for task in tree:
            task.with_context(calyx_sale_project_generation=True).unlink()
        stage.unlink()
        account = project.analytic_account_id
        project.with_context(calyx_sale_project_generation=True).unlink()
        account.exists().unlink()
        if created_employee:
            employee.unlink()
        env.cr.commit()
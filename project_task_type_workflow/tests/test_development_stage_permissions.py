from typing import Any, Dict

from odoo import models, tools
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

from ..models.project_task_type import DEVELOPMENT_STAGE_ROLES, WORKFLOW_ROLES


@tagged("post_install", "-at_install")
class TestDevelopmentStagePermissions(TransactionCase):
    """Verify project-specific stage movement permissions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Create users with distinct project roles and custom stages."""
        super().setUpClass()
        cls.users = {
            role: new_test_user(
                cls.env, login=f"workflow_{role}",
                groups=(
                    "project.group_project_user,"
                    "hr_timesheet.group_hr_timesheet_user"
                ),
            ) for role in WORKFLOW_ROLES
        }
        cls.outsider = new_test_user(
            cls.env, login="workflow_outsider",
            groups="project.group_project_manager",
        )
        cls.project = cls.env["project.project"].create({
            "name": "Development permissions",
            "privacy_visibility": "employees",
            "user_id": cls.users["pm"].id,
            "technical_leader_id": cls.users["technical_leader"].id,
            "workflow_scrum_master_ids": [(6, 0, cls.users["scrum_master"].ids)],
            "workflow_functional_ids": [(6, 0, cls.users["functional"].ids)],
            "workflow_developer_ids": [(6, 0, cls.users["developer"].ids)],
            "workflow_deployer_ids": [(6, 0, cls.users["deployer"].ids)],
        })
        cls.origin = cls.env["project.task.type"].create({
            "name": "Controlled development",
            "task_type_scope": "development",
            "workflow_allow_developer": True,
            "workflow_allow_technical_leader": True,
            "project_ids": [(6, 0, cls.project.ids)],
        })
        cls.destination = cls.env["project.task.type"].create({
            "name": "Next development stage",
            "task_type_scope": "development",
            "project_ids": [(6, 0, cls.project.ids)],
        })

    def _task(self, **values: Any) -> models.Model:
        """Create a task without relying on restricted setup movements."""
        vals: Dict[str, Any] = {
            "name": "Permission check",
            "description": "Development permissions test context.",
            "project_id": self.project.id,
            "task_type": "development",
            "stage_id": self.origin.id,
            "user_ids": [(6, 0, [user.id for user in self.users.values()])],
        }
        vals.update(values)
        return self.env["project.task"].with_context(
            tracking_disable=True, mail_create_nosubscribe=True,
        ).create(vals)

    def _stage(self, xmlid: str) -> models.Model:
        """Return a canonical stage by its stable external identity."""
        return self.env.ref(f"project_task_type_workflow.{xmlid}")

    def test_development_allows_only_dev_and_leader(self) -> None:
        """Only the configured project roles may leave development."""
        for role, user in self.users.items():
            with self.subTest(role=role):
                task = self._task()
                if role in ("developer", "technical_leader"):
                    task.with_user(user).write({
                        "stage_id": self.destination.id,
                    })
                    self.assertEqual(task.stage_id, self.destination)
                else:
                    with self.assertRaises(UserError):
                        task.with_user(user).write({
                            "stage_id": self.destination.id,
                        })
                    self.assertEqual(task.stage_id, self.origin)

    def test_complete_canonical_matrix(self) -> None:
        """Exercise every canonical origin with all roles and an outsider."""
        for xmlid, allowed_roles in DEVELOPMENT_STAGE_ROLES.items():
            origin = self._stage(xmlid)
            self.assertEqual(origin._get_workflow_roles(), set(allowed_roles))
            destination = (
                self._stage("stage_testing_failed")
                if xmlid == "stage_pruebas" else self.destination
            )
            for role, user in dict(
                self.users, outsider=self.outsider,
            ).items():
                with self.subTest(stage=xmlid, role=role):
                    task = self._task(stage_id=origin.id)
                    if role in allowed_roles:
                        task.with_user(user).write({
                            "stage_id": destination.id,
                        })
                        self.assertEqual(task.stage_id, destination)
                    else:
                        with self.assertRaises(UserError):
                            task.with_user(user).write({
                                "stage_id": destination.id,
                            })
                        self.assertEqual(task.stage_id, origin)

    def test_suspend_uses_current_assignees(self) -> None:
        """Suspension accepts leaders or existing assignees, not new ones."""
        destination = self._stage("stage_suspendida")
        for role in ("pm", "technical_leader", "functional"):
            task = self._task(user_ids=[
                (6, 0, self.users["functional"].ids),
            ])
            task.with_user(self.users[role]).write({
                "stage_id": destination.id,
            })
            self.assertEqual(task.stage_id, destination)
        task = self._task(user_ids=[(5, 0, 0)])
        for vals in (
            {"stage_id": destination.id},
            {
                "stage_id": destination.id,
                "user_ids": [(4, self.users["scrum_master"].id)],
            },
        ):
            with self.assertRaises(UserError):
                task.with_user(self.users["scrum_master"]).write(vals)
        self.assertFalse(task.user_ids)

    def test_reopen_ignores_origin_roles_and_sequence(self) -> None:
        """PM and leader may reopen even from a functional-only origin."""
        origin = self._stage("stage_pruebas")
        origin.sequence = 1
        for role, user in self.users.items():
            task = self._task(stage_id=origin.id)
            destination = self._stage("stage_pendiente_development")
            if role in ("pm", "technical_leader"):
                task.with_user(user).write({"stage_id": destination.id})
                self.assertEqual(task.stage_id, destination)
            else:
                with self.assertRaises(UserError):
                    task.with_user(user).write({"stage_id": destination.id})

    def test_testing_destinations(self) -> None:
        """Functional users cannot skip testing results or impersonate OK."""
        origin = self._stage("stage_pruebas")
        origin.name = "Renamed QA"
        task = self._task(stage_id=origin.id)
        with self.assertRaises(UserError):
            task.with_user(self.users["functional"]).write({
                "stage_id": self.destination.id,
            })
        imitation = self.env["project.task.type"].create({
            "name": "Testing OK", "task_type_scope": "development",
            "project_ids": [(6, 0, self.project.ids)],
        })
        with self.assertRaises(UserError):
            task.with_user(self.users["functional"]).write({
                "stage_id": imitation.id,
            })
        task.with_user(self.users["functional"]).write({
            "stage_id": self._stage("stage_testing_failed").id,
        })

    def test_empty_policy_blocks_ordinary_moves(self) -> None:
        """Custom stages require explicit permissions but allow recovery."""
        task = self._task(stage_id=self.destination.id)
        for user in self.users.values():
            with self.assertRaises(UserError):
                task.with_user(user).write({"stage_id": self.origin.id})
        task.with_user(self.users["pm"]).write({
            "stage_id": self._stage("stage_pendiente_development").id,
        })

    def test_multiple_roles_and_multiple_users(self) -> None:
        """Any matching role suffices and each role supports several users."""
        self.project.workflow_developer_ids = [
            (4, self.users["functional"].id), (4, self.outsider.id),
        ]
        for user in (self.users["functional"], self.outsider):
            self._task().with_user(user).write({
                "stage_id": self.destination.id,
            })

    def test_no_admin_sudo_or_context_bypass(self) -> None:
        """Project administration and sudo do not grant a movement role."""
        task = self._task()
        for candidate in (
            task, task.with_user(self.outsider),
            task.with_user(self.outsider).sudo(),
            task.with_user(self.outsider).with_context(
                skip_workflow=True, workflow_configuration_allowed=True,
            ),
        ):
            with self.assertRaises(UserError):
                candidate.write({"stage_id": self.destination.id})
        self.assertEqual(task.stage_id, self.origin)

    def test_batch_is_atomic(self) -> None:
        """One denied origin prevents every task in the batch from moving."""
        allowed = self._task()
        denied = self._task(stage_id=self.destination.id)
        with self.assertRaises(UserError):
            (allowed | denied).with_user(self.users["developer"]).write({
                "stage_id": self._stage("stage_desarrollo").id,
            })
        self.assertEqual(allowed.stage_id, self.origin)
        self.assertEqual(denied.stage_id, self.destination)

    def test_same_stage_and_other_edits_are_allowed(self) -> None:
        """The guard restricts real movement, not ordinary task editing."""
        task = self._task()
        task.with_user(self.users["functional"]).write({
            "stage_id": self.origin.id, "name": "Updated task",
        })
        self.assertEqual(task.name, "Updated task")

    def test_no_clearing_stage_or_reclassification_escape(self) -> None:
        """An ordinary user cannot remove the protected workflow context."""
        task = self._task()
        for vals in (
            {"stage_id": False}, {"task_type": "unclassified"},
            {
                "task_type": "unclassified",
                "stage_id": self.destination.id,
            },
        ):
            with self.assertRaises(UserError):
                task.with_user(self.users["developer"]).write(vals)
        task.with_user(self.users["pm"]).task_type = "unclassified"
        self.assertEqual(task.task_type, "unclassified")

    def test_missing_origin_can_be_recovered(self) -> None:
        """Only leaders can recover a legacy development task without stage."""
        task = self._task(stage_id=False)
        task.with_user(self.users["developer"]).write({
            "stage_id": False, "name": "Updated legacy task",
        })
        self.assertEqual(task.name, "Updated legacy task")
        with self.assertRaises(UserError):
            task.with_user(self.users["developer"]).stage_id = self.origin
        task.with_user(self.users["pm"]).stage_id = self._stage(
            "stage_pendiente_development"
        )

    def test_project_roles_do_not_leak(self) -> None:
        """Roles are resolved per project, including project transfers."""
        other = self.env["project.project"].create({
            "name": "Other project", "privacy_visibility": "employees",
            "user_id": self.outsider.id,
        })
        self.origin.project_ids = [(4, other.id)]
        self.destination.project_ids = [(4, other.id)]
        other_task = self._task(project_id=other.id)
        with self.assertRaises(UserError):
            other_task.with_user(self.users["developer"]).write({
                "stage_id": self.destination.id,
            })
        for vals in (
            {"project_id": self.project.id},
            {"project_id": self.project.id, "stage_id": self.destination.id},
        ):
            with self.assertRaises(UserError):
                other_task.with_user(self.users["developer"]).write(vals)

    def test_destination_must_belong_to_project(self) -> None:
        """A permitted role cannot move to another project's custom stage."""
        self.destination.project_ids = [(5, 0, 0)]
        with self.assertRaises(ValidationError):
            self._task().with_user(self.users["developer"]).write({
                "stage_id": self.destination.id,
            })

    def test_role_configuration_is_protected(self) -> None:
        """Ordinary project users cannot grant themselves roles or policies."""
        user = self.users["functional"]
        for vals in (
            {"workflow_developer_ids": [(4, user.id)]},
            {"user_id": user.id}, {"technical_leader_id": user.id},
        ):
            with self.assertRaises(AccessError):
                self.project.with_user(user).write(vals)
        with self.assertRaises(AccessError):
            self.origin.with_user(user).workflow_allow_functional = True
        with self.assertRaises(AccessError):
            self.env["project.task.type"].with_user(user).create({
                "name": "Unauthorized policy", "workflow_allow_pm": True,
            })
        self.assertFalse(
            self.project.with_user(user).workflow_configuration_allowed
        )
        self.assertTrue(
            self.project.with_user(self.outsider).workflow_configuration_allowed
        )
        self.origin.with_user(self.outsider).workflow_allow_functional = True

    def test_portal_cannot_receive_workflow_role(self) -> None:
        """Server constraints reject assignments excluded by the UI domain."""
        portal = new_test_user(
            self.env, login="workflow_portal", groups="base.group_portal",
        )
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.project.workflow_developer_ids = [(4, portal.id)]

    def test_creation_duplication_and_unclassified_are_unchanged(self) -> None:
        """Initial placement is intentionally outside movement restrictions."""
        task = self._task().with_user(self.users["functional"])
        copied = task.copy({"stage_id": self.destination.id})
        self.assertEqual(copied.stage_id, self.destination)
        unclassified = self._task(task_type="unclassified")
        unclassified.with_user(self.users["functional"]).stage_id = (
            self.destination
        )

    def test_functional_reopen_is_preserved(self) -> None:
        """The existing functional circuit keeps its PM/leader reopen rule."""
        origin = self._stage("stage_en_curso")
        destination = self._stage("stage_pendiente_functional")
        task = self._task(task_type="functional", stage_id=origin.id)
        with self.assertRaises(UserError):
            task.with_user(self.users["functional"]).stage_id = destination
        task.with_user(self.users["pm"]).stage_id = destination

    def test_data_reload_preserves_custom_policy(self) -> None:
        """Noupdate protects even deliberately empty administrator policies."""
        stage = self._stage("stage_desarrollo")
        stage.write({
            f"workflow_allow_{role}": False for role in WORKFLOW_ROLES
        })
        tools.convert_file(
            self.cr, "project_task_type_workflow",
            "data/project_task_type_data.xml", {}, mode="update", kind="data",
        )
        self.assertFalse(stage._get_workflow_roles())

    def test_entering_development_uses_original_project(self) -> None:
        """Simultaneous classification and movement require the old PM/lead."""
        task = self._task(task_type="unclassified")
        with self.assertRaises(UserError):
            task.with_user(self.users["functional"]).write({
                "task_type": "development",
                "stage_id": self.destination.id,
            })
        task.with_user(self.users["pm"]).write({
            "task_type": "development",
            "stage_id": self.destination.id,
        })
        self.assertEqual(task.task_type, "development")

    def test_testing_ok_keeps_checklist_requirement(self) -> None:
        """Authorization does not replace the independent checklist gate."""
        if "acceptance_criteria_ids" not in self.env["project.task"]._fields:
            self.skipTest("Checklist integration module is not installed")
        task = self._task(stage_id=self._stage("stage_pruebas").id)
        user = self.users["functional"]
        destination = self._stage("stage_testing_ok")
        with self.assertRaisesRegex(UserError, "checklist"):
            task.with_user(user).stage_id = destination
        criterion = self.env["project.task.acceptance.criteria"].create({
            "task_id": task.id, "name": "Acceptance verified",
        })
        with self.assertRaisesRegex(UserError, "checklist"):
            task.with_user(user).stage_id = destination
        criterion.is_validated = True
        task.with_user(user).stage_id = destination
        self.assertEqual(task.stage_id, destination)

    def test_finalization_keeps_consumed_hours_requirement(self) -> None:
        """An authorized leader must still satisfy timesheet controls."""
        if "hours_cap" not in self.env["project.task"]._fields:
            self.skipTest("Hours integration module is not installed")
        task = self._task()
        with self.assertRaisesRegex(UserError, "sin horas cargadas"):
            task.with_user(self.users["technical_leader"]).stage_id = (
                self._stage("stage_finalizada_development")
            )

    def test_calyx_pm_takes_precedence_when_available(self) -> None:
        """The explicit Calyx PM replaces, rather than adds to, the fallback."""
        if "calyx_project_manager_id" not in self.project._fields:
            self.skipTest("Calyx project PM integration is not installed")
        self.project.calyx_project_manager_id = self.outsider
        self.project.user_id = self.users["pm"]
        self.assertEqual(self.project._get_workflow_pm(), self.outsider)
        task = self._task()
        destination = self._stage("stage_pendiente_development")
        with self.assertRaises(UserError):
            task.with_user(self.users["pm"]).stage_id = destination
        task.with_user(self.outsider).stage_id = destination
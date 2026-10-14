from typing import Any, Dict

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

from ..models.project_task_type import WORKFLOW_ROLES


@tagged("post_install", "-at_install")
class TestTaskEventsAndTriage(TransactionCase):
    """Test unified task events, Testing Failed triage, and Suspendida restrictions."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.users = {
            role: new_test_user(
                cls.env,
                login=f"events_{role}",
                groups=(
                    "project.group_project_user,"
                    "hr_timesheet.group_hr_timesheet_user"
                ),
            )
            for role in WORKFLOW_ROLES
        }
        cls.project = cls.env["project.project"].create({
            "name": "Events and Triage Project",
            "privacy_visibility": "employees",
            "user_id": cls.users["pm"].id,
            "technical_leader_id": cls.users["technical_leader"].id,
            "workflow_scrum_master_ids": [(6, 0, cls.users["scrum_master"].ids)],
            "workflow_functional_ids": [(6, 0, cls.users["functional"].ids)],
            "workflow_developer_ids": [(6, 0, cls.users["developer"].ids)],
            "workflow_deployer_ids": [(6, 0, cls.users["deployer"].ids)],
        })
        cls.reason_technical = cls.env["project.task.suspension.reason"].create({
            "name": "Bloqueo técnico de prueba",
            "sequence": 10,
            "is_other": False,
        })
        cls.reason_other = cls.env["project.task.suspension.reason"].create({
            "name": "Otro de prueba",
            "sequence": 99,
            "is_other": True,
        })

    def _task(self, **values: Any):
        vals: Dict[str, Any] = {
            "name": "Events Task",
            "description": "Contexto y Qué hay que desarrollar obligatorio.",
            "project_id": self.project.id,
            "task_type": "development",
            "stage_id": self._stage("stage_pruebas").id,
            "user_ids": [(6, 0, [self.users["developer"].id])],
        }
        vals.update(values)
        return self.env["project.task"].with_context(
            tracking_disable=True,
            mail_create_nosubscribe=True,
        ).create(vals)

    def _stage(self, xmlid: str):
        return self.env.ref(f"project_task_type_workflow.{xmlid}")

    def test_direct_drag_to_testing_failed_blocked(self):
        """Moving to Testing Failed without wizard / skip_event_check raises UserError."""
        task = self._task(stage_id=self._stage("stage_pruebas").id)
        with self.assertRaises(UserError):
            task.with_user(self.users["functional"]).write({
                "stage_id": self._stage("stage_testing_failed").id,
            })

    def test_testing_failed_wizard_records_event(self):
        """Wizard creates an event record and moves task to Testing Failed."""
        task = self._task(stage_id=self._stage("stage_pruebas").id)
        self.assertEqual(task.event_count, 0)
        self.assertFalse(task.last_testing_failed_event_id)

        # Wizard validation: requires error_target and description
        wizard = self.env["project.task.event.wizard"].with_user(self.users["functional"]).create({
            "task_id": task.id,
            "event_type": "testing_failed",
            "error_target": False,
            "description": "",
        })
        with self.assertRaises(UserError):
            wizard.action_confirm()

        # Fill properly with code error
        attachment = self.env["ir.attachment"].create({
            "name": "screenshot.png",
            "datas": "iVBORw0KGgo=",
            "res_model": "project.task",
            "res_id": task.id,
        })
        wizard.write({
            "error_target": "code",
            "description": "Falla cálculo en backend",
            "attachment_ids": [(6, 0, [attachment.id])],
        })
        wizard.action_confirm()

        self.assertEqual(task.stage_id, self._stage("stage_testing_failed"))
        self.assertEqual(task.event_count, 1)
        event = task.last_testing_failed_event_id
        self.assertTrue(event)
        self.assertEqual(event.event_type, "testing_failed")
        self.assertEqual(event.error_target, "code")
        self.assertEqual(event.description, "Falla cálculo en backend")
        self.assertEqual(event.user_id, self.users["functional"])
        self.assertEqual(event.attachment_ids, attachment)
        self.assertEqual(task.last_testing_failed_error_target, "code")

    def test_functional_cannot_move_from_testing_failed(self):
        """Functional user cannot move the task out of Testing Failed."""
        task = self._task(stage_id=self._stage("stage_testing_failed").id)
        # Record a code error event
        self.env["project.task.event"].create({
            "task_id": task.id,
            "event_type": "testing_failed",
            "error_target": "code",
            "description": "Error funcional detectado",
        })

        # Functional tries to move to Desarrollo -> blocked
        with self.assertRaises(UserError):
            task.with_user(self.users["functional"]).write({
                "stage_id": self._stage("stage_desarrollo").id,
            })
        # Functional tries to move to Testing OK -> blocked
        with self.assertRaises(UserError):
            task.with_user(self.users["functional"]).write({
                "stage_id": self._stage("stage_testing_ok").id,
            })
        # Functional tries to move to Deploy Failed Staging -> blocked
        with self.assertRaises(UserError):
            task.with_user(self.users["functional"]).write({
                "stage_id": self._stage("stage_deploy_failed_staging").id,
            })

    def test_triage_code_error_to_desarrollo(self):
        """If last failure is code error, Dev / Leader can only move to Desarrollo."""
        task = self._task(stage_id=self._stage("stage_testing_failed").id)
        self.env["project.task.event"].create({
            "task_id": task.id,
            "event_type": "testing_failed",
            "error_target": "code",
            "description": "Bug en código python",
        })

        # Moving to Deploy Failed Staging is rejected
        with self.assertRaises(UserError):
            task.with_user(self.users["developer"]).write({
                "stage_id": self._stage("stage_deploy_failed_staging").id,
            })

        # Moving to Pruebas is rejected
        with self.assertRaises(UserError):
            task.with_user(self.users["developer"]).write({
                "stage_id": self._stage("stage_pruebas").id,
            })

        # Moving to Desarrollo succeeds
        task.with_user(self.users["developer"]).write({
            "stage_id": self._stage("stage_desarrollo").id,
        })
        self.assertEqual(task.stage_id, self._stage("stage_desarrollo"))

    def test_triage_deploy_error_to_deploy_failed_staging(self):
        """If last failure is deploy error, Dev / Leader can only move to Deploy Failed Staging."""
        task = self._task(stage_id=self._stage("stage_testing_failed").id)
        self.env["project.task.event"].create({
            "task_id": task.id,
            "event_type": "testing_failed",
            "error_target": "deploy",
            "description": "Faltó migración en staging",
        })

        # Moving to Desarrollo is rejected
        with self.assertRaises(UserError):
            task.with_user(self.users["developer"]).write({
                "stage_id": self._stage("stage_desarrollo").id,
            })

        # Moving to Deploy Failed Staging succeeds
        task.with_user(self.users["technical_leader"]).write({
            "stage_id": self._stage("stage_deploy_failed_staging").id,
        })
        self.assertEqual(task.stage_id, self._stage("stage_deploy_failed_staging"))

    def test_multiple_testing_failed_cycles_preserves_history(self):
        """Multiple failures are preserved and the latest failure controls triage."""
        task = self._task(stage_id=self._stage("stage_pruebas").id)

        # 1st Failure: code
        wizard1 = self.env["project.task.event.wizard"].with_user(self.users["functional"]).create({
            "task_id": task.id,
            "event_type": "testing_failed",
            "error_target": "code",
            "description": "Primer fallo: error de código",
        })
        wizard1.action_confirm()
        self.assertEqual(task.last_testing_failed_error_target, "code")

        # Dev moves to Desarrollo
        task.with_user(self.users["developer"]).write({
            "stage_id": self._stage("stage_desarrollo").id,
        })

        # Moves to Deploy a Staging -> Pruebas
        task.with_user(self.users["developer"]).write({
            "stage_id": self._stage("stage_deploy_staging").id,
        })
        task.with_user(self.users["deployer"]).write({
            "stage_id": self._stage("stage_pruebas").id,
        })

        # 2nd Failure: deploy
        wizard2 = self.env["project.task.event.wizard"].with_user(self.users["functional"]).create({
            "task_id": task.id,
            "event_type": "testing_failed",
            "error_target": "deploy",
            "description": "Segundo fallo: error de deploy",
        })
        wizard2.action_confirm()

        self.assertEqual(task.event_count, 2)
        self.assertEqual(task.last_testing_failed_error_target, "deploy")

        # Now triage destination MUST be Deploy Failed Staging, not Desarrollo
        with self.assertRaises(UserError):
            task.with_user(self.users["developer"]).write({
                "stage_id": self._stage("stage_desarrollo").id,
            })
        task.with_user(self.users["developer"]).write({
            "stage_id": self._stage("stage_deploy_failed_staging").id,
        })
        self.assertEqual(task.stage_id, self._stage("stage_deploy_failed_staging"))

    def test_direct_move_to_suspend_blocked(self):
        """Direct move to Suspendida without wizard / skip_event_check is blocked."""
        task = self._task(stage_id=self._stage("stage_desarrollo").id)
        with self.assertRaises(UserError):
            task.with_user(self.users["pm"]).write({
                "stage_id": self._stage("stage_suspendida").id,
            })

    def test_suspend_wizard_records_event(self):
        """Suspend wizard records reason and detail and changes stage to Suspendida."""
        task = self._task(stage_id=self._stage("stage_desarrollo").id)

        # Predefined reason
        wizard = self.env["project.task.event.wizard"].with_user(self.users["pm"]).create({
            "task_id": task.id,
            "event_type": "suspended",
            "suspension_reason_id": self.reason_technical.id,
        })
        wizard.action_confirm()
        self.assertEqual(task.stage_id, self._stage("stage_suspendida"))
        self.assertEqual(task.event_count, 1)
        event = task.event_ids[0]
        self.assertEqual(event.event_type, "suspended")
        self.assertEqual(event.suspension_reason_id, self.reason_technical)

    def test_functional_role_alone_cannot_suspend(self):
        """Functional project membership is not PM or task responsibility."""
        task = self._task(
            stage_id=self._stage("stage_desarrollo").id,
            user_ids=[(6, 0, [self.users["developer"].id])],
        )
        functional = self.users["functional"]
        self.assertIn(functional, self.project.workflow_functional_ids)
        self.assertNotIn(functional, task.user_ids)
        self.assertNotIn(functional, self.project._get_workflow_pm())
        self.assertNotIn(functional, self.project.technical_leader_id)
        self.assertFalse(task.with_user(functional).can_suspend_task)

        with self.assertRaises(UserError):
            task.with_user(functional).action_open_suspend_wizard()

        wizard = self.env["project.task.event.wizard"].with_user(functional).create({
            "task_id": task.id,
            "event_type": "suspended",
            "suspension_reason_id": self.reason_technical.id,
        })
        with self.assertRaises(UserError), self.cr.savepoint():
            wizard.action_confirm()
        self.assertEqual(task.stage_id, self._stage("stage_desarrollo"))
        self.assertFalse(task.event_ids)

    def test_suspend_wizard_other_requires_detail(self):
        """Selecting 'Otro' requires detail."""
        task = self._task(stage_id=self._stage("stage_desarrollo").id)
        wizard = self.env["project.task.event.wizard"].with_user(self.users["pm"]).create({
            "task_id": task.id,
            "event_type": "suspended",
            "suspension_reason_id": self.reason_other.id,
            "suspension_reason_detail": "",
            "description": "",
        })
        with self.assertRaises(UserError):
            wizard.action_confirm()

        wizard.write({
            "suspension_reason_detail": "Detalle de caso no tipificado",
        })
        wizard.action_confirm()
        self.assertEqual(task.stage_id, self._stage("stage_suspendida"))
        self.assertEqual(task.event_ids[0].suspension_reason_detail, "Detalle de caso no tipificado")

    def test_suspend_only_allowed_up_to_desarrollo(self):
        """Suspendida is permitted from stages up to Desarrollo, blocked from Deploy a Staging onwards."""
        # Allowed origins: Pendiente, Estimacion, Lista para hacer, Desarrollo
        allowed_origins = [
            "stage_pendiente_development",
            "stage_estimacion",
            "stage_lista_para_hacer",
            "stage_desarrollo",
        ]
        for xmlid in allowed_origins:
            origin = self._stage(xmlid)
            task = self._task(stage_id=origin.id)
            task.with_user(self.users["pm"]).with_context(skip_event_check=True).write({
                "stage_id": self._stage("stage_suspendida").id,
            })
            self.assertEqual(task.stage_id, self._stage("stage_suspendida"))

        # Blocked origins: Deploy a Staging, Deploy Failed Staging, Pruebas, Testing Failed, Desestimada, etc.
        blocked_origins = [
            "stage_deploy_staging",
            "stage_deploy_failed_staging",
            "stage_pruebas",
            "stage_testing_failed",
            "stage_testing_ok",
            "stage_desestimada",
        ]
        for xmlid in blocked_origins:
            origin = self._stage(xmlid)
            task = self._task(stage_id=origin.id)
            with self.assertRaises(UserError):
                task.with_user(self.users["pm"]).with_context(skip_event_check=True).write({
                    "stage_id": self._stage("stage_suspendida").id,
                })

    def test_timesheet_segment_deploy_failed_staging(self):
        """Deploy Failed Staging maps to deploy segment, Desarrollo maps to development."""
        stage_deploy_failed = self._stage("stage_deploy_failed_staging")
        stage_desarrollo = self._stage("stage_desarrollo")
        self.assertEqual(stage_deploy_failed.get_timesheet_stage_type(), "deploy")
        self.assertEqual(stage_desarrollo.get_timesheet_stage_type(), "development")

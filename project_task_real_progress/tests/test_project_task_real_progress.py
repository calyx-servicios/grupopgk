from lxml import etree

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProjectTaskRealProgress(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env["project.project"].create({
            "name": "Real progress",
            "allow_timesheets": True,
            "privacy_visibility": "employees",
        })
        cls.employee = cls.env["hr.employee"].create({
            "name": "Real progress worker",
            "user_id": cls.env.user.id,
        })
        cls.functional_open_stage = cls.env.ref(
            "project_task_type_workflow.stage_en_curso"
        )
        cls.functional_done_stage = cls.env.ref(
            "project_task_type_workflow.stage_finalizada_functional"
        )
        cls.development_open_stage = cls.env.ref(
            "project_task_type_workflow.stage_desarrollo"
        )
        cls.development_done_stage = cls.env.ref(
            "project_task_type_workflow.stage_finalizada_development"
        )

    def _task(self, name, task_type="functional", parent=None, done=False, **values):
        stages = {
            ("functional", False): self.functional_open_stage,
            ("functional", True): self.functional_done_stage,
            ("development", False): self.development_open_stage,
            ("development", True): self.development_done_stage,
        }
        vals = {
            "name": name,
            "description": f"Contexto de {name}.",
            "project_id": self.project.id,
            "task_type": task_type,
            "stage_id": stages[(task_type, done)].id,
            "parent_id": parent.id if parent else False,
        }
        vals.update(values)
        return self.env["project.task"].create(vals)

    def _criterion(self, task, name, validated=False):
        return self.env["project.task.acceptance.criteria"].create({
            "task_id": task.id,
            "name": name,
            "is_validated": validated,
        })

    def _timesheet(self, task, hours):
        values = {
            "name": "Trabajo registrado",
            "date": fields.Date.today(),
            "project_id": self.project.id,
            "task_id": task.id,
            "employee_id": self.employee.id,
            "unit_amount": hours,
        }
        if "hour_type_id" in self.env["account.analytic.line"]._fields:
            values.update({
                "hour_type_id": self.env.ref(
                    "timesheet_activity_management.hour_type_management"
                ).id,
                "activity_date": fields.Date.today(),
            })
        return self.env["account.analytic.line"].create(values)

    def test_task_without_items_has_zero_progress(self):
        task = self._task("Sin ítems")

        self.assertEqual(task.progress_total_items, 0)
        self.assertEqual(task.progress_completed_items, 0)
        self.assertEqual(task.progress, 0.0)

    def test_acceptance_criteria_define_progress(self):
        task = self._task("Criterios")
        first = self._criterion(task, "Primero", validated=True)
        self._criterion(task, "Segundo")

        self.assertEqual(task.progress_total_items, 2)
        self.assertEqual(task.progress_completed_items, 1)
        self.assertEqual(task.progress, 50.0)

        first.is_validated = False
        self.assertEqual(task.progress_completed_items, 0)
        self.assertEqual(task.progress, 0.0)

    def test_progress_rolls_up_complete_hierarchy(self):
        parent = self._task("Padre")
        self._criterion(parent, "Padre validado", validated=True)
        self._criterion(parent, "Padre pendiente")

        child = self._task("Hija funcional", parent=parent, done=True)
        self._criterion(child, "Hija validada", validated=True)

        grandchild = self._task(
            "Nieta desarrollo",
            task_type="development",
            parent=child,
            done=True,
        )
        self._criterion(grandchild, "Nieta validada", validated=True)
        self._criterion(grandchild, "Nieta pendiente")

        self.assertEqual(parent.progress_total_items, 7)
        self.assertEqual(parent.progress_completed_items, 5)
        self.assertEqual(parent.progress, 71.43)

    def test_only_canonical_final_stages_complete_subtasks(self):
        parent = self._task("Padre con hijas")
        self._task("Funcional abierta", parent=parent)
        self._task(
            "Desarrollo abierto",
            task_type="development",
            parent=parent,
        )

        self.assertEqual(parent.progress_total_items, 2)
        self.assertEqual(parent.progress_completed_items, 0)
        self.assertEqual(parent.progress, 0.0)

    def test_hours_never_change_real_progress(self):
        task = self._task("Horas", planned_hours=2.0)
        if "hours_cap" in task._fields:
            task.hours_cap = 4.0
        self._criterion(task, "Validado", validated=True)
        progress_before = task.progress

        self._timesheet(task, 3.0)

        self.assertEqual(task.progress, progress_before)
        self.assertEqual(task.progress, 100.0)
        self.assertEqual(task.total_hours_spent, 3.0)
        self.assertEqual(task.hours_consumption_percentage, 150.0)
        self.assertEqual(task.overtime, 1.0)

        task.planned_hours = 6.0
        self.assertEqual(task.progress, progress_before)
        self.assertEqual(task.hours_consumption_percentage, 50.0)
        self.assertEqual(task.overtime, 0.0)

    def test_reporting_actions_have_isolated_measures(self):
        real_action = self.env.ref(
            "project_task_real_progress."
            "action_project_task_real_progress_report"
        )
        hours_action = self.env.ref(
            "project_task_real_progress."
            "action_project_task_hours_consumption_report"
        )
        self.assertEqual(real_action.res_model, "project.task")
        self.assertEqual(hours_action.res_model, "project.task")
        self.assertEqual(
            set(real_action.view_ids.mapped("view_mode")),
            {"graph", "pivot"},
        )
        self.assertEqual(
            set(hours_action.view_ids.mapped("view_mode")),
            {"graph", "pivot"},
        )

        real_graph = self.env.ref(
            "project_task_real_progress."
            "view_project_task_real_progress_graph"
        )
        hours_graph = self.env.ref(
            "project_task_real_progress."
            "view_project_task_hours_consumption_graph"
        )
        real_measures = {
            node.get("name")
            for node in etree.fromstring(real_graph.arch_db).xpath(
                "//field[@type='measure']"
            )
        }
        hours_measures = {
            node.get("name")
            for node in etree.fromstring(hours_graph.arch_db).xpath(
                "//field[@type='measure']"
            )
        }
        self.assertEqual(real_measures, {
            "progress",
            "progress_completed_items",
            "progress_total_items",
        })
        self.assertNotIn("progress", hours_measures)
        self.assertTrue({
            "planned_hours",
            "effective_hours",
            "hours_consumption_percentage",
        }.issubset(hours_measures))

        real_menu = self.env.ref(
            "project_task_real_progress."
            "menu_project_task_real_progress_report"
        )
        standard_menu = self.env.ref(
            "project.menu_project_report_task_analysis"
        )
        self.assertEqual(real_menu.action, real_action)
        self.assertEqual(
            standard_menu.action,
            self.env.ref("project.action_project_task_user_tree"),
        )

    def test_hour_alerts_do_not_use_real_progress(self):
        view_xmlids = (
            "hr_timesheet.view_task_form2_inherited",
            "hr_timesheet.view_task_tree2_inherited",
            "hr_timesheet.view_task_kanban_inherited_progress",
            "hr_timesheet.project_sharing_inherit_project_task_view_form",
            "hr_timesheet.project_sharing_inherit_project_task_view_tree",
            "hr_timesheet."
            "project_sharing_kanban_inherit_project_task_view_kanban",
        )
        for xmlid in view_xmlids:
            with self.subTest(view=xmlid):
                arch = self.env.ref(xmlid).get_combined_arch()
                self.assertNotIn("record.progress.raw_value", arch)
                self.assertNotIn('decoration-danger="progress', arch)
                self.assertNotIn('decoration-warning="progress', arch)

        form_arch = self.env.ref(
            "hr_timesheet.view_task_form2_inherited"
        ).get_combined_arch()
        self.assertIn('name="progress"', form_arch)
        self.assertIn('name="hours_consumption_percentage"', form_arch)

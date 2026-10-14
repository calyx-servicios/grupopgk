from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from odoo.addons.calyx_sale_project_from_order.tests.test_calyx_sale_project_from_order import (
    TestCalyxSaleProjectFromOrder,
)
from odoo.addons.project_task_type_workflow.hooks import initialize_development_permissions
from odoo.addons.project_task_type_workflow.models.project_task_type import DEVELOPMENT_STAGE_ROLES


@tagged("post_install", "-at_install", "uat_triage")
class TestUatTriage(TestCalyxSaleProjectFromOrder):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        initialize_development_permissions(cls.env)
        for xmlid in DEVELOPMENT_STAGE_ROLES:
            cls.env.ref("project_task_type_workflow." + xmlid).task_type_scope = "development"
        cls.functional = new_test_user(
            cls.env, login="uat_triage_functional",
            groups="project.group_project_user,hr_timesheet.group_hr_timesheet_user",
        )
        cls.seller = new_test_user(
            cls.env, login="uat_triage_seller",
            groups="sales_team.group_sale_salesman,project.group_project_user",
        )
        cls.worker = new_test_user(
            cls.env, login="uat_triage_worker",
            groups="project.group_project_user,hr_timesheet.group_hr_timesheet_user,hr.group_hr_user",
        )
        cls.employee = cls.env["hr.employee"].create({
            "name": "UAT triage worker", "user_id": cls.worker.id,
        })

    def _stage(self, name):
        return self.env.ref("project_task_type_workflow." + name)

    def _origin(self):
        order, line = self._create_order()
        line.write({"contrated_hours": 20, "uat_support_hours": 2})
        order.action_confirm()
        root = line.task_id
        project = root.project_id
        project.write({
            "technical_leader_id": self.env.user.id,
            "workflow_functional_ids": [(6, 0, self.functional.ids)],
            "workflow_developer_ids": [(6, 0, self.worker.ids)],
            "allow_timesheets": True, "privacy_visibility": "employees",
        })
        parent = root
        if "config_level" in root._fields:
            module = self.env["project.task"].create({
                "name": "UAT module", "description": "Module",
                "project_id": project.id, "parent_id": root.id,
            })
            parent = self.env["project.task"].create({
                "name": "UAT activity", "description": "Activity",
                "project_id": project.id, "parent_id": module.id, "hours_cap": 20,
            })
        task = self.env["project.task"].create({
            "name": "Original UAT", "description": "Original acceptance context",
            "project_id": project.id, "parent_id": parent.id,
            "partner_id": self.partner.id, "task_type": "development",
            "stage_id": self._stage("stage_desarrollo").id,
            "estimated_dev_hours": 18, "estimated_uat_support_hours": 2,
        })
        root.action_activate_calyx_uat()
        return task, root, line

    def _hours(self, task, amount):
        vals = {
            "task_id": task.id, "project_id": task.project_id.id,
            "employee_id": self.employee.id, "unit_amount": amount,
            "name": "UAT acceptance work",
        }
        if "hour_type_id" in self.env["account.analytic.line"]._fields:
            vals.update(
                hour_type_id=self.env.ref("timesheet_activity_management.hour_type_management").id,
                activity_date=fields.Date.today(),
            )
        return self.env["account.analytic.line"].with_user(self.worker).create(vals)

    def _wizard(self, task, result, description="Reporte del cliente"):
        return self.env["project.task.uat.wizard"].with_user(self.functional).create({
            "task_id": task.id, "result": result, "description": description,
        })

    def _improvement(self):
        task, root, original_line = self._origin()
        task.stage_id = self._stage("stage_uat_cliente")
        wizard = self._wizard(task, "improvement")
        wizard.action_confirm()
        improvement = self.env["project.task"].browse(wizard.event_id.uat_improvement_id.id)
        order, line = self._create_order()
        order.user_id = self.seller
        line.write({
            "project_id": task.project_id.id,
            "contrated_hours": 4, "uat_support_hours": 1,
        })
        improvement.write({
            "uat_sale_line_id": line.id,
            "estimated_dev_hours": 2,
            "estimated_deploy_hours": 0.5,
            "estimated_functional_test_hours": 0.5,
            "estimated_uat_support_hours": 1,
        })
        return task, improvement, root, original_line, order, line

    def _client_approve(self, task):
        attachment = self.env["ir.attachment"].create({
            "name": "aprobacion.txt", "datas": "QXByb2JhZG8=",
            "res_model": "project.task", "res_id": task.id,
        })
        wizard = self.env["project.task.uat.client.wizard"].with_user(self.functional).create({
            "task_id": task.id, "description": "Cliente aprobó la propuesta",
            "attachment_ids": [(6, 0, attachment.ids)],
        })
        wizard.action_confirm()
        return wizard

    def test_bug_same_task_internal_hours_exact_budget(self):
        task, root, sale_line = self._origin()
        original = self._hours(task, 18)
        task.stage_id = self._stage("stage_uat_cliente")
        wizard = self._wizard(task, "bug", "<script>reporte</script>")
        count = self.env["project.task"].search_count([])
        wizard.action_confirm()
        self.assertEqual(self.env["project.task"].search_count([]), count)
        self.assertEqual(task.stage_id, self._stage("stage_desarrollo"))
        self.assertEqual(wizard.event_id.uat_result, "bug")
        self.assertEqual(task.uat_bug_event_id, wizard.event_id)
        for stage, hours in (
            ("stage_desarrollo", 2), ("stage_deploy_staging", 1), ("stage_pruebas", 1),
        ):
            task.stage_id = self._stage(stage)
            entry = self._hours(task, hours)
            self.assertEqual(entry.uat_rework_event_id, wizard.event_id)
            self.assertFalse(entry.so_line)
            self.assertEqual(entry.timesheet_invoice_type, "non_billable")
            with self.assertRaises(UserError), self.env.cr.savepoint():
                entry.write({"so_line": sale_line.id})
            with self.assertRaises(AccessError), self.env.cr.savepoint():
                entry.write({"uat_rework_event_id": False})
        self.assertEqual(root._get_budget_consumed_hours(), 18)
        self.assertEqual(root._get_total_consumed_hours(), 22)
        self.assertFalse(original.uat_rework_event_id)
        self.assertEqual(original.timesheet_segment, "development")
        internal_entries = task.timesheet_ids.filtered("uat_rework_event_id")
        self.assertEqual(sum(internal_entries.mapped("unit_amount")), 4)
        if "acceptance_criteria_ids" in task._fields:
            task.acceptance_criteria_ids = [(0, 0, {
                "name": "Corrección verificada", "is_validated": True,
            })]
        task.with_user(self.functional).write({"stage_id": self._stage("stage_testing_ok").id})
        task.with_user(self.functional).write({"stage_id": self._stage("stage_uat_cliente").id})
        self.assertFalse(task.uat_bug_event_id)
        uat_entry = self._hours(task, 1)
        self.assertFalse(uat_entry.uat_rework_event_id)
        self.assertEqual(uat_entry.timesheet_segment, "uat_support")
        self.assertEqual(root._get_budget_consumed_hours(), 19)
        self.assertEqual(task._get_consumed_hours("uat_support"), 1)
        self.assertIn("&lt;script&gt;", str(task.message_ids[0].body) + "".join(task.message_ids.mapped("body")))

    def test_quote_wizard_creates_dedicated_draft_in_same_project(self):
        origin, _, _ = self._origin()
        origin.stage_id = self._stage("stage_uat_cliente")
        wizard = self._wizard(origin, "improvement")
        wizard.action_confirm()
        task = self.env["project.task"].browse(wizard.event_id.uat_improvement_id.id)
        task.estimated_dev_hours = 2
        original_amount = origin.project_id.total_project_amount
        product = self.env["product.product"].create({
            "name": "UAT hourly service", "type": "service",
            "service_tracking": "project_only",
            "uom_id": self.env.ref("uom.product_uom_hour").id,
            "uom_po_id": self.env.ref("uom.product_uom_hour").id,
        })
        quote = self.env["project.task.uat.quotation.wizard"].with_user(self.seller).create({
            "task_id": task.id, "product_id": product.id, "price_unit": 100,
        })
        quote.action_confirm()
        self.assertEqual(task.uat_sale_line_id.state, "draft")
        self.assertEqual(task.uat_sale_line_id.project_id, origin.project_id)
        self.assertFalse(task.uat_sale_line_id.task_id)
        self.assertEqual(task.uat_sale_line_id.contrated_hours, 2)
        self.assertFalse(task.uat_ready)
        self.assertEqual(origin.project_id.total_project_amount, original_amount)
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            quote.action_confirm()

    def test_misunderstanding_trace_no_new_task(self):
        task, _, _ = self._origin()
        task.stage_id = self._stage("stage_uat_cliente")
        count = self.env["project.task"].search_count([])
        wizard = self._wizard(task, "misunderstanding", "Se aclaró el comportamiento acordado.")
        wizard.action_confirm()
        self.assertEqual(task.stage_id, self._stage("stage_uat_cliente"))
        self.assertEqual(self.env["project.task"].search_count([]), count)
        self.assertFalse(task.uat_bug_event_id)
        self.assertEqual(task.uat_last_result, "misunderstanding")
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            wizard.event_id.write({"description": "Alterado"})
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            wizard.event_id.unlink()

    def test_permissions_required_text_duplicate_and_stale_wizard(self):
        task, _, _ = self._origin()
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            task.with_user(self.functional).action_open_uat_wizard()
        task.stage_id = self._stage("stage_uat_cliente")
        wizard = self._wizard(task, "bug", "   ")
        with self.assertRaises(UserError), self.env.cr.savepoint():
            wizard.action_confirm()
        wizard.description = "Reporte válido"
        stale = self._wizard(task, "improvement")
        with self.assertRaises(UserError), self.env.cr.savepoint():
            task.with_user(self.functional).write({"stage_id": self._stage("stage_desarrollo").id})
        with self.assertRaises(UserError), self.env.cr.savepoint():
            task.with_user(self.functional).with_context(_uat_operation=True).write({
                "stage_id": self._stage("stage_desarrollo").id,
            })
        wizard.action_confirm()
        with self.assertRaises(UserError), self.env.cr.savepoint():
            wizard.action_confirm()
        with self.assertRaises(UserError), self.env.cr.savepoint():
            stale.action_confirm()
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.env["project.task.event"].create({
                "task_id": task.id, "event_type": "uat", "uat_result": "bug",
                "description": "Evento falsificado",
            })

    def test_improvement_independent_requires_both_approvals_and_sale(self):
        origin, task, root, original_line, order, line = self._improvement()
        self.assertFalse(task.parent_id)
        self.assertEqual(task.uat_origin_id, origin)
        self.assertEqual(task.stage_id, self._stage("stage_estimacion"))
        self.assertEqual(origin.stage_id, self._stage("stage_uat_cliente"))
        self.assertEqual(task.sale_line_id, line)
        self.assertNotEqual(task.sale_line_id, original_line)
        for action in (
            lambda: self._hours(task, 0.5),
            lambda: task.write({"stage_id": self._stage("stage_desarrollo").id}),
            order.action_confirm,
        ):
            with self.assertRaises(UserError), self.env.cr.savepoint():
                action()
        self._client_approve(task)
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            task.with_user(self.functional).action_approve_uat_commercial()
        with self.assertRaises(UserError), self.env.cr.savepoint():
            order.action_confirm()
        task.with_user(self.seller).action_approve_uat_commercial()
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self._hours(task, 0.5)
        order.action_confirm()
        self.assertEqual(line.project_id, origin.project_id)
        self.assertEqual(line.task_id.project_id, origin.project_id)
        self.assertTrue(task.uat_ready)
        task.stage_id = self._stage("stage_desarrollo")
        entry = self._hours(task, 2)
        self.assertEqual(entry.so_line, line)
        self.assertEqual(root._get_total_consumed_hours(), 0)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self._hours(task, 0.5)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self._hours(line.task_id, 0.5)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self.env["project.task"].create({
                "name": "Duplicate spender", "description": "No duplicated budget",
                "project_id": origin.project_id.id, "parent_id": line.task_id.id,
            })

    def test_approval_revision_evidence_and_immutability(self):
        _, task, _, _, order, line = self._improvement()
        wizard = self.env["project.task.uat.client.wizard"].with_user(self.functional).create({
            "task_id": task.id, "description": "Aprobado",
        })
        with self.assertRaises(UserError), self.env.cr.savepoint():
            wizard.action_confirm()
        self._client_approve(task)
        task.with_user(self.seller).action_approve_uat_commercial()
        order.action_confirm()
        self.assertTrue(task.uat_ready)
        old_revision = task.uat_revision
        task.estimated_dev_hours = 1.5
        self.assertGreater(task.uat_revision, old_revision)
        self.assertFalse(task.uat_ready)
        task.estimated_dev_hours = 2
        self.assertFalse(task.uat_ready)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self._hours(task, 0.5)
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            task.uat_approval_ids.write({"description": "Alterada"})
        self._client_approve(task)
        task.with_user(self.seller).action_approve_uat_commercial()
        self.assertTrue(task.uat_ready)
        line.price_unit += 1
        self.assertFalse(task.uat_ready)
        self.assertEqual(len(task.uat_approval_ids), 4)
        evidence = task.uat_approval_ids.filtered(
            lambda approval: approval.approval_type == "client"
        ).mapped("attachment_ids")
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            evidence.unlink()
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            evidence.write({"datas": "Q2FtYmlhZG8="})

    def test_multiple_bug_cycles_do_not_reclassify_history(self):
        task, root, _ = self._origin()
        task.stage_id = self._stage("stage_uat_cliente")
        first = self._wizard(task, "bug")
        first.action_confirm()
        internal = self._hours(task, 1)
        task.stage_id = self._stage("stage_uat_cliente")
        uat = self._hours(task, 0.5)
        second = self._wizard(task, "bug")
        second.action_confirm()
        correction = self._hours(task, 1)
        self.assertNotEqual(first.event_id, second.event_id)
        self.assertEqual(internal.uat_rework_event_id, first.event_id)
        self.assertEqual(correction.uat_rework_event_id, second.event_id)
        self.assertFalse(uat.uat_rework_event_id)
        self.assertEqual(root._get_budget_consumed_hours(), 0.5)
        self.assertEqual(root._get_total_consumed_hours(), 2.5)

    def test_sige_retains_internal_effort_but_excludes_chargeability(self):
        task, _, _ = self._origin()
        normal = self._hours(task, 0.5)
        task.stage_id = self._stage("stage_uat_cliente")
        self._wizard(task, "bug").action_confirm()
        internal = self._hours(task, 1)
        sheet = self.env["timesheet.sige"].create({
            "employee_id": self.employee.id,
        })
        normal.timesheet_id = sheet
        internal.timesheet_id = sheet
        self.assertGreater(sheet.required_hours, 0)
        self.assertEqual(sheet.register_hours, 1.5)
        self.assertAlmostEqual(sheet.chargeability, 0.5 / sheet.required_hours * 100)

    def test_event_report_respects_task_access(self):
        task, _, _ = self._origin()
        task.stage_id = self._stage("stage_uat_cliente")
        wizard = self._wizard(task, "misunderstanding")
        wizard.action_confirm()
        task.project_id.privacy_visibility = "followers"
        stranger = new_test_user(
            self.env, login="uat_triage_private_stranger",
            groups="project.group_project_user",
        )
        visible_task = self.env["project.task"].with_user(stranger).search([
            ("id", "=", task.id),
        ])
        visible_event = self.env["project.task.event"].with_user(stranger).search([
            ("id", "=", wizard.event_id.id),
        ])
        self.assertFalse(visible_task)
        self.assertFalse(visible_event)
        self.assertFalse(self.env["project.task.event"].with_user(stranger).read_group(
            [("id", "=", wizard.event_id.id)], ["event_type"], ["event_type"],
        ))
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            wizard.event_id.with_user(stranger).read(["description"])

    def test_event_access_includes_tasks_created_after_rule_was_used(self):
        task, _, _ = self._origin()
        task.stage_id = self._stage("stage_uat_cliente")
        first = self._wizard(task, "misunderstanding")
        first.action_confirm()
        self.env["project.task.event"].with_user(self.functional).search([]).read(["description"])
        copied = task.copy({
            "name": "New UAT task after report access",
            "stage_id": self._stage("stage_uat_cliente").id,
        })
        second = self._wizard(copied, "misunderstanding")
        second.action_confirm()
        self.assertTrue(self.env["project.task.event"].with_user(self.functional).search([
            ("id", "=", second.event_id.id),
        ]))

    def test_client_wizard_rejects_stale_proposal(self):
        _, task, _, _, _, _ = self._improvement()
        attachment = self.env["ir.attachment"].create({
            "name": "approval.txt", "datas": "QXByb2JhZG8=",
            "res_model": "project.task", "res_id": task.id,
        })
        wizard = self.env["project.task.uat.client.wizard"].with_user(self.functional).create({
            "task_id": task.id, "description": "Aprobado",
            "attachment_ids": [(6, 0, attachment.ids)],
        })
        task.estimated_dev_hours = 1
        with self.assertRaises(UserError), self.env.cr.savepoint():
            wizard.action_confirm()

    def test_order_cancellation_invalidates_approval_and_blocks_hours(self):
        _, task, _, _, order, _ = self._improvement()
        self._client_approve(task)
        task.with_user(self.seller).action_approve_uat_commercial()
        order.action_confirm()
        task.stage_id = self._stage("stage_desarrollo")
        order.action_cancel()
        self.assertEqual(order.state, "cancel")
        self.assertFalse(task.uat_ready)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self._hours(task, 0.5)

    def test_approved_timesheet_keeps_contract_after_line_change(self):
        _, task, _, _, order, line = self._improvement()
        self._client_approve(task)
        task.with_user(self.seller).action_approve_uat_commercial()
        order.action_confirm()
        task.stage_id = self._stage("stage_desarrollo")
        entry = self._hours(task, 0.5)
        new_order, new_line = self._create_order()
        new_order.user_id = self.seller
        new_line.write({
            "project_id": task.project_id.id, "contrated_hours": 4,
            "uat_support_hours": 1,
        })
        task.uat_sale_line_id = new_line
        self.assertFalse(task.uat_ready)
        self.assertEqual(entry.so_line, line)
        self.assertEqual(entry.uat_budget_line_id, line)
        self.assertEqual(line.uat_quotation_task_id, task)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            entry.project_id = False
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self._hours(line.task_id, 0.5)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            entry.unit_amount = 1
        with self.assertRaises(UserError), self.env.cr.savepoint():
            entry.so_line = new_line

    def test_internal_hours_cannot_be_forged_or_retroactive(self):
        task, _, _ = self._origin()
        old = self._hours(task, 0.5)
        task.stage_id = self._stage("stage_uat_cliente")
        self._wizard(task, "bug").action_confirm()
        with self.assertRaises(UserError), self.env.cr.savepoint():
            old.unit_amount = 1
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.env["account.analytic.line"].create({
                "task_id": task.id, "project_id": task.project_id.id,
                "unit_amount": 1, "uat_rework_event_id": task.uat_bug_event_id.id,
            })

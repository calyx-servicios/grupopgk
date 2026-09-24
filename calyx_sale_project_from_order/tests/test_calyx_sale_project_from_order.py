from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCalyxSaleProjectFromOrder(TransactionCase):
    """Verifica la generación Calyx desde órdenes de venta directas."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.calyx_sale_project_from_order_enabled = True
        cls.partner = cls.company.partner_id
        cls.pm = cls.env.ref("base.user_admin")
        cls.product = cls.env["product.product"].create(
            {
                "name": "Servicio Calyx de prueba",
                "type": "service",
                "service_tracking": "project_only",
                "list_price": 100.0,
            }
        )
        cls.analytic_account = cls._create_analytic_account("Cuenta padre Calyx")

    @classmethod
    def _create_analytic_account(cls, name):
        account_model = cls.env["account.analytic.account"]
        company_value = cls.company.id
        if account_model._fields["company_id"].type == "many2many":
            company_value = [(6, 0, cls.company.ids)]
        return account_model.create(
            {
                "name": name,
                "partner_id": cls.partner.id,
                "company_id": company_value,
            }
        )

    def _create_order(self):
        order_values = {
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "date_of_issue": fields.Datetime.now(),
            "client_order_ref": "CALYX-VENTA-DIRECTA-TEST",
            "calyx_project_manager_id": self.pm.id,
        }
        if "partner" in self.env["sale.order"]._fields:
            order_values["partner"] = self.pm.id
        order = self.env["sale.order"].with_company(self.company).create(order_values)
        line = self.env["sale.order.line"].with_company(self.company).create(
            {
                "order_id": order.id,
                "product_id": self.product.id,
                "product_uom_qty": 1.0,
                "product_uom": self.product.uom_id.id,
                "name": self.product.name,
                "price_unit": self.product.list_price,
                "project_name": "Implementación Calyx Test",
                "analytic_account_id": self.analytic_account.id,
                "contrated_hours": 12.0,
            }
        )
        return order, line

    def test_confirmacion_crea_proyecto_unico_y_tarea_por_linea(self):
        """La confirmación crea un proyecto y una tarea protegida por línea."""
        order, line = self._create_order()
        order.action_confirm()
        line.invalidate_cache()
        order.invalidate_cache()
        project = line.project_id
        self.assertTrue(project)
        self.assertIn(project, order.project_ids)
        self.assertEqual(project.user_id, self.pm)
        self.assertEqual(project.calyx_project_manager_id, self.pm)
        if "project_manager" in project._fields:
            self.assertEqual(project.project_manager, self.pm.name)
        if "partner" in project._fields:
            self.assertEqual(project.partner, self.pm)
        self.assertEqual(project.sale_line_id, line)
        root = line.task_id
        self.assertEqual(line.task_id, root)
        self.assertTrue(root.is_calyx_sale_root)
        self.assertEqual(root.calyx_budget_hours, 12.0)
        self.assertEqual(root.planned_hours, 12.0)

    def test_confirmacion_no_duplica_proyecto_ni_tareas(self):
        """Reejecutar la sincronización no crea proyectos ni tareas adicionales."""
        order, line = self._create_order()
        order.action_confirm()
        first_project = line.project_id
        first_task = line.task_id
        order._calyx_sync_sale_projects()
        self.assertEqual(line.project_id, first_project)
        self.assertEqual(line.task_id, first_task)
        self.assertEqual(
            self.env["project.project"].search_count(
                [("sale_line_id", "=", line.id)]
            ),
            1,
        )

    def test_confirmacion_dos_lineas_crea_un_proyecto_y_dos_tareas(self):
        """Una OV con dos líneas crea un solo proyecto con dos tareas raíz."""
        order, line_1 = self._create_order()
        product_2 = self.env["product.product"].create(
            {
                "name": "Servicio Calyx de prueba 2",
                "type": "service",
                "service_tracking": "task_in_project",
                "list_price": 200.0,
            }
        )
        line_2 = self.env["sale.order.line"].with_company(self.company).create(
            {
                "order_id": order.id,
                "product_id": product_2.id,
                "product_uom_qty": 1.0,
                "product_uom": product_2.uom_id.id,
                "name": product_2.name,
                "price_unit": product_2.list_price,
                "project_name": "Implementación Calyx Test 2",
                "analytic_account_id": self.analytic_account.id,
                "contrated_hours": 20.0,
            }
        )
        order.action_confirm()
        line_1.invalidate_cache()
        line_2.invalidate_cache()
        order.invalidate_cache()
        self.assertTrue(line_1.project_id)
        self.assertEqual(line_1.project_id, line_2.project_id)
        self.assertEqual(len(order.project_ids), 1)
        self.assertTrue(line_1.task_id.is_calyx_sale_root)
        self.assertTrue(line_2.task_id.is_calyx_sale_root)
        self.assertNotEqual(line_1.task_id, line_2.task_id)
        self.assertEqual(line_1.task_id.calyx_budget_hours, 12.0)
        self.assertEqual(line_2.task_id.calyx_budget_hours, 20.0)

    def test_bloquea_creacion_manual_de_proyecto(self):
        """La compañía activa no permite crear proyectos manuales."""
        with self.assertRaises(ValidationError):
            self.env["project.project"].create(
                {"name": "Proyecto manual bloqueado", "company_id": self.company.id}
            )

    def test_contratos_puede_crear_proyecto_manual(self):
        """Contratos autorizado puede crear proyectos sin OV en Calyx."""
        group = self.env.ref(
            "calyx_sale_project_from_order.group_contracts_project_creation_allowed"
        )
        self.pm.write({"groups_id": [(4, group.id)]})
        project = self.env["project.project"].with_user(self.pm).create(
            {
                "name": "Proyecto manual autorizado",
                "company_id": self.company.id,
                "calyx_project_manager_id": self.pm.id,
            }
        )
        self.assertTrue(project)
        self.assertFalse(project.sale_line_id)
        self.assertEqual(project.user_id, self.pm)

    def test_tarea_raiz_bloquea_edicion_y_partes(self):
        """La raíz contractual no se edita ni recibe partes de horas."""
        order, line = self._create_order()
        order.action_confirm()
        root = line.task_id
        with self.assertRaises(AccessError):
            root.write({"planned_hours": 20.0})
        with self.assertRaises(UserError):
            self.env["account.analytic.line"].create(
                {"name": "Parte inválido", "task_id": root.id}
            )

    def test_linea_confirmada_queda_congelada(self):
        """No permite cambiar horas, producto ni cuenta analítica tras confirmar."""
        order, line = self._create_order()
        order.action_confirm()
        with self.assertRaises(ValidationError):
            line.write({"contrated_hours": 15.0})
        with self.assertRaises(ValidationError):
            line.unlink()

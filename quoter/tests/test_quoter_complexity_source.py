# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from unittest.mock import patch

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestQuoterComplexitySource(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Level = cls.env["quoter.complexity.level"]
        cls.low = Level.create({"name": "Test bajo", "sequence": 110, "labor_agreement_ok": True})
        cls.medium = Level.create({"name": "Test medio", "sequence": 120, "labor_agreement_ok": True})
        cls.high = Level.create({"name": "Test alto", "sequence": 130, "labor_agreement_ok": True})
        levels = cls.low | cls.medium | cls.high
        Agreement = cls.env["quoter.labor.agreement"]
        cls.ag_low = Agreement.create({"name": "Test conv bajo", "complexity_level_id": cls.low.id})
        cls.ag_low2 = Agreement.create({"name": "Test conv bajo 2", "complexity_level_id": cls.low.id})
        cls.ag_medium = Agreement.create(
            {"name": "Test conv medio", "complexity_level_id": cls.medium.id}
        )
        cls.ag_high = Agreement.create({"name": "Test conv alto", "complexity_level_id": cls.high.id})
        Area = cls.env["quoter.professional.area"]
        cls.payroll_area = Area.create(
            {
                "name": "Test Payroll",
                "hour_matrix_mode": "regular",
                "complexity_level_ids": [(6, 0, levels.ids)],
                "complexity_source": "labor_agreement",
                "allow_change_complexity_level": True,
            }
        )
        cls.tax_area = Area.create(
            {
                "name": "Test Tax",
                "hour_matrix_mode": "regular",
                "complexity_level_ids": [(6, 0, levels.ids)],
                "complexity_source": "company_size",
                "size_level_ids": [
                    (0, 0, {"company_size": "micro", "complexity_level_id": cls.low.id}),
                    (0, 0, {"company_size": "small", "complexity_level_id": cls.low.id}),
                    (0, 0, {"company_size": "medium", "complexity_level_id": cls.medium.id}),
                    (0, 0, {"company_size": "large", "complexity_level_id": cls.high.id}),
                ],
            }
        )
        cls.services = cls.env.ref("quoter.quoter_industry_services")
        # partner_identification_required exige CUIT al crear contactos: uso uno existente.
        cls.partner = cls.env.company.partner_id

    def setUp(self):
        super().setUp()
        # Estos tests cubren el cálculo del nivel, no los permisos del workflow.
        patcher = patch.object(
            type(self.env["sale.order"]),
            "_quoter_user_is_cotizador_profile",
            return_value=True,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _payroll_level(self, agreements):
        return self.payroll_area._quoter_level_for_labor_agreements(agreements)

    def _create_block(self, area):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "is_quotation": True,
                "quoter_q_competitors": "Ninguno",
                "quoter_q_budget": "Sin info",
                "quoter_q_current_payment": "N/A",
                "quoter_q_notes": "Test",
                "date_of_issue": fields.Date.today(),
            }
        )
        # Como en la UI: el bloque se crea al agregar el área a la cotización.
        order.write({"quoter_area_ids": [(4, area.id)]})
        return order.quoter_area_block_ids.filtered(lambda b: b.area_id == area)

    def test_payroll_rule_no_agreement_is_lowest(self):
        self.assertEqual(self._payroll_level(self.env["quoter.labor.agreement"]), self.low)

    def test_payroll_rule_single_agreement_keeps_its_level(self):
        self.assertEqual(self._payroll_level(self.ag_low), self.low)
        self.assertEqual(self._payroll_level(self.ag_high), self.high)

    def test_payroll_rule_two_agreements_at_least_medium(self):
        self.assertEqual(self._payroll_level(self.ag_low | self.ag_low2), self.medium)
        self.assertEqual(self._payroll_level(self.ag_low | self.ag_medium), self.medium)
        self.assertEqual(self._payroll_level(self.ag_low | self.ag_high), self.high)

    def test_payroll_rule_three_agreements_always_highest(self):
        agreements = self.ag_low | self.ag_low2 | self.ag_medium
        self.assertEqual(self._payroll_level(agreements), self.high)

    def test_company_size_thresholds_are_inclusive(self):
        services = self.services
        self.assertFalse(services._quoter_company_size(0))
        self.assertEqual(services._quoter_company_size(374060000), "micro")
        self.assertEqual(services._quoter_company_size(374060001), "small")
        self.assertEqual(services._quoter_company_size(2255110000), "small")
        self.assertEqual(services._quoter_company_size(26655990000), "medium")
        self.assertEqual(services._quoter_company_size(26655990001), "large")

    def test_company_size_uses_threshold_in_force(self):
        self.env["quoter.sicypyme.threshold"].create(
            {
                "industry_id": self.services.id,
                "date_from": "2027-01-01",
                "micro_max": 500000000,
                "small_max": 3000000000,
                "medium_max": 30000000000,
            }
        )
        revenue = 450000000
        self.assertEqual(self.services._quoter_company_size(revenue, date="2026-06-30"), "small")
        self.assertEqual(self.services._quoter_company_size(revenue, date="2027-06-30"), "micro")

    def test_block_payroll_level_follows_agreements(self):
        block = self._create_block(self.payroll_area)
        self.assertEqual(block.complexity_level_id, self.low)
        block.write({"labor_agreement_ids": [(6, 0, (self.ag_low | self.ag_low2).ids)]})
        self.assertEqual(block.complexity_level_id, self.medium)
        block.write({"labor_agreement_ids": [(4, self.ag_medium.id)]})
        self.assertEqual(block.complexity_level_id, self.high)

    def test_block_tax_level_follows_company_size(self):
        block = self._create_block(self.tax_area)
        self.assertFalse(block.complexity_level_id)
        block.write({"industry_id": self.services.id, "prev_year_revenue": 1000000000})
        self.assertEqual(block.company_size, "small")
        self.assertEqual(block.complexity_level_id, self.low)
        block.write({"prev_year_revenue": 30000000000})
        self.assertEqual(block.company_size, "large")
        self.assertEqual(block.complexity_level_id, self.high)

    def test_block_manual_level_is_recalculated(self):
        block = self._create_block(self.payroll_area)
        block.write({"complexity_level_id": self.high.id})
        self.assertEqual(block.complexity_level_id, self.low)

    def test_block_frozen_level_rejects_manual_change(self):
        block = self._create_block(self.tax_area)
        block.write({"industry_id": self.services.id, "prev_year_revenue": 1000000000})
        with self.assertRaises(ValidationError):
            block.write({"complexity_level_id": self.high.id})

    def test_output_hours_rounding_before_minimum(self):
        area = self.tax_area
        area.write({"output_hours_rounding": 0.5, "output_hours_minimum": 0.0})
        self.assertEqual(area._apply_output_hours_minimum(37.25), 37.5)
        self.assertEqual(area._apply_output_hours_minimum(9.3), 9.5)
        self.assertEqual(area._apply_output_hours_minimum(0.12), 0.0)
        area.output_hours_minimum = 1.0
        self.assertEqual(area._apply_output_hours_minimum(0.12), 1.0)

    def _create_audit_area(self, levels):
        services_branch = self.env.ref("quoter.quoter_area_branch_industry_services")
        commerce_branch = self.env.ref("quoter.quoter_area_branch_industry_commerce")
        sizes = ("micro", "small", "medium", "large")
        return self.env["quoter.professional.area"].create(
            {
                "name": "Test Auditoría",
                "hour_matrix_mode": "regular",
                "group_id": self.env.ref("quoter.group_quoter_auditoria").id,
                "complexity_level_ids": [(6, 0, levels.ids)],
                "branch_ids": [(6, 0, (services_branch | commerce_branch).ids)],
                "matrix_branch_id": services_branch.id,
                "allow_change_complexity_level": True,
                "complexity_source": "company_size",
                "size_level_ids": [
                    (0, 0, {"company_size": size, "complexity_level_id": level.id})
                    for size, level in zip(sizes, levels)
                ],
            }
        )

    def test_size_levels_can_share_level(self):
        # Micro pasa a riesgo medio: cotiza igual que Pequeña.
        area = self._create_audit_area(self.medium + self.medium + self.high + self.high)
        block = self._create_block(area)
        block.write({"industry_id": self.services.id, "prev_year_revenue": 300000000})
        self.assertEqual(block.company_size, "micro")
        self.assertEqual(block.complexity_level_id, self.medium)

    def test_size_levels_must_be_complete(self):
        with self.assertRaises(ValidationError):
            self.tax_area.write({"size_level_ids": [(2, self.tax_area.size_level_ids[:1].id)]})

    def test_size_level_must_belong_to_area(self):
        other = self.env["quoter.complexity.level"].create({"name": "Test ajeno"})
        with self.assertRaises(ValidationError):
            self.tax_area.size_level_ids[:1].complexity_level_id = other

    def test_recompute_draft_levels(self):
        block = self._create_block(self.tax_area)
        block.write({"industry_id": self.services.id, "prev_year_revenue": 300000000})
        in_approval = self._create_block(self.tax_area)
        in_approval.write({"industry_id": self.services.id, "prev_year_revenue": 300000000})
        in_approval.order_id.with_context(quoter_workflow_transition=True).write(
            {"quoter_workflow_state": "en_aprobacion"}
        )
        micro = self.tax_area.size_level_ids.filtered(lambda r: r.company_size == "micro")
        micro.complexity_level_id = self.medium
        # El cambio de configuración no toca las cotizaciones hasta recalcular.
        self.assertEqual(block.complexity_level_id, self.low)
        micro.action_quoter_recompute_draft_levels()
        self.assertEqual(block.complexity_level_id, self.medium)
        self.assertEqual(in_approval.complexity_level_id, self.low)

    def test_audit_block_branch_follows_industry(self):
        very_high = self.env["quoter.complexity.level"].create(
            {"name": "Test muy alto", "sequence": 140}
        )
        area = self._create_audit_area(self.low | self.medium | self.high | very_high)
        block = self._create_block(area)
        block.write({"industry_id": self.services.id, "prev_year_revenue": 30000000000})
        self.assertEqual(block.complexity_level_id, very_high)
        self.assertEqual(block.branch_id, self.services.branch_id)
        commerce = self.env.ref("quoter.quoter_industry_commerce")
        block.write({"industry_id": commerce.id})
        self.assertEqual(block.branch_id, commerce.branch_id)
        self.assertEqual(block.complexity_level_id, self.high)

    def test_recompute_draft_levels_without_cotizador_profile(self):
        block = self._create_block(self.tax_area)
        block.write({"industry_id": self.services.id, "prev_year_revenue": 300000000})
        micro = self.tax_area.size_level_ids.filtered(lambda r: r.company_size == "micro")
        micro.complexity_level_id = self.medium
        # Administrador del cotizador sin perfil Cotizador.
        with patch.object(
            type(self.env["sale.order"]),
            "_quoter_user_is_cotizador_profile",
            return_value=False,
        ):
            self.tax_area.action_quoter_recompute_draft_levels()
        self.assertEqual(block.complexity_level_id, self.medium)

    def test_agreement_requires_level_ok_for_agreements(self):
        not_ok = self.env["quoter.complexity.level"].create({"name": "Test no apto"})
        with self.assertRaises(ValidationError):
            self.env["quoter.labor.agreement"].create(
                {"name": "Test conv nivel no apto", "complexity_level_id": not_ok.id}
            )
        domain = self.env["quoter.labor.agreement"]._fields["complexity_level_id"].domain
        self.assertEqual(domain, [("labor_agreement_ok", "=", True)])

    def test_level_in_use_cannot_stop_being_ok_for_agreements(self):
        with self.assertRaises(ValidationError):
            self.low.labor_agreement_ok = False
        unused = self.env["quoter.complexity.level"].create(
            {"name": "Test apto sin uso", "labor_agreement_ok": True}
        )
        unused.labor_agreement_ok = False
        self.assertFalse(unused.labor_agreement_ok)

    def test_replace_branches_reassigns_active_branch(self):
        # Como desde el formulario: la rama activa no se edita, solo la lista de ramas.
        services_branch = self.env.ref("quoter.quoter_area_branch_industry_services")
        commerce_branch = self.env.ref("quoter.quoter_area_branch_industry_commerce")
        mining_branch = self.env.ref("quoter.quoter_area_branch_industry_mining")
        area = self.env["quoter.professional.area"].create(
            {
                "name": "Test ramas",
                "hour_matrix_mode": "regular",
                "branch_ids": [(6, 0, (services_branch | commerce_branch).ids)],
                "matrix_branch_id": services_branch.id,
            }
        )
        area.write({"branch_ids": [(6, 0, mining_branch.ids)]})
        self.assertEqual(area.matrix_branch_id, mining_branch)
        with self.assertRaises(ValidationError):
            area.write({"matrix_branch_id": services_branch.id})

    def test_replace_branches_skips_quotations_out_of_preparation(self):
        services_branch = self.env.ref("quoter.quoter_area_branch_industry_services")
        mining_branch = self.env.ref("quoter.quoter_area_branch_industry_mining")
        area = self.env["quoter.professional.area"].create(
            {
                "name": "Test ramas cotizaciones",
                "hour_matrix_mode": "regular",
                "branch_ids": [(6, 0, services_branch.ids)],
                "matrix_branch_id": services_branch.id,
            }
        )
        draft = self._create_block(area)
        approved = self._create_block(area)
        approved.order_id.with_context(quoter_workflow_transition=True).write(
            {"quoter_workflow_state": "aprobado_cliente"}
        )
        # Sin perfil Cotizador (administrador del cotizador) y con una cotización aprobada.
        with patch.object(
            type(self.env["sale.order"]),
            "_quoter_user_is_cotizador_profile",
            return_value=False,
        ):
            area.write({"branch_ids": [(6, 0, mining_branch.ids)]})
        self.assertEqual(draft.branch_id, mining_branch)
        self.assertEqual(approved.branch_id, services_branch)

    def test_size_levels_created_before_choosing_company_size(self):
        # Desde el menú: primero las 4 filas, después «Tamaño de empresa» en el área.
        area = self.env["quoter.professional.area"].create(
            {
                "name": "Test filas antes",
                "hour_matrix_mode": "regular",
                "complexity_level_ids": [(6, 0, (self.low | self.medium | self.high).ids)],
            }
        )
        SizeLevel = self.env["quoter.area.size.level"]
        rows = SizeLevel.create(
            [
                {"area_id": area.id, "company_size": size, "complexity_level_id": level.id}
                for size, level in zip(
                    ("micro", "small", "medium", "large"),
                    (self.low, self.low, self.medium, self.high),
                )
            ]
        )
        area.complexity_source = "company_size"
        # Ya calcula por tamaño: no se puede borrar una fila suelta.
        with self.assertRaises(ValidationError):
            rows[:1].unlink()
        # Desde el formulario del área sí se puede reemplazar una fila en el mismo guardado.
        area.write(
            {
                "size_level_ids": [
                    (2, rows[0].id),
                    (0, 0, {"company_size": "micro", "complexity_level_id": self.medium.id}),
                ]
            }
        )
        self.assertEqual(area._quoter_level_for_company_size("micro"), self.medium)

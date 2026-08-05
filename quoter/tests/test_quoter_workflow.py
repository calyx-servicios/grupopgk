# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestQuoterWorkflow(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Cliente test workflow"})
        cls.cotizador_group = cls.env.ref("quoter.group_quoter_cotizador")
        cls.cotizador_user = cls.env["res.users"].create(
            {
                "name": "Usuario Cotizador Test",
                "login": "quoter_cotizador_test",
                "email": "quoter_cotizador_test@example.com",
                "groups_id": [
                    (6, 0, [cls.env.ref("base.group_user").id, cls.cotizador_group.id])
                ],
            }
        )

    def _create_quotation(self, user=None):
        env = self.env(user=user) if user else self.env
        return env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "is_quotation": True,
                "quoter_q_competitors": "Ninguno",
                "quoter_q_budget": "Sin info",
                "quoter_q_current_payment": "N/A",
                "quoter_q_notes": "Test",
            }
        )

    def test_cotizador_can_write_in_preparation(self):
        order = self._create_quotation(user=self.cotizador_user)
        self.assertEqual(order.quoter_workflow_state, "en_preparacion")
        order.write({"quoter_q_notes": "Actualizado en preparación"})
        self.assertEqual(order.quoter_q_notes, "Actualizado en preparación")

    def test_cotizador_cannot_write_outside_preparation(self):
        order = self._create_quotation(user=self.cotizador_user)
        order.with_context(quoter_workflow_transition=True).write(
            {"quoter_workflow_state": "en_aprobacion"}
        )
        with self.assertRaises(AccessError):
            order.write({"quoter_q_notes": "Intento fuera de preparación"})

    def test_submit_for_approval_changes_state(self):
        order = self._create_quotation(user=self.cotizador_user)
        order.action_quoter_submit_for_approval()
        self.assertEqual(order.quoter_workflow_state, "en_aprobacion")

# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged("post_install", "-at_install")
class TestQuoterAreaConfigAccess(TransactionCase):
    """Quoter - Administrador configura áreas sin pertenecer a Quoter - Gerente."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        level = cls.env["quoter.complexity.level"].create({"name": "Test nivel config"})
        cls.area = cls.env["quoter.professional.area"].create(
            {
                "name": "Test área config",
                "hour_matrix_mode": "regular",
                "complexity_level_ids": [(6, 0, level.ids)],
            }
        )
        cls.admin_user = new_test_user(
            cls.env, login="quoter_cfg_admin", groups="quoter.group_quoter_admin"
        )
        cls.manager_user = new_test_user(
            cls.env, login="quoter_cfg_manager", groups="quoter.group_quoter_manager"
        )
        # El cotizador tiene escritura sobre áreas por ACL, pero no puede configurarlas.
        cls.cotizador_user = new_test_user(
            cls.env, login="quoter_cfg_cotizador", groups="quoter.group_quoter_cotizador"
        )
        cls.form_view = cls.env.ref("quoter.view_quoter_professional_area_form")

    def _form_view_for(self, user):
        return (
            self.env["quoter.professional.area"]
            .with_user(user)
            .fields_view_get(view_id=self.form_view.id, view_type="form")
        )

    def test_admin_is_not_manager(self):
        self.assertTrue(self.admin_user.has_group("quoter.group_quoter_admin"))
        self.assertFalse(self.admin_user.has_group("quoter.group_quoter_manager"))

    def test_form_keeps_cerrado_for_every_user(self):
        # Los attrs de complexity_level_ids y hour_matrix_mode usan «cerrado»: si la vista lo
        # quita, el cliente web falla con «Unknown field cerrado in domain».
        for user in (self.admin_user, self.manager_user, self.cotizador_user):
            with self.subTest(user=user.login):
                self.assertIn("cerrado", self._form_view_for(user)["fields"])

    def test_form_config_controls_by_group(self):
        for user, visible in (
            (self.admin_user, True),
            (self.manager_user, True),
            (self.cotizador_user, False),
        ):
            with self.subTest(user=user.login):
                arch = etree.fromstring(self._form_view_for(user)["arch"])
                self.assertEqual(
                    bool(self._shown(arch, "//button[@name='action_quoter_area_unlock_config']")),
                    visible,
                )
                # Interruptor de «Cerrado»: el único nodo del campo que no es invisible="1".
                self.assertEqual(bool(self._shown(arch, "//field[@name='cerrado']")), visible)

    @staticmethod
    def _shown(arch, xpath):
        # Odoo 15 no quita los nodos con «groups» que el usuario no tiene: los deja
        # invisibles. Solo cuentan los que no quedan invisibles siempre.
        return [
            node
            for node in arch.xpath(xpath)
            if '"invisible": true' not in node.get("modifiers", "")
        ]

    def test_admin_can_save_area(self):
        # write() lee «cerrado»; sin caché, antes fallaba por permisos de campo.
        self.area.invalidate_cache()
        self.area.with_user(self.admin_user).write({"name": "Test área config editada"})
        self.assertEqual(self.area.name, "Test área config editada")

    def test_config_users_can_toggle_cerrado(self):
        for user in (self.admin_user, self.manager_user):
            with self.subTest(user=user.login):
                self.area.with_user(user).write({"cerrado": True})
                self.assertTrue(self.area.cerrado)
                self.area.with_user(user).write({"cerrado": False})
                self.assertFalse(self.area.cerrado)

    def test_cotizador_cannot_toggle_cerrado(self):
        with self.assertRaises(AccessError):
            self.area.with_user(self.cotizador_user).write({"cerrado": True})
        self.assertFalse(self.area.cerrado)

    def test_table_editor_access(self):
        for user in (self.admin_user, self.manager_user):
            with self.subTest(user=user.login):
                self.area.quoter_config_edit_mode = False
                self.area.with_user(user).action_quoter_area_unlock_config()
                self.assertTrue(self.area.quoter_config_edit_mode)
        self.area.quoter_config_edit_mode = False
        with self.assertRaises(AccessError):
            self.area.with_user(self.cotizador_user).action_quoter_area_unlock_config()
        self.assertFalse(self.area.quoter_config_edit_mode)

    def test_matrix_read_only_by_group(self):
        self.area.quoter_config_edit_mode = True
        self.assertFalse(self.area.with_user(self.admin_user)._formula_matrix_read_only())
        self.assertFalse(self.area.with_user(self.manager_user)._formula_matrix_read_only())
        self.assertTrue(self.area.with_user(self.cotizador_user)._formula_matrix_read_only())

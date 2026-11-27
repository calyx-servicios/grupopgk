# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from lxml import etree

from odoo.exceptions import AccessError
from odoo.fields import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user
from odoo.tools.safe_eval import safe_eval

from ..models.res_groups import QUOTER_MANAGED_GROUP_XMLIDS


@tagged("post_install", "-at_install")
class TestQuoterUserGroupsAccess(TransactionCase):
    """Quoter - Administrador gestiona los usuarios de los grupos del cotizador sin Ajustes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin_user = new_test_user(
            cls.env, login="quoter_grp_admin", groups="quoter.group_quoter_admin"
        )
        cls.cotizador_user = new_test_user(
            cls.env, login="quoter_grp_cotizador", groups="quoter.group_quoter_cotizador"
        )
        cls.target_user = new_test_user(cls.env, login="quoter_grp_target", groups="base.group_user")
        cls.tax_group = cls.env.ref("quoter.group_quoter_tax")
        cls.access_group = cls.env.ref("quoter.group_quoter_access")
        cls.menu = cls.env.ref("quoter.menu_quoter_admin_user_groups")
        cls.action = cls.env.ref("quoter.action_quoter_admin_user_groups")

    def test_admin_has_no_native_access_rights_settings(self):
        self.assertTrue(self.admin_user.has_group("quoter.group_quoter_admin"))
        self.assertFalse(self.admin_user.has_group("base.group_erp_manager"))
        self.assertFalse(
            self.env["res.groups"].with_user(self.admin_user).check_access_rights(
                "write", raise_exception=False
            )
        )

    def test_admin_adds_and_removes_users(self):
        group = self.tax_group.with_user(self.admin_user)
        group.write({"users": [Command.link(self.target_user.id)]})
        self.assertTrue(self.target_user.has_group("quoter.group_quoter_tax"))
        # Los grupos implícitos se propagan igual que cuando lo hace un administrador.
        self.assertIn(self.target_user, self.access_group.users)

        group.write({"users": [Command.unlink(self.target_user.id)]})
        self.assertFalse(self.target_user.has_group("quoter.group_quoter_tax"))

    def test_admin_saves_form_users(self):
        # El cliente web guarda el many2many con un comando SET.
        group = self.tax_group.with_user(self.admin_user)
        new_users = self.tax_group.users | self.target_user
        group.write({"users": [Command.set(new_users.ids)]})
        self.assertEqual(self.tax_group.users, new_users)
        self.assertEqual(self.tax_group.write_uid, self.admin_user)

    def test_admin_cannot_edit_other_group_fields(self):
        group = self.tax_group.with_user(self.admin_user)
        for vals in (
            {"name": "Otro nombre"},
            {"implied_ids": [Command.link(self.env.ref("base.group_system").id)]},
            {"users": [Command.link(self.target_user.id)], "comment": "x"},
        ):
            with self.subTest(vals=vals), self.assertRaises(AccessError):
                group.write(vals)

    def test_admin_cannot_touch_other_groups(self):
        for xmlid in ("base.group_system", "base.group_erp_manager", "quoter.group_quoter_access"):
            group = self.env.ref(xmlid).with_user(self.admin_user)
            with self.subTest(group=xmlid), self.assertRaises(AccessError):
                group.write({"users": [Command.link(self.target_user.id)]})
        mixed = (self.tax_group | self.env.ref("base.group_system")).with_user(self.admin_user)
        with self.assertRaises(AccessError):
            mixed.write({"users": [Command.link(self.target_user.id)]})
        self.assertFalse(self.target_user.has_group("base.group_system"))

    def test_admin_cannot_create_or_edit_users_through_group(self):
        group = self.tax_group.with_user(self.admin_user)
        for commands in (
            [Command.create({"name": "Nuevo", "login": "quoter_grp_new"})],
            [Command.update(self.target_user.id, {"name": "Cambiado"})],
            [Command.delete(self.target_user.id)],
        ):
            with self.subTest(command=commands[0][0]), self.assertRaises(AccessError):
                group.write({"users": commands})

    def test_non_admin_cannot_manage_users(self):
        group = self.tax_group.with_user(self.cotizador_user)
        with self.assertRaises(AccessError):
            group.write({"users": [Command.link(self.target_user.id)]})

    def test_menu_only_for_quoter_admin(self):
        self.assertEqual(self.menu.groups_id, self.env.ref("quoter.group_quoter_admin"))
        self.assertEqual(self.menu.parent_id, self.env.ref("quoter.menu_quoter_configuration"))
        for user, visible in ((self.admin_user, True), (self.cotizador_user, False)):
            with self.subTest(user=user.login):
                visible_ids = self.env["ir.ui.menu"].with_user(user)._visible_menu_ids()
                self.assertEqual(self.menu.id in visible_ids, visible)

    def test_action_lists_only_quoter_groups(self):
        managed = self.env["res.groups"]._quoter_managed_groups()
        self.assertEqual(len(managed), len(QUOTER_MANAGED_GROUP_XMLIDS))
        settings_action = self.env.ref("quoter.action_quoter_security_groups")
        for action in (self.action, settings_action):
            with self.subTest(action=action.name):
                found = self.env["res.groups"].with_user(self.admin_user).search(
                    safe_eval(action.domain)
                )
                self.assertEqual(found, managed.with_user(self.admin_user))

    def test_form_is_editable_for_admin(self):
        view = (
            self.env["res.groups"]
            .with_user(self.admin_user)
            .fields_view_get(view_id=self.env.ref("quoter.view_quoter_user_groups_form").id)
        )
        arch = etree.fromstring(view["arch"])
        self.assertEqual(arch.get("edit"), "1")
        self.assertEqual(arch.get("create"), "0")
        self.assertEqual(arch.get("delete"), "0")

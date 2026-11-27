# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models
from odoo.fields import Command

# Grupos cuyos usuarios gestiona Quoter - Administrador desde Cotizador → Configuración →
# Grupos de usuarios. Son los mismos que filtra la acción de Ajustes
# (quoter.action_quoter_security_groups) y la acción del menú
# (quoter.action_quoter_admin_user_groups): si se agrega o quita uno, actualizar las tres listas.
QUOTER_MANAGED_GROUP_XMLIDS = (
    "quoter.group_quoter_admin",
    "quoter.group_quoter_manager",
    "quoter.group_quoter_partner",
    "quoter.group_quoter_cotizador",
    "quoter.group_quoter_aprobador",
    "quoter.group_quoter_contratos",
    "quoter.group_quoter_tax",
    "quoter.group_quoter_auditoria",
    "quoter.group_quoter_formula",
    "quoter.group_quoter_payroll",
    "quoter.group_quoter_finanzas",
)

# Solo vincular o desvincular usuarios existentes: sin crear, editar ni borrar usuarios.
_QUOTER_USER_LINK_COMMANDS = {Command.UNLINK, Command.LINK, Command.CLEAR, Command.SET}


class ResGroups(models.Model):
    _inherit = "res.groups"

    @api.model
    def _quoter_managed_groups(self):
        groups = self.browse()
        for xmlid in QUOTER_MANAGED_GROUP_XMLIDS:
            groups |= self.env.ref(xmlid, raise_if_not_found=False) or self.browse()
        return groups

    def _quoter_admin_can_write_users(self, vals):
        """Quoter - Administrador sin Ajustes / Derechos de acceso puede cambiar los
        usuarios de los grupos del cotizador, y nada más: ni otros campos ni otros grupos."""
        if not self or self.env.su or set(vals) != {"users"}:
            return False
        commands = vals["users"]
        if not isinstance(commands, (list, tuple)) or not all(
            isinstance(command, (list, tuple))
            and command
            and command[0] in _QUOTER_USER_LINK_COMMANDS
            for command in commands
        ):
            return False
        if self.check_access_rights("write", raise_exception=False):
            return False
        if not self.env.user.has_group("quoter.group_quoter_admin"):
            return False
        return not (self - self._quoter_managed_groups())

    def write(self, vals):
        if self._quoter_admin_can_write_users(vals):
            # El ACL nativo de res.groups solo deja escribir a Ajustes / Derechos de acceso.
            # Los grupos implícitos se propagan por SQL y Odoo no aplica sudo a los comandos
            # sobre res.users (_allow_sudo_commands = False).
            return super(ResGroups, self.sudo()).write(vals)
        return super().write(vals)

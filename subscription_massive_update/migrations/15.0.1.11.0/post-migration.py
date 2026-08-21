# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """El registro noupdate=1 no se refresca solo: se fuerza el group_id
    por ORM para que el botón Crear de IPC Mensual quede atado al mismo
    grupo que ya controla la visibilidad del menú de Configuración.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    access = env.ref(
        "subscription_massive_update.ir_model_access_subscription_ipc_monthly_manager_all",
        raise_if_not_found=False,
    )
    manager_group = env.ref("account.group_account_manager", raise_if_not_found=False)
    if access and manager_group:
        access.write({"group_id": manager_group.id})

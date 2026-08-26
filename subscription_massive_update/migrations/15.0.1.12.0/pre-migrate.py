# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Los grupos custom (Contratos/Administrador/Socios) se reemplazan por
    los 2 grupos de subscription_package.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    remap = {
        "subscription_massive_update.group_subscription_contracts": (
            "subscription_package.group_subscription_user"
        ),
        "subscription_massive_update.group_subscription_partners": (
            "subscription_package.group_subscription_user"
        ),
        "subscription_massive_update.group_subscription_admin": (
            "subscription_package.group_subscription_manager"
        ),
    }

    for old_xmlid, new_xmlid in remap.items():
        old_group = env.ref(old_xmlid, raise_if_not_found=False)
        new_group = env.ref(new_xmlid, raise_if_not_found=False)
        if not old_group or not new_group:
            continue
        cr.execute(
            "UPDATE ir_model_access SET group_id = %s WHERE group_id = %s",
            (new_group.id, old_group.id),
        )

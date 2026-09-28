def post_init_hook(cr, registry):
    """Initialize root task caps from their contracted hour budgets."""
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    roots = env["project.task"].search([
        ("is_calyx_sale_root", "=", True),
        ("hours_cap", "=", 0),
    ])
    for root in roots:
        root.write({"hours_cap": root.calyx_budget_hours})
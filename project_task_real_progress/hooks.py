from odoo import SUPERUSER_ID, api


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    tasks = env["project.task"].with_context(active_test=False).search([])
    for field_name in (
        "progress_total_items",
        "progress_completed_items",
        "progress",
        "hours_consumption_percentage",
    ):
        env.add_to_compute(tasks._fields[field_name], tasks)
    tasks.recompute()

from datetime import datetime, time, timedelta

import pytz

from odoo import SUPERUSER_ID, api, fields


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    timezone = pytz.timezone("America/Argentina/Buenos_Aires")
    now = datetime.now(timezone)
    days_to_monday = (0 - now.weekday()) % 7
    next_run = now.replace(
        hour=8,
        minute=0,
        second=0,
        microsecond=0,
    ) + timedelta(days=days_to_monday)
    if next_run <= now:
        next_run += timedelta(days=7)
    cron = env.ref(
        "timesheet_activity_management.ir_cron_weekly_management_report",
        raise_if_not_found=False,
    )
    if cron:
        cron.sudo().write({
            "nextcall": fields.Datetime.to_string(
                next_run.astimezone(pytz.UTC).replace(tzinfo=None)
            ),
        })

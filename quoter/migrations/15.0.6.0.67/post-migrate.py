# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'quoter_mig_plr_hours'
        )
        """
    )
    has_mig = cr.fetchone()[0]
    LevelRange = env["quoter.product.level.range"]
    for plr in LevelRange.search([]):
        plr._sync_range_hour_lines()
        if not has_mig:
            continue
        cr.execute(
            "SELECT r1, r2, r3, r4 FROM quoter_mig_plr_hours WHERE plr_id = %s",
            (plr.id,),
        )
        row = cr.fetchone()
        if not row:
            continue
        area = plr.area_id
        if not area:
            continue
        ranges = area.area_range_ids.sorted(key=lambda r: (r.sequence, r.id))[:4]
        for i, ar in enumerate(ranges):
            if i >= len(row):
                break
            val = row[i]
            if val is None:
                continue
            line = plr.range_hour_ids.filtered(lambda h, a=ar: h.area_range_id == a)[:1]
            if line:
                line.hours = float(val)
    if has_mig:
        cr.execute("DROP TABLE IF EXISTS quoter_mig_plr_hours")

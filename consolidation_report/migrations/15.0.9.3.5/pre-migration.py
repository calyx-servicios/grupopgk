# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def migrate(cr, version):
    """Crea y llena account_id_int y sige_period_start por SQL"""
    if not version:
        return
    cr.execute(
        "ALTER TABLE account_analytic_line ADD COLUMN IF NOT EXISTS account_id_int integer"
    )
    cr.execute("UPDATE account_analytic_line SET account_id_int = account_id")
    cr.execute(
        "ALTER TABLE account_analytic_line ADD COLUMN IF NOT EXISTS sige_period_start date"
    )
    cr.execute(
        """
        UPDATE account_analytic_line l
           SET sige_period_start = ts.start_of_period
          FROM timesheet_sige ts
         WHERE ts.id = l.timesheet_id
        """
    )

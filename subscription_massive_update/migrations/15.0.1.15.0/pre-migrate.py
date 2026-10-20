# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def migrate(cr, version):
    cr.execute(
        "ALTER TABLE subscription_package "
        "ALTER COLUMN next_tariff_update TYPE date USING NULL"
    )
    cr.execute("""
        UPDATE subscription_package
        SET next_tariff_update = date_trunc(
            'month',
            last_tariff_update_at + make_interval(months => CASE tariff_update_frequency
                WHEN 'monthly' THEN 1
                WHEN 'bimonthly' THEN 2
                WHEN 'quarterly' THEN 3
                WHEN 'four_monthly' THEN 4
                WHEN 'semiannual' THEN 6
                WHEN 'annual' THEN 12
            END)
        )::date
        WHERE last_tariff_update_at IS NOT NULL
          AND tariff_update_frequency IS NOT NULL
    """)

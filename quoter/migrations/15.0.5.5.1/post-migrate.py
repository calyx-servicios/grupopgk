# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)


def migrate(cr, version):
    # La regla pudo quedar vieja por noupdate=1 y seguir usando area_id.*
    # Forzamos un dominio neutro para evitar fallos al evaluar campos inexistentes.
    cr.execute(
        """
        UPDATE ir_rule r
           SET domain_force = '[(1, ''='', 1)]'
          FROM ir_model_data imd
         WHERE imd.module = 'quoter'
           AND imd.name = 'quoter_rule_area_complexity_range_visibility'
           AND imd.model = 'ir.rule'
           AND imd.res_id = r.id
        """
    )

# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""quoter_config_edit_mode reemplaza el uso de cerrado como candado de edición.

Áreas con cerrado = False quedan en modo edición; con cerrado = True, bloqueadas.
"""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE quoter_professional_area
        SET quoter_config_edit_mode = (NOT COALESCE(cerrado, FALSE))
        """
    )

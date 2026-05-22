# pylint: disable=invalid-name
"""Visual separadores: opción «punto de color» retirada del selection."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE quoter_professional_area
           SET separator_visual_mode = 'none'
         WHERE separator_visual_mode = 'dot'
        """
    )

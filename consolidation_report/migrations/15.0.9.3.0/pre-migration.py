# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import logging

_logger = logging.getLogger(__name__)

MODEL = "consolidation.analytic.line.error"
TABLE = "consolidation_analytic_line_error"


def migrate(cr, version):
    """Elimina la metadata residual del modelo consolidation.analytic.line.error.
    """
    if not version:
        return

    # xmlids de selections, campos, ACL y del propio modelo
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE model = 'ir.model.fields.selection'
           AND res_id IN (
               SELECT s.id FROM ir_model_fields_selection s
               JOIN ir_model_fields f ON s.field_id = f.id
                WHERE f.model = %(model)s OR f.relation = %(model)s)
        """,
        {"model": MODEL},
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE model = 'ir.model.fields'
           AND res_id IN (SELECT id FROM ir_model_fields
                           WHERE model = %(model)s OR relation = %(model)s)
        """,
        {"model": MODEL},
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE model = 'ir.model.access'
           AND res_id IN (SELECT id FROM ir_model_access
                           WHERE model_id IN (SELECT id FROM ir_model WHERE model = %(model)s))
        """,
        {"model": MODEL},
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE model = 'ir.model'
           AND res_id IN (SELECT id FROM ir_model WHERE model = %(model)s)
        """,
        {"model": MODEL},
    )

    # ACL
    cr.execute(
        """
        DELETE FROM ir_model_access
         WHERE model_id IN (SELECT id FROM ir_model WHERE model = %(model)s)
        """,
        {"model": MODEL},
    )

    # selections y campos, incluido list_errors en account.consolidation.report
    cr.execute(
        """
        DELETE FROM ir_model_fields_selection
         WHERE field_id IN (SELECT id FROM ir_model_fields
                             WHERE model = %(model)s OR relation = %(model)s)
        """,
        {"model": MODEL},
    )
    cr.execute(
        """
        DELETE FROM ir_model_fields
         WHERE model = %(model)s OR relation = %(model)s
        """,
        {"model": MODEL},
    )

    # constraints y relations
    cr.execute(
        """
        DELETE FROM ir_model_constraint
         WHERE model IN (SELECT id FROM ir_model WHERE model = %(model)s)
        """,
        {"model": MODEL},
    )
    cr.execute(
        """
        DELETE FROM ir_model_relation
         WHERE model IN (SELECT id FROM ir_model WHERE model = %(model)s)
        """,
        {"model": MODEL},
    )

    # el modelo y su tabla
    cr.execute("DELETE FROM ir_model WHERE model = %s", (MODEL,))
    cr.execute("DROP TABLE IF EXISTS %s" % TABLE)

    _logger.info("Metadata y tabla de %s eliminadas.", MODEL)

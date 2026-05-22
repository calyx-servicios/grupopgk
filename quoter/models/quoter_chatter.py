# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields
from odoo.tools.float_utils import float_compare


def quoter_chatter_should_log(env):
    return not env.context.get("quoter_skip_chatter_log")


def quoter_chatter_format_value(record, field_name, value):
    """Texto legible para un valor de campo (antes o después del cambio)."""
    if value in (False, None, ""):
        return "-"
    field = record._fields.get(field_name)
    if not field:
        return str(value)
    if field.type == "many2one":
        rec = value
        if isinstance(value, int):
            rec = record.env[field.comodel_name].browse(value)
        return rec.display_name if rec else "-"
    if field.type == "many2many":
        if isinstance(value, list):
            ids = []
            for cmd in value:
                if isinstance(cmd, (list, tuple)) and len(cmd) >= 3 and cmd[0] == 6:
                    ids = list(cmd[2] or [])
                    break
            recs = record.env[field.comodel_name].browse(ids) if ids else record.env[field.comodel_name]
        else:
            recs = value
        return ", ".join(recs.mapped("display_name")) or "-"
    if field.type == "selection":
        return dict(field.selection).get(value, value)
    if field.type in ("float", "monetary"):
        return "%.4g" % float(value)
    if field.type == "boolean":
        return _("Sí") if value else _("No")
    if field.type in ("date", "datetime"):
        return fields.Datetime.to_string(value) if field.type == "datetime" else str(value)
    return str(value)


def quoter_chatter_collect_changes(record, vals, field_labels, float_fields=None):
    """Devuelve líneas «etiqueta: viejo → nuevo» para campos presentes en vals."""
    float_fields = float_fields or frozenset()
    parts = []
    for fname, label in field_labels.items():
        if fname not in vals:
            continue
        new_raw = vals[fname]
        old = record[fname]
        field = record._fields.get(fname)
        if field and field.type == "many2many":
            old_disp = quoter_chatter_format_value(record, fname, old)
            new_disp = quoter_chatter_format_value(record, fname, new_raw)
            if old_disp == new_disp:
                continue
            parts.append("%s: %s → %s" % (label, old_disp, new_disp))
            continue
        if field and field.type == "many2one":
            old_disp = old.display_name if old else "-"
            new_disp = quoter_chatter_format_value(record, fname, new_raw)
            if old_disp == new_disp:
                continue
            parts.append("%s: %s → %s" % (label, old_disp, new_disp))
        elif fname in float_fields:
            if float_compare(float(old or 0.0), float(new_raw or 0.0), precision_digits=4) == 0:
                continue
            parts.append("%s: %s → %s" % (label, old, new_raw))
        else:
            if old == new_raw:
                continue
            old_disp = quoter_chatter_format_value(record, fname, old)
            new_disp = quoter_chatter_format_value(record, fname, new_raw)
            parts.append("%s: %s → %s" % (label, old_disp, new_disp))
    return parts

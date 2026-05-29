# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


def _apply_matrix_b_policy_for_areas(records):
    areas = records.mapped("area_id").exists()
    if areas:
        areas._apply_matrix_b_advanced_rules_to_level_ranges()
        shared = areas.filtered("matrix_shared_b_calculation")
        shared._apply_matrix_b_policy_to_shared_matrix_b()
        shared._recompute_shared_b_calc_outputs()


class QuoterAreaMatrixBRoleRule(models.Model):
    _name = "quoter.area.matrix.b.role.rule"
    _description = "Tabla B - regla base por rol"
    _order = "area_range_sequence, id"

    area_id = fields.Many2one(
        comodel_name="quoter.professional.area",
        string="Area",
        required=True,
        ondelete="cascade",
        index=True,
    )
    area_range_id = fields.Many2one(
        comodel_name="quoter.area.complexity.range",
        string="Rol",
        required=True,
        ondelete="restrict",
        index=True,
    )
    area_range_sequence = fields.Integer(
        related="area_range_id.sequence",
        store=True,
        readonly=True,
    )
    default_factor = fields.Float(string="Valor por defecto", default=0.0)
    is_fixed = fields.Boolean(string="Fijo", default=False)
    is_hidden = fields.Boolean(string="Oculto", default=False)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        area_id = self.env.context.get("default_area_id")
        if area_id and not res.get("area_id"):
            res["area_id"] = area_id
        return res

    _sql_constraints = [
        (
            "uniq_area_b_role_rule",
            "UNIQUE(area_id, area_range_id)",
            "Ya existe una regla base de tabla B para este rol en el ?rea.",
        )
    ]

    @api.constrains("area_id", "area_range_id")
    def _check_role_in_area(self):
        for rec in self:
            if rec.area_id and rec.area_range_id and rec.area_range_id not in rec.area_id.area_range_ids:
                raise ValidationError(
                    _("El rol de la regla debe pertenecer a los roles configurados en el ?rea.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        _apply_matrix_b_policy_for_areas(recs)
        return recs

    def write(self, vals):
        res = super().write(vals)
        _apply_matrix_b_policy_for_areas(self)
        return res

    def unlink(self):
        areas = self.mapped("area_id").exists()
        res = super().unlink()
        if areas:
            areas._apply_matrix_b_advanced_rules_to_level_ranges()
        return res


class QuoterAreaMatrixBBranchException(models.Model):
    _name = "quoter.area.matrix.b.branch.exception"
    _description = "Tabla B - excepci?n por rama"
    _order = "branch_sequence, area_range_sequence, id"

    area_id = fields.Many2one(
        comodel_name="quoter.professional.area",
        string="Area",
        required=True,
        ondelete="cascade",
        index=True,
    )
    branch_id = fields.Many2one(
        comodel_name="quoter.area.branch",
        string="Rama",
        required=True,
        ondelete="restrict",
        index=True,
    )
    branch_sequence = fields.Integer(
        related="branch_id.sequence",
        store=True,
        readonly=True,
    )
    area_range_id = fields.Many2one(
        comodel_name="quoter.area.complexity.range",
        string="Rol",
        required=True,
        ondelete="restrict",
        index=True,
    )
    area_range_sequence = fields.Integer(
        related="area_range_id.sequence",
        store=True,
        readonly=True,
    )
    factor_override = fields.Float(string="Valor excepción", default=0.0)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        area_id = self.env.context.get("default_area_id")
        if area_id and not res.get("area_id"):
            res["area_id"] = area_id
        return res

    _sql_constraints = [
        (
            "uniq_area_b_branch_exception",
            "UNIQUE(area_id, branch_id, area_range_id)",
            "Ya existe una excepci?n de tabla B para esa combinaci?n de rama y rol.",
        )
    ]

    @api.constrains("area_id", "branch_id", "area_range_id")
    def _check_dimensions_in_area(self):
        for rec in self:
            if not rec.area_id:
                continue
            if rec.branch_id and rec.branch_id not in rec.area_id._effective_branch_ids():
                raise ValidationError(_("La rama debe pertenecer al ?rea."))
            if rec.area_range_id and rec.area_range_id not in rec.area_id.area_range_ids:
                raise ValidationError(_("El rol debe pertenecer al ?rea."))

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        _apply_matrix_b_policy_for_areas(recs)
        return recs

    def write(self, vals):
        res = super().write(vals)
        _apply_matrix_b_policy_for_areas(self)
        return res

    def unlink(self):
        areas = self.mapped("area_id").exists()
        res = super().unlink()
        if areas:
            areas._apply_matrix_b_advanced_rules_to_level_ranges()
        return res


class QuoterAreaMatrixBLevelException(models.Model):
    _name = "quoter.area.matrix.b.level.exception"
    _description = "Tabla B - excepci?n por nivel"
    _order = "level_sequence, area_range_sequence, id"

    area_id = fields.Many2one(
        comodel_name="quoter.professional.area",
        string="Area",
        required=True,
        ondelete="cascade",
        index=True,
    )
    area_complexity_level_ids = fields.Many2many(
        comodel_name="quoter.complexity.level",
        related="area_id.complexity_level_ids",
        string="Niveles del área",
        readonly=True,
    )
    area_range_option_ids = fields.Many2many(
        comodel_name="quoter.area.complexity.range",
        related="area_id.area_range_ids",
        string="Roles del área",
        readonly=True,
    )
    complexity_level_id = fields.Many2one(
        comodel_name="quoter.complexity.level",
        string="Nivel",
        required=True,
        ondelete="restrict",
        index=True,
    )
    level_sequence = fields.Integer(
        related="complexity_level_id.sequence",
        store=True,
        readonly=True,
    )
    area_range_id = fields.Many2one(
        comodel_name="quoter.area.complexity.range",
        string="Rol",
        required=True,
        ondelete="restrict",
        index=True,
    )
    area_range_sequence = fields.Integer(
        related="area_range_id.sequence",
        store=True,
        readonly=True,
    )
    factor_override = fields.Float(string="Valor excepción", default=0.0)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        area_id = self.env.context.get("default_area_id")
        if area_id and not res.get("area_id"):
            res["area_id"] = area_id
        return res

    _sql_constraints = [
        (
            "uniq_area_b_level_exception",
            "UNIQUE(area_id, complexity_level_id, area_range_id)",
            "Ya existe una excepci?n de tabla B para esa combinaci?n de nivel y rol.",
        )
    ]

    @api.constrains("area_id", "complexity_level_id", "area_range_id")
    def _check_dimensions_in_area(self):
        for rec in self:
            if not rec.area_id:
                continue
            if rec.complexity_level_id and rec.complexity_level_id not in rec.area_id.complexity_level_ids:
                raise ValidationError(_("El nivel debe pertenecer al ?rea."))
            if rec.area_range_id and rec.area_range_id not in rec.area_id.area_range_ids:
                raise ValidationError(_("El rol debe pertenecer al ?rea."))

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        _apply_matrix_b_policy_for_areas(recs)
        return recs

    def write(self, vals):
        res = super().write(vals)
        _apply_matrix_b_policy_for_areas(self)
        return res

    def unlink(self):
        areas = self.mapped("area_id").exists()
        res = super().unlink()
        if areas:
            areas._apply_matrix_b_advanced_rules_to_level_ranges()
        return res


class QuoterAreaMatrixBLegacyException(models.Model):
    """Alias legado para evitar fallos por metadatos hist?ricos."""

    _name = "quoter.area.matrix.b.exception"
    _description = "Legacy alias de excepci?n Tabla B por rama"
    _auto = False


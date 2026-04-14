# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero
from odoo.tools import html_escape


class SaleOrder(models.Model):
    _inherit = "sale.order"
    
    is_quotation = fields.Boolean(
        string="Es Cotización",
        default=False,
        help="Indica si esta orden es una cotización profesional",
    )
    quoter_menu_context = fields.Boolean(
        compute="_compute_quoter_menu_context",
        string="Contexto menú Cotizador",
        help="True cuando la vista se abre con el contexto del menú Cotizador.",
    )
    
    quotation_sequence = fields.Char(
        string="Número de Cotización",
        readonly=True,
        copy=False,
        help="Número secuencial de cotización",
    )
    quoter_form_title = fields.Char(
        string="Referencia visible",
        compute="_compute_quoter_form_title",
        help="En cotizaciones profesionales muestra el número de cotización en el título del formulario.",
    )

    # Cabecera preventa PGK
    quoter_manager_id = fields.Many2one(
        comodel_name="res.users",
        string="Gerente responsable",
        copy=False,
        help="Usuario responsable (filtrado por grupo Gerente).",
    )
    quoter_partner_id = fields.Many2one(
        comodel_name="res.users",
        string="Socio asignado",
        copy=False,
        help="Usuario socio (filtrado por grupo Socio).",
    )

    quoter_user_can_edit_manager = fields.Boolean(
        compute="_compute_quoter_user_can_edit_fields",
    )
    quoter_user_can_edit_partner = fields.Boolean(
        compute="_compute_quoter_user_can_edit_fields",
    )
    quoter_user_is_assigned_manager = fields.Boolean(
        compute="_compute_quoter_user_can_edit_fields",
        string="Usuario es gerente asignado",
    )
    quoter_user_is_assigned_partner = fields.Boolean(
        compute="_compute_quoter_user_can_edit_fields",
        string="Usuario es socio asignado",
    )
    quoter_manager_candidate_user_ids = fields.Many2many(
        comodel_name="res.users",
        compute="_compute_quoter_candidate_users",
        string="Usuarios candidatos gerente",
    )
    quoter_partner_candidate_user_ids = fields.Many2many(
        comodel_name="res.users",
        compute="_compute_quoter_candidate_users",
        string="Usuarios candidatos socio",
    )

    # Preguntas estratégicas (max 140)
    quoter_q_competitors = fields.Char(
        string="¿Conoce si hay otros estudios presentándose a cotizar estos servicios?",
        size=140,
        copy=False,
    )
    quoter_q_budget = fields.Char(
        string="¿Conoce si el cliente cuenta con un presupuesto estimado o tiene información adicional del cliente?",
        size=140,
        copy=False,
    )
    quoter_q_current_payment = fields.Char(
        string="¿Conoce cuánto está pagando el cliente al proveedor actual?",
        size=140,
        copy=False,
    )
    quoter_q_notes = fields.Char(
        string="Otras observaciones que considere importante mencionar",
        size=140,
        copy=False,
    )

    quoter_area_ids = fields.Many2many(
        comodel_name="quoter.professional.area",
        relation="sale_order_quoter_area_rel",
        column1="order_id",
        column2="area_id",
        string="Áreas",
        domain="[('active', '=', True), ('cerrado', '=', True)]",
        help="Áreas de la cotización (máx. 5). Cada una tiene su pestaña en el cotizador.",
    )
    quoter_footer_area_discount_amount = fields.Monetary(
        string="Descuento/Recargo (áreas)",
        currency_field="currency_id",
        compute="_compute_quoter_footer_area_discount_amount",
        help="Total de la línea de pedido que agrupa descuentos/recargos globales por área (sin impuestos).",
    )

    @api.depends()
    def _compute_quoter_user_can_edit_fields(self):
        can_mgr = self.env.user.has_group("quoter.group_quoter_manager") or self.env.user.has_group("base.group_system")
        can_partner = self.env.user.has_group("quoter.group_quoter_partner") or self.env.user.has_group("base.group_system")
        current_user = self.env.user
        for order in self:
            order.quoter_user_can_edit_manager = bool(can_mgr)
            order.quoter_user_can_edit_partner = bool(can_partner)
            order.quoter_user_is_assigned_manager = bool(
                can_mgr and order.quoter_manager_id and order.quoter_manager_id == current_user
            )
            order.quoter_user_is_assigned_partner = bool(
                can_partner
                and order.quoter_partner_id
                and order.quoter_partner_id == current_user
            )

    def _check_quoter_partner_adjustment_write_access(self):
        """Descuento/recargo % por área: solo gerente asignado o administrador."""
        self.ensure_one()
        if self.env.user.has_group("base.group_system"):
            return
        if not self.env.user.has_group("quoter.group_quoter_manager"):
            raise UserError(
                _("Solo usuarios del grupo Quoter - Gerente pueden editar el porcentaje de descuento o recargo por área.")
            )
        if not self.quoter_manager_id:
            raise UserError(
                _("Defina un Gerente responsable en la cotización para poder cargar porcentaje de descuento o recargo por área.")
            )
        if self.quoter_manager_id != self.env.user:
            raise UserError(
                _("Solo el gerente asignado en la cotización puede editar el porcentaje de descuento o recargo por área.")
            )

    @api.depends()
    def _compute_quoter_candidate_users(self):
        User = self.env["res.users"]
        manager_group = self.env.ref("quoter.group_quoter_manager", raise_if_not_found=False)
        partner_group = self.env.ref("quoter.group_quoter_partner", raise_if_not_found=False)
        manager_users = User.browse()
        partner_users = User.browse()
        if manager_group:
            manager_users = manager_group.users.filtered(
                lambda u: u.active and not u.share
            )
        if partner_group:
            partner_users = partner_group.users.filtered(
                lambda u: u.active and not u.share
            )
        for order in self:
            order.quoter_manager_candidate_user_ids = manager_users
            order.quoter_partner_candidate_user_ids = partner_users

    def _check_quoter_responsibles_write_access(self, vals):
        """Refuerza en servidor la edición por grupo de campos cabecera Quoter."""
        if not vals:
            return
        can_mgr = self.env.user.has_group("quoter.group_quoter_manager") or self.env.user.has_group("base.group_system")
        can_partner = self.env.user.has_group("quoter.group_quoter_partner") or self.env.user.has_group("base.group_system")
        manager_group = self.env.ref("quoter.group_quoter_manager", raise_if_not_found=False)
        partner_group = self.env.ref("quoter.group_quoter_partner", raise_if_not_found=False)
        if "quoter_manager_id" in vals and not can_mgr:
            raise UserError(
                _("Solo usuarios del grupo Quoter - Gerente pueden editar Gerente responsable.")
            )
        if "quoter_partner_id" in vals and not can_partner:
            raise UserError(
                _("Solo usuarios del grupo Quoter - Socio pueden editar Socio asignado.")
            )
        if "quoter_manager_id" in vals and vals.get("quoter_manager_id"):
            manager_user = self.env["res.users"].browse(vals["quoter_manager_id"])
            if manager_group and manager_group not in manager_user.groups_id:
                raise UserError(
                    _("El usuario seleccionado en Gerente responsable debe pertenecer a Quoter - Gerente.")
                )
        if "quoter_partner_id" in vals and vals.get("quoter_partner_id"):
            partner_user = self.env["res.users"].browse(vals["quoter_partner_id"])
            if partner_group and partner_group not in partner_user.groups_id:
                raise UserError(
                    _("El usuario seleccionado en Socio asignado debe pertenecer a Quoter - Socio.")
                )

    @api.constrains(
        "quoter_q_competitors",
        "quoter_q_budget",
        "quoter_q_current_payment",
        "quoter_q_notes",
    )
    def _check_quoter_questions_length(self):
        for order in self:
            for fname in (
                "quoter_q_competitors",
                "quoter_q_budget",
                "quoter_q_current_payment",
                "quoter_q_notes",
            ):
                val = getattr(order, fname) or ""
                if len(val) > 140:
                    raise UserError(_("El campo no puede superar 140 caracteres."))

    @api.constrains(
        "order_line",
        "order_line.quoter_is_adjustment_line",
        "order_line.quoter_adjustment_note",
        "order_line.display_type",
    )
    def _check_quoter_adjustment_notes_required(self):
        for order in self.filtered("is_quotation"):
            missing = order.order_line.filtered(
                lambda l: not l.display_type
                and l.quoter_is_adjustment_line
                and not (l.quoter_adjustment_note or "").strip()
            )
            if missing:
                raise UserError(
                    _(
                        "Todas las líneas de ajuste deben tener observación. "
                        "Complete la observación en cada línea de ajuste antes de guardar."
                    )
                )

    quoter_area_block_ids = fields.One2many(
        comodel_name="quoter.sale.order.area",
        inverse_name="order_id",
        string="Bloques cotizador por área",
        copy=True,
    )

    # Slots 1..5: área i-ésima de quoter_area_ids (orden por id), para dominios por pestaña.
    quoter_slot_1_area_id = fields.Many2one(
        comodel_name="quoter.professional.area",
        compute="_compute_quoter_slot_areas",
        string="Área pestaña 1",
    )
    quoter_slot_2_area_id = fields.Many2one(
        comodel_name="quoter.professional.area",
        compute="_compute_quoter_slot_areas",
        string="Área pestaña 2",
    )
    quoter_slot_3_area_id = fields.Many2one(
        comodel_name="quoter.professional.area",
        compute="_compute_quoter_slot_areas",
        string="Área pestaña 3",
    )
    quoter_slot_4_area_id = fields.Many2one(
        comodel_name="quoter.professional.area",
        compute="_compute_quoter_slot_areas",
        string="Área pestaña 4",
    )
    quoter_slot_5_area_id = fields.Many2one(
        comodel_name="quoter.professional.area",
        compute="_compute_quoter_slot_areas",
        string="Área pestaña 5",
    )

    # Sin store: no exige columnas nuevas en sale_order; el rendimiento se mantiene con M2M seleccionables no almacenados.
    quoter_block_slot_1_id = fields.Many2one(
        comodel_name="quoter.sale.order.area",
        compute="_compute_quoter_block_slots",
        string="Bloque slot 1",
    )
    quoter_block_slot_2_id = fields.Many2one(
        comodel_name="quoter.sale.order.area",
        compute="_compute_quoter_block_slots",
        string="Bloque slot 2",
    )
    quoter_block_slot_3_id = fields.Many2one(
        comodel_name="quoter.sale.order.area",
        compute="_compute_quoter_block_slots",
        string="Bloque slot 3",
    )
    quoter_block_slot_4_id = fields.Many2one(
        comodel_name="quoter.sale.order.area",
        compute="_compute_quoter_block_slots",
        string="Bloque slot 4",
    )
    quoter_block_slot_5_id = fields.Many2one(
        comodel_name="quoter.sale.order.area",
        compute="_compute_quoter_block_slots",
        string="Bloque slot 5",
    )

    # La secuencia se define en la configuración del área (quoter.professional.area.sequence).

    quoter_slot_1_area_level_ids = fields.Many2many(
        comodel_name="quoter.complexity.level",
        related="quoter_slot_1_area_id.complexity_level_ids",
        string="Niveles área 1",
    )
    quoter_slot_2_area_level_ids = fields.Many2many(
        comodel_name="quoter.complexity.level",
        related="quoter_slot_2_area_id.complexity_level_ids",
        string="Niveles área 2",
    )
    quoter_slot_3_area_level_ids = fields.Many2many(
        comodel_name="quoter.complexity.level",
        related="quoter_slot_3_area_id.complexity_level_ids",
        string="Niveles área 3",
    )
    quoter_slot_4_area_level_ids = fields.Many2many(
        comodel_name="quoter.complexity.level",
        related="quoter_slot_4_area_id.complexity_level_ids",
        string="Niveles área 4",
    )
    quoter_slot_5_area_level_ids = fields.Many2many(
        comodel_name="quoter.complexity.level",
        related="quoter_slot_5_area_id.complexity_level_ids",
        string="Niveles área 5",
    )

    quoter_slot_1_block_state = fields.Selection(
        related="quoter_block_slot_1_id.state",
        readonly=False,
        string="Estado bloque 1",
    )
    quoter_slot_2_block_state = fields.Selection(
        related="quoter_block_slot_2_id.state",
        readonly=False,
        string="Estado bloque 2",
    )
    quoter_slot_3_block_state = fields.Selection(
        related="quoter_block_slot_3_id.state",
        readonly=False,
        string="Estado bloque 3",
    )
    quoter_slot_4_block_state = fields.Selection(
        related="quoter_block_slot_4_id.state",
        readonly=False,
        string="Estado bloque 4",
    )
    quoter_slot_5_block_state = fields.Selection(
        related="quoter_block_slot_5_id.state",
        readonly=False,
        string="Estado bloque 5",
    )

    quoter_slot_1_block_level_id = fields.Many2one(
        comodel_name="quoter.complexity.level",
        related="quoter_block_slot_1_id.complexity_level_id",
        readonly=False,
        domain="[('area_ids', '=', quoter_slot_1_area_id)]",
        string="Nivel bloque 1",
    )
    quoter_slot_2_block_level_id = fields.Many2one(
        comodel_name="quoter.complexity.level",
        related="quoter_block_slot_2_id.complexity_level_id",
        readonly=False,
        domain="[('area_ids', '=', quoter_slot_2_area_id)]",
        string="Nivel bloque 2",
    )
    quoter_slot_3_block_level_id = fields.Many2one(
        comodel_name="quoter.complexity.level",
        related="quoter_block_slot_3_id.complexity_level_id",
        readonly=False,
        domain="[('area_ids', '=', quoter_slot_3_area_id)]",
        string="Nivel bloque 3",
    )
    quoter_slot_4_block_level_id = fields.Many2one(
        comodel_name="quoter.complexity.level",
        related="quoter_block_slot_4_id.complexity_level_id",
        readonly=False,
        domain="[('area_ids', '=', quoter_slot_4_area_id)]",
        string="Nivel bloque 4",
    )
    quoter_slot_5_block_level_id = fields.Many2one(
        comodel_name="quoter.complexity.level",
        related="quoter_block_slot_5_id.complexity_level_id",
        readonly=False,
        domain="[('area_ids', '=', quoter_slot_5_area_id)]",
        string="Nivel bloque 5",
    )

    quoter_slot_1_editable = fields.Boolean(
        compute="_compute_quoter_slot_editable",
        string="Slot 1 editable",
    )
    quoter_slot_2_editable = fields.Boolean(
        compute="_compute_quoter_slot_editable",
        string="Slot 2 editable",
    )
    quoter_slot_3_editable = fields.Boolean(
        compute="_compute_quoter_slot_editable",
        string="Slot 3 editable",
    )
    quoter_slot_4_editable = fields.Boolean(
        compute="_compute_quoter_slot_editable",
        string="Slot 4 editable",
    )
    quoter_slot_5_editable = fields.Boolean(
        compute="_compute_quoter_slot_editable",
        string="Slot 5 editable",
    )

    quoter_slot_1_structure_locked = fields.Boolean(
        compute="_compute_quoter_slot_lock_flags",
        string="Slot 1 estructura bloqueada",
    )
    quoter_slot_2_structure_locked = fields.Boolean(
        compute="_compute_quoter_slot_lock_flags",
        string="Slot 2 estructura bloqueada",
    )
    quoter_slot_3_structure_locked = fields.Boolean(
        compute="_compute_quoter_slot_lock_flags",
        string="Slot 3 estructura bloqueada",
    )
    quoter_slot_4_structure_locked = fields.Boolean(
        compute="_compute_quoter_slot_lock_flags",
        string="Slot 4 estructura bloqueada",
    )
    quoter_slot_5_structure_locked = fields.Boolean(
        compute="_compute_quoter_slot_lock_flags",
        string="Slot 5 estructura bloqueada",
    )
    quoter_slot_1_lines_frozen = fields.Boolean(
        compute="_compute_quoter_slot_lock_flags",
        string="Slot 1 líneas congeladas",
    )
    quoter_slot_2_lines_frozen = fields.Boolean(
        compute="_compute_quoter_slot_lock_flags",
        string="Slot 2 líneas congeladas",
    )
    quoter_slot_3_lines_frozen = fields.Boolean(
        compute="_compute_quoter_slot_lock_flags",
        string="Slot 3 líneas congeladas",
    )
    quoter_slot_4_lines_frozen = fields.Boolean(
        compute="_compute_quoter_slot_lock_flags",
        string="Slot 4 líneas congeladas",
    )
    quoter_slot_5_lines_frozen = fields.Boolean(
        compute="_compute_quoter_slot_lock_flags",
        string="Slot 5 líneas congeladas",
    )

    quoter_slot_1_line_ids = fields.One2many(
        comodel_name="sale.order.line",
        inverse_name="order_id",
        string="Líneas cotizador 1",
        domain="['&', ('quoter_tab_area_id', '=', quoter_slot_1_area_id), '|', ('display_type', '=', False), ('display_type', '=', 'line_section')]",
        copy=False,
    )
    quoter_slot_2_line_ids = fields.One2many(
        comodel_name="sale.order.line",
        inverse_name="order_id",
        string="Líneas cotizador 2",
        domain="['&', ('quoter_tab_area_id', '=', quoter_slot_2_area_id), '|', ('display_type', '=', False), ('display_type', '=', 'line_section')]",
        copy=False,
    )
    quoter_slot_3_line_ids = fields.One2many(
        comodel_name="sale.order.line",
        inverse_name="order_id",
        string="Líneas cotizador 3",
        domain="['&', ('quoter_tab_area_id', '=', quoter_slot_3_area_id), '|', ('display_type', '=', False), ('display_type', '=', 'line_section')]",
        copy=False,
    )
    quoter_slot_4_line_ids = fields.One2many(
        comodel_name="sale.order.line",
        inverse_name="order_id",
        string="Líneas cotizador 4",
        domain="['&', ('quoter_tab_area_id', '=', quoter_slot_4_area_id), '|', ('display_type', '=', False), ('display_type', '=', 'line_section')]",
        copy=False,
    )
    quoter_slot_5_line_ids = fields.One2many(
        comodel_name="sale.order.line",
        inverse_name="order_id",
        string="Líneas cotizador 5",
        domain="['&', ('quoter_tab_area_id', '=', quoter_slot_5_area_id), '|', ('display_type', '=', False), ('display_type', '=', 'line_section')]",
        copy=False,
    )

    quoter_slot_1_selectable_product_ids = fields.Many2many(
        comodel_name="product.product",
        string="Productos cotizador slot 1",
        compute="_compute_quoter_slot_selectable_products",
    )
    quoter_slot_2_selectable_product_ids = fields.Many2many(
        comodel_name="product.product",
        string="Productos cotizador slot 2",
        compute="_compute_quoter_slot_selectable_products",
    )
    quoter_slot_3_selectable_product_ids = fields.Many2many(
        comodel_name="product.product",
        string="Productos cotizador slot 3",
        compute="_compute_quoter_slot_selectable_products",
    )
    quoter_slot_4_selectable_product_ids = fields.Many2many(
        comodel_name="product.product",
        string="Productos cotizador slot 4",
        compute="_compute_quoter_slot_selectable_products",
    )
    quoter_slot_5_selectable_product_ids = fields.Many2many(
        comodel_name="product.product",
        string="Productos cotizador slot 5",
        compute="_compute_quoter_slot_selectable_products",
    )

    # --- Totales por pestaña de área (sin impuestos) + ajustes globales por bloque ---
    quoter_slot_1_global_discount = fields.Float(
        string="Descuento % (área 1)",
        digits=(16, 4),
        compute="_compute_quoter_slot_global_adjustments",
        inverse="_inverse_quoter_slot_1_global_discount",
    )
    quoter_slot_1_global_surcharge = fields.Float(
        string="Recargo % (área 1)",
        digits=(16, 4),
        compute="_compute_quoter_slot_global_adjustments",
        inverse="_inverse_quoter_slot_1_global_surcharge",
    )
    quoter_slot_2_global_discount = fields.Float(
        string="Descuento % (área 2)",
        digits=(16, 4),
        compute="_compute_quoter_slot_global_adjustments",
        inverse="_inverse_quoter_slot_2_global_discount",
    )
    quoter_slot_2_global_surcharge = fields.Float(
        string="Recargo % (área 2)",
        digits=(16, 4),
        compute="_compute_quoter_slot_global_adjustments",
        inverse="_inverse_quoter_slot_2_global_surcharge",
    )
    quoter_slot_3_global_discount = fields.Float(
        string="Descuento % (área 3)",
        digits=(16, 4),
        compute="_compute_quoter_slot_global_adjustments",
        inverse="_inverse_quoter_slot_3_global_discount",
    )
    quoter_slot_3_global_surcharge = fields.Float(
        string="Recargo % (área 3)",
        digits=(16, 4),
        compute="_compute_quoter_slot_global_adjustments",
        inverse="_inverse_quoter_slot_3_global_surcharge",
    )
    quoter_slot_4_global_discount = fields.Float(
        string="Descuento % (área 4)",
        digits=(16, 4),
        compute="_compute_quoter_slot_global_adjustments",
        inverse="_inverse_quoter_slot_4_global_discount",
    )
    quoter_slot_4_global_surcharge = fields.Float(
        string="Recargo % (área 4)",
        digits=(16, 4),
        compute="_compute_quoter_slot_global_adjustments",
        inverse="_inverse_quoter_slot_4_global_surcharge",
    )
    quoter_slot_5_global_discount = fields.Float(
        string="Descuento % (área 5)",
        digits=(16, 4),
        compute="_compute_quoter_slot_global_adjustments",
        inverse="_inverse_quoter_slot_5_global_discount",
    )
    quoter_slot_5_global_surcharge = fields.Float(
        string="Recargo % (área 5)",
        digits=(16, 4),
        compute="_compute_quoter_slot_global_adjustments",
        inverse="_inverse_quoter_slot_5_global_surcharge",
    )
    quoter_slot_1_product_untaxed = fields.Monetary(
        string="Subtotal productos (área 1)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_1_adjustment_untaxed = fields.Monetary(
        string="Subtotal ajustes (área 1)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_1_total_untaxed = fields.Monetary(
        string="Total área 1 (sin imp.)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_2_product_untaxed = fields.Monetary(
        string="Subtotal productos (área 2)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_2_adjustment_untaxed = fields.Monetary(
        string="Subtotal ajustes (área 2)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_2_total_untaxed = fields.Monetary(
        string="Total área 2 (sin imp.)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_3_product_untaxed = fields.Monetary(
        string="Subtotal productos (área 3)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_3_adjustment_untaxed = fields.Monetary(
        string="Subtotal ajustes (área 3)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_3_total_untaxed = fields.Monetary(
        string="Total área 3 (sin imp.)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_4_product_untaxed = fields.Monetary(
        string="Subtotal productos (área 4)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_4_adjustment_untaxed = fields.Monetary(
        string="Subtotal ajustes (área 4)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_4_total_untaxed = fields.Monetary(
        string="Total área 4 (sin imp.)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_5_product_untaxed = fields.Monetary(
        string="Subtotal productos (área 5)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_5_adjustment_untaxed = fields.Monetary(
        string="Subtotal ajustes (área 5)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_5_total_untaxed = fields.Monetary(
        string="Total área 5 (sin imp.)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_1_discount_line = fields.Monetary(
        string="Importe descuento (área 1)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_2_discount_line = fields.Monetary(
        string="Importe descuento (área 2)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_3_discount_line = fields.Monetary(
        string="Importe descuento (área 3)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_4_discount_line = fields.Monetary(
        string="Importe descuento (área 4)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_5_discount_line = fields.Monetary(
        string="Importe descuento (área 5)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_1_surcharge_line = fields.Monetary(
        string="Importe recargo (área 1)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_2_surcharge_line = fields.Monetary(
        string="Importe recargo (área 2)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_3_surcharge_line = fields.Monetary(
        string="Importe recargo (área 3)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_4_surcharge_line = fields.Monetary(
        string="Importe recargo (área 4)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_5_surcharge_line = fields.Monetary(
        string="Importe recargo (área 5)",
        currency_field="currency_id",
        compute="_compute_quoter_slot_area_totals_untaxed",
    )
    quoter_slot_1_caption_products = fields.Char(
        string="Leyenda productos (área 1)",
        compute="_compute_quoter_slot_footer_captions",
    )
    quoter_slot_1_caption_adjustments = fields.Char(
        string="Leyenda ajustes (área 1)",
        compute="_compute_quoter_slot_footer_captions",
    )
    quoter_slot_2_caption_products = fields.Char(
        string="Leyenda productos (área 2)",
        compute="_compute_quoter_slot_footer_captions",
    )
    quoter_slot_2_caption_adjustments = fields.Char(
        string="Leyenda ajustes (área 2)",
        compute="_compute_quoter_slot_footer_captions",
    )
    quoter_slot_3_caption_products = fields.Char(
        string="Leyenda productos (área 3)",
        compute="_compute_quoter_slot_footer_captions",
    )
    quoter_slot_3_caption_adjustments = fields.Char(
        string="Leyenda ajustes (área 3)",
        compute="_compute_quoter_slot_footer_captions",
    )
    quoter_slot_4_caption_products = fields.Char(
        string="Leyenda productos (área 4)",
        compute="_compute_quoter_slot_footer_captions",
    )
    quoter_slot_4_caption_adjustments = fields.Char(
        string="Leyenda ajustes (área 4)",
        compute="_compute_quoter_slot_footer_captions",
    )
    quoter_slot_5_caption_products = fields.Char(
        string="Leyenda productos (área 5)",
        compute="_compute_quoter_slot_footer_captions",
    )
    quoter_slot_5_caption_adjustments = fields.Char(
        string="Leyenda ajustes (área 5)",
        compute="_compute_quoter_slot_footer_captions",
    )
    quoter_slot_1_area_summary_html = fields.Html(
        string="Resumen horas/tarifas (área 1)",
        compute="_compute_quoter_slot_area_summary_html",
        sanitize=False,
    )
    quoter_slot_2_area_summary_html = fields.Html(
        string="Resumen horas/tarifas (área 2)",
        compute="_compute_quoter_slot_area_summary_html",
        sanitize=False,
    )
    quoter_slot_3_area_summary_html = fields.Html(
        string="Resumen horas/tarifas (área 3)",
        compute="_compute_quoter_slot_area_summary_html",
        sanitize=False,
    )
    quoter_slot_4_area_summary_html = fields.Html(
        string="Resumen horas/tarifas (área 4)",
        compute="_compute_quoter_slot_area_summary_html",
        sanitize=False,
    )
    quoter_slot_5_area_summary_html = fields.Html(
        string="Resumen horas/tarifas (área 5)",
        compute="_compute_quoter_slot_area_summary_html",
        sanitize=False,
    )

    # Se eliminó la lógica de "variantes por nivel" del pedido:
    # el producto real es único; la relación nivel+rango se gestiona en un modelo separado.

    @api.depends(
        "quoter_slot_1_area_id",
        "quoter_slot_2_area_id",
        "quoter_slot_3_area_id",
        "quoter_slot_4_area_id",
        "quoter_slot_5_area_id",
        "quoter_slot_1_block_level_id",
        "quoter_slot_2_block_level_id",
        "quoter_slot_3_block_level_id",
        "quoter_slot_4_block_level_id",
        "quoter_slot_5_block_level_id",
        "quoter_area_block_ids.complexity_level_id",
    )
    def _compute_quoter_slot_selectable_products(self):
        """Solo variantes canónicas del área; sin nivel elegido no hay productos seleccionables."""
        QuoterLine = self.env["quoter.service.line"]
        empty = self.env["product.product"]
        for order in self:
            for n in range(1, 6):
                area = getattr(order, "quoter_slot_%d_area_id" % n)
                level = getattr(order, "quoter_slot_%d_block_level_id" % n)
                fname = "quoter_slot_%d_selectable_product_ids" % n
                if not area or not level:
                    order[fname] = empty
                    continue
                products = (
                    QuoterLine.search([("area_id", "=", area.id)])
                    .mapped("product_id")
                    .filtered(
                        lambda p: p
                        and p.sale_ok
                        and not getattr(p, "is_quoter_range_rate_product", False)
                    )
                )
                order[fname] = products

    def _quoter_refresh_selectable_products(self):
        """Recalcula listas de productos por slot (p. ej. tras cambiar líneas quoter.service.line)."""
        self._compute_quoter_slot_selectable_products()

    def _quoter_refresh_area_lines_hours_from_levels(self, area):
        """Replica horas de quoter.product.level.range según el nivel del bloque del área."""
        self.ensure_one()
        if not area:
            return
        lines = self.order_line.filtered(
            lambda l, a=area: l.quoter_tab_area_id == a
            and l.product_id
            and getattr(l.product_id, "is_quoter_product", False)
        )
        for line in lines:
            line._quoter_sync_range_hours()
            line._quoter_apply_level_template_hours()
            price, _warn = line._quoter_compute_unit_price_from_ranges()
            line.write({"price_unit": price})

    @api.onchange(
        "quoter_slot_1_block_level_id",
        "quoter_slot_2_block_level_id",
        "quoter_slot_3_block_level_id",
        "quoter_slot_4_block_level_id",
        "quoter_slot_5_block_level_id",
    )
    def _onchange_quoter_block_levels_apply_template_hours(self):
        """Al cambiar el nivel (o limpiarlo), horas y precio por rangos."""
        for order in self:
            if not order.is_quotation:
                continue
            for n in range(1, 6):
                area = getattr(order, "quoter_slot_%d_area_id" % n)
                if area:
                    order._quoter_refresh_area_lines_hours_from_levels(area)

    def _quoter_blocks_ordered_for_slots(self):
        """Orden estable por secuencia del área + área; tolera NewId."""
        self.ensure_one()

        def sort_key(block):
            area = block.area_id
            seq = (area.sequence or 0) if area else 0
            rid = area.id if area else False
            if isinstance(rid, int):
                return (seq, 0, rid)
            origin = getattr(rid, "origin", None)
            if origin is not None:
                return (seq, 0, int(origin))
            return (seq, 1, str(rid))

        return self.quoter_area_block_ids.sorted(key=sort_key)

    @api.depends("quoter_area_ids", "quoter_area_block_ids", "quoter_area_block_ids.sequence", "quoter_area_block_ids.area_id")
    def _compute_quoter_slot_areas(self):
        user_group_ids = set(self.env.user.groups_id.ids)
        can_view_all_tabs = (
            self.env.user.has_group("base.group_system")
            or self.env.user.has_group("quoter.group_quoter_manager")
            or self.env.user.has_group("quoter.group_quoter_partner")
        )
        for order in self:
            # Mapeo fijo: pestaña N = área con sequence == N
            blocks = order.quoter_area_block_ids.filtered(lambda b: b.area_id)
            by_seq = {}
            for b in blocks:
                # Gerente/Socio/Administrador ven todas las pestañas.
                # El resto solo ve áreas sin grupo o de sus grupos.
                if not can_view_all_tabs and b.area_id.group_id and b.area_id.group_id.id not in user_group_ids:
                    continue
                seq = b.area_id.sequence
                if isinstance(seq, int) and 1 <= seq <= 5 and seq not in by_seq:
                    by_seq[seq] = b.area_id
            for n in range(1, 6):
                setattr(order, f"quoter_slot_{n}_area_id", by_seq.get(n))

    @api.depends(
        "quoter_area_block_ids",
        "quoter_area_block_ids.area_id",
        "quoter_slot_1_area_id",
        "quoter_slot_2_area_id",
        "quoter_slot_3_area_id",
        "quoter_slot_4_area_id",
        "quoter_slot_5_area_id",
    )
    def _compute_quoter_block_slots(self):
        empty_block = self.env["quoter.sale.order.area"].browse()
        for order in self:
            for n in range(1, 6):
                area = getattr(order, "quoter_slot_%s_area_id" % n)
                if not area:
                    setattr(order, "quoter_block_slot_%s_id" % n, empty_block)
                    continue
                block = order.quoter_area_block_ids.filtered(
                    lambda b, a=area: b.area_id == a
                )[:1]
                setattr(order, "quoter_block_slot_%s_id" % n, block)

    @api.model
    def _quoter_block_adjustment_amounts(self, block):
        """Devuelve (descuento %, recargo %) no negativos; compatible con datos legacy."""
        if not block:
            return 0.0, 0.0
        raw_discount = float(block.global_discount_amount or 0.0)
        raw_surcharge = float(getattr(block, "global_surcharge_amount", 0.0) or 0.0)
        # Legacy: recargo como valor negativo en descuento.
        if raw_discount < 0.0:
            raw_surcharge += abs(raw_discount)
            raw_discount = 0.0
        return max(0.0, raw_discount), max(0.0, raw_surcharge)

    def _quoter_slot_subtotals_untaxed(self, area):
        """Subtotal productos y subtotal líneas de ajuste (sin impuestos) para un área."""
        self.ensure_one()
        if not area:
            return 0.0, 0.0
        olines = self.order_line.filtered(
            lambda l, a=area: not l.display_type and l.quoter_tab_area_id == a
        )
        prod = sum(olines.filtered(lambda l: not l.quoter_is_adjustment_line).mapped("price_subtotal"))
        adj = sum(olines.filtered(lambda l: l.quoter_is_adjustment_line).mapped("price_subtotal"))
        return float(prod or 0.0), float(adj or 0.0)

    @api.model
    def _quoter_format_number_es(self, value, decimals=2):
        """Número con separador de miles tipo es_AR (sin depender del usuario)."""
        fmt = "{:,.%sf}" % int(decimals)
        s = fmt.format(float(value or 0.0))
        return s.replace(",", "X").replace(".", ",").replace("X", ".")

    def _quoter_slot_hours_base_and_adjustment(self, area, limit=4):
        """Suma horas por rango: [base por rango], [ajuste por rango]."""
        self.ensure_one()
        base = [0.0] * limit
        adj = [0.0] * limit
        if not area:
            return base, adj
        ranges = area.area_range_ids.sorted(key=lambda r: (r.sequence, r.id))[:limit]
        range_ids = [r.id for r in ranges]
        if not range_ids:
            return base, adj
        lines = self.order_line.filtered(
            lambda l, a=area: not l.display_type and l.quoter_tab_area_id == a
        )
        for line in lines:
            by_range = {
                h.area_range_id.id: float(h.hours or 0.0)
                for h in line.quoter_range_hour_ids
                if h.area_range_id
            }
            target = adj if line.quoter_is_adjustment_line else base
            for idx, rid in enumerate(range_ids):
                if idx < limit:
                    target[idx] += by_range.get(rid, 0.0)
        return base, adj

    def _quoter_slot_range_rates(self, area, limit=4):
        """Tarifa/h por rango (lista misma longitud que rangos del área)."""
        self.ensure_one()
        rates = [0.0] * limit
        if not area:
            return rates, self.env["quoter.area.complexity.range"].browse()
        ranges = area.area_range_ids.sorted(key=lambda r: (r.sequence, r.id))[:limit]
        pl = area.pricelist_id or self.pricelist_id
        if not pl:
            return rates, ranges
        partner = self.partner_id or self.env["res.partner"]
        tmpl_model = self.env["product.template"]
        for idx, range_rec in enumerate(ranges):
            if idx >= limit:
                break
            tmpl = tmpl_model.search(
                [
                    ("is_quoter_range_rate_product", "=", True),
                    ("quoter_range_rate_area_id", "=", area.id),
                    ("quoter_range_rate_range_id", "=", range_rec.id),
                ],
                limit=1,
            )
            variant = tmpl.product_variant_id if tmpl else self.env["product.product"]
            if not variant:
                continue
            rates[idx] = float(
                pl.get_product_price(
                    variant,
                    1.0,
                    partner,
                    date=self.date_order,
                    uom_id=variant.uom_id.id,
                )
                or 0.0
            )
        return rates, ranges

    def _quoter_build_area_summary_html(self, area, block):
        """Resumen por rango (estilo filas/columnas tipo planilla, sin tabla HTML)."""
        self.ensure_one()
        if not area:
            return False
        limit = 4
        base_h, adj_h = self._quoter_slot_hours_base_and_adjustment(area, limit=limit)
        rates, ranges = self._quoter_slot_range_rates(area, limit=limit)
        disc_pct, sur_pct = self._quoter_block_adjustment_amounts(block)
        rate_factor = 1.0 - (disc_pct / 100.0) + (sur_pct / 100.0)
        tot_h = [base_h[i] + adj_h[i] for i in range(limit)]
        adj_rates = [max(0.0, rates[i] * rate_factor) for i in range(limit)]
        base_vals = [base_h[i] * rates[i] for i in range(limit)]
        final_vals = [tot_h[i] * adj_rates[i] for i in range(limit)]

        def esc(t):
            return html_escape(t or "")

        col_labels = []
        for i in range(limit):
            if i < len(ranges) and ranges[i]:
                col_labels.append(esc(ranges[i].name or str(i + 1)))
            else:
                col_labels.append("—")
        col_labels.append(esc(_("Total")))

        def cells_numeric(values, decimals=2, money=False, total_mode="sum"):
            out = []
            for i in range(limit):
                pref = "$" if money else ""
                out.append(pref + self._quoter_format_number_es(values[i], decimals=decimals))
            if total_mode == "sum":
                tot = sum(values)
                pref = "$" if money else ""
                out.append(pref + self._quoter_format_number_es(tot, decimals=decimals))
            else:
                out.append("—")
            return out

        def cells_pct_same(pct, decimals=2):
            s = self._quoter_format_number_es(pct, decimals=decimals) + "%"
            return [s] * (limit + 1)

        olines = self.order_line.filtered(
            lambda l, a=area: not l.display_type and l.quoter_tab_area_id == a
        )
        adj_lines = olines.filtered(lambda l: l.quoter_is_adjustment_line)
        if len(adj_lines) == 1:
            adj_title = _("Ajuste socio - %s") % (adj_lines[0].name or adj_lines[0].product_id.display_name or "")
        elif adj_lines:
            adj_title = _("Ajuste socio (suma de %s líneas)") % len(adj_lines)
        else:
            adj_title = _("Ajuste socio")

        rows_html = []
        # Misma base tipográfica que el bloque oe_subtotal_footer (sin "small", tamaño heredado del formulario).
        style_grid = (
            "display:grid;"
            "grid-template-columns:minmax(11rem,16rem) repeat(5, minmax(4.5rem, 1fr));"
            "column-gap:.5rem;row-gap:.4rem;align-items:center;"
            "font-size:inherit;line-height:1.45;"
        )
        style_hdr = "font-weight:600;font-size:inherit;opacity:0.7;"
        style_lbl = "font-weight:400;font-size:inherit;"
        style_lbl_total = "font-weight:700;font-size:inherit;"
        style_cell = (
            "text-align:right;font-variant-numeric:tabular-nums;"
            "font-size:inherit;font-weight:400;"
        )
        style_cell_total = (
            "text-align:right;font-variant-numeric:tabular-nums;"
            "font-size:inherit;font-weight:700;"
        )

        hdr = [f'<div style="{style_hdr}"></div>']
        for lab in col_labels:
            hdr.append(f'<div style="{style_hdr}{style_cell}">{lab}</div>')
        rows_html.append(f'<div style="{style_grid}">{"".join(hdr)}</div>')

        def add_row(label, cell_strings, strong=False):
            ls = style_lbl_total if strong else style_lbl
            cs = style_cell_total if strong else style_cell
            parts = [f'<div style="{ls}">{esc(label)}</div>']
            for c in cell_strings:
                parts.append(f'<div style="{cs}">{esc(c)}</div>')
            rows_html.append(f'<div style="{style_grid}">{"".join(parts)}</div>')

        add_row(_("Totales (horas)"), cells_numeric(base_h, decimals=2))
        add_row(_("Tarifa online"), cells_numeric(rates, decimals=2, money=True, total_mode="none"))
        add_row(_("Valor total"), cells_numeric(base_vals, decimals=2, money=True))
        rows_html.append(
            '<div class="text-muted mt-2 mb-1" '
            'style="font-weight:600;font-size:inherit;line-height:1.45;">'
            f"{esc(_('AJUSTE SOCIO a las horas'))}</div>"
        )
        add_row(adj_title, cells_numeric(adj_h, decimals=2))
        add_row(_("Totales horas"), cells_numeric(tot_h, decimals=2))
        add_row(_("Tarifa online"), cells_numeric(rates, decimals=2, money=True, total_mode="none"))
        add_row(_("Ajuste socio - descuento"), cells_pct_same(disc_pct))
        add_row(_("Ajuste socio - aumento"), cells_pct_same(sur_pct))
        add_row(_("Tarifa ajustada"), cells_numeric(adj_rates, decimals=2, money=True, total_mode="none"))
        add_row(_("Valor total"), cells_numeric(final_vals, decimals=2, money=True), strong=True)

        return (
            '<div class="o_quoter_area_summary" style="max-width:52rem;font-size:inherit;">'
            + "".join(rows_html)
            + "</div>"
        )

    @api.depends(
        "quoter_block_slot_1_id.global_discount_amount",
        "quoter_block_slot_2_id.global_discount_amount",
        "quoter_block_slot_3_id.global_discount_amount",
        "quoter_block_slot_4_id.global_discount_amount",
        "quoter_block_slot_5_id.global_discount_amount",
        "quoter_block_slot_1_id.global_surcharge_amount",
        "quoter_block_slot_2_id.global_surcharge_amount",
        "quoter_block_slot_3_id.global_surcharge_amount",
        "quoter_block_slot_4_id.global_surcharge_amount",
        "quoter_block_slot_5_id.global_surcharge_amount",
    )
    def _compute_quoter_slot_global_adjustments(self):
        for order in self:
            for n in range(1, 6):
                block = getattr(order, "quoter_block_slot_%d_id" % n)
                disc, surcharge = order._quoter_block_adjustment_amounts(block)
                order["quoter_slot_%d_global_discount" % n] = disc
                order["quoter_slot_%d_global_surcharge" % n] = surcharge

    def _inverse_quoter_slot_1_global_discount(self):
        for order in self:
            order._check_quoter_partner_adjustment_write_access()
            if order.quoter_block_slot_1_id:
                order.quoter_block_slot_1_id.global_discount_amount = max(
                    0.0, float(order.quoter_slot_1_global_discount or 0.0)
                )
            if order.is_quotation:
                order._quoter_sync_area_discount_total_line()

    def _inverse_quoter_slot_2_global_discount(self):
        for order in self:
            order._check_quoter_partner_adjustment_write_access()
            if order.quoter_block_slot_2_id:
                order.quoter_block_slot_2_id.global_discount_amount = max(
                    0.0, float(order.quoter_slot_2_global_discount or 0.0)
                )
            if order.is_quotation:
                order._quoter_sync_area_discount_total_line()

    def _inverse_quoter_slot_3_global_discount(self):
        for order in self:
            order._check_quoter_partner_adjustment_write_access()
            if order.quoter_block_slot_3_id:
                order.quoter_block_slot_3_id.global_discount_amount = max(
                    0.0, float(order.quoter_slot_3_global_discount or 0.0)
                )
            if order.is_quotation:
                order._quoter_sync_area_discount_total_line()

    def _inverse_quoter_slot_4_global_discount(self):
        for order in self:
            order._check_quoter_partner_adjustment_write_access()
            if order.quoter_block_slot_4_id:
                order.quoter_block_slot_4_id.global_discount_amount = max(
                    0.0, float(order.quoter_slot_4_global_discount or 0.0)
                )
            if order.is_quotation:
                order._quoter_sync_area_discount_total_line()

    def _inverse_quoter_slot_5_global_discount(self):
        for order in self:
            order._check_quoter_partner_adjustment_write_access()
            if order.quoter_block_slot_5_id:
                order.quoter_block_slot_5_id.global_discount_amount = max(
                    0.0, float(order.quoter_slot_5_global_discount or 0.0)
                )
            if order.is_quotation:
                order._quoter_sync_area_discount_total_line()

    def _inverse_quoter_slot_1_global_surcharge(self):
        for order in self:
            order._check_quoter_partner_adjustment_write_access()
            if order.quoter_block_slot_1_id:
                order.quoter_block_slot_1_id.global_surcharge_amount = max(
                    0.0, float(order.quoter_slot_1_global_surcharge or 0.0)
                )
            if order.is_quotation:
                order._quoter_sync_area_discount_total_line()

    def _inverse_quoter_slot_2_global_surcharge(self):
        for order in self:
            order._check_quoter_partner_adjustment_write_access()
            if order.quoter_block_slot_2_id:
                order.quoter_block_slot_2_id.global_surcharge_amount = max(
                    0.0, float(order.quoter_slot_2_global_surcharge or 0.0)
                )
            if order.is_quotation:
                order._quoter_sync_area_discount_total_line()

    def _inverse_quoter_slot_3_global_surcharge(self):
        for order in self:
            order._check_quoter_partner_adjustment_write_access()
            if order.quoter_block_slot_3_id:
                order.quoter_block_slot_3_id.global_surcharge_amount = max(
                    0.0, float(order.quoter_slot_3_global_surcharge or 0.0)
                )
            if order.is_quotation:
                order._quoter_sync_area_discount_total_line()

    def _inverse_quoter_slot_4_global_surcharge(self):
        for order in self:
            order._check_quoter_partner_adjustment_write_access()
            if order.quoter_block_slot_4_id:
                order.quoter_block_slot_4_id.global_surcharge_amount = max(
                    0.0, float(order.quoter_slot_4_global_surcharge or 0.0)
                )
            if order.is_quotation:
                order._quoter_sync_area_discount_total_line()

    def _inverse_quoter_slot_5_global_surcharge(self):
        for order in self:
            order._check_quoter_partner_adjustment_write_access()
            if order.quoter_block_slot_5_id:
                order.quoter_block_slot_5_id.global_surcharge_amount = max(
                    0.0, float(order.quoter_slot_5_global_surcharge or 0.0)
                )
            if order.is_quotation:
                order._quoter_sync_area_discount_total_line()

    @api.depends(
        "order_line",
        "order_line.price_subtotal",
        "order_line.quoter_tab_area_id",
        "order_line.quoter_is_adjustment_line",
        "order_line.display_type",
        "quoter_slot_1_area_id",
        "quoter_slot_2_area_id",
        "quoter_slot_3_area_id",
        "quoter_slot_4_area_id",
        "quoter_slot_5_area_id",
        "quoter_block_slot_1_id.global_discount_amount",
        "quoter_block_slot_2_id.global_discount_amount",
        "quoter_block_slot_3_id.global_discount_amount",
        "quoter_block_slot_4_id.global_discount_amount",
        "quoter_block_slot_5_id.global_discount_amount",
        "quoter_block_slot_1_id.global_surcharge_amount",
        "quoter_block_slot_2_id.global_surcharge_amount",
        "quoter_block_slot_3_id.global_surcharge_amount",
        "quoter_block_slot_4_id.global_surcharge_amount",
        "quoter_block_slot_5_id.global_surcharge_amount",
    )
    def _compute_quoter_slot_area_totals_untaxed(self):
        for order in self:
            for n in range(1, 6):
                area = getattr(order, "quoter_slot_%d_area_id" % n)
                block = getattr(order, "quoter_block_slot_%d_id" % n)
                pname = "quoter_slot_%d_product_untaxed" % n
                aname = "quoter_slot_%d_adjustment_untaxed" % n
                dname = "quoter_slot_%d_discount_line" % n
                rname = "quoter_slot_%d_surcharge_line" % n
                tname = "quoter_slot_%d_total_untaxed" % n
                if not area:
                    order[pname] = 0.0
                    order[aname] = 0.0
                    order[dname] = 0.0
                    order[rname] = 0.0
                    order[tname] = 0.0
                    continue
                olines = order.order_line.filtered(
                    lambda l, a=area: not l.display_type and l.quoter_tab_area_id == a
                )
                prod = sum(olines.filtered(lambda l: not l.quoter_is_adjustment_line).mapped("price_subtotal"))
                adj = sum(olines.filtered(lambda l: l.quoter_is_adjustment_line).mapped("price_subtotal"))
                sub = prod + adj
                disc_pct, surcharge_pct = order._quoter_block_adjustment_amounts(block)
                disc_amt = sub * (disc_pct / 100.0)
                surcharge_amt = sub * (surcharge_pct / 100.0)
                total = sub - disc_amt + surcharge_amt
                order[pname] = prod
                order[aname] = adj
                order[dname] = disc_amt
                order[rname] = surcharge_amt
                order[tname] = total

    @api.depends(
        "quoter_slot_1_area_id",
        "quoter_slot_2_area_id",
        "quoter_slot_3_area_id",
        "quoter_slot_4_area_id",
        "quoter_slot_5_area_id",
    )
    def _compute_quoter_slot_footer_captions(self):
        for order in self:
            for n in range(1, 6):
                area = getattr(order, "quoter_slot_%d_area_id" % n)
                aname = area.name if area else ""
                order["quoter_slot_%d_caption_products" % n] = (
                    _("Productos %s") % aname if aname else _("Productos")
                )
                order["quoter_slot_%d_caption_adjustments" % n] = (
                    _("Ajustes %s") % aname if aname else _("Ajustes")
                )

    @api.depends(
        "order_line",
        "order_line.quoter_tab_area_id",
        "order_line.quoter_is_adjustment_line",
        "order_line.quoter_range_hour_ids",
        "order_line.quoter_range_hour_ids.hours",
        "order_line.quoter_range_hour_ids.area_range_id",
        "order_line.name",
        "quoter_slot_1_area_id",
        "quoter_slot_2_area_id",
        "quoter_slot_3_area_id",
        "quoter_slot_4_area_id",
        "quoter_slot_5_area_id",
        "quoter_slot_1_area_id.area_range_ids",
        "quoter_slot_2_area_id.area_range_ids",
        "quoter_slot_3_area_id.area_range_ids",
        "quoter_slot_4_area_id.area_range_ids",
        "quoter_slot_5_area_id.area_range_ids",
        "quoter_block_slot_1_id.global_discount_amount",
        "quoter_block_slot_2_id.global_discount_amount",
        "quoter_block_slot_3_id.global_discount_amount",
        "quoter_block_slot_4_id.global_discount_amount",
        "quoter_block_slot_5_id.global_discount_amount",
        "quoter_block_slot_1_id.global_surcharge_amount",
        "quoter_block_slot_2_id.global_surcharge_amount",
        "quoter_block_slot_3_id.global_surcharge_amount",
        "quoter_block_slot_4_id.global_surcharge_amount",
        "quoter_block_slot_5_id.global_surcharge_amount",
        "partner_id",
        "pricelist_id",
        "date_order",
    )
    def _compute_quoter_slot_area_summary_html(self):
        for order in self:
            for n in range(1, 6):
                area = getattr(order, "quoter_slot_%d_area_id" % n)
                block = getattr(order, "quoter_block_slot_%d_id" % n)
                fname = "quoter_slot_%d_area_summary_html" % n
                if not area:
                    order[fname] = False
                else:
                    order[fname] = order._quoter_build_area_summary_html(area, block)

    @api.depends(
        "quoter_block_slot_1_id.state",
        "quoter_block_slot_2_id.state",
        "quoter_block_slot_3_id.state",
        "quoter_block_slot_4_id.state",
        "quoter_block_slot_5_id.state",
    )
    def _compute_quoter_slot_editable(self):
        """Solo en Abierto (draft): botones, nivel y cambio de estado vía flujo normal."""
        for order in self:
            for n in range(1, 6):
                block = getattr(order, "quoter_block_slot_%s_id" % n)
                # En registros nuevos (NewId) el bloque puede existir pero aún sin estado seteado.
                editable = (not block) or (block.state in (False, "draft"))
                setattr(order, "quoter_slot_%s_editable" % n, editable)

    @api.depends(
        "quoter_block_slot_1_id.state",
        "quoter_block_slot_2_id.state",
        "quoter_block_slot_3_id.state",
        "quoter_block_slot_4_id.state",
        "quoter_block_slot_5_id.state",
    )
    def _compute_quoter_slot_lock_flags(self):
        for order in self:
            for n in range(1, 6):
                block = getattr(order, "quoter_block_slot_%s_id" % n)
                st = block.state if block else False
                structure_locked = bool(block) and st in ("published", "cancel")
                lines_frozen = bool(block) and st == "cancel"
                setattr(order, "quoter_slot_%s_structure_locked" % n, structure_locked)
                setattr(order, "quoter_slot_%s_lines_frozen" % n, lines_frozen)

    @api.depends()
    def _compute_quoter_menu_context(self):
        active = bool(self.env.context.get("quoter_use_cot_sequence"))
        for order in self:
            order.quoter_menu_context = active

    @api.depends(
        "is_quotation",
        "order_line",
        "order_line.price_subtotal",
        "order_line.quoter_is_area_discount_total_line",
        "order_line.display_type",
    )
    def _compute_quoter_footer_area_discount_amount(self):
        for order in self:
            if not order.is_quotation:
                order.quoter_footer_area_discount_amount = 0.0
                continue
            lines = order.order_line.filtered(
                lambda l: l.quoter_is_area_discount_total_line and not l.display_type
            )
            order.quoter_footer_area_discount_amount = sum(lines.mapped("price_subtotal"))

    @api.depends("is_quotation", "quotation_sequence", "name")
    def _compute_quoter_form_title(self):
        for order in self:
            if order.is_quotation:
                order.quoter_form_title = (
                    order.quotation_sequence or order.name or ""
                )
            else:
                order.quoter_form_title = False

    def name_get(self):
        res = super().name_get()
        if not res:
            return res
        by_id = {oid: name for oid, name in res}
        out = []
        for record in self:
            disp = by_id.get(record.id, record.name or "")
            if record.is_quotation and record.quotation_sequence:
                disp = record.quotation_sequence
            out.append((record.id, disp))
        return out

    def _quoter_sale_name_is_placeholder(self):
        """Nombre aún no asignado por el flujo estándar (evita pisar un S... ya generado)."""
        self.ensure_one()
        mark = _("New")
        name = (self.name or "").strip()
        return not name or name == mark

    def _quoter_prepare_vals_for_create(self, vals):
        """Cotización: solo consume ``quoter.quotation`` (Q…).

        Se asigna ``name`` igual al número Q para que ``sale.order``:create no llame a la secuencia
        estándar de pedidos (evita saltos 8183–8184 al crear una cotización entre dos ventas).

        - ``is_quotation`` puede no venir en el primer ``create`` del formulario.
        - La acción del menú Cotizador envía ``default_is_quotation`` y ``quoter_use_cot_sequence``.
        """
        ctx = self.env.context
        if ctx.get("quoter_use_cot_sequence"):
            vals["is_quotation"] = True
        elif "is_quotation" not in vals and "default_is_quotation" in ctx:
            vals["is_quotation"] = ctx["default_is_quotation"]
        if not vals.get("is_quotation"):
            return
        if not vals.get("quotation_sequence"):
            vals["quotation_sequence"] = (
                self.env["ir.sequence"].next_by_code("quoter.quotation") or "/"
            )
        vals["name"] = vals["quotation_sequence"]

    def _quoter_guard_quotation_name_before_sale_create(self, vals):
        """Refuerzo: si ``sale.order``:create ve ``name`` == _('New'), consume ``sale.order``.

        Odoo 15 usa ``model_create_multi`` y vuelve a fusionar defaults; además el orden de
        herencias puede dejar ``name`` en placeholder pese a ser cotización PGK.

        Repite la lógica de contexto de ``_quoter_prepare_vals_for_create`` para no depender
        del orden entre ambos si en el futuro se refactoriza.
        """
        ctx = self.env.context
        if ctx.get("quoter_use_cot_sequence"):
            vals["is_quotation"] = True
        elif "is_quotation" not in vals and "default_is_quotation" in ctx:
            vals["is_quotation"] = ctx["default_is_quotation"]
        if not vals.get("is_quotation"):
            return
        mark = _("New")
        name = vals.get("name")
        if name and name != mark:
            return
        if not vals.get("quotation_sequence"):
            vals["quotation_sequence"] = (
                self.env["ir.sequence"].next_by_code("quoter.quotation") or "/"
            )
        vals["name"] = vals["quotation_sequence"]

    def _quoter_apply_default_sales_setup(self, vals):
        """Completa valores por defecto de cabecera desde Ajustes del Cotizador."""
        if not vals.get("is_quotation"):
            return
        icp = self.env["ir.config_parameter"].sudo()
        defaults_map = (
            ("pricelist_id", "quoter.default_pricelist_id", "product.pricelist"),
            ("payment_term_id", "quoter.default_payment_term_id", "account.payment.term"),
            ("team_id", "quoter.default_team_id", "crm.team"),
        )
        for field_name, param_key, model_name in defaults_map:
            if field_name not in self._fields or vals.get(field_name):
                continue
            raw_id = icp.get_param(param_key)
            if not raw_id:
                continue
            try:
                rec_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            rec = self.env[model_name].browse(rec_id)
            if rec.exists():
                vals[field_name] = rec.id

    def _quoter_apply_hidden_fields_policy(self, vals, force=False):
        """Para cotizaciones, limpia campos ocultos de la UI."""
        if not force and not vals.get("is_quotation"):
            return
        for field_name in ("note", "internal_notes"):
            if field_name in self._fields:
                vals[field_name] = False
        # Campo custom de "socio" (distinto a Socio asignado): oculto y desactivado.
        if "partner" in self._fields:
            vals["partner"] = False
        # Pestaña de firma del cliente oculta para cotizaciones.
        if "require_signature" in self._fields:
            vals["require_signature"] = False

    @api.model_create_multi
    def create(self, vals_list):
        # Normalizar como BaseModel (dict único → lista de un elemento).
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        for vals in vals_list:
            self._check_quoter_responsibles_write_access(vals)
            merged = self._add_missing_default_values(dict(vals or {}))
            vals.clear()
            vals.update(merged)
            self._quoter_prepare_vals_for_create(vals)
            self._quoter_guard_quotation_name_before_sale_create(vals)
            self._quoter_apply_default_sales_setup(vals)
            self._quoter_apply_hidden_fields_policy(vals)
        records = super().create(vals_list)
        for order, vals in zip(records, vals_list):
            order._sync_quoter_area_blocks()
            order._quoter_autoload_default_products_after_save(trigger_vals=vals)
            if order.is_quotation:
                order._quoter_sync_area_discount_total_line()
        return records

    def write(self, vals):
        self._check_quoter_responsibles_write_access(vals)
        if vals is not None and self.env.context.get("quoter_use_cot_sequence"):
            vals = dict(vals)
            vals["is_quotation"] = True
        if vals and (
            vals.get("is_quotation")
            or any(order.is_quotation for order in self)
        ):
            vals = dict(vals)
            self._quoter_apply_hidden_fields_policy(
                vals, force=not vals.get("is_quotation")
            )
        res = super().write(vals)
        if "quoter_area_ids" in vals or "is_quotation" in vals:
            self._sync_quoter_area_blocks()
        if vals:
            self._quoter_autoload_default_products_after_save(trigger_vals=vals)
            discount_keys = {
                "quoter_slot_1_global_discount",
                "quoter_slot_2_global_discount",
                "quoter_slot_3_global_discount",
                "quoter_slot_4_global_discount",
                "quoter_slot_5_global_discount",
                "quoter_slot_1_global_surcharge",
                "quoter_slot_2_global_surcharge",
                "quoter_slot_3_global_surcharge",
                "quoter_slot_4_global_surcharge",
                "quoter_slot_5_global_surcharge",
            }
            if any(k in vals for k in discount_keys):
                for order in self.filtered("is_quotation"):
                    order._quoter_sync_area_discount_total_line()
        # Refuerzo: sincronizar siempre después de guardar para evitar que comandos
        # de order_line del formulario pisen la línea técnica.
        for order in self.filtered(lambda o: o.is_quotation and isinstance(o.id, int)):
            order._quoter_sync_area_discount_total_line()
        # Solo registros ya guardados (id entero). Con NewId aún no hay fila en BD:
        # pedir la secuencia aquí consumía Q... al editar el formulario antes del 1er guardado.
        missing_seq = self.filtered(
            lambda o: o.is_quotation
            and not o.quotation_sequence
            and isinstance(o.id, int)
        )
        if missing_seq:
            seq_env = self.env["ir.sequence"]
            for order in missing_seq:
                qref = seq_env.next_by_code("quoter.quotation") or "/"
                patch = {"quotation_sequence": qref}
                if order._quoter_sale_name_is_placeholder():
                    patch["name"] = qref
                super(SaleOrder, order).write(patch)
        return res

    def _quoter_autoload_default_products_after_save(self, trigger_vals=None):
        """Al guardar: asegurar predeterminados por área (sin depender del nivel)."""
        trigger_vals = trigger_vals or {}
        should_run = bool(
            "quoter_area_ids" in trigger_vals
            or "is_quotation" in trigger_vals
            or "default_is_quotation" in self.env.context
            or self.env.context.get("quoter_use_cot_sequence")
        )
        if not should_run:
            return

        for order in self:
            if not order.is_quotation:
                continue
            blocks = order.quoter_area_block_ids.filtered(lambda b: b.state in (False, "draft"))
            for block in blocks:
                block.action_quoter_load_default_products()

    def _quoter_load_default_products_onchange(self):
        """En el formulario: cargar líneas predeterminadas por área (sin depender del nivel)."""
        self.ensure_one()
        if not self.is_quotation:
            return
        QuoterLine = self.env["quoter.service.line"]
        for area in self.quoter_area_ids:
            default_lines = QuoterLine.search(
                [("area_id", "=", area.id), ("is_default_product", "=", True)]
            )
            for qline in default_lines:
                tmpl = qline.product_tmpl_id or (
                    qline.product_id and qline.product_id.product_tmpl_id
                )
                product = tmpl.product_variant_id if tmpl else qline.product_id
                if not product:
                    continue
                exists = self.order_line.filtered(
                    lambda l, a=area, p=product: l.quoter_tab_area_id == a and l.product_id == p
                )[:1]
                if exists:
                    continue
                line_new = self.env["sale.order.line"].new(
                    {
                        "order_id": self,
                        "product_id": product.id,
                        "product_uom_qty": 1.0,
                        "quoter_tab_area_id": area.id,
                    }
                )
                if hasattr(line_new, "product_id_change"):
                    line_new.product_id_change()
                if hasattr(line_new, "_onchange_product_id"):
                    line_new._onchange_product_id()
                self.order_line += line_new

    def _sync_quoter_area_blocks(self):
        Block = self.env["quoter.sale.order.area"]
        for order in self:
            if not order.is_quotation:
                order.quoter_area_block_ids.unlink()
                continue
            keep = order.quoter_area_ids
            order.quoter_area_block_ids.filtered(lambda b: b.area_id not in keep).unlink()
            have = order.quoter_area_block_ids.mapped("area_id")
            for area in keep:
                if area not in have:
                    Block.create({"order_id": order.id, "area_id": area.id})

    def _quoter_area_discount_line_product(self):
        return self.env.ref("quoter.product_quoter_area_discount_sum", raise_if_not_found=False)

    def _quoter_sync_area_discount_total_line(self):
        """Sincroniza una sola línea contable con el neto Descuento/Recargo de áreas."""
        self.ensure_one()
        if not self.is_quotation:
            return
        product = self._quoter_area_discount_line_product()
        if not product:
            return
        line_model = self.env["sale.order.line"]
        discount_lines = self.order_line.filtered("quoter_is_area_discount_total_line")
        total_discount = 0.0
        total_surcharge = 0.0
        for block in self.quoter_area_block_ids:
            if not block.area_id:
                continue
            prod, adj = self._quoter_slot_subtotals_untaxed(block.area_id)
            sub = prod + adj
            disc_pct, surcharge_pct = self._quoter_block_adjustment_amounts(block)
            total_discount += sub * (disc_pct / 100.0)
            total_surcharge += sub * (surcharge_pct / 100.0)
        # Neto: descuento resta, recargo suma.
        line_amount = float(total_surcharge or 0.0) - float(total_discount or 0.0)
        rounding = self.currency_id.rounding or 0.01
        if float_is_zero(line_amount, precision_rounding=rounding):
            if discount_lines:
                discount_lines.unlink()
            return
        vals = {
            "order_id": self.id,
            "company_id": self.company_id.id,
            "product_id": product.id,
            "name": _("Descuento/Recargo global de áreas"),
            "product_uom_qty": 1.0,
            "product_uom": product.uom_id.id,
            "price_unit": line_amount,
            "tax_id": [(6, 0, [])],
            "discount": 0.0,
            "quoter_is_area_discount_total_line": True,
        }
        if discount_lines:
            discount_lines[0].write(vals)
            if len(discount_lines) > 1:
                discount_lines[1:].unlink()
        else:
            vals["sequence"] = (max(self.order_line.mapped("sequence") or [0]) + 1)
            line_model.create(vals)

    def action_confirm(self):
        for order in self:
            if order.is_quotation:
                draft_blocks = order.quoter_area_block_ids.filtered(
                    lambda b: b.state == "draft"
                )
                if draft_blocks:
                    raise UserError(
                        _(
                            "No puede confirmar: hay cotización por área abierta (sin cerrar): %s."
                        )
                        % ", ".join(draft_blocks.mapped("area_id.display_name"))
                    )
                order._quoter_sync_area_discount_total_line()
        return super().action_confirm()

    @api.onchange("is_quotation")
    def _onchange_is_quotation(self):
        if not self.is_quotation:
            self.quoter_area_ids = [(5, 0, 0)]
            self.quoter_area_block_ids = [(5, 0, 0)]

    @api.onchange("quoter_area_ids")
    def _onchange_quoter_area_ids(self):
        if not self.quoter_area_ids:
            self.quoter_area_block_ids = [(5, 0, 0)]
            return
        if len(self.quoter_area_ids) > 5:
            top5 = self._quoter_areas_ordered_for_slots()[:5]
            self.quoter_area_ids = [(6, 0, top5.ids)]
        self._sync_quoter_area_blocks_onchange()
        self._quoter_load_default_products_onchange()

    def _sync_quoter_area_blocks_onchange(self):
        selected = set(self.quoter_area_ids.ids)
        cmds = []
        for block in self.quoter_area_block_ids:
            if block.area_id.id not in selected:
                cmds.append((2, block.id))
        existing = set(self.quoter_area_block_ids.mapped("area_id").ids) & selected
        for aid in selected:
            if aid not in existing:
                cmds.append((0, 0, {"area_id": aid}))
        if cmds:
            self.quoter_area_block_ids = cmds

    def _quoter_block_for_slot(self, slot):
        self.ensure_one()
        area = getattr(self, "quoter_slot_%s_area_id" % slot)
        if not area:
            return self.env["quoter.sale.order.area"]
        return self.quoter_area_block_ids.filtered(lambda b, a=area: b.area_id == a)[:1]

    def _action_slot_load_defaults(self, slot):
        self.ensure_one()
        block = self._quoter_block_for_slot(slot)
        if block:
            return block.action_quoter_load_default_products()
        return True

    def _action_slot_publish(self, slot):
        self.ensure_one()
        block = self._quoter_block_for_slot(slot)
        if block:
            return block.action_quoter_publish()
        return True

    def _action_slot_cancel(self, slot):
        self.ensure_one()
        block = self._quoter_block_for_slot(slot)
        if block:
            return block.action_quoter_cancel_block()
        return True

    def _action_slot_reopen(self, slot):
        self.ensure_one()
        block = self._quoter_block_for_slot(slot)
        if block:
            return block.action_quoter_reopen()
        return True

    def action_quoter_slot_1_load_defaults(self):
        return self._action_slot_load_defaults(1)

    def action_quoter_slot_2_load_defaults(self):
        return self._action_slot_load_defaults(2)

    def action_quoter_slot_3_load_defaults(self):
        return self._action_slot_load_defaults(3)

    def action_quoter_slot_4_load_defaults(self):
        return self._action_slot_load_defaults(4)

    def action_quoter_slot_5_load_defaults(self):
        return self._action_slot_load_defaults(5)

    def action_quoter_slot_1_publish(self):
        return self._action_slot_publish(1)

    def action_quoter_slot_2_publish(self):
        return self._action_slot_publish(2)

    def action_quoter_slot_3_publish(self):
        return self._action_slot_publish(3)

    def action_quoter_slot_4_publish(self):
        return self._action_slot_publish(4)

    def action_quoter_slot_5_publish(self):
        return self._action_slot_publish(5)

    def action_quoter_slot_1_cancel(self):
        return self._action_slot_cancel(1)

    def action_quoter_slot_2_cancel(self):
        return self._action_slot_cancel(2)

    def action_quoter_slot_3_cancel(self):
        return self._action_slot_cancel(3)

    def action_quoter_slot_4_cancel(self):
        return self._action_slot_cancel(4)

    def action_quoter_slot_5_cancel(self):
        return self._action_slot_cancel(5)

    def action_quoter_slot_1_reopen(self):
        return self._action_slot_reopen(1)

    def action_quoter_slot_2_reopen(self):
        return self._action_slot_reopen(2)

    def action_quoter_slot_3_reopen(self):
        return self._action_slot_reopen(3)

    def action_quoter_slot_4_reopen(self):
        return self._action_slot_reopen(4)

    def action_quoter_slot_5_reopen(self):
        return self._action_slot_reopen(5)

    @api.constrains("quoter_area_ids")
    def _check_quoter_area_ids_max_5(self):
        for order in self:
            if order.is_quotation and len(order.quoter_area_ids) > 5:
                raise UserError(_("Como máximo puede seleccionar 5 áreas en una cotización."))

from odoo import fields, models


class SubscriptionTariffUpdateHistory(models.Model):
    """Stores one history row per affected subscription line update."""

    _name = "subscription.tariff.update.history"
    _description = "Subscription Tariff Update History"
    _order = "update_datetime desc, id desc"

    subscription_id = fields.Many2one(
        "subscription.package",
        string="Suscripción",
        required=True,
        ondelete="cascade",
        index=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        ondelete="restrict",
    )
    quantity = fields.Float(
        string="Cantidad",
    )
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Cuenta analítica",
        ondelete="set null",
    )
    update_datetime = fields.Datetime(
        string="Fecha de actualización",
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    update_type = fields.Selection(
        selection=[
            ("manual", "Manual"),
            ("manual_percentage", "Porcentaje manual"),
            ("ipc", "IPC"),
        ],
        string="Tipo de actualización",
        required=True,
        default="manual",
    )
    applied_percentage = fields.Float(
        string="Porcentaje aplicado",
        digits="Subscription IPC Percentage",
    )
    old_price = fields.Float(
        string="Precio anterior",
        digits="Product Price",
        required=True,
    )
    new_price = fields.Float(
        string="Precio nuevo",
        digits="Product Price",
        required=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Usuario",
        required=True,
        default=lambda self: self.env.user,
    )
    event_id = fields.Char(
        string="Evento",
        required=True,
        index=True,
        help="Identificador común para agrupar líneas del mismo evento.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        related="subscription_id.company_id",
        store=True,
        readonly=True,
    )
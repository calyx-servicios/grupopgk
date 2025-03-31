# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ar_payment_foreign_currency = fields.Selection(
        [("S", "Yes"), ("N", "No")],
        compute="compute_l10n_ar_payment_foreign_currency",
        store=True,
        readonly=False
    )
    l10n_ar_currency_code = fields.Char("Currency Code", related="currency_id.name")

    @api.onchange("currency_id", "line_ids")
    @api.depends("currency_id")
    def compute_l10n_ar_payment_foreign_currency(self):
        self.l10n_ar_payment_foreign_currency = False
        for move in self:
            default_value = move.company_id.l10n_ar_payment_foreign_currency
            if default_value == "account":
                account = move.line_ids.account_id.filtered(lambda x: x.account_type == "asset_receivable")
                default_value = "S" if account.currency_id and account.currency_id != move.company_currency_id else "N"
            move.l10n_ar_payment_foreign_currency = default_value

    def get_pyafipws_currency_rate(self):
        self.ensure_one()
        afip_ws = self.journal_id.afip_ws
        ws = self.company_id.get_connection(afip_ws).connect()
        afipws_get_currency_rate = self.pyafipws_get_currency_rate(ws)
        # TODO: crear cotizacion?
        self._set_afip_rate()
        notification = {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _(
                    "Actual afip rate is %s" % afipws_get_currency_rate
                ),
                "type": "success",
                "sticky": True,  # True/False will display for few seconds if false
            },
        }
        return notification

    # Metodo sobreescripto
    def wsfe_pyafipws_create_invoice(self, ws, invoice_info):
        ws.CrearFactura(
            invoice_info["concepto"],
            invoice_info["tipo_doc"],
            invoice_info["nro_doc"],
            invoice_info["doc_afip_code"],
            invoice_info["pos_number"],
            invoice_info["cbt_desde"],
            invoice_info["cbt_hasta"],
            invoice_info["imp_total"],
            invoice_info["imp_tot_conc"],
            invoice_info["imp_neto"],
            invoice_info["imp_iva"],
            invoice_info["imp_trib"],
            invoice_info["imp_op_ex"],
            invoice_info["fecha_cbte"],
            invoice_info["fecha_venc_pago"],
            invoice_info["fecha_serv_desde"],
            invoice_info["fecha_serv_hasta"],
            invoice_info["moneda_id"],
            invoice_info["moneda_ctz"],
            cancela_misma_moneda_ext=invoice_info["cancela_misma_moneda_ext"],
            condicion_iva_receptor=invoice_info["condicion_iva_receptor_id"],
        )

    def wsmtxca_pyafipws_create_invoice(self, ws, invoice_info):
        ws.CrearFactura(
            invoice_info["concepto"],
            invoice_info["tipo_doc"],
            invoice_info["nro_doc"],
            invoice_info["doc_afip_code"],
            invoice_info["pos_number"],
            invoice_info["cbt_desde"],
            invoice_info["cbt_hasta"],
            invoice_info["imp_total"],
            invoice_info["imp_tot_conc"],
            invoice_info["imp_neto"],
            invoice_info["imp_subtotal"],
            invoice_info["imp_trib"],
            invoice_info["imp_op_ex"],
            invoice_info["fecha_cbte"],
            invoice_info["fecha_venc_pago"],
            invoice_info["fecha_serv_desde"],
            invoice_info["fecha_serv_hasta"],
            invoice_info["moneda_id"],
            invoice_info["moneda_ctz"],
            invoice_info["obs_generales"],
            cancela_misma_moneda_ext=invoice_info["cancela_misma_moneda_ext"],
            condicion_iva_receptor=invoice_info["condicion_iva_receptor_id"],
        )

    def wsfex_pyafipws_create_invoice(self, ws, invoice_info):
        ws.CrearFactura(
            invoice_info["doc_afip_code"],
            invoice_info["pos_number"],
            invoice_info["cbte_nro"],
            invoice_info["fecha_cbte"],
            invoice_info["imp_total"],
            invoice_info["tipo_expo"],
            invoice_info["permiso_existente"],
            invoice_info["pais_dst_cmp"],
            invoice_info["nombre_cliente"],
            invoice_info["cuit_pais_cliente"],
            invoice_info["domicilio_cliente"],
            invoice_info["id_impositivo"],
            invoice_info["moneda_id"],
            invoice_info["moneda_ctz"],
            invoice_info["obs_comerciales"],
            invoice_info["obs_generales"],
            invoice_info["forma_pago"],
            invoice_info["incoterms"],
            invoice_info["idioma_cbte"],
            invoice_info["incoterms_ds"],
            invoice_info["fecha_pago"],
            cancela_misma_moneda_ext=invoice_info["cancela_misma_moneda_ext"],
            condicion_iva_receptor=invoice_info["condicion_iva_receptor_id"],
        )

    def wsbfe_pyafipws_create_invoice(self, ws, invoice_info):
        ws.CrearFactura(
            invoice_info["tipo_doc"],
            invoice_info["nro_doc"],
            invoice_info["zona"],
            invoice_info["doc_afip_code"],
            invoice_info["pos_number"],
            invoice_info["cbte_nro"],
            invoice_info["fecha_cbte"],
            invoice_info["imp_total"],
            invoice_info["imp_neto"],
            invoice_info["imp_iva"],
            invoice_info["imp_tot_conc"],
            invoice_info["impto_liq_rni"],
            invoice_info["imp_op_ex"],
            invoice_info["imp_perc"],
            invoice_info["imp_iibb"],
            invoice_info["imp_perc_mun"],
            invoice_info["imp_internos"],
            invoice_info["moneda_id"],
            invoice_info["moneda_ctz"],
            invoice_info["fecha_venc_pago"],
            cancela_misma_moneda_ext=invoice_info["cancela_misma_moneda_ext"],
            condicion_iva_receptor=invoice_info["condicion_iva_receptor_id"],
        )

    def base_map_invoice_info(self):
        invoice_info = super().base_map_invoice_info()

        invoice_info["cancela_misma_moneda_ext"] = self.l10n_ar_payment_foreign_currency
        invoice_info["condicion_iva_receptor_id"] = self.partner_id.l10n_ar_afip_responsibility_type_id.code

        return invoice_info

    def pyafipws_get_currency_rate(self, ws):
        self.ensure_one()
        afip_ws = self.journal_id.afip_ws
        if not afip_ws:
            return
        if hasattr(self, "%s_pyafipws_get_currency_rate" % afip_ws):
            return getattr(self, "%s_pyafipws_get_currency_rate" % afip_ws)(
                ws
            )
        else:
            return _("AFIP WS %s not implemented") % afip_ws

    def pyafipws_get_currency_rate(self, ws):
        return ws.ParamGetCotizacion(self.currency_id.l10n_ar_afip_code)
    
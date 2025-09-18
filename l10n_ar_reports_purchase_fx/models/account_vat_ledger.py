from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountVatLedger(models.Model):

    _inherit = "account.vat.ledger"

    def _get_REGINFO_CV_CBTE(self, alicuotas):
        self.ensure_one()
        res = []
        invoices = self._get_txt_invoices()
        for inv in invoices:
            # si no existe la factura en alicuotas es porque no tienen ninguna
            cant_alicuotas = len(alicuotas.get(inv))

            currency_rate = inv.l10n_ar_currency_rate
            currency_code = inv.currency_id.l10n_ar_afip_code

            invoice_number, pos_number = self._get_pos_and_invoice_invoice_number(inv)
            doc_code, doc_number = self._get_partner_document_code_and_number(
                inv.partner_id
            )

            if self.type == "purchase":
                if inv.currency_id == inv.company_id.currency_id:
                    amount_total = (1 if inv.is_inbound() else -1) * inv.amount_total_signed
                    amounts = inv._l10n_ar_get_amounts(company_currency=True)
                else:
                    amount_total = inv.amount_total
                    amounts = inv._l10n_ar_get_amounts(company_currency=False)
            else:
                # Facturas de venta
                amounts = inv._l10n_ar_get_amounts(company_currency=True)
                amount_total = (1 if inv.is_inbound() else -1) * inv.amount_total_signed
            vat_amount = amounts["vat_amount"]
            vat_exempt_base_amount = amounts["vat_exempt_base_amount"]
            vat_untaxed_base_amount = amounts["vat_untaxed_base_amount"]
            other_taxes_amount = amounts["other_taxes_amount"]
            vat_perc_amount = amounts["vat_perc_amount"]
            iibb_perc_amount = amounts["iibb_perc_amount"]
            mun_perc_amount = amounts["mun_perc_amount"]
            intern_tax_amount = amounts["intern_tax_amount"]
            perc_imp_nacionales_amount = (
                amounts["profits_perc_amount"] + amounts["other_perc_amount"]
            )

            if vat_exempt_base_amount:
                # operacion con zona franca
                if inv.partner_id.l10n_ar_afip_responsibility_type_id.code == "10":
                    codigo_operacion = "Z"
                # expo al exterior
                elif inv.l10n_latam_document_type_id.l10n_ar_letter == "E":
                    codigo_operacion = "X"
                # operacion exenta
                else:
                    codigo_operacion = "E"
            # despacho de importacion
            elif inv.l10n_latam_document_type_id.code == "66":
                codigo_operacion = "E"
            # operacion no gravada
            elif vat_untaxed_base_amount:
                codigo_operacion = "N"
            else:
                codigo_operacion = " "

            row = [
                # Campo 1: Fecha de comprobante
                inv.invoice_date.strftime("%Y%m%d"),
                # Campo 2: Tipo de Comprobante.
                "{:0>3d}".format(int(inv.l10n_latam_document_type_id.code)),
                # Campo 3: Punto de Venta
                pos_number,
                # Campo 4: Número de Comprobante
                # Si se trata de un comprobante de varias hojas, se deberá
                # informar el número de documento de la primera hoja, teniendo
                # en cuenta lo normado en el  artículo 23, inciso a), punto
                # 6., de la Resolución General N° 1.415, sus modificatorias y
                # complementarias.
                # En el supuesto de registrar de manera agrupada por totales
                # diarios, se deberá consignar el primer número de comprobante
                # del rango a considerar.
                invoice_number,
            ]

            if self.type == "sale":
                # Campo 5: Número de Comprobante Hasta.
                # En el resto de los casos se consignará el dato registrado en el campo 4
                row.append(invoice_number)
            else:
                # Campo 5: Despacho de importación
                if inv.l10n_latam_document_type_id.code == "66":
                    row.append((inv.l10n_latam_document_number).rjust(16, "0"))
                else:
                    row.append("".rjust(16, " "))

            row += [
                # Campo 6: Código de documento del comprador.
                doc_code,
                # Campo 7: Número de Identificación del comprador
                doc_number,
                # Campo 8: Apellido y Nombre del comprador.
                inv.commercial_partner_id.name.ljust(30, " ")[:30],
                # Campo 9: Importe Total de la Operación.
                self.format_amount(amount_total),
                # Campo 10: Importe total de conceptos que no integran el precio neto gravado
                self.format_amount(vat_untaxed_base_amount),
            ]

            if self.type == "sale":
                row += [
                    # Campo 11: Percepción a no categorizados
                    # la figura no categorizado / responsable no inscripto no se usa más
                    self.format_amount(0.0),
                    # Campo 12: Importe de operaciones exentas
                    self.format_amount(vat_exempt_base_amount),
                    # Campo 13: Importe de percepciones o pagos a cuenta de impuestos Nacionales
                    self.format_amount(perc_imp_nacionales_amount + vat_perc_amount),
                ]
            else:
                row += [
                    # Campo 11: Importe de operaciones exentas
                    self.format_amount(vat_exempt_base_amount),
                    # Campo 12: Importe de percepciones o pagos a cuenta del Impuesto al Valor Agregado
                    self.format_amount(vat_perc_amount),
                    # Campo 13: Importe de percepciones o pagos a cuenta otros impuestos nacionales
                    self.format_amount(perc_imp_nacionales_amount),
                ]

            row += [
                # Campo 14: Importe de percepciones de ingresos brutos
                self.format_amount(iibb_perc_amount),
                # Campo 15: Importe de percepciones de impuestos municipales
                self.format_amount(mun_perc_amount),
                # Campo 16: Importe de impuestos internos
                self.format_amount(intern_tax_amount),
                # Campo 17: Código de Moneda
                str(currency_code),
                # Campo 18: Tipo de Cambio
                # nueva modalidad de currency_rate
                self.format_amount(currency_rate, padding=10, decimals=6),
                # Campo 19: Cantidad de alícuotas de IVA
                str(cant_alicuotas),
                # Campo 20: Código de operación.
                codigo_operacion,
            ]

            if self.type == "sale":
                row += [
                    # Campo 21: Otros Tributos
                    self.format_amount(other_taxes_amount),
                    # Campo 22: vencimiento comprobante (no figura en
                    # instructivo pero si en aplicativo) para tique y factura
                    # de exportacion no se informa, tmb para algunos otros
                    # pero que tampoco tenemos implementados
                    (
                        inv.l10n_latam_document_type_id.code
                        in [
                            "19",
                            "20",
                            "21",
                            "16",
                            "55",
                            "81",
                            "82",
                            "83",
                            "110",
                            "111",
                            "112",
                            "113",
                            "114",
                            "115",
                            "116",
                            "117",
                            "118",
                            "119",
                            "120",
                            "201",
                            "202",
                            "203",
                            "206",
                            "207",
                            "208",
                            "211",
                            "212",
                            "213",
                        ]
                        and "00000000"
                        or inv.invoice_date_due.strftime("%Y%m%d")
                    ),
                ]
            else:
                # Campo 21: Crédito Fiscal Computable
                if self.prorate_tax_credit:
                    if self.prorate_type == "global":
                        row.append(self.format_amount(0))
                    else:
                        # row.append(self.format_amount(0))
                        # por ahora no implementado pero seria lo mismo que
                        # sacar si prorrateo y que el cliente entre en el txt
                        # en cada comprobante y complete cuando es en
                        # credito fiscal computable
                        raise ValidationError(
                            _(
                                "Para utilizar el prorrateo por comprobante:\n"
                                '1) Exporte los archivos sin la opción "Proratear '
                                'Crédito de Impuestos"\n2) Importe los mismos '
                                "en el aplicativo\n3) En el aplicativo de afip, "
                                "comprobante por comprobante, indique el valor "
                                'correspondiente en el campo "Crédito Fiscal '
                                'Computable"'
                            )
                        )
                else:
                    row.append(self.format_amount(vat_amount))

                liquido_type = inv.l10n_latam_document_type_id.code in [
                    "033",
                    "058",
                    "059",
                    "060",
                    "063",
                ]
                row += [
                    # Campo 22: Otros Tributos
                    self.format_amount(other_taxes_amount),
                    # TODO still not implemented on this three fields for use case with third pary commisioner
                    # Campo 23: CUIT Emisor / Corredor
                    # Se informará sólo si en el campo "Tipo de Comprobante" se consigna '033', '058', '059', '060' ó
                    # '063'. Si para éstos comprobantes no interviene un tercero en la operación, se consignará la
                    # C.U.I.T. del informante. Para el resto de los comprobantes se completará con ceros
                    self.format_amount(
                        liquido_type and inv.company_id.partner_id.ensure_vat() or 0,
                        padding=11,
                    ),
                    # Campo 24: Denominación Emisor / Corredor
                    (liquido_type and inv.company_id.name or "").ljust(30, " ")[:30],
                    # Campo 25: IVA Comisión
                    # Si el campo 23 es distinto de cero se consignará el importe del I.V.A. de la comisión
                    self.format_amount(0),
                ]
            res.append("".join(row))
        self.REGINFO_CV_CBTE = "\r\n".join(res)
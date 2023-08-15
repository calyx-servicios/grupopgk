import logging

from odoo import fields

_logger = logging.getLogger(__name__)


def _get_net_price(line) -> float:
    percent = 0
    fixed = 0
    if line.tax_ids and line.price_total != 0:
        for tax in line.tax_ids:
            if tax.amount_type == "percent":
                percent += tax.amount
            else:
                fixed += tax.amount
        percent *= 0.01
    return (line.price_total - fixed) / (1 + percent)


def calculate_taxes(taxes, net_price) -> list:
    necessary_tax_fields = [
        "id",
        "name",
        "amount",
        "amount_type",
    ]
    tax_dictionary = taxes.read(necessary_tax_fields)
    for tax in tax_dictionary:
        if tax["amount_type"] == "percent":
            monto = tax["amount"] * 0.01 * net_price
            tax["monto"] = round(monto, 4)
        else:
            tax["monto"] = tax["amount"]
    return tax_dictionary


def format_name(doc):
    if not doc.journal_id.l10n_latam_use_documents:
        return doc.name
    try:
        return f"{doc.l10n_latam_document_type_id.l10n_ar_letter}-{doc.l10n_latam_document_number}"
    except Exception as ex:
        _logger.error(ex)
        return doc.name


def format_date(date: fields) -> str:
    if isinstance(date, str):
        from datetime import datetime as dt

        dt_date = dt.strptime(date, "%Y-%m-%d").strftime("%d/%m/%Y")
        return dt_date
    return date.strftime("%d/%m/%Y")


def get_own_net_amount(doc, include_tax=False):
    own_lines = doc.invoice_line_ids.filtered(
        lambda il: il.product_id and not il.product_id.is_third_party_product
    )
    if include_tax:
        lines_amount = sum(line.price_unit * line.quantity for line in own_lines)
    else:
        lines_amount = sum(_get_net_price(line) for line in own_lines)
    if doc.type == "out_refund":
        lines_amount *= -1
    return lines_amount


def get_third_party_net_amount(doc, include_tax=False):
    third_party_lines = doc.invoice_line_ids.filtered(
        lambda il: il.product_id and il.product_id.is_third_party_product
    )
    if include_tax:
        lines_amount = sum(line.price_unit * line.quantity for line in third_party_lines)
    else:
        lines_amount = sum(_get_net_price(line) for line in third_party_lines)
    if doc.type == "out_refund":
        lines_amount *= -1
    return lines_amount


def get_invoice_type(doc):
    return "NC" if doc.type == "out_refund" else "FA"


def get_payment_report_lines(docs):
    report_lines = []
    for doc in docs:
        own_net_price = round(get_own_net_amount(doc, True), 2)
        third_party_net_amount = round(get_third_party_net_amount(doc, True), 2)
        net_total = round(own_net_price + third_party_net_amount, 2)
        report_lines.append(
            {
                "date": format_date(doc.invoice_date),
                "transaction_id": "- ".join(doc.personal_pay_transaction_ids.mapped("name")),
                "razon_social": doc.partner_id.name,
                "CUIT/DNI": format_vat(doc),
                "invoice_type": get_invoice_type(doc),
                "name": format_name(doc),
                "invoice_due_date": format_date(doc.invoice_date_due),
                "amount_total": doc.amount_total,
                "own_net_price": own_net_price,
                "third_party_net_amount": third_party_net_amount,
                "net_total": net_total,
                "payment_method": "RET",  # this must change
            }
        )
    return report_lines


def format_vat(doc):
    cuit_dni = doc.partner_id.l10n_ar_formatted_vat
    if not cuit_dni:
        _logger.info(len(doc.partner_id.vat))
        if len(doc.partner_id.vat) == 11:
            vat = doc.partner_id.vat
            cuit_dni = f"{vat[:2]}-{vat[2:10]}-{vat[-1]}"
        else:
            cuit_dni = doc.partner_id.vat
    return cuit_dni


def get_invoicing_report_lines(docs):
    report_lines = []
    for doc in docs:
        IVA_tax_id = doc.invoice_line_ids.tax_ids.filtered(lambda t: "IVA" in t.name)
        if len(IVA_tax_id) != 1:
            _logger.error("multiple IVAs found, choosing one")
            if IVA_tax_id and bool(len(IVA_tax_id)):
                IVA_tax_id = IVA_tax_id[0]
        other_tax_ids = doc.invoice_line_ids.tax_ids.filtered(lambda t: "IVA" not in t.name)
        own_net_price = round(get_own_net_amount(doc), 2)
        third_party_net_amount = round(get_third_party_net_amount(doc), 2)
        net_total = own_net_price + third_party_net_amount
        other_taxes_amount = round(
            sum(
                tax.get("monto")
                for tax in calculate_taxes(
                    other_tax_ids,
                    net_total,
                )
            ),
            2,
        )
        iva = round(
            sum(
                tax["monto"]
                for tax in calculate_taxes(
                    IVA_tax_id,
                    net_total,
                )
            ),
            2,
        )
        amount_total = doc.amount_total if doc.type == "out_invoice" else doc.amount_total * -1
        report_lines.append(
            {
                "date": format_date(doc.invoice_date),
                "invoice_type": get_invoice_type(doc),
                "name": format_name(doc),
                "razon_social": doc.partner_id.name,
                "CUIT/DNI": format_vat(doc),
                "own_net_price": own_net_price,
                "third_party_net_amount": third_party_net_amount,
                "exempt_amount": 0,
                "IVA": iva,
                "alicuot": f"{IVA_tax_id.amount}%",
                "other_taxes": other_taxes_amount,
                "amount_total": round(amount_total, 2),
            }
        )
    return report_lines

from odoo import tools, models
import logging

_logger = logging.getLogger(__name__)

class AccountArVatLine(models.Model):
    _inherit = "account.ar.vat.line"
    _auto = False

    def init(self):
        _logger.info("Vista account_ar_vat_line regenerada por account_ar_vat_fix_v1.1")
        cr = self._cr
        tools.drop_view_if_exists(cr, self._table)

        query = """
SELECT
    am.id,
    (CASE WHEN lit.l10n_ar_afip_code = '80' THEN rp.vat ELSE null END) as cuit,
    art.name as afip_responsibility_type_name,
    am.name as move_name,
    rp.name as partner_name,
    am.id as move_id,
    am.move_type,
    am.date,
    am.invoice_date,
    am.partner_id,
    am.journal_id,
    am.name,
    am.l10n_ar_afip_responsibility_type_id as afip_responsibility_type_id,
    am.l10n_latam_document_type_id as document_type_id,
    am.state,
    am.company_id,
    sum(CASE WHEN btg.l10n_ar_vat_afip_code = '5' AND am.move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1 
             WHEN btg.l10n_ar_vat_afip_code = '5' AND am.move_type IN ('in_invoice',  'in_refund')  THEN aml.balance 
             ELSE Null END) as base_21,
    sum(CASE WHEN ntg.l10n_ar_vat_afip_code = '5' AND am.move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1 
             WHEN ntg.l10n_ar_vat_afip_code = '5' AND am.move_type IN ('in_invoice',  'in_refund')  THEN aml.balance 
    		 ELSE Null END) as vat_21,
    sum(CASE WHEN btg.l10n_ar_vat_afip_code = '4' AND am.move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1 
             WHEN btg.l10n_ar_vat_afip_code = '4' AND am.move_type IN ('in_invoice',  'in_refund')  THEN aml.balance 
             ELSE Null END) as base_10,
    sum(CASE WHEN ntg.l10n_ar_vat_afip_code = '4' AND am.move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1 
             WHEN ntg.l10n_ar_vat_afip_code = '4' AND am.move_type IN ('in_invoice',  'in_refund')  THEN aml.balance 
    		 ELSE Null END) as vat_10,
    sum(CASE WHEN btg.l10n_ar_vat_afip_code = '6' AND am.move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1 
             WHEN btg.l10n_ar_vat_afip_code = '6' AND am.move_type IN ('in_invoice',  'in_refund')  THEN aml.balance 
             ELSE Null END) as base_27,
    sum(CASE WHEN ntg.l10n_ar_vat_afip_code = '6' AND am.move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1 
             WHEN ntg.l10n_ar_vat_afip_code = '6' AND am.move_type IN ('in_invoice',  'in_refund')  THEN aml.balance 
    		 ELSE Null END) as vat_27,
    sum(CASE WHEN btg.l10n_ar_vat_afip_code = '9' AND am.move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1 
             WHEN btg.l10n_ar_vat_afip_code = '9' AND am.move_type IN ('in_invoice',  'in_refund')  THEN aml.balance 
             ELSE Null END) as base_25,
    sum(CASE WHEN ntg.l10n_ar_vat_afip_code = '9' AND am.move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1 
             WHEN ntg.l10n_ar_vat_afip_code = '9' AND am.move_type IN ('in_invoice',  'in_refund')  THEN aml.balance 
    		 ELSE Null END) as vat_25,
    sum(CASE WHEN btg.l10n_ar_vat_afip_code = '8' AND am.move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1 
             WHEN btg.l10n_ar_vat_afip_code = '8' AND am.move_type IN ('in_invoice',  'in_refund')  THEN aml.balance 
             ELSE Null END) as base_5,
    sum(CASE WHEN ntg.l10n_ar_vat_afip_code = '8' AND am.move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1 
             WHEN ntg.l10n_ar_vat_afip_code = '8' AND am.move_type IN ('in_invoice',  'in_refund')  THEN aml.balance 
    		 ELSE Null END) as vat_5,
    sum(CASE WHEN btg.l10n_ar_vat_afip_code IN ('0', '1', '2', '3', '7') AND am.move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1 
             WHEN btg.l10n_ar_vat_afip_code IN ('0', '1', '2', '3', '7') AND am.move_type IN ('in_invoice',  'in_refund')  THEN aml.balance 
             ELSE Null END) as not_taxed,
    sum(CASE WHEN ntg.l10n_ar_tribute_afip_code = '06' AND am.move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1 
             WHEN ntg.l10n_ar_tribute_afip_code = '06' AND am.move_type IN ('in_invoice',  'in_refund')  THEN aml.balance 
    		 ELSE Null END) as vat_per,
    sum(CASE WHEN ntg.l10n_ar_vat_afip_code is null and ntg.l10n_ar_tribute_afip_code != '06' AND am.move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1 
             WHEN ntg.l10n_ar_vat_afip_code is null and ntg.l10n_ar_tribute_afip_code != '06' AND am.move_type IN ('in_invoice',  'in_refund')  THEN aml.balance 
             ELSE Null END) as other_taxes,
    sum(CASE WHEN am.move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1
             WHEN am.move_type IN ('in_invoice', 'in_refund') THEN aml.balance END) as total
FROM
    account_move_line aml
LEFT JOIN
    account_move as am
    ON aml.move_id = am.id
LEFT JOIN
    -- nt = net tax
    account_tax AS nt
    ON aml.tax_line_id = nt.id
LEFT JOIN
    account_move_line_account_tax_rel AS amltr
    ON aml.id = amltr.account_move_line_id
LEFT JOIN
    -- bt = base tax
    account_tax AS bt
    ON amltr.account_tax_id = bt.id
LEFT JOIN
    account_tax_group AS btg
    ON btg.id = bt.tax_group_id
LEFT JOIN
    account_tax_group AS ntg
    ON ntg.id = nt.tax_group_id
LEFT JOIN
    res_partner AS rp
    ON rp.id = am.partner_id
LEFT JOIN
    l10n_latam_identification_type AS lit
    ON rp.l10n_latam_identification_type_id = lit.id
LEFT JOIN
    l10n_ar_afip_responsibility_type AS art
    ON am.l10n_ar_afip_responsibility_type_id = art.id
WHERE
    (aml.tax_line_id is not null or btg.l10n_ar_vat_afip_code is not null)
    and am.move_type in ('out_invoice', 'in_invoice', 'out_refund', 'in_refund')
    and am.state = 'posted'
GROUP BY
    am.id, art.name, rp.id, lit.id
ORDER BY
    am.date, am.name
        """
        sql = """CREATE or REPLACE VIEW %s as (%s)""" % (self._table, query)
        cr.execute(sql)

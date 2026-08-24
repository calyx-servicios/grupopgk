from odoo import models, fields, api, _
from odoo.tools import cache
from ..utils import datareader_conn, box, cuit_alias
from datetime import datetime
import logging
import re
from odoo.exceptions import UserError
import os
import json
import traceback
from datetime import datetime, timedelta
from pprint import pprint
    
_logger = logging.getLogger(__name__)


class DataReaderConnectorWrapper(models.AbstractModel):
    _name = "datareader.connector"
    _description = "Wrapper para DataReaderConnector (externo)"

    def get_connector(self):
        return datareader_conn.DatareaderConnector.create_from_environment(self.env)

class DataReaderAccountPaymentGroupLog(models.Model):
    _name = "datareader.account.payment.group.log"
    _description = "Conector DataReader para Procesar Json"
    _inherit = ['mail.thread']
        
    name = fields.Char(string="Nombre", default="Conector DataReader", readonly=True)
    last_token = fields.Char(string="Último Token", readonly=True)
    last_connection = fields.Datetime(string="Última conexión", readonly=True)
    account_payment_group_item_ids = fields.One2many(
        'datareader.account.payment.group.log.item',
        'log_id',
        string="Detalles de Procesamiento"
    )

    @staticmethod
    def _normalize_op_number_prefix(value):
        """
        Quita caracteres no alfanuméricos pegados al INICIO del string
        """
        if not value:
            return value
        return re.sub(r'^[^A-Za-z0-9]+', '', str(value).strip())

    def _validate_op_number(self, data, errors, log_item=None):
        """
        Valida que venga número de operación y que no esté duplicado.
        Si no viene op_number, intenta usar user_id-amount_neto del JSON.
        Devuelve el número de operación o None si hay error.
        """
        op_number = data.get('op_number')

        # Si no viene op_number o es 'na', intentar usar user_id-amount_neto
        if not op_number or str(op_number).lower() == 'na':
            user_id_data = data.get('user_id')
            amount_neto = data.get('amount_neto')
            
            # Construir op_number como user_id-amount_neto
            if user_id_data and amount_neto is not None:
                if isinstance(user_id_data, dict):
                    user_id = user_id_data.get('id', '')
                else:
                    user_id = str(user_id_data) if user_id_data else ''
                
                amount_neto_str = str(amount_neto) if amount_neto else ''
                op_number = f"{user_id}-{amount_neto_str}"
            elif user_id_data:
                # Si solo hay user_id, usar solo ese
                if isinstance(user_id_data, dict):
                    op_number = str(user_id_data.get('id', ''))
                else:
                    op_number = str(user_id_data)
            
            # Si aún no hay op_number, reportar error
            if not op_number or op_number == '-':
                errors.append("No vino número de operación en la orden y no se pudo generar desde user_id y amount_neto.")
                if log_item:
                    log_item.write({'message': "\n".join(errors)})
                return None, errors

        # Validar duplicado en payment.group.
        op_number_core = self._normalize_op_number_prefix(op_number)
        duplicate_domain = [
            ('state', '=', 'posted'),
            ('communication', '!=', False),
        ]
        use_fuzzy_match = bool(op_number_core) and len(op_number_core) >= 4
        if use_fuzzy_match:
            duplicate_domain.append(('communication', 'ilike', op_number_core))
        else:
            duplicate_domain.append(('communication', '=', op_number))

        candidates = self.env['account.payment.group'].sudo().search(duplicate_domain, limit=50)
        existing_op = self.env['account.payment.group']
        if use_fuzzy_match:
            for candidate in candidates:
                if self._normalize_op_number_prefix(candidate.communication) == op_number_core:
                    existing_op = candidate
                    break
        else:
            existing_op = candidates[:1]

        if existing_op:
            errors.append(f"Ya existe un recibo de pago con el número {op_number} (ID {existing_op.id}) .")
            if log_item:
                log_item.write({'message': "\n".join(errors), 'op_exists': True})
            return None, errors

        # Si no existe, asegurar que op_exists sea False
        if log_item:
            log_item.op_exists = False
        
        return op_number, errors

    def _validate_required_fields(self, data, required_fields):
        missing = []
        for field in required_fields:
            value = data.get(field) if isinstance(data, dict) else getattr(data, field, None)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(field)
        return missing

    def _get_datareader_error_policy(self, error_code):
        """Devuelve la política de revisión para el código de error recibido."""
        if error_code in (None, False, ''):
            return self.env['datareader.error.code']

        code = str(error_code).strip()
        return self.env['datareader.error.code'].sudo().search([
            ('code', '=', code)
        ], limit=1)

    def _datareader_invoices_settled(self, lines):
        """
        Confirma contra Odoo que TODAS las facturas informadas en el JSON están
        publicadas y sin saldo pendiente.
        """
        if not lines:
            return False

        for line in lines:
            raw_odoo_id = line.get('odoo_id')
            if raw_odoo_id in (None, False, '', 'na', 'NA', 'null', 'None'):
                return False
            try:
                odoo_id = int(float(str(raw_odoo_id).strip()))
            except (TypeError, ValueError):
                return False

            invoice = self.env['account.move'].sudo().browse(odoo_id).exists()
            if not invoice or invoice.state != 'posted':
                return False
            if abs(invoice.amount_residual or 0.0) >= 0.01:
                return False

        return True

    def _create_log_item(self, file_name, order_id=None, error_code=None):
        vals = {
            'log_id': self.id,
            'file_name': file_name or 'No hay archivo relacionado',
            'error_code': str(error_code).strip() or "0",
        }
        if order_id:
            vals['order_id'] = str(order_id)
        return self.env['datareader.account.payment.group.log.item'].create(vals)

    def _get_company(self, company_name, errors):
        company, errors = cuit_alias.find_record_by_cuit_or_name(
            self.env, 'res.company', name=company_name, errors=errors
        )
        if not company:
            errors.append(f"No se encontró compañía '{company_name}', se detiene el proceso.")
        return company, errors

    def _get_partner(self, cuit, name, errors, journal_id=None, client_id=None):
        if client_id:
            normalized_client_id = client_id
            try:
                normalized_client_id = int(str(client_id).strip())
            except (TypeError, ValueError):
                normalized_client_id = client_id

            partner = self.env["res.partner"].with_context(active_test=False).sudo().browse(normalized_client_id)
            if partner.exists():
                return partner, errors
            else:
                errors.append(f"No se encontró cliente con ID {client_id}. Se intentará buscar por CUIT o nombre.")
        partner, errors = cuit_alias.find_record_by_cuit_or_name(
            self.env, 'res.partner', cuit=cuit, name=name, journal_id=journal_id, errors=errors
        )
        return partner, errors

    def _get_journal(self, journal_name, errors):
        journal, errors = cuit_alias.find_record_by_cuit_or_name(
            self.env, 'account.journal', name=journal_name, errors=errors
        )
        return journal, errors
    
    def _parse_payment_date(self, date_str, errors):
        """
        Convierte un string a fecha en formato Odoo (YYYY-MM-DD).
        Si la fecha es inválida o no viene, usa la fecha de hoy.
        """
        if date_str and str(date_str).lower() != 'na':
            try:
                payment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                errors.append(f"Fecha malformada '{date_str}', se usará fecha de hoy.")
                payment_date = datetime.today().date()
        else:
            payment_date = datetime.today().date()

        return fields.Date.to_string(payment_date), errors
    
    def _get_receiptbook(self, company, errors, log_item=None):
        """
        Busca el receiptbook de la compañía. 
        Primero intenta con el automático, si no lo encuentra busca cualquiera.
        """
        receiptbook = self.env['account.payment.receiptbook'].sudo().search([
            ('is_automatic_receiptbook', '=', True),
            ('company_id', '=', company.id),
            ('partner_type', '=', 'customer')
        ], limit=1)

        if not receiptbook:
            errors.append(f"No se encontró receiptbook automático para la compañía '{company.name}'.")
            receiptbook = self.env['account.payment.receiptbook'].sudo().search([
                ('company_id', '=', company.id),
                ('partner_type', '=', 'customer')
            ], limit=1)

            if not receiptbook:
                errors.append(f"No se encontró ningún receiptbook para la compañía '{company.name}'.")
                if log_item:
                    log_item.write({'message': "\n".join(errors)})
                return None, errors

        return receiptbook, errors
    
    def _get_default_withholding_journal(self, data, partner, company, journal_name, errors, log_item=None):
        """
        Busca un diario por defecto en el partner y, si no lo encuentra, en la compañía.
        Usa la moneda para decidir cuál diario corresponde.
        Si no encuentra ninguno, devuelve None y acumula errores.
        """
        journal = partner.with_company(company).datareader_default_partner_withholding_journal_id or False
        if not journal:
            errors.append(f"No se encontró diario predeterminado para retenciones en el contacto '{partner.name}' para la compañía '{company.name}'.")
            if log_item:
                log_item.write({'message': "\n".join(errors)})
            journal = company.datareader_default_withholding_journal_id or False
            if not journal:
                errors.append("Tampoco se encontró diario predeterminado para retenciones en las configuraciones de la compañia.")
                if log_item:
                    log_item.write({'message': "\n".join(errors)})
                    return None, errors

        return journal, errors

    def _get_withholding_tax(self, search_domain, company, errors, tax_id=None):
        """
        Obtiene un impuesto de retención válido para la compañía indicada.

        Prioriza el `tax_id` (si viene) y valida que pertenezca a la misma
        compañía. Si no es válido, intenta resolver por dominio de búsqueda
        sumando filtros de compañía y activo.

        :param search_domain: dominio base para buscar impuesto
        :param company: res.company destino
        :param errors: lista mutable de errores
        :param tax_id: ID opcional del impuesto proveniente de DataReader
        :return: account.tax (0..1 registro)
        """
        withholding_tax = False
        normalized_tax_id = False

        if tax_id not in ("na", "NA", None, False, "", "null", "None"):
            try:
                normalized_tax_id = int(float(str(tax_id).strip()))
            except (TypeError, ValueError):
                normalized_tax_id = False

        if normalized_tax_id:
            tax_candidate = self.env['account.tax'].sudo().browse(normalized_tax_id).exists()
            if tax_candidate:
                if tax_candidate.company_id.id == company.id:
                    return tax_candidate
                errors.append(
                    _(
                        "El impuesto de retención con ID %s pertenece a la compañía '%s' "
                        "y no a '%s'."
                    )
                    % (normalized_tax_id, tax_candidate.company_id.name, company.name)
                )

        final_domain = list(search_domain or []) + [
            ('company_id', '=', company.id),
            ('active', '=', True),
        ]
        withholding_tax = self.env['account.tax'].sudo().search(final_domain, limit=1)
        return withholding_tax
                
    def _get_default_journal(self, data, partner, company, journal_name, errors, log_item=None):
        """
        Busca un diario por defecto en el partner y, si no lo encuentra, en la compañía.
        Usa la moneda para decidir cuál diario corresponde.
        Si no encuentra ninguno, devuelve None y acumula errores.
        """
        currency = data.get('currency')
        journal= False
        pay_method = data.get('pay_method').lower()
        if pay_method == 'cheque':
            journal = partner.with_company(company).datareader_default_partner_check_journal_id or False
            if not journal:
                errors.append(f"No se encontró diario Predeterminado para cheques en el contacto '{partner.name}' para la compañía '{company.name}'.")
                if log_item:
                    log_item.write({'message': "\n".join(errors)})
                journal = company.datareader_default_check_journal_id or False
        elif currency == 'ARS':
            journal = partner.with_company(company).datareader_default_partner_transfer_journal_id or False
            if not journal:
                errors.append(f"No se encontró diario Predeterminado (Pesos) en el contacto '{partner.name}' para la compañía '{company.name}'.")
                if log_item:
                    log_item.write({'message': "\n".join(errors)})
                journal = company.datareader_default_transfer_journal_id or False
        elif currency == 'USD':
            journal = partner.with_company(company).datareader_default_partner_transfer_usd_journal_id or False
            if not journal:
                errors.append(f"No se encontró diario Predeterminado (Dólares) en el contacto '{partner.name}' para la compañía '{company.name}'.")
                if log_item:
                    log_item.write({'message': "\n".join(errors)})
                journal = company.datareader_default_transfer_usd_journal_id or False
        else:
            errors.append("No se encontró tipo de moneda en DataReader.")
            if log_item:
                log_item.write({'message': "\n".join(errors)})
                return None, errors

        if not journal:
            errors.append(f"No se encontró ningún diario predeterminado ({pay_method}) en el contacto ni en compañía, ({partner.name}, {company.name}), se detiene el proceso.")
            if log_item:
                log_item.write({'message': "\n".join(errors)})
            return None, errors

        return journal, errors

    def _get_bank_reconciliation_payment_line(self, payment_group, partner_id, company_id, amount, payment_date=None, force_create=False):
        """
        Devuelve una línea de pago (account.payment) como la normal pero usando el diario
        de conciliación bancaria, si existe una línea de pago bancario en plan de cuentas
        en los últimos X días (configurable en ir.config_parameter), para el mismo partner,
        y la diferencia (crédito - débito) es igual o mayor al monto indicado (ej. nota de
        débito dentro del pago). Más tarde se ajusta la lógica de comparación.

        :param payment_group: account.payment.group
        :param partner_id: res.partner
        :param company_id: res.company
        :param amount: float - monto a comparar (ej. importe de nota de débito en el pago)
        :param payment_date: str (YYYY-MM-DD) o date - fecha del pago (default: hoy)
        :param force_create: bool - si True, crea la línea sin comprobar balance (cuando ya hubo match con factura)
        :return: account.payment o recordset vacío
        """
        if not amount or amount <= 0:
            return self.env['account.payment']

        ir_config = self.env['ir.config_parameter'].sudo()
        lookback_days = int(ir_config.get_param('datareader_odoo.bank_reconciliation_lookback_days', '30') or '30')
        reconciliation_account = company_id.datareader_bank_reconciliation_account_id
        reconciliation_journal = company_id.datareader_bank_reconciliation_journal_id

        if not reconciliation_account or not reconciliation_journal:
            _logger.debug("Conciliación bancaria: falta cuenta o diario configurado en la compañía.")
            return self.env['account.payment']

        payment_date = payment_date or fields.Date.today()
        if isinstance(payment_date, str):
            payment_dt = datetime.strptime(payment_date, '%Y-%m-%d').date()
        else:
            payment_dt = payment_date
        date_from = payment_dt - timedelta(days=lookback_days)
        date_from_str = date_from.strftime('%Y-%m-%d')
        payment_date_str = payment_dt.strftime('%Y-%m-%d') if hasattr(payment_dt, 'strftime') else str(payment_date)

        if not force_create:
            commercial_partner_id = partner_id.commercial_partner_id.id
            domain = [
                ('account_id', '=', reconciliation_account.id),
                ('partner_id', '=', commercial_partner_id),
                ('move_id.state', '=', 'posted'),
                ('date', '>=', date_from_str),
                ('date', '<=', payment_date_str),
                ('company_id', '=', company_id.id),
            ]
            bank_lines = self.env['account.move.line'].sudo().search(domain)
            balance = sum((l.credit or 0.0) - (l.debit or 0.0) for l in bank_lines)

            if balance < amount:
                _logger.debug(
                    "Conciliación bancaria: balance (%.2f) menor que monto (%.2f), no se crea línea con diario conciliación.",
                    balance, amount
                )
                return self.env['account.payment']

        payment_method = self.env['account.payment.method'].sudo().search([
            ('code', '=', 'manual'),
            ('payment_type', '=', 'inbound'),
        ], limit=1)
        if not payment_method:
            _logger.warning("Conciliación bancaria: no se encontró método de pago manual inbound.")
            return self.env['account.payment']

        payment_method_line = self.env['account.payment.method.line'].sudo().search([
            ('payment_method_id', '=', payment_method.id),
            ('journal_id', '=', reconciliation_journal.id),
        ], limit=1)
        if not payment_method_line:
            _logger.warning(
                "Conciliación bancaria: el diario %s no tiene método manual inbound.",
                reconciliation_journal.display_name
            )
            return self.env['account.payment']

        payment_vals = {
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': partner_id.id,
            'amount': amount,
            'date': payment_date_str,
            'journal_id': reconciliation_journal.id,
            'payment_method_line_id': payment_method_line.id,
            'company_id': company_id.id,
            'currency_id': company_id.currency_id.id,
            'state': 'draft',
            'payment_group_id': payment_group.id,
        }
        payment_line = self.env['account.payment'].sudo().create(payment_vals)
        _logger.info(
            "Conciliación bancaria: creada línea de pago %s (diario %s) para payment_group %s, monto %.2f.",
            payment_line.id, reconciliation_journal.name, payment_group.id, amount
        )
        return payment_line

    def _get_bank_line_amount_matching_invoice(self, debt_lines, total_payment_line, log_item=None, company_id=None, commercial_partner_id=None):
        """
        Busca apuntes contables en el diario y cuenta de conciliación del partner.
        Si existe una línea bancaria no conciliada y su monto coincide con el total
        de alguna factura en las líneas a pagar, devuelve ese monto para restarlo
        de la línea de pago y crear una línea en el diario de conciliación.

        Si hay línea(s) bancaria(s) pero ningún monto coincide con una factura,
        escribe en log_item el mensaje de detalle/error y devuelve None.

        :param debt_lines: account.move.line recordset - Líneas a pagar (ej. to_pay_move_line_ids)
        :param log_item: datareader.account.payment.group.log.item opcional
        :return: float o None - Monto que coincide con una factura, o None
        """
        total_payment = total_payment_line.amount if total_payment_line else 0.0

        company = company_id if company_id else None
        commercial_partner_id = commercial_partner_id if commercial_partner_id else None
        reconciliation_account = company.datareader_bank_reconciliation_account_id
        reconciliation_journal = company.datareader_bank_reconciliation_journal_id
        if not reconciliation_account or not reconciliation_journal:
            _logger.debug("_get_bank_line_amount_matching_invoice: sin cuenta o diario de conciliación configurado.")
            return None

        ir_config = self.env['ir.config_parameter'].sudo()
        lookback_days = int(ir_config.get_param('datareader_odoo.bank_reconciliation_lookback_days', '30') or '30')
        date_to_str = fields.Date.today()
        if isinstance(date_to_str, str):
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        else:
            date_to = date_to_str
            date_to_str = date_to.strftime('%Y-%m-%d') if hasattr(date_to, 'strftime') else str(date_to)
        date_from = date_to - timedelta(days=lookback_days)
        date_from_str = date_from.strftime('%Y-%m-%d')

        domain_bank = [
            ('account_id', '=', reconciliation_account.id),
            #('journal_id', '=', reconciliation_journal.id),
            ('partner_id', '=', commercial_partner_id),
            ('move_id.state', '=', 'posted'),
            ('date', '>=', date_from_str),
            ('date', '<=', date_to_str),
            ('company_id', '=', company.id),
            ('reconciled', '=', False),
        ]
        bank_lines = self.env['account.move.line'].sudo().search(domain_bank)
        if not bank_lines:
            _logger.debug("_get_bank_line_amount_matching_invoice: no hay líneas bancarias no conciliadas en el período.")
            return None
        bank_lines = list(bank_lines)

        # Montos de facturas a pagar (por move_id) - amount_total redondeado a 2 decimales
        if debt_lines:
            moves = debt_lines.mapped('move_id')
            moves = list(moves) if moves else []
            invoice_totals = {round(m.amount_total, 2) for m in moves}
        else:
            invoice_totals = {round(total_payment, 2)}

        for aml in bank_lines:
            # Usar débito/crédito en lugar de balance (compatible Odoo 15)
            balance = (aml.debit or 0.0) - (aml.credit or 0.0)
            line_amount = round(abs(balance), 2)
            if line_amount <= 0:
                continue
            if line_amount in invoice_totals or line_amount == total_payment:
                _logger.info(
                    "_get_bank_line_amount_matching_invoice: monto %.2f coincide con factura (partner %s).",
                    line_amount, commercial_partner_id
                )
                # Devolver el monto de la factura que hizo match (mismo valor, desde factura)
                return line_amount

        # Hay líneas bancarias pero ningún monto coincide con una factura
        _logger.info(
            "_get_bank_line_amount_matching_invoice: hay línea(s) bancaria(s) pero ningún monto coincide con factura (partner %s).",
            commercial_partner_id
        )
        if log_item:
            msg = _("Existió un pago antes del cierre de mes para conciliar pero que el monto no corresponde.")
            current = (log_item.message or "").strip()
            log_item.write({'message': f"{current}\n{msg}".strip() if current else msg})
        return None

    def create_from_datareader_json(self, data, connector, log_item=None):
        """
        Crea un recibo (account.payment.group) y sus líneas de pago (account.payment)
        desde un JSON proveniente de DataReader.
        
        :param data: Datos JSON de la orden de pago
        :param connector: Conector DataReader
        :param log_item: Log item opcional. Si se proporciona, se usa este en lugar de crear uno nuevo.
        """
        ir_config = self.env['ir.config_parameter'].sudo()
        # ver si se utiliza
        ap_post = eval(ir_config.get_param("datareader_odoo.datareader_post_account_payment", 'False'))
        apg_post = eval(ir_config.get_param("datareader_odoo.datareader_post_account_payment_group", 'False'))
        post_when_missing_invoice = ir_config.get_param(
            "datareader_odoo.post_when_missing_invoice", 'no'
        )
        
        file_name = data.get("file_name")
        order_id = data.get("id")
        raw_error_code = data.get('error_code')
        error_code = str(raw_error_code).strip() or "0"
        if not log_item:
            log_item = self._create_log_item(file_name, order_id, error_code=error_code)
        else:
            log_item.write({'error_code': error_code or False})
        errors = []

        error_policy = self._get_datareader_error_policy(error_code)
        requires_review = bool(error_policy and error_policy.requires_review)
        review_reason = False
        if requires_review:
            review_reason = _(
                "Recibo en borrador por revisión obligatoria de IA. "
                "Código %s: %s"
            ) % (
                str(error_code).strip(),
                error_policy.description or _('Sin descripción del código.'),
            )

        # Códigos que no deben generar recibo (ej. facturas ya pagadas sin deuda).
        # Se corta antes de crear el grupo de pagos, pero solo si Odoo confirma la
        # condición: si alguna factura todavía tiene deuda, sigue el flujo normal.
        if error_policy and error_policy.skip_receipt:
            if self._datareader_invoices_settled(data.get('lines') or []):
                skip_reason = _(
                    "No se genera recibo por código %s: %s"
                ) % (
                    str(error_code).strip(),
                    error_policy.description or _('Sin descripción del código.'),
                )
                errors.append(skip_reason)
                log_item.write({'message': "\n".join(errors), 'readed': True})
                connector.set_payment_order_readed(data.get("id"), True)
                _logger.info(
                    "Orden %s sin recibo por código de error %s (skip_receipt).",
                    order_id, error_code,
                )
                return log_item

            not_settled_msg = _(
                "El código %s indica facturas ya pagadas, pero en Odoo no todas están "
                "sin deuda. El recibo se procesa normalmente."
            ) % str(error_code).strip()
            errors.append(not_settled_msg)
            _logger.info(
                "Orden %s con código %s pero con facturas pendientes en Odoo - se procesa normalmente.",
                order_id, error_code,
            )

        op_number, errors = self._validate_op_number(data, errors, log_item)
        if not op_number:
            connector.set_payment_order_readed(data.get("id"), True)
            log_item.readed = True
            return log_item

        company_name = data['society']
        company_id, errors = self._get_company(company_name, errors)
        if not company_id:
            log_item.write({'message': "\n".join(errors)})
            return log_item
        elif len(company_id) > 1:
            return log_item
        
        partner_cuit = data.get('client_cuit')
        partner_name = data.get('client_name')
        
        # Intentar obtener el journal primero para usarlo en la búsqueda del partner
        journal_name = data.get('journal')
        journal_id_preliminar = None
        if journal_name:
            journal_id_preliminar, _j_errors = self._get_journal(journal_name, [])
            # Si hay múltiples journals, no usar para priorización
            if journal_id_preliminar and not isinstance(journal_id_preliminar, list):
                journal_id_preliminar = journal_id_preliminar if hasattr(journal_id_preliminar, 'id') else None
        
        partner_id, errors = self._get_partner(partner_cuit, partner_name, errors, journal_id=journal_id_preliminar, client_id=data.get("client_id"))
        if not partner_id:
            log_item.write({'message': "\n".join(errors)})
            return log_item
        elif hasattr(partner_id, '__len__') and len(partner_id) > 1:
            log_item.write({'message': "\n".join(errors)})
            return log_item

        # Obtener el journal definitivo (puede ser el mismo o uno por defecto)
        journal_id, errors = self._get_journal(journal_name, errors)

        if not journal_id:
            journal_id, errors = self._get_default_journal(data, partner_id, company_id, journal_name, errors, log_item)
            if not journal_id:
                return log_item
        elif len(journal_id) > 1:
            return log_item

        if data.get('retentions'):
            log_item.has_withholding = True
            payment_method_withholding = self.env.ref(
                'account_withholding.account_payment_method_in_withholding', raise_if_not_found=False
            )
            if not payment_method_withholding:
                errors.append("No se encontró el método de pago para retenciones, se detiene el proceso.")
                log_item.write({'message': "\n".join(errors)})
                return log_item
            
            ret_journal_id, errors = self._get_default_withholding_journal(data, partner_id, company_id, journal_name, errors, log_item)

            if not ret_journal_id:
                return log_item
            payment_method_withholding_line = self.env['account.payment.method.line'].sudo().search([
                ('payment_method_id', '=', payment_method_withholding.id),
                ('journal_id', '=', ret_journal_id.id),
            ], limit=1)

            if not payment_method_withholding_line:
                errors.append(
                    f"El diario '{ret_journal_id.display_name}' "
                    f"no tiene línea para el método de pago de retenciones."
                )
                log_item.write({'message': "\n".join(errors)})
                return log_item

        payment_date_str, errors = self._parse_payment_date(data.get('date'), errors)

        receiptbook_id, errors = self._get_receiptbook(company_id, errors, log_item)
        if not receiptbook_id:
            return log_item
        
        post_neto = False

        bruto = float(data.get('amount_bruto') or 0.0)
        neto = float(data.get('amount_neto') or 0.0)

        # Regla:
        # - Si no hay bruto (>0), usar neto.
        # - Si hay bruto (>0) pero el neto es MAYOR, usar el neto (caso donde el bruto viene mal informado).
        # - En el resto de casos, usar el bruto.
        if bruto <= 0.0:
            amount = neto
            errors.append(f"No vino monto bruto. Se toma el monto neto ({neto}).")
            log_item.write({'message': "\n".join(errors)})
        elif neto > bruto:
            amount = neto
            errors.append(f"El monto neto ({neto}) es mayor que el bruto ({bruto}). Se toma el neto.")
            log_item.write({'message': "\n".join(errors)})
        else:
            amount = bruto

        if amount <= 0.0:
            errors.append(f"El monto calculado (bruto/neto) es 0 o negativo. Se detiene el proceso.")
            log_item.write({'message': "\n".join(errors)})
            return log_item
            
        # Método de pago base
        pay_method = data.get('pay_method').lower()
        payment_method_obj = self.env['account.payment.method'].sudo()
        payment_method = payment_method_obj.search([
            ('code', '=', 'new_third_party_checks' if pay_method == 'cheque' else 'manual'),
            ('payment_type', '=', 'inbound')
        ], limit=1)
        if not payment_method:
            errors.append(f"No hay método de pago {'Cheque' if pay_method == 'cheque' else 'Manual'} para la compañia {company_id.name}."
            )
            log_item.write({'message': "\n".join(errors)})
            return log_item
            
        payment_method_line = self.env['account.payment.method.line'].sudo().search([
            ('payment_method_id', '=', payment_method.id),
            ('journal_id', '=', journal_id.id),
        ], limit=1)

        if not payment_method_line:
            errors.append(
                f"El diario '{journal_id.display_name}' "
                f"no tiene línea configurada para el método de pago '{payment_method.name}'."
            )
            log_item.write({'message': "\n".join(errors)})
            return log_item
        
        vals = {
            'partner_id': partner_id.id,
            'commercial_partner_id': partner_id.commercial_partner_id.id,
            'company_id': company_id.id,
            'payment_date': fields.Date.today(),
            'receiptbook_id': receiptbook_id.id,
            'state': 'draft',
            'partner_type': 'customer',
            'communication': op_number,
            'is_datareader_op': True,
            'datareader_op_date': payment_date_str,
        }

        payment_group = self.env['account.payment.group'].sudo().create(vals)

        self.env.cr.flush()
        log_item.payment_group_id = payment_group

        if review_reason:
            errors.append(review_reason)
        
        json_lines = data.get('lines', [])
        missing_found = False
        paid_invoice_found = False
        partial_invoice_found = False
        missing_invoice_numbers = []
        missing_invoice_ids = []
        
        if not json_lines:
            errors.append("No se encontraron líneas en el JSON.")
            log_item.write({'message': "\n".join(errors)})
        else:
            (
                missing_found,
                paid_invoice_found,
                partial_invoice_found,
                matched_invoice_count,
                missing_invoice_numbers,
                missing_invoice_ids,
            ) = self._find_and_attach_invoices(
                payment_group, json_lines, errors=errors
            )
        
        """ if invoice_found:
            log_item.write({
                'invoices_found': True
            }) """
            
        log_item.write({
            'message': "\n".join(errors)
        })
        
        # Crear el pago con el monto original del JSON (sin ajustar)
        payment_vals = {
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': partner_id.id,
            'amount': amount,  # Usar el monto original del JSON
            'date': fields.Date.today(),
            'journal_id': journal_id.id,
            'payment_method_line_id': payment_method_line.id if payment_method_line else False,
            'company_id': company_id.id,
            'currency_id': company_id.currency_id.id,
            'state': 'draft',
            'payment_group_id': payment_group.id,
        }
        
        if pay_method == 'cheque' and data.get('nro_cheque'):
            log_item.has_check = True
            payment_vals['check_number'] = data['nro_cheque']

        total_payment_line = self.env['account.payment'].sudo().create(payment_vals)
        
        # Verificar si hay tolerancia aplicable antes de postear
        # Si hay tolerancia y publicación automática, no postear el pago individual
        # porque se publicará el payment_group completo después de aplicar tolerancia
        should_post_individual_payment = ap_post and not requires_review
        if partner_id.datareader_auto_payment_post and pay_method != 'cheque':
            tolerance_enabled = company_id.datareader_tolerance_enabled
            if tolerance_enabled:
                # Calcular diferencia para ver si está dentro de tolerancia
                # Usar la diferencia calculada por payment_group para contemplar
                # correctamente ajustes internos (ej. diferencias del propio grupo).
                payment_difference = payment_group.payment_difference
                tolerance_amount = company_id.datareader_tolerance_amount or 0.0
                tolerance_account = company_id.datareader_tolerance_account_id
                
                # Si está dentro de tolerancia, no postear individualmente
                if (tolerance_amount > 0.0 and 
                    abs(payment_difference) <= tolerance_amount and
                    tolerance_account):
                    should_post_individual_payment = False

        if should_post_individual_payment and total_payment_line:
            total_payment_line.action_post()            

        withholdings = data.get('retentions', [])
        
        if total_payment_line and withholdings:
            total_retentions = sum(float(w.get('amount') or 0.0) for w in withholdings)
            if total_payment_line.amount < total_retentions:
                errors.append(
                    _(
                        "El monto bruto de la orden (%s) es menor al total de retenciones (%s). "
                        "No se crean pagos de retención ni se descuenta del pago principal."
                    )
                    % (total_payment_line.amount, total_retentions)
                )
                log_item.write({'message': "\n".join(errors)})
                return log_item
        
        for withholding in withholdings:
            ret_account_payment_obj = self.env['account.payment'].sudo()
            ret_amount = float(withholding.get('amount') or 0.0)
            ret_number = withholding.get('number') or False
            ret_id = withholding.get('odoo_id', "na") or "na"
            ret_name = withholding.get('name') or False
            if not ret_number or str(ret_number).lower() == 'na':
                ret_number = 'N/A'
                
            if not ret_amount:
                continue

            # Impuesto de retención con validación de compañía.
            withholding_tax = self._get_withholding_tax(
                [
                    ('type_tax_use', 'ilike', 'customer'),
                    ('datareader_custom_identifier', '=', ret_name),
                ],
                company_id,
                errors,
                tax_id=ret_id,
            )

            # Si no existe impuesto, registra error y corta el proceso ya que es requerido
            if not withholding_tax.exists():
                errors.append(f"No se encontró el impuesto de Retención para {ret_name}, puede que se deba configurar el campo datareader_custom_identifier")
                log_item.write({'message': "\n".join(errors)})
                return log_item

            ret_payment_vals = {
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': partner_id.id,
                'amount': ret_amount,
                'date': fields.Date.today(),
                'journal_id': ret_journal_id.id,
                'payment_method_line_id': payment_method_withholding_line.id,
                'company_id': company_id.id,
                'currency_id': company_id.currency_id.id,
                'tax_withholding_id': withholding_tax.id,
                'withholding_number': ret_number,
                'payment_group_id': payment_group.id,
            }

            if total_payment_line:
                # Evitar que la línea de pago principal quede en negativo por restar retenciones
                new_amount = (total_payment_line.amount or 0.0) - ret_amount
                if new_amount < 0:
                    errors.append(
                        _(
                            "La retención (%s) dejaría el pago principal en negativo "
                            "(monto actual %s, retención %s). "
                            "Revise los montos de bruto y retenciones en la orden."
                        )
                        % (ret_name or ret_number, total_payment_line.amount, ret_amount)
                    )
                    log_item.write({'message': "\n".join(errors)})
                    return log_item
                total_payment_line.amount = new_amount
            missings = self._validate_required_fields(
                ret_payment_vals,
                ['partner_id', 'amount', 'date', 'journal_id', 'payment_method_line_id', 'tax_withholding_id', 'withholding_number']
            )
            if not missings:
                ret_account_payment = ret_account_payment_obj.create(ret_payment_vals)
                log_item.write({'message': "\n".join(errors)})
            else:
                errors.append(f"Faltan campos obligatorios para la retención: {', '.join(missings)}")
                log_item.write({'message': "\n".join(errors)})
                return log_item
            
        # Lógica de publicación automática con tolerancia
        _logger.info(f"=== INICIO PROCESO TOLERANCIA - Payment Group {payment_group.id} ===")
        _logger.info(f"partner_id.datareader_auto_payment_post: {partner_id.datareader_auto_payment_post}")
        _logger.info(f"pay_method: {pay_method}")
        
        # Conciliación bancaria (antes del post): crear línea con diario de ajustes y descontar de la línea principal
        had_reconciliation_match = False
        reconciliation_payment_created = None
        reconciliation_matched_amount = None
        
        matched_amount = self._get_bank_line_amount_matching_invoice(
            payment_group.to_pay_move_line_ids, total_payment_line, log_item=log_item, company_id=company_id, commercial_partner_id=partner_id.id
        )
        if matched_amount is not None and matched_amount > 0:
            main_payment = payment_group.payment_ids.filtered(lambda p: not p.tax_withholding_id)[:1]
            if main_payment and main_payment.amount >= matched_amount:
                reconciliation_payment_created = self._get_bank_reconciliation_payment_line(
                    payment_group, partner_id, company_id, matched_amount, payment_date_str, force_create=True
                )
                reconciliation_matched_amount = matched_amount
                main_payment.amount -= matched_amount
                if main_payment.amount == 0:
                    main_payment.unlink()
                had_reconciliation_match = True
                # Buscar la línea del apunte con débito = monto del match y poner account_id de la conf
                reconciliation_account = company_id.datareader_bank_reconciliation_account_id
                if reconciliation_payment_created and reconciliation_matched_amount and reconciliation_account:
                    move = reconciliation_payment_created.move_id
                    if move and move.line_ids:
                        for line in move.line_ids:
                            if line.debit and abs((line.debit or 0) - reconciliation_matched_amount) < 0.01:
                                line.sudo().write({'account_id': reconciliation_account.id})
                                _logger.info(
                                    "Conciliación: línea con débito %.2f actualizada a cuenta %s.",
                                    reconciliation_matched_amount, reconciliation_account.code
                                )
                                break
                if log_item:
                    msg = _("Se concilió un pago anterior al cierre de mes por %s.") % matched_amount
                    current = (log_item.message or "").strip()
                    log_item.write({'message': f"{current}\n{msg}".strip() if current else msg})
            elif main_payment and log_item:
                msg = _("Existió un pago antes del cierre de mes para conciliar pero que el monto no corresponde.")
                current = (log_item.message or "").strip()
                log_item.write({'message': f"{current}\n{msg}".strip() if current else msg})
        
        if post_neto == True:
            return log_item
        
        elif partner_id.datareader_auto_payment_post and pay_method != 'cheque':
            amount_from_json = amount
            invoices = payment_group.to_pay_move_line_ids.mapped('move_id')
            total_debt = sum(invoices.mapped('amount_total'))
            payment_difference = payment_group.payment_difference
            company = company_id
            
            tolerance_enabled = company.datareader_tolerance_enabled
            tolerance_amount = company.datareader_tolerance_amount or 0.0
            tolerance_account = company.datareader_tolerance_account_id
            # Diferencia distinta de cero pero cubierta por la tolerancia: corresponde nota de
            # crédito/débito, haya habido conciliación bancaria o no.
            needs_note = bool(
                abs(payment_difference) != 0.0
                and tolerance_enabled
                and tolerance_amount > 0.0
                and abs(payment_difference) <= tolerance_amount
                and tolerance_account
            )

            _logger.info(f"amount_from_json (del JSON): {amount_from_json}")
            _logger.info(f"total_debt (deuda original): {total_debt}")
            _logger.info(f"payment_difference: {payment_difference}")
            _logger.info(f"needs_note: {needs_note}")

            # Si hubo match de conciliación y la tolerancia no cubre la diferencia:
            # no aplicar lógica de tolerancia; solo postear si diferencia = 0
            if had_reconciliation_match and not needs_note:
                if abs(payment_difference) == 0.0:
                    _logger.info(f"Hubo conciliación bancaria y diferencia = 0 - publicando.")
                    try:
                        if not requires_review:
                            payment_group.post()
                        else:
                            _logger.info(
                                "Payment group %s no se publica por revisión obligatoria (error_code=%s).",
                                payment_group.id,
                                error_code,
                            )
                        if log_item:
                            if not requires_review:
                                log_item.readed = True
                                _logger.info(f"Payment group {payment_group.id} publicado exitosamente. Marcado como leído.")
                    except Exception as e:
                        _logger.exception(f"Error al postear payment group {payment_group.id} tras conciliación: {e}")
                else:
                    _logger.info(f"Hubo conciliación pero diferencia != 0 ({payment_difference}) - no se publica.")
                    residual_amount = sum(payment_group.to_pay_move_line_ids.mapped('amount_residual'))
                    diff_msg = _(
                        "El recibo no se publicó porque existe diferencia entre el pago y el monto residual de la deuda. "
                        "Monto pago: %s | Residual deuda: %s | Diferencia: %s."
                    ) % (amount_from_json, residual_amount, payment_difference)
                    errors.append(diff_msg)
                    if log_item:
                        current = (log_item.message or "").strip()
                        log_item.write({'message': f"{current}\n{diff_msg}".strip() if current else diff_msg})
            else:
                # Lógica normal de tolerancia
                _logger.info(f"tolerance_enabled: {tolerance_enabled}")
                _logger.info(f"tolerance_amount: {tolerance_amount}")
                _logger.info(f"tolerance_account: {tolerance_account.name if tolerance_account else 'None'}")
                _logger.info(f"abs(payment_difference): {abs(payment_difference)}")
                _logger.info(f"abs(payment_difference) <= tolerance_amount: {abs(payment_difference) <= tolerance_amount if tolerance_amount > 0 else False}")
                
                # Si no hay diferencia, publicar normalmente (solo si cumple condiciones de retenciones)
                if abs(payment_difference) == 0.0:
                    _logger.info(f"Sin diferencia - publicando normalmente")
                    if self._should_post_payment_group(log_item):
                        if not requires_review:
                            payment_group.post()
                        else:
                            _logger.info(
                                "Payment group %s no se publica por revisión obligatoria (error_code=%s).",
                                payment_group.id,
                                error_code,
                            )
                        # Marcar como leído cuando el recibo se haya publicado exitosamente
                        if log_item:
                            if not requires_review:
                                log_item.readed = True
                                _logger.info(f"Payment group {payment_group.id} publicado exitosamente. Marcado como leído.")
                    else:
                        _logger.info(f"Payment group {payment_group.id} no publicado: condiciones de retenciones no cumplidas")
                # Si hay diferencia dentro del margen de tolerancia
                elif (tolerance_enabled and 
                      tolerance_amount > 0.0 and 
                      abs(payment_difference) <= tolerance_amount and
                      tolerance_account):
                    _logger.info(f"=== DIFERENCIA DENTRO DE TOLERANCIA - Creando nota ===")
                    
                    # Calcular el monto total que deben cubrir las facturas
                    matched_amount = sum(payment_group.to_pay_move_line_ids.mapped('amount_residual'))
                    
                    # Obtener el pago principal para usar su diario y método de pago
                    main_payment = payment_group.payment_ids.filtered(lambda p: p.state == 'draft')
                    if not main_payment:
                        main_payment = payment_group.payment_ids[0] if payment_group.payment_ids else None
                    
                    if not main_payment:
                        _logger.error(f"No se encontró pago en el payment_group {payment_group.id}")
                        return log_item
                    
                    # Si la diferencia es positiva (pago menor), crear nota de crédito
                    credit_note_created = False
                    if payment_difference > 0:
                        _logger.info(f"Pago menor detectado. Diferencia: {payment_difference}. Creando nota de crédito...")
                        # Crear nota de crédito para reducir la deuda por la diferencia
                        credit_note = self._create_credit_note_for_tolerance(
                            payment_group,
                            payment_difference,
                            payment_date_str,
                            company
                        )
                        
                        if credit_note:
                            _logger.info(f"Nota de crédito creada para tolerancia: {credit_note.name}")
                            # Recalcular matched_amount después de agregar la nota de crédito
                            matched_amount = sum(payment_group.to_pay_move_line_ids.mapped('amount_residual'))
                            credit_note_created = True
                        else:
                            _logger.warning(f"No se pudo crear la nota de crédito para tolerancia")
                            return log_item
                    
                    # Si la diferencia es negativa (pago mayor), crear nota de débito por la diferencia
                    elif payment_difference < 0:
                        # Crear nota de débito por la diferencia y agregarla a la deuda
                        debit_note = self._create_invoice_for_tolerance(
                            payment_group,
                            payment_difference,
                            payment_date_str,
                            company
                        )
                        
                        if debit_note:
                            _logger.info(f"Nota de débito creada para tolerancia: {debit_note.name}")
                            # Recalcular matched_amount después de agregar la nota de débito
                            matched_amount = sum(payment_group.to_pay_move_line_ids.mapped('amount_residual'))
                        else:
                            _logger.warning(f"No se pudo crear la nota de débito para tolerancia")
                            return log_item
                    
                    # Misma regla para NC y ND: solo postear si _should_post_payment_group lo permite
                    if self._should_post_payment_group(log_item):
                        note_label = (
                            "Nota de crédito creada"
                            if credit_note_created
                            else "Nota de débito creada"
                        )
                        _logger.info(
                            f"{note_label}. Posteando payment group {payment_group.id} automáticamente..."
                        )
                        if not requires_review:
                            payment_group.post()
                        else:
                            _logger.info(
                                "Payment group %s no se publica por revisión obligatoria (error_code=%s).",
                                payment_group.id,
                                error_code,
                            )
                    else:
                        _logger.info(
                            f"Payment group {payment_group.id} no publicado: "
                            f"condiciones de retenciones no cumplidas"
                        )
                        return log_item
                    
                    # Marcar como leído cuando el recibo se haya publicado exitosamente
                    if log_item:
                        if not requires_review:
                            log_item.readed = True
                            _logger.info(f"Payment group {payment_group.id} publicado exitosamente. Marcado como leído.")
                # Si hay diferencia fuera de tolerancia:
                # - payment_difference > 0 (pagó MENOS, pago parcial genuino): se
                #   publica igual automáticamente, SIN crear nota de crédito.
                # - payment_difference < 0 (pagó de MÁS): sin cambios, queda en draft.
                else:
                    if payment_difference > 0.0:
                        _logger.info(
                            f"Payment group {payment_group.id}: diferencia positiva ({payment_difference}) "
                            f"fuera de tolerancia ({tolerance_amount}) - pago parcial genuino, se publica sin notas."
                        )
                        residual_amount = sum(payment_group.to_pay_move_line_ids.mapped('amount_residual'))
                        partial_msg = _(
                            "El recibo se publicó como pago parcial (queda deuda pendiente) sin generar notas de "
                            "crédito, ya que el monto pagado es menor a la deuda informada. "
                            "Monto pago: %s | Residual deuda: %s | Diferencia: %s."
                        ) % (amount_from_json, residual_amount, payment_difference)
                        errors.append(partial_msg)
                        if log_item:
                            current = (log_item.message or "").strip()
                            log_item.write({'message': f"{current}\n{partial_msg}".strip() if current else partial_msg})

                        if self._should_post_payment_group(log_item):
                            if not requires_review:
                                payment_group.post()
                            else:
                                _logger.info(
                                    "Payment group %s no se publica por revisión obligatoria (error_code=%s).",
                                    payment_group.id,
                                    error_code,
                                )
                            if log_item and not requires_review:
                                log_item.readed = True
                                _logger.info(
                                    f"Payment group {payment_group.id} publicado exitosamente como pago parcial. Marcado como leído."
                                )
                        else:
                            _logger.info(
                                f"Payment group {payment_group.id} no publicado: condiciones de retenciones no cumplidas"
                            )

                    elif payment_difference != 0.0:
                        _logger.info(f"Payment group {payment_group.id} no publicado. Diferencia {payment_difference} fuera de tolerancia ({tolerance_amount})")
                        _logger.info(f"Condiciones: tolerance_enabled={tolerance_enabled}, tolerance_amount={tolerance_amount}, abs_diff={abs(payment_difference)}, tolerance_account={bool(tolerance_account)}")
                        residual_amount = sum(payment_group.to_pay_move_line_ids.mapped('amount_residual'))
                        move_lines = payment_group.to_pay_move_line_ids
                        has_partial_residual = any(
                            (line.amount_residual or 0.0) > 0.0 and
                            (line.amount_residual or 0.0) < (line.move_id.amount_total or 0.0)
                            for line in move_lines
                        )
                        has_withholdings = bool(payment_group.payment_ids.filtered(lambda p: p.tax_withholding_id))
                        if has_partial_residual:
                            diff_msg = _(
                                "El recibo quedó en borrador porque hay facturas con pago parcial en las líneas a pagar "
                                "y los montos no cierran con la OP (puede incluir retenciones). "
                                "Monto pago: %s | Residual deuda: %s | Diferencia: %s."
                            ) % (amount_from_json, residual_amount, payment_difference)
                        elif has_withholdings:
                            diff_msg = _(
                                "Los montos de pago y retenciones no coinciden con la deuda residual informada en la OP. "
                                "Si corresponde publicación por faltante de facturas, el recibo se publicará como pago a cuenta. "
                                "Monto pago: %s | Residual deuda: %s | Diferencia: %s | Tolerancia: %s."
                            ) % (amount_from_json, residual_amount, payment_difference, tolerance_amount)
                        else:
                            diff_msg = _(
                                "El recibo quedó en borrador por diferencia fuera de tolerancia entre pago y residual de deuda. "
                                "Monto pago: %s | Residual deuda: %s | Diferencia: %s | Tolerancia: %s."
                            ) % (amount_from_json, residual_amount, payment_difference, tolerance_amount)
                        errors.append(diff_msg)
                        if log_item:
                            current = (log_item.message or "").strip()
                            log_item.write({'message': f"{current}\n{diff_msg}".strip() if current else diff_msg})
        else:
            _logger.info(f"No se procesa tolerancia: datareader_auto_payment_post={partner_id.datareader_auto_payment_post}, pay_method={pay_method}")

        # Publicar al final por faltante de facturas.
        # Si falta una o más facturas, el recibo se publica como pago a cuenta.
        if (
            missing_found
            and not paid_invoice_found
            and payment_group.state == 'draft'
        ):
            if payment_group:
                listed_numbers = ', '.join(str(n) for n in missing_invoice_numbers) if missing_invoice_numbers else _("sin número informado")
                listed_ids = ', '.join(str(i) for i in missing_invoice_ids) if missing_invoice_ids else _("sin odoo_id informado")
                body_msg = _(
                    "No se identificaron todas las facturas con coincidencia exacta (100%%) para esta orden. "
                    "El recibo se publicó completamente como pago a cuenta del cliente para conciliación posterior. "
                    "Comprobantes informados: %s | IDs Odoo sin coincidencia: %s"
                ) % (listed_numbers, listed_ids)
                if requires_review:
                    body_msg = _(
                        "No se identificaron todas las facturas con coincidencia exacta (100%%) para esta orden. "
                        "El recibo quedó en borrador por revisión obligatoria de IA. "
                        "Comprobantes informados: %s | IDs Odoo sin coincidencia: %s"
                    ) % (listed_numbers, listed_ids)
                payment_group.sudo().message_post(
                    body=body_msg,
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )

            try:
                if not requires_review:
                    payment_group.post()
                else:
                    _logger.info(
                        "Payment group %s no se publica por revisión obligatoria (error_code=%s).",
                        payment_group.id,
                        error_code,
                    )
                if log_item:
                    if not requires_review:
                        log_item.readed = True
                        _logger.info(
                            "Payment group %s publicado como pago a cuenta por faltante de facturas.",
                            payment_group.id,
                        )
                    else:
                        _logger.info(
                            "Payment group %s quedó en borrador por revisión obligatoria.",
                            payment_group.id,
                        )
            except Exception as e:
                _logger.exception(
                    "Error al postear payment group %s por faltante de facturas: %s",
                    payment_group.id, e
                )
        elif (
            missing_found
            and paid_invoice_found
            and payment_group.state == 'draft'
        ):
            if partial_invoice_found:
                partial_paid_msg = _(
                    "Se detectaron facturas con pago parcial/no disponibles para imputar. "
                    "El recibo se publicará sin imputaciones como pago a cuenta del contacto."
                )
            else:
                partial_paid_msg = _(
                    "Se detectaron facturas ya pagadas/canceladas. "
                    "El recibo se publicará sin imputaciones como pago a cuenta del contacto."
                )
            errors.append(partial_paid_msg)
            if log_item:
                current = (log_item.message or "").strip()
                log_item.write({'message': f"{current}\n{partial_paid_msg}".strip() if current else partial_paid_msg})
            if payment_group:
                listed_numbers = ', '.join(str(n) for n in missing_invoice_numbers) if missing_invoice_numbers else _("sin número informado")
                listed_ids = ', '.join(str(i) for i in missing_invoice_ids) if missing_invoice_ids else _("sin odoo_id informado")
                body_msg = _(
                    "No se pudieron imputar todas las facturas informadas (%s). "
                    "IDs Odoo sin coincidencia: %s. "
                    "El recibo se publicó completamente como pago a cuenta del cliente."
                ) % (listed_numbers, listed_ids)
                if requires_review:
                    body_msg = _(
                        "No se pudieron imputar todas las facturas informadas (%s). "
                        "IDs Odoo sin coincidencia: %s. "
                        "El recibo quedó en borrador por revisión obligatoria de IA."
                    ) % (listed_numbers, listed_ids)
                payment_group.sudo().message_post(
                    body=body_msg,
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )
            try:
                if not requires_review:
                    payment_group.post()
                else:
                    _logger.info(
                        "Payment group %s no se publica por revisión obligatoria (error_code=%s).",
                        payment_group.id,
                        error_code,
                    )
                if log_item:
                    if not requires_review:
                        log_item.readed = True
                        _logger.info(
                            "Payment group %s publicado como pago a cuenta por faltante/no disponibilidad de facturas.",
                            payment_group.id,
                        )
                    else:
                        _logger.info(
                            "Payment group %s quedó en borrador por revisión obligatoria.",
                            payment_group.id,
                        )
            except Exception as e:
                _logger.exception(
                    "Error al postear payment group %s por faltante/no disponibilidad de facturas: %s",
                    payment_group.id,
                    e,
                )
        
        _logger.info(f"=== FIN PROCESO TOLERANCIA - Payment Group {payment_group.id} ===")
        return log_item

    def _has_retention_files(self, log_item):
        """
        Verifica si hay archivos de retención descargados en el log_item.
        Retorna True si hay al menos un archivo de retención (attachment_ret1_id a attachment_ret4_id).
        """
        if not log_item:
            return False
        for i in range(1, 5):
            ret_field = f'attachment_ret{i}_id'
            if getattr(log_item, ret_field, None):
                return True
        return False

    def _should_post_payment_group(self, log_item):
        """
        Determina si se debe postear el payment_group basado en las reglas de retenciones:
        - Solo se postea si hay retenciones (has_withholding=True) Y hay al menos un archivo de retención descargado
        - Si hay archivo de retención pero no hay líneas de retención, no se postea
        """
        if not log_item:
            return True  # Si no hay log_item, se postea normalmente (comportamiento anterior)
        
        has_files = self._has_retention_files(log_item)
        has_withholding = log_item.has_withholding
        
        # Si hay archivos de retención pero no hay líneas de retención, no se postea
        if has_files and not has_withholding:
            _logger.info(f"Payment group no se postea: hay archivos de retención pero no hay líneas de retención")
            return False
        
        # Si hay retenciones, verificar que también haya archivos de retención
        if has_withholding:
            return True
        
        # Si no hay retenciones ni archivos, se postea normalmente
        return True

    def _normalize_invoice_number(self, number):
        """
        Normaliza números de factura/comprobante:
        - Si tiene más de 8 dígitos, separa punto de venta y número (últimos 8 dígitos siempre)
        - Si el punto de venta es 0, se omite y solo retorna el número de factura
        - Si tiene 8 dígitos o menos, rellena ceros a la izquierda
        """
        if not number:
            return None
        number = str(number).strip()
        number = re.sub(r'\D', '', number)
        number = number.replace('-', '')

        if len(number) > 8:
            point_of_sale = number[:-8].lstrip('0')
            invoice_number = number[-8:].zfill(8)
            # Si el punto de venta es 0 (todos ceros), omitirlo y retornar solo el número
            if not point_of_sale:
                return invoice_number
            return f"{point_of_sale}-{invoice_number}"
        else:
            return number.zfill(8)

    def _find_and_attach_invoices(self, payment_group, lines, errors):
        """
        Busca y vincula las facturas correspondientes a las líneas de pago.
        - Prioriza búsqueda por odoo_id si viene en la línea JSON
        - Si no se encuentra por odoo_id, usa fallback por número normalizado
        - Normaliza los números de factura usando _normalize_invoice_number
        - Coincide exactamente si viene punto de venta, puede ser 1-12345678 ó 00001-12345678
        - Si solo trae el número (8 dígitos), hace comparación con los últimos 8 dígitos de las facturas del cliente a pagar
        """
        domain = [
            ('partner_id.commercial_partner_id', '=', payment_group.commercial_partner_id.id),
            ('account_id.reconcile', '=', True),
            ('reconciled', '=', False),
            ('full_reconcile_id', '=', False),
            ('company_id', '=', payment_group.company_id.id),
            ('move_id.state', '=', 'posted'),
            ('account_id.internal_type', '=', 'receivable' if payment_group.partner_type == 'customer' else 'payable'),
        ]
        pending_lines = self.env['account.move.line'].sudo().search(domain)
        
        pending_by_id = {}
        pending_by_number = {}
        for l in pending_lines:
            move_id = l.move_id.id
            if move_id:
                if move_id not in pending_by_id:
                    pending_by_id[move_id] = []
                pending_by_id[move_id].append(l)

            norm_number = self._normalize_invoice_number(l.move_id.name)
            if norm_number:
                if norm_number not in pending_by_number:
                    pending_by_number[norm_number] = []
                pending_by_number[norm_number].append(l)

        customer_invoices_domain = [
            ('partner_id.commercial_partner_id', '=', payment_group.commercial_partner_id.id),
            ('company_id', '=', payment_group.company_id.id),
            ('state', '=', 'posted'),
            ('move_type', 'in', ('out_invoice', 'out_refund')) if payment_group.partner_type == 'customer'
            else ('move_type', 'in', ('in_invoice', 'in_refund')),
        ]
        customer_invoices = self.env['account.move'].sudo().search(customer_invoices_domain)
        invoices_by_id = {invoice.id: invoice for invoice in customer_invoices}
        invoices_by_number = {}
        for invoice in customer_invoices:
            norm_number = self._normalize_invoice_number(invoice.name) or self._normalize_invoice_number(invoice.ref)
            if norm_number and norm_number not in invoices_by_number:
                invoices_by_number[norm_number] = invoice

        found_moves = []
        missing_found = False
        paid_invoice_found = False
        partial_invoice_found = False
        missing_invoice_numbers = []
        missing_invoice_ids = []
        for line in lines:
            raw_odoo_id = line.get('odoo_id')
            odoo_id = None
            if raw_odoo_id not in (None, False, '', 'na', 'NA', 'null', 'None'):
                try:
                    odoo_id = int(float(str(raw_odoo_id).strip()))
                except (TypeError, ValueError):
                    odoo_id = None

            norm_line_number = self._normalize_invoice_number(line.get('number'))
            matches = pending_by_id.get(odoo_id) if odoo_id else None
            if not matches:
                matches = pending_by_number.get(norm_line_number) if norm_line_number else None


            if matches:
                found_moves.append(matches[0].id)
            else:
                paid_invoice = invoices_by_id.get(odoo_id) if odoo_id else None
                if not paid_invoice:
                    paid_invoice = invoices_by_number.get(norm_line_number) if norm_line_number else None

                if paid_invoice:
                    paid_invoice_found = True
                    invoice_total = paid_invoice.amount_total or 0.0
                    invoice_residual = paid_invoice.amount_residual or 0.0
                    if 0.0 < invoice_residual < invoice_total:
                        partial_invoice_found = True
                        errors.append(
                            _(
                                "La factura %s (ID Odoo: %s) del partner %s tiene pago parcial y no está disponible para imputar en deudas del recibo. "
                                "Total: %s | Residual: %s."
                            ) % (line.get('number'), paid_invoice.id, payment_group.commercial_partner_id.name, invoice_total, invoice_residual)
                        )
                    else:
                        errors.append(
                            _(
                                "Se encontró la factura %s (ID Odoo: %s) para el partner %s, pero no está disponible para imputar en deudas del recibo "
                                "(ya pagada/cancelada). Total: %s | Residual: %s."
                            ) % (line.get('number'), paid_invoice.id, payment_group.commercial_partner_id.name, invoice_total, invoice_residual)
                        )
                else:
                    errors.append(
                        _("No se encontró la factura %s (ID Odoo: %s) para el partner %s - factura en formato odoo (%s)") %
                        (line.get('number'), raw_odoo_id or 'N/A', payment_group.commercial_partner_id.name, norm_line_number)
                    )
                missing_invoice_numbers.append(line.get('number') or _('(sin número)'))
                if raw_odoo_id not in (None, False, '', 'na', 'NA', 'null', 'None'):
                    missing_invoice_ids.append(str(raw_odoo_id))
                missing_found = True
        if missing_found:
            # Si falta al menos una factura, no se imputa ninguna para evitar
            # conciliaciones parciales no deseadas.
            if len(found_moves) > 0:
                errors.append(
                    _("No se identificaron todas las facturas; el recibo se dejó sin imputaciones para conciliación posterior.")
                )
            payment_group.to_pay_move_line_ids = [(6, 0, [])]
            payment_group.state = 'draft'
        else:
            payment_group.to_pay_move_line_ids = [(6, 0, found_moves)] if found_moves else [(6, 0, [])]
        return (
            missing_found,
            paid_invoice_found,
            partial_invoice_found,
            len(found_moves),
            missing_invoice_numbers,
            missing_invoice_ids,
        )
            
            
    def _create_tolerance_line_before_post(self, payment, payment_group, tolerance_account, difference, payment_date):
        """
        Crea la línea de tolerancia en el asiento draft antes del posteo.
        El monto del pago ya fue ajustado previamente, así que solo creamos la línea de tolerancia.
        
        :param payment: account.payment - El pago en draft
        :param payment_group: account.payment.group - El grupo de pago
        :param tolerance_account: account.account - La cuenta para la diferencia
        :param difference: float - La diferencia (positiva = exceso, negativa = falta)
        :param payment_date: str - La fecha del pago
        :return: account.move.line - La línea de tolerancia creada o None
        """
        try:
            payment_move = payment.move_id
            if not payment_move or payment_move.state != 'draft':
                return None
            
            # Obtener el diario y la cuenta analítica de la compañía
            company = payment_group.company_id
            tolerance_journal = company.datareader_tolerance_journal_id
            tolerance_analytic_account = company.datareader_tolerance_analytic_account_id
            
            abs_diff = abs(difference)
            
            # Obtener payment_group_ids
            existing_payment_group_ids = {payment_group.id}
            payment_group_ids_command = [(6, 0, list(existing_payment_group_ids))]
            
            # Crear línea de tolerancia
            # Si difference > 0 (pago mayor): tolerancia en crédito para balancear
            # Si difference < 0 (pago menor): tolerancia en débito para balancear
            tolerance_line_vals = {
                'move_id': payment_move.id,
                'account_id': tolerance_account.id,
                'partner_id': payment_group.partner_id.id,
                'payment_id': payment.id,
                'payment_group_ids': payment_group_ids_command,
                'date': payment_date,
                'name': 'Diferencia entre recibo y op',
                'debit': abs_diff if difference < 0 else 0.0,  # Débito si falta dinero
                'credit': abs_diff if difference > 0 else 0.0,  # Crédito si sobra dinero
                'company_id': payment_group.company_id.id,
                'currency_id': payment_move.currency_id.id if payment_move.currency_id else False,
            }
            
            # Agregar el diario si está configurado
            if tolerance_journal:
                tolerance_line_vals['journal_id'] = tolerance_journal.id
            
            # Agregar la cuenta analítica si está configurada
            if tolerance_analytic_account:
                tolerance_line_vals['analytic_account_id'] = tolerance_analytic_account.id
            
            # Agregar amount_currency si hay moneda
            if payment_move.currency_id:
                if difference < 0:
                    tolerance_line_vals['amount_currency'] = abs_diff
                else:
                    tolerance_line_vals['amount_currency'] = -abs_diff
            
            create_context = {
                'skip_account_move_synchronization': True,
                'check_move_validity': False,
            }
            
            tolerance_line = self.env['account.move.line'].sudo().with_context(**create_context).create(tolerance_line_vals)
            _logger.info(f"Línea de tolerancia creada antes del post: {tolerance_line.id} (diferencia: {difference})")
            return tolerance_line
            
        except Exception as e:
            _logger.error(f"Error al crear línea de tolerancia antes del post: {e}")
            return None

    def _adjust_payment_lines_with_tolerance(self, payment, payment_group, tolerance_account, difference, matched_amount, payment_date):
        """
        Ajusta las líneas contables del pago y crea la línea de tolerancia en draft.
        
        Reglas:
        - Si diferencia > 0 (pago mayor): ajustar la primera línea de débito restando la diferencia, tolerancia en crédito
        - Si diferencia < 0 (pago menor): ajustar la primera línea de débito sumando la diferencia, tolerancia en crédito
        
        :param payment: account.payment - El pago en draft
        :param payment_group: account.payment.group - El grupo de pago
        :param tolerance_account: account.account - La cuenta para la diferencia
        :param difference: float - La diferencia (positiva = exceso, negativa = falta)
        :param matched_amount: float - El monto total de las facturas
        :param payment_date: str - La fecha del pago
        :return: bool - True si se ajustó correctamente
        """
        try:
            payment_move = payment.move_id
            if not payment_move:
                _logger.warning("El pago no está en draft, no se pueden ajustar las líneas")
                return False
            
            # Obtener el diario y la cuenta analítica de la compañía
            company = payment_group.company_id
            tolerance_journal = company.datareader_tolerance_journal_id
            tolerance_analytic_account = company.datareader_tolerance_analytic_account_id
            
            write_context = {
                'check_move_validity': False,
                'skip_account_move_synchronization': True
            }
            
            # Obtener la cuenta del diario
            journal = payment.journal_id
            if not journal:
                _logger.warning("No se pudo obtener el diario del pago")
                return False
            
            journal_account = journal.default_account_id
            if not journal_account:
                _logger.warning(f"No se pudo obtener la cuenta por defecto del diario {journal.name}")
                return False
            
            # Obtener payment_group_ids
            existing_payment_group_ids = {payment_group.id}
            payment_group_ids_command = [(6, 0, list(existing_payment_group_ids))]
            
            # Obtener la primera línea contable existente del asiento
            # Excluir líneas del diario y de tolerancia para ajustar una línea de cuenta por cobrar
            first_line = payment_move.line_ids.filtered(
                lambda l: l.account_id != tolerance_account and l.account_id != journal_account
            )
            
            _logger.info(f"Buscando primera línea. Líneas encontradas: {len(first_line)}, diferencia: {difference}")
            _logger.info(f"Todas las líneas del asiento: {[(l.id, l.account_id.code, l.debit, l.credit) for l in payment_move.line_ids]}")
            _logger.info(f"Cuenta de tolerancia: {tolerance_account.code if tolerance_account else 'None'}, Cuenta diario: {journal_account.code if journal_account else 'None'}")
            
            if not first_line:
                _logger.warning("No se encontró línea contable existente para ajustar")
                return False
            
            # Tomar el primer registro
            first_line = first_line[0]
            
            _logger.info(f"Ajustando primera línea {first_line.id}, cuenta: {first_line.account_id.code}, débito actual: {first_line.debit}, crédito actual: {first_line.credit}")
            
            # Ajustar la primera línea contable con la diferencia (será la contrapartida)
            current_debit = first_line.debit or 0.0
            
            abs_diff = abs(difference)
            
            if difference < 0:
                if current_debit > 0:
                    new_debit = current_debit + abs_diff
                    first_line.with_context(**write_context).write({'debit': new_debit})

            else:
                if current_debit > 0:
                    new_debit = current_debit - abs_diff
                    first_line.with_context(**write_context).write({'debit': new_debit})
            
            # Agregar payment_group_ids a la línea ajustada
            if first_line.payment_group_ids:
                first_line.with_context(**write_context).payment_group_ids = [(4, payment_group.id)]
            else:
                first_line.with_context(**write_context).payment_group_ids = payment_group_ids_command
            
            # Crear línea de tolerancia en crédito (según lo solicitado)
            tolerance_line_vals = {
                'move_id': payment_move.id,
                'account_id': tolerance_account.id,
                'partner_id': payment_group.partner_id.id,
                'payment_id': payment.id,
                'payment_group_ids': payment_group_ids_command,
                'date': payment_date,
                'name': 'Diferencia entre recibo y op',
                'debit': 0.0,
                'credit': abs_diff,
                'company_id': payment_group.company_id.id,
                'currency_id': payment_move.currency_id.id if payment_move.currency_id else False,
            }
            
            # Agregar el diario si está configurado
            if tolerance_journal:
                tolerance_line_vals['journal_id'] = tolerance_journal.id
            
            # Agregar la cuenta analítica si está configurada
            if tolerance_analytic_account:
                tolerance_line_vals['analytic_account_id'] = tolerance_analytic_account.id
            
            # Agregar amount_currency si hay moneda
            if payment_move.currency_id:
                # amount_currency debe tener el signo opuesto al balance (debit - credit)
                if tolerance_line_vals['credit'] > 0:
                    tolerance_line_vals['amount_currency'] = -abs_diff
                else:
                    tolerance_line_vals['amount_currency'] = abs_diff
            
            create_context = {
                'skip_account_move_synchronization': True,
                'check_move_validity': False,
            }
            
            tolerance_line = self.env['account.move.line'].sudo().with_context(**create_context).create(tolerance_line_vals)
            _logger.info(f"Línea de tolerancia creada después del post: {tolerance_line.id} (diferencia: {difference})")
            
            # Si la cuenta de tolerancia es reconciliable, buscar líneas pendientes para conciliar
            if tolerance_account.reconcile:
                # Buscar líneas de débito pendientes en la cuenta de tolerancia del mismo partner
                domain = [
                    ('account_id', '=', tolerance_account.id),
                    ('partner_id', '=', payment_group.partner_id.id),
                    ('reconciled', '=', False),
                    ('debit', '>', 0),
                    ('company_id', '=', payment_group.company_id.id),
                    ('id', '!=', tolerance_line.id),
                ]
                pending_debit_lines = self.env['account.move.line'].sudo().search(domain, limit=1)
                
                if pending_debit_lines:
                    try:
                        (tolerance_line + pending_debit_lines).reconcile()
                        _logger.info(f"Línea de tolerancia conciliada con línea pendiente: {tolerance_line.id} y {pending_debit_lines.id}")
                    except Exception as e:
                        _logger.warning(f"No se pudo conciliar la línea de tolerancia: {e}")
                else:
                    # Si no hay líneas pendientes, crear una línea de débito para conciliar
                    tolerance_debit_line_vals = {
                        'move_id': payment_move.id,
                        'account_id': tolerance_account.id,
                        'partner_id': payment_group.partner_id.id,
                        'payment_id': payment.id,
                        'payment_group_ids': payment_group_ids_command,
                        'date': payment_date,
                        'name': 'Diferencia entre recibo y op (contrapartida)',
                        'debit': abs_diff,
                        'credit': 0.0,
                        'company_id': payment_group.company_id.id,
                        'currency_id': payment_move.currency_id.id if payment_move.currency_id else False,
                    }
                    
                    if tolerance_journal:
                        tolerance_debit_line_vals['journal_id'] = tolerance_journal.id
                    
                    if tolerance_analytic_account:
                        tolerance_debit_line_vals['analytic_account_id'] = tolerance_analytic_account.id
                    
                    if payment_move.currency_id:
                        tolerance_debit_line_vals['amount_currency'] = abs_diff
                    
                    tolerance_debit_line = self.env['account.move.line'].sudo().with_context(**create_context).create(tolerance_debit_line_vals)
                    _logger.info(f"Línea de débito de tolerancia creada: {tolerance_debit_line.id}")
                    
                    try:
                        (tolerance_line + tolerance_debit_line).reconcile()
                        _logger.info(f"Líneas de tolerancia conciliadas: {tolerance_line.id} y {tolerance_debit_line.id}")
                    except Exception as e:
                        _logger.warning(f"No se pudieron conciliar las líneas de tolerancia: {e}")
            
            return True

        except Exception as e:
            _logger.error(f"Error al ajustar líneas del pago con tolerancia: {e}")
            return False

    def _adjust_payment_lines_and_reconcile(self, payment_group, tolerance_account, difference, matched_amount, tolerance_line):
        """
        Ajusta las líneas del pago y reconcilia con la línea de tolerancia creada antes del post.
        
        :param payment_group: account.payment.group - El grupo de pago
        :param tolerance_account: account.account - La cuenta para la diferencia
        :param difference: float - La diferencia
        :param matched_amount: float - El monto total de las facturas
        :param tolerance_line: account.move.line - La línea de tolerancia ya creada
        :return: bool - True si se ajustó correctamente
        """
        try:
            # Obtener el pago publicado
            payments = payment_group.payment_ids.filtered(lambda p: p.state == 'posted')
            if not payments:
                return False
            
            payment = payments[0]
            payment_move = payment.move_id
            if not payment_move:
                return False

            write_context = {
                'check_move_validity': False,
                'skip_account_move_synchronization': True
            }

            # Obtener las líneas del pago (débito y crédito), excluyendo la línea de tolerancia
            debit_line = payment_move.line_ids.filtered(lambda l: l.debit > 0 and l.account_id != tolerance_account)
            credit_line = payment_move.line_ids.filtered(lambda l: l.credit > 0 and l.account_id != tolerance_account)

            payment_amount = payment.amount
            abs_diff = abs(difference)

            # Ajustar las líneas según la diferencia
            if difference < 0:
                # Pago menor: ajustar débito
                if debit_line:
                    debit_line[0].with_context(**write_context).write({
                        'debit': payment_amount - difference
                    })
            else:
                # Pago mayor: ajustar débito y crédito
                if debit_line:
                    debit_line[0].with_context(**write_context).write({
                        'debit': matched_amount
                    })
                if credit_line:
                    credit_line[0].with_context(**write_context).write({
                        'credit': matched_amount
                    })
            
            # Reconciliar todas las líneas juntas (las 2 del pago + la de tolerancia)
            # Primero, desreconciliar las líneas del pago si están reconciliadas
            lines_to_desreconcile = self.env['account.move.line']
            if debit_line and debit_line[0].reconciled:
                lines_to_desreconcile += debit_line[0]
            if credit_line and credit_line[0].reconciled:
                lines_to_desreconcile += credit_line[0]
            
            if lines_to_desreconcile:
                try:
                    lines_to_desreconcile.remove_move_reconcile()
                    _logger.info(f"Líneas desreconciliadas: {lines_to_desreconcile.ids}")
                except Exception as e:
                    _logger.warning(f"No se pudieron desreconciliar las líneas: {e}")
            
            # Ahora reconciliar todas juntas
            lines_to_reconcile = self.env['account.move.line']
            if debit_line:
                lines_to_reconcile += debit_line[0]
            if credit_line:
                lines_to_reconcile += credit_line[0]
            if tolerance_line:
                lines_to_reconcile += tolerance_line
            
            if len(lines_to_reconcile) >= 2:
                try:
                    lines_to_reconcile.reconcile()
                    _logger.info(f"Líneas reconciliadas: {lines_to_reconcile.ids}")
                except Exception as e:
                    _logger.warning(f"No se pudieron reconciliar las líneas: {e}")
            
            _logger.info(f"Líneas del pago ajustadas y reconciliadas con línea de tolerancia. Diferencia: {difference}")
            return True
            
        except Exception as e:
            _logger.error(f"Error al ajustar líneas y reconciliar: {e}")
            return False

    def _get_tolerance_product(self, company):
        """
        Obtiene el producto para notas de débito de tolerancia.
        
        :param company: res.company - La compañía
        :return: product.product - El producto de tolerancia o None si no está configurado
        """
        if company.datareader_tolerance_product_id:
            # with_company para que las cuentas contables del producto (company-dependent)
            # se resuelvan en la compañía del recibo y no en la del entorno.
            return company.datareader_tolerance_product_id.with_company(company)
        return None

    def _create_credit_note_for_tolerance(self, payment_group, difference, payment_date, company):
        """
        Crea una nota de crédito por la diferencia cuando el pago es menor y está dentro de la tolerancia.
        La nota de crédito reduce la deuda del payment_group.
        
        :param payment_group: account.payment.group - El grupo de pago
        :param difference: float - La diferencia (debe ser positiva, pago menor)
        :param payment_date: str - La fecha del pago (no se usa, se usa fecha de hoy)
        :param company: res.company - La compañía
        :return: account.move - La nota de crédito creada o None
        """
        try:
            if difference <= 0:
                _logger.warning(f"No se crea nota de crédito porque la diferencia es negativa: {difference}")
                return None
            
            abs_diff = abs(difference)
            partner = payment_group.partner_id
            
            # Obtener el partner de la factura asociada que va a imputar
            invoice_partner = None
            invoice_user = None  # res.users del campo partner de la factura
            if payment_group.to_pay_move_line_ids:
                # Tomar el partner de la primera factura asociada
                first_invoice_line = payment_group.to_pay_move_line_ids[0]
                if first_invoice_line.move_id:
                    if first_invoice_line.move_id.partner_id:
                        invoice_partner = first_invoice_line.move_id.partner_id
                        _logger.info(f"Partner obtenido de factura asociada: {invoice_partner.name} (ID: {invoice_partner.id})")
                    
                    # Obtener el usuario comercial (res.users) del campo 'partner' de la factura
                    if hasattr(first_invoice_line.move_id, 'partner') and first_invoice_line.move_id.partner:
                        invoice_user = first_invoice_line.move_id.partner
                        _logger.info(f"Usuario comercial obtenido de factura: {invoice_user.name} (ID: {invoice_user.id})")
            
            # Obtener el producto de tolerancia
            product = self._get_tolerance_product(company)
            
            if not product:
                _logger.error(f"No se encontró producto de tolerancia configurado para la compañía {company.name}")
                return None
            
            # Obtener el diario para la nota de crédito
            # Usar el diario de tolerancia si está configurado, sino buscar un diario de ventas
            journal = company.datareader_tolerance_journal_id
            if not journal:
                journal = self.env['account.journal'].sudo().search([
                    ('company_id', '=', company.id),
                    ('type', '=', 'sale'),
                    ('active', '=', True)
                ], limit=1)
            
            if not journal:
                _logger.error(f"No se encontró diario para crear la nota de crédito en la compañía {company.name}")
                return None
            
            # Orden de prioridad: Configuracion - Producto - Categoria
            product = product.with_company(company)
            income_account = company.datareader_tolerance_account_id
            if not income_account:
                income_account = product.property_account_income_id
            if not income_account:
                income_account = product.categ_id.property_account_income_categ_id
            
            if not income_account:
                _logger.error(f"No se encontró cuenta de ingresos para el producto de tolerancia")
                return None
            
            # Obtener la cuenta por cobrar del partner
            receivable_account = partner.property_account_receivable_id
            if not receivable_account:
                receivable_account = self.env['account.account'].sudo().search([
                    ('company_id', '=', company.id),
                    ('internal_type', '=', 'receivable'),
                    ('deprecated', '=', False)
                ], limit=1)
            
            if not receivable_account:
                _logger.error(f"No se encontró cuenta por cobrar para el partner {partner.name}")
                return None
            
            # Obtener el tipo de documento desde el diario (código 43 para nota de crédito)
            document_type = False
            if hasattr(journal, 'l10n_ar_document_type_ids') and journal.l10n_ar_document_type_ids:
                document_type = journal.l10n_ar_document_type_ids.filtered(lambda d: d.code == '43')
                if not document_type:
                    document_type = journal.l10n_ar_document_type_ids[0] if journal.l10n_ar_document_type_ids else False
                # Asegurarse de que document_type sea un solo registro (no un recordset)
                if document_type:
                    if len(document_type) > 1:
                        document_type = document_type[0]
                    elif len(document_type) == 0:
                        document_type = False
                    # Si es un solo registro, asegurarse de que tenga ID válido
                    elif not document_type.id:
                        document_type = False
            
            # Crear la nota de crédito (out_refund - disminuye la deuda)
            move_vals = {
                'move_type': 'out_refund',
                'partner_id': partner.id,
                'journal_id': journal.id,
                'company_id': company.id,
                'currency_id': company.currency_id.id,
                'date': fields.Date.today(),  # Usar fecha de hoy
                'invoice_date': fields.Date.today(),
                'invoice_origin': f'Nota de Crédito - Diferencia de Tolerancia - Recibo {payment_group.communication or payment_group.id}',
                'ref': f'Nota de Crédito - Diferencia de Tolerancia - Recibo {payment_group.communication or payment_group.id}',
            }
            # Agregar usuario comercial (res.users) de la factura original si existe
            if invoice_user:
                move_vals['partner'] = invoice_user.id
            
            # Agregar tipo de documento si existe
            if document_type and document_type.id:
                move_vals['l10n_latam_document_type_id'] = document_type.id
            
            credit_note = self.env['account.move'].sudo().with_context(datareader=True).create(move_vals)
            
            # Obtener los impuestos del producto
            taxes = product.taxes_id.filtered(lambda t: t.company_id == company)
            if not taxes:
                # Si el producto no tiene impuestos, buscar impuestos por defecto de venta
                taxes = self.env['account.tax'].sudo().search([
                    ('type_tax_use', '=', 'sale'),
                    ('company_id', '=', company.id),
                    ('active', '=', True)
                ], limit=1)
            
            # Crear la línea de producto usando invoice_line_ids
            line_vals = {
                'product_id': product.id,
                'name': f'Diferencia de Tolerancia - Recibo {payment_group.communication or payment_group.id}',
                'quantity': 1.0,
                'price_unit': abs_diff,
                'account_id': income_account.id,
            }
            
            # Agregar el partner de la factura asociada a la línea de producto
            if invoice_partner:
                line_vals['partner_id'] = invoice_partner.id
                _logger.info(f"Partner agregado a línea de nota de crédito: {invoice_partner.name} (ID: {invoice_partner.id})")
            
            # Agregar impuestos si existen
            if taxes:
                line_vals['tax_ids'] = [(6, 0, taxes.ids)]
            
            # Agregar cuenta analítica si está configurada
            if company.datareader_tolerance_analytic_account_id:
                line_vals['analytic_account_id'] = company.datareader_tolerance_analytic_account_id.id
            
            credit_note.with_context(check_move_validity=False).write({
                'invoice_line_ids': [(0, 0, line_vals)]
            })
            
            # Publicar la nota de crédito
            credit_note.with_context(datareader=True).action_post()
            
            _logger.info(f"Nota de crédito creada para tolerancia: {credit_note.name} (ID: {credit_note.id}), monto: {abs_diff}")
            
            # La nota de crédito tiene una línea de cuenta por cobrar con saldo negativo (crédito)
            # Esto reduce automáticamente la deuda cuando se reconcilia
            # Buscar la línea de cuenta por cobrar de la nota de crédito
            credit_note.refresh()
            credit_note_line = credit_note.line_ids.filtered(
                lambda l: l.account_id.internal_type == 'receivable' and not l.reconciled
            )
            
            _logger.info(f"Líneas de la nota de crédito: {[(l.id, l.account_id.code, l.account_id.internal_type, l.debit, l.credit) for l in credit_note.line_ids]}")
            _logger.info(f"Línea de cuenta por cobrar encontrada: {credit_note_line.ids if credit_note_line else 'None'}")
            
            if credit_note_line:
                receivable_line = credit_note_line[0]
                line_id = receivable_line.id
                _logger.info(f"ID de línea a agregar: {line_id}")
                
                # Agregar cuenta analítica a la línea de cuenta por cobrar si está configurada
                if company.datareader_tolerance_analytic_account_id:
                    receivable_line.sudo().write({
                        'analytic_account_id': company.datareader_tolerance_analytic_account_id.id
                    })
                    _logger.info(f"Cuenta analítica {company.datareader_tolerance_analytic_account_id.name} agregada a la línea de cuenta por cobrar {line_id}")
                
                # Agregar la línea al payment_group usando el comando (4, id) para agregar directamente
                payment_group.refresh()
                current_lines = list(payment_group.to_pay_move_line_ids.ids)
                _logger.info(f"Líneas actuales del payment_group: {current_lines}")
                
                if line_id not in current_lines:
                    # Usar comando (4, id) para agregar la línea directamente
                    payment_group.sudo().write({
                        'to_pay_move_line_ids': [(4, line_id)]
                    })
                    payment_group.refresh()
                    _logger.info(f"Línea de nota de crédito {line_id} agregada al payment_group {payment_group.id} usando comando (4, id)")
                    _logger.info(f"Líneas actualizadas del payment_group: {payment_group.to_pay_move_line_ids.ids}")
                else:
                    _logger.info(f"La línea {line_id} ya estaba en el payment_group")
            else:
                _logger.warning(f"No se encontró línea de cuenta por cobrar en la nota de crédito {credit_note.id}")
                _logger.warning(f"Todas las líneas: {[(l.id, l.account_id.code, l.account_id.internal_type) for l in credit_note.line_ids]}")
            
            return credit_note
            
        except Exception as e:
            _logger.error(f"Error al crear nota de crédito para tolerancia: {e}")
            return None

    def _create_invoice_for_tolerance(self, payment_group, difference, payment_date, company):
        """
        Crea una nota de débito por la diferencia cuando el pago es mayor y está dentro de la tolerancia.
        La nota de débito se agrega a la deuda del payment_group.
        
        :param payment_group: account.payment.group - El grupo de pago
        :param difference: float - La diferencia (debe ser negativa, pago mayor)
        :param payment_date: str - La fecha del pago (no se usa, se usa fecha de hoy)
        :param company: res.company - La compañía
        :return: account.move - La nota de débito creada o None
        """
        try:
            if difference >= 0:
                _logger.warning(f"No se crea nota de débito porque la diferencia es positiva: {difference}")
                return None
            
            abs_diff = abs(difference)
            partner = payment_group.partner_id
            
            # Obtener el partner de la factura asociada que va a imputar
            invoice_partner = None
            invoice_user = None  # res.users del campo partner de la factura
            if payment_group.to_pay_move_line_ids:
                # Tomar el partner de la primera factura asociada
                first_invoice_line = payment_group.to_pay_move_line_ids[0]
                if first_invoice_line.move_id:
                    if first_invoice_line.move_id.partner_id:
                        invoice_partner = first_invoice_line.move_id.partner_id
                        _logger.info(f"Partner obtenido de factura asociada: {invoice_partner.name} (ID: {invoice_partner.id})")
                    
                    # Obtener el usuario comercial (res.users) del campo 'partner' de la factura
                    if hasattr(first_invoice_line.move_id, 'partner') and first_invoice_line.move_id.partner:
                        invoice_user = first_invoice_line.move_id.partner
                        _logger.info(f"Usuario comercial obtenido de factura: {invoice_user.name} (ID: {invoice_user.id})")
            
            # Obtener el producto de tolerancia
            product = self._get_tolerance_product(company)
            
            if not product:
                _logger.error(f"No se encontró producto de tolerancia configurado para la compañía {company.name}")
                return None
            
            # Obtener el diario para la nota de débito
            # Usar el diario de tolerancia si está configurado, sino buscar un diario de ventas
            journal = company.datareader_tolerance_journal_id
            if not journal:
                journal = self.env['account.journal'].sudo().search([
                    ('company_id', '=', company.id),
                    ('type', '=', 'sale'),
                    ('active', '=', True)
                ], limit=1)
            
            if not journal:
                _logger.error(f"No se encontró diario para crear la nota de débito en la compañía {company.name}")
                return None
            
            # Orden de prioridad: Configuracion - Producto - Categoria
            income_account = company.datareader_tolerance_account_id
            if not income_account:
                income_account = product.property_account_income_id
            if not income_account:
                income_account = product.categ_id.property_account_income_categ_id
            
            if not income_account:
                _logger.error(f"No se encontró cuenta de ingresos para el producto de tolerancia")
                return None
            
            # Obtener la cuenta por cobrar del partner
            receivable_account = partner.property_account_receivable_id
            if not receivable_account:
                receivable_account = self.env['account.account'].sudo().search([
                    ('company_id', '=', company.id),
                    ('internal_type', '=', 'receivable'),
                    ('deprecated', '=', False)
                ], limit=1)
            
            if not receivable_account:
                _logger.error(f"No se encontró cuenta por cobrar para el partner {partner.name}")
                return None
            
            # Obtener el tipo de documento desde el diario (código 46 para nota de débito)
            document_type = False
            if hasattr(journal, 'l10n_ar_document_type_ids') and journal.l10n_ar_document_type_ids:
                document_type = journal.l10n_ar_document_type_ids.filtered(lambda d: d.code == '46')
                if not document_type:
                    document_type = journal.l10n_ar_document_type_ids[0] if journal.l10n_ar_document_type_ids else False
                # Asegurarse de que document_type sea un solo registro (no un recordset)
                if document_type:
                    if len(document_type) > 1:
                        document_type = document_type[0]
                    elif len(document_type) == 0:
                        document_type = False
                    # Si es un solo registro, asegurarse de que tenga ID válido
                    elif not document_type.id:
                        document_type = False
            
            # Crear la nota de débito (out_invoice - aumenta la deuda)
            # En Odoo, las notas de débito de venta se crean como out_invoice
            move_vals = {
                'move_type': 'out_invoice',
                'partner_id': partner.id,
                'journal_id': journal.id,
                'company_id': company.id,
                'currency_id': company.currency_id.id,
                'date': fields.Date.today(),  # Usar fecha de hoy
                'invoice_date': fields.Date.today(),
                'invoice_origin': f'Nota de Débito - Diferencia de Tolerancia - Recibo {payment_group.communication or payment_group.id}',
                'ref': f'Nota de Débito - Diferencia de Tolerancia - Recibo {payment_group.communication or payment_group.id}',
            }
            # Agregar usuario comercial (res.users) de la factura original si existe
            if invoice_user:
                move_vals['partner'] = invoice_user.id
            
            # Agregar tipo de documento si existe
            if document_type and document_type.id:
                move_vals['l10n_latam_document_type_id'] = document_type.id
            
            # Si existe el campo debit_origin_id (módulo l10n_ar_ux o account_ux), 
            # se puede usar para identificar como nota de débito, pero como no hay factura original, se deja vacío
            if 'debit_origin_id' in self.env['account.move']._fields:
                # Nota de débito standalone (sin factura original)
                move_vals['debit_origin_id'] = False
            
            debit_note = self.env['account.move'].sudo().create(move_vals)
            
            # Obtener los impuestos del producto
            taxes = product.taxes_id.filtered(lambda t: t.company_id == company)
            if not taxes:
                # Si el producto no tiene impuestos, buscar impuestos por defecto de venta
                taxes = self.env['account.tax'].sudo().search([
                    ('type_tax_use', '=', 'sale'),
                    ('company_id', '=', company.id),
                    ('active', '=', True)
                ], limit=1)
            
            # Crear la línea de producto usando invoice_line_ids
            line_vals = {
                'product_id': product.id,
                'name': f'Diferencia de Tolerancia - Recibo {payment_group.communication or payment_group.id}',
                'quantity': 1.0,
                'price_unit': abs_diff,
                'account_id': income_account.id,
            }
            
            # Agregar el partner de la factura asociada a la línea de producto
            if invoice_partner:
                line_vals['partner_id'] = invoice_partner.id
                _logger.info(f"Partner agregado a línea de nota de débito: {invoice_partner.name} (ID: {invoice_partner.id})")
            
            # Agregar impuestos si existen
            if taxes:
                line_vals['tax_ids'] = [(6, 0, taxes.ids)]
            
            # Agregar cuenta analítica si está configurada
            if company.datareader_tolerance_analytic_account_id:
                line_vals['analytic_account_id'] = company.datareader_tolerance_analytic_account_id.id
            
            debit_note.with_context(check_move_validity=False).write({
                'invoice_line_ids': [(0, 0, line_vals)]
            })
            
            # Publicar la nota de débito
            debit_note.action_post()
            
            _logger.info(f"Nota de débito creada para tolerancia: {debit_note.name} (ID: {debit_note.id}), monto: {abs_diff}")
            
            # Agregar la línea de la nota de débito al payment_group (agregar a la deuda)
            # Buscar la línea de cuenta por cobrar de la nota de débito
            debit_note.refresh()
            debit_note_line = debit_note.line_ids.filtered(
                lambda l: l.account_id.internal_type == 'receivable' and not l.reconciled
            )
            
            _logger.info(f"Líneas de la nota de débito: {[(l.id, l.account_id.code, l.account_id.internal_type, l.debit, l.credit) for l in debit_note.line_ids]}")
            _logger.info(f"Línea de cuenta por cobrar encontrada: {debit_note_line.ids if debit_note_line else 'None'}")
            
            if debit_note_line:
                receivable_line = debit_note_line[0]
                line_id = receivable_line.id
                _logger.info(f"ID de línea a agregar: {line_id}")
                
                # Agregar cuenta analítica a la línea de cuenta por cobrar si está configurada
                if company.datareader_tolerance_analytic_account_id:
                    receivable_line.sudo().write({
                        'analytic_account_id': company.datareader_tolerance_analytic_account_id.id
                    })
                    _logger.info(f"Cuenta analítica {company.datareader_tolerance_analytic_account_id.name} agregada a la línea de cuenta por cobrar {line_id}")
                
                # Agregar la línea al payment_group usando el comando (4, id) para agregar directamente
                payment_group.refresh()
                current_lines = list(payment_group.to_pay_move_line_ids.ids)
                _logger.info(f"Líneas actuales del payment_group: {current_lines}")
                
                if line_id not in current_lines:
                    # Usar comando (4, id) para agregar la línea directamente
                    payment_group.sudo().write({
                        'to_pay_move_line_ids': [(4, line_id)]
                    })
                    payment_group.refresh()
                    _logger.info(f"Línea de nota de débito {line_id} agregada al payment_group {payment_group.id} usando comando (4, id)")
                    _logger.info(f"Líneas actualizadas del payment_group: {payment_group.to_pay_move_line_ids.ids}")
                else:
                    _logger.info(f"La línea {line_id} ya estaba en el payment_group")
            else:
                _logger.warning(f"No se encontró línea de cuenta por cobrar en la nota de débito {debit_note.id}")
                _logger.warning(f"Todas las líneas: {[(l.id, l.account_id.code, l.account_id.internal_type) for l in debit_note.line_ids]}")
            
            return debit_note
            
        except Exception as e:
            _logger.error(f"Error al crear nota de débito para tolerancia: {e}")
            return None

    def _attach_files_to_payment_group(self, log_item, payment_group):
        """
        Adjunta los archivos de pago y retenciones del log_item al payment_group (recibo).
        Crea nuevos attachments vinculados al payment_group.
        """
        if not payment_group or not log_item:
            return []
        
        attachments_created = []
        attachment_names = []
        
        # Adjuntar archivo de OP (Orden de Pago)
        if log_item.attachment_op_id:
            attachment_op = self.env['ir.attachment'].sudo().create({
                'name': log_item.attachment_op_id.name,
                'type': 'binary',
                'datas': log_item.attachment_op_id.datas,
                'res_model': 'account.payment.group',
                'res_id': payment_group.id,
                'mimetype': log_item.attachment_op_id.mimetype or 'application/pdf',
            })
            attachments_created.append(attachment_op)
            attachment_names.append(f"• {attachment_op.name} (Orden de Pago)")
            _logger.info(f"Archivo OP adjuntado al recibo {payment_group.id}: {attachment_op.name}")
        
        # Adjuntar archivos de retenciones
        for i in range(1, 5):
            ret_field = f'attachment_ret{i}_id'
            ret_attachment = getattr(log_item, ret_field, None)
            if ret_attachment:
                attachment_ret = self.env['ir.attachment'].sudo().create({
                    'name': ret_attachment.name,
                    'type': 'binary',
                    'datas': ret_attachment.datas,
                    'res_model': 'account.payment.group',
                    'res_id': payment_group.id,
                    'mimetype': ret_attachment.mimetype or 'application/pdf',
                })
                attachments_created.append(attachment_ret)
                attachment_names.append(f"• {attachment_ret.name} (Retención {i})")
                _logger.info(f"Retención {i} adjuntada al recibo {payment_group.id}: {attachment_ret.name}")
        
        # Publicar mensaje en el chatter del recibo
        if attachments_created:
            message_body = _("Se adjuntaron los siguientes archivos al recibo:\n\n%s") % "\n".join(attachment_names)
            payment_group.sudo().message_post(
                body=message_body,
                attachment_ids=[att.id for att in attachments_created],
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )
            _logger.info(f"Mensaje publicado en el chatter del recibo {payment_group.id} con {len(attachments_created)} archivo(s)")
            
        # Si se agregó un attachment y hay errores, agregarlos al chatter
        if log_item.message and log_item.payment_group_id:
            error_message = _("Errores encontrados al procesar la orden de pago:\n\n%s") % log_item.message
            log_item.payment_group_id.sudo().message_post(
                body=error_message,
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )
            _logger.info(f"Errores de la orden agregados al chatter del recibo {log_item.payment_group_id.id}")
        
        return attachments_created

    def action_connect(self):
        ir_config = self.env['ir.config_parameter'].sudo()
        download_files = eval(ir_config.get_param("datareader_odoo.download_files", 'True'))
        download_first_batch = eval(ir_config.get_param("datareader_odoo.download_first_batch", 'False'))
        connector = self.env["datareader.connector"].get_connector()
        pprint(download_files)
        try:
            connector.login()
            failed_orders = []
            while True:
                orders = connector.get_payment_orders()
                if not orders:
                    break

                self.write({
                    "last_token": connector._token,
                    "last_connection": fields.Datetime.now(),
                })

                message = f"Conexión exitosa.\nSe recibieron {len(orders)} órdenes de pago."
                all_files_downloaded = []
                
                for order in orders:
                    order_id = order.get("id")
                    pprint(order_id)
                    file_name = order.get("file_name")
                    
                    # Crear log_item primero para poder descargar archivos antes del procesamiento
                    import json
                    log_item = self._create_log_item(
                        file_name,
                        order_id,
                        error_code=order.get('error_code'),
                    )
                    log_item.json_data = json.dumps(order, ensure_ascii=False)
                    
                    # Descargar archivos ANTES del procesamiento
                    attachment_status = "No descargado"
                    if download_files == True and file_name:
                        try:
                            attachment = box.download_and_attach_file(log_item, file_name, folder_field='box_folder_id_op')
                            if attachment:
                                attachment_status = f"Adjuntado OP: {attachment.name}"
                                _logger.info(f"Archivo OP adjuntado: {attachment.name}")
                                ret_attachments = box.download_and_attach_retentions(log_item, file_name, folder_field='box_folder_id_withholding')
                                if ret_attachments:
                                    attachment_status += f" | Retenciones: {[a.name for a in ret_attachments]}"
                            else:
                                attachment_status = "No se encontró el archivo de OP en Box"
                        except Exception as e:
                            attachment_status = f"Error descargando: {str(e)}"
                            _logger.error(f"Error descargando y adjuntando {file_name}: {e}")
                    
                    # Procesar la orden usando el log_item ya creado
                    log_item = self.create_from_datareader_json(order, connector, log_item=log_item)
                    
                    connector.set_payment_order_readed(order.get("id"), True)
                    if (not log_item.payment_group_id
                            and not log_item.readed
                            and 'Ya existe un recibo de pago' not in log_item.message):
                        failed_orders.append(order.get("id"))
                    
                    # Adjuntar archivos al payment_group (recibo) si existe
                    # Solo intentar adjuntar si los archivos fueron descargados (download_files=True)
                    if log_item.payment_group_id and download_files:
                        try:
                            pg_attachments = self._attach_files_to_payment_group(log_item, log_item.payment_group_id)
                            if pg_attachments:
                                attachment_status += f" | Adjuntados al recibo: {len(pg_attachments)} archivo(s)"
                                _logger.info(f"Archivos adjuntados al recibo {log_item.payment_group_id.id}: {len(pg_attachments)} archivo(s)")
                        except Exception as e:
                            _logger.error(f"Error adjuntando archivos al recibo: {e}")
                    elif log_item.payment_group_id and not download_files:
                        _logger.info(f"Archivos no adjuntados al recibo {log_item.payment_group_id.id}: download_files está deshabilitado")

                    all_files_downloaded.append(f"{file_name}: {attachment_status}")
                        
                message += f"\nArchivos descargados: {all_files_downloaded}"
                _logger.info(message)
                if download_first_batch:
                    for order_id in failed_orders:
                        connector.set_payment_order_readed(order_id, False)
                        # Buscar y marcar el log_item correspondiente como no leído
                        log_item = self.account_payment_group_item_ids.filtered(
                            lambda l: l.json_data and str(order_id) in l.json_data
                        )
                        if log_item:
                            log_item[0].readed = False
                    break
            for order_id in failed_orders:
                connector.set_payment_order_readed(order_id, False)
                # Buscar y marcar el log_item correspondiente como no leído
                log_item = self.account_payment_group_item_ids.filtered(
                    lambda l: l.json_data and str(order_id) in l.json_data
                )
                if log_item:
                    log_item[0].readed = False

        except Exception as e:
            tb = traceback.format_exc()
            message = f"Error al conectar u obtener órdenes: {str(e)}\nTraceback:\n{tb}"
            _logger.error(message)
            raise UserError(f"Error al conectar u obtener órdenes: {str(e)}")

    def action_sync_normalized_partners(self):
        partners = self.env['res.partner'].sudo().search([
            ('active', '=', True),
            #('parent_id', '!=', False),
            ('name', '!=', ''),
        ])
        
        ResPartnerNormalized = self.env['normalized.text']
        ResPartnerNormalizedAlias = self.env['normalized.text.items']

        for partner in partners:
            if not partner.name:
                continue

            original_name = partner.name
            name_processed = partner.preprocess_siglas(original_name)
            partner._ensure_normalized_record(original_name)
            if name_processed.lower() != partner.name.lower():
                partner._ensure_normalized_record(name_processed)
                
    def action_sync_normalized_companies(self):
        companies = self.env['res.company'].sudo().search([
            #('active', '=', True),
            #('parent_id', '!=', False),
            ('name', '!=', ''),
        ])

        RescompanyNormalized = self.env['normalized.text']
        RescompanyNormalizedAlias = self.env['normalized.text.items']

        for company in companies:
            if not company.name:
                continue

            original_name = company.name
            name_processed = company.preprocess_siglas(original_name)
            company._ensure_normalized_record(original_name)
            if name_processed.lower() != company.name.lower():
                company._ensure_normalized_record(name_processed)
    
    def action_sync_normalized_journals(self):
        journals = self.env['account.journal'].sudo().search([
            #('active', '=', True),
            #('parent_id', '!=', False),
            ('name', '!=', ''),
        ])
        
        AccountJournalNormalized = self.env['normalized.text']
        AccountJournalNormalizedAlias = self.env['normalized.text.items']

        for journal in journals:
            if not journal.name:
                continue

            original_name = journal.name
            name_processed = journal.preprocess_siglas(original_name)
            journal._ensure_normalized_record(original_name)
            if name_processed.lower() != journal.name.lower():
                journal._ensure_normalized_record(name_processed)
            
    def action_open_normalized_partners(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Normalized Partners',
            'res_model': 'normalized.text',
            'view_mode': 'tree,form',
            'views': [
                (self.env.ref('datareader_customer_receipts.view_normalized_text_tree_partner').id, 'tree'),
                (self.env.ref('datareader_customer_receipts.view_normalized_text_form').id, 'form')
            ],
            'domain': [
                ('res_partner_id', '!=', False),
                ('res_company_id', '=', False),
                ('account_journal_id', '=', False),
            ],
            'target': 'current',
        }

    def action_open_normalized_companies(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Normalized Partners',
            'res_model': 'normalized.text',
            'view_mode': 'tree,form',
            'views': [
                (self.env.ref('datareader_customer_receipts.view_normalized_text_tree_company').id, 'tree'),
                (self.env.ref('datareader_customer_receipts.view_normalized_text_form').id, 'form')
            ],
            'domain': [
                ('res_partner_id', '=', False),
                ('res_company_id', '!=', False),
                ('account_journal_id', '=', False),
            ],
            'target': 'current',
        }

    def action_open_normalized_journals(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Normalized Partners',
            'res_model': 'normalized.text',
            'view_mode': 'tree,form',
            'views': [
                (self.env.ref('datareader_customer_receipts.view_normalized_text_tree_journal').id, 'tree'),
                (self.env.ref('datareader_customer_receipts.view_normalized_text_form').id, 'form')
            ],      
            'domain': [
                ('res_partner_id', '=', False),
                ('res_company_id', '=', False),
                ('account_journal_id', '!=', False),
            ],
            'target': 'current',
        }

class DataReaderAccountPaymentGroupLogItem(models.Model):
    _name = "datareader.account.payment.group.log.item"
    _description = "Detalle de ejecución del Payment Group"

    payment_group_id = fields.Many2one(
        'account.payment.group', string="Recibo Contable")
    log_id = fields.Many2one(
        'datareader.account.payment.group.log', string="Log Principal", required=True, ondelete='cascade'
    )
    file_name = fields.Char('Nombre del Archivo en Box')
    state = fields.Selection(
        related='payment_group_id.state',
        string='Estado',
        readonly=True
    )
    message = fields.Text(string="Detalle / Error")
    has_withholding = fields.Boolean(string="Tiene Retenciones")
    has_check = fields.Boolean(string="Tiene Cheques")
    create_date = fields.Datetime(string="Fecha de Creación", readonly=True)
    # Archivos PDF descargados desde BOX
    attachment_op_id = fields.Many2one('ir.attachment', string="Archivo OP", help="Archivo PDF o documento original de la Orden de Pago")
    attachment_ret1_id = fields.Many2one('ir.attachment', string="Retención 1")
    attachment_ret2_id = fields.Many2one('ir.attachment', string="Retención 2")
    attachment_ret3_id = fields.Many2one('ir.attachment', string="Retención 3")
    attachment_ret4_id = fields.Many2one('ir.attachment', string="Retención 4")
    invoices_found = fields.Boolean(string="Invoices", default=False)
    json_data = fields.Text(string="Invoices", default=False)
    readed = fields.Boolean(string="Leída", default=False, help="Indica si la orden de pago ha sido marcada como leída")
    op_exists = fields.Boolean(string="OP Existe", default=False, help="Indica si ya existe un payment_group con el mismo op_number")
    reprocessed = fields.Boolean(string="Reprocesada", default=False, help="Indica si la orden de pago fue reprocesada mediante el botón de reprocesamiento")
    order_id = fields.Char(string="ID Orden", help="ID de la orden de pago en el conector DataReader")
    error_code = fields.Char(string="Código de Error", readonly=True)

    def _get_order_by_id_from_connector(self, order_id):
        """
        Método base que obtiene el conector, hace login y busca la orden específica por ID.
        Retorna (connector, order) o (None, None) si no se encuentra.
        """
        if not order_id:
            return None, None
        
        try:
            connector = self.env["datareader.connector"].get_connector()
            connector.login()
            
            # Buscar la orden en los lotes (el conector trae de a 20)
            while True:
                orders = connector.get_payment_orders()
                if not orders:
                    break
                
                # Buscar la orden con el ID específico
                for order in orders:
                    if order.get("id") == order_id:
                        return connector, order
            
            # Si no se encontró en ningún lote
            return connector, None
            
        except Exception as e:
            _logger.error(f"Error obteniendo orden {order_id} del conector: {e}")
            return None, None

    def _parse_json_data(self, json_data):
        """
        Parsea json_data que puede estar en diferentes formatos:
        - String JSON válido
        - String con representación de diccionario Python (repr)
        - Diccionario Python
        """
        import json
        import ast
        
        if not json_data:
            return None
        
        # Si ya es un diccionario, retornarlo directamente
        if isinstance(json_data, dict):
            return json_data
        
        # Si es string, intentar parsear
        if isinstance(json_data, str):
            # Primero intentar como JSON válido
            try:
                return json.loads(json_data)
            except (json.JSONDecodeError, ValueError):
                # Si falla, intentar como literal de Python (dict con comillas simples)
                try:
                    return ast.literal_eval(json_data)
                except (ValueError, SyntaxError) as e:
                    _logger.warning(f"Error parseando json_data con ast.literal_eval: {e}")
                    _logger.debug(f"Contenido json_data (primeros 200 chars): {json_data[:200]}")
                    raise UserError(_("Error al parsear los datos JSON. El formato no es válido. Por favor, contacte al administrador."))
        
        return None

    def action_mark_as_read(self):
        """Marca la orden de pago como leída en el conector."""
        if not self.json_data:
            raise UserError(_("No hay datos JSON para procesar."))
        
        try:
            # Parsear el json_data usando el método helper
            order_data = self._parse_json_data(self.json_data)
            if not order_data:
                raise UserError(_("No se pudieron parsear los datos JSON."))
            
            order_id = order_data.get("id")
            
            if not order_id:
                raise UserError(_("No se encontró el ID de la orden en los datos JSON."))
            
            # Obtener el conector y conectar
            connector = self.env["datareader.connector"].get_connector()
            connector.login()
            
            if not connector:
                raise UserError(_("Error al conectar con el conector."))
            
            # Marcar como leída solo esta orden (las demás se ignoran)
            connector.set_payment_order_readed(order_id, True)
            
            # Actualizar el campo readed del modelo
            self.readed = True
            
            # Actualizar el json_data para reflejar que está leída
            import json
            order_data['readed'] = True
            self.json_data = json.dumps(order_data, ensure_ascii=False)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Éxito'),
                    'message': _('La orden de pago %s ha sido marcada como leída.') % order_id,
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.client', 'tag': 'reload'},
                }
            }
            
        except UserError:
            raise
        except Exception as e:
            _logger.error(f"Error marcando orden como leída: {e}")
            raise UserError(_("Error al marcar la orden como leída: %s") % str(e))

    def action_reprocess_payment_order(self):
        """Reprocesa completamente la orden de pago."""
        if not self.json_data:
            raise UserError(_("No hay datos JSON para procesar."))
        
        try:
            # Parsear el json_data usando el método helper
            order_data = self._parse_json_data(self.json_data)
            if not order_data:
                raise UserError(_("No se pudieron parsear los datos JSON."))
            
            order_id = order_data.get("id")
            
            if not order_id:
                raise UserError(_("No se encontró el ID de la orden en los datos JSON."))
            
            # Obtener el conector y buscar la orden
            connector, order = self._get_order_by_id_from_connector(order_id)
            
            if not connector:
                raise UserError(_("Error al conectar con el conector."))
            
            if not order:
                raise UserError(_("No se encontró la orden de pago con ID %s en el conector.") % order_id)
            
            # Obtener configuración
            ir_config = self.env['ir.config_parameter'].sudo()
            download_files = eval(ir_config.get_param("datareader_odoo.download_files", 'True'))
            
            # Reprocesar la orden completa usando el método del log principal
            # Esto creará un nuevo log_item, pero actualizaremos el actual
            new_log_item = self.log_id.create_from_datareader_json(order, connector)
            
            # Actualizar este log_item con los datos del nuevo procesamiento
            import json
            update_vals = {
                'message': new_log_item.message if new_log_item else self.message,
                'json_data': json.dumps(order, ensure_ascii=False) if isinstance(order, dict) else order,
                'reprocessed': True,
            }
            # Solo actualizar order_id si no existe
            if not self.order_id:
                update_vals['order_id'] = str(order_id)
            
            if new_log_item and new_log_item.payment_group_id:
                update_vals.update({
                    'payment_group_id': new_log_item.payment_group_id.id,
                    'has_withholding': new_log_item.has_withholding,
                    'has_check': new_log_item.has_check,
                })
            
            self.write(update_vals)
            
            # Si se creó un nuevo log_item diferente, eliminar los attachments del nuevo
            # y copiarlos al actual, luego eliminar el nuevo log_item
            if new_log_item and new_log_item.id != self.id:
                # Copiar attachments del nuevo al actual si no existen
                attachment_added = False
                if new_log_item.attachment_op_id and not self.attachment_op_id:
                    self.attachment_op_id = new_log_item.attachment_op_id.id
                    attachment_added = True
                for i in range(1, 5):
                    ret_field = f'attachment_ret{i}_id'
                    new_ret = getattr(new_log_item, ret_field, None)
                    current_ret = getattr(self, ret_field, None)
                    if new_ret and not current_ret:
                        setattr(self, ret_field, new_ret.id)
                        attachment_added = True
                
                # Si se agregó un attachment y hay errores, agregarlos al chatter
                if attachment_added and new_log_item.message and new_log_item.payment_group_id:
                    error_message = _("Errores encontrados al procesar la orden de pago:\n\n%s") % new_log_item.message
                    new_log_item.payment_group_id.sudo().message_post(
                        body=error_message,
                        message_type='notification',
                        subtype_xmlid='mail.mt_note'
                    )
                    _logger.info(f"Errores de la orden agregados al chatter del recibo {new_log_item.payment_group_id.id}")
                
                # Eliminar el nuevo log_item ya que actualizamos el actual
                new_log_item.unlink()
            
            # Usar este log_item para descargar archivos
            log_item = self

            # Descargar y adjuntar archivos si está configurado
            file_name = order.get("file_name")
            if download_files and file_name and log_item:
                try:
                    attachment = box.download_and_attach_file(log_item, file_name, folder_field='box_folder_id_op')
                    if attachment:
                        _logger.info(f"Archivo OP adjuntado: {attachment.name}")
                        ret_attachments = box.download_and_attach_retentions(log_item, file_name, folder_field='box_folder_id_withholding')
                        
                        # Adjuntar archivos al payment_group (recibo) si existe
                        if log_item.payment_group_id:
                            try:
                                pg_attachments = self.log_id._attach_files_to_payment_group(log_item, log_item.payment_group_id)
                                if pg_attachments:
                                    _logger.info(f"Archivos adjuntados al recibo {log_item.payment_group_id.id}: {len(pg_attachments)} archivo(s)")
                            except Exception as e:
                                _logger.error(f"Error adjuntando archivos al recibo: {e}")
                except Exception as e:
                    _logger.error(f"Error descargando y adjuntando {file_name}: {e}")
            
            # Marcar como leída solo si se generó el recibo (payment_group_id)
            if self.payment_group_id:
                connector.set_payment_order_readed(order_id, True)
                self.readed = True
                message = _('La orden de pago %s ha sido reprocesada correctamente y marcada como leída.') % order_id
            else:
                message = _('La orden de pago %s fue procesada pero no se generó recibo. No se marcó como leída.') % order_id
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Éxito'),
                    'message': message,
                    'type': 'success' if self.payment_group_id else 'warning',
                    'sticky': False,
                    'next': {'type': 'ir.actions.client', 'tag': 'reload'},
                }
            }
            
        except UserError:
            raise
        except Exception as e:
            _logger.error(f"Error reprocesando orden: {e}")
            raise UserError(_("Error al reprocesar la orden: %s") % str(e))
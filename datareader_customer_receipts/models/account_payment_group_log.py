from odoo import models, fields, api, _
from odoo.tools import cache
from ..utils import datareader_conn, box, cuit_alias
from datetime import datetime
import logging
import re
from odoo.exceptions import UserError
import os
import json
from datetime import datetime
    
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

        # Validar duplicado en payment.group
        existing_op = self.env['account.payment.group'].sudo().search(
            [('communication', '=', op_number)],
            limit=1
        )
        if existing_op:
            errors.append(f"Ya existe un recibo de pago con el número {op_number} (ID {existing_op.id}) .")
            if log_item:
                log_item.write({'message': "\n".join(errors)})
            return None, errors

        return op_number, errors

    def _validate_required_fields(self, data, required_fields):
        missing = []
        for field in required_fields:
            value = data.get(field) if isinstance(data, dict) else getattr(data, field, None)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(field)
        return missing

    def _create_log_item(self, file_name):
        return self.env['datareader.account.payment.group.log.item'].create({
            'log_id': self.id,
            'file_name': file_name or 'No hay archivo relacionado'
        })

    def _get_company(self, company_name, errors):
        company, errors = cuit_alias.find_record_by_cuit_or_name(
            self.env, 'res.company', name=company_name, errors=errors
        )
        if not company:
            errors.append(f"No se encontró compañía '{company_name}', se detiene el proceso.")
        return company, errors

    def _get_partner(self, cuit, name, errors):
        partner, errors = cuit_alias.find_record_by_cuit_or_name(
            self.env, 'res.partner', cuit=cuit, name=name, errors=errors
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

    def create_from_datareader_json(self, data, connector):
        """
        Crea un recibo (account.payment.group) y sus líneas de pago (account.payment)
        desde un JSON proveniente de DataReader.
        """
        ir_config = self.env['ir.config_parameter'].sudo()
        # ver si se utiliza
        ap_post = eval(ir_config.get_param("datareader_odoo.datareader_post_account_payment", 'False'))
        apg_post = eval(ir_config.get_param("datareader_odoo.datareader_post_account_payment_group", 'False'))
        
        file_name = data.get("file_name")
        log_item = self._create_log_item(file_name)
        errors = []

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
        partner_id, errors = self._get_partner(partner_cuit, partner_name, errors)
        if not partner_id:
            log_item.write({'message': "\n".join(errors)})
            return log_item
        elif len(partner_id) > 1:
            return log_item

        journal_name = data.get('journal')
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

        amount = float(data.get('amount_bruto') or 0.0)
        if amount == 0.0:
            errors.append(f"No vino monto en la orden.")
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
            'payment_date': payment_date_str,
            'receiptbook_id': receiptbook_id.id,
            'state': 'draft',
            'partner_type': 'customer',
            'communication': op_number,
        }

        payment_group = self.env['account.payment.group'].sudo().create(vals)

        self.env.cr.flush()
        log_item.payment_group_id = payment_group

        invoices_found = self._find_and_attach_invoices(payment_group, data.get('lines', []), errors=errors)
        if invoices_found:
            log_item.write({
                'invoices_found': True
            })
        log_item.write({
            'message': "\n".join(errors)
        })
        
        payment_vals = {
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': partner_id.id,
            'amount': amount,
            'date': payment_date_str,
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
        if ap_post:
            total_payment_line.action_post()            

        withholdings = data.get('retentions', [])
        
        for withholding in withholdings:
            ret_account_payment_obj = self.env['account.payment'].sudo()
            ret_amount = float(withholding.get('amount') or 0.0)
            ret_number = withholding.get('number') or False
            ret_name = withholding.get('name') or False
            if not ret_number or str(ret_number).lower() == 'na':
                ret_number = 'N/A'
                
            if not ret_amount:
                continue

            # Impuesto de retención
            withholding_tax = self.env['account.tax'].sudo().search([
                ('type_tax_use', 'ilike', 'customer'),
                ('datareader_custom_identifier', '=', ret_name),
                ('company_id', '=', company_id.id),
                ('active', '=', True)
            ], limit=1)

            # Si no existe impuesto, registra error y corta el proceso ya que es requerido
            if not withholding_tax:
                errors.append(f"No se encontró el impuesto de Retención para {ret_name}, puede que se deba configurar el campo datareader_custom_identifier")
                log_item.write({'message': "\n".join(errors)})
                return log_item

            ret_payment_vals = {
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': partner_id.id,
                'amount': ret_amount,
                'date': payment_date_str,
                'journal_id': ret_journal_id.id,
                'payment_method_line_id': payment_method_withholding_line.id,
                'company_id': company_id.id,
                'currency_id': company_id.currency_id.id,
                'tax_withholding_id': withholding_tax.id,
                'withholding_number': ret_number,
                'payment_group_id': payment_group.id,
            }

            total_payment_line.amount -= ret_amount
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
        if partner_id.datareader_auto_payment_post and payment_method != 'cheque':
            payment_difference = payment_group.payment_difference
            company = company_id
            
            # Verificar si está habilitada la tolerancia
            tolerance_enabled = company.datareader_tolerance_enabled
            tolerance_amount = company.datareader_tolerance_amount or 0.0
            tolerance_account = company.datareader_tolerance_account_id
            
            # Si no hay diferencia, publicar normalmente
            if abs(payment_difference) == 0.0:
                payment_group.post()
            # Si hay diferencia dentro del margen de tolerancia
            elif (tolerance_enabled and 
                  tolerance_amount > 0.0 and 
                  abs(payment_difference) <= tolerance_amount and
                  tolerance_account):
                # Calcular el monto total que deben cubrir las facturas
                matched_amount = sum(payment_group.to_pay_move_line_ids.mapped('amount_residual'))
                
                # Ajustar el monto del pago principal para que cubra exactamente las facturas
                main_payment = payment_group.payment_ids.filtered(lambda p: p.state == 'draft')[0] if payment_group.payment_ids else None
                if main_payment and matched_amount > 0:
                    # Ajustar el monto del pago para que coincida con el monto de las facturas
                    old_amount = main_payment.amount
                    main_payment.amount = matched_amount
                    _logger.info(f"Ajustado monto del pago {main_payment.id} de {old_amount} a {matched_amount}")
                
                # Publicar el payment_group primero (esto reconciliará las facturas)
                payment_group.post()
                
                # Crear las líneas contables de tolerancia después del post
                # para manejar la diferencia y asegurar que las facturas queden totalmente pagadas
                tolerance_created = self._create_tolerance_move_line(
                    payment_group,
                    tolerance_account,
                    payment_difference,
                    payment_date_str
                )
                
                if tolerance_created:
                    _logger.info(f"Payment group {payment_group.id} publicado con tolerancia aplicada. Diferencia: {payment_difference}")
                else:
                    _logger.warning(f"Payment group {payment_group.id} publicado pero no se pudieron crear líneas de tolerancia")
            # Si hay diferencia fuera de tolerancia, no publicar (dejar en draft)
            else:
                if payment_difference != 0.0:
                    _logger.info(f"Payment group {payment_group.id} no publicado. Diferencia {payment_difference} fuera de tolerancia ({tolerance_amount})")
            
        return log_item

    def _normalize_invoice_number(self, number):
        """
        Normaliza números de factura/comprobante:
        - Si tiene más de 8 dígitos, separa punto de venta y número (últimos 8 dígitos siempre)
        - Si tiene 8 dígitos o menos, rellena ceros a la izquierda
        """
        if not number:
            return None
        number = str(number).strip()
        number = re.sub(r'\D', '', number)
        number = number.replace('-', '')

        if len(number) > 8:
            point_of_sale = number[:-8].lstrip('0') or '0'
            invoice_number = number[-8:].zfill(8)
            return f"{point_of_sale}-{invoice_number}"
        else:
            return number.zfill(8)

    def _find_and_attach_invoices(self, payment_group, lines, errors):
        """
        Busca y vincula las facturas correspondientes a las líneas de pago.
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
        
        pending_by_number = {}
        for l in pending_lines:
            norm_number = self._normalize_invoice_number(l.move_id.name)
            if norm_number:
                if norm_number not in pending_by_number:
                    pending_by_number[norm_number] = []
                pending_by_number[norm_number].append(l)
        found_moves = []
        missing_found = False
        for line in lines:
            norm_line_number = self._normalize_invoice_number(line.get('number'))
            matches = None
            for key, lines in pending_by_number.items():
                if norm_line_number in key:
                    matches = lines
                    break


            if matches:
                found_moves.append(matches[0].id)
            else:
                errors.append(
                    _("No se encontró la factura %s para el partner %s - factura en formato odoo (%s)") %
                    (line.get('number'), payment_group.commercial_partner_id.name, norm_line_number)
                )
                missing_found = True
        if missing_found:
            if len(found_moves) > 0:
                errors.append(
                    _("No se imputaron todas las facturas")
                )
                payment_group.to_pay_move_line_ids = [(6, 0, found_moves)]
                payment_group.state = 'draft'
        else:
            payment_group.to_pay_move_line_ids = [(6, 0, found_moves)] if found_moves else [(6, 0, 0)]

    def _create_tolerance_move_line(self, payment_group, tolerance_account, difference, payment_date):
        """
        Crea una línea contable en el asiento del payment_group para saldar
        la diferencia de tolerancia. No modifica las facturas.
        
        :param payment_group: account.payment.group - El grupo de pago
        :param tolerance_account: account.account - La cuenta para la diferencia
        :param difference: float - La diferencia (puede ser positiva o negativa)
        :param payment_date: str - La fecha del pago (formato YYYY-MM-DD)
        :return: bool - True si se creó la línea correctamente
        """
        # Obtener el pago principal del payment_group
        payments = payment_group.payment_ids.filtered(lambda p: p.state == 'posted')
        if not payments:
            _logger.warning("No hay pagos publicados en el payment_group para aplicar tolerancia")
            return False
        
        # Tomar el primer pago publicado (o el principal si hay varios)
        payment = payments[0]
        payment_move = payment.move_id
        
        if not payment_move:
            _logger.warning("No se pudo obtener el asiento contable del pago")
            return False
        
        # Verificar que el asiento esté publicado
        if payment_move.state != 'posted':
            _logger.warning(f"El asiento {payment_move.name} no está publicado (state: {payment_move.state})")
            return False
        
        # Obtener la cuenta del diario del pago para la contrapartida
        journal = payment.journal_id
        if not journal:
            _logger.warning("No se pudo obtener el diario del pago")
            return False
        
        # La cuenta del diario es la contrapartida (cuenta de banco/efectivo)
        # Normalmente está en payment.journal_id.default_account_id
        journal_account = journal.default_account_id
        if not journal_account:
            _logger.warning(f"No se pudo obtener la cuenta por defecto del diario {journal.name}")
            return False
        
        try:
            # Lógica para saldar:
            # Si difference > 0: el recibo es mayor, necesitamos HABER en tolerancia (y DEBE en diario)
            # Si difference < 0: el recibo es menor, necesitamos DEBE en tolerancia (y HABER en diario)
            
            # Obtener payment_group_ids existentes de otras líneas del asiento (si las hay)
            # y agregar el payment_group actual
            existing_move_lines = payment_move.line_ids.filtered(lambda l: l.payment_group_ids)
            existing_payment_group_ids = set()
            for line in existing_move_lines:
                existing_payment_group_ids.update(line.payment_group_ids.ids)
            existing_payment_group_ids.add(payment_group.id)
            payment_group_ids_command = [(6, 0, list(existing_payment_group_ids))]
            
            # Línea en cuenta de tolerancia
            tolerance_line_vals = {
                'move_id': payment_move.id,
                'account_id': tolerance_account.id,
                'partner_id': payment_group.partner_id.id,
                'payment_id': payment.id,
                'payment_group_ids': payment_group_ids_command,
                'date': payment_date,
                'name': 'diferencia entre recibo y op',
                'debit': abs(difference) if difference < 0 else 0.0,  # DEBE si diferencia negativa
                'credit': difference if difference > 0 else 0.0,  # HABER si diferencia positiva
                'company_id': payment_group.company_id.id,
                'currency_id': payment_move.currency_id.id if payment_move.currency_id else False,
            }
            
            # Línea contrapartida en cuenta del diario
            counterpart_line_vals = {
                'move_id': payment_move.id,
                'account_id': journal_account.id,
                'partner_id': payment_group.partner_id.id,
                'payment_id': payment.id,
                'payment_group_ids': payment_group_ids_command,
                'date': payment_date,
                'name': 'diferencia entre recibo y op',
                'debit': difference if difference > 0 else 0.0,  # DEBE si diferencia positiva
                'credit': abs(difference) if difference < 0 else 0.0,  # HABER si diferencia negativa
                'company_id': payment_group.company_id.id,
                'currency_id': payment_move.currency_id.id if payment_move.currency_id else False,
            }
            
            # Crear ambas líneas
            self.env['account.move.line'].sudo().create(tolerance_line_vals)
            self.env['account.move.line'].sudo().create(counterpart_line_vals)
            
            _logger.info(f"Líneas contables de tolerancia creadas en el asiento {payment_move.name} por diferencia de {difference}")
            return True
            
        except Exception as e:
            _logger.error(f"Error al crear líneas contables de tolerancia: {e}")
            return False

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
        
        return attachments_created

    def action_connect(self):
        ir_config = self.env['ir.config_parameter'].sudo()
        download_files = eval(ir_config.get_param("datareader_odoo.download_files", 'True'))
        download_first_batch = eval(ir_config.get_param("datareader_odoo.download_first_batch", 'False'))
        connector = self.env["datareader.connector"].get_connector()

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
                    log_item = self.create_from_datareader_json(order, connector)
                    # Guardar como JSON string para evitar problemas de parseo
                    import json
                    log_item.json_data = json.dumps(order, ensure_ascii=False)
                    
                    connector.set_payment_order_readed(order.get("id"), True)
                    log_item.readed = True
                    if not log_item.payment_group_id and not 'Ya existe un recibo de pago' in log_item.message:
                        failed_orders.append(order.get("id"))

                    file_name = order.get("file_name")
                    
                    attachment_status = "No descargado"
                    if download_files and file_name:
                        try:
                            attachment = box.download_and_attach_file(log_item, file_name, folder_field='box_folder_id_op')
                            if attachment:
                                attachment_status = f"Adjuntado OP: {attachment.name}"
                                _logger.info(f"Archivo OP adjuntado: {attachment.name}")
                                ret_attachments = box.download_and_attach_retentions(log_item, file_name, folder_field='box_folder_id_withholding')
                                if ret_attachments:
                                    attachment_status += f" | Retenciones: {[a.name for a in ret_attachments]}"
                                
                                # Adjuntar archivos al payment_group (recibo) si existe
                                if log_item.payment_group_id:
                                    try:
                                        pg_attachments = self._attach_files_to_payment_group(log_item, log_item.payment_group_id)
                                        if pg_attachments:
                                            attachment_status += f" | Adjuntados al recibo: {len(pg_attachments)} archivo(s)"
                                            _logger.info(f"Archivos adjuntados al recibo {log_item.payment_group_id.id}: {len(pg_attachments)} archivo(s)")
                                    except Exception as e:
                                        _logger.error(f"Error adjuntando archivos al recibo: {e}")
                            else:
                                attachment_status = "No se encontró el archivo de OP en Box"
                        except Exception as e:
                            attachment_status = f"Error descargando: {str(e)}"
                            _logger.error(f"Error descargando y adjuntando {file_name}: {e}")

                    all_files_downloaded.append(f"{file_name}: {attachment_status}")
                        
                message += f"\nArchivos descargados: {all_files_downloaded}"
                _logger.info(message)
                if download_first_batch:
                    for order in failed_orders:
                        connector.set_payment_order_readed(order, False)
                    break
            for order in failed_orders:
                connector.set_payment_order_readed(order, False)

        except Exception as e:
            message = f"Error al conectar u obtener órdenes: {str(e)}"
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
            
            # Obtener el conector y buscar la orden
            connector, order = self._get_order_by_id_from_connector(order_id)
            
            if not connector:
                raise UserError(_("Error al conectar con el conector."))
            
            if not order:
                raise UserError(_("No se encontró la orden de pago con ID %s en el conector.") % order_id)
            
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
            }
            
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
                if new_log_item.attachment_op_id and not self.attachment_op_id:
                    self.attachment_op_id = new_log_item.attachment_op_id.id
                for i in range(1, 5):
                    ret_field = f'attachment_ret{i}_id'
                    new_ret = getattr(new_log_item, ret_field, None)
                    current_ret = getattr(self, ret_field, None)
                    if new_ret and not current_ret:
                        setattr(self, ret_field, new_ret.id)
                
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
                }
            }
            
        except UserError:
            raise
        except Exception as e:
            _logger.error(f"Error reprocesando orden: {e}")
            raise UserError(_("Error al reprocesar la orden: %s") % str(e))
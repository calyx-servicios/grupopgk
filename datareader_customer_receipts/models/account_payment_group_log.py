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
    _description = _("Wrapper for DataReaderConnector (external)")

    def get_connector(self):
        return datareader_conn.DatareaderConnector.create_from_environment(self.env)

class DataReaderAccountPaymentGroupLog(models.Model):
    _name = "datareader.account.payment.group.log"
    _description = _("DataReader Connector to Process Json")
    _inherit = ['mail.thread']
        
    name = fields.Char(string=_("Name"), default=_("DataReader Connector"), readonly=True)
    last_token = fields.Char(string=_("Last Token"), readonly=True)
    last_connection = fields.Datetime(string=_("Last Connection"), readonly=True)
    account_payment_group_item_ids = fields.One2many(
        'datareader.account.payment.group.log.item',
        'log_id',
        string=_("Processing Details")
    )

    def _validate_op_number(self, data, errors, log_item=None):
        """
        Validates that operation number comes and is not duplicated.
        Returns the operation number or None if there is an error.
        """
        op_number = data.get('op_number')

        if not op_number or str(op_number).lower() == 'na':
            errors.append(_("No operation number came in the order."))
            if log_item:
                log_item.write({'message': "\n".join(errors)})
            return None, errors

        # Validar duplicado en payment.group
        existing_op = self.env['account.payment.group'].sudo().search(
            [('communication', '=', op_number)],
            limit=1
        )
        if existing_op:
            errors.append(_("A payment receipt with number %s (ID %s) already exists.") % (op_number, existing_op.id))
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

    def _create_log_item(self, file_name, order_id=None):
        vals = {
            'log_id': self.id,
            'file_name': file_name or _('No related file')
        }
        if order_id:
            vals['order_id'] = str(order_id)
        return self.env['datareader.account.payment.group.log.item'].create(vals)

    def _get_company(self, company_name, errors):
        company, errors = cuit_alias.find_record_by_cuit_or_name(
            self.env, 'res.company', name=company_name, errors=errors
        )
        if not company:
            errors.append(_("Company '%s' not found, process stopped.") % company_name)
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
        Converts a string to date in Odoo format (YYYY-MM-DD).
        If the date is invalid or does not come, uses today's date.
        """
        if date_str and str(date_str).lower() != 'na':
            try:
                payment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                errors.append(_("Malformed date '%s', today's date will be used.") % date_str)
                payment_date = datetime.today().date()
        else:
            payment_date = datetime.today().date()

        return fields.Date.to_string(payment_date), errors
    
    def _get_receiptbook(self, company, errors, log_item=None):
        """
        Searches for the company's receiptbook.
        First tries with the DataReader one, then automatic one, if not found searches for any.
        """
        # First try to find DataReader receiptbook
        receiptbook = self.env['account.payment.receiptbook'].sudo().search([
            ('is_datareader_receiptbook', '=', True),
            ('company_id', '=', company.id),
            ('partner_type', '=', 'customer')
        ], limit=1)

        if not receiptbook:
            # If no DataReader receiptbook, try automatic one
            receiptbook = self.env['account.payment.receiptbook'].sudo().search([
                ('is_automatic_receiptbook', '=', True),
                ('company_id', '=', company.id),
                ('partner_type', '=', 'customer')
            ], limit=1)

        if not receiptbook:
            errors.append(_("No DataReader or automatic receiptbook found for company '%s'.") % company.name)
            receiptbook = self.env['account.payment.receiptbook'].sudo().search([
                ('company_id', '=', company.id),
                ('partner_type', '=', 'customer')
            ], limit=1)

            if not receiptbook:
                errors.append(_("No receiptbook found for company '%s'.") % company.name)
                if log_item:
                    log_item.write({'message': "\n".join(errors)})
                return None, errors

        return receiptbook, errors
    
    def _get_default_withholding_journal(self, data, partner, company, journal_name, errors, log_item=None):
        """
        Searches for a default journal in the partner and, if not found, in the company.
        Uses the currency to decide which journal corresponds.
        If none is found, returns None and accumulates errors.
        """
        journal = partner.with_company(company).datareader_default_partner_withholding_journal_id or False
        if not journal:
            errors.append(_("No default journal found for withholdings in contact '%s' for company '%s'.") % (partner.name, company.name))
            if log_item:
                log_item.write({'message': "\n".join(errors)})
            journal = company.datareader_default_withholding_journal_id or False
            if not journal:
                errors.append(_("No default journal found for withholdings in company settings either."))
                if log_item:
                    log_item.write({'message': "\n".join(errors)})
                    return None, errors

        return journal, errors
                
    def _get_default_journal(self, data, partner, company, journal_name, errors, log_item=None):
        """
        Searches for a default journal in the partner and, if not found, in the company.
        Uses the currency to decide which journal corresponds.
        If none is found, returns None and accumulates errors.
        """
        currency = data.get('currency')
        journal= False
        pay_method = data.get('pay_method').lower()
        if pay_method == 'cheque':
            journal = partner.with_company(company).datareader_default_partner_check_journal_id or False
            if not journal:
                errors.append(_("No default journal found for checks in contact '%s' for company '%s'.") % (partner.name, company.name))
                if log_item:
                    log_item.write({'message': "\n".join(errors)})
                journal = company.datareader_default_check_journal_id or False
        elif currency == 'ARS':
            journal = partner.with_company(company).datareader_default_partner_transfer_journal_id or False
            if not journal:
                errors.append(_("No default journal found (Pesos) in contact '%s' for company '%s'.") % (partner.name, company.name))
                if log_item:
                    log_item.write({'message': "\n".join(errors)})
                journal = company.datareader_default_transfer_journal_id or False
        elif currency == 'USD':
            journal = partner.with_company(company).datareader_default_partner_transfer_usd_journal_id or False
            if not journal:
                errors.append(_("No default journal found (Dollars) in contact '%s' for company '%s'.") % (partner.name, company.name))
                if log_item:
                    log_item.write({'message': "\n".join(errors)})
                journal = company.datareader_default_transfer_usd_journal_id or False
        else:
            errors.append(_("No currency type found in DataReader."))
            if log_item:
                log_item.write({'message': "\n".join(errors)})
                return None, errors

        if not journal:
            errors.append(_("No default journal found (%s) in contact or company, (%s, %s), process stopped.") % (pay_method, partner.name, company.name))
            if log_item:
                log_item.write({'message': "\n".join(errors)})
            return None, errors

        return journal, errors

    def create_from_datareader_json(self, data, connector):
        """
        Creates a receipt (account.payment.group) and its payment lines (account.payment)
        from a JSON coming from DataReader.
        """
        ir_config = self.env['ir.config_parameter'].sudo()
        # ver si se utiliza
        ap_post = eval(ir_config.get_param("datareader_odoo.datareader_post_account_payment", 'False'))
        apg_post = eval(ir_config.get_param("datareader_odoo.datareader_post_account_payment_group", 'False'))
        
        file_name = data.get("file_name")
        order_id = data.get("id")
        log_item = self._create_log_item(file_name, order_id)
        errors = []

        op_number, errors = self._validate_op_number(data, errors, log_item)
        if not op_number:
            connector.set_payment_order_readed(data.get("id"), True)
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
                errors.append(_("Payment method for withholdings not found, process stopped."))
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
                    _("Journal '%s' does not have a line for withholding payment method.") % ret_journal_id.display_name
                )
                log_item.write({'message': "\n".join(errors)})
                return log_item

        payment_date_str, errors = self._parse_payment_date(data.get('date'), errors)

        receiptbook_id, errors = self._get_receiptbook(company_id, errors, log_item)
        if not receiptbook_id:
            return log_item

        amount = float(data.get('amount_neto') or 0.0)
        if amount == 0.0:
            errors.append(_("No amount came in the order."))
        # Método de pago base
        pay_method = data.get('pay_method').lower()
        payment_method_obj = self.env['account.payment.method'].sudo()
        payment_method = payment_method_obj.search([
            ('code', '=', 'new_third_party_checks' if pay_method == 'cheque' else 'manual'),
            ('payment_type', '=', 'inbound')
        ], limit=1)
        if not payment_method:
            errors.append(_("No payment method %s for company %s.") % ('Check' if pay_method == 'cheque' else 'Manual', company_id.name))
            log_item.write({'message': "\n".join(errors)})
            return log_item
            
        payment_method_line = self.env['account.payment.method.line'].sudo().search([
            ('payment_method_id', '=', payment_method.id),
            ('journal_id', '=', journal_id.id),
        ], limit=1)

        if not payment_method_line:
            errors.append(
                _("Journal '%s' does not have a line configured for payment method '%s'.") % (journal_id.display_name, payment_method.name)
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
                errors.append(_("Withholding tax not found for %s, datareader_custom_identifier field may need to be configured") % ret_name)
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

            missings = self._validate_required_fields(
                ret_payment_vals,
                ['partner_id', 'amount', 'date', 'journal_id', 'payment_method_line_id', 'tax_withholding_id', 'withholding_number']
            )
            if not missings:
                ret_account_payment = ret_account_payment_obj.create(ret_payment_vals)
                log_item.write({'message': "\n".join(errors)})
            else:
                errors.append(_("Missing required fields for withholding: %s") % ', '.join(missings))
                log_item.write({'message': "\n".join(errors)})
                return log_item
            
        if partner_id.datareader_auto_payment_post and payment_method != 'cheque' and payment_group.payment_difference == 0:
            payment_group.post()
            
        return log_item

    def _normalize_invoice_number(self, number):
        """
        Normalizes invoice/receipt numbers:
        - If it has more than 8 digits, separates point of sale and number (last 8 digits always)
        - If it has 8 digits or less, fills with zeros on the left
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
        Searches and links the corresponding invoices to the payment lines.
        - Normalizes invoice numbers using _normalize_invoice_number
        - Matches exactly if point of sale comes, can be 1-12345678 or 00001-12345678
        - If only brings the number (8 digits), makes comparison with the last 8 digits of the customer's invoices to pay
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
                    _("Invoice %s not found for partner %s - invoice in odoo format (%s)") %
                    (line.get('number'), payment_group.commercial_partner_id.name, norm_line_number)
                )
                missing_found = True
        if missing_found:
            if len(found_moves) > 0:
                errors.append(
                    _("Not all invoices were allocated")
                )
                payment_group.to_pay_move_line_ids = [(6, 0, found_moves)]
                payment_group.state = 'draft'
        else:
            payment_group.to_pay_move_line_ids = [(6, 0, found_moves)] if found_moves else [(6, 0, 0)]

    def action_connect(self):
        ir_config = self.env['ir.config_parameter'].sudo()
        download_files = eval(ir_config.get_param("datareader_odoo.download_files", 'True'))
        download_first_batch = eval(ir_config.get_param("datareader_odoo.download_first_batch", 'False'))
        connector = self.env["datareader.connector"].get_connector()

        processed_orders = []  # Lista para trackear órdenes procesadas
        failed_orders = []
        
        try:
            connector.login()
            while True:
                orders = connector.get_payment_orders()
                if not orders:
                    break

                self.write({
                    "last_token": connector._token,
                    "last_connection": fields.Datetime.now(),
                })

                message = _("Successful connection.\nReceived %s payment orders.") % len(orders)
                all_files_downloaded = []
                
                for order in orders:
                    order_id = order.get("id")
                    try:
                        log_item = self.create_from_datareader_json(order, connector)
                        log_item.json_data = order
                        
                        # Marcar como leída solo si se procesó exitosamente
                        connector.set_payment_order_readed(order_id, True)
                        processed_orders.append(order_id)
                        
                        if not log_item.payment_group_id and not 'Ya existe un recibo de pago' in log_item.message:
                            failed_orders.append(order_id)

                        file_name = order.get("file_name")
                        
                        attachment_status = _("Not downloaded")
                        if download_files and file_name:
                            try:
                                attachment = box.download_and_attach_file(log_item, file_name, folder_field='box_folder_id_op')
                                if attachment:
                                    attachment_status = _("Attached OP: %s") % attachment.name
                                    _logger.info(f"Archivo OP adjuntado: {attachment.name}")
                                    ret_attachments = box.download_and_attach_retentions(log_item, file_name, folder_field='box_folder_id_withholding')
                                    if ret_attachments:
                                        attachment_status += _(" | Withholdings: %s") % [a.name for a in ret_attachments]
                                else:
                                    attachment_status = "No se encontró el archivo de OP en Box"
                            except Exception as e:
                                attachment_status = f"Error descargando: {str(e)}"
                                _logger.error(f"Error descargando y adjuntando {file_name}: {e}")

                        all_files_downloaded.append(f"{file_name}: {attachment_status}")
                        
                    except Exception as e:
                        # Si hay error procesando una orden, agregar a failed_orders y revertir
                        failed_orders.append(order_id)
                        error_msg = f"Error procesando orden {order_id}: {str(e)}"
                        _logger.error(error_msg)
                        
                        # Revertir la orden marcada como leída
                        try:
                            connector.set_payment_order_readed(order_id, False)
                            processed_orders.remove(order_id) if order_id in processed_orders else None
                        except:
                            pass
                        
                        # Mostrar error en chatter
                        self.message_post(body=error_msg, message_type='notification')
                        
                message += f"\nArchivos descargados: {all_files_downloaded}"
                _logger.info(message)
                
                if download_first_batch:
                    break
                    
            # Revertir órdenes fallidas
            for order_id in failed_orders:
                try:
                    connector.set_payment_order_readed(order_id, False)
                except:
                    pass

        except Exception as e:
            # En caso de error general, revertir TODAS las órdenes procesadas
            error_message = f"Error al conectar u obtener órdenes: {str(e)}"
            _logger.error(error_message)
            
            # Revertir todas las órdenes que se marcaron como leídas
            for order_id in processed_orders:
                try:
                    connector.set_payment_order_readed(order_id, False)
                except:
                    pass
            
            # Mostrar error en chatter
            self.message_post(body=error_message, message_type='notification')
            
            raise UserError(error_message)

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
    order_id = fields.Char(string="ID Orden", help="ID de la orden de pago en el conector DataReader")
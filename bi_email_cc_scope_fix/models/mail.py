import base64
import logging
import re
import smtplib

import psycopg2

from odoo import _, api, tools
from odoo.addons.base.models.ir_mail_server import MailDeliveryException
from odoo.tools.safe_eval import safe_eval

from odoo.addons.bi_email_cc.models.mail import MailMail as BiEmailCCMailMail

_logger = logging.getLogger(__name__)


@api.model
def create(self, values):
    """Scope the CC/BCC/reply-to lookup to the record being sent instead of the
    globally most recent wizard (bi_email_cc bug: leaks data across concurrent
    sends of different invoices/orders)."""
    model = False
    res_id = False
    message_id = values.get("mail_message_id", False)
    if message_id:
        message = self.env["mail.message"].browse(message_id)
        model = message.model
        res_id = message.res_id

    if model == "sale.order" and res_id:
        data = self.env["mail.compose.message"].sudo().search(
            [("model", "=", "sale.order"), ("res_id", "=", res_id)],
            order="id desc", limit=1,
        )
        if data.is_cc:
            values.update({"cc_partner_ids": [(6, 0, data.cc_partner_ids.ids)]})
        if data.is_bcc:
            values.update({"bcc_partner_ids": [(6, 0, data.bcc_partner_ids.ids)]})
        if data.is_reply:
            values.update({"rply_partner_id": int(data.rply_partner_id)})

    if model == "account.move" and res_id:
        record = self.env["account.invoice.send"].sudo().search(
            [("invoice_ids", "in", [res_id])], order="id desc", limit=1,
        )
        if record.is_cc:
            values.update({"cc_partner_ids": [(6, 0, record.cc_partner_ids.ids)]})
        if record.is_bcc:
            values.update({"bcc_partner_ids": [(6, 0, record.bcc_partner_ids.ids)]})
        if record.is_reply:
            values.update({"rply_partner_id": int(record.rply_partner_id)})

    # Skip bi_email_cc's own (buggy) create() and go straight to its parent,
    # since we already computed the correctly-scoped values above.
    return super(BiEmailCCMailMail, self).create(values)


# Patch bi_email_cc's create() in place, without forking the submodule.
BiEmailCCMailMail.create = create


def _send(self, auto_commit=False, raise_exception=False, smtp_session=None):
    """Same as bi_email_cc._send(), fixing 'mail_id' -> 'mail_mail_id' (that
    field does not exist on mail.notification), which made every mail sent
    through this override raise ValueError before ever reaching the SMTP
    server, always ending in state 'exception'."""
    IrMailServer = self.env['ir.mail_server']
    IrAttachment = self.env['ir.attachment']
    for mail_id in self.ids:
        success_pids = []
        failure_type = None
        processing_pid = None
        mail = None
        try:
            mail = self.browse(mail_id)
            if mail.state != 'outgoing':
                if mail.state != 'exception' and mail.auto_delete:
                    mail.sudo().unlink()
                continue

            # remove attachments if user send the link with the access_token
            body = mail.body_html or ''
            attachments = mail.attachment_ids
            for link in re.findall(r'/web/(?:content|image)/([0-9]+)', body):
                attachments = attachments - IrAttachment.browse(int(link))

            # load attachment binary data with a separate read(), as prefetching all
            # `datas` (binary field) could bloat the browse cache, triggerring
            # soft/hard mem limits with temporary data.
            attachments = [(a['name'], base64.b64decode(a['datas']), a['mimetype'])
                           for a in attachments.sudo().read(['name', 'datas', 'mimetype'])]

            # specific behavior to customize the send email for notified partners
            email_list = []
            email_cc_list = []
            email_bcc_list = []
            if mail.email_to:
                email_list.append(mail._send_prepare_values())
            for partner in mail.cc_partner_ids:
                email_cc_list += mail._send_prepare_values(
                    partner=partner).get('email_to')
            for partner in mail.bcc_partner_ids:
                email_bcc_list += mail._send_prepare_values(
                    partner=partner).get('email_to')

            for partner in mail.recipient_ids:
                values = mail._send_prepare_values(partner=partner)
                values['partner_id'] = partner
                email_list.append(values)

            headers = {}
            ICP = self.env['ir.config_parameter'].sudo()
            bounce_alias = ICP.get_param("mail.bounce.alias")
            catchall_domain = ICP.get_param("mail.catchall.domain")
            if bounce_alias and catchall_domain:
                if mail.mail_message_id.is_thread_message():
                    headers['Return-Path'] = '%s+%d-%s-%d@%s' % (bounce_alias, mail.id, mail.model, mail.res_id, catchall_domain)
                else:
                    headers['Return-Path'] = '%s+%d@%s' % (bounce_alias, mail.id, catchall_domain)
            if mail.headers:
                try:
                    headers.update(safe_eval(mail.headers))
                except Exception:
                    pass

            # Writing on the mail object may fail (e.g. lock on user) which
            # would trigger a rollback *after* actually sending the email.
            # To avoid sending twice the same email, provoke the failure earlier
            mail.write({
                'state': 'exception',
                'failure_reason': _('Error without exception. Probably due do sending an email without computed recipients.'),
            })
            # Update notification in a transient exception state to avoid concurrent
            # update in case an email bounces while sending all emails related to current
            # mail record.
            notifs = self.env['mail.notification'].search([
                ('notification_type', '=', 'email'),
                ('mail_mail_id', 'in', mail.ids),
                ('notification_status', 'not in', ('sent', 'canceled'))
            ])
            if notifs:
                notif_msg = _('Error without exception. Probably due do concurrent access update of notification records. Please see with an administrator.')
                notifs.sudo().write({
                    'notification_status': 'exception',
                    'failure_type': 'UNKNOWN',
                    'failure_reason': notif_msg,
                })
                # `test_mail_bounce_during_send`, force immediate update to obtain the lock.
                # see rev. 56596e5240ef920df14d99087451ce6f06ac6d36
                notifs.flush(fnames=['notification_status', 'failure_type', 'failure_reason'], records=notifs)

            # build an RFC2822 email.message.Message object and send it without queuing
            res = None
            for email in email_list:
                msg = IrMailServer.build_email(
                    email_from = mail.email_from,
                    email_to = email.get('email_to'),
                    subject = mail.subject,
                    body = email.get('body'),
                    body_alternative = email.get('body_alternative'),
                    reply_to = mail.reply_to,
                    attachments = attachments,
                    message_id = mail.message_id,
                    references = mail.references,
                    object_id = mail.res_id and ('%s-%s' % (mail.res_id, mail.model)),
                    subtype = 'html',
                    subtype_alternative = 'plain',
                    email_cc = tools.email_split(mail.email_cc)+ email_cc_list,
                    email_bcc = tools.email_split(mail.email_bcc) + email_bcc_list,
                    headers = headers
                )

                processing_pid = email.pop("partner_id", None)
                try:
                    res = IrMailServer.send_email(
                        msg, mail_server_id=mail.mail_server_id.id, smtp_session=smtp_session)
                    if processing_pid:
                        success_pids.append(processing_pid)
                    processing_pid = None
                except AssertionError as error:
                    if str(error) == IrMailServer.NO_VALID_RECIPIENT:
                        failure_type = "RECIPIENT"
                        # No valid recipient found for this particular
                        # mail item -> ignore error to avoid blocking
                        # delivery to next recipients, if any. If this is
                        # the only recipient, the mail will show as failed.
                        _logger.info("Ignoring invalid recipients for mail.mail %s: %s",
                                     mail.message_id, email.get('email_to'))
                    else:
                        raise
            if res:  # mail has been sent at least once, no major exception occured
                mail.write({'state': 'sent', 'message_id': res, 'failure_reason': False})
                _logger.info('Mail with ID %r and Message-Id %r successfully sent', mail.id, mail.message_id)
                # /!\ can't use mail.state here, as mail.refresh() will cause an error
                # see revid:odo@openerp.com-20120622152536-42b2s28lvdv3odyr in 6.1
            mail._postprocess_sent_message(success_pids=success_pids, failure_type=failure_type)
        except MemoryError:
            # prevent catching transient MemoryErrors, bubble up to notify user or abort cron job
            # instead of marking the mail as failed
            _logger.exception(
                'MemoryError while processing mail with ID %r and Msg-Id %r. Consider raising the --limit-memory-hard startup option',
                mail.id, mail.message_id)
            # mail status will stay on ongoing since transaction will be rollback
            raise
        except (psycopg2.Error, smtplib.SMTPServerDisconnected):
            # If an error with the database or SMTP session occurs, chances are that the cursor
            # or SMTP session are unusable, causing further errors when trying to save the state.
            _logger.exception(
                'Exception while processing mail with ID %r and Msg-Id %r.',
                mail.id, mail.message_id)
            raise
        except Exception as e:
            failure_reason = tools.ustr(e)
            _logger.exception('failed sending mail (id: %s) due to %s', mail.id, failure_reason)
            mail.write({'state': 'exception', 'failure_reason': failure_reason})
            mail._postprocess_sent_message(success_pids=success_pids, failure_reason=failure_reason, failure_type='UNKNOWN')
            if raise_exception:
                if isinstance(e, (AssertionError, UnicodeEncodeError)):
                    if isinstance(e, UnicodeEncodeError):
                        value = "Invalid text: %s" % e.object
                    else:
                        # get the args of the original error, wrap into a value and throw a MailDeliveryException
                        # that is an except_orm, with name and value as arguments
                        value = '. '.join(e.args)
                    raise MailDeliveryException(_("Mail Delivery Failed"), value)
                raise

        if auto_commit is True:
            self._cr.commit()
    return True


BiEmailCCMailMail._send = _send

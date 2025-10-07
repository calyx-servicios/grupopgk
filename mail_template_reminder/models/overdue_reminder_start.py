# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)

MOD = "account_invoice_overdue_reminder"

class OverdueReminderStart(models.TransientModel):
    _inherit = 'overdue.reminder.start'

    def run(self):
        self.ensure_one()
        if not self.up_to_date:
            raise UserError(
                _(
                    "In order to start overdue reminders, you must make sure that "
                    "customer payments are up-to-date."
                )
            )
        if self.start_days < 0:
            raise UserError(_("The trigger delay cannot be negative."))
        if self.min_interval_days < 1:
            raise UserError(
                _("The minimum delay since last reminder must be strictly positive.")
            )
        if self.company_id:
            template = self.env['mail.template'].search([
                ('is_reminder_template', '=', True),
                ('company_ids', 'in', [self.company_id.id])
            ], limit=1)
            
            if not template:
                raise UserError(_(
                    "No hay plantillas de recordatorio disponibles para la compañía '%s'. "
                    "Por favor, cree una plantilla de recordatorio o asigne una a esta compañía "
                    "antes de continuar con los recordatorios de facturas vencidas."
                ) % self.company_id.name)

        amo = self.env["account.move"]
        ajo = self.env["account.journal"]
        rpo = self.env["res.partner"]
        orso = self.env["overdue.reminder.step"]
        user_id = self.env.user.id
        existing_actions = orso.search([("user_id", "=", user_id)])
        existing_actions.unlink()
        payment_journals = ajo.search(
            [
                ("company_id", "=", self.company_id.id),
                ("type", "in", ("bank", "cash")),
            ]
        )
        sale_journals = ajo.search(
            [
                ("company_id", "=", self.company_id.id),
                ("type", "=", "sale"),
            ]
        )
        today = fields.Date.context_today(self)
        min_interval_date = today - relativedelta(days=self.min_interval_days)
        # It is important to understand this: there are 2 search on invoice :
        # 1. a first search to know if a partner must be reminded or not
        # 2. a second search to get the invoices to remind for that partner
        # There are some slight differences between these 2 searches;
        # for example: search 1 compares due_date to (today + start_days)
        # whereas search 2 compares due_date to today
        base_domain = self._prepare_base_domain()
        domain = self._prepare_remind_trigger_domain(base_domain)
        rg_res = amo.read_group(
            domain,
            ["commercial_partner_id", "amount_residual_signed"],
            ["commercial_partner_id"],
        )
        # Sort by residual amount desc
        rg_res_sorted = sorted(
            rg_res, key=lambda to_sort: to_sort["amount_residual_signed"], reverse=True
        )
        action_ids = []
        for rg_re in rg_res_sorted:
            commercial_partner_id = rg_re["commercial_partner_id"][0]
            commercial_partner = rpo.browse(commercial_partner_id)
            vals = self._prepare_reminder_step(
                commercial_partner,
                base_domain,
                min_interval_date,
                payment_journals,
                sale_journals,
            )
            if vals:
                action = orso.create(vals)
                action_ids.append(action.id)
        if not action_ids:
            raise UserError(_("There are no overdue reminders."))
        if self.interface == "onebyone":
            xid = MOD + ".overdue_reminder_step_onebyone_action"
            action = self.env.ref(xid).sudo().read()[0]
            action["res_id"] = action_ids[0]
        elif self.interface == "mass":
            action = orso.goto_list_view()
        return action

    def _prepare_reminder_step(
        self,
        commercial_partner,
        base_domain,
        min_interval_date,
        payment_journals,
        sale_journals,
    ):
        vals = super()._prepare_reminder_step(
            commercial_partner,
            base_domain,
            min_interval_date,
            payment_journals,
            sale_journals,
        )
        
        if vals:
            template = self.env['mail.template'].search([
                ('is_reminder_template', '=', True),
                ('company_ids', 'in', [self.company_id.id])
            ], limit=1)
            
            if template:
                vals['reminder_template_id'] = template.id
        return vals

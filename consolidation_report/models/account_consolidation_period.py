from odoo import api, fields, models, _
from datetime import date, timedelta, datetime
import calendar

class AccountConsolidationPeriod(models.Model):
    _name = 'account.consolidation.period'
    _description = 'Account consolidation period'

    year = fields.Integer(default=lambda self: self._default_year(), help='Year of the period', string='Year')
    month = fields.Integer(default=lambda self: self._default_month(), help='Month of the period', string='Month')
    period = fields.Char(compute="_compute_period", string='Period')
    date_from = fields.Date('From', readonly=True, compute="_compute_dates")
    date_to = fields.Date('To', readonly=True, compute="_compute_dates")
    consolidation_companies = fields.One2many('account.consolidation.company', 'account_consolidation_report_id', string='Configurations Consolidations')
    name = fields.Char(compute='_compute_name', store=True)

    @api.model
    def default_get(self, fields):
        res = super(AccountConsolidationPeriod, self).default_get(fields)
        companies = self.env['res.company'].search([])
        consolidation_companies = []
        for company in companies:
            consolidation_companies.append((0, 0, {
                'company_id': company.id,
                'currency_id': company.currency_id.id,
            }))
        res.update({
            'consolidation_companies': consolidation_companies,
        })
        return res

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Already exists this period.')
    ]

    @api.depends('year', 'month')
    def _compute_name(self):
        for record in self:
            record.name = _('Period: ') + '%d/%02d' % (record.year, record.month)

    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, '%s%.2d' % (rec.year, rec.month)))
        return res

    @staticmethod
    def _last_month():
        today = date.today()
        first = today.replace(day=1)
        return first - timedelta(days=1)

    def _default_year(self):
        return self._last_month().year

    def _default_month(self):
        return self._last_month().month

    @api.onchange('year', 'month')
    def _compute_period(self):
        for reg in self:
            reg.period = '%s/%s' % (reg.year, reg.month)

    @api.onchange('year', 'month')
    def _compute_dates(self):
        for rec in self:
            month = rec.month
            year = int(rec.year)
            first_day = datetime(year=year, month=month, day=1).date()
            last_day = datetime(year=year, month=month, day=calendar.monthrange(year, month)[1]).date()
            rec.date_from = first_day
            rec.date_to = last_day
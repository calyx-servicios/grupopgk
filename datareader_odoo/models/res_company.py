from odoo import models, fields, api, _
import re

class ResCompany(models.Model):
    _inherit = 'res.company'

    datareader_default_transfer_journal_id = fields.Many2one(
        'account.journal',
        string=_('Diario para Transferencias'),
        domain="[('type', '=', 'bank'), ('active', '=', True)]",
        help=_('Diario usado por defecto para pagos por transferencia')
    )

    datareader_default_check_journal_id = fields.Many2one(
        'account.journal',
        string=_('Diario para Cheques'),
        domain="[('type', '=', 'bank'), ('active', '=', True)]",
        help=_('Diario usado por defecto para pagos con cheque depositado')
    )
    datareader_default_withholding_journal_id = fields.Many2one(
        'account.journal',
        string=_('Diario para Retenciones'),
        domain="[('type', '=', 'cash'), ('active', '=', True)]",
        help=_('Diario usado por defecto para retenciones')
    )

    @staticmethod
    def preprocess_siglas(name):
        """
        Transforma nombres con siglas separadas como 'A. R. M.' en 'A.R.M.',
        y también 'S. R. L.' en 'S.R.L.', preservando los puntos.
        """
        name = name or ''
        name = name.strip()

        # Junta siglas iniciales como 'A. R. M.' -> 'A.R.M.'
        # Solo si están al principio del string
        match = re.match(r'^((?:[A-Z]\.\s*){2,})(.*)', name, flags=re.IGNORECASE)
        if match:
            siglas_raw = match.group(1)  # ej: 'A. R. M.'
            resto = match.group(2)       # ej: 'Jordan S.R.L.'
            letras = re.findall(r'([A-Z])\.', siglas_raw, flags=re.IGNORECASE)
            siglas_unidas = '.'.join(letras) + '.'
            name = siglas_unidas + ' ' + resto.strip()

        # Junta siglas en cualquier parte tipo 'S. R. L.' -> 'S.R.L.'
        name = re.sub(r'\b([A-Z])\.\s+([A-Z])\.\s+([A-Z])\.', r'\1.\2.\3.', name, flags=re.IGNORECASE)

        return name.strip()

    def _ensure_normalized_record(self, name):
        self.ensure_one()

        normalized = self.env['normalized.text'].search([
            ('res_company_id', '=', self.id)
        ], limit=1)

        if not normalized:
            normalized = self.env['normalized.text'].create({
                'res_company_id': self.id,
            })

        aliases = self.env['normalized.text.items'].search([
            ('normalized_id', '=', normalized.id),
            ('is_real_name', '=', True),
        ])

        exists = any(alias.name == name for alias in aliases)

        if not exists:
            self.env['normalized.text.items'].create({
                'name': name,
                'is_real_name': True,
                'normalized_id': normalized.id,
            })

        else:
            self.env['normalized.text.items'].create({
                'name': name,
                'is_real_name': True,
                'normalized_id': normalized.id,
            })

    @api.model
    def create(self, vals):
        company = super().create(vals)
        if vals.get('name'):
            name_processed = self.preprocess_siglas(vals['name'])
            company._ensure_normalized_record(vals.get('name'))
            if name_processed.lower() != company.name.lower():
                company._ensure_normalized_record(name_processed)
        return company

    def write(self, vals):
        res = super().write(vals)
        if 'name' in vals:
            for company in self:
                original_name = vals['name']
                name_processed = self.preprocess_siglas(original_name)
                company._ensure_normalized_record(original_name)
                if name_processed.lower() != company.name.lower():
                    company._ensure_normalized_record(name_processed)
        return res

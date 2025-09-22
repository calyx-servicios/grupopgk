import re
import unicodedata
from pprint import pprint
from odoo import _

def preprocess_siglas(name):
    name = name or ''
    name = name.strip()

    match = re.match(r'^((?:[A-Z]\.\s*){2,})(.*)', name, flags=re.IGNORECASE)
    if match:
        siglas_raw = match.group(1)
        resto = match.group(2)
        letras = re.findall(r'([A-Z])\.', siglas_raw, flags=re.IGNORECASE)
        siglas_unidas = '.'.join(letras) + '.'
        name = siglas_unidas + ' ' + resto.strip()

    name = re.sub(r'\b([A-Z])\.\s+([A-Z])\.\s+([A-Z])\.', r'\1.\2.\3.', name, flags=re.IGNORECASE)

    return normalize_text(name)

def normalize_text(text):
    if not text:
        return ""

    text = text.lower()
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = text.replace('ñ', 'ñ')
    text = text.replace('.', '')
    text = re.sub(r'[^a-z0-9ñ]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def normalize_cuit(cuit_str):
    return ''.join(re.findall(r'\d', cuit_str or ''))


def find_record_by_cuit_or_name(env, model_name, name=None, cuit=None, errors=None):
    """
    Busca en res.partner, res.company o account.journal usando CUIT (si es partner) o nombre.
    Acumula errores en la lista 'errors'.
    """
    if errors is None:
        errors = []

    Model = env[model_name]
    AliasModel = env['normalized.text.items']
    record = False
    records = Model.browse()

    # --------------------
    # Validación por CUIT (solo para Contactos, campo cuit en la OP)
    if model_name == 'res.partner':
        if not cuit:
            errors.append(_("No CUIT for '%s'") % name)
        else:
            cuit_normalized = normalize_cuit(cuit)
            if len(cuit_normalized) != 11:
                errors.append(_("Invalid CUIT for '%s': %s") % (name, cuit))
            else:
                partner_ids = Model.search([('vat', '=', cuit_normalized)])
                if not partner_ids:
                    errors.append(_("No partner found for CUIT %s") % cuit)
                elif len(partner_ids) > 1:
                    # Buscar si hay algún partner con categoría 'Cliente'
                    client_partners = partner_ids.filtered(lambda p: 'Cliente' in p.category_id.mapped('name'))
                    if len(client_partners) == 1:
                        record = client_partners[0]
                        errors.append(_("Selected partner %s for CUIT %s because it has 'Cliente' category") % (record.id, cuit))
                        errors.append(_("Multiple partners found for CUIT %s: %s") % (cuit, [p.id for p in partner_ids]))
                    else:
                        record = False
                        if client_partners:
                            errors.append(_("Multiple partners with 'Cliente' category found for CUIT %s: %s") % (cuit, [p.id for p in client_partners]))
                        else:
                            errors.append(_("No partner with 'Cliente' category found for CUIT %s. Available partners: %s") % (cuit, [p.id for p in partner_ids]))
                else:
                    record = partner_ids[0]

    # --------------------
    # Validación por nombre si no se encontró por CUIT
    if not record and name:
        name_norm = normalize_text(name)
        name_alt = preprocess_siglas(name)
        normalize_model_type = 'normalized_id.' + model_name.replace('.', '_') + '_id'
        field_name = model_name.replace('.', '_') + '_id'
        domain = [
            '|',
                ('normalized_name', 'ilike', name_norm),
                ('normalized_name', 'ilike', name_alt),
            (normalize_model_type, '!=', False),
        ]
        if model_name == 'res.partner':
            domain.append((normalize_model_type + '.active', '=', True))
        aliases = AliasModel.search(domain) if name_norm != 'na' else False
        
        if aliases:
            normalized_ids = aliases.mapped('normalized_id').filtered(lambda n: getattr(n, field_name))                    
            records = normalized_ids.mapped(field_name)
            unique_records = list(set(records))
            
            if unique_records:
                if model_name == 'res.partner':
                    #real_partners = records.filtered(lambda p: not p.parent_id and p.id == p.commercial_partner_id.id)
                    if len(unique_records) == 1:
                        record = unique_records[0]
                    else:
                        # Buscar si hay algún partner con categoría 'Cliente'
                        client_partners = unique_records.filtered(lambda p: 'Cliente' in p.category_id.mapped('name'))
                        if len(client_partners) == 1:
                            record = client_partners[0]
                            errors.append(_("Selected partner %s for '%s' because it has 'Cliente' category") % (record.id, name))
                        else:
                            record = False
                            if client_partners:
                                errors.append(_("Multiple partners with 'Cliente' category found for '%s': %s") % (name, [p.id for p in client_partners]))
                            else:
                                errors.append(_("No partner with 'Cliente' category found for '%s'. Available partners: %s") % (name, [p.id for p in unique_records]))
                else:
                    if len(unique_records) > 1:
                        errors.append(
                            _("Multiple distinct records found for '%s' in %s: %s. Process stopped.") % (name, model_name, [r.id for r in unique_records])
                        )
                    record = unique_records[0]
            else:
                errors.append(_("No valid records found for '%s' in %s") % (name, model_name))
        else:
            if model_name != 'account.journal':
                errors.append(_("No alias found for '%s' in %s") % (name, model_name))
    return record, errors
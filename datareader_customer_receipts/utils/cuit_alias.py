import re
import unicodedata
from pprint import pprint

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


def _partner_has_journal(partner, journal_id, env):
    """
    Verifica si un partner tiene un journal específico configurado.
    """
    partner_with_company = partner.with_company(env.company)
    result = (
        partner_with_company.datareader_default_partner_transfer_journal_id.id == journal_id.id or
        partner_with_company.datareader_default_partner_transfer_usd_journal_id.id == journal_id.id or
        partner_with_company.datareader_default_partner_check_journal_id.id == journal_id.id or
        partner_with_company.datareader_default_partner_withholding_journal_id.id == journal_id.id
    )
    pprint(f"[_partner_has_journal] Partner ID {partner.id} ({partner.name}), journal_id {journal_id.id if journal_id else None}: {result}")
    pprint(f"  - transfer: {partner_with_company.datareader_default_partner_transfer_journal_id.id if partner_with_company.datareader_default_partner_transfer_journal_id else None}")
    pprint(f"  - transfer_usd: {partner_with_company.datareader_default_partner_transfer_usd_journal_id.id if partner_with_company.datareader_default_partner_transfer_usd_journal_id else None}")
    pprint(f"  - check: {partner_with_company.datareader_default_partner_check_journal_id.id if partner_with_company.datareader_default_partner_check_journal_id else None}")
    pprint(f"  - withholding: {partner_with_company.datareader_default_partner_withholding_journal_id.id if partner_with_company.datareader_default_partner_withholding_journal_id else None}")
    return result


def _partner_has_any_journal(partner, env):
    """
    Verifica si un partner tiene algún journal configurado (cualquiera de los 4).
    """
    partner_with_company = partner.with_company(env.company)
    result = bool(
        partner_with_company.datareader_default_partner_transfer_journal_id or
        partner_with_company.datareader_default_partner_transfer_usd_journal_id or
        partner_with_company.datareader_default_partner_check_journal_id or
        partner_with_company.datareader_default_partner_withholding_journal_id
    )
    pprint(f"[_partner_has_any_journal] Partner ID {partner.id} ({partner.name}): {result}")
    pprint(f"  - transfer: {partner_with_company.datareader_default_partner_transfer_journal_id.id if partner_with_company.datareader_default_partner_transfer_journal_id else None}")
    pprint(f"  - transfer_usd: {partner_with_company.datareader_default_partner_transfer_usd_journal_id.id if partner_with_company.datareader_default_partner_transfer_usd_journal_id else None}")
    pprint(f"  - check: {partner_with_company.datareader_default_partner_check_journal_id.id if partner_with_company.datareader_default_partner_check_journal_id else None}")
    pprint(f"  - withholding: {partner_with_company.datareader_default_partner_withholding_journal_id.id if partner_with_company.datareader_default_partner_withholding_journal_id else None}")
    return result


def find_record_by_cuit_or_name(env, model_name, name=None, cuit=None, journal_id=None, errors=None):
    """
    Busca en res.partner, res.company o account.journal usando CUIT (si es partner) o nombre.
    Acumula errores en la lista 'errors'.
    
    Lógica mejorada para partners:
    - Caso 1: Hay CUIT y NO hay alias
    - Caso 2: NO hay CUIT pero SÍ hay alias
    - Caso 3: Hay CUIT y alias
    - Caso implícito: NO hay CUIT ni alias -> Retorna False
    """
    if errors is None:
        errors = []

    Model = env[model_name]
    AliasModel = env['normalized.text.items']
    record = False
    
    # ====================
    # LÓGICA MEJORADA PARA RES.PARTNER
    # ====================
    if model_name == 'res.partner':
        partners_by_cuit = Model.browse()
        partners_by_alias = Model.browse()
        
        # Buscar por CUIT
        if cuit and cuit != 'na':
            cuit_normalized = normalize_cuit(cuit)
            if len(cuit_normalized) != 11:
                errors.append(f"CUIT inválido para '{name or cuit}': {cuit}")
            else:
                partners_by_cuit = Model.search([('vat', '=', cuit_normalized)])
                if not partners_by_cuit:
                    errors.append(f"No se encontró partner para CUIT {cuit}")

        # Buscar por alias (nombre)
        if name and name != 'na':
            name_norm = normalize_text(name)
            name_alt = preprocess_siglas(name)
            normalize_model_type = 'normalized_id.res_partner_id'
            domain = [
                '|',
                    ('normalized_name', 'ilike', name_norm),
                    ('normalized_name', 'ilike', name_alt),
                (normalize_model_type, '!=', False),
                (normalize_model_type + '.active', '=', True),
            ]
            aliases = AliasModel.search(domain)
            
            if aliases:
                normalized_ids = aliases.mapped('normalized_id').filtered(lambda n: n.res_partner_id)
                partners_by_alias = normalized_ids.mapped('res_partner_id')
            # No agregar error aquí si no hay alias, porque puede que se encuentre por CUIT
            # El error se agregará solo si realmente no se encuentra el partner por ningún método
        
        # ====================
        # CASO 1: Hay CUIT y NO hay alias
        # ====================
        if partners_by_cuit and not partners_by_alias:
            if len(partners_by_cuit) == 0:
                return False, errors
            elif len(partners_by_cuit) == 1:
                # 1.1. Un partner → retorna ese partner
                return partners_by_cuit[0], errors
            else:
                # 1.2. Múltiples partners → PRIORIDAD: 1. Diarios, 2. Sin parent_id
                pprint("=" * 80)
                pprint("[CASO 1.2] Múltiples partners por CUIT")
                pprint(f"CUIT: {cuit}")
                pprint(f"Partners encontrados por CUIT: {len(partners_by_cuit)} - IDs: {partners_by_cuit.ids}")
                pprint(f"journal_id recibido: {journal_id.id if journal_id else None}")
                
                filtered_partners = partners_by_cuit
                
                # 1. Filtrar por diarios (SIEMPRE priorizar los que tienen diarios)
                if journal_id:
                    pprint("Buscando partners con journal específico...")
                    partners_with_specific_journal = partners_by_cuit.filtered(
                        lambda p: _partner_has_journal(p, journal_id, env)
                    )
                    pprint(f"Partners con journal específico: {len(partners_with_specific_journal)} - IDs: {partners_with_specific_journal.ids}")
                    if partners_with_specific_journal:
                        filtered_partners = partners_with_specific_journal
                    else:
                        pprint("No hay partners con journal específico, buscando con cualquier journal...")
                        partners_with_any_journal = partners_by_cuit.filtered(
                            lambda p: _partner_has_any_journal(p, env)
                        )
                        pprint(f"Partners con cualquier journal: {len(partners_with_any_journal)} - IDs: {partners_with_any_journal.ids}")
                        if partners_with_any_journal:
                            filtered_partners = partners_with_any_journal
                else:
                    # Aunque no haya journal_id específico, priorizar los que tienen algún journal configurado
                    pprint("No hay journal_id específico, buscando partners con cualquier journal...")
                    partners_with_any_journal = partners_by_cuit.filtered(
                        lambda p: _partner_has_any_journal(p, env)
                    )
                    pprint(f"Partners con cualquier journal: {len(partners_with_any_journal)} - IDs: {partners_with_any_journal.ids}")
                    if partners_with_any_journal:
                        filtered_partners = partners_with_any_journal
                
                pprint(f"Partners filtrados por diarios: {len(filtered_partners)} - IDs: {filtered_partners.ids}")
                
                # 2. Filtrar por sin parent_id (dentro de los que tienen diarios si aplica)
                partners_sin_parent = filtered_partners.filtered(lambda p: not p.parent_id)
                pprint(f"Partners sin parent_id: {len(partners_sin_parent)} - IDs: {partners_sin_parent.ids}")
                
                if len(partners_sin_parent) == 1:
                    # 1.2.1. Uno sin parent_id → retorna ese
                    pprint(f"✓ Retornando partner sin parent_id: ID {partners_sin_parent[0].id}")
                    return partners_sin_parent[0], errors
                elif len(partners_sin_parent) > 1:
                    # 1.2.2. Múltiples sin parent_id → error, retorna lista
                    pprint(f"✗ Múltiples partners sin parent_id: {partners_sin_parent.ids}")
                    errors.append(
                        f"Se encontraron múltiples partners sin parent_id para CUIT {cuit} "
                        f"(IDs: {partners_sin_parent.ids}). Se detiene el proceso."
                    )
                    return partners_sin_parent, errors
                elif len(filtered_partners) == 1:
                    # Si hay uno con diarios pero tiene parent_id, retornarlo
                    pprint(f"✓ Retornando partner con diarios (tiene parent_id): ID {filtered_partners[0].id}")
                    return filtered_partners[0], errors
                elif len(filtered_partners) > 1:
                    # Si hay múltiples con diarios pero todos tienen parent_id, retornar el primero
                    pprint(f"✓ Retornando primer partner con diarios (todos tienen parent_id): ID {filtered_partners[0].id}")
                    return filtered_partners[0], errors
                else:
                    # 1.2.3. Ninguno sin parent_id ni con diarios → error, retorna False
                    pprint(f"✗ Ningún partner con diarios ni sin parent_id")
                    errors.append(
                        f"Se encontraron múltiples partners para CUIT {cuit} (IDs: {partners_by_cuit.ids}), "
                        f"pero ninguno sin parent_id ni con diarios. Se detiene el proceso."
                    )
                    return False, errors
        
        # ====================
        # CASO 2: NO hay CUIT pero SÍ hay alias
        # ====================
        elif not partners_by_cuit and partners_by_alias:
            if len(partners_by_alias) == 0:
                # Solo aquí agregar el error, porque no hay CUIT y no se encontró por alias
                errors.append(f"No se encontró alias para '{name}' en res.partner")
                return False, errors
            elif len(partners_by_alias) == 1:
                # 2.1. Un partner → retorna ese partner
                return partners_by_alias[0], errors
            else:
                # 2.2. Múltiples partners → filtra por diario, luego por parent_id
                filtered_partners = partners_by_alias
                
                # Filtrar por diario si está disponible
                if journal_id:
                    # Primero: buscar partners que tengan el journal específico configurado
                    partners_with_specific_journal = filtered_partners.filtered(
                        lambda p: _partner_has_journal(p, journal_id, env)
                    )
                    if partners_with_specific_journal:
                        filtered_partners = partners_with_specific_journal
                    else:
                        # Si no hay ninguno con el journal específico, priorizar los que tienen algún journal configurado
                        partners_with_any_journal = filtered_partners.filtered(
                            lambda p: _partner_has_any_journal(p, env)
                        )
                        if partners_with_any_journal:
                            filtered_partners = partners_with_any_journal
                
                # Filtrar por sin parent_id
                partners_sin_parent = filtered_partners.filtered(lambda p: not p.parent_id)
                
                if len(partners_sin_parent) == 1:
                    return partners_sin_parent[0], errors
                elif len(partners_sin_parent) > 1:
                    errors.append(
                        f"Se encontraron múltiples partners sin parent_id para alias '{name}' "
                        f"(IDs: {partners_sin_parent.ids}). Se detiene el proceso."
                    )
                    return partners_sin_parent, errors
                else:
                    # Si no hay sin parent_id, intentar con los que tienen parent_id
                    if len(filtered_partners) == 1:
                        return filtered_partners[0], errors
                    else:
                        errors.append(
                            f"Se encontraron múltiples partners para alias '{name}' "
                            f"(IDs: {filtered_partners.ids}), pero ninguno sin parent_id. Se detiene el proceso."
                        )
                        return filtered_partners if len(filtered_partners) > 1 else False, errors
        
        # ====================
        # CASO 3: Hay CUIT y alias
        # ====================
        elif partners_by_cuit and partners_by_alias:
            # Buscar intersección entre partners por CUIT y por alias
            common_partners = partners_by_cuit & partners_by_alias
            
            # 3.1. Un CUIT y un alias → verifica coincidencia de IDs
            if len(partners_by_cuit) == 1 and len(partners_by_alias) == 1:
                if partners_by_cuit[0].id == partners_by_alias[0].id:
                    return partners_by_cuit[0], errors
                else:
                    errors.append(
                        f"El partner del CUIT {cuit} (ID: {partners_by_cuit[0].id}) "
                        f"no coincide con el partner del alias '{name}' (ID: {partners_by_alias[0].id}). "
                        f"Se detiene el proceso."
                    )
                    return False, errors
            
            # 3.2. Múltiples CUIT y un alias → busca coincidencia
            elif len(partners_by_cuit) > 1 and len(partners_by_alias) == 1:
                if partners_by_alias[0] in partners_by_cuit:
                    return partners_by_alias[0], errors
                else:
                    errors.append(
                        f"El partner del alias '{name}' (ID: {partners_by_alias[0].id}) "
                        f"no coincide con ninguno de los partners del CUIT {cuit} (IDs: {partners_by_cuit.ids}). "
                        f"Se detiene el proceso."
                    )
                    return False, errors
            
            # 3.3. Un CUIT y múltiples alias → busca coincidencia, luego aplica filtros
            elif len(partners_by_cuit) == 1 and len(partners_by_alias) > 1:
                pprint("=" * 80)
                pprint("[CASO 3.3] Un CUIT y múltiples alias")
                pprint(f"CUIT: {cuit}, Alias: {name}")
                pprint(f"Partners por CUIT: {len(partners_by_cuit)} - ID: {partners_by_cuit[0].id}")
                pprint(f"Partners por alias: {len(partners_by_alias)} - IDs: {partners_by_alias.ids}")
                pprint(f"journal_id recibido: {journal_id.id if journal_id else None}")
                
                # Verificar que el partner del CUIT esté en los partners del alias
                if partners_by_cuit[0] in partners_by_alias:
                    pprint("✓ El partner del CUIT está en los partners del alias")
                    # PRIORIDAD: 1. CUIT (ya tenemos partners_by_cuit[0])
                    #            2. Diarios (SIEMPRE priorizar)
                    #            3. Sin parent_id
                    partner_cuit = partners_by_cuit[0]
                    
                    # Verificar si tiene diarios (SIEMPRE verificar, no solo si hay journal_id)
                    has_journal = False
                    if journal_id:
                        has_journal = _partner_has_journal(partner_cuit, journal_id, env)
                    if not has_journal:
                        has_journal = _partner_has_any_journal(partner_cuit, env)
                    
                    # Verificar si no tiene parent_id
                    has_no_parent = not partner_cuit.parent_id
                    
                    pprint(f"Partner ID {partner_cuit.id} - has_journal: {has_journal}, has_no_parent: {has_no_parent}")
                    
                    # Si cumple todas las condiciones, retornarlo
                    if has_journal and has_no_parent:
                        pprint("✓ Retornando partner: tiene diarios Y no tiene parent_id")
                        return partner_cuit, errors
                    # Si tiene diarios pero tiene parent_id, aún así retornarlo (prioridad diarios > parent_id)
                    elif has_journal:
                        pprint("✓ Retornando partner: tiene diarios (aunque tiene parent_id)")
                        return partner_cuit, errors
                    # Si no tiene diarios pero no tiene parent_id, retornarlo
                    elif has_no_parent:
                        pprint("✓ Retornando partner: no tiene diarios pero no tiene parent_id")
                        return partner_cuit, errors
                    # Si no cumple ninguna, retornarlo de todas formas (es el único con el CUIT)
                    else:
                        pprint("✓ Retornando partner: es el único con el CUIT (sin diarios ni sin parent_id)")
                        return partner_cuit, errors
                else:
                    errors.append(
                    f"El partner del CUIT {cuit} (ID: {partners_by_cuit[0].id}) "
                    f"no coincide con ninguno de los partners del alias '{name}' (IDs: {partners_by_alias.ids}). "
                    f"Se detiene el proceso."
                )
                return False, errors
            
            # 3.4. Múltiples CUIT y múltiples alias → busca intersección
            elif len(partners_by_cuit) > 1 and len(partners_by_alias) > 1:
                pprint("=" * 80)
                pprint("[CASO 3.4] Múltiples CUIT y múltiples alias")
                pprint(f"CUIT: {cuit}, Alias: {name}")
                pprint(f"Partners por CUIT: {len(partners_by_cuit)} - IDs: {partners_by_cuit.ids}")
                pprint(f"Partners por alias: {len(partners_by_alias)} - IDs: {partners_by_alias.ids}")
                pprint(f"journal_id recibido: {journal_id.id if journal_id else None}")
                
                if common_partners:
                    pprint(f"Intersección (common_partners): {len(common_partners)} - IDs: {common_partners.ids}")
                    # PRIORIDAD: 1. CUIT (ya filtrado en common_partners)
                    #            2. Diarios (SIEMPRE priorizar los que tienen diarios)
                    #            3. Sin parent_id
                    filtered_common = common_partners
                    
                    # 2. Filtrar por diarios (SIEMPRE, prioridad sobre parent_id)
                    if journal_id:
                        pprint("Buscando partners con journal específico en intersección...")
                        # Primero: buscar partners que tengan el journal específico configurado
                        partners_with_specific_journal = common_partners.filtered(
                            lambda p: _partner_has_journal(p, journal_id, env)
                        )
                        pprint(f"Partners con journal específico: {len(partners_with_specific_journal)} - IDs: {partners_with_specific_journal.ids}")
                        if partners_with_specific_journal:
                            filtered_common = partners_with_specific_journal
                        else:
                            # Si no hay ninguno con el journal específico, priorizar los que tienen algún journal configurado
                            pprint("No hay partners con journal específico, buscando con cualquier journal...")
                            partners_with_any_journal = common_partners.filtered(
                                lambda p: _partner_has_any_journal(p, env)
                            )
                            pprint(f"Partners con cualquier journal: {len(partners_with_any_journal)} - IDs: {partners_with_any_journal.ids}")
                            if partners_with_any_journal:
                                filtered_common = partners_with_any_journal
                    else:
                        # Aunque no haya journal_id específico, priorizar los que tienen algún journal configurado
                        pprint("No hay journal_id específico, buscando partners con cualquier journal...")
                        partners_with_any_journal = common_partners.filtered(
                            lambda p: _partner_has_any_journal(p, env)
                        )
                        pprint(f"Partners con cualquier journal: {len(partners_with_any_journal)} - IDs: {partners_with_any_journal.ids}")
                        if partners_with_any_journal:
                            filtered_common = partners_with_any_journal
                    
                    pprint(f"Partners filtrados por diarios: {len(filtered_common)} - IDs: {filtered_common.ids}")
                    
                    # 3. Filtrar por sin parent_id (dentro de los que tienen diarios si aplica)
                    partners_sin_parent = filtered_common.filtered(lambda p: not p.parent_id)
                    pprint(f"Partners sin parent_id (de los filtrados por diarios): {len(partners_sin_parent)} - IDs: {partners_sin_parent.ids}")
                    
                    # Si hay uno sin parent_id y con diarios, retornarlo
                    if len(partners_sin_parent) == 1:
                        pprint(f"✓ Retornando partner sin parent_id y con diarios: ID {partners_sin_parent[0].id}")
                        return partners_sin_parent[0], errors
                    # Si hay múltiples sin parent_id, error
                    elif len(partners_sin_parent) > 1:
                        pprint(f"✗ Múltiples partners sin parent_id: {partners_sin_parent.ids}")
                        errors.append(
                            f"Se encontraron múltiples partners en la intersección de CUIT {cuit} y alias '{name}' "
                            f"sin parent_id (IDs: {partners_sin_parent.ids}). Se detiene el proceso."
                        )
                        return partners_sin_parent, errors
                    # Si no hay sin parent_id pero hay con diarios, retornar el primero con diarios
                    elif len(filtered_common) == 1:
                        pprint(f"✓ Retornando partner con diarios (tiene parent_id): ID {filtered_common[0].id}")
                        return filtered_common[0], errors
                    elif len(filtered_common) > 1:
                        # Si hay múltiples con diarios pero todos tienen parent_id, retornar el primero
                        pprint(f"✓ Retornando primer partner con diarios (todos tienen parent_id): ID {filtered_common[0].id}")
                        return filtered_common[0], errors
                    else:
                        # Si no hay con diarios, usar todos los common_partners y filtrar por sin parent_id
                        partners_sin_parent_all = common_partners.filtered(lambda p: not p.parent_id)
                        if len(partners_sin_parent_all) == 1:
                            return partners_sin_parent_all[0], errors
                        elif len(partners_sin_parent_all) > 1:
                            errors.append(
                                f"Se encontraron múltiples partners en la intersección de CUIT {cuit} y alias '{name}' "
                                f"sin parent_id (IDs: {partners_sin_parent_all.ids}). Se detiene el proceso."
                            )
                            return partners_sin_parent_all, errors
                        else:
                            errors.append(
                                f"Se encontraron múltiples partners en la intersección de CUIT {cuit} y alias '{name}' "
                                f"(IDs: {common_partners.ids}), pero ninguno sin parent_id ni con diarios. Se detiene el proceso."
                            )
                            return common_partners if len(common_partners) > 1 else False, errors
                else:
                    errors.append(
                        f"No hay intersección entre los partners del CUIT {cuit} (IDs: {partners_by_cuit.ids}) "
                        f"y los partners del alias '{name}' (IDs: {partners_by_alias.ids}). Se detiene el proceso."
                    )
                    return False, errors
        
        # ====================
        # CASO IMPLÍCITO: NO hay CUIT ni alias
        # ====================
        else:
            # Si hay name pero no se encontró alias ni CUIT, agregar el error
            if name and name != 'na' and not partners_by_cuit:
                errors.append(f"No se encontró alias para '{name}' en res.partner")
            return False, errors
            
    # ====================
    # LÓGICA ORIGINAL PARA OTROS MODELOS (res.company, account.journal, etc.)
    # ====================
    else:
        # Mantener lógica original para otros modelos
        if name:
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
            aliases = AliasModel.search(domain) if name_norm != 'na' else False
            
            if aliases:
                normalized_ids = aliases.mapped('normalized_id').filtered(lambda n: getattr(n, field_name))                    
                records = normalized_ids.mapped(field_name)
                # Obtener IDs únicos y luego buscar los registros
                if records:
                    # Asegurarse de que records.ids sea una lista antes de convertir a set
                    record_ids = list(records.ids) if hasattr(records, 'ids') and records.ids else []
                    if record_ids:
                        unique_ids = list(set(record_ids))
                        if unique_ids:
                            unique_records = Model.browse(unique_ids)
                            if len(unique_records) > 1:
                                errors.append(
                                    f"Se encontraron múltiples registros distintos para '{name}' en {model_name}: {unique_ids}. "
                                    f"Se detiene el proceso."
                                )
                            record = unique_records[0] if unique_records else False
                        else:
                            errors.append(f"No se encontraron registros válidos para '{name}' en {model_name}")
                    else:
                        errors.append(f"No se encontraron registros válidos para '{name}' en {model_name}")
                else:
                    errors.append(f"No se encontraron registros válidos para '{name}' en {model_name}")
            else:
                if model_name != 'account.journal':
                    errors.append(f"No se encontró alias para '{name}' en {model_name}")
        return record, errors
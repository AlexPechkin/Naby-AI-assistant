"""Local, deterministic pharmacist scenarios. Evidence occurrence is not truth.

No network, account access, signature, submission, dispensing or batch release.
All source selections remain proposals requiring the host's evidence binding.
"""
from collections import Counter
from datetime import date, datetime, timedelta
import calendar
from decimal import Decimal, InvalidOperation
import copy
import json
import re
from functools import wraps

FUNCTIONS = ('mdlp_marking', 'acceptance_control', 'drug_info', 'pharmacovigilance', 'gpp_sop')
GPP_INVENTORY = ('quality_system', 'personnel', 'acceptance', 'storage', 'dispensing',
                 'information', 'complaints', 'withdrawal', 'documentation', 'self_inspection', 'capa')
SOURCE_FIELDS = {'source_reference', 'edition', 'publication_date', 'effective_date', 'not_after', 'text'}


def _obj(value, required=(), optional=(), label='object'):
    if type(value) is not dict or not set(required) <= set(value) or set(value) - set(required) - set(optional):
        raise ValueError(label + '_fields')
    return value


def _rows(value, label, minimum=0, maximum=100):
    if type(value) is not list or not minimum <= len(value) <= maximum:
        raise ValueError(label + '_bounded_list_required')
    return value


def _text(value, label='text', maximum=2000):
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise ValueError(label + '_required')
    if any(ord(c) < 32 and c not in '\n\r\t' for c in value):
        raise ValueError(label + '_control_character')
    return value


def _day(value, label='date'):
    if type(value) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError(label + '_iso_date_required')
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(label + '_invalid') from None


def _number(value, label='number'):
    if type(value) not in (str, int) or not re.fullmatch(r'-?(?:0|[1-9]\d{0,14})(?:\.\d{1,8})?', str(value)):
        raise ValueError(label + '_exact_decimal_required')
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise ValueError(label + '_invalid') from None
    if not result.is_finite():
        raise ValueError(label + '_finite_required')
    return result


def _ref(value):
    return _text(value, 'source_reference', 200)


def _bounded(value, depth=0, budget=None):
    if budget is None:
        budget = [0]
    budget[0] += 1
    if depth > 24 or budget[0] > 20000:
        raise ValueError('scenario_structure_limit')
    if type(value) is dict:
        if len(value) > 100:
            raise ValueError('scenario_object_limit')
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError('string_keys_required')
            if key.endswith(('_verified', '_approved', '_confirmed', '_signed')) or key in {
                'approved', 'signed', 'verified', 'confirmed', 'authorized', 'compliant',
                'actual_success_at', 'last_verified_at', 'host_context', 'clearance',
                'batch_released', 'dispensing_allowed', 'submission_performed'}:
                raise ValueError('reserved_authority_field:' + key)
            _bounded(item, depth + 1, budget)
    elif type(value) is list:
        if len(value) > 500:
            raise ValueError('scenario_list_limit')
        for item in value:
            _bounded(item, depth + 1, budget)
    elif type(value) is str:
        if len(value) > 200000:
            raise ValueError('scenario_text_limit')
    elif value is not None and type(value) not in (int, bool):
        raise ValueError('json_exact_values_required')


def _base(data, required, optional=()):
    _bounded(data)
    _obj(data, ('as_of', 'jurisdiction', *required), optional, 'scenario')
    if data['jurisdiction'] != 'RU':
        raise ValueError('jurisdiction_RU_required')
    return _day(data['as_of'], 'as_of')


def _past(value, asof, label):
    d = _day(value, label)
    if d > asof:
        raise ValueError(label + '_after_as_of')
    return d


def _source(source, asof, validity_date=None):
    _obj(source, SOURCE_FIELDS - {'not_after'}, ('not_after',), 'selected_source')
    _ref(source['source_reference'])
    _text(source['edition'], 'edition')
    _text(source['text'], 'source_text', 200000)
    published = _past(source['publication_date'], asof, 'publication_date')
    effective = _past(source['effective_date'], asof, 'effective_date')
    target = asof if validity_date is None else validity_date
    if effective > target:
        raise ValueError('selected_source_not_effective_on_event_date')
    if source.get('not_after') is not None:
        end = _day(source['not_after'], 'not_after')
        if end < effective or target > end:
            raise ValueError('selected_source_outside_provided_period')
    return dict(source_reference=source['source_reference'], edition=source['edition'],
                publication_date=published.isoformat(), effective_date=effective.isoformat(),
                not_after=source.get('not_after'))


def _excerpt(row, source=None):
    _ref(row['source_reference'])
    _text(row['excerpt'], 'excerpt', 20000)
    if source is not None:
        if row['source_reference'] != source['source_reference']:
            raise ValueError('excerpt_selected_source_mismatch')
        if row['excerpt'] not in source['text']:
            raise ValueError('excerpt_not_in_selected_text')


def _result(function, data, **values):
    return dict(function=function, as_of=data['as_of'], jurisdiction='RU', status='analysis_only',
                analysis_only=True, private=True, external_network_used=False,
                source_semantics_verified=False, current_legal_applicability_verified=False,
                dispensing_performed=False, batch_released=False, report_submitted=False,
                signature_applied=False, status_codes=['review_by_pharmacist'], **values)


def _display(code):
    return json.dumps(code, ensure_ascii=True)[1:-1]


def _parse_code(code):
    """One documented RU medicine layout, NOT a general GS1 or crypto validator.

    01 + GTIN14 + 21 + serial13 + GS + 91 + key4 + GS + 92 + crypto44.
    Scanner symbology identifier ]d2 is optional. ASCII GS is never stripped.
    Printable punctuation is supported; cryptographic content is opaque.
    """
    if type(code) is not str or not 1 <= len(code) <= 200:
        raise ValueError('bounded_code_string_required')
    raw = code[3:] if code.startswith(']d2') else code
    result = dict(code_display=_display(code), format='ru_medicine_gs1_full',
                  parse_status='unsupported_structure', crypto_status='not_checked', authenticity='not_assessed')
    if not (len(raw) == 85 and raw[:2] == '01' and raw[2:16].isascii() and raw[2:16].isdigit()
            and raw[16:18] == '21' and raw[31:34] == '\x1d91' and raw[38:41] == '\x1d92'):
        return result, 'raw:' + _display(raw)
    for block in (raw[18:31], raw[34:38], raw[41:]):
        if any(not 33 <= ord(ch) <= 126 for ch in block):
            return result, 'raw:' + _display(raw)
    gtin = raw[2:16]
    check = (10 - sum(int(ch) * (3 if i % 2 == 0 else 1)
                      for i, ch in enumerate(reversed(gtin[:-1]))) % 10) % 10
    result.update(parse_status='structure_recognized', gtin=gtin, serial_display=_display(raw[18:31]),
                  gtin_check_digit='matches' if check == int(gtin[-1]) else 'mismatch')
    return result, gtin + ':' + raw[18:31]


def mdlp_marking(data):
    asof = _base(data, ('operation', 'expected', 'actual', 'snapshot_date', 'source_reference'))
    if data['operation'] not in ('acceptance', 'sale', 'write_off', 'return', 'discrepancy'):
        raise ValueError('unsupported_mdlp_operation')
    snapshot = _past(data['snapshot_date'], asof, 'snapshot_date')
    _ref(data['source_reference'])
    buckets = []
    for side in ('expected', 'actual'):
        records = []
        for row in _rows(data[side], side, maximum=300):
            _obj(row, ('code', 'series'), ('status', 'status_reference'), 'mdlp_record')
            _text(row['series'], 'series', 200)
            if row.get('status') is not None:
                _text(row['status'], 'status', 200)
                _ref(row.get('status_reference'))
            elif row.get('status_reference') is not None:
                raise ValueError('status_reference_without_status')
            parsed, identity = _parse_code(row['code'])
            records.append(dict(identity=identity, parsed=parsed, series=row['series'],
                                supplied_status=row.get('status', 'unknown'),
                                status_reference=row.get('status_reference'), raw=row['code']))
        buckets.append(records)
    expected, actual = buckets
    if not expected and not actual:
        raise ValueError('mdlp_records_required')
    ec = Counter(r['identity'] for r in expected)
    ac = Counter(r['identity'] for r in actual)
    issues = []
    for side, rows, counts in (('expected', expected, ec), ('actual', actual, ac)):
        seen = set()
        for row in rows:
            identity = row['identity']
            if counts[identity] > 1 and identity not in seen:
                issues.append(dict(code='duplicate_codes', side=side, code_display=row['parsed']['code_display'], count=counts[identity]))
            seen.add(identity)
            if row['parsed']['parse_status'] != 'structure_recognized' or row['parsed'].get('gtin_check_digit') != 'matches':
                issues.append(dict(code='code_structure_issue', side=side, code_display=row['parsed']['code_display']))
            if row['supplied_status'] == 'unknown':
                issues.append(dict(code='status_missing', side=side, code_display=row['parsed']['code_display']))
    for identity in sorted(set(ec) | set(ac)):
        left = [r for r in expected if r['identity'] == identity]
        right = [r for r in actual if r['identity'] == identity]
        row = (left or right)[0]
        difference = ac[identity] - ec[identity]
        if difference:
            issues.append(dict(code='extra_codes' if difference > 0 else 'missing_codes',
                               code_display=row['parsed']['code_display'], count=abs(difference)))
        if left and right:
            if {r['series'] for r in left} != {r['series'] for r in right}:
                issues.append(dict(code='series_mismatch', code_display=row['parsed']['code_display']))
            if {r['supplied_status'] for r in left} != {r['supplied_status'] for r in right}:
                issues.append(dict(code='status_mismatch', code_display=row['parsed']['code_display']))
            if {r['raw'].removeprefix(']d2') for r in left} != {r['raw'].removeprefix(']d2') for r in right}:
                issues.append(dict(code='same_identifier_different_payload', code_display=row['parsed']['code_display']))
    def public(rows):
        return [dict(r['parsed'], series=r['series'], supplied_status=r['supplied_status'],
                     status_reference=r['status_reference']) for r in rows]
    return _result('mdlp_marking', data, operation=data['operation'], expected=public(expected), actual=public(actual),
                   discrepancies=issues, snapshot_date=snapshot.isoformat(), snapshot_age_days=(asof-snapshot).days,
                   source_reference=data['source_reference'], next_steps=['no_online_check', 'crypto_not_checked', 'review_by_pharmacist'])


def _stamp(value, label):
    if type(value) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})', value):
        raise ValueError(label + '_offset_timestamp_required')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError(label + '_invalid') from None
    if parsed.utcoffset() is None:
        raise ValueError(label + '_timezone_required')
    return parsed


def _expiry(record, asof):
    _obj(record, ('label_value', 'semantics', 'source_reference'), ('observation_at',), 'expiry')
    value = _text(record['label_value'], 'expiry_label', 1000)
    _ref(record['source_reference'])
    mode = record['semantics']
    boundary = None
    expired = None
    if mode == 'unresolved':
        if record.get('observation_at') is not None:
            raise ValueError('unresolved_expiry_with_timestamp')
    elif mode in ('end_of_day', 'end_of_month'):
        if record.get('observation_at') is not None:
            raise ValueError('date_expiry_does_not_accept_timestamp')
        if mode == 'end_of_day':
            last_day = _day(value, 'expiry_day')
        else:
            if not re.fullmatch(r'\d{4}-(?:0[1-9]|1[0-2])', value):
                raise ValueError('expiry_month_required')
            year, month = map(int, value.split('-'))
            if year == 0:
                raise ValueError('expiry_month_invalid')
            last_day = date(year, month, calendar.monthrange(year, month)[1])
        if last_day == date.max:
            raise ValueError('expiry_boundary_out_of_range')
        boundary_day = last_day + timedelta(days=1)
        boundary = boundary_day.isoformat()
        expired = asof >= boundary_day
    elif mode == 'exclusive_instant':
        instant = _stamp(value, 'expiry_instant')
        observation = _stamp(record.get('observation_at'), 'expiry_observation')
        if observation.date() != asof or observation.utcoffset() != instant.utcoffset():
            raise ValueError('expiry_observation_date_or_offset_mismatch')
        boundary = instant.isoformat()
        expired = observation >= instant
    else:
        raise ValueError('explicit_expiry_semantics_required')
    return dict(label_value=value, semantics=mode, source_reference=record['source_reference'],
                exclusive_expiry=boundary, expired_on_analysis_date=expired,
                observation_at=record.get('observation_at'))


def acceptance_control(data):
    asof = _base(data, ('items', 'withdrawal_snapshot'), ('responsible',))
    if data.get('responsible') is not None:
        _text(data['responsible'], 'responsible')
    snapshot = data['withdrawal_snapshot']
    _obj(snapshot, ('date', 'coverage', 'source_reference', 'records'), label='withdrawal_snapshot')
    snapdate = _past(snapshot['date'], asof, 'withdrawal_snapshot_date')
    _text(snapshot['coverage'], 'snapshot_coverage')
    _ref(snapshot['source_reference'])
    withdrawals = _rows(snapshot['records'], 'withdrawal_records', maximum=300)
    for row in withdrawals:
        _obj(row, ('registration_number', 'series', 'action', 'decision_date', 'source_reference', 'excerpt'), label='withdrawal_record')
        for key in ('registration_number', 'series', 'action'):
            _text(row[key], key)
        _past(row['decision_date'], snapdate, 'withdrawal_decision_date')
        _excerpt(row)
    results = []
    seen = set()
    for item in _rows(data['items'], 'items', 1):
        _obj(item, ('id', 'name', 'registration_number', 'form', 'strength', 'series', 'expiry', 'checks'), ('transport',), 'acceptance_item')
        for key in ('id', 'name', 'registration_number', 'form', 'strength', 'series'):
            _text(item[key], key)
        if item['id'] in seen:
            raise ValueError('duplicate_item_id')
        seen.add(item['id'])
        expiry = _expiry(item['expiry'], asof)
        _obj(item['checks'], ('description', 'packaging', 'marking', 'documents'), label='acceptance_checks')
        gaps = []
        if expiry['semantics'] == 'unresolved':
            gaps.append('expiry_semantics')
        for name, check in item['checks'].items():
            _obj(check, ('state',), ('excerpt', 'source_reference'), 'acceptance_check')
            if check['state'] not in ('provided', 'missing', 'unknown', 'not_applicable'):
                raise ValueError('unsupported_check_state')
            if check['state'] == 'provided':
                _excerpt(check)
            elif check.get('excerpt') is not None or check.get('source_reference') is not None:
                _excerpt(check)
            if check['state'] in ('missing', 'unknown'):
                gaps.append(name)
        transport = item.get('transport')
        temperature = 'not_assessed'
        if transport is not None:
            _obj(transport, ('lower', 'upper', 'minimum', 'maximum', 'unit', 'source_reference', 'excerpt'), label='transport')
            _excerpt(transport)
            if transport['unit'] != 'degC':
                raise ValueError('temperature_unit_degC_required')
            lower, upper, minimum, maximum = (_number(transport[k], k) for k in ('lower', 'upper', 'minimum', 'maximum'))
            if not -100 <= lower <= upper <= 100 or not -100 <= minimum <= maximum <= 100:
                raise ValueError('temperature_range_invalid')
            temperature = 'excursion_observed' if minimum < lower or maximum > upper else 'within_supplied_range'
        else:
            gaps.append('transport')
        matches = [copy.deepcopy(row) for row in withdrawals if row['registration_number'] == item['registration_number'] and row['series'] == item['series']]
        results.append(dict(id=item['id'], name=item['name'], registration_number=item['registration_number'],
                            form=item['form'], strength=item['strength'], series=item['series'],
                            expiry=expiry, expired_on_analysis_date=expiry['expired_on_analysis_date'], evidence_gaps=gaps,
                            checks=copy.deepcopy(item['checks']), transport=copy.deepcopy(transport), temperature_result=temperature,
                            withdrawal_status='withdrawal_match' if matches else 'not_found_in_selected_snapshot',
                            withdrawal_matches=matches, release_decision='not_assessed'))
    return _result('acceptance_control', data, items=results, snapshot_date=snapshot['date'],
                   snapshot_age_days=(asof-snapdate).days, snapshot_coverage=snapshot['coverage'],
                   responsible=data.get('responsible'), context_gaps=[] if data.get('responsible') else ['responsible'],
                   source_reference=snapshot['source_reference'], next_steps=['source_only_no_safety_conclusion', 'review_by_pharmacist'])


def _ingredients(values):
    rows = _rows(values, 'inn', 1, 20)
    cleaned = []
    for value in rows:
        token = ' '.join(_text(value, 'inn', 300).split()).casefold()
        if token in cleaned:
            raise ValueError('duplicate_ingredient_within_medicine')
        cleaned.append(token)
    return cleaned


def drug_info(data):
    asof = _base(data, ('medicines', 'interactions'))
    medicines = _rows(data['medicines'], 'medicines', 1, 30)
    byid = {}
    result = []
    for medicine in medicines:
        _obj(medicine, ('id', 'trade_name', 'registration_number', 'form', 'strength', 'inn', 'selected_instruction', 'claims'), label='medicine')
        for key in ('id', 'trade_name', 'registration_number', 'form', 'strength'):
            _text(medicine[key], key)
        if medicine['id'] in byid:
            raise ValueError('duplicate_medicine_id')
        ingredients = _ingredients(medicine['inn'])
        instruction = medicine['selected_instruction']
        _obj(instruction, (*SOURCE_FIELDS - {'not_after'}, 'registration_number', 'form', 'strength', 'inn'), ('not_after',), 'instruction')
        source = {k: v for k, v in instruction.items() if k in SOURCE_FIELDS}
        meta = _source(source, asof)
        for key in ('registration_number', 'form', 'strength'):
            if medicine[key] != instruction[key]:
                raise ValueError('instruction_identity_mismatch:' + key)
            if instruction[key] not in instruction['text']:
                raise ValueError('instruction_identity_not_in_selected_text:' + key)
        if sorted(ingredients) != sorted(_ingredients(instruction['inn'])):
            raise ValueError('instruction_identity_mismatch:inn')
        normalized_instruction = ' '.join(instruction['text'].split()).casefold()
        if any(ingredient not in normalized_instruction for ingredient in ingredients):
            raise ValueError('instruction_ingredient_not_in_selected_text')
        claims = []
        for claim in _rows(medicine['claims'], 'claims', maximum=30):
            _obj(claim, ('topic', 'excerpt', 'source_reference'), label='instruction_claim')
            if claim['topic'] not in ('indications', 'contraindications', 'interactions', 'dispensing', 'storage', 'warnings'):
                raise ValueError('unsupported_instruction_topic')
            _excerpt(claim, source)
            claims.append(dict(claim, occurrence='present', semantic_status='not_assessed'))
        topics = {c['topic'] for c in claims}
        result.append(dict(id=medicine['id'], trade_name=medicine['trade_name'], registration_number=medicine['registration_number'],
                           form=medicine['form'], strength=medicine['strength'], inn=copy.deepcopy(medicine['inn']),
                           instruction=meta, selected_claims=claims,
                           missing_topics=sorted({'indications', 'contraindications', 'interactions', 'dispensing'}-topics)))
        byid[medicine['id']] = dict(ingredients=ingredients, source=source)
    duplicates = []
    ids = list(byid)
    for i, first in enumerate(ids):
        for second in ids[i+1:]:
            overlap = sorted(set(byid[first]['ingredients']) & set(byid[second]['ingredients']))
            if overlap:
                duplicates.append(dict(medicine_ids=[first, second], ingredients=overlap, code='duplicate_ingredient'))
    interactions = []
    documented_pairs = set()
    for row in _rows(data['interactions'], 'interactions', maximum=100):
        _obj(row, ('medicine_ids', 'excerpt', 'source_reference'), label='interaction')
        pair = _rows(row['medicine_ids'], 'interaction_medicine_ids', 2, 2)
        if any(type(identity) is not str or identity not in byid for identity in pair) or len(set(pair)) != 2:
            raise ValueError('interaction_medicine_pair_required')
        sources = [byid[identity]['source'] for identity in pair]
        matches = [source for source in sources if source['source_reference'] == row['source_reference']]
        if not matches:
            raise ValueError('interaction_source_not_pair_instruction')
        _excerpt(row, matches[0])
        documented_pairs.add(tuple(sorted(pair)))
        interactions.append(dict(row, code='documented_interaction', semantic_status='not_assessed'))
    uncovered = [[first, second] for i, first in enumerate(ids) for second in ids[i+1:]
                 if tuple(sorted((first, second))) not in documented_pairs]
    return _result('drug_info', data, medicines=result, ingredient_duplicates=duplicates,
                   documented_interactions=interactions, pairs_without_selected_interaction=uncovered,
                   next_steps=['no_interaction_data_not_no_risk', 'review_by_pharmacist'])


def _deadline(rule, awareness, asof, calendar):
    source = {k: v for k, v in rule.items() if k in SOURCE_FIELDS}
    _source(source, asof, awareness)
    days = _number(rule['days'], 'reporting_days')
    if days != days.to_integral_value() or not 1 <= days <= 365:
        raise ValueError('bounded_integer_reporting_days_required')
    if rule['clock'] not in ('calendar', 'working') or rule['trigger'] != 'awareness':
        raise ValueError('unsupported_reporting_clock_or_trigger')
    if type(rule['count_start']) is not bool:
        raise ValueError('explicit_count_start_boolean_required')
    include = rule['count_start']
    count = int(days)
    if rule['clock'] == 'working':
        _obj(calendar, ('coverage_from', 'coverage_to', 'days', 'source_reference'), label='working_calendar')
        start = _day(calendar['coverage_from'])
        end = _day(calendar['coverage_to'])
        if not start <= awareness <= end or (end-start).days > 365:
            raise ValueError('calendar_coverage_invalid')
        _ref(calendar['source_reference'])
        supplied = _rows(calendar['days'], 'calendar_days', 1, 366)
        if len(supplied) != (end-start).days+1:
            raise ValueError('complete_daily_calendar_required')
        eligible = []
        for i, row in enumerate(supplied):
            _obj(row, ('date', 'working'), label='calendar_day')
            current = _day(row['date'], 'calendar_date')
            if current != start + timedelta(days=i):
                raise ValueError('complete_ordered_calendar_required')
            if type(row['working']) is not bool:
                raise ValueError('calendar_working_boolean_required')
            if row['working'] and (current > awareness or include and current == awareness):
                eligible.append(current)
        if len(eligible) < count:
            raise ValueError('deadline_outside_selected_calendar')
        return eligible[count-1]
    offset = count-1 if include else count
    if (date.max-awareness).days < offset:
        raise ValueError('deadline_out_of_date_range')
    return awareness + timedelta(days=offset)


def pharmacovigilance(data):
    asof = _base(data, ('case', 'reporter_scope', 'reporting_rule', 'selected_form'), ('working_calendar',))
    case = data['case']
    _obj(case, ('patient', 'reporter', 'suspected_drug', 'reaction', 'awareness_date', 'seriousness', 'concomitants', 'source_reference'),
         ('drug_start_date', 'drug_stop_date', 'ongoing', 'outcome'), 'adverse_case')
    _ref(case['source_reference'])
    _text(data['reporter_scope'], 'reporter_scope')
    awareness = _past(case['awareness_date'], asof, 'awareness_date')
    gaps = []
    for name in ('patient', 'reporter'):
        record = case[name]
        _obj(record, (), ('local_id', 'description', 'role'), name)
        for value in record.values():
            _text(value, name)
        if not record.get('local_id') and not record.get('description'):
            gaps.append(name)
    drug = case['suspected_drug']
    _obj(drug, (), ('name', 'inn', 'series', 'registration_number'), 'suspected_drug')
    for key, value in drug.items():
        _text(value, key)
    if not drug.get('name') and not drug.get('inn'):
        gaps.append('suspected_drug')
    if not drug.get('series'):
        gaps.append('series')
    reaction = case['reaction']
    _obj(reaction, (), ('description', 'onset_date'), 'reaction')
    if reaction.get('description'):
        _text(reaction['description'], 'reaction_description', 10000)
    else:
        gaps.append('reaction')
    chronology = []
    dates = {}
    for name, value in (('onset', reaction.get('onset_date')), ('drug_start', case.get('drug_start_date')),
                        ('drug_stop', case.get('drug_stop_date'))):
        if value is not None:
            d = _past(value, asof, name + '_date')
            dates[name] = d
            chronology.append(dict(event=name, date=d.isoformat()))
        else:
            gaps.append(name + '_date')
    if 'ongoing' in case and type(case['ongoing']) is not bool:
        raise ValueError('ongoing_boolean_required')
    if case.get('ongoing') is True:
        if 'drug_stop' in dates:
            raise ValueError('ongoing_with_stop_date')
        gaps = [gap for gap in gaps if gap != 'drug_stop_date']
    if case.get('outcome') is not None:
        _text(case['outcome'], 'outcome')
    else:
        gaps.append('outcome')
    seriousness = _rows(case['seriousness'], 'seriousness', maximum=10)
    allowed = {'death', 'life_threatening', 'hospitalization', 'disability', 'congenital_anomaly', 'other_medically_important', 'unknown', 'none_reported'}
    if any(type(value) is not str or value not in allowed for value in seriousness) or len(set(seriousness)) != len(seriousness):
        raise ValueError('seriousness_categories_required')
    if not seriousness or 'unknown' in seriousness:
        gaps.append('seriousness')
    if len(seriousness) > 1 and ({'unknown', 'none_reported'} & set(seriousness)):
        raise ValueError('seriousness_conflict')
    for row in _rows(case['concomitants'], 'concomitants', maximum=50):
        _obj(row, ('name',), ('start_date', 'stop_date'), 'concomitant')
        _text(row['name'], 'concomitant_name')
        cdates = {}
        for key in ('start_date', 'stop_date'):
            if row.get(key) is not None:
                cdates[key] = _past(row[key], asof, key)
        if 'start_date' in cdates and 'stop_date' in cdates and cdates['stop_date'] < cdates['start_date']:
            raise ValueError('concomitant_stop_before_start')
    conflicts = []
    if 'drug_start' in dates and 'drug_stop' in dates and dates['drug_stop'] < dates['drug_start']:
        conflicts.append('drug_stop_before_start')
    if 'onset' in dates and 'drug_start' in dates and dates['onset'] < dates['drug_start']:
        conflicts.append('onset_before_drug_start')
    if 'onset' in dates and dates['onset'] > awareness:
        conflicts.append('awareness_before_onset')
    rule = data['reporting_rule']
    due = None
    rulemeta = None
    if rule is None:
        gaps.append('reporting_rule')
    else:
        _obj(rule, (*SOURCE_FIELDS-{'not_after'}, 'reporter_scope', 'case_scope', 'clock', 'days', 'trigger', 'count_start'), ('not_after',), 'reporting_rule')
        _text(rule['reporter_scope'], 'rule_reporter_scope')
        if rule['case_scope'] not in ('any_suspected', 'serious', 'fatal_or_life_threatening'):
            raise ValueError('unsupported_reporting_case_scope')
        if rule['case_scope'] == 'serious' and not (set(seriousness)-{'unknown', 'none_reported'}):
            raise ValueError('reporting_rule_case_scope_mismatch')
        if rule['case_scope'] == 'fatal_or_life_threatening' and not ({'death', 'life_threatening'} & set(seriousness)):
            raise ValueError('reporting_rule_case_scope_mismatch')
        if rule['reporter_scope'] != data['reporter_scope']:
            raise ValueError('reporting_rule_reporter_scope_mismatch')
        due = _deadline(rule, awareness, asof, data.get('working_calendar'))
        rulemeta = dict(_source({k: v for k, v in rule.items() if k in SOURCE_FIELDS}, asof, awareness),
                        reporter_scope=rule['reporter_scope'], case_scope=rule['case_scope'],
                        clock=rule['clock'], days=str(_number(rule['days'])), trigger=rule['trigger'], count_start=rule['count_start'],
                        scope_semantics='not_assessed')
    form = data['selected_form']
    if form is None:
        gaps.append('selected_form')
        formmeta = None
    else:
        formmeta = _source(form, asof)
    minimum = [gap for gap in gaps if gap in ('patient', 'reporter', 'suspected_drug', 'reaction')]
    return _result('pharmacovigilance', data, draft_case=copy.deepcopy(case), reporter_scope=data['reporter_scope'],
                   minimum_case_gaps=minimum, completeness_gaps=gaps, chronology=sorted(chronology, key=lambda row: row['date']),
                   chronology_conflicts=conflicts, selected_reporting_rule=rulemeta, selected_form=formmeta,
                   candidate_deadline=due.isoformat() if due else None, deadline_overdue_at_as_of=due < asof if due else None,
                   deadline_basis='selected_rule_only', causal_link='not_assessed',
                   next_steps=['causality_not_assessed', 'draft_not_submitted', 'review_by_pharmacist'])


def _sop_metadata(row, asof, prefix):
    for key in ('scope', 'version', 'owner'):
        _text(row[key], prefix + '_' + key)
    _day(row['review_date'], 'review_date')
    for record in _rows(row['records'], prefix + '_records', 1, 30):
        _text(record, 'record')
    _ref(row['source_reference'])


def gpp_sop(data):
    asof = _base(data, ('organization_scope', 'plan', 'selected_rule', 'required_controls', 'existing_documents', 'capa'), ('additional_rules',))
    _text(data['organization_scope'], 'organization_scope')
    source = data['selected_rule']
    source_meta = _source(source, asof)
    sources = {source['source_reference']: source}
    additional_meta = []
    for additional in _rows(data.get('additional_rules', []), 'additional_rules', maximum=10):
        meta = _source(additional, asof)
        identity = additional['source_reference']
        if identity in sources:
            raise ValueError('duplicate_selected_rule_reference')
        sources[identity] = additional
        additional_meta.append(meta)
    plan = data['plan']
    _obj(plan, ('purpose', 'procedure', 'scope', 'version', 'owner', 'review_date', 'records', 'source_reference'), label='sop_plan')
    _sop_metadata(plan, asof, 'plan')
    _text(plan['purpose'], 'sop_purpose', 10000)
    _text(plan['procedure'], 'sop_procedure', 20000)
    if plan['scope'] != data['organization_scope']:
        raise ValueError('plan_organization_scope_mismatch')
    controls = {}
    for row in _rows(data['required_controls'], 'required_controls', 1):
        _obj(row, ('id', 'title', 'scope', 'excerpt', 'source_reference'), label='required_control')
        for key in ('id', 'title', 'scope'):
            _text(row[key], key)
        if row['scope'] != data['organization_scope']:
            raise ValueError('control_organization_scope_mismatch')
        if row['id'] in controls:
            raise ValueError('duplicate_control_id')
        if row['source_reference'] not in sources:
            raise ValueError('unselected_control_rule_reference')
        _excerpt(row, sources[row['source_reference']])
        controls[row['id']] = row
    docs = []
    docids = set()
    covered = set()
    for doc in _rows(data['existing_documents'], 'existing_documents'):
        _obj(doc, ('id', 'title', 'scope', 'version', 'owner', 'review_date', 'records', 'source_reference', 'text', 'controls'), label='existing_document')
        _sop_metadata(doc, asof, 'document')
        _text(doc['id'], 'document_id')
        _text(doc['title'], 'document_title')
        _text(doc['text'], 'document_text', 100000)
        if doc['id'] in docids:
            raise ValueError('duplicate_document_id')
        docids.add(doc['id'])
        matches = []
        local = set()
        for row in _rows(doc['controls'], 'document_controls'):
            _obj(row, ('control_id', 'excerpt', 'source_reference'), label='document_control')
            if type(row['control_id']) is not str or row['control_id'] not in controls or row['control_id'] in local:
                raise ValueError('unknown_or_duplicate_document_control')
            local.add(row['control_id'])
            _excerpt(row, doc)
            same_scope = doc['scope'] == controls[row['control_id']]['scope']
            if same_scope:
                covered.add(row['control_id'])
            matches.append(dict(row, occurrence='present', semantic_status='not_assessed', scope_match=same_scope))
        docs.append(dict(id=doc['id'], title=doc['title'], scope=doc['scope'], version=doc['version'], owner=doc['owner'],
                         review_date=doc['review_date'], records=copy.deepcopy(doc['records']), source_reference=doc['source_reference'],
                         selected_controls=matches, review_due=_day(doc['review_date']) <= asof))
    actions = []
    for row in _rows(data['capa'], 'capa'):
        _obj(row, ('control_id', 'discrepancy', 'action', 'scope', 'version', 'owner', 'due_date', 'records', 'review_date', 'source_reference'), label='capa')
        _sop_metadata(row, asof, 'capa')
        if type(row['control_id']) is not str or row['control_id'] not in controls:
            raise ValueError('unknown_capa_control')
        if row['scope'] != controls[row['control_id']]['scope']:
            raise ValueError('capa_control_scope_mismatch')
        _text(row['discrepancy'], 'discrepancy', 5000)
        _text(row['action'], 'corrective_action', 5000)
        due = _day(row['due_date'], 'capa_due_date')
        actions.append(dict(row, overdue_at_as_of=due < asof))
    missing = sorted(set(controls)-covered)
    missing_inventory = sorted(set(GPP_INVENTORY)-set(controls))
    missing_capa = [identity for identity in missing if not any(row['control_id'] == identity for row in actions)]
    return _result('gpp_sop', data, organization_scope=data['organization_scope'], draft_plan=dict(copy.deepcopy(plan), authorship='proposed_not_approved'),
                   selected_rule=source_meta, additional_rules=additional_meta, required_controls=copy.deepcopy(list(controls.values())), document_inventory=docs,
                   missing_control_documents=missing, inventory_topics_without_selected_requirement=missing_inventory,
                   corrective_actions=actions, missing_corrective_actions=missing_capa,
                   next_steps=['excerpt_present_not_compliance', 'review_by_pharmacist'])


def input_units(function, data):
    if function not in FUNCTIONS:
        raise ValueError('unknown_scenario_function')
    if type(data) is not dict:
        raise ValueError('scenario_object_required')
    units = {}
    if function == 'acceptance_control':
        for i, item in enumerate(_rows(data.get('items'), 'items', 1)):
            if type(item) is not dict:
                raise ValueError('acceptance_item_object_required')
            if item.get('transport') is not None:
                for key in ('lower', 'upper', 'minimum', 'maximum'):
                    units[f'/items/{i}/transport/{key}'] = {'unit': 'degC', 'not_after': data['as_of']}
    elif function == 'pharmacovigilance' and data.get('reporting_rule') is not None:
        if type(data['reporting_rule']) is not dict:
            raise ValueError('reporting_rule_object_required')
        units['/reporting_rule/days'] = {'unit': 'day', 'effective_date': data['reporting_rule']['effective_date'], 'not_after': data['as_of']}
    return units


def selected_texts(function, data):
    if function not in FUNCTIONS:
        raise ValueError('unknown_scenario_function')
    _bounded(data)
    texts = {}
    def walk(value, path=''):
        if type(value) is dict:
            for key, item in value.items():
                pointer = path + '/' + key.replace('~', '~0').replace('/', '~1')
                # Literal source text and excerpts are bound by occurrence only.
                if key in ('text', 'excerpt', 'label_value'):
                    texts[pointer] = _text(item, 'selected_text', 200000)
                elif key in ('registration_number', 'form', 'strength') and 'text' in value and 'source_reference' in value:
                    texts[pointer] = _text(item, 'instruction_identity', 2000)
                else:
                    walk(item, pointer)
        elif type(value) is list:
            for i, item in enumerate(value):
                walk(item, path + '/' + str(i))
    walk(data)
    return texts


def _public(fn):
    @wraps(fn)
    def checked(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (KeyError, TypeError, AttributeError, IndexError, OverflowError, RecursionError) as exc:
            raise ValueError('invalid_nested_scenario_input') from None
    return checked


for _name in (*FUNCTIONS, 'input_units', 'selected_texts'):
    globals()[_name] = _public(globals()[_name])

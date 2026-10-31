"""Local arithmetic and discrepancy drafts for supplied pharmacy records.

No built-in legal thresholds, clinical advice, formula design or authority decisions.
Rules and source semantics require a separate dated human review by the host.
"""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, Context, localcontext, DecimalException, ROUND_HALF_UP
from functools import wraps
import calendar
import re

D = Decimal
CTX = Context(prec=80, rounding=ROUND_HALF_UP)
FUNCTIONS = ('rx_dispensing', 'storage_quality', 'compounding', 'zhnvlp_pricing', 'nmo_pharma')

def fail(code):
    raise ValueError(code)

def obj(v, n):
    if type(v) is not dict: fail(n + '_object_required')
    return v

def rows(v, n, lo=0, hi=40):
    if type(v) is not list or not lo <= len(v) <= hi: fail(n + '_bounded_list_required')
    return v

def text(v, n, limit=4000):
    if type(v) is not str or not v.strip() or len(v) > limit: fail(n + '_text_required')
    return v.strip()

def boolean(v, n):
    if type(v) is not bool: fail(n + '_boolean_required')
    return v

def num(v, n, lo='0', hi='1000000000000'):
    if type(v) not in (str, int, D) or not re.fullmatch(r'-?(?:0|[1-9]\d{0,12})(?:\.\d{1,8})?', str(v)):
        fail(n + '_exact_decimal_required')
    value = D(v)
    if not value.is_finite() or not D(lo) <= value <= D(hi): fail(n + '_range')
    return value

def integer(v, n, lo=0, hi=10000):
    value = num(v, n, str(lo), str(hi))
    if value != int(value): fail(n + '_integer_required')
    return int(value)

def day(v, n):
    if type(v) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', v): fail(n + '_iso_date_required')
    try: return date.fromisoformat(v)
    except ValueError: fail(n + '_invalid_date')

def stamp(v, n):
    if type(v) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})', v):
        fail(n + '_offset_timestamp_required')
    try: result = datetime.fromisoformat(v.replace('Z', '+00:00'))
    except ValueError: fail(n + '_invalid_timestamp')
    if result.utcoffset() is None: fail(n + '_offset_required')
    return result

def exact(v): return format(v, 'f')
def money(v): return format(v.quantize(D('.01')), 'f')
def ref(v, n='source_reference'): return text(v, n, 200)

def optional_text(c,key,limit=1000):
    return text(c[key],key,limit) if key in c and c[key] is not None else None

def reject_keys(value,keys):
    if type(value) is dict:
        for key,item in value.items():
            if key in keys: fail('unsupported_supplied_'+key)
            reject_keys(item,keys)
    elif type(value) is list:
        for item in value: reject_keys(item,keys)

def rule(v, asof, name='rule'):
    r = obj(v, name)
    ref(r.get('source_reference'))
    for key in ('document_identity','edition'): text(r.get(key), name+'_'+key,1000)
    published = day(r.get('publication_date'),name+'_publication_date')
    if published > asof: fail(name+'_publication_after_analysis_cutoff')
    if r.get('retrospective_policy') not in ('review_gap','selected_retroactive_interpretation'):
        fail(name+'_retrospective_policy_required')
    start = day(r.get('effective_from'), name + '_effective_from')
    if 'effective_to' not in r: fail(name + '_effective_to_or_null_required')
    end = day(r['effective_to'], name + '_effective_to') if r['effective_to'] is not None else None
    if end is not None and start > end or not in_rule(r, asof): fail(name + '_outside_selected_effective_dates')
    return r

def in_rule(r, d):
    return day(r['effective_from'],'effective_from') <= d and (r['effective_to'] is None or d <= day(r['effective_to'],'effective_to'))

def retrospective_gaps(r, event):
    return ['selected_rule_published_after_event_requires_review'] if day(r['publication_date'],'publication_date') > event and r['retrospective_policy']=='review_gap' else []

def stringlist(v, n, lo=0, hi=30):
    values = [text(x, n, 200) for x in rows(v, n, lo, hi)]
    if len(set(values)) != len(values): fail(n + '_duplicate')
    return values

def bounded_tree(value, depth=0, budget=None):
    # Bound memory/recursion even when helpers are called without the facade.
    if budget is None: budget = [0]
    budget[0] += 1
    if depth > 12 or budget[0] > 5000: fail('calculation_structure_limit')
    if type(value) is dict:
        if len(value) > 80 or any(type(k) is not str for k in value): fail('calculation_object_keys')
        for item in value.values(): bounded_tree(item, depth + 1, budget)
    elif type(value) is list:
        if len(value) > 200: fail('calculation_list_limit')
        for item in value: bounded_tree(item, depth + 1, budget)
    elif type(value) is str:
        if len(value) > 12000: fail('calculation_text_limit')
    elif value is not None and type(value) not in (bool, int, D): fail('unsupported_calculation_value')

def guard(fn):
    @wraps(fn)
    def wrapped(data):
        bounded_tree(data)
        with localcontext(CTX):
            c = deepcopy(obj(data, 'data'))
            asof = day(c.get('as_of'), 'as_of')
            try: result = fn(c, asof)
            except (KeyError, TypeError, AttributeError, IndexError, OverflowError):
                raise ValueError('invalid_' + fn.__name__ + '_structure') from None
            except DecimalException:
                raise ValueError('unsupported_numeric_condition_' + fn.__name__) from None
            result.update(as_of=c['as_of'], assisted_draft=True, source_semantics_verified=False,
                          current_legal_applicability_verified=False, external_network_used=False,
                          human_review_required=True)
            return result
    return wrapped

def _deferred(config, asof):
    v = obj(config, 'deferred'); start = day(v.get('start_date'), 'deferred_start')
    if start > asof: fail('deferred_start_after_as_of')
    r = rule(v.get('rule'), asof, 'deferred_rule')
    if not in_rule(r, start):
        fail('deferred_start_outside_rule')
    n = integer(r.get('workdays'), 'workdays', 1, 90)
    include = boolean(r.get('count_start'), 'count_start')
    cal = obj(v.get('calendar'), 'calendar'); ref(cal.get('source_reference'))
    begin = day(cal.get('coverage_from'), 'coverage_from'); end = day(cal.get('coverage_to'), 'coverage_to')
    if not begin <= start <= end or (end - begin).days > 180: fail('calendar_coverage_range')
    supplied = rows(cal.get('days'), 'calendar_days', 1, 181)
    if len(supplied) != (end - begin).days + 1: fail('complete_daily_calendar_required')
    eligible = []
    for i, item in enumerate(supplied):
        item = obj(item, 'calendar_day'); current = day(item.get('date'), 'calendar_date')
        if current != begin + timedelta(days=i): fail('complete_ordered_calendar_required')
        working = boolean(item.get('working'), 'calendar_working')
        if working and (current > start or include and current == start): eligible.append(current)
    if len(eligible) < n: fail('calendar_does_not_cover_deadline')
    return dict(deadline=eligible[n-1].isoformat(), counted_dates=[x.isoformat() for x in eligible[:n]],
                start_date=start.isoformat(),
                workdays=n, count_start=include, rule=deepcopy(r), calendar_reference=cal['source_reference'],
                rule_review_gaps=retrospective_gaps(r,start),
                conditional_on_selected_rule_and_calendar=True)

@guard
def rx_dispensing(c, asof):
    r = rule(c.get('rule'), asof)
    rx = obj(c.get('prescription'), 'prescription'); ref(rx.get('source_reference'))
    for key in ('id', 'form', 'channel', 'category', 'quantity_unit'): text(rx.get(key), 'prescription_' + key, 200)
    optional_text(rx,'product')
    required = stringlist(r.get('required_fields'), 'required_fields', 1)
    fields = stringlist(rx.get('present_fields'), 'present_fields')
    forms = stringlist(r.get('forms'), 'forms', 1)
    channels = stringlist(r.get('channels'), 'channels', 1)
    category = text(r.get('category'), 'rule_category', 200)
    pku = boolean(rx.get('pku'), 'prescription_pku'); benefit = boolean(rx.get('benefit'), 'prescription_benefit')
    pku_expected = boolean(r.get('pku_expected'), 'rule_pku'); benefit_expected = boolean(r.get('benefit_expected'), 'rule_benefit')
    inpatient = boolean(rx.get('inpatient_only'), 'inpatient_only')
    issue = day(rx.get('issue_date'), 'issue_date'); contact = day(c.get('contact_date'), 'contact_date')
    if issue > contact or contact > asof: fail('prescription_event_chronology')
    if not in_rule(r,issue) or not in_rule(r,contact): fail('prescription_events_outside_selected_rule')
    mode = r.get('validity_mode')
    if mode == 'calendar_days':
        days = integer(r.get('valid_days'), 'valid_days', 1, 730)
        includes = boolean(r.get('validity_count_issue_day'), 'validity_count_issue_day')
        valid_to = issue + timedelta(days=days - (1 if includes else 0))
    elif mode in ('calendar_months','calendar_years'):
        period = integer(r.get('valid_period'), 'valid_period', 1, 120 if mode=='calendar_months' else 10)
        months = period if mode=='calendar_months' else period*12
        yy, mm = divmod(issue.year*12+issue.month-1+months,12); mm += 1
        last = calendar.monthrange(yy,mm)[1]
        policy = r.get('anniversary_policy')
        if policy not in ('clamp_to_month_end','reject_invalid_anniversary'): fail('anniversary_policy_required')
        if issue.day > last and policy=='reject_invalid_anniversary': fail('invalid_calendar_anniversary')
        anniversary = date(yy,mm,min(issue.day,last))
        boundary = r.get('expiry_boundary')
        if boundary not in ('anniversary_inclusive','day_before_anniversary'): fail('expiry_boundary_required')
        valid_to = anniversary - timedelta(days=1 if boundary=='day_before_anniversary' else 0)
    elif mode == 'explicit_record_expiry':
        valid_to = day(rx.get('expiry_date'), 'record_expiry_date')
        text(rx.get('expiry_text'), 'expiry_text',4000)
        if valid_to < issue: fail('record_expiry_before_issue')
    else: fail('explicit_prescription_validity_mode_required')
    q = num(rx.get('quantity'), 'prescription_quantity', '0.00000001')
    requested = num(c.get('requested_quantity'), 'requested_quantity', '0.00000001')
    limit = num(r.get('max_quantity'), 'max_quantity', '0.00000001')
    if text(r.get('quantity_unit'), 'quantity_unit', 100) != rx['quantity_unit']: fail('prescription_quantity_unit_mismatch')
    missing = [f for f in required if f not in fields]
    findings = retrospective_gaps(r,issue)
    for condition, code in ((rx['form'] not in forms, 'form_not_in_selected_rule'),
        (rx['channel'] not in channels, 'channel_not_in_selected_rule'), (rx['category'] != category, 'category_mismatch'),
        (pku != pku_expected, 'pku_classification_mismatch'), (benefit != benefit_expected, 'benefit_classification_mismatch'),
        (bool(missing), 'missing_prescription_fields'), (contact > valid_to, 'outside_conditional_validity'),
        (requested > q, 'requested_exceeds_prescription_quantity'), (q > limit, 'quantity_exceeds_selected_limit'),
        (inpatient, 'inpatient_only_requires_retail_restriction_review')):
        if condition: findings.append(code)
    deferred = None
    if c.get('deferred') is not None: deferred = _deferred(c['deferred'], asof)
    return dict(prescription_id=rx['id'], prescription=deepcopy(rx), selected_rule=deepcopy(r), validity_mode=mode,
                contact_date=c['contact_date'],
                missing_fields=missing, conditional_valid_through=valid_to.isoformat(),
                requested_quantity=exact(requested), findings=findings, deferred=deferred,
                decision_scope='record_check_only_no_dispensing_or_substitution_decision')

@guard
def storage_quality(c, asof):
    if c.get('mode') == 'expiry_only': return _storage_expiry_only(c,asof)
    if c.get('mode') == 'temperature_only': return _storage_temperature_only(c,asof)
    if c.get('mode') not in (None,'combined'): fail('supported_storage_mode_required')
    r = rule(c.get('instruction'), asof, 'instruction')
    lo = num(r.get('temperature_min'), 'temperature_min', '-100', '200')
    hi = num(r.get('temperature_max'), 'temperature_max', '-100', '200')
    hlo = num(r.get('humidity_min'), 'humidity_min', '0', '100')
    hhi = num(r.get('humidity_max'), 'humidity_max', '0', '100')
    maxgap = num(r.get('max_gap_minutes'), 'max_gap_minutes', '0.00000001', '100000')
    if lo > hi or hlo > hhi: fail('instruction_range_reversed')
    observed = stamp(c.get('observed_at'), 'observed_at')
    if observed.date() != asof: fail('observed_date_must_equal_as_of')
    start = stamp(c.get('window_start'), 'window_start'); end = stamp(c.get('window_end'), 'window_end')
    if not start < end <= observed or end - start > timedelta(days=366): fail('storage_window_range')
    if not in_rule(r,start.date()) or not in_rule(r,end.date()): fail('storage_window_outside_selected_instruction')
    offset = text(c.get('timezone_offset'), 'timezone_offset', 6)
    if not re.fullmatch(r'[+-](?:0\d|1\d|2[0-3]):[0-5]\d', offset): fail('fixed_timezone_offset_required')
    expected_offset = stamp('2000-01-01T00:00:00' + offset, 'offset').utcoffset()
    def same_offset(t):
        if t.utcoffset() != expected_offset: fail('storage_timezone_offset_mismatch')
    for t in (observed, start, end): same_offset(t)
    readings = []; times = []; previous = None
    for item in rows(c.get('measurements'), 'measurements', 1, 40):
        item = obj(item, 'measurement'); ref(item.get('source_reference'))
        t = stamp(item.get('timestamp'), 'measurement_timestamp'); same_offset(t)
        if not start <= t <= end or previous is not None and t <= previous: fail('ordered_unique_measurements_in_window_required')
        temp = num(item.get('temperature'), 'temperature', '-100', '200')
        humidity = num(item.get('humidity'), 'humidity', '0', '100')
        readings.append(dict(timestamp=item['timestamp'], temperature=exact(temp), humidity=exact(humidity),
                             temperature_outside=not lo <= temp <= hi, humidity_outside=not hlo <= humidity <= hhi,
                             source_reference=item['source_reference']))
        times.append(t); previous = t
    segments = []; gaps = []
    boundaries = [start] + times + [end]
    for i in range(len(boundaries)-1):
        a, b = boundaries[i:i+2]
        if a == b: continue
        elapsed = D((b-a).days*86400 + (b-a).seconds) / 60
        edge = i == 0 or i == len(boundaries)-2
        item = dict(start=a.isoformat(), end=b.isoformat(), elapsed_minutes=exact(elapsed),
                    measurement_gap=elapsed > maxgap or edge, actual_excursion_duration_minutes=None,
                    observation_interval_only=True)
        if not edge:
            item['endpoint_excursion_observed'] = any(readings[j]['temperature_outside'] or readings[j]['humidity_outside'] for j in (i-1, i))
        segments.append(item)
        if item['measurement_gap']: gaps.append(deepcopy(item))
    horizon = integer(c.get('expiry_alert_days'), 'expiry_alert_days', 0, 3650)
    location=optional_text(c,'location');responsible=optional_text(c,'responsible')
    zones=stringlist(c['zones'],'zones') if 'zones' in c else None
    expiries = []; seen = set()
    for item in rows(c.get('expiry_items'), 'expiry_items', 0, 30):
        item = obj(item, 'expiry_item'); ident = text(item.get('id'), 'expiry_id', 200)
        if ident in seen: fail('duplicate_expiry_id')
        seen.add(ident); ref(item.get('source_reference'))
        mode = item.get('semantics'); value = item.get('label_value')
        if mode == 'exclusive_instant':
            boundary = stamp(value, 'expiry_instant'); same_offset(boundary)
        elif mode == 'end_of_day':
            d = day(value, 'expiry_day'); boundary = datetime.combine(d + timedelta(days=1), datetime.min.time(), tzinfo=observed.tzinfo)
        elif mode == 'end_of_month':
            if type(value) is not str or not re.fullmatch(r'\d{4}-(?:0[1-9]|1[0-2])', value): fail('expiry_month_required')
            yy, mm = map(int, value.split('-')); d = date(yy, mm, calendar.monthrange(yy, mm)[1])
            boundary = datetime.combine(d + timedelta(days=1), datetime.min.time(), tzinfo=observed.tzinfo)
        else: fail('explicit_expiry_semantics_required')
        expired = observed >= boundary
        expiries.append(dict(id=ident, label_value=value, semantics=mode, exclusive_expiry=boundary.isoformat(),
            expired_at_observation=expired, within_alert_horizon=not expired and boundary <= observed + timedelta(days=horizon),
            quarantine_review_required=expired, source_reference=item['source_reference']))
    excursion = any(x['temperature_outside'] or x['humidity_outside'] for x in readings)
    return dict(instruction=deepcopy(r), timezone_offset=offset, readings=readings, segments=segments,
                location=location,responsible=responsible,zones=zones,
                gaps=gaps, expiry_rows=expiries, excursion_observed=excursion,
                rule_review_gaps=retrospective_gaps(r,start.date()),
                quarantine_review_required=excursion or bool(gaps) or any(x['expired_at_observation'] for x in expiries),
                actual_excursion_duration_minutes=None, interpolation_used=False,
                decision_scope='observations_only_no_batch_fitness_decision')

def _storage_offset_context(c,asof):
    observed=stamp(c.get('observed_at'),'observed_at')
    if observed.date()!=asof: fail('observed_date_must_equal_as_of')
    offset=text(c.get('timezone_offset'),'timezone_offset',6)
    if not re.fullmatch(r'[+-](?:0\d|1\d|2[0-3]):[0-5]\d',offset): fail('fixed_timezone_offset_required')
    expected=stamp('2000-01-01T00:00:00'+offset,'offset').utcoffset()
    if observed.utcoffset()!=expected: fail('storage_timezone_offset_mismatch')
    return observed,offset,expected

def _storage_expiry_rows(c,observed,expected):
    horizon=integer(c.get('expiry_alert_days'),'expiry_alert_days',0,3650)
    prepared=[];gaps=[];seen=set()
    for item in rows(c.get('expiry_items'),'expiry_items',0,30):
        item=obj(item,'expiry_item');ident=text(item.get('id'),'expiry_id',200)
        if ident in seen: fail('duplicate_expiry_id')
        seen.add(ident);ref(item.get('source_reference'))
        mode=item.get('semantics');value=text(item.get('label_value'),'expiry_label',4000)
        boundary=None
        if mode=='unresolved':
            gaps.append(dict(kind='expiry_semantics_unresolved',id=ident,source_reference=item['source_reference']))
        elif mode=='exclusive_instant':
            boundary=stamp(value,'expiry_instant')
            if boundary.utcoffset()!=expected: fail('storage_timezone_offset_mismatch')
        elif mode=='end_of_day':
            d=day(value,'expiry_day')
            if d==date.max: fail('expiry_boundary_out_of_range')
            boundary=datetime.combine(d+timedelta(days=1),datetime.min.time(),tzinfo=observed.tzinfo)
        elif mode=='end_of_month':
            if not re.fullmatch(r'\d{4}-(?:0[1-9]|1[0-2])',value): fail('expiry_month_required')
            yy,mm=map(int,value.split('-'));d=date(yy,mm,calendar.monthrange(yy,mm)[1])
            if d==date.max: fail('expiry_boundary_out_of_range')
            boundary=datetime.combine(d+timedelta(days=1),datetime.min.time(),tzinfo=observed.tzinfo)
        else: fail('explicit_expiry_semantics_required')
        expired=observed>=boundary if boundary is not None else None
        prepared.append(dict(id=ident,label_value=value,semantics=mode,
            exclusive_expiry=boundary.isoformat() if boundary is not None else None,
            expired_at_observation=expired,
            within_alert_horizon=(not expired and boundary<=observed+timedelta(days=horizon)) if boundary is not None else None,
            expiry_semantics_review_required=boundary is None,
            quarantine_review_required=expired is True or boundary is None,source_reference=item['source_reference']))
    return prepared,gaps

def _storage_expiry_only(c,asof):
    if any(key in c for key in ('instruction','measurements','window_start','window_end')):
        fail('expiry_only_does_not_accept_measurements_or_instruction')
    observed,offset,expected=_storage_offset_context(c,asof)
    expiry,gaps=_storage_expiry_rows(c,observed,expected)
    return dict(mode='expiry_only',observed_at=c['observed_at'],timezone_offset=offset,
        expiry_alert_days=integer(c['expiry_alert_days'],'expiry_alert_days',0,3650),
        location=optional_text(c,'location'),responsible=optional_text(c,'responsible'),
        zones=stringlist(c['zones'],'zones') if 'zones' in c else None,
        expiry_rows=expiry,expiry_semantics_gaps=gaps,gaps=deepcopy(gaps),readings=[],segments=[],
        excursion_observed=None,temperature_check_performed=False,humidity_check_performed=False,
        expiry_check_performed=True,quarantine_review_required=any(x['quarantine_review_required'] for x in expiry),
        actual_excursion_duration_minutes=None,interpolation_used=False,
        decision_scope='expiry_records_only_no_batch_fitness_decision')

def _storage_temperature_only(c,asof):
    r=rule(c.get('instruction'),asof,'instruction')
    applicability=r.get('humidity_applicability')
    if applicability not in ('not_applicable','unknown'): fail('explicit_humidity_applicability_required')
    if any(key in r for key in ('humidity_min','humidity_max')): fail('temperature_only_unused_humidity_limits')
    lo=num(r.get('temperature_min'),'temperature_min','-100','200')
    hi=num(r.get('temperature_max'),'temperature_max','-100','200')
    maxgap=num(r.get('max_gap_minutes'),'max_gap_minutes','0.00000001','100000')
    if lo>hi: fail('instruction_range_reversed')
    observed,offset,expected=_storage_offset_context(c,asof)
    start=stamp(c.get('window_start'),'window_start');end=stamp(c.get('window_end'),'window_end')
    if not start<end<=observed or end-start>timedelta(days=366): fail('storage_window_range')
    if not in_rule(r,start.date()) or not in_rule(r,end.date()): fail('storage_window_outside_selected_instruction')
    if start.utcoffset()!=expected or end.utcoffset()!=expected: fail('storage_timezone_offset_mismatch')
    readings=[];times=[];previous=None
    for item in rows(c.get('measurements'),'measurements',1,40):
        item=obj(item,'measurement');ref(item.get('source_reference'))
        t=stamp(item.get('timestamp'),'measurement_timestamp')
        if t.utcoffset()!=expected: fail('storage_timezone_offset_mismatch')
        if not start<=t<=end or previous is not None and t<=previous: fail('ordered_unique_measurements_in_window_required')
        if item.get('humidity') is not None: fail('temperature_only_humidity_must_be_missing_or_null')
        temp=num(item.get('temperature'),'temperature','-100','200')
        readings.append(dict(timestamp=item['timestamp'],temperature=exact(temp),humidity=None,
            temperature_outside=not lo<=temp<=hi,humidity_outside=None,source_reference=item['source_reference']))
        times.append(t);previous=t
    segments=[];gaps=[];boundaries=[start]+times+[end]
    for i in range(len(boundaries)-1):
        a,b=boundaries[i:i+2]
        if a==b: continue
        elapsed=D((b-a).days*86400+(b-a).seconds)/60;edge=i==0 or i==len(boundaries)-2
        segment=dict(start=a.isoformat(),end=b.isoformat(),elapsed_minutes=exact(elapsed),
            measurement_gap=elapsed>maxgap or edge,actual_excursion_duration_minutes=None,observation_interval_only=True)
        if not edge:segment['endpoint_excursion_observed']=any(readings[j]['temperature_outside'] for j in (i-1,i))
        segments.append(segment)
        if segment['measurement_gap']:gaps.append(dict(kind='measurement_gap',**segment))
    if applicability=='unknown':gaps.append(dict(kind='humidity_applicability_unknown',source_reference=r['source_reference']))
    expiry=[];expiry_gaps=[];expiry_performed='expiry_items' in c
    if expiry_performed:
        expiry,expiry_gaps=_storage_expiry_rows(c,observed,expected);gaps.extend(expiry_gaps)
    elif 'expiry_alert_days' in c:fail('expiry_alert_requires_expiry_items')
    excursion=any(row['temperature_outside'] for row in readings)
    return dict(mode='temperature_only',instruction=deepcopy(r),observed_at=c['observed_at'],timezone_offset=offset,
        expiry_alert_days=integer(c['expiry_alert_days'],'expiry_alert_days',0,3650) if expiry_performed else None,
        location=optional_text(c,'location'),responsible=optional_text(c,'responsible'),
        zones=stringlist(c['zones'],'zones') if 'zones' in c else None,
        humidity_applicability=applicability,humidity_check_performed=False,temperature_check_performed=True,
        expiry_check_performed=expiry_performed,readings=readings,segments=segments,gaps=gaps,
        expiry_rows=expiry,expiry_semantics_gaps=expiry_gaps,excursion_observed=excursion,
        rule_review_gaps=retrospective_gaps(r,start.date()),
        quarantine_review_required=excursion or bool(gaps) or any(x['quarantine_review_required'] for x in expiry),
        actual_excursion_duration_minutes=None,interpolation_used=False,
        decision_scope='temperature_observations_only_no_batch_fitness_decision')

def quantity(v, n):
    v = obj(v, n); amount = num(v.get('amount'), n + '_amount', '0.00000001')
    unit = v.get('unit')
    if unit not in ('mg', 'g', 'mL'): fail(n + '_supported_unit_required')
    return (amount / 1000 if unit == 'mg' else amount), ('g' if unit in ('mg', 'g') else 'mL')

def convert(q, target, ingredient):
    amount, unit = q
    if unit == target: return amount
    density = num(ingredient.get('density_g_mL'), 'density_g_mL', '0.00000001', '100')
    ref(ingredient.get('density_reference'))
    return amount * density if unit == 'mL' else amount / density

def active_mass(q, ingredient):
    basis = obj(ingredient.get('active_basis'), 'active_basis'); ref(basis.get('source_reference'))
    mode = basis.get('mode')
    if mode in ('pure_substance','stock_mass_fraction'):
        fraction = num(basis.get('active_fraction'), 'active_fraction', '0.00000001', '1')
        return convert(q,'g',ingredient)*fraction
    if mode == 'stock_mass_per_volume':
        strength = num(basis.get('strength_mg_mL'), 'strength_mg_mL', '0.00000001', '100000')
        return convert(q,'mL',ingredient)*strength/1000
    fail('supported_active_basis_required')

@guard
def compounding(c, asof):
    reject_keys(c,{'actual_concentration'})
    number=optional_text(c,'number',200)
    r = rule(c.get('control_rule'), asof, 'control_rule')
    tolerance = num(r.get('relative_tolerance'), 'relative_tolerance', '0', '1')
    text(c.get('prescription_text'), 'prescription_text', 12000); ref(c.get('prescription_source_reference'))
    text(c.get('ppk_text'), 'ppk_text', 12000); ref(c.get('ppk_source_reference'))
    expected_total = quantity(c.get('prescribed_total'), 'prescribed_total')
    actual_total = quantity(c.get('recorded_total'), 'recorded_total')
    if expected_total[1] != actual_total[1]: fail('final_mass_volume_comparison_requires_same_dimension')
    target = expected_total[1]; prepared = []; seen = set(); sums = [D(0), D(0)]; comparable = [True, True]
    for item in rows(c.get('ingredients'), 'ingredients', 1, 20):
        item = obj(item, 'ingredient'); ident = text(item.get('id'), 'ingredient_id', 200)
        if ident in seen: fail('duplicate_ingredient_id')
        seen.add(ident); ref(item.get('source_reference'))
        role_ = item.get('role')
        if role_ not in ('active', 'excipient'): fail('ingredient_role_required')
        expected = quantity(item.get('prescribed'), 'prescribed'); actual = quantity(item.get('recorded'), 'recorded')
        if 'actual_concentration' in item: fail('supplied_actual_concentration_not_supported')
        recorded_match = convert(actual, expected[1], item)
        delta = recorded_match - expected[0]; relative = delta / expected[0]
        for j, q in enumerate((expected, actual)):
            if q[1] == target: sums[j] += q[0]
            elif 'density_g_mL' in item: sums[j] += convert(q, target, item)
            else: comparable[j] = False
        concentration = None
        if role_ == 'active':
            ep = active_mass(expected,item); ap = active_mass(actual,item)
            factor = D(100) if target == 'g' else D(1000)
            concentration = dict(unit='percent_m_m' if target == 'g' else 'mg/mL',
                prescribed=exact(ep / expected_total[0] * factor),
                recorded=exact(ap / actual_total[0] * factor), derived_from_ingredient_and_final_quantity=True)
        prepared.append(dict(id=ident, role=role_, prescribed=deepcopy(item['prescribed']), recorded=deepcopy(item['recorded']),
            comparison_unit=expected[1], absolute_difference=exact(delta), relative_difference=exact(relative),
            exceeds_selected_tolerance=abs(relative) > tolerance, concentration=concentration,
            active_basis=deepcopy(item.get('active_basis')), source_reference=item['source_reference']))
    total_delta = actual_total[0] - expected_total[0]
    return dict(prescription_text=c['prescription_text'], ppk_text=c['ppk_text'], control_rule=deepcopy(r),
        number=number,
        ingredient_checks=prepared, final_unit=target, prescribed_total=exact(expected_total[0]), recorded_total=exact(actual_total[0]),
        final_absolute_difference=exact(total_delta), final_relative_difference=exact(total_delta/expected_total[0]),
        final_exceeds_selected_tolerance=abs(total_delta/expected_total[0]) > tolerance,
        ingredient_sum_checks=[dict(record=label, dimension_comparable=comparable[i],
            sum_in_final_unit=exact(sums[i]) if comparable[i] else None,
            difference_from_final=exact(sums[i]-(expected_total,actual_total)[i][0]) if comparable[i] else None,
            volume_additivity_not_established=target=='mL') for i,label in enumerate(('prescription','ppk'))],
        decision_scope='arithmetic_only_no_formula_dose_or_release_decision')

@guard
def zhnvlp_pricing(c, asof):
    r = rule(c.get('regional_rule'), asof, 'regional_rule'); tax = rule(c.get('tax_rule'), asof, 'tax_rule')
    for k in ('region', 'category'): text(r.get(k), k, 200)
    wholesale = num(r.get('wholesale_rate'), 'wholesale_rate', '0', '5')
    retail = num(r.get('retail_rate'), 'retail_rate', '0', '5')
    lower = num(r.get('category_min_net'), 'category_min_net'); upper = num(r.get('category_max_net'), 'category_max_net')
    lower_inclusive = boolean(r.get('category_min_inclusive'), 'category_min_inclusive')
    upper_inclusive = boolean(r.get('category_max_inclusive'), 'category_max_inclusive')
    if lower > upper: fail('pricing_category_range_reversed')
    p = obj(c.get('prices'), 'prices'); ref(p.get('source_reference')); text(p.get('item_id'), 'item_id', 200)
    d = day(p.get('price_date'), 'price_date')
    if d > asof: fail('price_after_as_of')
    for selected in (r, tax):
        if not in_rule(selected, d):
            fail('price_date_outside_selected_rule')
    actual = num(p.get('manufacturer_actual_net'), 'manufacturer_actual_net', '0.00000001')
    cap = num(p.get('registered_cap_net'), 'registered_cap_net', '0.00000001')
    net = num(p.get('purchase_net'), 'purchase_net'); vat = num(p.get('purchase_vat'), 'purchase_vat')
    gross = num(p.get('purchase_gross'), 'purchase_gross'); proposed = num(p.get('proposed_gross'), 'proposed_gross')
    selected_wholesale = num(p.get('wholesale_markup_net'), 'wholesale_markup_net'); ref(p.get('wholesale_reference'))
    if gross != net + vat: fail('purchase_net_vat_gross_identity')
    output_rate = num(tax.get('output_vat_rate'), 'output_vat_rate', '0', '1')
    mode = tax.get('mode')
    if mode not in ('deductible_vat', 'non_deductible_no_output_vat', 'non_deductible_output_vat'): fail('explicit_tax_model_required')
    if mode == 'non_deductible_no_output_vat' and output_rate != 0: fail('no_output_vat_requires_zero_rate')
    purchase_base = net if mode == 'deductible_vat' else gross
    retail_amount = actual * retail; wholesale_limit = actual * wholesale
    taxable_base = purchase_base + retail_amount; output_vat = taxable_base * output_rate
    ceiling = taxable_base + output_vat
    findings = list(dict.fromkeys(retrospective_gaps(r,d)+retrospective_gaps(tax,d)))
    for condition, code in ((actual > cap, 'actual_manufacturer_above_registered_cap'),
        (actual < lower or actual==lower and not lower_inclusive or actual > upper or actual==upper and not upper_inclusive, 'manufacturer_price_outside_selected_category'),
        (net-actual-selected_wholesale != 0, 'price_protocol_reconciliation_gap_requires_review'),
        (selected_wholesale > wholesale_limit, 'selected_wholesale_markup_above_selected_limit'),
        (proposed > ceiling, 'proposed_above_conditional_ceiling')):
        if condition: findings.append(code)
    return dict(item_id=p['item_id'], prices=deepcopy(p), regional_rule=deepcopy(r), tax_rule=deepcopy(tax),
        price_components=dict(manufacturer_actual_net=exact(actual), registered_cap_net=exact(cap),
            purchase_minus_manufacturer_net=exact(net-actual), selected_wholesale_markup_net=exact(selected_wholesale),
            reconciliation_gap_net=exact(net-actual-selected_wholesale), selected_wholesale_limit=exact(wholesale_limit),
            retail_markup_base=exact(actual), selected_retail_markup=exact(retail_amount), purchase_base=exact(purchase_base),
            taxable_base=exact(taxable_base), output_vat=exact(output_vat)),
        conditional_ceiling_unrounded=exact(ceiling), conditional_ceiling_display=money(ceiling),
        proposed_minus_ceiling=exact(proposed-ceiling), findings=findings,
        rounding='comparison_uses_unrounded_decimal_display_half_up_2_places',
        decision_scope='conditional_calculation_only_no_price_approval')

@guard
def nmo_pharma(c, asof):
    r = rule(c.get('qualification_rule'), asof, 'qualification_rule')
    for key in ('role', 'education_level', 'specialty'): text(r.get(key), 'rule_' + key, 200)
    training = stringlist(r.get('required_training_specialties'), 'required_training_specialties')
    minexp = integer(r.get('min_experience_months'), 'min_experience_months', 0, 1200)
    totalmin = num(r.get('total_hours_min'), 'total_hours_min', '0', '10000')
    pkmin = num(r.get('pk_hours_min'), 'pk_hours_min', '0', '10000')
    if pkmin > totalmin: fail('pk_min_exceeds_total_min')
    lead = integer(r.get('submission_lead_calendar_days'), 'submission_lead_calendar_days', 0, 365)
    statuses = stringlist(r.get('report_statuses'), 'report_statuses', 1)
    allowed_delivery = stringlist(r.get('allowed_delivery_modes'), 'allowed_delivery_modes', 1)
    delivery_policy = r.get('delivery_mismatch_policy')
    if delivery_policy not in ('exclude','flag_only'): fail('selected_delivery_mismatch_policy_required')
    person = obj(c.get('person'), 'person'); ref(person.get('source_reference'))
    optional_text(person,'workplace')
    for key in ('role', 'education_level', 'specialty'): text(person.get(key), 'person_' + key, 200)
    completed_training = stringlist(person.get('training_specialties'), 'training_specialties')
    experience = integer(person.get('experience_months'), 'experience_months', 0, 1200)
    acc = obj(c.get('accreditation'), 'accreditation'); ref(acc.get('source_reference'))
    begin = day(acc.get('cycle_start'), 'cycle_start'); end = day(acc.get('valid_through'), 'valid_through')
    if begin > asof or begin >= end or (end-begin).days > 3653: fail('accreditation_cycle_range')
    specialty = text(acc.get('specialty'), 'accreditation_specialty', 200)
    report = obj(c.get('report'), 'report'); ref(report.get('source_reference')); text(report.get('status'), 'report_status', 200)
    optional_text(report,'activity_description',4000)
    totals = {'pk': D(0), 'nmo': D(0)}; zet = D(0); seen_docs = {}; seen_ids = {}; activity_rows = []
    for item in rows(c.get('activities'), 'activities', 0, 40):
        item = obj(item, 'activity'); ident = text(item.get('id'), 'activity_id', 200)
        doc = text(item.get('document_id'), 'document_id', 200); ref(item.get('source_reference'))
        kind = item.get('kind')
        if kind not in ('pk', 'nmo'): fail('activity_kind_required')
        hours = num(item.get('hours'), 'activity_hours', '0', '10000'); credits = num(item.get('zet'), 'activity_zet', '0', '10000')
        ended = day(item.get('ended'), 'activity_ended'); spec = text(item.get('specialty'), 'activity_specialty', 200)
        delivery = text(item.get('delivery_mode'), 'delivery_mode', 100)
        documented = item.get('document_status')
        if documented not in ('provided', 'missing'): fail('activity_document_status_required')
        signature = (kind, hours, credits, ended, spec, delivery, documented)
        if doc in seen_docs and seen_docs[doc] != signature or ident in seen_ids and seen_ids[ident] != (doc, signature):
            fail('conflicting_duplicate_education_document')
        duplicate = doc in seen_docs or ident in seen_ids
        seen_docs[doc] = signature; seen_ids[ident] = (doc, signature)
        reasons = []
        if duplicate: reasons.append('duplicate_document_or_activity')
        if documented != 'provided': reasons.append('supporting_document_missing')
        if not begin <= ended <= min(asof, end): reasons.append('outside_observed_accreditation_cycle')
        if spec != specialty: reasons.append('specialty_mismatch')
        delivery_mismatch = delivery not in allowed_delivery
        if delivery_mismatch and delivery_policy=='exclude': reasons.append('delivery_mode_outside_selected_rule')
        if not reasons: totals[kind] += hours; zet += credits
        activity_rows.append(dict(id=ident, document_id=doc, kind=kind, hours=exact(hours), zet=exact(credits),
            ended=item['ended'], specialty=spec, delivery_mode=delivery, included_in_documented_total=not reasons,
            exclusion_reasons=reasons, delivery_mode_mismatch=delivery_mismatch, source_reference=item['source_reference']))
    total = totals['pk'] + totals['nmo']; gaps = []
    for key in ('role', 'education_level', 'specialty'):
        if person[key] != r[key]: gaps.append('selected_' + key + '_mismatch')
    if specialty != person['specialty']: gaps.append('accreditation_specialty_mismatch')
    missing_training = [x for x in training if x not in completed_training]
    if missing_training: gaps.append('selected_training_missing')
    if experience < minexp: gaps.append('below_selected_experience')
    if total < totalmin: gaps.append('below_selected_total_hours')
    if totals['pk'] < pkmin: gaps.append('below_selected_pk_hours')
    if report['status'] not in statuses: gaps.append('report_status_requires_review')
    if any(x['delivery_mode_mismatch'] for x in activity_rows): gaps.append('delivery_modes_require_review')
    if end < asof: gaps.append('supplied_accreditation_date_passed')
    return dict(person=deepcopy(person), accreditation=deepcopy(acc), report=deepcopy(report),
        qualification_rule=deepcopy(r), activities=activity_rows, documented_total_hours=exact(total),
        documented_pk_hours=exact(totals['pk']), documented_other_nmo_hours=exact(totals['nmo']), documented_zet=exact(zet),
        total_hours_gap=exact(max(D(0),totalmin-total)), pk_hours_gap=exact(max(D(0),pkmin-totals['pk'])),
        missing_training_specialties=missing_training, findings=gaps,
        conditional_submission_target=(end-timedelta(days=lead)).isoformat(),
        submission_target_kind='selected_calendar_day_planning_assumption',
        zet_not_equated_to_hours=True, delivery_modes_checked_against_selected_rule=True,
        decision_scope='portfolio_gap_draft_only_no_qualification_or_practice_right')

def input_units(function, data):
    if function not in FUNCTIONS: fail('unknown_calculation_function')
    globals()[function](data)
    bounded_tree(data); c = obj(data, 'data'); units = {}
    def put(path, unit, when=None):
        units[path] = {'unit':unit,'not_after':when} if when else unit
    if function == 'rx_dispensing':
        put('/prescription/quantity', c['prescription']['quantity_unit'], c['contact_date'])
        put('/requested_quantity', c['prescription']['quantity_unit'])
        put('/rule/max_quantity', c['rule']['quantity_unit'], c['as_of'])
        mode=c['rule']['validity_mode']
        if mode=='calendar_days': put('/rule/valid_days', 'day', c['as_of'])
        elif mode in ('calendar_months','calendar_years'): put('/rule/valid_period','month' if mode=='calendar_months' else 'year',c['as_of'])
        if c.get('deferred') is not None: put('/deferred/rule/workdays', 'working_day', c['as_of'])
    elif function == 'storage_quality':
        if c.get('mode')=='expiry_only':
            put('/expiry_alert_days','day')
            return units
        if c.get('mode')=='temperature_only':
            for k in ('temperature_min','temperature_max'): put('/instruction/'+k,'degC',c['as_of'])
            put('/instruction/max_gap_minutes','minute',c['as_of'])
            for i,row in enumerate(c['measurements']):put(f'/measurements/{i}/temperature','degC',c['as_of'])
            if 'expiry_items' in c:put('/expiry_alert_days','day')
            return units
        for k in ('temperature_min','temperature_max'): put('/instruction/'+k, 'degC', c['as_of'])
        for k in ('humidity_min','humidity_max'): put('/instruction/'+k, 'percent_RH', c['as_of'])
        put('/instruction/max_gap_minutes','minute', c['as_of']); put('/expiry_alert_days','day')
        for i, row in enumerate(c['measurements']):
            for key, unit in (('temperature','degC'),('humidity','percent_RH')): put(f'/measurements/{i}/'+key, unit, c['as_of'])
    elif function == 'compounding':
        put('/control_rule/relative_tolerance','ratio',c['as_of'])
        for key in ('prescribed_total','recorded_total'): put('/'+key+'/amount', c[key]['unit'])
        for i, row in enumerate(c['ingredients']):
            for key in ('prescribed','recorded'): put(f'/ingredients/{i}/{key}/amount',row[key]['unit'])
            if 'density_g_mL' in row: put(f'/ingredients/{i}/density_g_mL','g/mL',c['as_of'])
            if row['role']=='active':
                basis=row['active_basis']
                key='strength_mg_mL' if basis['mode']=='stock_mass_per_volume' else 'active_fraction'
                put(f'/ingredients/{i}/active_basis/'+key,'mg/mL' if key=='strength_mg_mL' else 'ratio',c['as_of'])
    elif function == 'zhnvlp_pricing':
        for key in ('manufacturer_actual_net','registered_cap_net','purchase_net','purchase_vat','purchase_gross','proposed_gross','wholesale_markup_net'):
            put('/prices/'+key,'RUB',c['prices']['price_date'])
        for key in ('wholesale_rate','retail_rate'): put('/regional_rule/'+key,'ratio',c['as_of'])
        for key in ('category_min_net','category_max_net'): put('/regional_rule/'+key,'RUB',c['as_of'])
        put('/tax_rule/output_vat_rate','ratio',c['as_of'])
    else:
        for key in ('min_experience_months',): put('/qualification_rule/'+key,'month',c['as_of'])
        for key in ('total_hours_min','pk_hours_min'): put('/qualification_rule/'+key,'hour',c['as_of'])
        put('/qualification_rule/submission_lead_calendar_days','day')
        put('/person/experience_months','month',c['as_of'])
        for i, row in enumerate(c['activities']):
            put(f'/activities/{i}/hours','hour',c['as_of']); put(f'/activities/{i}/zet','ZET',c['as_of'])
    return units

def selected_texts(function, data):
    """Only literal source fragments; task choices and analysis are authored."""
    if function not in FUNCTIONS: fail('unknown_calculation_function')
    globals()[function](data)
    c = obj(data,'data'); selected = {}
    if function == 'compounding':
        for key in ('prescription_text','ppk_text'): selected['/'+key] = text(c.get(key),key,12000)
    if function=='storage_quality' and c.get('mode') in ('expiry_only','temperature_only'):
        for i,row in enumerate(c.get('expiry_items',[])):
            selected[f'/expiry_items/{i}/label_value']=text(row.get('label_value'),'expiry_label',4000)
    def walk(v, path=''):
        if type(v) is dict:
            for key, value in v.items():
                p = path + '/' + key.replace('~','~0').replace('/','~1')
                if key in ('quote','excerpt','instruction_text','rule_text','expiry_text'): selected[p] = text(value,key,12000)
                else: walk(value,p)
        elif type(v) is list:
            for i, value in enumerate(v): walk(value,path+'/'+str(i))
    walk(c)
    return selected


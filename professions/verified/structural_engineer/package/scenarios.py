"""Bounded local structural document reviews. No drawing, safety or substitution approval.

The program reviews explicitly supplied records. It neither parses CAD/IFC/BCF nor
establishes that selected legal excerpts apply. All arithmetic is Decimal-local.
"""
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal, Context, localcontext, InvalidOperation
import re

FUNCTIONS = ('kr_section', 'inspection', 'expertise_review', 'site_support')
SECTIONS = ('surveys', 'loads', 'schemes', 'materials', 'reliability', 'protection', 'graphics')
CHECK_CATEGORIES = ('general_data', 'reference_documents', 'specifications', 'details', 'stamps_signatures', 'changes')
SCOPE_KEYS = ('object_id', 'element_id', 'metric', 'component', 'axes', 'combination', 'limit_state', 'location', 'sign_convention', 'geometry_basis', 'boundary_basis', 'stiffness_basis', 'load_basis')


def fail(code):
    raise ValueError(code)


def obj(value, required=(), optional=()):
    if type(value) is not dict or set(value) - set(required) - set(optional) or set(required) - set(value):
        fail('scenario_object_fields')
    return value


def text(value, maximum=6000):
    if type(value) is not str or not value.strip() or len(value) > maximum or any(ord(c) < 32 and c not in '\n\r\t' for c in value):
        fail('scenario_text_required')
    return value  # retain the selected literal; no strip/rewriting


def rows(value, maximum=16):
    if type(value) is not list or len(value) > maximum:
        fail('scenario_row_limit')
    return value


def strings(value, maximum=16):
    return [text(v, 2000) for v in rows(value, maximum)]


def enum(value, options):
    if value not in options or type(value) is not str:
        fail('scenario_enum')
    return value


def day(value, cutoff=None):
    text(value, 10)
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        fail('scenario_date')
    if parsed.isoformat() != value or (cutoff is not None and value > cutoff):
        fail('scenario_date_cutoff')
    return value


def number(value):
    if type(value) is not str or not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?', value) or len(value) > 90:
        fail('scenario_exact_numeric_string')
    try: result = Decimal(value)
    except InvalidOperation: fail('scenario_numeric_bound')
    if not result.is_finite() or abs(result.as_tuple().exponent) > 100 or (result and not -50 <= result.adjusted() <= 50):
        fail('scenario_numeric_bound')
    return result


def fmt(value):
    return format(value, 'f')


def quantity(value, units, path, contracts, cutoff, positive=False, nonnegative=False, information_cutoff=None):
    obj(value, ('value', 'unit', 'source_reference'), ('observed_date',))
    n = number(value['value']); unit = text(value['unit'], 80); text(value['source_reference'], 150)
    if units is not None and unit not in units:
        fail('scenario_quantity_unit')
    if positive and n <= 0 or nonnegative and n < 0:
        fail('scenario_quantity_range')
    limit = day(value['observed_date'], cutoff) if 'observed_date' in value else cutoff
    contracts[path + '/value'] = {'unit': unit, 'effective_not_after': cutoff, 'published_not_after': information_cutoff or cutoff}
    if 'observed_date' in value: contracts[path + '/value']['effective_date'] = limit
    return deepcopy(value), n


def unique(items, field='id'):
    ids = [text(i[field], 150) for i in items]
    if len(ids) != len(set(ids)):
        fail('scenario_duplicate_identity')
    return set(ids)


def budget(value):
    """Bound combined raw leaves before evidence: this is a bound, not truncation."""
    count = 0
    def visit(v, depth):
        nonlocal count
        if depth > 18:
            fail('scenario_nesting_limit')
        if type(v) is dict:
            if any(type(k) is not str for k in v): fail('scenario_string_keys')
            for item in v.values(): visit(item, depth + 1)
        elif type(v) is list:
            for item in v: visit(item, depth + 1)
        elif v is not None:
            count += 1
            if type(v) not in (str, bool): fail('scenario_no_untyped_numeric_leaf')
        if count > 900: fail('scenario_fact_budget')
    visit(value, 0)


def base(data, required, optional):
    obj(data, ('as_of', 'jurisdiction') + tuple(required), tuple(optional) + ('selected_requirements', 'selected_applicability_date'))
    budget(data); day(data['as_of']); enum(data['jurisdiction'], ('RU',))
    if 'selected_applicability_date' in data:
        day(data['selected_applicability_date'], data['as_of'])


def requirements(data):
    out, gaps = [], []
    selected_date = data.get('selected_applicability_date')
    for r in rows(data.get('selected_requirements', []), 12):
        obj(r, ('id', 'document_identity', 'edition', 'publication_date', 'effective_from', 'effective_to', 'clause', 'excerpt', 'source_reference'))
        for k in ('id', 'document_identity', 'edition', 'clause', 'excerpt', 'source_reference'): text(r[k])
        day(r['publication_date'], data['as_of'])
        for k in ('effective_from', 'effective_to'):
            if r[k] is not None: day(r[k])
        if r['effective_from'] and r['effective_to'] and r['effective_from'] > r['effective_to']:
            fail('scenario_requirement_window_reversed')
        in_window = None if selected_date is None or r['effective_from'] is None else (
            selected_date >= r['effective_from'] and (r['effective_to'] is None or selected_date <= r['effective_to']))
        item = deepcopy(r)
        item.update(selected_applicability_date=selected_date, selected_date_within_supplied_window=in_window,
                    publication_after_selected_date=None if selected_date is None else r['publication_date'] > selected_date,
                    legal_applicability_established=False)
        out.append(item)
        if selected_date is None: gaps.append({'kind': 'requirement_applicability_date_missing', 'id': r['id']})
        elif in_window is None: gaps.append({'kind': 'requirement_effective_start_unknown', 'id': r['id']})
        elif not in_window: gaps.append({'kind': 'requirement_selected_date_outside_window', 'id': r['id']})
        if selected_date is not None and r['publication_date'] > selected_date:
            gaps.append({'kind': 'requirement_published_after_selected_date_review_needed', 'id': r['id']})
        if r['effective_to'] is None: gaps.append({'kind': 'requirement_effective_end_unknown', 'id': r['id']})
    unique(out)
    if not out: gaps.append({'kind': 'selected_requirements_missing'})
    return out, gaps


def refs(value, known, gaps, owner):
    values = strings(value, 12)
    for identity in values:
        if identity not in known: gaps.append({'kind': 'requirement_id_not_supplied', 'id': owner, 'target_id': identity})
    return values


def document_inventory(items, cutoff):
    output = []
    for r in rows(items, 24):
        obj(r, ('id', 'revision', 'date', 'source_reference'), ('title',))
        for k in ('id', 'revision', 'source_reference'): text(r[k], 200)
        day(r['date'], cutoff)
        if 'title' in r: text(r['title'])
        output.append(deepcopy(r))
    unique(output)
    return output


def decisions(items, issue_ids, cutoff, gaps):
    output = []
    for r in rows(items, 16):
        obj(r, ('id', 'issue_id', 'date', 'author', 'decision_text', 'state'), ('source_reference',))
        for k in ('id', 'issue_id', 'author', 'decision_text'): text(r[k])
        day(r['date'], cutoff); enum(r['state'], ('proposed', 'recorded'))
        if r['state'] == 'recorded': text(r.get('source_reference'), 150)
        elif 'source_reference' in r: text(r['source_reference'], 150)
        if r['issue_id'] not in issue_ids: gaps.append({'kind': 'decision_issue_not_supplied', 'id': r['id'], 'target_id': r['issue_id']})
        output.append(dict(deepcopy(r), authority_established=False))
    unique(output)
    return output


def deadline(value, cutoff):
    if value is None: return None
    obj(value, ('date', 'source_reference'))
    day(value['date']); text(value['source_reference'], 150)
    return dict(deepcopy(value), overdue_at_as_of=value['date'] < cutoff,
                interpretation='provided_date_legal_applicability_not_established')


def _kr(data, units):
    base(data, ('stage', 'object', 'structure_class', 'content_items'), ('sheets', 'specifications', 'details', 'revisions', 'checklist'))
    enum(data['stage'], ('P', 'R')); text(data['object']); text(data['structure_class'], 200)
    req, gaps = requirements(data); known = {r['id'] for r in req}
    content = []
    for r in rows(data['content_items'], 24):
        obj(r, ('id', 'section', 'text', 'requirement_ids'), ('source_reference', 'authorship'))
        text(r['id'], 150); enum(r['section'], SECTIONS); text(r['text'])
        authorship = enum(r.get('authorship', 'selected_record'), ('selected_record', 'proposed_draft'))
        if authorship == 'selected_record' or 'source_reference' in r: text(r.get('source_reference'), 150)
        refs(r['requirement_ids'], known, gaps, r['id']); content.append(dict(deepcopy(r), authorship=authorship))
    unique(content)
    for section in SECTIONS:
        if not any(c['section'] == section for c in content): gaps.append({'kind': 'section_content_missing', 'section': section})
    sheets = []
    for s in rows(data.get('sheets', []), 16):
        obj(s, ('id', 'mark', 'title', 'revision', 'date', 'source_reference'), ('links', 'specification_ids', 'detail_ids', 'stamp_record'))
        for k in ('id', 'mark', 'title', 'revision', 'source_reference'): text(s[k])
        day(s['date'], data['as_of']); row = deepcopy(s)
        row['links'] = rows(s.get('links', []), 12)
        for link in row['links']:
            obj(link, ('target_id', 'expected_revision')); text(link['target_id'], 150); text(link['expected_revision'], 150)
        row['specification_ids'] = strings(s.get('specification_ids', []), 12)
        row['detail_ids'] = strings(s.get('detail_ids', []), 12)
        if 'stamp_record' in s:
            obj(s['stamp_record'], ('excerpt', 'source_reference')); text(s['stamp_record']['excerpt']); text(s['stamp_record']['source_reference'], 150)
        else: gaps.append({'kind': 'stamp_record_missing', 'id': s['id']})
        sheets.append(row)
    sheet_ids = [s['id'] for s in sheets]
    duplicates = sorted({v for v in sheet_ids if sheet_ids.count(v) > 1})
    for identity in duplicates: gaps.append({'kind': 'conflicting_sheet_identity', 'id': identity})
    specs = []
    for i, s in enumerate(rows(data.get('specifications', []), 12)):
        obj(s, ('id', 'revision', 'source_reference', 'items'))
        for k in ('id', 'revision', 'source_reference'): text(s[k])
        row = deepcopy(s)
        for j, item in enumerate(rows(s['items'], 12)):
            obj(item, ('id', 'description'), ('quantity',)); text(item['id']); text(item['description'])
            if 'quantity' in item: quantity(item['quantity'], None, f'/specifications/{i}/items/{j}/quantity', units, data['as_of'], nonnegative=True)
        unique(s['items']); specs.append(row)
    spec_ids = unique(specs); details = document_inventory(data.get('details', []), data['as_of']); detail_ids = {r['id'] for r in details}
    links = []
    for s in sheets:
        for link in s['links']:
            targets = [v for v in sheets if v['id'] == link['target_id']]
            status = 'target_missing' if not targets else 'target_ambiguous' if len(targets) > 1 else 'revision_matches' if targets[0]['revision'] == link['expected_revision'] else 'revision_mismatch'
            links.append({'sheet_id': s['id'], **link, 'status': status})
            if status != 'revision_matches': gaps.append({'kind': status, 'id': s['id'], 'target_id': link['target_id']})
        for key, available in (('specification_ids', spec_ids), ('detail_ids', detail_ids)):
            for identity in s[key]:
                if identity not in available: gaps.append({'kind': 'linked_record_missing', 'id': s['id'], 'target_id': identity})
    revisions = []
    for r in rows(data.get('revisions', []), 16):
        obj(r, ('id', 'document_id', 'from_revision', 'to_revision', 'date', 'reason', 'affected_ids', 'source_reference'), ('supersedes_id',))
        for k in ('id', 'document_id', 'from_revision', 'to_revision', 'reason', 'source_reference'): text(r[k])
        day(r['date'], data['as_of']); strings(r['affected_ids'])
        if 'supersedes_id' in r: text(r['supersedes_id'], 150)
        for identity in [r['document_id']] + r['affected_ids']:
            if identity not in set(sheet_ids) | spec_ids | detail_ids: gaps.append({'kind': 'revision_document_missing', 'id': r['id'], 'target_id': identity})
        revisions.append(deepcopy(r))
    unique(revisions)
    bare_ids = [r['id'] for group in (content, sheets, specs, details, revisions) for r in group]
    ambiguous_ids = sorted({identity for identity in bare_ids if bare_ids.count(identity) > 1})
    for identity in ambiguous_ids: gaps.append({'kind': 'bare_evidence_id_ambiguous', 'id': identity})
    by_revision = {r['id']: r for r in revisions}
    for r in revisions:
        seen = set(); current = r
        while current.get('supersedes_id'):
            identity = current['supersedes_id']
            if identity not in by_revision:
                gaps.append({'kind': 'superseded_revision_missing', 'id': r['id'], 'target_id': identity}); break
            if identity in seen:
                gaps.append({'kind': 'revision_chain_cycle', 'id': r['id']}); break
            seen.add(identity); current = by_revision[identity]
    checklist = []
    for r in rows(data.get('checklist', []), 18):
        obj(r, ('id', 'category', 'requirement_id', 'evidence_ids', 'review_note'), ('applicability',))
        text(r['id']); enum(r['category'], CHECK_CATEGORIES); text(r['review_note']); text(r['requirement_id'], 150)
        applicability = enum(r.get('applicability', 'unknown'), ('applicable', 'not_applicable', 'unknown'))
        ids = strings(r['evidence_ids']); pool = {c['id'] for c in content} | set(sheet_ids) | spec_ids | detail_ids | {v['id'] for v in revisions}
        missing = [v for v in ids if v not in pool]
        ambiguous_evidence = [v for v in ids if v in ambiguous_ids]
        draft_ids = [v for v in ids if v not in ambiguous_ids and any(c['id'] == v and c['authorship'] == 'proposed_draft' for c in content)]
        if r['requirement_id'] not in known: gaps.append({'kind': 'requirement_id_not_supplied', 'id': r['id'], 'target_id': r['requirement_id']})
        status = 'selected_nonapplicability_requires_review' if applicability == 'not_applicable' else 'evidence_missing' if not ids or missing else 'selected_evidence_linked_not_compliance'
        if applicability != 'not_applicable' and draft_ids and not missing: status = 'proposed_content_linked_requires_review'
        if ambiguous_evidence: status = 'target_ambiguous'
        if missing or not ids and applicability != 'not_applicable': gaps.append({'kind': 'checklist_evidence_missing', 'id': r['id']})
        if applicability == 'unknown': gaps.append({'kind': 'checklist_applicability_unknown', 'id': r['id']})
        checklist.append(dict(deepcopy(r), applicability=applicability, missing_evidence_ids=missing, ambiguous_evidence_ids=ambiguous_evidence, proposed_content_ids=draft_ids, status=status))
    unique(checklist)
    for category in CHECK_CATEGORIES:
        if not any(r['category'] == category for r in checklist): gaps.append({'kind': 'checklist_category_not_reviewed', 'category': category})
    if not sheets: gaps.append({'kind': 'drawing_inventory_missing'})
    requirement_review = []
    for r in req:
        matches = [c['id'] for c in content if r['id'] in c['requirement_ids'] and c['authorship'] == 'selected_record']
        drafts = [c['id'] for c in content if r['id'] in c['requirement_ids'] and c['authorship'] == 'proposed_draft']
        checks = [c['id'] for c in checklist if c['requirement_id'] == r['id']]
        requirement_review.append({'id': r['id'], 'content_ids': matches, 'proposed_content_ids': drafts, 'checklist_ids': checks,
                                   'status': 'selected_evidence_linked_not_compliance' if matches else 'proposed_content_linked_requires_review' if drafts else 'evidence_missing'})
        if not matches and not drafts and not checks: gaps.append({'kind': 'selected_requirement_unmapped', 'id': r['id']})
    return dict(stage=data['stage'], object=data['object'], structure_class=data['structure_class'], selected_requirements=req,
                content_items=content, sections={k: [c for c in content if c['section'] == k] for k in SECTIONS},
                sheets=sheets, specifications=specs, details=details, link_checks=links, revisions=revisions, checklist=checklist, requirement_review=requirement_review, ambiguous_record_ids=ambiguous_ids,
                graphical_content_generated=False, design_compliance_established=False, evidence_gaps=gaps)


def _inspection(data, units):
    base(data, ('object', 'goal', 'access', 'structures', 'program', 'defects'), ('construction_year', 'archive_records', 'photos', 'test_results', 'verification_calculation', 'selected_category_record', 'recommendations'))
    for k in ('object', 'goal', 'access'): text(data[k])
    if 'construction_year' in data: text(data['construction_year'], 40)
    req, gaps = requirements(data); known = {r['id'] for r in req}
    structures = []
    for r in rows(data['structures'], 16):
        obj(r, ('id', 'description', 'source_reference')); text(r['id'], 150); text(r['description']); text(r['source_reference'], 150); structures.append(deepcopy(r))
    structure_ids = unique(structures)
    archives = document_inventory(data.get('archive_records', []), data['as_of'])
    program = []
    for r in rows(data['program'], 16):
        obj(r, ('id', 'method', 'target', 'proposed_work', 'requirement_ids'), ('owner',))
        for k in ('id', 'target', 'proposed_work'): text(r[k])
        enum(r['method'], ('visual', 'instrumental', 'opening', 'laboratory')); refs(r['requirement_ids'], known, gaps, r['id'])
        if 'owner' in r: text(r['owner'])
        program.append(dict(deepcopy(r), work_performed_by_tool=False))
    unique(program)
    if not program: gaps.append({'kind': 'inspection_program_missing'})
    photos = []
    for r in rows(data.get('photos', []), 16):
        obj(r, ('id', 'captured_at', 'caption', 'source_reference', 'local_identifier'))
        for k in ('id', 'caption', 'source_reference', 'local_identifier'): text(r[k])
        # metadata only, never reads a path or classifies image pixels
        if '/' in r['local_identifier'] or '\\' in r['local_identifier'] or ':' in r['local_identifier']: fail('photo_local_basename_required')
        text(r['captured_at'], 40)
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2}|Z)', r['captured_at']): fail('photo_timestamp_offset_required')
        try: dt = datetime.fromisoformat(r['captured_at'])
        except (ValueError, TypeError): fail('photo_timestamp_offset_required')
        if dt.utcoffset() is None or abs(dt.utcoffset().total_seconds()) > 14 * 3600: fail('photo_timestamp_offset_required')
        day(dt.date().isoformat(), data['as_of']); photos.append(dict(deepcopy(r), image_content_examined=False))
    photo_ids = unique(photos); defects = []; risk = []
    for i, r in enumerate(rows(data['defects'], 16)):
        obj(r, ('id', 'structure_id', 'location', 'description', 'observed_date', 'source_reference', 'urgency', 'urgency_basis'), ('measurements', 'photo_ids', 'cause_hypothesis', 'hazard_description', 'owner', 'proposed_actions'))
        for k in ('id', 'structure_id', 'location', 'description', 'source_reference', 'urgency_basis'): text(r[k])
        day(r['observed_date'], data['as_of']); urgency = enum(r['urgency'], ('reported_urgent', 'not_reported_urgent', 'unknown'))
        if r['structure_id'] not in structure_ids: gaps.append({'kind': 'defect_structure_missing', 'id': r['id']})
        for k in ('cause_hypothesis', 'hazard_description', 'owner'):
            if r.get(k) is not None: text(r[k])
        measurements = []
        for j, m in enumerate(rows(r.get('measurements', []), 8)):
            obj(m, ('id', 'kind', 'quantity', 'method'), ('instrument', 'uncertainty'))
            for k in ('id', 'kind', 'method'): text(m[k])
            q, _ = quantity(m['quantity'], None, f'/defects/{i}/measurements/{j}/quantity', units, r['observed_date'], information_cutoff=data['as_of'])
            if 'instrument' in m: text(m['instrument'])
            if 'uncertainty' in m:
                quantity(m['uncertainty'], (q['unit'],), f'/defects/{i}/measurements/{j}/uncertainty', units, r['observed_date'], nonnegative=True, information_cutoff=data['as_of'])
            measurements.append(deepcopy(m))
        unique(measurements)
        selected_photos = strings(r.get('photo_ids', []))
        if not selected_photos: gaps.append({'kind': 'defect_photo_metadata_missing', 'id': r['id']})
        for identity in selected_photos:
            if identity not in photo_ids: gaps.append({'kind': 'defect_photo_id_not_supplied', 'id': r['id'], 'target_id': identity})
        if urgency == 'unknown': gaps.append({'kind': 'defect_urgency_not_established', 'id': r['id']})
        if r.get('owner') is None: gaps.append({'kind': 'risk_owner_missing', 'id': r['id']})
        row = dict(deepcopy(r), measurements=measurements, photo_ids=selected_photos, proposed_actions=strings(r.get('proposed_actions', [])),
                   immediate_human_escalation=urgency == 'reported_urgent', safety_established=False, cause_established=False)
        defects.append(row)
        if urgency == 'reported_urgent': risk.append(dict(row, escalation_instruction='escalate_to_responsible_person_now_do_not_wait_for_report',
                                                         temporary_measures='responsible_specialist_determines_measures_no_tool_permission'))
    unique(defects)
    tests = []
    for i, t in enumerate(rows(data.get('test_results', []), 16)):
        obj(t, ('id', 'description', 'observed_date', 'source_reference'), ('quantity',))
        for k in ('id', 'description', 'source_reference'): text(t[k])
        day(t['observed_date'], data['as_of'])
        if 'quantity' in t: quantity(t['quantity'], None, f'/test_results/{i}/quantity', units, t['observed_date'], information_cutoff=data['as_of'])
        tests.append(deepcopy(t))
    unique(tests)
    calc = data.get('verification_calculation')
    if calc is not None:
        obj(calc, ('excerpt', 'source_reference')); text(calc['excerpt']); text(calc['source_reference'], 150)
    else: gaps.append({'kind': 'verification_calculation_not_supplied'})
    category = data.get('selected_category_record')
    if category is not None:
        obj(category, ('excerpt', 'source_reference', 'date', 'author'))
        for k in ('excerpt', 'source_reference', 'author'): text(category[k])
        day(category['date'], data['as_of'])
    return dict(object=data['object'], goal=data['goal'], access=data['access'], construction_year=data.get('construction_year'),
                selected_requirements=req, archive_records=archives, structures=structures, program=program,
                defects=defects, risk_register=risk, immediate_escalation_required=bool(risk),
                photos=photos, test_results=tests, verification_calculation=deepcopy(calc), verification_calculation_performed=False,
                category_review={'selected_record': deepcopy(category), 'assignment_performed': False, 'status': 'human_specialist_category_only'},
                recommendations=strings(data.get('recommendations', [])), evidence_gaps=gaps)


def _second_run(value, cutoff, units):
    if value is None: return None
    obj(value, ('primary_run', 'secondary_run', 'comparisons'))
    for key in ('primary_run', 'secondary_run'):
        obj(value[key], ('program', 'version', 'model_revision', 'run_date', 'source_reference'))
        for k in ('program', 'version', 'model_revision', 'source_reference'): text(value[key][k])
        day(value[key]['run_date'], cutoff)
    output = []
    for i, r in enumerate(rows(value['comparisons'], 12)):
        obj(r, ('id', 'primary', 'secondary', 'tolerance')); text(r['id'], 150)
        vals = []; reasons = []
        for key in ('primary', 'secondary'):
            obj(r[key], ('quantity', 'scope'))
            obj(r[key]['scope'], SCOPE_KEYS)
            for val in r[key]['scope'].values(): text(val, 500)
            _, n = quantity(r[key]['quantity'], None, f'/second_run/comparisons/{i}/{key}/quantity', units, value[key+'_run']['run_date'], information_cutoff=cutoff)
            vals.append(n)
        _, tol = quantity(r['tolerance'], None, f'/second_run/comparisons/{i}/tolerance', units, cutoff, nonnegative=True)
        for key in SCOPE_KEYS:
            if r['primary']['scope'][key] != r['secondary']['scope'][key]: reasons.append('scope_mismatch:' + key)
        if r['primary']['quantity']['unit'] != r['secondary']['quantity']['unit']: reasons.append('comparison_units_differ')
        if r['primary']['quantity']['unit'] != r['tolerance']['unit']: reasons.append('tolerance_unit_differs')
        delta = vals[1] - vals[0] if not reasons else None
        output.append(dict(deepcopy(r), comparison_performed=not reasons, comparability_gaps=reasons,
                           signed_difference=fmt(delta) if delta is not None else None,
                           absolute_difference=fmt(abs(delta)) if delta is not None else None,
                           within_selected_tolerance=abs(delta) <= tol if delta is not None else None,
                           numerical_agreement_not_model_validation=True))
    unique(output)
    return dict(primary_run=deepcopy(value['primary_run']), secondary_run=deepcopy(value['secondary_run']), comparisons=output,
                solver_executed=False, independent_verification_established=False,
                distinct_program_names_supplied=value['primary_run']['program'] != value['secondary_run']['program'])


def _expertise(data, units):
    base(data, ('object', 'comments'), ('supplied_documents', 'decisions', 'second_run', 'scientific_support'))
    text(data['object']); req, gaps = requirements(data); known = {r['id'] for r in req}
    documents = document_inventory(data.get('supplied_documents', []), data['as_of']); docs = {d['id']: d for d in documents}
    comments = []
    for c in rows(data['comments'], 12):
        obj(c, ('id', 'excerpt', 'source_reference', 'requirement_ids', 'proposed_response', 'disposition'), ('proposed_changes', 'owner', 'due'))
        for k in ('id', 'excerpt', 'source_reference', 'proposed_response'): text(c[k])
        enum(c['disposition'], ('proposed_change', 'proposed_disagreement', 'needs_clarification'))
        refs(c['requirement_ids'], known, gaps, c['id'])
        if not c['requirement_ids']: gaps.append({'kind': 'comment_requirement_basis_missing', 'id': c['id']})
        if 'owner' in c: text(c['owner'])
        changes = []
        for change in rows(c.get('proposed_changes', []), 8):
            obj(change, ('document_id', 'from_revision', 'to_revision', 'description'))
            for v in change.values(): text(v)
            supplied = docs.get(change['document_id'])
            status = 'target_missing' if supplied is None else 'revision_matches' if supplied['revision'] == change['to_revision'] else 'revision_mismatch'
            changes.append(dict(deepcopy(change), supplied_revision=None if supplied is None else supplied['revision'], change_evidence_status=status,
                                content_change_verified=False))
            if status != 'revision_matches': gaps.append({'kind': 'changed_document_revision_not_supplied', 'id': c['id'], 'target_id': change['document_id']})
        if c['disposition'] == 'proposed_disagreement': gaps.append({'kind': 'disagreement_requires_responsible_calculation_review', 'id': c['id']})
        if not c.get('owner'): gaps.append({'kind': 'comment_owner_missing', 'id': c['id']})
        comments.append(dict(deepcopy(c), proposed_changes=changes, due=deadline(c.get('due'), data['as_of']),
                             expert_comment_closed=False, response_authorship='proposed_not_signed_or_submitted'))
    ids = unique(comments)
    second = _second_run(data.get('second_run'), data['as_of'], units)
    if not comments and (second is None or not second['comparisons']): fail('comments_or_second_run_comparisons_required')
    if second:
        if not second['comparisons']: gaps.append({'kind': 'second_run_comparisons_missing'})
        for r in second['comparisons']:
            for cause in r['comparability_gaps']: gaps.append({'kind': 'comparison_not_performed', 'id': r['id'], 'reason': cause})
    scientific = data.get('scientific_support')
    if scientific is not None: text(scientific)
    return dict(object=data['object'], selected_requirements=req, comments=comments, supplied_documents=documents, second_run=second,
                second_run_status='not_requested' if second is None else 'supplied_exports_compared_only' if second['comparisons'] else 'supplied_exports_no_comparisons',
                decision_log=decisions(data.get('decisions', []), ids, data['as_of'], gaps), scientific_support=scientific, evidence_gaps=gaps)


def _site(data, units):
    base(data, ('request', 'design_records', 'observations'), ('substitution', 'decisions', 'issue_history', 'rd_changes', 'required_checks', 'draft_response'))
    request = data['request']; obj(request, ('id', 'date', 'excerpt', 'source_reference', 'object_id', 'element_id'), ('due',))
    for k in ('id', 'excerpt', 'source_reference', 'object_id', 'element_id'): text(request[k])
    day(request['date'], data['as_of']); req, gaps = requirements(data)
    designs = []
    for r in rows(data['design_records'], 16):
        obj(r, ('id', 'revision', 'description', 'source_reference'), ('requirements',))
        for k in ('id', 'revision', 'description', 'source_reference'): text(r[k])
        if 'requirements' in r: strings(r['requirements'])
        designs.append(deepcopy(r))
    design_ids = unique(designs); observations = []
    for i, r in enumerate(rows(data['observations'], 16)):
        obj(r, ('id', 'date', 'description', 'source_reference', 'design_record_id', 'reported_relation'), ('quantity', 'urgency', 'owner'))
        for k in ('id', 'description', 'source_reference', 'design_record_id'): text(r[k])
        day(r['date'], data['as_of']); enum(r['reported_relation'], ('reported_deviation', 'reported_match', 'unknown'))
        if r['design_record_id'] not in design_ids: gaps.append({'kind': 'observation_design_record_missing', 'id': r['id']})
        if 'quantity' in r: quantity(r['quantity'], None, f'/observations/{i}/quantity', units, r['date'], information_cutoff=data['as_of'])
        urgency = enum(r.get('urgency', 'unknown'), ('reported_urgent', 'not_reported_urgent', 'unknown'))
        if 'owner' in r: text(r['owner'])
        if urgency == 'reported_urgent' and not r.get('owner'): gaps.append({'kind': 'risk_owner_missing', 'id': r['id']})
        observations.append(dict(deepcopy(r), urgency=urgency, immediate_human_escalation=urgency == 'reported_urgent',
                                 design_conformity_verified=False))
    unique(observations)
    substitution = data.get('substitution'); check = None
    if substitution is not None:
        obj(substitution, ('description', 'required_checks'), ('strength_indicator', 'anchorage_review'))
        text(substitution['description']); strings(substitution['required_checks'])
        if substitution.get('anchorage_review') is not None: text(substitution['anchorage_review'])
        indicator = None
        if substitution.get('strength_indicator') is not None:
            obj(substitution['strength_indicator'], ('original', 'proposed'))
            capacities = []
            for key in ('original', 'proposed'):
                row = substitution['strength_indicator'][key]; obj(row, ('description', 'area', 'design_strength'))
                text(row['description'])
                _, area = quantity(row['area'], ('mm2',), f'/substitution/strength_indicator/{key}/area', units, data['as_of'], positive=True)
                _, strength = quantity(row['design_strength'], ('MPa',), f'/substitution/strength_indicator/{key}/design_strength', units, data['as_of'], positive=True)
                capacities.append(area * strength / Decimal(1000))
            indicator = dict(deepcopy(substitution['strength_indicator']), original_As_Rs_kN=fmt(capacities[0]), proposed_As_Rs_kN=fmt(capacities[1]),
                             ratio=fmt(capacities[1] / capacities[0]), scope='As_times_selected_Rs_only_not_substitution_equivalence')
        check = dict(deepcopy(substitution), strength_indicator=indicator,
                     indicator_status='not_requested' if indicator is None else 'single_indicator_only', adequacy_or_equivalence_established=False)
        gaps.append({'kind': 'substitution_full_structural_checks_not_performed'})
    history = []
    for r in rows(data.get('issue_history', []), 16):
        obj(r, ('id', 'issue_id', 'date', 'event_text', 'source_reference'))
        for k in ('id', 'issue_id', 'event_text', 'source_reference'): text(r[k])
        day(r['date'], data['as_of'])
        if r['issue_id'] != request['id']: gaps.append({'kind': 'history_issue_mismatch', 'id': r['id']})
        history.append(deepcopy(r))
    unique(history)
    changes = []
    designs_by_id = {r['id']: r for r in designs}
    for r in rows(data.get('rd_changes', []), 12):
        obj(r, ('document_id', 'current_revision', 'proposed_revision', 'description'))
        for v in r.values(): text(v)
        selected = designs_by_id.get(r['document_id'])
        if selected is None: gaps.append({'kind': 'rd_change_document_missing', 'id': r['document_id']})
        elif selected['revision'] != r['current_revision']: gaps.append({'kind': 'rd_change_current_revision_mismatch', 'id': r['document_id']})
        changes.append(dict(deepcopy(r), selected_design_revision=None if selected is None else selected['revision'],
                            current_revision_matches_selected=None if selected is None else selected['revision'] == r['current_revision'], change_issued=False))
    if not designs: gaps.append({'kind': 'design_records_missing'})
    if not observations: gaps.append({'kind': 'site_observations_missing'})
    response = data.get('draft_response')
    if response is not None: text(response)
    return dict(request=dict(deepcopy(request), due=deadline(request.get('due'), data['as_of'])), selected_requirements=req,
                design_records=designs, observations=observations, substitution_review=check,
                substitution_status='not_requested' if check is None else 'proposed_substitution_requires_full_review', issue_history=history,
                decision_log=decisions(data.get('decisions', []), {request['id']}, data['as_of'], gaps), rd_changes=changes,
                required_checks=strings(data.get('required_checks', [])), draft_response=response,
                immediate_escalation_required=any(r['immediate_human_escalation'] for r in observations),
                escalation_instruction='escalate_to_responsible_person_now_do_not_wait_for_report' if any(r['immediate_human_escalation'] for r in observations) else None,
                responsible_signature_status='not_applied_tool_draft', evidence_gaps=gaps)


_DISPATCH = dict(kr_section=_kr, inspection=_inspection, expertise_review=_expertise, site_support=_site)


def _run(function, data):
    if type(function) is not str or function not in FUNCTIONS: fail('unknown_scenario_function')
    contracts = {}
    with localcontext(Context(prec=180)):
        result = _DISPATCH[function](data, contracts)
    result.update(as_of=data['as_of'], jurisdiction='RU', analysis_only=True, assisted_draft=True,
                  source_semantics_verified=False, current_legal_applicability_verified=False,
                  design_approved=False, fitness_for_use_certified=False, technical_category_assigned=False,
                  drawings_issued=False, signature_applied=False, submission_performed=False, physical_work_authorized=False)
    return result, contracts


def execute(function, data):
    return _run(function, deepcopy(data))[0]


def input_units(function, data):
    return _run(function, deepcopy(data))[1]


def selected_texts(function, data):
    """Existing observed text must occur in the cited local selected document.

    Authored proposed_work/response/decision/recommendation are drafts and do not
    become source quotations just because their basis is cited.
    """
    _run(function, data)
    output = {}
    def add(path, row, key):
        output[path + '/' + key] = row[key]
    if function == 'kr_section':
        for i, r in enumerate(data['content_items']):
            if r.get('authorship', 'selected_record') == 'selected_record': add(f'/content_items/{i}', r, 'text')
    elif function == 'inspection':
        for key in ('structures', 'defects', 'test_results'):
            for i, r in enumerate(data.get(key, [])): add(f'/{key}/{i}', r, 'description')
        for i, r in enumerate(data.get('photos', [])): add(f'/photos/{i}', r, 'caption')
    elif function == 'site_support':
        for key in ('design_records', 'observations'):
            for i, r in enumerate(data[key]): add(f'/{key}/{i}', r, 'description')
        for i, r in enumerate(data.get('issue_history', [])): add(f'/issue_history/{i}', r, 'event_text')
    for i, r in enumerate(data.get('decisions', [])):
        if r['state'] == 'recorded': add(f'/decisions/{i}', r, 'decision_text')
    return output

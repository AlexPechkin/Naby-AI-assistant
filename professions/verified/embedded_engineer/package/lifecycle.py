"""Local lifecycle drafts and supplied-record review; no scanner, device or signing engine."""
import copy
import hashlib
import json
import re
from collections import deque
from datetime import date
from decimal import Decimal, Context, localcontext
from fractions import Fraction
from .privacy import reject_known_secret_material

FUNCTIONS = ('secure_dev', 'sw_docs_rights', 'release')
_NUMBER = re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z')

def _obj(v, required=(), optional=()):
    if type(v) is not dict or set(required)-set(v) or set(v)-set(required)-set(optional):
        raise ValueError('lifecycle_object_fields')
    return v

def _text(v, empty=False, maximum=20000):
    if type(v) is not str or (not empty and not v.strip()) or len(v)>maximum:
        raise ValueError('bounded_lifecycle_text_required')
    if any(ord(c)<32 and c not in '\r\n\t' for c in v):raise ValueError('unsafe_control_in_text')
    return v

def _rows(v, maximum=1000):
    if type(v) is not list or len(v)>maximum:raise ValueError('bounded_lifecycle_list_required')
    return v

def _day(v):
    _text(v)
    try:d=date.fromisoformat(v)
    except ValueError:raise ValueError('lifecycle_date_required') from None
    if d.isoformat()!=v:raise ValueError('lifecycle_date_required')
    return v

def _scan(v, depth=0):
    if depth==0:reject_known_secret_material(v)
    if depth>30:raise ValueError('lifecycle_nesting_limit')
    if type(v) is dict:
        for k,x in v.items():
            if type(k) is not str:raise ValueError('lifecycle_string_keys_required')
            if k.endswith(('_verified','_approved','_confirmed','_checked_by_human')):raise ValueError('authority_boolean_not_accepted')
            _scan(x,depth+1)
    elif type(v) is list:
        for x in v:_scan(x,depth+1)
    elif type(v) in (int,float,bool):raise ValueError('numeric_values_require_exact_source_quantity_no_authority_booleans')

def _num(v):
    if type(v) is not str or len(v)>64 or not _NUMBER.fullmatch(v):raise ValueError('bounded_exact_decimal_required')
    d=Decimal(v)
    if not d.is_finite() or len(d.as_tuple().digits)>40 or abs(d.as_tuple().exponent)>100 or (d and abs(d.adjusted())>100):raise ValueError('bounded_exact_decimal_required')
    return d

def _q(v, unit=None, minimum=None, integer=False):
    _obj(v,('value','unit','source_reference'),('observed_date',))
    x=_num(v['value']);_text(v['unit']);_text(v['source_reference'])
    if unit is not None and v['unit']!=unit:raise ValueError('lifecycle_quantity_unit_mismatch')
    if minimum is not None and x<minimum:raise ValueError('lifecycle_quantity_below_minimum')
    if integer and x!=x.to_integral_value():raise ValueError('lifecycle_integer_quantity_required')
    if 'observed_date' in v:_day(v['observed_date'])
    return x

def _out(x):
    if isinstance(x,Fraction):
        with localcontext(Context(prec=180)):return str(Decimal(x.numerator)/Decimal(x.denominator))
    return str(x)

def _json(raw):
    def pairs(items):
        out={}
        for key,value in items:
            if key in out:raise ValueError('duplicate_selected_record_json_key')
            out[key]=value
        return out
    def constant(_):raise ValueError('nonfinite_selected_record_json')
    def bounded(v,depth=0):
        if depth>30:raise ValueError('selected_record_nesting_limit')
        if type(v) is dict:
            for x in v.values():bounded(x,depth+1)
        elif type(v) is list:
            for x in v:bounded(x,depth+1)
    try:
        out=json.loads(raw,object_pairs_hook=pairs,parse_constant=constant);reject_known_secret_material(out);bounded(out);return out
    except (ValueError,TypeError,RecursionError):raise ValueError('bounded_unambiguous_selected_json_required') from None

def _unique(rows, key='id'):
    ids=[_text(x[key]) for x in rows]
    if len(ids)!=len(set(ids)):raise ValueError('duplicate_lifecycle_id')
    return {x[key]:x for x in rows}

def _source(v):
    _obj(v,('source_reference','excerpt'),('document_identity','edition','publication_date','effective_from','effective_to','clause','selection_date','scope'))
    _text(v['source_reference']);_text(v['excerpt'])
    for k in ('publication_date','effective_from','effective_to','selection_date'):
        if v.get(k) is not None:_day(v[k])
    return copy.deepcopy(v)

def _context(v):
    _obj(v,('build_id','image_sha256','board_revision'),('software_version','test_environment','toolchain','commit','run_id'))
    for x in v.values():_text(x)
    if not re.fullmatch('[a-fA-F0-9]{64}',v['image_sha256']):raise ValueError('sha256_digest_required')
    return copy.deepcopy(v)

def _component(v):
    _obj(v,('id','name','version','source_reference'),('ecosystem','purl','commit','license_expression','sbom_extract'))
    for k,x in v.items():
        if k!='sbom_extract':_text(x)
    out=copy.deepcopy(v)
    if 'sbom_extract' in v:
        e=_obj(v['sbom_extract'],('format','record_json','source_reference'))
        formats={'SPDX-2.3','SPDX-3.0.1','CycloneDX-1.6','CycloneDX-1.7'}
        if e['format'] not in formats:raise ValueError('unsupported_selected_sbom_format')
        if e['source_reference']!=v['source_reference']:raise ValueError('component_and_selected_sbom_source_mismatch')
        _text(e['source_reference']);raw=_text(e['record_json'],maximum=60000)
        try:r=_json(raw)
        except (ValueError,TypeError):raise ValueError('selected_sbom_json_record_required') from None
        if type(r) is not dict:raise ValueError('selected_sbom_package_record_required')
        namekey,versionkey=('name','versionInfo') if e['format']=='SPDX-2.3' else ('name','software_packageVersion') if e['format']=='SPDX-3.0.1' else ('name','version')
        if e['format']=='SPDX-3.0.1' and r.get('type')!='software_Package':raise ValueError('selected_spdx3_package_type_required')
        if r.get(namekey)!=v['name'] or r.get(versionkey)!=v['version']:raise ValueError('sbom_component_identity_mismatch')
        # A selected record adapter, never a complete SPDX graph or BOM validator.
        out['sbom_extract_review']={'format':e['format'],'identity_status':'selected_record_identity_matches','schema_validation_performed':False,'license_interpretation_performed':False,'license_graph_resolution_performed':False}
    return out

def _query(v, components):
    _obj(v,('id','component_id','provider','queried_at','query_json','response_json','source_reference'),('context','query_date_source_reference'))
    for k in ('id','component_id','provider','source_reference'):_text(v[k])
    if v['queried_at'] is not None:_day(v['queried_at'])
    if 'query_date_source_reference' in v:_text(v['query_date_source_reference'])
    if 'context' in v:_context(v['context'])
    if v['component_id'] not in components:raise ValueError('unknown_vulnerability_component')
    try:q=_json(_text(v['query_json'],maximum=60000));r=_json(_text(v['response_json'],maximum=120000))
    except ValueError:raise ValueError('vulnerability_json_required') from None
    if v['provider']!='OSV-v1-query':raise ValueError('unsupported_vulnerability_record_format')
    c=components[v['component_id']]
    if type(q) is not dict or type(r) is not dict:raise ValueError('osv_query_response_objects_required')
    _obj(r,(),('vulns','next_page_token'))
    if 'next_page_token' in r:_text(r['next_page_token'],empty=True)
    if 'commit' in q:
        if set(q)!={'commit'} or not c.get('commit') or q['commit']!=c['commit']:raise ValueError('osv_commit_context_mismatch')
    else:
        if set(q)!={'package','version'} or q['version']!=c['version']:raise ValueError('osv_version_context_mismatch')
        p=q['package']
        named=bool(c.get('ecosystem')) and p=={'name':c['name'],'ecosystem':c['ecosystem']}
        located=bool(c.get('purl')) and p=={'purl':c['purl']}
        if not named and not located:raise ValueError('osv_package_context_mismatch')
        if 'purl' in p and '@' in p['purl']:raise ValueError('osv_versioned_purl_and_version_not_supported')
    vulns=_rows(r.get('vulns',[]))
    ids=[];affected_reviews=[]
    for row in vulns:
        if type(row) is not dict:raise ValueError('osv_vulnerability_record_required')
        ids.append(_text(row.get('id')))
        states=[]
        for a in _rows(row.get('affected',[])):
            if type(a) is not dict or type(a.get('package')) is not dict:raise ValueError('osv_affected_package_record_required')
            p=a['package'];matched=bool(c.get('ecosystem') and p.get('name')==c['name'] and p.get('ecosystem')==c['ecosystem']) or bool(c.get('purl') and p.get('purl')==c['purl'])
            if not matched:states.append('different_affected_package')
            versions=[_text(x) for x in _rows(a.get('versions',[]))]
            ranges=_rows(a.get('ranges',[]))
            for rg in ranges:
                _obj(rg,('type','events'),('repo',))
                if rg['type'] not in ('SEMVER','ECOSYSTEM','GIT'):raise ValueError('unsupported_osv_range_type')
                if 'repo' in rg:_text(rg['repo'])
                for event in _rows(rg['events']):
                    if type(event) is not dict or len(event)!=1 or set(event)-{'introduced','fixed','last_affected','limit'}:raise ValueError('typed_osv_range_event_required')
                    _text(next(iter(event.values())))
            if not matched:continue
            if c['version'] in versions:states.append('version_list_contains_selected_version')
            elif ranges:states.append('range_present_not_evaluated')
            else:states.append('selected_version_not_in_provided_version_list')
        affected_reviews.append({'id':row['id'],'affected_record_states':states,'status':'affected_records_require_review' if states else 'affected_package_records_not_supplied'})
    pagination=bool(r.get('next_page_token'))
    out={**copy.deepcopy(v),'reported_vulnerability_ids':ids,'reported_count':len(ids),'affected_record_reviews':affected_reviews,'pagination_status':'more_selected_pages_required' if pagination else 'provided_response_has_no_next_page_token','review_status':'reported_findings_require_triage' if ids else 'no_findings_in_supplied_response_only','scan_executed':False,'version_range_evaluation_performed':False}
    if v['queried_at'] is None:out['query_time_status']='not_supplied_no_freshness_established'
    return out

def _secure(d):
    allowed=('brief','threat_model','requirements','components','tool_reports','vulnerability_queries','security_controls','update_plan','risk_matrix')
    _obj(d,('as_of','jurisdiction','mode'),allowed)
    gaps=[]
    requirements=[_source(x) for x in _rows(d.get('requirements',[]))]
    comps=[_component(x) for x in _rows(d.get('components',[]))];index=_unique(comps)
    queries=[_query(x,index) for x in _rows(d.get('vulnerability_queries',[]))];_unique(queries)
    for c in comps:
        if not any(q['component_id']==c['id'] for q in queries):gaps.append({'kind':'component_vulnerability_evidence_not_supplied','id':c['id']})
    tools=[]
    for row in _rows(d.get('tool_reports',[])):
        _obj(row,('id','tool','tool_version','analysis_kind','context','reported_status','source_reference','excerpt'),('finding_ids',))
        _context(row['context']);_source({k:row[k] for k in ('source_reference','excerpt')})
        for k in ('id','tool','tool_version'):_text(row[k])
        if row['analysis_kind'] not in ('static_analysis','dependency_scan','configuration_review'):raise ValueError('unsupported_analysis_kind')
        if row['reported_status'] not in ('findings','no_findings','incomplete','error'):raise ValueError('typed_tool_report_status_required')
        tools.append({**copy.deepcopy(row),'interpretation':'supplied_tool_record_not_execution_or_clearance'})
    controls=[]
    for row in _rows(d.get('security_controls',[])):
        _obj(row,('id','control','proposal'),('evidence','context'))
        for k in ('id','control','proposal'):_text(row[k])
        if 'evidence' in row:_source(row['evidence'])
        if 'context' in row:_context(row['context'])
        controls.append({**copy.deepcopy(row),'evidence_state':'provided_record_requires_review' if 'evidence' in row else 'proposal_without_execution_evidence'})
    _unique(tools);_unique(controls)
    update=None
    if 'update_plan' in d:
        u=_obj(d['update_plan'],('channel','image_authentication','rollback','recovery','debug_interface','key_storage_reference'),('candidate_counter','stored_counter','counter_basis','image_context','evidence'))
        for k in ('channel','image_authentication','rollback','recovery','debug_interface','key_storage_reference'):_text(u[k])
        if 'image_context' in u:_context(u['image_context'])
        if 'evidence' in u:_source(u['evidence'])
        update=copy.deepcopy(u);update['counter_comparison']=None
        if 'candidate_counter' in u or 'stored_counter' in u:
            if not all(k in u for k in ('candidate_counter','stored_counter','counter_basis')):raise ValueError('both_counters_and_selected_basis_required')
            a=_q(u['candidate_counter'],'count',0,True);b=_q(u['stored_counter'],'count',0,True);_source(u['counter_basis'])
            update['counter_comparison']={'candidate_not_below_stored':a>=b,'difference':_out(Fraction(a)-Fraction(b)),'interpretation':'numeric_counter_comparison_not_hardware_rollback_protection'}
    matrix=None
    if 'risk_matrix' in d:
        m=_obj(d['risk_matrix'],('basis','cells','risks'));_source(m['basis']);cells={}
        for c in _rows(m['cells']):
            _obj(c,('likelihood','impact','category'));pair=(_text(c['likelihood']),_text(c['impact']))
            if pair in cells:raise ValueError('duplicate_ordinal_risk_cell')
            cells[pair]=_text(c['category'])
        reviews=[]
        for r in _rows(m['risks']):
            _obj(r,('id','description','likelihood','impact'),('owner','response'))
            key=(r['likelihood'],r['impact']);category=cells.get(key)
            reviews.append({**copy.deepcopy(r),'selected_category':category,'status':'selected_ordinal_cell' if category is not None else 'selected_cell_missing'})
        _unique(reviews)
        matrix={'basis':copy.deepcopy(m['basis']),'risks':reviews,'interpretation':'ordinal_categories_not_probability_or_expected_loss'}
    if not d.get('threat_model'):gaps.append({'kind':'threat_model_not_supplied'})
    return {'mode':d['mode'],'threat_model':copy.deepcopy(d.get('threat_model')),'requirements':requirements,'components':comps,'tool_reports':tools,'vulnerability_queries':queries,'security_controls':controls,'update_plan':update,'risk_matrix':matrix,'evidence_gaps':gaps,'questions':['supply_threat_model_and_update_context','select_dated_requirements_and_component_evidence'] if d['mode']=='questions' else [],'decision_scope':'draft_security_review_no_certification_or_vulnerability_clearance'}

def _docs(d):
    _obj(d,('as_of','jurisdiction','mode'),('brief','recipient','document_basis','program_sections','source_files','license_records','rights','registration'))
    basis=[_source(x) for x in _rows(d.get('document_basis',[]))];files=[]
    for row in _rows(d.get('source_files',[]),200):
        _obj(row,('id','path_label','content','provided_utf8_content_sha256','source_reference'),('version','version_source_reference','original_bytes_sha256','encoding_note'))
        _text(row['id']);_text(row['path_label']);content=_text(row['content'],empty=True,maximum=500000);_text(row['source_reference'])
        digest=hashlib.sha256(content.encode('utf8')).hexdigest()
        supplied=_text(row['provided_utf8_content_sha256'])
        if not re.fullmatch('[a-fA-F0-9]{64}',supplied)or supplied.lower()!=digest:raise ValueError('provided_utf8_content_hash_mismatch')
        if 'version'in row:_text(row['version'])
        if 'version_source_reference'in row:
            _text(row['version_source_reference'])
            if 'version'not in row:raise ValueError('version_required_for_selected_version_source')
        if row.get('original_bytes_sha256') is not None and not re.fullmatch('[a-fA-F0-9]{64}',row['original_bytes_sha256']):raise ValueError('sha256_digest_required')
        files.append({**copy.deepcopy(row),'utf8_content_bytes':len(content.encode('utf8')),'hash_scope':'provided_logical_content_encoded_utf8_not_original_file_bytes','source_compiled':False})
    _unique(files)
    licenses=[]
    for row in _rows(d.get('license_records',[])):
        _obj(row,('id','component','version','license_expression','basis'),('distribution_context','selected_obligations','unresolved_questions'))
        for k in ('id','component','version','license_expression'):_text(row[k])
        _source(row['basis'])
        licenses.append({**copy.deepcopy(row),'interpretation':'selected_license_statement_not_legal_compatibility_conclusion'})
    _unique(licenses)
    rights=None
    if 'rights' in d:
        r=_obj(d['rights'],('right_holder','authors'),('employment_basis','assignment_basis','contract_notes','unresolved_questions'))
        _text(r['right_holder']);[_text(a) for a in _rows(r['authors'],100)]
        for k in ('employment_basis','assignment_basis'):
            if k in r:_source(r[k])
        rights={**copy.deepcopy(r),'interpretation':'provided_rights_claims_not_ownership_determination'}
    registration=None
    if 'registration' in d:
        r=_obj(d['registration'],('program_name','abstract','deposited_material_ids'),('basis','application_notes'))
        _text(r['program_name']);_text(r['abstract']);ids=[_text(x) for x in _rows(r['deposited_material_ids'])]
        if len(set(ids))!=len(ids) or any(x not in {f['id'] for f in files} for x in ids):raise ValueError('unknown_or_duplicate_deposited_material')
        if 'basis' in r:_source(r['basis'])
        registration={**copy.deepcopy(r),'status':'private_registration_draft_not_submitted'}
    sections=d.get('program_sections',{})
    _obj(sections,(),('general','purpose','structure','technical_means','inputs_outputs','characteristics','invocation','messages'))
    for value in sections.values():_text(value)
    return {'mode':d['mode'],'recipient':d.get('recipient'),'document_basis':basis,'program_sections':copy.deepcopy(sections),'source_files':files,'license_records':licenses,'rights':rights,'registration':registration,'evidence_gaps':[{'kind':'rights_basis_not_supplied'}] if rights is None else [],'questions':['select_recipient_document_standard_and_requested_materials','supply_selected_rights_and_license_context_without_secrets'] if d['mode']=='questions' else [],'decision_scope':'private_document_drafts_no_legal_conclusion_or_registration'}

def _schedule(v):
    _obj(v,('tasks',));tasks=_rows(v['tasks']);index=_unique(tasks);following={x:[] for x in index};indegree={x:0 for x in index};dur={};deps={}
    for row in tasks:
        _obj(row,('id','duration','depends_on'),('description',));dur[row['id']]=Fraction(_q(row['duration'],'day',0));ds=[_text(x) for x in _rows(row['depends_on'],1000)]
        if len(set(ds))!=len(ds) or any(x not in index for x in ds):raise ValueError('invalid_schedule_dependency')
        deps[row['id']]=ds;indegree[row['id']]=len(ds)
        for x in ds:following[x].append(row['id'])
    queue=deque(x for x in index if not indegree[x]);order=[];es={};ef={}
    while queue:
        x=queue.popleft();order.append(x);es[x]=max((ef[p] for p in deps[x]),default=Fraction(0));ef[x]=es[x]+dur[x]
        for y in following[x]:
            indegree[y]-=1
            if not indegree[y]:queue.append(y)
    if len(order)!=len(index):raise ValueError('schedule_cycle')
    total=max(ef.values(),default=Fraction(0));ls={};lf={}
    for x in reversed(order):lf[x]=min((ls[y] for y in following[x]),default=total);ls[x]=lf[x]-dur[x]
    return {'tasks':[{**copy.deepcopy(index[x]),'earliest_start':_out(es[x]),'earliest_finish':_out(ef[x]),'latest_start':_out(ls[x]),'latest_finish':_out(lf[x]),'slack':_out(ls[x]-es[x]),'critical_in_supplied_DAG':ls[x]==es[x]} for x in order],'total_duration_days':_out(total) if tasks else None,'schedule_status':'supplied_DAG_calculated' if tasks else 'empty_task_graph_no_duration_estimated','calendar_dates_computed':False,'resource_constraints_modelled':False,'interpretation':'unconstrained_supplied_dependency_schedule_not_release_authorization'}

def _release(d):
    _obj(d,('as_of','jurisdiction','mode'),('brief','notes','images','builds','expected_tests','executions','schedule'))
    notes=d.get('notes')
    if notes is not None:
        _obj(notes,('version','date','changes','fixes','compatibility','limitations','update','rollback'),('branch','tag'))
        _day(notes['date'])
        for k,x in notes.items():
            if k in ('changes','fixes','limitations'):[_text(y) for y in _rows(x)]
            else:_text(x)
    images=[]
    for x in _rows(d.get('images',[])):
        _obj(x,('id','name','sha256','bytes','source_reference'),('build_id','board_revision'))
        for k in ('id','name','source_reference'):_text(x[k])
        if not re.fullmatch('[a-fA-F0-9]{64}',x['sha256']):raise ValueError('sha256_digest_required')
        _q(x['bytes'],'byte',0,True)
        images.append({**copy.deepcopy(x),'hash_status':'provided_digest_not_binary_rehashed','signature_status':'not_checked'})
    image_index=_unique(images);builds=[]
    for x in _rows(d.get('builds',[])):
        _obj(x,('id','software_version','board_revision','image_id','source_reference'),('toolchain','commit','excerpt'))
        if x['image_id'] not in image_index:raise ValueError('unknown_build_image')
        for k,y in x.items():_text(y)
        image=image_index[x['image_id']]
        if image.get('build_id',x['id'])!=x['id'] or image.get('board_revision',x['board_revision'])!=x['board_revision']:raise ValueError('image_build_context_mismatch')
        builds.append(copy.deepcopy(x))
    build_index=_unique(builds);expected=_rows(d.get('expected_tests',[]));_unique(expected)
    for x in expected:
        _obj(x,('id','test_revision','requirement_ids','build_id','source_reference'),('procedure_excerpt',))
        if x['build_id'] not in build_index:raise ValueError('unknown_expected_test_build')
        for k in ('id','test_revision','source_reference'):_text(x[k])
        [_text(y) for y in _rows(x['requirement_ids'])]
    executions=[]
    for x in _rows(d.get('executions',[])):
        _obj(x,('id','test_id','test_revision','context','status','source_reference','excerpt'))
        _context(x['context']);_source({k:x[k] for k in ('source_reference','excerpt')})
        for k in ('id','test_id','test_revision'):_text(x[k])
        if x['status'] not in ('passed','failed','blocked','not_run','build_only'):raise ValueError('typed_execution_status_required')
        executions.append(copy.deepcopy(x))
    _unique(executions);reviews=[]
    for e in expected:
        b=build_index[e['build_id']];image=image_index[b['image_id']];rows=[x for x in executions if x['test_id']==e['id']];matching=[];rejected=[];constraint_checks=[]
        constraints={'test_revision':e['test_revision'],'build_id':b['id'],'image_sha256':image['sha256'].lower(),'board_revision':b['board_revision'],'software_version':b['software_version']}
        for optional in ('toolchain','commit'):
            if optional in b:constraints[optional]=b[optional]
        for x in rows:
            c=x['context'];actual=dict(c,test_revision=x['test_revision']);actual['image_sha256']=actual['image_sha256'].lower()
            mismatch=[k for k,value in constraints.items() if actual.get(k)!=value]
            constraint_checks.append({'execution_id':x['id'],'compared_fields':list(constraints),'missing_fields':[k for k in constraints if k not in actual],'mismatched_fields':mismatch,'fields_without_selected_expected_constraint':[k for k in c if k not in constraints]})
            if mismatch:rejected.append({'execution_id':x['id'],'mismatched_fields':mismatch})
            else:matching.append(x)
        statuses=[x['status'] for x in matching]
        status='no_matching_execution' if not matching else 'conflicting_supplied_statuses' if len(set(statuses))>1 else 'reported_'+statuses[0]+'_matching_context'
        reviews.append({'test_id':e['id'],'test_revision':e['test_revision'],'requirement_ids':copy.deepcopy(e['requirement_ids']),'build_id':b['id'],'expected_context_constraints':constraints,'constraint_checks':constraint_checks,'matching_execution_ids':[x['id'] for x in matching],'context_mismatches':rejected,'status':status})
    unknown=[x['id'] for x in executions if x['test_id'] not in {r['id'] for r in expected}]
    gaps=[]
    for row in reviews:
        if row['status']!='reported_passed_matching_context':gaps.append({'kind':'test_not_reported_passed_in_matching_context','id':row['test_id']})
    if unknown:gaps.append({'kind':'executions_without_selected_expected_test','ids':unknown})
    return {'mode':d['mode'],'notes':copy.deepcopy(notes),'images':images,'builds':builds,'expected_tests':copy.deepcopy(expected),'executions':executions,'test_reviews':reviews,'test_ledger_status':'not_requested' if 'expected_tests' not in d and 'executions' not in d else 'no_expected_tests_supplied' if not expected else 'supplied_records_compared_only','unmatched_execution_ids':unknown,'schedule':_schedule(d['schedule']) if 'schedule' in d else None,'evidence_gaps':gaps,'questions':['select_requested_notes_test_ledger_or_schedule','supply_exact_build_image_board_and_test_identity'] if d['mode']=='questions' else [],'decision_scope':'private_release_draft_no_signing_publication_or_field_update'}

def execute(function_id,data):
    if function_id not in FUNCTIONS:raise ValueError('unknown_lifecycle_function')
    _scan(data);_obj(data,('as_of','jurisdiction','mode'),tuple(set(data)-{'as_of','jurisdiction','mode'}));_day(data['as_of'])
    if data['jurisdiction']!='RU' or data['mode'] not in ('questions','review' if function_id=='secure_dev' else 'draft'):raise ValueError('lifecycle_mode_or_jurisdiction')
    def dates(v):
        if type(v) is dict:
            for k,x in v.items():
                if k in ('observed_date','queried_at','publication_date','selection_date') and x is not None:
                    if _day(x)>data['as_of']:raise ValueError('record_after_information_cutoff')
                else:dates(x)
        elif type(v) is list:
            for x in v:dates(x)
    dates(data)
    result={'secure_dev':_secure,'sw_docs_rights':_docs,'release':_release}[function_id](copy.deepcopy(data))
    result.update(as_of=data['as_of'],jurisdiction='RU',assisted_draft=True,analysis_only=True)
    return result

def input_units(function_id,data):
    execute(function_id,data);result={}
    def walk(v,path=''):
        if type(v) is dict:
            if {'value','unit','source_reference'}<=set(v):
                spec={'unit':v['unit'],'effective_not_after':data['as_of'],'published_not_after':data['as_of'],'source_references':[v['source_reference']]}
                if 'observed_date' in v:spec['effective_date']=v['observed_date']
                result[path+'/value']=spec
            else:
                for k,x in v.items():walk(x,path+'/'+k.replace('~','~0').replace('/','~1'))
        elif type(v) is list:
            for i,x in enumerate(v):walk(x,path+'/'+str(i))
    walk(data);return result

def selected_texts(function_id,data):
    execute(function_id,data);result={}
    literal={'excerpt','record_json','query_json','response_json','content','procedure_excerpt'}
    identity={'name','version','ecosystem','purl','commit','license_expression','software_version','tool','tool_version','toolchain','build_id','test_id','test_revision','sha256','image_sha256','board_revision','provided_utf8_content_sha256','original_bytes_sha256'}
    def walk(v,path='',refs=None):
        if type(v) is dict:
            local=[v['source_reference']] if type(v.get('source_reference')) is str else refs
            if type(v.get('basis')) is dict:local=[v['basis']['source_reference']]
            source_file=function_id=='sw_docs_rights' and re.fullmatch(r'/source_files/\d+',path)is not None
            for k,x in v.items():
                p=path+'/'+k.replace('~','~0').replace('/','~1')
                if source_file and k in ('provided_utf8_content_sha256','original_bytes_sha256'):continue
                if source_file and k=='version':
                    if 'version_source_reference'in v:result[p]={'text':x,'source_references':[v['version_source_reference']]}
                    continue
                if source_file and k=='content' and x=='':result[p]={'text':'','source_references':[v['source_reference']],'empty_file':True}
                elif k=='queried_at' and type(x)is str:result[p]={'text':x,'source_references':[v.get('query_date_source_reference',v['source_reference'])]}
                elif k=='observed_date' and type(x)is str and {'value','unit','source_reference'}<=set(v):result[p]={'text':x,'source_references':[v['source_reference']]}
                elif type(x) is str and x and (k in literal or k in identity and local):result[p]={'text':x,'source_references':local} if local else x
                else:walk(x,p,local)
        elif type(v) is list:
            for i,x in enumerate(v):walk(x,path+'/'+str(i),refs)
    walk(data);return result

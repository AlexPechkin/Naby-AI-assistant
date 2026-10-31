"""Pure selected-source climate drafts. No downloads, approval or policy defaults.

Ordinal cells classify selected categories; they are not physical probabilities,
expected monetary losses or a universal IPCC/national-plan formula.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation
import re

FUNCTIONS=('climate_risk_adaptation','design_climate','climate_publication')
DECIMAL=re.compile(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$')
COMMON={'as_of','jurisdiction','mode'}
def fail(code):raise ValueError(code)
def obj(v,required=(),optional=(),name='object'):
    if type(v) is not dict or set(required)-set(v) or set(v)-set(required)-set(optional):fail('invalid_'+name+'_fields')
    return v
def text(v,name='text',maximum=6000):
    if type(v) is not str or not v.strip() or len(v)>maximum or any(ord(c)<32 and c not in '\n\t\r' for c in v):fail('invalid_'+name)
    return v
def optional_text(v):return None if v is None else text(v)
def rows(v,name='rows',maximum=60):
    if type(v) is not list or len(v)>maximum:fail('bounded_'+name+'_required')
    return v
def day(v,name='date'):
    text(v,name,10)
    try:d=date.fromisoformat(v)
    except ValueError:fail('invalid_'+name)
    if d.isoformat()!=v:fail('invalid_'+name)
    return v
def enum(v,allowed,name):
    if v not in allowed or type(v) is not str:fail('invalid_'+name)
    return v
def unique(items,name='id'):
    seen=set()
    for item in items:
        if type(item) is not dict or name not in item:fail('object_'+name+'_required')
        identity=text(item[name],name,160)
        if identity in seen:fail('duplicate_'+name)
        seen.add(identity)
    return seen
def number(v):
    if type(v) is not str or len(v)>160 or not DECIMAL.fullmatch(v):fail('bounded_decimal_string_required')
    try:n=Decimal(v)
    except InvalidOperation:fail('bounded_decimal_string_required')
    if not n.is_finite() or len(n.as_tuple().digits)>40 or abs(n.as_tuple().exponent)>140 or (n and abs(n.adjusted())>100):fail('bounded_decimal_string_required')
    return n
def quantity(v,asof):
    obj(v,('value','unit','source_reference'),('observed_at','description'),'quantity')
    number(v['value']);text(v['unit'],'unit',100);text(v['source_reference'],'source_reference',160)
    if 'observed_at' in v:
        if day(v['observed_at'])>asof:fail('observation_after_information_cutoff')
    if 'description' in v:text(v['description'])
    return deepcopy(v)
def note(v):
    obj(v,('text','source_reference'),(), 'selected_note');text(v['text']);text(v['source_reference'],'source_reference',160)
    return deepcopy(v)
def common(data,function,extra_required,extra_optional):
    obj(data,COMMON|set(extra_required),extra_optional,function)
    if data['jurisdiction']!='RU':fail('explicit_RU_jurisdiction_required')
    day(data['as_of'],'as_of')
    return data['as_of']
def selected_documents(values,asof):
    result=[];gaps=[]
    for i,item in enumerate(rows(values,'selected_documents',20)):
        obj(item,('id','document_identity','edition','publication_date','effective_from','effective_to','clause','excerpt','source_reference'),('selected_applicability_date',),'selected_document')
        for key in ('id','document_identity','edition','clause','excerpt','source_reference'):text(item[key],key)
        published=day(item['publication_date'])
        if published>asof:fail('selected_document_published_after_information_cutoff')
        start=None if item['effective_from'] is None else day(item['effective_from'])
        end=None if item['effective_to'] is None else day(item['effective_to'])
        if start and end and end<start:fail('selected_document_date_order')
        app=item.get('selected_applicability_date')
        if app is not None:day(app)
        status='applicability_date_not_supplied'
        if app is None:gaps.append('selected_applicability_date_missing:'+item['id'])
        elif start is None:status='effective_start_unknown';gaps.append('effective_start_unknown:'+item['id'])
        elif app<start or (end is not None and app>end):status='outside_selected_metadata_window';gaps.append('outside_selected_metadata_window:'+item['id'])
        else:status='within_selected_metadata_window_only'
        if end is None:gaps.append('effective_end_unknown:'+item['id'])
        result.append(dict(deepcopy(item),selected_metadata_window_status=status,legal_applicability_established=False))
    unique(result)
    return result,gaps

def _matrix(value):
    obj(value,('id','kind','likelihood_categories','consequence_categories','cells','excerpt','source_reference'),(),'matrix')
    enum(value['kind'],('ordinal_lookup',),'matrix_kind')
    for key in ('id','excerpt','source_reference'):text(value[key])
    categories={}
    for axis in ('likelihood','consequence'):
        parsed=[]
        for row in rows(value[axis+'_categories'],axis+'_categories',12):
            obj(row,('id','label','definition','source_reference'),(),'category')
            for key in row:text(row[key])
            parsed.append(deepcopy(row))
        if not parsed:fail('nonempty_matrix_categories_required')
        categories[axis]=unique(parsed)
    pairs=set()
    for cell in rows(value['cells'],'matrix_cells',144):
        obj(cell,('likelihood_id','consequence_id','priority','label'),(),'matrix_cell')
        for key in cell:text(cell[key])
        pair=(cell['likelihood_id'],cell['consequence_id'])
        if pair in pairs:fail('duplicate_matrix_cell')
        if pair[0] not in categories['likelihood'] or pair[1] not in categories['consequence']:fail('unknown_matrix_category')
        pairs.add(pair)
    return deepcopy(value)

def _risk(data):
    asof=common(data,'climate_risk_adaptation',('object','horizon'),('hazards','measures','matrix','selected_documents','context'))
    mode=enum(data['mode'],('questions','assessment'),'risk_mode')
    for key in ('object','horizon'):text(data[key])
    if data.get('context') is not None:note(data['context'])
    documents,gaps=selected_documents(data.get('selected_documents',[]),asof)
    hazards=[];measures=[]
    matrix=None if data.get('matrix') is None else _matrix(data['matrix'])
    inputs=rows(data.get('hazards',[]),'hazards',50);ids=unique(inputs)
    if mode=='questions':
        if inputs or data.get('measures') or matrix is not None:fail('questions_mode_has_assessment_data')
        gaps.extend(('hazard_evidence_missing','exposure_vulnerability_missing','selected_risk_method_missing'))
    elif not inputs:fail('assessment_hazards_required')
    for item in inputs:
        obj(item,('id','hazard','asset','evaluation_basis'),('evidence','exposure','vulnerability','likelihood_category','consequence_category','metrics','scenario_context'),'hazard')
        for key in ('id','hazard','asset'):text(item[key])
        enum(item['evaluation_basis'],('selected_evidence','expert_judgement'),'evaluation_basis')
        for key in ('likelihood_category','consequence_category'):
            if item.get(key) is not None:text(item[key])
        row=deepcopy(item)
        for key in ('evidence','exposure','vulnerability','scenario_context'):
            if item.get(key) is not None:note(item[key])
            else:gaps.append(key+'_missing:'+item['id'])
        row['metrics']=[quantity(q,asof) for q in rows(item.get('metrics',[]),'metrics',10)]
        priority=None;label=None;status='selected_matrix_not_supplied'
        if matrix is not None:
            likelihood=item.get('likelihood_category');consequence=item.get('consequence_category')
            for key in ('likelihood_category','consequence_category'):
                if item.get(key) is not None:text(item[key])
            if likelihood is None or consequence is None:status='risk_categories_missing'
            elif likelihood not in {v['id'] for v in matrix['likelihood_categories']} or consequence not in {v['id'] for v in matrix['consequence_categories']}:
                status='risk_category_not_in_selected_matrix'
            else:
                matched=[c for c in matrix['cells'] if c['likelihood_id']==likelihood and c['consequence_id']==consequence]
                if matched:priority=matched[0]['priority'];label=matched[0]['label'];status='selected_ordinal_cell_matched'
                else:status='selected_matrix_cell_missing'
        if status!='selected_ordinal_cell_matched':gaps.append(status+':'+item['id'])
        if item['evaluation_basis']=='expert_judgement':gaps.append('expert_judgement_not_measurement:'+item['id'])
        row.update(priority=priority,priority_label=label,classification_status=status,physical_expected_loss=None)
        hazards.append(row)
    for item in rows(data.get('measures',[]),'measures',60):
        obj(item,('id','hazard_ids','action'),('responsible','deadline','indicator','funding','monitoring','source_reference','tradeoffs'),'adaptation_measure')
        for key in ('id','action'):text(item[key])
        linked=rows(item['hazard_ids'],'hazard_ids',50)
        for identity in linked:text(identity)
        if not linked or len(set(linked))!=len(linked) or any(v not in ids for v in linked):fail('unknown_or_duplicate_measure_hazard')
        row=deepcopy(item)
        for key in ('responsible','deadline','indicator','funding','monitoring'):
            if item.get(key) is None:gaps.append('measure_'+key+'_missing:'+item['id']);row[key]=None
        if item.get('responsible') is not None:text(item['responsible'])
        if item.get('deadline') is not None:day(item['deadline'])
        if item.get('source_reference') is not None:text(item['source_reference'])
        if item.get('tradeoffs') is not None:text(item['tradeoffs'])
        if item.get('indicator') is not None:
            obj(item['indicator'],('description',),('target','baseline'),'indicator');text(item['indicator']['description'])
            for key in ('target','baseline'):
                if item['indicator'].get(key) is not None:quantity(item['indicator'][key],asof)
        if item.get('funding') is not None:
            obj(item['funding'],('status','description'),('amount',),'funding')
            enum(item['funding']['status'],('not_estimated','selected_estimate','identified_source'),'funding_status');text(item['funding']['description'])
            if item['funding'].get('amount') is not None:
                quantity(item['funding']['amount'],asof)
                if number(item['funding']['amount']['value'])<0:fail('negative_funding_amount')
            if item['funding']['status']=='not_estimated' and item['funding'].get('amount') is not None:fail('unestimated_funding_has_amount')
        if item.get('monitoring') is not None:
            obj(item['monitoring'],('procedure','frequency'),('responsible',),'monitoring')
            for v in item['monitoring'].values():text(v)
        measures.append(row)
    unique(measures)
    linked={hid for m in measures for hid in m['hazard_ids']}
    for hid in ids-linked:gaps.append('adaptation_measure_missing:'+hid)
    return dict(mode=mode,object=data['object'],horizon=data['horizon'],context=deepcopy(data.get('context')),hazards=hazards,
        selected_matrix=matrix,measures=measures,selected_documents=documents,evidence_gaps=sorted(set(gaps)),
        risk_interpretation='ordinal_lookup_not_probability_or_expected_loss',effectiveness_established=False,
        questions=['provide_hazard_exposure_vulnerability','select_explicit_risk_method','identify_measure_owner_dates_indicators_funding_monitoring'] if mode=='questions' else [])

def _design(data):
    asof=common(data,'design_climate',('location','object_type'),('station','selected_documents','parameters','supplementary_context','limitations'))
    mode=enum(data['mode'],('questions','selected_parameters'),'design_mode')
    text(data['location']);text(data['object_type'])
    docs,gaps=selected_documents(data.get('selected_documents',[]),asof);byid={v['id']:v for v in docs}
    station=None if data.get('station') is None else deepcopy(data['station'])
    if station is not None:
        obj(station,('id','name','selection_basis','source_reference'),('representativeness','period_start','period_end'),'station')
        for key in ('id','name','source_reference'):text(station[key])
        enum(station['selection_basis'],('same_location','selected_representative'),'station_selection_basis')
        if station.get('representativeness') is not None:note(station['representativeness'])
        else:gaps.append('station_representativeness_not_supplied')
        if ('period_start' in station)!=('period_end' in station):fail('station_period_pair_required')
        if 'period_start' in station:
            if day(station['period_end'])<day(station['period_start']):fail('station_period_order')
    else:gaps.append('station_not_supplied')
    parameters=[]
    for item in rows(data.get('parameters',[]),'parameters',60):
        obj(item,('id','name','quantity','document_id','table','row','column','statistic'),('period_start','period_end','selected_probability','use_limitation'),'design_parameter')
        for key in ('id','name','document_id','table','row','column','statistic'):text(item[key])
        if item['document_id'] not in byid:fail('unknown_parameter_document')
        quantity(item['quantity'],asof)
        document_source=byid[item['document_id']]['source_reference']
        if item['quantity']['source_reference']!=document_source:fail('normative_parameter_document_source_mismatch')
        if ('period_start' in item)!=('period_end' in item):fail('parameter_period_pair_required')
        if 'period_start' in item and day(item['period_end'])<day(item['period_start']):fail('parameter_period_order')
        if item.get('selected_probability') is not None:
            q=quantity(item['selected_probability'],asof)
            if q['source_reference']!=document_source:fail('normative_probability_document_source_mismatch')
            if q['unit']!='ratio' or not Decimal('0')<=number(q['value'])<=Decimal('1'):fail('selected_probability_ratio_required')
        if item.get('use_limitation') is not None:text(item['use_limitation'])
        parameters.append(dict(deepcopy(item),selection_status='selected_table_value_not_semantically_certified'))
    unique(parameters)
    if mode=='questions' and (parameters or station is not None):fail('questions_mode_has_design_values')
    if mode=='selected_parameters' and not parameters:fail('selected_design_parameters_required')
    if mode=='questions':gaps.extend(('selected_tabular_parameters_missing','selected_document_edition_missing'))
    supplements=[]
    for item in rows(data.get('supplementary_context',[]),'supplementary_context',20):
        obj(item,('kind','text','source_reference'),('quantities',),'supplementary_context')
        enum(item['kind'],('observation','reanalysis','projection'),'supplementary_kind');text(item['text']);text(item['source_reference'])
        for q in rows(item.get('quantities',[]),'quantities',10):quantity(q,asof)
        supplements.append(deepcopy(item))
    limitations=[text(v) for v in rows(data.get('limitations',[]),'limitations',20)]
    return dict(mode=mode,location=data['location'],object_type=data['object_type'],station=station,parameters=parameters,
        selected_documents=docs,supplementary_context=supplements,limitations=limitations,evidence_gaps=sorted(set(gaps)),
        parameter_scope='selected_normative_table_values_only_no_automatic_station_substitution',
        normative_applicability_established=False,representativeness_established=False,load_conversion_performed=False,
        questions=['select_object_location_and_representative_station','supply_selected_edition_table_row_column_and_units'] if mode=='questions' else [])

SECTIONS=('main','temperature','precipitation','extremes','comparison','confidence')
def _publication(data):
    asof=common(data,'climate_publication',('audience','purpose'),('sections','statements','references','limitations'))
    mode=enum(data['mode'],('questions','draft'),'publication_mode')
    text(data['audience']);text(data['purpose'])
    references=[]
    for item in rows(data.get('references',[]),'references',50):
        obj(item,('id','citation','publication_date','source_reference'),('url','edition','excerpt'),'publication_reference')
        for key in ('id','citation','source_reference'):text(item[key])
        if day(item['publication_date'])>asof:fail('reference_published_after_information_cutoff')
        if item.get('url') is not None:
            text(item['url'],'url',2000)
            if not item['url'].startswith(('https://','http://')):fail('reference_http_url_required')
        for key in ('edition','excerpt'):
            if item.get(key) is not None:text(item[key])
        references.append(deepcopy(item))
    refids=unique(references);gaps=[];statements=[]
    inputs=rows(data.get('statements',[]),'statements',60);statementids=unique(inputs)
    for item in inputs:
        obj(item,('id','kind','topic','statement','reference_ids','source_references'),('quantities','uncertainty','confidence_basis','scenario_context','derived_from_ids'),'publication_statement')
        for key in ('id','statement'):text(item[key])
        enum(item['kind'],('fact','inference','projection'),'statement_kind')
        enum(item['topic'],SECTIONS,'statement_topic')
        selected=rows(item['reference_ids'],'reference_ids',20)
        for identity in selected:text(identity)
        if len(set(selected))!=len(selected) or any(r not in refids for r in selected):fail('unknown_or_duplicate_publication_reference')
        source_ids=rows(item['source_references'],'source_references',20)
        for identity in source_ids:text(identity)
        expected_sources={v['source_reference'] for v in references if v['id'] in selected}
        if len(set(source_ids))!=len(source_ids) or set(source_ids)!=expected_sources:fail('publication_source_reference_mapping_mismatch')
        if item['kind']=='fact' and not source_ids:fail('selected_fact_source_required')
        if not selected:gaps.append('statement_source_missing:'+item['id'])
        for q in rows(item.get('quantities',[]),'quantities',10):
            quantity(q,asof)
            if q['source_reference'] not in expected_sources:fail('quantity_source_not_in_statement_references')
        for key in ('uncertainty','confidence_basis'):
            if item.get(key) is not None:text(item[key])
            else:gaps.append(key+'_missing:'+item['id'])
        parents=rows(item.get('derived_from_ids',[]),'derived_from_ids',20)
        for identity in parents:text(identity)
        if len(set(parents))!=len(parents) or any(p not in statementids or p==item['id'] for p in parents):fail('unknown_or_self_statement_dependency')
        if item.get('scenario_context') is not None:
            obj(item['scenario_context'],('scenario','models','horizon_start','horizon_end'),(),'scenario_context')
            text(item['scenario_context']['scenario'])
            models=rows(item['scenario_context']['models'],'models',30)
            for model in models:text(model)
            if not models:fail('projection_models_required')
            if day(item['scenario_context']['horizon_end'])<day(item['scenario_context']['horizon_start']):fail('projection_horizon_order')
        elif item['kind']=='projection':gaps.append('projection_scenario_context_missing:'+item['id'])
        statements.append(dict(deepcopy(item),source_interpretation_status='selected_sources_only_not_independent_verification'))
    # A dependency cycle cannot serve as evidence for its own inference.
    parents={v['id']:v.get('derived_from_ids',[]) for v in inputs}
    def visit(identity,stack,done):
        if identity in stack:fail('cyclic_statement_dependencies')
        if identity in done:return
        for parent in parents[identity]:visit(parent,stack|{identity},done)
        done.add(identity)
    done=set()
    for identity in parents:visit(identity,set(),done)
    sections=obj(data.get('sections',{}),(),SECTIONS,'publication_sections')
    for value in sections.values():text(value)
    if mode=='questions' and (inputs or sections):fail('questions_mode_has_publication_draft')
    if mode=='draft' and not sections and not inputs:fail('publication_draft_content_required')
    if not references:gaps.append('publication_sources_missing')
    if not inputs:gaps.append('typed_evidence_statements_missing')
    for section in SECTIONS:
        if section in sections and not any(v['topic']==section for v in statements):gaps.append('section_evidence_links_missing:'+section)
    return dict(mode=mode,audience=data['audience'],purpose=data['purpose'],draft_sections=deepcopy(sections),statements=statements,
        references=references,limitations=[text(v) for v in rows(data.get('limitations',[]),'limitations',20)],evidence_gaps=sorted(set(gaps)),
        authorship='proposed_not_approved',fact_inference_projection_distinction_preserved=True,
        publication_cleared=False,independent_reference_verification_performed=False,
        questions=['select_actual_sources_and_classify_fact_inference_projection','specify_audience_and_uncertainty_basis'] if mode=='questions' else [])

def execute(function,data):
    if function not in FUNCTIONS:fail('unknown_climate_scenario')
    result={'climate_risk_adaptation':_risk,'design_climate':_design,'climate_publication':_publication}[function](deepcopy(data))
    return dict(result,as_of=data['as_of'],jurisdiction='RU',assisted_draft=True,analysis_only=True,
        source_semantics_verified=False,current_legal_applicability_verified=False,external_actions=False,
        report_certified=False,methodology_approved=False,signature_applied=False,submission_performed=False,
        physical_work_authorized=False)

def _walk(value,path=''):
    if type(value) is dict:
        yield path,value
        for key,item in value.items():
            yield from _walk(item,path+'/'+key.replace('~','~0').replace('/','~1'))
    elif type(value) is list:
        for i,item in enumerate(value):yield from _walk(item,path+'/'+str(i))

def input_units(function,data):
    execute(function,data)
    result={}
    for path,value in _walk(data):
        if {'value','unit','source_reference'}<=set(value):
            spec={'unit':value['unit'],'effective_not_after':data['as_of'],'published_not_after':data['as_of'],
                  'source_references':[value['source_reference']]}
            if 'observed_at' in value:spec['effective_date']=value['observed_at']
            result[path+'/value']=spec
    if len(result)>1000:fail('numeric_contract_limit')
    return result

def selected_texts(function,data):
    execute(function,data)
    result={}
    for path,value in _walk(data):
        if {'text','source_reference'}<=set(value):result[path+'/text']=value['text']
        if {'definition','source_reference'}<=set(value):result[path+'/definition']=value['definition']
        if 'statement' in value and value.get('kind')=='fact':result[path+'/statement']=value['statement']
    return result


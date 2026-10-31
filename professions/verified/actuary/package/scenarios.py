"""Pure local actuarial data review and explicitly bounded valuation ledgers.

The host service owns engagement confirmation. No approval, practice right,
signature, filing, policy adoption or current-law certification is performed here.
"""
import copy
import json
import re
from collections import Counter
from datetime import date,timedelta
from decimal import Decimal,Context,localcontext,DecimalException
from functools import wraps

FUNCTIONS=('data_assumptions','actuarial_task','mandatory_assessment','ifrs17','solvency_stress','actuary_status')
SOURCE_KEYS={'source_reference','edition','publication_date','effective_date','scope','text'}
STATES={'provided','missing','unknown','not_applicable'}
CLAUSE_TOPICS=('client','executor','purpose','object','valuation_date','data_scope','data_responsibility','limitations','result_usage','delivery_date')
RECORD_TEXT_FIELDS={'record_id','contract_id','claim_id','currency','perimeter'}
RECORD_DATE_FIELDS={'occurrence_date','reported_date','payment_date','start_date','end_date'}
RECORD_FIELDS=RECORD_TEXT_FIELDS|RECORD_DATE_FIELDS|{'amount','exposure'}


def obj(v,required=(),optional=(),label='object'):
    if type(v) is not dict or not set(required)<=set(v) or set(v)-set(required)-set(optional):raise ValueError(label+'_fields')
    return v


def rows(v,label='rows',minimum=0,maximum=50):
    if type(v) is not list or not minimum<=len(v)<=maximum:raise ValueError(label+'_bounded_list_required')
    return v


def text(v,label='text',limit=10000):
    if type(v) is not str or not v.strip() or len(v)>limit:raise ValueError(label+'_required')
    if any(ord(ch)<32 and ch not in '\n\r\t' for ch in v):raise ValueError(label+'_control_character')
    return v


def ref(v):return text(v,'source_reference',200)


def present(v):return v is not None and not (type(v) is str and not v.strip())


def day(v,label='date'):
    if type(v) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',v):raise ValueError(label+'_iso_date_required')
    try:return date.fromisoformat(v)
    except ValueError:raise ValueError(label+'_invalid') from None


def past(v,cutoff,label='date'):
    d=day(v,label)
    if d>cutoff:raise ValueError(label+'_after_cutoff')
    return d


def number(v,label='number'):
    if type(v) is not str or len(v)>160 or not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d{1,3})?',v):raise ValueError(label+'_decimal_string_required')
    n=Decimal(v)
    if not n.is_finite() or len(n.as_tuple().digits)>40 or abs(n.as_tuple().exponent)>140 or n and abs(n.adjusted())>100:raise ValueError(label+'_bounded_decimal_required')
    return n


def quantity(v,unit=None,label='quantity',nonnegative=False):
    obj(v,('value','unit'),('source_reference',),label);text(v['unit'],'unit',80)
    if unit is not None and v['unit']!=unit:raise ValueError(label+'_unit_mismatch')
    if v.get('source_reference') is not None:ref(v['source_reference'])
    n=number(v['value'],label)
    if nonnegative and n<0:raise ValueError(label+'_nonnegative_required')
    return n


def unique(values,key='id'):
    seen=set()
    for row in values:
        ident=text(row[key],key,200)
        if ident in seen:raise ValueError('duplicate_'+key)
        seen.add(ident)


def bounded(v,depth=0,budget=None):
    if budget is None:budget=[0]
    budget[0]+=1
    if depth>24 or budget[0]>18000:raise ValueError('input_structure_limit')
    if type(v) is dict:
        if len(v)>100:raise ValueError('object_size_limit')
        for key,item in v.items():
            if type(key) is not str:raise ValueError('string_keys_required')
            if key.endswith(('_verified','_approved','_confirmed','_signed','_authorization_established')) or key in {
              'verified','approved','confirmed','signed','authorized','registered','sro_member','attested',
              'accounting_policy_approved_by_insurer','data_scope_agreed','qualified_status_granted',
              'actual_success_at','actual_weekly_update_performed','last_verified_at','host_context','engagement_context','safe','compliant'}:
                raise ValueError('reserved_authority_field:'+key)
            bounded(item,depth+1,budget)
    elif type(v) is list:
        if len(v)>500:raise ValueError('list_size_limit')
        for item in v:bounded(item,depth+1,budget)
    elif type(v) is str:
        if len(v)>160000:raise ValueError('text_size_limit')
    elif v is not None and type(v) is not bool:raise ValueError('exact_json_decimal_strings_required')


def base(data,required,optional=()):
    bounded(data);obj(data,('as_of','jurisdiction','valuation_date','data_scope',*required),optional,'scenario')
    if data['jurisdiction']!='RU':raise ValueError('jurisdiction_RU_required')
    asof=day(data['as_of'],'as_of');valuation=past(data['valuation_date'],asof,'valuation_date');text(data['data_scope'],'data_scope',500)
    return asof,valuation


def quote(v,source=None):
    ref(v['source_reference']);text(v['excerpt'],'excerpt',20000)
    if source is not None and (v['source_reference']!=source['source_reference'] or v['excerpt'] not in source['text']):raise ValueError('excerpt_not_in_selected_source')


def source(v,asof,event,scope):
    obj(v,SOURCE_KEYS,('not_after','role'),'selected_source')
    for key in ('source_reference','edition','scope'):text(v[key],key,2000)
    text(v['text'],'source_text',160000);past(v['publication_date'],asof,'publication_date')
    begin=day(v['effective_date'],'effective_date')
    if begin>event or v['scope']!=scope:raise ValueError('source_scope_or_event_period_mismatch')
    if v.get('not_after') is not None:
        end=day(v['not_after'],'not_after')
        if end<begin or event>end:raise ValueError('event_outside_provided_source_period')
    if v.get('role') is not None:text(v['role'],'source_role')
    return {k:copy.deepcopy(val) for k,val in v.items() if k!='text'}


def observation(v,asof,valuation):
    obj(v,('state',),('source_reference','excerpt','snapshot_date','valid_from','valid_to','subject_id','scope'),'evidence_record')
    if v['state'] not in STATES:raise ValueError('unsupported_evidence_state')
    if v['state']=='provided' or 'source_reference' in v or 'excerpt' in v:quote(v)
    if v.get('snapshot_date') is not None:past(v['snapshot_date'],asof,'snapshot_date')
    for k in ('valid_from','valid_to'):
        if v.get(k) is not None:day(v[k],k)
    if v.get('valid_from') is not None and v.get('valid_to') is not None and day(v['valid_to'])<day(v['valid_from']):raise ValueError('provided_evidence_period_invalid')
    for k in ('subject_id','scope'):
        if v.get(k) is not None:text(v[k],k)
    gaps=[]
    if v['state']!='provided':gaps.append('evidence_'+v['state'])
    if v.get('snapshot_date') is None:gaps.append('snapshot_date')
    elif day(v['snapshot_date'])>valuation:gaps.append('snapshot_after_valuation_date')
    if v.get('valid_from') is not None and day(v['valid_from'])>valuation:gaps.append('provided_period_not_started')
    if v.get('valid_to') is not None and day(v['valid_to'])<valuation:gaps.append('provided_period_ended')
    return dict(copy.deepcopy(v),evidence_gaps=gaps,semantic_status='not_assessed')


def result(function,data,**values):
    return dict(function=function,as_of=data['as_of'],valuation_date=data['valuation_date'],jurisdiction='RU',data_scope=data['data_scope'],
                analysis_only=True,assisted_draft=True,private=True,external_network_used=False,records_changed=False,
                approval_granted=False,signature_applied=False,submission_performed=False,qualified_status_granted=False,
                accounting_policy_adopted=False,source_semantics_verified=False,current_legal_applicability_verified=False,**values)


def data_assumptions(data):
    asof,valuation=base(data,('datasets',),('assumptions','proposed_corrections','limitations','selected_requirements'))
    output=[]
    for dataset in rows(data['datasets'],'datasets',1,5):
        obj(dataset,('id','period_start','period_end','cutoff_date','currency','perimeter','required_fields','dedup_keys','aggregation_basis','records','source_reference'),('accounting_control','exposure_control','exposure_unit'),'dataset')
        for k in ('id','currency','perimeter'):text(dataset[k],k,500)
        ref(dataset['source_reference']);start,end=day(dataset['period_start']),day(dataset['period_end']);cutoff=past(dataset['cutoff_date'],valuation,'data_cutoff')
        if start>end or end>cutoff:raise ValueError('dataset_period_outside_cutoff')
        required=rows(dataset['required_fields'],'required_fields',1,20);keys=rows(dataset['dedup_keys'],'dedup_keys',1,10)
        if len(set(required))!=len(required) or any(k not in RECORD_FIELDS for k in required):raise ValueError('supported_required_fields_required')
        if len(set(keys))!=len(keys) or any(k not in RECORD_TEXT_FIELDS|RECORD_DATE_FIELDS for k in keys):raise ValueError('supported_dedup_fields_required')
        if dataset['aggregation_basis'] not in ('raw_eligible','remove_identical_duplicates'):raise ValueError('explicit_aggregation_basis_required')
        records=rows(dataset['records'],'dataset_records',maximum=50);missing=Counter();groups={};issues=[];eligible=[]
        raw_amount=Decimal(0);raw_exposure=Decimal(0);exposure_unit=dataset.get('exposure_unit')
        if exposure_unit is not None:text(exposure_unit,'dataset_exposure_unit',80)
        for i,row in enumerate(records):
            obj(row,(),RECORD_FIELDS,'data_row');rowissues=[]
            for key in required:
                if key not in row or not present(row[key]):missing[key]+=1;rowissues.append('missing.'+key)
            for key,value in row.items():
                if not present(value):continue
                if key in RECORD_TEXT_FIELDS:text(value,key,1000)
                elif key in RECORD_DATE_FIELDS:
                    d=day(value,key)
                    # Known contract coverage boundaries can lie in the future;
                    # they are not observed claim/payment/reporting events.
                    if key in {'occurrence_date','reported_date','payment_date'} and d>cutoff:rowissues.append('after_cutoff.'+key)
                elif key=='amount':quantity(value,label='row_amount')
                elif key=='exposure':quantity(value,label='row_exposure',nonnegative=True)
            if present(row.get('occurrence_date')):
                event=day(row['occurrence_date'])
                if not start<=event<=end:rowissues.append('event_outside_selected_period')
                if present(row.get('reported_date')) and day(row['reported_date'])<event:rowissues.append('reported_before_occurrence')
                if present(row.get('payment_date')) and day(row['payment_date'])<event:rowissues.append('payment_before_occurrence')
            if present(row.get('start_date')) and present(row.get('end_date')) and day(row['end_date'])<day(row['start_date']):rowissues.append('coverage_end_before_start')
            if present(row.get('currency')) and row['currency']!=dataset['currency']:rowissues.append('currency_outside_selected_perimeter')
            if present(row.get('perimeter')) and row['perimeter']!=dataset['perimeter']:rowissues.append('record_perimeter_mismatch')
            if present(row.get('amount')) and row['amount']['unit']!=dataset['currency']:rowissues.append('amount_unit_outside_selected_currency')
            if present(row.get('exposure')):
                unit=row['exposure']['unit']
                if exposure_unit is None:rowissues.append('dataset_exposure_unit_missing')
                elif unit!=exposure_unit:rowissues.append('exposure_unit_mismatch')
            key=tuple(row.get(k) for k in keys)
            if all(type(part) is str and part for part in key):groups.setdefault(key,[]).append(i)
            else:rowissues.append('dedup_key_incomplete')
            if rowissues:issues.append(dict(row_index=i,codes=rowissues))
            is_eligible=not rowissues
            eligible.append(is_eligible)
            if is_eligible:
                if present(row.get('amount')):raw_amount+=quantity(row['amount'],dataset['currency'])
                if present(row.get('exposure')):raw_exposure+=quantity(row['exposure'],exposure_unit)
        duplicates=[];remove=set();conflicts=False
        for key,indices in groups.items():
            if len(indices)<2:continue
            serial=[json.dumps(records[i],sort_keys=True,ensure_ascii=False) for i in indices];identical=len(set(serial))==1
            duplicates.append(dict(key=list(key),row_indices=indices,identical_rows=identical))
            if identical:remove.update(indices[1:])
            else:conflicts=True
        dedup_amount=raw_amount;dedup_exposure=raw_exposure
        for i in remove:
            if eligible[i]:
                if present(records[i].get('amount')):dedup_amount-=quantity(records[i]['amount'],dataset['currency'])
                if present(records[i].get('exposure')):dedup_exposure-=quantity(records[i]['exposure'],exposure_unit)
        chosen_amount=raw_amount if dataset['aggregation_basis']=='raw_eligible' else (None if conflicts else dedup_amount)
        chosen_exposure=raw_exposure if dataset['aggregation_basis']=='raw_eligible' else (None if conflicts else dedup_exposure)
        accounting=None;exposure_control=None;gaps=[]
        if dataset.get('accounting_control') is not None:
            c=dataset['accounting_control'];obj(c,('amount','period_start','period_end','cutoff_date','perimeter','source_reference','excerpt'),label='accounting_control');quote(c)
            control_amount=quantity(c['amount'],dataset['currency'])
            scope_matches=all(c[k]==dataset[k] for k in ('period_start','period_end','cutoff_date','perimeter'))
            for k in ('period_start','period_end','cutoff_date'):past(c[k],asof,'control_'+k)
            accounting=dict(source_reference=c['source_reference'],scope_match=scope_matches,
                            control_amount=str(control_amount),difference=str(chosen_amount-control_amount) if scope_matches and chosen_amount is not None else None)
            if not scope_matches:gaps.append('accounting_control_scope_mismatch')
        else:gaps.append('accounting_control')
        if dataset.get('exposure_control') is not None:
            exposure_control_value=quantity(dataset['exposure_control'],exposure_unit)
            exposure_control=dict(unit=dataset['exposure_control']['unit'],control_value=str(exposure_control_value),difference=str(chosen_exposure-exposure_control_value) if chosen_exposure is not None and exposure_unit is not None else None)
        else:gaps.append('exposure_control')
        if conflicts:gaps.append('conflicting_duplicate_keys')
        output.append(dict(id=dataset['id'],period_start=dataset['period_start'],period_end=dataset['period_end'],cutoff_date=dataset['cutoff_date'],
                           record_count=len(records),eligible_record_count=sum(eligible),missing_field_counts=dict(missing),row_issues=issues,
                           duplicate_groups=duplicates,duplicate_excess_rows=sum(len(d['row_indices'])-1 for d in duplicates),
                           currency=dataset['currency'],perimeter=dataset['perimeter'],aggregation_basis=dataset['aggregation_basis'],
                           raw_eligible_amount=str(raw_amount),identical_dedup_candidate_amount=None if conflicts else str(dedup_amount),
                           selected_amount=str(chosen_amount) if chosen_amount is not None else None,
                           exposure_unit=exposure_unit,raw_eligible_exposure=str(raw_exposure),selected_exposure=str(chosen_exposure) if chosen_exposure is not None else None,
                           accounting_reconciliation=accounting,exposure_reconciliation=exposure_control,evidence_gaps=gaps,source_reference=dataset['source_reference']))
    unique(output);assumptions=[]
    for a in rows(data.get('assumptions',[]),'assumptions',maximum=20):
        obj(a,('id','kind','proposed_value','experience_start','experience_end','source_reference','excerpt','rationale'),('sensitivity','source_edition','source_publication_date','population_scope'),'assumption')
        quote(a);quantity(a['proposed_value']);text(a['kind'],'assumption_kind');text(a['rationale'],'proposed_rationale')
        for key in ('source_edition','population_scope'):
            if a.get(key) is not None:text(a[key],key)
        if a.get('source_publication_date') is not None:past(a['source_publication_date'],asof,'assumption_source_publication_date')
        begin,end=day(a['experience_start']),past(a['experience_end'],valuation,'experience_end')
        if begin>end:raise ValueError('assumption_experience_period_invalid')
        sensitivity=[]
        for s in rows(a.get('sensitivity',[]),'sensitivity',maximum=5):
            obj(s,('alternative',),('result','comment'),'sensitivity');quantity(s['alternative'],a['proposed_value']['unit'])
            if s.get('result') is not None:quantity(s['result'])
            if s.get('comment') is not None:text(s['comment'],'sensitivity_comment')
            sensitivity.append(copy.deepcopy(s))
        assumption_gaps=[key for key in ('source_edition','source_publication_date','population_scope') if a.get(key) is None]
        assumptions.append(dict(copy.deepcopy(a),sensitivity=sensitivity,evidence_gaps=assumption_gaps,status='proposed_assumption_not_adopted'))
    unique(assumptions)
    notes={}
    for field in ('proposed_corrections','limitations'):
        notes[field]=[text(v,field) for v in rows(data.get(field,[]),field,maximum=30)]
    requirements=[source(r,asof,valuation,data['data_scope']) for r in rows(data.get('selected_requirements',[]),'selected_requirements',maximum=10)]
    return result('data_assumptions',data,dataset_reviews=output,assumption_reviews=assumptions,selected_requirements=requirements,**notes,
                  notices=['local_pseudonymous_data_only','candidate_dedup_is_not_data_mutation','source_occurrence_not_semantics'])


def actuarial_task(data):
    asof,valuation=base(data,('draft_task','clauses','source_reference'),('selected_contract','selected_requirements'))
    ref(data['source_reference'])
    draft=data['draft_task'];obj(draft,('client','executor','purpose','object','data_responsibility','limitations','result_usage'),('delivery_date',),'draft_task')
    for key,value in draft.items():
        if key=='delivery_date':day(value)
        else:text(value,key)
    contract=data.get('selected_contract');contractmeta=None
    if contract is not None:
        obj(contract,(*SOURCE_KEYS,'valuation_date','data_scope'),('not_after','role'),'selected_contract')
        sourcepart={k:v for k,v in contract.items() if k in SOURCE_KEYS|{'not_after','role'}}
        contractmeta=source(sourcepart,asof,valuation,data['data_scope']);day(contract['valuation_date']);text(contract['data_scope'],'contract_data_scope')
        contractmeta.update(valuation_date=contract['valuation_date'],data_scope=contract['data_scope'])
    seen={};reviews=[]
    for clause in rows(data['clauses'],'clauses',maximum=30):
        obj(clause,('topic','value','source_reference','excerpt'),label='contract_clause')
        if clause['topic'] not in CLAUSE_TOPICS:raise ValueError('supported_contract_clause_topic_required')
        text(clause['value'],'clause_value');quote(clause,contract)
        if contract is None:raise ValueError('selected_contract_required_for_existing_clause')
        if clause['value'] not in clause['excerpt']:raise ValueError('clause_value_not_in_selected_excerpt')
        seen.setdefault(clause['topic'],[]).append(clause['value'])
        proposed=data[clause['topic']] if clause['topic'] in ('valuation_date','data_scope') else draft.get(clause['topic'])
        reviews.append(dict(copy.deepcopy(clause),matches_proposed_literal=proposed==clause['value'],semantic_status='not_assessed'))
    contradictions=[dict(topic=k,provided_values=sorted(set(v))) for k,v in seen.items() if len(set(v))>1]
    missing=[k for k in CLAUSE_TOPICS if k not in seen];gaps=[]
    if contract is None:gaps.append('selected_contract')
    elif contract['valuation_date']!=data['valuation_date'] or contract['data_scope']!=data['data_scope']:gaps.append('contract_valuation_or_data_scope_mismatch')
    rules=[source(r,asof,valuation,data['data_scope']) for r in rows(data.get('selected_requirements',[]),'selected_requirements',maximum=10)]
    if not rules:gaps.append('selected_requirements')
    return result('actuarial_task',data,draft_task=copy.deepcopy(draft),source_reference=data['source_reference'],selected_contract=contractmeta,clause_reviews=reviews,
                  missing_clause_topics=missing,contradictions=contradictions,evidence_gaps=gaps,selected_requirements=rules,
                  engagement_status='host_scope_confirmation_required_for_valuation',notices=['draft_contract_not_agreement','literal_clause_match_not_legal_clearance'])


def ledger(v,currency):
    obj(v,('assets','liabilities','liability_basis'),label='balance_sheet')
    if v['liability_basis']!='all_liabilities_including_reserves':raise ValueError('all_liabilities_including_reserves_required')
    assets=[];liabilities=[]
    for kind,output in (('assets',assets),('liabilities',liabilities)):
        for row in rows(v[kind],kind,maximum=50):
            obj(row,('id','kind','amount','source_reference'),label='balance_sheet_item');ref(row['id']);ref(row['source_reference'])
            allowed={'general','reinsurance'} if kind=='assets' else {'reserve','other'}
            if row['kind'] not in allowed:raise ValueError('supported_balance_sheet_item_kind_required')
            quantity(row['amount'],currency,nonnegative=True);output.append(copy.deepcopy(row))
        unique(output)
    if set(a['id'] for a in assets)&set(l['id'] for l in liabilities):raise ValueError('balance_sheet_id_in_both_sides')
    asset_total=sum((quantity(r['amount'],currency) for r in assets),Decimal(0));liability_total=sum((quantity(r['amount'],currency) for r in liabilities),Decimal(0))
    reserve_total=sum((quantity(r['amount'],currency) for r in liabilities if r['kind']=='reserve'),Decimal(0))
    reinsurance_total=sum((quantity(r['amount'],currency) for r in assets if r['kind']=='reinsurance'),Decimal(0))
    return dict(assets=assets,liabilities=liabilities,liability_basis=v['liability_basis'],currency=currency,
                assets_total=str(asset_total),liabilities_total=str(liability_total),reserves_subset=str(reserve_total),
                reinsurance_assets=str(reinsurance_total),capital=str(asset_total-liability_total))


def conditional_deadline(config,event):
    obj(config,('duration','count_start','roll'),('calendar',),'deadline_calculation');n=quantity(config['duration']);unit=config['duration']['unit']
    if n!=n.to_integral_value() or not 1<=n<=365 or unit not in ('calendar_days','business_days'):raise ValueError('supported_positive_bounded_day_duration_required')
    if config['count_start'] not in ('include_event','next_day') or config['roll'] not in ('none','next_working_day'):raise ValueError('explicit_count_start_and_roll_required')
    include=config['count_start']=='include_event';calendar=config.get('calendar');classified={}
    if unit=='business_days' or config['roll']=='next_working_day':
        obj(calendar,('coverage_from','coverage_to','days','source_reference'),label='calendar');ref(calendar['source_reference']);begin,end=day(calendar['coverage_from']),day(calendar['coverage_to'])
        if not begin<=event<=end or (end-begin).days>365:raise ValueError('calendar_coverage_invalid')
        values=rows(calendar['days'],'calendar_days',1,366)
        if len(values)!=(end-begin).days+1:raise ValueError('complete_daily_calendar_required')
        for i,row in enumerate(values):
            obj(row,('date','working'),label='calendar_day');d=day(row['date'])
            if d!=begin+timedelta(days=i) or type(row['working']) is not bool:raise ValueError('complete_ordered_classified_calendar_required')
            classified[d]=row['working']
    elif calendar is not None:raise ValueError('unused_calendar')
    counted=[]
    if unit=='business_days':
        choices=[d for d,w in classified.items() if w and (d>event or include and d==event)]
        if len(choices)<int(n):raise ValueError('calendar_does_not_cover_deadline')
        counted=choices[:int(n)];candidate=counted[-1]
    else:
        offset=int(n)-(1 if include else 0)
        if (date.max-event).days<offset:raise ValueError('deadline_overflow')
        candidate=event+timedelta(days=offset)
    nominal=candidate
    if config['roll']=='next_working_day':
        while True:
            if candidate not in classified:raise ValueError('calendar_does_not_cover_roll')
            if classified[candidate]:break
            if candidate==date.max:raise ValueError('deadline_overflow')
            candidate+=timedelta(days=1)
    return dict(candidate_deadline=candidate.isoformat(),nominal_deadline=nominal.isoformat(),counted_dates=[d.isoformat() for d in counted],
                calendar_reference=calendar['source_reference'] if calendar else None,count_start=config['count_start'],roll=config['roll'])


def deadline(v,asof,scope):
    obj(v,('event_date','role','selected_rule'),('due_date','calculation'),'reporting_deadline')
    if ('due_date' in v)==('calculation' in v):raise ValueError('exactly_one_deadline_mode_required')
    event=past(v['event_date'],asof,'deadline_event');text(v['role'],'reporting_role');meta=source(v['selected_rule'],asof,event,scope)
    if meta.get('role')!=v['role']:raise ValueError('deadline_rule_role_mismatch')
    calculated=conditional_deadline(v['calculation'],event) if 'calculation' in v else None
    d=day(calculated['candidate_deadline'] if calculated else v['due_date'],'due_date')
    if d<event:raise ValueError('deadline_before_event')
    return dict(candidate_deadline=d.isoformat(),selected_rule=meta,calculation=calculated,provided_date=v.get('due_date'),
                overdue_at_as_of=d<asof,legal_applicability='not_assessed')


def mandatory_assessment(data):
    asof,valuation=base(data,('organization','organization_type','currency','balance_sheet','selected_requirements'),
              ('reported_reserves','prior_period','assessment_sections','reporting_deadline','actuary'))
    text(data['organization'],'organization');text(data['organization_type'],'organization_type');text(data['currency'],'currency',10)
    current=ledger(data['balance_sheet'],data['currency']);requirements=data['selected_requirements']
    obj(requirements,('selected_rule',),('required_capital',),'capital_requirements');rulemeta=source(requirements['selected_rule'],asof,valuation,data['data_scope'])
    req=None;ratio=None;gaps=[]
    actuary=None
    if data.get('actuary') is not None:
        a=data['actuary'];obj(a,('local_id',),('name','registry_identifier','record'),'actuary_identity');text(a['local_id'],'actuary_local_id')
        for key in ('name','registry_identifier'):
            if a.get(key) is not None:text(a[key],key)
        actuary=copy.deepcopy(a)
        if a.get('record') is not None:actuary['record']=observation(a['record'],asof,valuation)
        else:gaps.append('actuary_identity_record')
    else:gaps.append('actuary_identity')
    if requirements.get('required_capital') is not None:
        req=quantity(requirements['required_capital'],data['currency'],nonnegative=True)
        if req:ratio=Decimal(current['capital'])/req
        else:gaps.append('zero_required_capital_ratio_undefined')
    else:gaps.append('required_capital')
    reserve_difference=None
    if data.get('reported_reserves') is not None:reserve_difference=str(Decimal(current['reserves_subset'])-quantity(data['reported_reserves'],data['currency'],nonnegative=True))
    else:gaps.append('reported_reserves')
    prior=None
    if data.get('prior_period') is not None:
        p=data['prior_period'];obj(p,('valuation_date','balance_sheet'),label='prior_period')
        if day(p['valuation_date'])>=valuation:raise ValueError('prior_period_must_precede_valuation')
        old=ledger(p['balance_sheet'],data['currency'])
        prior=dict(valuation_date=p['valuation_date'],balance_sheet=old,changes={key:str(Decimal(current[key])-Decimal(old[key])) for key in ('assets_total','liabilities_total','reserves_subset','capital')})
    else:gaps.append('prior_period')
    sections={}
    obj(data.get('assessment_sections',{}),(),('data_review','assumptions','methods','limitations','recommendations'),'assessment_sections')
    for k,val in data.get('assessment_sections',{}).items():sections[k]=text(val,k,20000)
    gaps.extend('assessment_sections.'+key for key in ('data_review','assumptions','methods','limitations','recommendations') if key not in sections)
    due=deadline(data['reporting_deadline'],asof,data['data_scope']) if data.get('reporting_deadline') is not None else None
    if due is None:gaps.append('reporting_deadline')
    return result('mandatory_assessment',data,organization=data['organization'],organization_type=data['organization_type'],actuary=actuary,balance_sheet=current,
                  selected_requirements=rulemeta,required_capital=str(req) if req is not None else None,conditional_capital_ratio=str(ratio) if ratio is not None else None,
                  reported_reserves=copy.deepcopy(data.get('reported_reserves')),reserve_reconciliation_difference=reserve_difference,prior_period=prior,assessment_sections=sections,reporting_deadline=due,evidence_gaps=gaps,
                  notices=['reserves_are_subset_of_all_liabilities','conditional_ratio_not_regulatory_solvency','draft_conclusion_requires_responsible_actuary'])


def gmm_initial(v,currency,valuation):
    obj(v,('scope','cashflows','risk_adjustment','risk_basis'),label='gmm_initial')
    if v['scope']!='issued_no_prior_recognised_assets_or_initial_settlements':raise ValueError('supported_initial_recognition_scope_required')
    obj(v['risk_basis'],('kind','source_reference','excerpt'),label='risk_basis');quote(v['risk_basis'])
    if v['risk_basis']['kind']!='nonfinancial':raise ValueError('risk_adjustment_nonfinancial_required')
    ra=quantity(v['risk_adjustment'],currency,nonnegative=True);pv=Decimal(0);flows=[]
    for flow in rows(v['cashflows'],'gmm_cashflows',1,40):
        obj(flow,('date','outflow','inflow','discount_factor'),label='gmm_cashflow')
        if day(flow['date'])<valuation:raise ValueError('future_cashflow_before_valuation')
        out,incoming=quantity(flow['outflow'],currency,nonnegative=True),quantity(flow['inflow'],currency,nonnegative=True)
        df=quantity(flow['discount_factor'],'ratio')
        if df<=0:raise ValueError('positive_discount_factor_required')
        part=(out-incoming)*df;pv+=part;flows.append(dict(copy.deepcopy(flow),pv_outflow_minus_inflow=str(part)))
    fcf=pv+ra;csm=max(-fcf,Decimal(0));loss=max(fcf,Decimal(0))
    return dict(present_value_outflow_minus_inflow=str(pv),risk_adjustment=str(ra),risk_basis=copy.deepcopy(v['risk_basis']),fulfilment_cashflows=str(fcf),
                initial_csm=str(csm),initial_onerous_loss=str(loss),initial_net_carrying_liability=str(fcf+csm),cashflow_review=flows,
                sign_convention='positive_is_net_outflow_liability',scope=v['scope'])


def csm_movement(v,currency):
    obj(v,('opening_csm','interest_accretion','future_service_change','opening_loss_component','coverage_current','coverage_future','fx_mode'),
        ('fx_csm_change','fx_loss_change','loss_component_service_allocation'),'csm_rollforward')
    opening=quantity(v['opening_csm'],currency,nonnegative=True);interest=quantity(v['interest_accretion'],currency)
    change=quantity(v['future_service_change'],currency);oldloss=quantity(v['opening_loss_component'],currency,nonnegative=True)
    if opening and oldloss:raise ValueError('opening_csm_and_loss_component_cannot_both_be_positive_in_supported_group')
    if not opening and interest:raise ValueError('interest_accretion_requires_positive_opening_csm')
    available=opening+interest
    if available<0:raise ValueError('negative_csm_after_provided_interest')
    if change>=0:
        after=max(available-change,Decimal(0));newloss=oldloss+max(change-available,Decimal(0));recognition=max(change-available,Decimal(0));reversal=Decimal(0)
    else:
        benefit=-change;reversal=min(oldloss,benefit);newloss=oldloss-reversal;after=available+benefit-reversal;recognition=Decimal(0)
    fx=Decimal(0);lossfx=Decimal(0)
    if v['fx_mode']=='provided_adjustments':
        fx=quantity(v['fx_csm_change'],currency);lossfx=quantity(v['fx_loss_change'],currency)
    elif v['fx_mode']=='no_currency_translation_selected':
        if 'fx_csm_change' in v or 'fx_loss_change' in v:raise ValueError('no_fx_mode_with_fx_amounts')
    else:raise ValueError('explicit_fx_mode_required')
    before_release=after+fx;loss_before_allocation=newloss+lossfx
    if before_release<0 or loss_before_allocation<0:raise ValueError('negative_margin_or_loss_after_fx')
    if before_release and loss_before_allocation:raise ValueError('provided_movements_create_csm_and_loss_component_overlap_in_supported_group')
    current=quantity(v['coverage_current'],'coverage_unit',nonnegative=True);future=quantity(v['coverage_future'],'coverage_unit',nonnegative=True)
    if current+future<=0:raise ValueError('positive_total_coverage_units_required')
    released=before_release*current/(current+future);closing=before_release-released
    allocated=None;closing_loss=None;gaps=[]
    if v.get('loss_component_service_allocation') is not None:
        allocated=quantity(v['loss_component_service_allocation'],currency,nonnegative=True)
        if allocated>loss_before_allocation:raise ValueError('loss_allocation_exceeds_available_component')
        closing_loss=loss_before_allocation-allocated
    elif loss_before_allocation:gaps.append('loss_component_service_allocation')
    else:closing_loss=Decimal(0)
    return dict(opening_csm=str(opening),opening_loss_component=str(oldloss),interest_accretion=str(interest),future_service_change=str(change),
                new_loss_recognition=str(recognition),loss_reversal=str(reversal),fx_csm_change=str(fx),fx_loss_change=str(lossfx),
                csm_before_service_release=str(before_release),csm_released=str(released),closing_csm=str(closing),
                loss_component_before_service_allocation=str(loss_before_allocation),closing_loss_component=str(closing_loss) if closing_loss is not None else None,
                coverage_current=copy.deepcopy(v['coverage_current']),coverage_future=copy.deepcopy(v['coverage_future']),fx_mode=v['fx_mode'],
                loss_component_service_allocation=str(allocated) if allocated is not None else None,
                evidence_gaps=gaps,scope='selected_movements_no_new_contracts_or_full_fcf_reconciliation',change_sign='positive_future_service_change_is_adverse')


def paa_movement(v,currency,asof,valuation):
    obj(v,('opening_lrc_excluding_loss_component','eligibility_basis','acquisition_policy','movements'),('loss_test',),'paa')
    eligibility=observation(v['eligibility_basis'],asof,valuation)
    if v['acquisition_policy'] not in ('capitalise','expense_as_incurred_selected'):raise ValueError('explicit_paa_acquisition_policy_required')
    opening=quantity(v['opening_lrc_excluding_loss_component'],currency);closing=opening;review=[]
    signs={'premium_received':1,'acquisition_paid':-1,'acquisition_amortisation':1,'insurance_revenue':-1,'investment_component_paid':-1,'financing':1,'fx':1}
    for m in rows(v['movements'],'paa_movements',maximum=30):
        obj(m,('id','type','amount'),label='paa_movement');ref(m['id'])
        if m['type'] not in signs:raise ValueError('supported_paa_movement_type_required')
        amount=quantity(m['amount'],currency,nonnegative=m['type'] not in ('financing','fx'))
        if v['acquisition_policy']=='expense_as_incurred_selected' and m['type'] in ('acquisition_paid','acquisition_amortisation'):raise ValueError('paa_expensed_acquisition_not_in_lrc_ledger')
        delta=signs[m['type']]*amount;closing+=delta;review.append(dict(copy.deepcopy(m),signed_lrc_change=str(delta)))
    unique(review);loss=None;gaps=list(eligibility['evidence_gaps'])
    if v.get('loss_test') is not None:
        loss_=v['loss_test'];obj(loss_,('remaining_fcf','opening_loss_component','source_reference','excerpt'),label='paa_loss_test');quote(loss_)
        fcf=quantity(loss_['remaining_fcf'],currency);old=quantity(loss_['opening_loss_component'],currency,nonnegative=True)
        component=max(fcf-closing,Decimal(0))
        loss=dict(remaining_fcf=str(fcf),closing_loss_component=str(component),change_in_loss_component=str(component-old),
                  lrc_including_loss_component=str(closing+component),basis='supplied_remaining_fcf_and_lrc_excluding_loss_component')
    else:gaps.append('paa_onerous_loss_test')
    return dict(opening_lrc_excluding_loss_component=str(opening),closing_lrc_excluding_loss_component=str(closing),movements=review,
                eligibility_basis=eligibility,eligibility_conclusion='not_assessed',acquisition_policy=v['acquisition_policy'],loss_test=loss,evidence_gaps=gaps)


def ifrs17(data):
    asof,valuation=base(data,('groups',),('regulatory_reconciliation','transition_note'));reviews=[]
    for group in rows(data['groups'],'ifrs_groups',1,20):
        obj(group,('id','portfolio','cohort','profitability','currency','model','selected_rule'),('initial','rollforward','paa','vfa_review'),'ifrs_group')
        for key in ('id','portfolio','cohort','currency'):text(group[key],key,500)
        if not re.fullmatch(r'\d{4}',group['cohort']):raise ValueError('explicit_annual_cohort_required')
        if group['profitability'] not in ('onerous','no_significant_possibility','other'):raise ValueError('explicit_profitability_group_required')
        meta=source(group['selected_rule'],asof,valuation,data['data_scope']);currency=group['currency'];gaps=[]
        initial=movement=paa=vfa=None
        if group['model']=='GMM':
            if 'paa' in group or 'vfa_review' in group:raise ValueError('gmm_cannot_use_other_model_inputs')
            if group.get('initial') is not None:
                initial=gmm_initial(group['initial'],currency,valuation)
                if (Decimal(initial['initial_onerous_loss'])>0)!=(group['profitability']=='onerous'):gaps.append('declared_profitability_differs_from_initial_arithmetic')
            if group.get('rollforward') is not None:movement=csm_movement(group['rollforward'],currency)
            if initial is None and movement is None:raise ValueError('gmm_initial_or_movement_required')
        elif group['model']=='PAA':
            if 'initial' in group or 'rollforward' in group or 'vfa_review' in group:raise ValueError('paa_has_separate_lrc_path')
            paa=paa_movement(group['paa'],currency,asof,valuation)
        elif group['model']=='VFA_REVIEW':
            if any(k in group for k in ('initial','rollforward','paa')):raise ValueError('vfa_review_is_not_generic_discount_model')
            v=group['vfa_review'];obj(v,('underlying_fair_value','entity_share_ratio','nonvarying_fcf','eligibility_basis','fee_basis','risk_adjustment_scope'),label='vfa_review')
            underlying=quantity(v['underlying_fair_value'],currency,nonnegative=True);share=quantity(v['entity_share_ratio'],'ratio');nonvarying=quantity(v['nonvarying_fcf'],currency)
            if not 0<=share<=1:raise ValueError('entity_share_ratio_between_zero_and_one_required')
            if v['risk_adjustment_scope']!='included_in_nonvarying_fcf':raise ValueError('explicit_vfa_nonfinancial_ra_scope_required')
            eligibility=observation(v['eligibility_basis'],asof,valuation);fee_basis=observation(v['fee_basis'],asof,valuation)
            vfa=dict(entity_share_of_underlying_items=str(underlying*share),nonvarying_fcf=str(nonvarying),selected_variable_fee=str(underlying*share-nonvarying),
                     eligibility_basis=eligibility,fee_basis=fee_basis,eligibility_conclusion='not_assessed',csm='not_calculated',
                     scope='selected_B104_fee_arithmetic_only_no_options_guarantees_or_full_VFA_measurement')
        else:raise ValueError('supported_ifrs_model_required')
        reviews.append(dict(id=group['id'],portfolio=group['portfolio'],cohort=group['cohort'],profitability=group['profitability'],currency=currency,
                            model=group['model'],selected_rule=meta,gmm_initial=initial,csm_rollforward=movement,paa=paa,vfa_review=vfa,evidence_gaps=gaps))
    unique(reviews)
    regulatory=observation(data['regulatory_reconciliation'],asof,valuation) if data.get('regulatory_reconciliation') is not None else None
    if data.get('transition_note') is not None:text(data['transition_note'],'transition_note')
    return result('ifrs17',data,group_reviews=reviews,regulatory_reconciliation=regulatory,transition_note=data.get('transition_note'),
                  evidence_gaps=['regulatory_reconciliation'] if regulatory is None else list(regulatory['evidence_gaps']),
                  notices=['conditional_accounting_arithmetic_not_ifrs_compliance','positive_is_net_outflow_liability','no_policy_approval_or_automatic_posting'])


def solvency_stress(data):
    asof,valuation=base(data,('currency','balance_sheet','required_capital','selected_rule','scenarios'))
    text(data['currency'],'currency',10);currency=data['currency'];base_=ledger(data['balance_sheet'],currency);required=quantity(data['required_capital'],currency,nonnegative=True)
    rulemeta=source(data['selected_rule'],asof,valuation,data['data_scope']);scenarios=[]
    for scenario in rows(data['scenarios'],'stress_scenarios',1,30):
        obj(scenario,('id','description','asset_changes','liability_changes','direct_cost','required_capital_change','source_reference'),label='stress_scenario')
        ref(scenario['id']);text(scenario['description'],'scenario_description');ref(scenario['source_reference'])
        assets={r['id']:quantity(r['amount'],currency) for r in base_['assets']};liabilities={r['id']:quantity(r['amount'],currency) for r in base_['liabilities']}
        all_changes=[]
        for name,values in (('asset_changes',assets),('liability_changes',liabilities)):
            changes=rows(scenario[name],name,maximum=50);ids=set()
            for c in changes:
                obj(c,('item_id','delta','source_reference','excerpt'),label='stress_change');quote(c);ref(c['item_id'])
                if c['item_id'] not in values or c['item_id'] in ids:raise ValueError('unknown_or_duplicate_stress_item')
                ids.add(c['item_id']);delta=quantity(c['delta'],currency);values[c['item_id']]+=delta
                if values[c['item_id']]<0:raise ValueError('stressed_balance_item_negative')
                all_changes.append(dict(side=name,**copy.deepcopy(c)))
        direct_cost=quantity(scenario['direct_cost'],currency,nonnegative=True);capital_delta=quantity(scenario['required_capital_change'],currency)
        stressed_required=required+capital_delta
        if stressed_required<0:raise ValueError('stressed_required_capital_negative')
        asset_total=sum(assets.values(),Decimal(0));liability_total=sum(liabilities.values(),Decimal(0));capital=asset_total-liability_total-direct_cost
        reinsurance=sum((assets[r['id']] for r in base_['assets'] if r['kind']=='reinsurance'),Decimal(0))
        reserves=sum((liabilities[r['id']] for r in base_['liabilities'] if r['kind']=='reserve'),Decimal(0))
        scenarios.append(dict(id=scenario['id'],description=scenario['description'],changes=all_changes,stressed_assets_before_direct_cost=str(asset_total),
                              stressed_reinsurance_assets=str(reinsurance),stressed_reserves_subset=str(reserves),stressed_all_liabilities=str(liability_total),
                              direct_cost=str(direct_cost),conditional_capital=str(capital),capital_change=str(capital-Decimal(base_['capital'])),
                              stressed_required_capital=str(stressed_required),conditional_ratio=str(capital/stressed_required) if stressed_required else None,
                              source_reference=scenario['source_reference'],solvency_conclusion='not_assessed'))
    unique(scenarios)
    return result('solvency_stress',data,base_balance_sheet=base_,base_required_capital=str(required),base_conditional_ratio=str(Decimal(base_['capital'])/required) if required else None,selected_rule=rulemeta,scenario_reviews=scenarios,
                  evidence_gaps=['reserve_gross_net_basis_not_established'],
                  notices=['reserves_subset_reinsurance_assets_and_other_liabilities_separate','selected_deltas_not_automatic_lapse_factor','conditional_ratio_not_regulatory_solvency'])


def actuary_status(data):
    asof,valuation=base(data,('subject_id','purpose','requirements'));text(data['subject_id'],'subject_id');text(data['purpose'],'purpose');reviews=[]
    topics=set()
    for r in rows(data['requirements'],'status_requirements',1,30):
        obj(r,('id','topic','selected_rule','record'),('observed_quantity','minimum_quantity'),'status_requirement')
        ref(r['id'])
        if r['topic'] not in ('sro','attestation','registry','experience','cpd','independence','restrictions','education'):raise ValueError('supported_status_requirement_topic_required')
        topics.add(r['topic']);meta=source(r['selected_rule'],asof,valuation,data['data_scope']);observed=observation(r['record'],asof,valuation);gaps=list(observed['evidence_gaps'])
        if r['record'].get('subject_id') is None:gaps.append('subject_id')
        elif r['record']['subject_id']!=data['subject_id']:gaps.append('evidence_subject_mismatch')
        if r['record'].get('scope') is not None and r['record']['scope']!=data['data_scope']:gaps.append('evidence_scope_mismatch')
        quantitative=None
        if 'observed_quantity' in r or 'minimum_quantity' in r:
            if not ('observed_quantity' in r and 'minimum_quantity' in r):raise ValueError('observed_and_selected_minimum_required_together')
            actual=quantity(r['observed_quantity'],nonnegative=True);minimum=quantity(r['minimum_quantity'],r['observed_quantity']['unit'],nonnegative=True)
            if r['topic'] not in ('experience','cpd'):raise ValueError('numeric_status_comparison_only_experience_or_cpd')
            quantitative=dict(observed_value=str(actual),selected_minimum=str(minimum),unit=r['observed_quantity']['unit'],difference=str(actual-minimum),
                              below_selected_minimum=actual<minimum,eligibility='not_assessed')
        reviews.append(dict(id=r['id'],topic=r['topic'],selected_rule=meta,record=observed,numeric_comparison=quantitative,evidence_gaps=gaps,practice_status='not_determined'))
    unique(reviews);missing=sorted({'sro','attestation','registry','experience','cpd','independence','restrictions'}-topics)
    return result('actuary_status',data,subject_id=data['subject_id'],purpose=data['purpose'],requirement_reviews=reviews,unaddressed_topics=missing,
                  notices=['selected_registry_snapshot_not_live_lookup','provided_record_does_not_grant_practice_right','no_fixed_eternal_experience_threshold'])


def input_units(function,data):
    if function not in FUNCTIONS:raise ValueError('unknown_actuary_scenario')
    bounded(data);units={};asof=data['as_of'];valuation=data['valuation_date']
    def walk(v,path='',when=None):
        if type(v) is dict:
            when=v.get('snapshot_date',when)
            if 'value' in v and 'unit' in v:
                effective_cutoff=asof if function in ('data_assumptions','actuary_status','actuarial_task') else valuation
                if path.startswith('/reporting_deadline/'):
                    effective_cutoff=data['reporting_deadline']['event_date']
                item={'unit':v['unit'],'effective_not_after':effective_cutoff,'published_not_after':asof}
                if when is not None:item['effective_date']=when
                units[path+'/value']=item
            for key,item in v.items():walk(item,path+'/'+key.replace('~','~0').replace('/','~1'),when)
        elif type(v) is list:
            for i,item in enumerate(v):walk(item,path+'/'+str(i),when)
    walk(data)
    if len(units)>900:raise ValueError('numeric_binding_contract_limit')
    return units


def selected_texts(function,data):
    if function not in FUNCTIONS:raise ValueError('unknown_actuary_scenario')
    bounded(data);texts={}
    def walk(v,path=''):
        if type(v) is dict:
            for key,item in v.items():
                p=path+'/'+key.replace('~','~0').replace('/','~1')
                if key=='excerpt' or key=='text' and 'source_reference' in v:texts[p]=text(item,'existing_selected_text',160000)
                else:walk(item,p)
        elif type(v) is list:
            for i,item in enumerate(v):walk(item,path+'/'+str(i))
    walk(data);return texts


def public(fn):
    @wraps(fn)
    def checked(*args,**kwargs):
        try:
            with localcontext(Context(prec=128,Emax=999,Emin=-999)):return fn(*args,**kwargs)
        except (KeyError,TypeError,AttributeError,IndexError,OverflowError,RecursionError,DecimalException):raise ValueError('invalid_nested_or_numeric_actuary_input') from None
    return checked


for _name in (*FUNCTIONS,'input_units','selected_texts'):globals()[_name]=public(globals()[_name])

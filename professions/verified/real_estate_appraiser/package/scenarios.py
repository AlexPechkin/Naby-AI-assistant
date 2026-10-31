"""Pure assisted appraisal scenarios; source trust and user consent are host-owned."""
from copy import deepcopy
from datetime import date,timedelta
from calendar import monthrange
from decimal import Decimal,Context,localcontext,ROUND_HALF_UP
import re
D=Decimal
CTX=Context(prec=80,rounding=ROUND_HALF_UP)
CLAUSES=('object_rights','purpose_value_type','valuation_date','assumptions_limitations','appraiser_sro_insurance','fee_payment','deadline_delivery','standards','independence','responsibility')
INSPECTION_TOPICS=('structure','finish','utilities','alterations','environment','access')
REPORT_TOPICS=('assignment','standards','assumptions','object','market','approaches','reconciliation','value','appraiser','appendices')
APPROACH_IDS=('sales_comparison','income_approach','cost_approach')

def fail(code):raise ValueError(code)
def obj(v,n):
    if type(v) is not dict:fail(n+'_object_required')
    return v
def text(v,n,limit=10000):
    if type(v) is not str or not v.strip() or len(v)>limit or any(ord(x)<32 and x not in '\n\r\t' for x in v):fail(n+'_text_required')
    return v.strip()
def seq(v,n,minimum=0,maximum=200):
    if type(v) is not list or not minimum<=len(v)<=maximum:fail(n+'_list_required')
    return v
def day(v,n):
    if type(v) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',v):fail(n+'_iso_date')
    try:return date.fromisoformat(v)
    except ValueError:fail(n+'_invalid_date')
def number(v,n,minimum=D(0),maximum=D('1e20')):
    if type(v) not in (str,int,Decimal) or not re.fullmatch(r'-?(?:0|[1-9]\d{0,20})(?:\.\d{1,8})?',str(v)):fail(n+'_exact_decimal')
    x=D(v)
    if not minimum<=x<=maximum:fail(n+'_range')
    return x
def money(v):
    with localcontext(CTX):return str(v.quantize(D('.01')))
def flag(v,n):
    if v is not None and type(v) is not bool:fail(n+'_boolean_or_unknown')
    return v
def boolean(v,n):
    if type(v) is not bool:fail(n+'_boolean')
    return v
def refs(v,n,minimum=1):
    seq(v,n,minimum,200)
    for x in v:text(x,n,1000)
    if len(set(v))!=len(v):fail(n+'_duplicates')
    return deepcopy(v)
def rule(v,event):
    r=obj(v,'dated_rule');text(r.get('source_reference'),'rule_source',1000);text(r.get('edition'),'rule_edition',1000)
    start=day(r.get('effective_from'),'effective_from');end=day(r['effective_to'],'effective_to') if r.get('effective_to') is not None else None
    if start>event or (end is not None and (end<start or event>end)):fail('rule_not_effective_on_event_date')
    if r.get('published_at') and day(r['published_at'],'rule_published')>event:fail('rule_published_after_event')
    return deepcopy(r)
def _base(c):return day(obj(c,'data').get('as_of'),'as_of')
def _scope(v,asof):
    v=obj(v,'task_scope')
    if set(v)!={'object_id','rights','valuation_date','currency','purpose','value_type'}:fail('task_scope_exact_fields')
    text(v['object_id'],'object_id',1000);text(v['rights'],'rights',4000)
    if v['currency']!='RUB':fail('only_rub_scope_supported')
    text(v['purpose'],'task_purpose',4000)
    if v['value_type'] not in ('market','liquidation','cadastral'):fail('task_value_type')
    if day(v['valuation_date'],'valuation_date')>asof:fail('future_valuation_date')
    return deepcopy(v)
def _review(v,asof,name='review'):
    r=deepcopy(obj(v,name))
    if r.get('status') not in ('present','missing','unknown','not_applicable'):fail(name+'_status')
    text(r.get('analysis'),name+'_analysis',8000)
    r['evidence_refs']=refs(r.get('evidence_refs'),name+'_refs',0 if r['status'] in ('missing','unknown') else 1)
    if r.get('checked_at') is not None and day(r['checked_at'],'checked_at')>asof:fail('future_review')
    return r
def _identity(v):
    p=deepcopy(obj(v,'appraiser_identity'))
    for k in ('name','registration_id','sro_name','source_reference'):text(p.get(k),'appraiser_'+k,2000)
    return p
def _professional_documents(v,event):
    """Record actual evidence or its absence; no implied license/cover approval."""
    if v is None:v={'qualification':{'status':'missing'},'insurance':{'status':'missing'}}
    source=obj(v,'appraiser_documentation')
    if set(source)!={'qualification','insurance'}:fail('qualification_and_insurance_documentation_required')
    result={};gaps=[]
    for kind in ('qualification','insurance'):
        row=deepcopy(obj(source[kind],kind+'_documentation'));status=row.get('status')
        if status not in ('provided','missing','unknown'):fail(kind+'_documentation_status')
        if status!='provided':
            if any(row.get(k) is not None for k in ('number','amount_rub','valid_from','valid_until','source_reference')):fail('missing_professional_document_has_claimed_details')
            gaps.append(kind+'_'+status);result[kind]={'status':status};continue
        for k in ('number','source_reference'):text(row.get(k),kind+'_'+k,2000)
        start=day(row.get('valid_from'),kind+'_valid_from');end=day(row.get('valid_until'),kind+'_valid_until');inclusive=boolean(row.get('end_inclusive'),kind+'_end_inclusive')
        if end<start:fail(kind+'_coverage_date_range')
        if event<start:gaps.append(kind+'_not_yet_effective_on_relevant_date')
        if event>end or (event==end and not inclusive):gaps.append(kind+'_expired_on_relevant_date')
        if kind=='qualification':
            text(row.get('direction'),'qualification_direction',2000)
            issued=day(row.get('issued_on'),'qualification_issued_on')
            if issued>start or issued>event:fail('qualification_issue_date_range')
        else:
            number(row.get('amount_rub'),'insurance_document_amount_rub')
            if row.get('holder_type') not in ('individual','company'):fail('insurance_document_holder_type')
        result[kind]=row
    return result,gaps
def _attachment(v,asof):
    r=deepcopy(obj(v,'attachment'));text(r.get('title'),'attachment_title',4000)
    if r.get('status') not in ('included','missing','not_applicable'):fail('attachment_status')
    text(r.get('rationale'),'attachment_rationale',4000)
    if r['status']=='included':text(r.get('source_reference'),'attachment_reference',1000)
    elif r.get('source_reference') is not None:fail('unavailable_attachment_reference')
    if r.get('date') is not None and day(r['date'],'attachment_date')>asof:fail('future_attachment')
    return r

def assignment(c):
    asof=_base(c);scope=_scope(c.get('task_scope'),asof)
    purpose=text(c.get('purpose'),'purpose',4000);value_type=c.get('value_type')
    if value_type not in ('market','liquidation','cadastral'):fail('supported_value_type_required')
    if purpose!=scope['purpose'] or value_type!=scope['value_type']:fail('assignment_scope_purpose_value_type_mismatch')
    client=deepcopy(obj(c.get('client'),'client'))
    for k in ('name','capacity','source_reference'):text(client.get(k),'client_'+k,3000)
    appraiser=_identity(c.get('appraiser'));documentation,doc_gaps=_professional_documents(c.get('appraiser_documentation'),asof)
    assumptions=[text(x,'assumption',4000) for x in seq(c.get('assumptions'),'assumptions')]
    limitations=[text(x,'limitation',4000) for x in seq(c.get('limitations'),'limitations')]
    fee=deepcopy(obj(c.get('fee_terms'),'fee_terms'));number(fee.get('amount_rub'),'fee_amount')
    for k in ('payment_terms','source_reference'):text(fee.get(k),'fee_'+k,4000)
    contingent=flag(fee.get('depends_on_value'),'fee_depends_on_value')
    delivery=deepcopy(obj(c.get('delivery'),'delivery'));day(delivery.get('due_date'),'delivery_due_date');text(delivery.get('format'),'delivery_format',1000)
    independent=obj(c.get('independence'),'independence');states={k:flag(independent.get(k),k) for k in ('related_to_client','financial_interest','related_to_object')}
    refs(independent.get('evidence_refs'),'independence_refs',0 if None in states.values() else 1)
    conflicts=[k for k,v in states.items() if v is True];unknown=[k for k,v in states.items() if v is None]
    if contingent is True:conflicts.append('fee_depends_on_value')
    if contingent is None:unknown.append('fee_depends_on_value')
    contract=c.get('contract_text');clauses=[]
    if contract is not None:text(contract,'contract_text',200000)
    supplied=obj(c.get('clauses'),'clauses')
    if set(supplied)!=set(CLAUSES):fail('all_assignment_clauses_required')
    for k in CLAUSES:
        row=_review(supplied[k],asof,'clause');row['topic']=k
        text(row.get('draft_text'),'draft_clause_text',12000)
        if row['status']=='present':
            quote=text(row.get('quote'),'clause_quote',10000)
            if contract is None or quote not in contract:fail('clause_quote_not_in_selected_contract')
        elif row.get('quote') is not None:fail('absent_clause_has_quote')
        if row['status']=='not_applicable':fail('required_assignment_clause_cannot_be_waived')
        clauses.append(row)
    standards=[rule(x,asof) for x in seq(c.get('standards'),'standards',1,30)]
    missing=[r['topic'] for r in clauses if r['status']!='present']
    return dict(object=scope['object_id'],rights=scope['rights'],purpose=purpose,value_type=value_type,valuation_date=scope['valuation_date'],task_scope=scope,
      client=client,appraiser=appraiser,appraiser_documentation=documentation,documentation_gaps=doc_gaps,assumptions=assumptions,limitations=limitations,fee_terms=fee,price_terms=fee,delivery=delivery,standards=standards,
      clause_checks=clauses,missing_contract_terms=missing,independence=deepcopy(independent),independence_issues=conflicts,unresolved_independence=unknown,
      task_ready_for_review=not conflicts and not unknown and not missing and not doc_gaps,calculation_allowed=False,assignment_approval_established=False,
      draft_only=True,next_action='host_owned_task_review_and_agreement_required',as_of=asof.isoformat())

def object_docs(c):
    asof=_base(c);cad=text(c.get('cadastral_number'),'cadastral_number',100);object_id=text(c.get('object_id'),'object_id',1000)
    if not re.fullmatch(r'\d{2}:\d{2}:\d{4,9}:\d{1,12}',cad):fail('cadastral_number_format')
    egrn=deepcopy(obj(c.get('egrn'),'egrn'));status=egrn.get('status');gaps=[]
    if status not in ('provided','missing'):fail('egrn_status')
    if status=='provided':
        for k in ('document_number','source_reference','rights','encumbrances','cadastral_number'):text(egrn.get(k),'egrn_'+k,4000)
        if day(egrn.get('issued_on'),'egrn_issued_on')>asof:fail('future_egrn')
        earea=number(egrn.get('area_m2'),'egrn_area',D('.00000001'))
    else:earea=None;gaps.append('egrn_not_provided')
    technical=deepcopy(obj(c.get('technical'),'technical'))
    for k in ('document','building_type','source_reference','object_id'):text(technical.get(k),'technical_'+k,4000)
    if day(technical.get('date'),'technical_date')>asof:fail('future_technical_document')
    property_type=c.get('property_type')
    if property_type not in ('premises','building','land'):fail('property_type_required')
    year=technical.get('year_built')
    if property_type!='land':
        if year is None:gaps.append('construction_year_not_provided')
        elif type(year) is not str or not re.fullmatch(r'\d{4}',year) or not 1<=int(year)<=asof.year:fail('construction_year')
    land_use=deepcopy(c.get('land_use'))
    if property_type=='land':
        if land_use is None:gaps.append('land_category_and_permitted_use_not_provided')
        else:
            obj(land_use,'land_use')
            for k in ('category','permitted_use','source_reference'):text(land_use.get(k),'land_'+k,4000)
    elif land_use is not None:fail('land_use_requires_land_object')
    tarea=None if technical.get('area_m2') is None else number(technical['area_m2'],'technical_area',D('.00000001'))
    inspection=deepcopy(obj(c.get('inspection'),'inspection'))
    text(inspection.get('object_id'),'inspection_object_id',1000)
    if inspection.get('status') not in ('performed','partial','not_performed'):fail('inspection_status')
    if inspection['status']=='not_performed':
        if inspection.get('date') is not None or inspection.get('area_m2') is not None:fail('unperformed_inspection_has_observations')
        if seq(inspection.get('rooms'),'inspection_rooms',0,200):fail('unperformed_inspection_has_rooms')
        iarea=None;gaps.append('physical_inspection_not_performed')
    else:
        if day(inspection.get('date'),'inspection_date')>asof:fail('future_inspection')
        text(inspection.get('participants'),'inspection_participants',4000);refs(inspection.get('evidence_refs'),'inspection_refs')
        for room in seq(inspection.get('rooms'),'inspection_rooms',1,200):text(room,'inspected_room',4000)
        iarea=None if inspection.get('area_m2') is None else number(inspection['area_m2'],'inspection_area',D('.00000001'))
    topics=obj(inspection.get('checklist'),'inspection_checklist')
    if set(topics)!=set(INSPECTION_TOPICS):fail('all_inspection_topics_required')
    for k,r in topics.items():
        obj(r,'inspection_topic')
        if r.get('status') not in ('observed','unobserved','not_applicable'):fail('inspection_topic_status')
        text(r.get('notes'),'inspection_notes',6000);refs(r.get('evidence_refs'),'inspection_topic_refs',0 if r['status']=='unobserved' else 1)
        if inspection['status']=='not_performed' and r['status']=='observed':fail('unperformed_inspection_has_observed_topic')
        if r['status']=='unobserved':gaps.append('inspection_'+k)
    tolerance=number(c.get('area_tolerance_m2'),'area_tolerance_m2',D(0),D(100));discrepancies=[];areas={'egrn':earea,'technical':tarea,'inspection':iarea}
    for source,identity,expected in [('egrn',egrn.get('cadastral_number') if status=='provided' else None,cad),('technical',technical['object_id'],object_id),('inspection',inspection['object_id'],object_id)]:
        if identity is not None and identity!=expected:discrepancies.append(dict(field='object_identity',source=source,expected=expected,observed=identity))
    with localcontext(CTX):
        for left,right in (('egrn','technical'),('egrn','inspection'),('technical','inspection')):
            if areas[left] is not None and areas[right] is not None and abs(areas[left]-areas[right])>tolerance:
                discrepancies.append(dict(field='area_m2',left=left,right=right,left_value=str(areas[left]),right_value=str(areas[right]),difference=str(areas[right]-areas[left])))
    photos=[];seen=set()
    for p in seq(c.get('photos'),'photos',0,200):
        p=deepcopy(obj(p,'photo'));identity=text(p.get('id'),'photo_id',200)
        if identity in seen:fail('duplicate_photo_id')
        seen.add(identity)
        if type(p.get('sha256')) is not str or not re.fullmatch('[0-9a-f]{64}',p['sha256']):fail('photo_sha256')
        for k in ('caption','source_reference'):text(p.get(k),'photo_'+k,4000)
        if day(p.get('date'),'photo_date')>asof:fail('future_photo')
        photos.append(p)
    if not photos:gaps.append('photo_evidence_not_provided')
    return dict(cadastral_number=cad,address=text(c.get('address'),'address',4000),object_id=object_id,property_type=property_type,land_use=land_use,
      rights=egrn.get('rights') if status=='provided' else None,encumbrances=egrn.get('encumbrances') if status=='provided' else None,egrn=egrn,egrn_area=None if earea is None else str(earea),
      technical=technical,inspection=inspection,area_tolerance_m2=str(tolerance),discrepancies=discrepancies,photos=photos,missing_evidence=gaps,
      rights_from_map_not_accepted=True,rights_authenticity_verified=False,physical_inspection_performed_by_tool=False,
      photo_metadata_only=True,photo_bytes_verified=False,as_of=asof.isoformat())

def _reconcile(rows,mode):
    seq(rows,'approaches',1,3);prepared=[];seen=set();weighted=D(0);total=D(0)
    with localcontext(CTX):
        for r in rows:
            r=deepcopy(obj(r,'approach'));identity=r.get('id')
            if identity not in APPROACH_IDS or identity in seen:fail('unique_supported_approaches_required')
            seen.add(identity);value=number(r.get('value'),'approach_value',D('.00000001'));weight=number(r.get('weight'),'approach_weight',D(0),D(1))
            refs(r.get('evidence_refs'),'approach_refs');text(r.get('rationale'),'approach_rationale',8000)
            weighted+=value*weight;total+=weight;r.update(value=str(value),weight=str(weight));prepared.append(r)
        if mode!='explicit_weights_sum_one' or total!=1:fail('explicit_weights_must_sum_one')
        return prepared,weighted

def valuation_report(c):
    asof=_base(c);scope=_scope(c.get('task_scope'),asof);valuation=day(scope['valuation_date'],'valuation_date');report_date=day(c.get('report_date'),'report_date')
    if not valuation<=report_date<=asof:fail('report_date_range')
    task=deepcopy(obj(c.get('assignment'),'assignment'))
    for k in ('source_reference','purpose','value_type'):text(task.get(k),'assignment_'+k,4000)
    if task['purpose']!=scope['purpose'] or task['value_type']!=scope['value_type']:fail('report_assignment_scope_mismatch')
    text(c.get('assignment_reference'),'assignment_reference',1000)
    description=text(c.get('object'),'object',30000);market=text(c.get('market'),'market',40000)
    assumptions=[text(x,'report_assumption',8000) for x in seq(c.get('assumptions'),'assumptions')];limitations=[text(x,'report_limitation',8000) for x in seq(c.get('limitations'),'limitations')]
    standards=[rule(x,report_date) for x in seq(c.get('standards'),'standards',1,30)];applied=[];refusals=[];seen=set()
    for r in seq(c.get('approaches'),'approaches',3,3):
        r=deepcopy(obj(r,'report_approach'));identity=r.get('id')
        if identity not in APPROACH_IDS or identity in seen:fail('all_three_approaches_once')
        seen.add(identity)
        if r.get('status') not in ('applied','not_applied'):fail('approach_status')
        text(r.get('rationale'),'approach_rationale',10000);refs(r.get('evidence_refs'),'approach_refs')
        if r['status']=='applied':
            if r.get('valuation_date')!=scope['valuation_date'] or r.get('currency')!='RUB' or r.get('object_id')!=scope['object_id']:fail('approach_scope_mismatch')
            if _scope(r.get('task_scope'),asof)!=scope:fail('approach_task_scope_mismatch')
            if any(key in r and r[key]!=scope[key] for key in ('rights','purpose','value_type')):fail('approach_explicit_scope_conflict')
            text(r.get('calculation_reference'),'approach_calculation_reference',1000);calculation=obj(r.get('calculation_summary'),'calculation_summary')
            text(calculation.get('method'),'calculation_method',4000);text(calculation.get('explanation'),'calculation_explanation',30000);applied.append(r)
        else:
            if any(r.get(k) is not None for k in ('value','weight','calculation_reference')):fail('refused_approach_has_result')
            refusals.append(r)
    prepared,value=_reconcile(applied,c.get('weight_mode'));appraiser=_identity(c.get('appraiser'));documentation,doc_gaps=_professional_documents(c.get('appraiser_documentation'),report_date);appendices=[_attachment(x,asof) for x in seq(c.get('appendices'),'appendices',1,100)]
    interval=None
    if c.get('value_range') is not None:
        r=obj(c['value_range'],'value_range');low=number(r.get('low'),'range_low');high=number(r.get('high'),'range_high')
        if not low<=value<=high:fail('value_range_excludes_reconciled_result')
        text(r.get('basis'),'value_range_basis',8000);refs(r.get('evidence_refs'),'range_refs');interval=dict(low=money(low),high=money(high),basis=r['basis'],evidence_refs=deepcopy(r['evidence_refs']))
    reconciliation=text(c.get('reconciliation_rationale'),'reconciliation_rationale',12000)
    return dict(task_scope=scope,assignment_reference=c['assignment_reference'],assignment=task,standards=standards,assumptions=assumptions,limitations=limitations,object=description,market=market,
      approaches=prepared,refusals=refusals,weight_mode=c['weight_mode'],reconciliation=reconciliation,final_value=money(value),reconciled_value_unrounded=str(value),range=interval,
      valuation_date=scope['valuation_date'],report_date=report_date.isoformat(),appraiser=appraiser,appraiser_documentation=documentation,documentation_gaps=doc_gaps,appendices=appendices,missing_appendices=[x['title'] for x in appendices if x['status']=='missing'],
      final_judgment_human_only=True,professional_report_signed=False,standards_compliance_verified=False,draft_only=True)

def _calendar(v):
    v=obj(v,'calendar');start=day(v.get('start'),'calendar_start');end=day(v.get('end'),'calendar_end');days=obj(v.get('days'),'calendar_days')
    if end<start or len(days)>40000:fail('calendar_range')
    refs(v.get('evidence_refs'),'calendar_refs')
    for k,x in days.items():
        if not start<=day(k,'calendar_day')<=end:fail('calendar_day_range')
        boolean(x,'calendar_working_day')
    return days
def _deadline(spec,asof):
    spec=deepcopy(obj(spec,'deadline'));event=day(spec.get('event_date'),'deadline_event')
    if event>asof:fail('future_deadline_event')
    text(spec.get('event_reference'),'deadline_event_reference',1000)
    # The historical valuation date starts the arithmetic period; the selected
    # procedure's governing edition is checked on its explicit application date.
    apply_on=day(spec.get('rule_apply_on'),'deadline_rule_apply_on')
    if not event<=apply_on<=asof:fail('deadline_rule_application_date_range')
    rule(spec.get('rule'),apply_on);count=number(spec.get('period_count'),'deadline_period_count',D(0),D(10000))
    if count!=count.to_integral_value():fail('deadline_period_integer')
    unit=spec.get('period_unit');include=boolean(spec.get('include_event_day'),'include_event_day');roll=spec.get('roll_forward')
    if roll not in ('none','next_working'):fail('roll_forward_policy')
    cal=_calendar(spec.get('calendar')) if unit=='working_days' or roll=='next_working' else None
    def working(d):
        if d.isoformat() not in cal:fail('calendar_day_missing')
        return cal[d.isoformat()]
    try:
        if unit in ('calendar_months','calendar_years'):
            if include:fail('monthly_period_cannot_include_event_day')
            policy=spec.get('month_end_policy')
            if policy not in ('last_day','reject'):fail('month_end_policy_required')
            months=int(count)*(12 if unit=='calendar_years' else 1)
            monthindex=event.year*12+event.month-1+months;year,month=divmod(monthindex,12);month+=1
            if not 1<=year<=9999:fail('deadline_year_range')
            last=monthrange(year,month)[1]
            if event.day>last and policy=='reject':fail('deadline_target_day_missing')
            result=date(year,month,min(event.day,last))
        elif unit in ('calendar_days','working_days'):
            if spec.get('month_end_policy')!='not_applicable':fail('day_period_month_policy')
            result=event;seen=0
            if count:
                result=event if include else event+timedelta(days=1)
                for _ in range(40000):
                    if unit=='calendar_days' or working(result):seen+=1
                    if seen==int(count):break
                    result+=timedelta(days=1)
                else:fail('deadline_horizon')
        else:fail('deadline_period_unit')
        if roll=='next_working':
            for _ in range(40000):
                if working(result):break
                result+=timedelta(days=1)
            else:fail('deadline_roll_horizon')
    except OverflowError:fail('deadline_overflow')
    spec.update(calculated_deadline=result.isoformat(),expired_as_of=asof>result);return spec

def _existing_report(v,asof,object_id=None,cadastral_number=None):
    """Selected existing report, not a newly generated valuation hidden in another tool."""
    r=deepcopy(obj(v,'existing_report'))
    for k in ('number','source_reference','appraiser','object_id','cadastral_number','rights','purpose'):text(r.get(k),'existing_report_'+k,4000)
    if r.get('value_type')!='market':fail('existing_market_report_required')
    if object_id is not None and r['object_id']!=object_id:fail('existing_report_object_mismatch')
    if cadastral_number is not None and r['cadastral_number']!=cadastral_number:fail('existing_report_cadastral_mismatch')
    valuation=day(r.get('valuation_date'),'existing_valuation_date');issued=day(r.get('report_date'),'existing_report_date')
    if not valuation<=issued<=asof:fail('existing_report_date_range')
    number(r.get('market_value'),'existing_market_value',D('.00000001'))
    if r.get('currency')!='RUB':fail('existing_report_currency')
    sections=obj(r.get('sections'),'existing_report_sections')
    if set(sections)!=set(REPORT_TOPICS):fail('all_existing_report_sections_required')
    for key,part in sections.items():
        obj(part,'existing_report_section');text(part.get('text'),'report_section_text',80000);refs(part.get('evidence_refs'),'report_section_refs')
    documentation,gaps=_professional_documents(r.get('appraiser_documentation'),issued)
    r['appraiser_documentation']=documentation;r['documentation_gaps']=gaps
    return r

def cadastral_dispute(c):
    asof=_base(c);mode=c.get('mode')
    if mode not in ('market_value','error_correction','judicial_review'):fail('cadastral_mode')
    applicant=deepcopy(obj(c.get('applicant'),'applicant'))
    for k in ('name','capacity','basis','source_reference'):text(applicant.get(k),'applicant_'+k,4000)
    route=deepcopy(obj(c.get('route'),'route'))
    for k in ('region','body','procedure'):text(route.get(k),'route_'+k,4000)
    application=day(c.get('application_date'),'application_date')
    if application>asof:fail('future_application_date_not_current_case')
    route['rule']=rule(route.get('rule'),application)
    if route['rule'].get('procedure')!=mode:fail('cadastral_route_rule_mismatch')
    ownership=deepcopy(obj(c.get('owner_consent'),'owner_consent'))
    if ownership.get('status') not in ('provided','missing','unknown','not_required_under_supplied_rule'):fail('owner_consent_status')
    text(ownership.get('basis'),'owner_consent_basis',4000);refs(ownership.get('evidence_refs'),'owner_consent_refs',0 if ownership['status'] in ('missing','unknown') else 1)
    cad=text(c.get('cadastral_number'),'cadastral_number',100);current=number(c.get('cadastral_value'),'cadastral_value',D('.00000001'));determined=day(c.get('cadastral_determined_on'),'cadastral_determined_on')
    if not re.fullmatch(r'\d{2}:\d{2}:\d{4,9}:\d{1,12}',cad):fail('cadastral_number_format')
    if determined>application:fail('cadastral_value_determined_after_application')
    report=None;market=ratio=None;errors=[]
    if mode!='error_correction':
        report=_existing_report(c.get('report'),asof,cadastral_number=cad)
        if day(report['report_date'],'report_date')>application:fail('report_after_application_date')
        market=number(report['market_value'],'market_value',D('.00000001'))
        with localcontext(CTX):ratio=str(market/current)
    elif c.get('report') is not None:fail('error_correction_does_not_require_fabricated_appraisal')
    if mode=='error_correction':
        for item in seq(c.get('errors'),'registry_errors',1,100):
            item=deepcopy(obj(item,'registry_error'))
            for k in ('field','recorded','proposed','reason'):text(item.get(k),'error_'+k,6000)
            if item['recorded']==item['proposed']:fail('registry_error_no_change')
            refs(item.get('evidence_refs'),'registry_error_refs');errors.append(item)
    decision=None
    if mode=='judicial_review':
        decision=deepcopy(obj(c.get('challenged_decision'),'challenged_decision'))
        for k in ('number','issuer','source_reference'):text(decision.get(k),'decision_'+k,4000)
        if day(decision.get('date'),'decision_date')>application:fail('challenged_decision_after_application')
    deadline=_deadline(c.get('deadline'),asof) if c.get('deadline') is not None else None
    if mode=='market_value':
        if deadline is None:fail('market_value_application_deadline_required')
        if deadline.get('start_basis') not in ('valuation_date','tax_notice','other_sourced_event'):fail('deadline_start_basis_required')
        if deadline['start_basis']=='valuation_date' and deadline['event_date']!=report['valuation_date']:fail('market_value_deadline_event_must_match_valuation_date')
        if deadline['start_basis']!='valuation_date':text(deadline.get('event_description'),'alternative_deadline_event_description',8000)
    if deadline is not None and deadline['rule_apply_on']!=c['application_date']:fail('deadline_rule_application_date_mismatch')
    attachments=[_attachment(x,asof) for x in seq(c.get('attachments'),'attachments',1,100)]
    return dict(mode=mode,applicant=applicant,cadastral_number=cad,cadastral_value=money(current),cadastral_determined_on=determined.isoformat(),market_value=None if market is None else money(market),ratio=ratio,
      report=report,valuation_report=report,report_reference=None if report is None else report['source_reference'],requirement=text(c.get('requirement'),'requirement',12000),route=route,owner_consent=ownership,
      registry_errors=errors,challenged_decision=decision,application_date=application.isoformat(),deadline=deadline,within_supplied_deadline=None if deadline is None else application<=day(deadline['calculated_deadline'],'deadline'),
      attachments=attachments,missing_attachments=[x['title'] for x in attachments if x['status']=='missing'],tax_effect='requires_separate_current_rule_and_period_check',submission_human_only=True,submission_performed=False,legal_entitlement_verified=False)

def mortgage_pledge(c):
    asof=_base(c);scope=_scope(c.get('task_scope'),asof);mode=c.get('mode')
    if mode not in ('preparation','existing_report'):fail('mortgage_mode')
    bank=text(c.get('bank'),'bank',4000);purpose=text(c.get('purpose'),'mortgage_purpose',4000);policy=rule(c.get('bank_policy'),asof);fso9=rule(c.get('fso9_rule'),asof)
    requirements=[]
    for item in seq(c.get('bank_requirements'),'bank_requirements',1,100):
        item=_review(item,asof,'bank_requirement');text(item.get('requirement'),'bank_requirement',6000);requirements.append(item)
    card=object_docs(obj(c.get('object_card'),'object_card'))
    if card['object_id']!=scope['object_id'] or card['as_of']!=c['as_of']:fail('mortgage_object_card_scope_mismatch')
    liquidity=deepcopy(obj(c.get('liquidity'),'liquidity'))
    for k in ('classification','analysis'):text(liquidity.get(k),'liquidity_'+k,10000)
    refs(liquidity.get('evidence_refs'),'liquidity_refs');exposure=number(c.get('exposure_months'),'exposure_months',D('.00000001'),D(1200));report=None;market=None
    if mode=='existing_report':
        report=_existing_report(c.get('report'),asof,scope['object_id'])
        if report['valuation_date']!=scope['valuation_date'] or report['rights']!=scope['rights'] or report['value_type']!=scope['value_type']:fail('mortgage_report_scope_mismatch')
        market=money(number(report['market_value'],'market_value'))
    elif c.get('report') is not None:fail('preparation_does_not_claim_completed_valuation')
    pledge=c.get('pledge_value_rub');pledge_source=None
    if pledge is not None:
        pledge=number(pledge,'pledge_value_rub',D('.00000001'));pledge_source=rule(c.get('pledge_policy'),asof);text(c.get('pledge_basis'),'pledge_basis',8000)
        if mode!='existing_report':fail('pledge_value_requires_selected_report')
    return dict(mode=mode,task_scope=scope,bank=bank,purpose=purpose,bank_policy=policy,fso9_basis=fso9,bank_requirements_to_verify=requirements,
      unresolved_bank_requirements=[r['requirement'] for r in requirements if r['status']!='present'],object_card=card,valuation_report=report,market_value=market,pledge_value=None if pledge is None else money(pledge),
      pledge_policy=pledge_source,pledge_basis=c.get('pledge_basis') if pledge is not None else None,pledge_value_is_bank_supplied_not_automatic_discount=True,
      exposure_months=str(exposure),liquidity=liquidity,report_purpose_matches_task=None if report is None else report['purpose']==scope['purpose'],
      credit_decision_not_made=True,bank_acceptance_verified=False,personal_data_local_only=True,draft_only=True)

def report_review(c):
    asof=_base(c);report_date=day(c.get('report_date'),'reviewed_report_date')
    if report_date>asof:fail('reviewed_report_after_review_date')
    pages=[];seen=set();by_number={}
    for page in seq(c.get('report_pages'),'report_pages',1,1000):
        page=deepcopy(obj(page,'report_page'));nr=page.get('number')
        if type(nr) is not int or not 1<=nr<=10000 or nr in seen:fail('unique_page_number_required')
        seen.add(nr);text(page.get('text'),'page_text',100000);text(page.get('source_reference'),'page_source_reference',1000);pages.append(page);by_number[nr]=page['text']
    issue_list=[];ids=set()
    for issue in seq(c.get('issues'),'issues',0,200):
        issue=deepcopy(obj(issue,'issue'));identity=text(issue.get('id'),'issue_id',200)
        if identity in ids:fail('duplicate_issue_id')
        ids.add(identity);nr=issue.get('page')
        if type(nr) is not int or nr not in by_number:fail('issue_page_not_selected')
        if text(issue.get('excerpt'),'issue_excerpt',10000) not in by_number[nr]:fail('issue_quote_not_on_selected_page')
        for k in ('issue','impact'):text(issue.get(k),'issue_'+k,12000)
        if issue.get('rule_event') not in ('report_date','review_date'):fail('issue_rule_event_required')
        apply_on=report_date if issue['rule_event']=='report_date' else asof
        issue['rule']=rule(issue.get('rule'),apply_on);issue['rule_apply_on']=apply_on.isoformat()
        refs(issue.get('evidence_refs'),'issue_refs');issue_list.append(issue)
    checks=obj(c.get('section_checks'),'section_checks')
    if set(checks)!=set(REPORT_TOPICS):fail('all_report_sections_required')
    reviews={k:_review(v,asof,'report_section') for k,v in checks.items()};arithmetic=c.get('arithmetic');calc=None
    if arithmetic is not None:
        arithmetic=obj(arithmetic,'arithmetic');prepared,value=_reconcile(arithmetic.get('approaches'),arithmetic.get('weight_mode'));declared=number(arithmetic.get('declared_final_value'),'declared_final_value',D('.00000001'))
        with localcontext(CTX):difference=declared-value
        calc=dict(approaches=prepared,recalculated_value_unrounded=str(value),recalculated_final_value=money(value),declared_final_value=money(declared),arithmetic_difference=money(difference),difference_unrounded=str(difference))
    return dict(purpose=text(c.get('purpose'),'review_purpose',6000),report_identifier=text(c.get('report_identifier'),'report_identifier',1000),report_date=report_date.isoformat(),report_pages=pages,issues=issue_list,section_checks=reviews,
      unreviewed_sections=[k for k,r in reviews.items() if r['status'] in ('unknown','missing')],arithmetic=calc,recalculated_final_value=None if calc is None else calc['recalculated_final_value'],
      declared_final_value=None if calc is None else calc['declared_final_value'],arithmetic_difference=None if calc is None else calc['arithmetic_difference'],
      conclusion=text(c.get('conclusion'),'review_conclusion',16000),official_sro_expertise_not_claimed=True,report_compliance_verified=False,as_of=asof.isoformat())

STATUS_TOPICS=('qualification_exam','sro_admission','insurance','independence','report_archive')
def _status_roadmap(c,asof):
    mode=c['mode'];person=deepcopy(obj(c.get('appraiser'),'appraiser'))
    for k in ('name','source_reference'):text(person.get(k),'planning_appraiser_'+k,2000)
    goal=text(c.get('goal'),'status_goal',6000)
    direction=text(c.get('activity_direction'),'activity_direction',2000);steps=[];seen=set();unresolved=[]
    for item in seq(c.get('roadmap'),'status_roadmap',5,5):
        item=deepcopy(obj(item,'roadmap_step'));topic=item.get('topic')
        if topic not in STATUS_TOPICS or topic in seen:fail('all_status_roadmap_topics_once')
        seen.add(topic)
        if item.get('status') not in ('pending','done','unknown','not_required'):fail('roadmap_step_status')
        for k in ('action','responsible_party','provider','expected_result'):text(item.get(k),'roadmap_'+k,12000)
        item['documents']=[text(x,'roadmap_document',4000) for x in seq(item.get('documents'),'roadmap_documents',1,50)]
        refs(item.get('evidence_refs'),'roadmap_refs');item['rule']=rule(item.get('rule'),asof)
        due=item.get('due_date')
        if due is not None:day(due,'roadmap_due_date')
        if item['status']=='done':
            done=day(item.get('completed_on'),'roadmap_completed_on')
            if done>asof:fail('future_roadmap_completion')
            text(item.get('completion_reference'),'roadmap_completion_reference',1000)
        elif item.get('completed_on') is not None or item.get('completion_reference') is not None:fail('incomplete_roadmap_has_completion_claim')
        if item['status'] in ('pending','unknown'):unresolved.append(topic)
        steps.append(item)
    current=None
    if c.get('current_records') is not None:
        existing=deepcopy(obj(c['current_records'],'current_records'))
        if existing.get('mode','current_check')!='current_check' or existing.get('as_of')!=c['as_of'] or obj(existing.get('appraiser'),'current_appraiser').get('name')!=person['name']:fail('roadmap_current_record_scope')
        current=appraiser_status(existing)
    return dict(mode=mode,goal=goal,activity_direction=direction,appraiser=person,roadmap=steps,current_records=current,unresolved_steps=unresolved,
      reminders=[dict(topic=r['topic'],due_date=r['due_date'],status='proposed_for_existing_host_only') for r in steps if r.get('due_date')],
      declared_registry_record_date=None,review_due_from_declared_record=None,registry_refresh_suggested=True,actual_registry_check_verified=False,last_confirmed_registry_snapshot=None,
      professional_authority_verified=False,background_reminder_created=False,external_action_performed=False,draft_only=True,as_of=asof.isoformat())

def appraiser_status(c):
    asof=_base(c);mode=c.get('mode','current_check')
    if mode not in ('current_check','onboarding','renewal'):fail('appraiser_status_mode')
    if mode!='current_check':return _status_roadmap(c,asof)
    person=_identity(c.get('appraiser'));membership=deepcopy(obj(c.get('membership'),'membership'))
    if membership.get('status') not in ('active','suspended','terminated','unknown'):fail('membership_status')
    for k in ('sro_name','registration_id'):text(membership.get(k),'membership_'+k,2000)
    if day(membership.get('checked_at'),'membership_checked_at')>asof:fail('future_registry_check')
    refs(membership.get('evidence_refs'),'membership_refs',0 if membership['status']=='unknown' else 1);certificate=deepcopy(obj(c.get('certificate'),'certificate'))
    for k in ('number','direction','source_reference'):text(certificate.get(k),'certificate_'+k,2000)
    issued=day(certificate.get('issued_on'),'certificate_issued');start=day(certificate.get('valid_from'),'certificate_start');end=day(certificate.get('valid_until'),'certificate_end')
    if not issued<=start<=end or issued>asof:fail('certificate_date_range')
    inclusive=boolean(certificate.get('end_inclusive'),'certificate_end_inclusive');direction=rule(c.get('qualification_rule'),asof);expected=text(direction.get('required_direction'),'required_direction',1000)
    insurance=deepcopy(obj(c.get('insurance'),'insurance'))
    if insurance.get('holder_type') not in ('individual','company'):fail('insurance_holder_type')
    for k in ('number','source_reference'):text(insurance.get(k),'insurance_'+k,2000)
    amount=number(insurance.get('amount_rub'),'insurance_amount_rub');i_start=day(insurance.get('valid_from'),'insurance_start');i_end=day(insurance.get('valid_until'),'insurance_end')
    if i_end<i_start:fail('insurance_date_range')
    i_inclusive=boolean(insurance.get('end_inclusive'),'insurance_end_inclusive');requirement=deepcopy(obj(c.get('insurance_requirement'),'insurance_requirement'));minimum=number(requirement.get('minimum_rub'),'insurance_minimum_rub')
    requirement['rule']=rule(requirement.get('rule'),asof);holder=text(requirement.get('holder_type'),'required_insurance_holder',100)
    if holder not in ('individual','company'):fail('required_insurance_holder_type')
    independence=deepcopy(obj(c.get('independence'),'independence'))
    for k in ('related_to_client','financial_interest','related_to_object'):flag(independence.get(k),k)
    refs(independence.get('evidence_refs'),'independence_refs',0 if any(independence.get(k) is None for k in ('related_to_client','financial_interest','related_to_object')) else 1)
    archive=deepcopy(obj(c.get('archive'),'archive'))
    for k in ('location','index','retention_policy'):text(archive.get(k),'archive_'+k,6000)
    refs(archive.get('evidence_refs'),'archive_refs');issues=[]
    if membership['status']!='active':issues.append('membership_'+membership['status'])
    if membership['sro_name']!=person['sro_name'] or membership['registration_id']!=person['registration_id']:issues.append('membership_identity_mismatch')
    if certificate['direction']!=expected:issues.append('certificate_direction_mismatch')
    if asof<start:issues.append('certificate_not_yet_effective')
    if asof>end or (asof==end and not inclusive):issues.append('certificate_expired')
    if asof<i_start:issues.append('insurance_not_yet_effective')
    if asof>i_end or (asof==i_end and not i_inclusive):issues.append('insurance_expired')
    if amount<minimum:issues.append('insurance_below_supplied_minimum')
    if insurance['holder_type']!=holder:issues.append('insurance_holder_type_mismatch')
    issues.extend('independence_'+k for k in ('related_to_client','financial_interest','related_to_object') if independence.get(k) is True)
    unknown=[k for k in ('related_to_client','financial_interest','related_to_object') if independence.get(k) is None]
    checked=day(membership['checked_at'],'checked_at')
    try:next_review=checked+timedelta(days=7)
    except OverflowError:next_review=date.max
    declared_member=membership['status']=='active' and membership['sro_name']==person['sro_name'] and membership['registration_id']==person['registration_id']
    return dict(appraiser=person,membership=membership,sro_member=declared_member,sro_membership_is_declared_not_registry_validated=True,certificate=certificate,qualification_rule=direction,insurance=insurance,insurance_requirement=requirement,
      independence=independence,archive=archive,issues=issues,unresolved_independence=unknown,reminders=dict(certificate=end.isoformat(),insurance=i_end.isoformat()),
      declared_registry_record_date=checked.isoformat(),review_due_from_declared_record=next_review.isoformat(),registry_refresh_suggested=asof>=next_review or membership['status']=='unknown',
      actual_registry_check_verified=False,last_confirmed_registry_snapshot=None,registry_check_human_only=True,professional_authority_verified=False,as_of=asof.isoformat())

def input_units(function_id,c):
    obj(c,'data');units={}
    if function_id=='assignment':obj(c.get('fee_terms'),'fee_terms');units['/fee_terms/amount_rub']='RUB'
    elif function_id=='object_docs':
        units['/area_tolerance_m2']='m2'
        if obj(c.get('egrn'),'egrn').get('status')=='provided':units['/egrn/area_m2']='m2'
        for cat in ('technical','inspection'):
            if obj(c.get(cat),cat).get('area_m2') is not None:units['/'+cat+'/area_m2']='m2'
        if c['technical'].get('year_built') is not None:units['/technical/year_built']='calendar_year'
    elif function_id=='valuation_report':
        for i,r in enumerate(seq(c.get('approaches'),'approaches',3,3)):
            obj(r,'approach')
            if r.get('status')=='applied':
                units['/approaches/'+str(i)+'/value']={'unit':'RUB','effective_date':r.get('valuation_date')}
                units['/approaches/'+str(i)+'/weight']={'unit':'fraction','not_after':c.get('report_date')}
        if c.get('value_range') is not None:obj(c['value_range'],'value_range');units['/value_range/low']='RUB';units['/value_range/high']='RUB'
    elif function_id=='cadastral_dispute':
        units['/cadastral_value']={'unit':'RUB','effective_date':c.get('cadastral_determined_on')}
        if c.get('report') is not None:units['/report/market_value']={'unit':'RUB','effective_date':obj(c['report'],'report').get('valuation_date')}
        if c.get('deadline') is not None:
            unit=obj(c['deadline'],'deadline').get('period_unit');units['/deadline/period_count']='month' if unit=='calendar_months' else 'year' if unit=='calendar_years' else 'day'
    elif function_id=='mortgage_pledge':
        units['/exposure_months']='month'
        if c.get('pledge_value_rub') is not None:units['/pledge_value_rub']='RUB'
        for k,v in input_units('object_docs',obj(c.get('object_card'),'object_card')).items():units['/object_card'+k]=v
        if c.get('report') is not None:units['/report/market_value']={'unit':'RUB','effective_date':obj(c['report'],'report').get('valuation_date')}
    elif function_id=='report_review':
        if c.get('arithmetic') is not None:
            obj(c['arithmetic'],'arithmetic')
            units['/arithmetic/declared_final_value']={'unit':'RUB','not_after':c.get('report_date')}
            for i,r in enumerate(seq(c['arithmetic'].get('approaches'),'approaches',1,3)):
                obj(r,'approach');units['/arithmetic/approaches/'+str(i)+'/value']={'unit':'RUB','not_after':c.get('report_date')};units['/arithmetic/approaches/'+str(i)+'/weight']={'unit':'fraction','not_after':c.get('report_date')}
    elif function_id=='appraiser_status':
        mode=c.get('mode','current_check')
        if mode not in ('current_check','onboarding','renewal'):fail('appraiser_status_mode')
        if mode=='current_check':units={'/insurance/amount_rub':'RUB','/insurance_requirement/minimum_rub':'RUB'}
        elif c.get('current_records') is not None:
            existing=obj(c['current_records'],'current_records')
            if existing.get('mode','current_check')!='current_check':fail('roadmap_current_record_scope')
            for k,v in input_units('appraiser_status',existing).items():units['/current_records'+k]=v
    else:fail('unknown_scenario_function')
    if function_id in ('assignment','valuation_report') and c.get('appraiser_documentation') is not None:
        insurance=obj(obj(c['appraiser_documentation'],'appraiser_documentation').get('insurance'),'insurance_documentation')
        if insurance.get('status')=='provided':units['/appraiser_documentation/insurance/amount_rub']={'unit':'RUB','not_after':c.get('report_date',c['as_of'])}
    if function_id in ('cadastral_dispute','mortgage_pledge') and c.get('report') is not None:
        documentation=obj(c['report'],'report').get('appraiser_documentation')
        if documentation is not None and obj(obj(documentation,'appraiser_documentation').get('insurance'),'insurance_documentation').get('status')=='provided':
            units['/report/appraiser_documentation/insurance/amount_rub']={'unit':'RUB','not_after':c['report'].get('report_date')}
    return units

def selected_texts(function_id,c):
    obj(c,'data');result={}
    if function_id=='assignment' and c.get('contract_text') is not None:result['/contract_text']=c['contract_text']
    if function_id=='report_review':
        for i,p in enumerate(seq(c.get('report_pages'),'report_pages',1,1000)):result['/report_pages/'+str(i)+'/text']=obj(p,'page').get('text')
    if function_id in ('cadastral_dispute','mortgage_pledge') and c.get('report') is not None:
        for key,part in obj(obj(c['report'],'report').get('sections'),'sections').items():result['/report/sections/'+key+'/text']=obj(part,'section').get('text')
    return result

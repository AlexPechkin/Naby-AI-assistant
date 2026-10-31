"""Offline customs scenarios. Evidence binding is performed by the host facade."""
from copy import deepcopy
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal,Context,localcontext,ROUND_HALF_UP
from calendar import monthrange
import re
from .common import fail,text,mapping,boolean
D=Decimal
TOPICS=('licenses','encryption','conformity','sanitary','veterinary','phytosanitary','marking','national_restrictions','sanctions')
CLAUSES=('parties_law','subject_specifications','incoterms','price_currency_payment','documents_deadlines','force_majeure_sanctions')

def _list(v,name,minimum=0,maximum=100):
    if type(v) is not list or not minimum<=len(v)<=maximum:fail(name+'_list_required')
    return v

def _date(v,name):
    if type(v) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',v):fail(name+'_iso_date')
    try:return date.fromisoformat(v)
    except ValueError:fail(name+'_invalid_date')

def _n(v,name,minimum=D(0),maximum=D('1e18')):
    if type(v) not in (str,int,Decimal) or not re.fullmatch(r'-?(?:0|[1-9]\d{0,18})(?:\.\d{1,8})?',str(v)):fail(name+'_exact_decimal_required')
    n=D(v)
    if not minimum<=n<=maximum:fail(name+'_range')
    return n

def _money(v):
    with localcontext(Context(prec=60)) as ctx:
        ctx.prec=60;return str(v.quantize(D('.01'),rounding=ROUND_HALF_UP))

def _code(v,name,length=10):
    if type(v) is not str or not re.fullmatch(r'\d{'+str(length)+'}',v):fail(name+'_digits')
    return v

def _refs(v,name,minimum=1):
    _list(v,name,minimum,100)
    for item in v:text(item,name,1000)
    if len(set(v))!=len(v):fail(name+'_duplicates')
    return deepcopy(v)

def _tri(v,name):
    if v is not None and type(v) is not bool:fail(name+'_boolean_or_unknown')
    return v

def _rule(v,asof):
    r=mapping(v,'dated_rule');text(r.get('source_reference'),'rule_source',1000);text(r.get('edition'),'rule_edition',200)
    start=_date(r.get('effective_from'),'rule_effective_from');end=_date(r['effective_to'],'rule_effective_to') if r.get('effective_to') is not None else None
    if start>asof or (end is not None and (end<start or asof>end)):fail('rule_not_effective_on_analysis_date')
    if r.get('published_at') and _date(r['published_at'],'rule_published')>asof:fail('future_rule_publication')
    return deepcopy(r)

def _review(v,asof):
    r=deepcopy(mapping(v,'review'))
    if r.get('status') not in ('unknown','reviewed','not_applicable'):fail('review_status')
    text(r.get('rationale'),'review_rationale',4000)
    r['evidence_refs']=_refs(r.get('evidence_refs'),'review_refs',0 if r['status']=='unknown' else 1)
    if r['status']!='unknown' and _date(r.get('checked_at'),'checked_at')>asof:fail('future_review')
    r['semantic_applicability_verified']=False
    return r

def _documents(v,name,asof):
    docs=mapping(v,name);allowed=('invoice','packing_list','transport','specification','insurance') if name=='shipping_documents' else ('bank_registration','currency_operations','supporting_documents','repatriation')
    if set(docs)!=set(allowed):fail(name+'_categories_required')
    for key,row in docs.items():
        if row is None:continue
        mapping(row,'document')
        for f in ('number','issuer','description','source_reference'):text(row.get(f),'document_'+f,4000)
        if _date(row.get('date'),'document_date')>asof:fail('future_document')
    return deepcopy(docs)

def tnved_classification(c):
    asof=_date(c.get('as_of'),'as_of');rule=_rule(c.get('nomenclature'),asof);product=deepcopy(mapping(c.get('product'),'product'))
    for k in ('name','composition','purpose','principle','completeness'):text(product.get(k),'product_'+k,4000)
    _refs(product.get('evidence_refs'),'product_refs');out=[];seen=set()
    for candidate in _list(c.get('candidates'),'candidates',1,3):
        mapping(candidate,'classification_candidate')
        code=_code(candidate.get('code'),'tnved')
        if code in seen:fail('duplicate_candidate')
        seen.add(code);checks=[];rules=set()
        for entry in _list(candidate.get('rule_checks'),'opi_checks',6,6):
            mapping(entry,'opi_check')
            nr=entry.get('rule')
            if type(nr) is not int or nr not in range(1,7) or nr in rules:fail('six_unique_opi_rules_required')
            rules.add(nr);r=_review(entry,asof)
            if nr in (1,6) and r['status']=='not_applicable':fail('opi_1_and_6_must_be_considered')
            checks.append(r)
        out.append(dict(code=code,arguments=text(candidate.get('arguments'),'arguments',4000),impact=text(candidate.get('impact'),'impact',2000),opi=[r['rationale'] for r in sorted(checks,key=lambda x:x['rule'])],rule_checks=checks,evidence_refs=_refs(candidate.get('evidence_refs'),'candidate_refs'),status='proposal_pending_current_nomenclature_check'))
    return dict(candidates=out,official_checks=_refs(c.get('source_references'),'classification_sources'),product=product,nomenclature=rule,as_of=asof.isoformat(),missing_product_documents=[k for k in ('photo_reference','technical_description_reference') if not product.get(k)],final_classification=False,preliminary_decision_recommended=len(out)>1 or any(r['status']=='unknown' for x in out for r in x['rule_checks']),rule_applicability_verified=False)

def declaration(c):
    asof=_date(c.get('as_of'),'as_of')
    fields=('procedure','parties','tnved_code','description','origin_country');data={k:text(c.get(k),k,4000) for k in fields};_code(data['tnved_code'],'declaration_tnved')
    numbers={k:_n(c.get(k),k,D('0.00000001') if k!='payments' else D(0)) for k in ('customs_value_rub','payments','net_weight_kg')}
    docs=_refs(c.get('g44_documents'),'g44_documents');_refs(c.get('document_evidence_refs'),'document_evidence_refs')
    expected=mapping(c.get('source_expected'),'source_expected');refs=mapping(c.get('source_expected_refs'),'source_expected_refs');mismatches=[];compared=[]
    for key,source in expected.items():
        if key not in data and key not in numbers:fail('unexpected_reconciliation_field')
        _refs(refs.get(key),'reconciliation_refs');actual=numbers[key] if key in numbers else data[key]
        other=_n(source,'source_'+key,D(0)) if key in numbers else text(source,'source_'+key,4000);compared.append(key)
        if actual!=other:mismatches.append(dict(field=key,declaration=str(actual),source=str(other),evidence_refs=deepcopy(refs[key])))
    start_value=text(c.get('submitted_at'),'submitted_at',40)
    if len(start_value)==10:start_day=_date(start_value,'submitted_at');start=None
    else:
        try:start=datetime.fromisoformat(start_value)
        except ValueError:fail('submitted_at_timestamp')
        if start.tzinfo is None or start.utcoffset() is None:fail('submitted_at_timezone_required')
        start_day=start.date()
    if start_day>asof:fail('future_registration')
    rule=_rule(c.get('release_rule'),start_day)
    hours=_n(c.get('release_hours'),'release_hours',D('0.00000001'),D(100000))
    with localcontext(Context(prec=60)):micro=hours*D(3600000000)
    if micro!=micro.to_integral_value():fail('release_hours_precision')
    try:deadline=(start.astimezone(timezone.utc)+timedelta(microseconds=int(micro))).astimezone(start.tzinfo) if start else None
    except OverflowError:fail('release_deadline_range')
    if c.get('stage') not in ('before_release','after_release'):fail('adjustment_stage')
    correction=None
    if c.get('correction') is not None:
        src=mapping(c['correction'],'correction');stage=src.get('stage')
        if stage!=c['stage']:fail('correction_stage_mismatch')
        request_day=_date(src.get('requested_on'),'correction_requested_on')
        if not start_day<=request_day<=asof:fail('correction_request_date_range')
        correction_rule=_rule(src.get('rule'),request_day)
        number=text(src.get('declaration_number'),'declaration_number',100)
        changes=[];seen=set();proposed={**data,**{k:str(v) for k,v in numbers.items()}}
        for item in _list(src.get('changes'),'correction_changes',1,30):
            mapping(item,'correction_change');field=item.get('field')
            if type(field) is not str or field not in proposed or field in seen:fail('unique_supported_correction_field')
            seen.add(field);reason=text(item.get('reason'),'correction_reason',4000);refs=_refs(item.get('evidence_refs'),'correction_evidence_refs')
            if field in numbers:
                old=_n(item.get('old_value'),'correction_old_value');new=_n(item.get('new_value'),'correction_new_value',D(0) if field=='payments' else D('0.00000001'))
                if old!=numbers[field]:fail('correction_old_value_does_not_match_declaration')
                if old==new:fail('correction_has_no_semantic_change')
                with localcontext(Context(prec=60)):delta=str(new-old)
                row=dict(field=field,old_value=str(old),new_value=str(new),reason=reason,evidence_refs=refs,numeric=True,delta=delta,unit='kg' if field=='net_weight_kg' else 'RUB')
            else:
                old=text(item.get('old_value'),'correction_old_value',4000);new=text(item.get('new_value'),'correction_new_value',4000)
                if old!=data[field]:fail('correction_old_value_does_not_match_declaration')
                if old==new:fail('correction_has_no_semantic_change')
                if field=='tnved_code':_code(new,'corrected_tnved')
                row=dict(field=field,old_value=old,new_value=new,reason=reason,evidence_refs=refs,numeric=False)
            proposed[field]=row['new_value'];changes.append(row)
        impacts={'tnved_code':('tariff_and_non_tariff_measures','customs_payments'), 'origin_country':('origin_and_preferences','customs_payments'), 'customs_value_rub':('customs_payments','customs_value_documents'), 'net_weight_kg':('specific_duty_quantities','shipping_documents'), 'payments':('payment_reconciliation',), 'description':('classification_and_specification',), 'parties':('party_and_contract_documents',), 'procedure':('procedure_eligibility_and_payments',)}
        rechecks=sorted({item for field in seen for item in impacts.get(field,())})
        correction=dict(stage=stage,requested_on=request_day.isoformat(),declaration_number=number,rule=correction_rule,changes=changes,document_refs=_refs(src.get('document_refs'),'correction_document_refs'),proposed_fields=proposed,dependent_rechecks_required=rechecks,related_calculations_recomputed=False,preparatory_status='draft_requires_review',official_kdt=False,submission_performed=False,original_declaration_changed=False)
    return dict(**data,**{k:str(v) for k,v in numbers.items()},g44_documents=docs,shipping_documents=_documents(c.get('shipping_documents'),'shipping_documents',asof),mismatches=mismatches,compared_fields=compared,unverified_fields=sorted(set(fields+tuple(numbers))-set(compared)),release_deadline=deadline.isoformat() if deadline else None,release_rule=rule,registration_timestamp_required=start is None,release_period_is_user_supplied_not_current_legal_rule=True,adjustment_stage=c['stage'],correction=correction,submission_and_signature='human_only',submission_performed=False)

def non_tariff(c):
    asof=_date(c.get('as_of'),'as_of');_code(c.get('tnved_code'),'tnved')
    if c.get('direction') not in ('import','export'):fail('direction')
    for flag in ('encryption','animal_origin','plant_origin','marked_goods'):_tri(c.get(flag),flag)
    for key in ('purpose','dispatch_country','origin_country','end_recipient'):text(c.get(key),key,2000)
    inputs=mapping(c.get('checks'),'checks')
    if set(inputs)!=set(TOPICS):fail('all_non_tariff_topics_required')
    checklist=[]
    for topic in TOPICS:
        row=_review(inputs[topic],asof);row['topic']=topic;required=_tri(row.get('required'),'measure_required')
        if row['status']=='unknown' and required is not None:fail('unknown_measure_cannot_have_requirement_conclusion')
        if row['status']=='not_applicable' and required is not False:fail('not_applicable_requires_false')
        if row['status']=='reviewed' and required is None:fail('reviewed_measure_requires_explicit_requirement')
        if row['status']!='unknown':row['rule']=_rule(row.get('rule'),asof)
        row['requirement']=text(row.get('requirement'),'measure_requirement',2000);checklist.append(row)
    groups={'Нетарифные меры':('licenses','encryption'),'Технические регламенты ЕАЭС':('conformity',),'Санитарный, ветеринарный, фитоконтроль':('sanitary','veterinary','phytosanitary'),'Маркировка':('marking',),'Санкции и национальные запреты':('national_restrictions','sanctions')}
    return dict(blocks={k:[r for r in checklist if r['topic'] in v] for k,v in groups.items()},checklist=checklist,declared_features={k:c.get(k) for k in ('encryption','animal_origin','plant_origin','marked_goods')},unresolved=[r['topic'] for r in checklist if r['status']=='unknown'],date_verification_required=True,legality_conclusion=False,end_recipient=c['end_recipient'],as_of=asof.isoformat())

def origin(c):
    asof=_date(c.get('as_of'),'as_of');output=_code(c.get('output_code'),'output_code');country=text(c.get('manufacture_country'),'manufacture_country',100)
    currency=text(c.get('currency'),'origin_currency',3)
    if not re.fullmatch('[A-Z]{3}',currency):fail('currency_code')
    method=mapping(c.get('method'),'origin_method');rule=_rule(method.get('rule'),asof);text(method.get('agreement'),'selected_agreement',1000)
    if method.get('regime') not in ('preferential','nonpreferential') or method.get('combination') not in ('all','any'):fail('origin_regime_and_combination')
    full=_tri(c.get('full_production'),'full_production');direct=_tri(c.get('direct_shipment'),'direct_shipment')
    material_rows=[];nonorigin=D(0);total=D(0);unknown=False
    for m in _list(c.get('materials'),'materials',0,200):
        row=deepcopy(mapping(m,'material'));_code(row.get('code'),'material_code');text(row.get('country'),'material_country',100)
        status=_tri(row.get('originating'),'material_originating');value=_n(row.get('value'),'material_value')
        row['evidence_refs']=_refs(row.get('evidence_refs'),'material_refs')
        if status is None:unknown=True
        row['value']=str(value);material_rows.append(row)
    checks=[];seen=set();heading=None;value_calc=None
    with localcontext(Context(prec=60)) as ctx:
        ctx.prec=60
        total=sum((D(m['value']) for m in material_rows),D(0))
        nonorigin=sum((D(m['value']) for m in material_rows if m['originating'] is False),D(0))
        for criterion in _list(method.get('criteria'),'origin_criteria',1,4):
            mapping(criterion,'origin_criterion')
            kind=criterion.get('kind')
            if kind in seen or kind not in ('wholly_obtained','tariff_shift','value_content','processing'):fail('unique_supported_origin_criterion')
            seen.add(kind);_refs(criterion.get('evidence_refs'),'criterion_refs');result=None;detail={}
            if kind=='wholly_obtained':
                result=full
                if full is True and any(m['originating'] is False for m in material_rows):fail('wholly_obtained_conflicts_with_nonorigin_material')
            elif kind=='tariff_shift':
                digits=criterion.get('digits')
                if type(digits) is not int or digits not in (2,4,6):fail('tariff_shift_level')
                non=[m for m in material_rows if m['originating'] is False]
                result=None if unknown or not material_rows else all(m['code'][:digits]!=output[:digits] for m in non)
                detail={'digits':digits,'unchanged_nonorigin_codes':[m['code'] for m in non if m['code'][:digits]==output[:digits]]}
                if digits==4:heading=result
            elif kind=='value_content':
                denominator=_n(criterion.get('denominator_value'),'origin_denominator',D('0.00000001'))
                if criterion.get('denominator_basis') not in ('ex_works','fob','transaction_value','net_cost'):fail('origin_denominator_basis')
                threshold=_n(criterion.get('threshold_percent'),'origin_threshold',D(0),D(100))
                if criterion.get('formula') not in ('regional_content','nonorigin_max'):fail('origin_value_formula')
                if nonorigin>denominator:fail('nonorigin_exceeds_declared_valuation_base')
                percent=(denominator-nonorigin)/denominator*100 if criterion['formula']=='regional_content' else nonorigin/denominator*100
                result=None if unknown or not material_rows else (percent>=threshold if criterion['formula']=='regional_content' else percent<=threshold)
                detail={'formula':criterion['formula'],'denominator_basis':criterion['denominator_basis'],'denominator_value':str(denominator),'threshold_percent':str(threshold),'percent':None if result is None else str(percent),'nonorigin_value':None if unknown else str(nonorigin)};value_calc=detail
            else:
                operations=_list(criterion.get('operations'),'processing_operations',1,100);values=[]
                for op in operations:
                    mapping(op,'processing_operation')
                    text(op.get('operation'),'operation',2000);_refs(op.get('evidence_refs'),'operation_refs');values.append(_tri(op.get('performed'),'operation_performed'))
                result=False if False in values else None if None in values else True;detail={'operations':deepcopy(operations)}
            checks.append(dict(kind=kind,met=result,evidence_refs=deepcopy(criterion['evidence_refs']),details=detail))
    vals=[r['met'] for r in checks]
    sufficient=(False if False in vals else None if None in vals else True) if method['combination']=='all' else (True if True in vals else None if None in vals else False)
    certificate=deepcopy(mapping(c.get('certificate'),'certificate'))
    if certificate.get('status') not in ('supplied','missing'):fail('certificate_status')
    if certificate['status']=='supplied':
        for key in ('number','issuer','exporter'):text(certificate.get(key),'certificate_'+key,1000)
        if _date(certificate.get('date'),'certificate_date')>asof:fail('future_certificate')
        _refs(certificate.get('evidence_refs'),'certificate_refs')
    preference=mapping(c.get('preference_conditions'),'preference_conditions');required={'country_eligible','goods_eligible','direct_shipment_required','document_required','other_conditions_met'}
    if not required<=set(preference):fail('all_preference_conditions_required')
    for k in required:_tri(preference[k],k)
    _refs(preference.get('evidence_refs'),'preference_refs',0 if any(preference[k] is None for k in required) else 1)
    pvals=[sufficient,preference['country_eligible'],preference['goods_eligible'],preference['other_conditions_met']]
    pvals.append(direct if preference['direct_shipment_required'] is True else None if preference['direct_shipment_required'] is None else True)
    pvals.append(certificate['status']=='supplied' if preference['document_required'] is True else None if preference['document_required'] is None else True)
    eligible=False if method['regime']=='nonpreferential' or False in pvals else None if None in pvals else True
    return dict(manufacture_country=country,currency=currency,criterion=method['combination'],method=deepcopy(method),rule=rule,criteria_results=checks,heading_changed=heading,sufficient_processing=sufficient,direct_shipment=direct,non_origin_value=None if unknown else _money(nonorigin),total_material_value=_money(total),materials=material_rows,value_content=value_calc,certificate=certificate,preference_conditions=deepcopy(preference),preference_eligible_preliminary=eligible,official_lists_verification_required=True,rule_applicability_verified=False,final_origin_determination=False)

def trade_contract(c):
    asof=_date(c.get('as_of'),'as_of');contract=text(c.get('contract_text'),'contract_text',200000)
    if c.get('direction') not in ('import','export'):fail('direction')
    checklist=[];supplied=mapping(c.get('clauses'),'contract_clauses')
    if set(supplied)!=set(CLAUSES):fail('all_contract_clauses_required')
    for topic in CLAUSES:
        item=_review(supplied[topic],asof);item['topic']=topic
        if item['status']=='not_applicable':fail('essential_clause_cannot_be_auto_exempt')
        quote=item.get('quote')
        if item['status']=='reviewed':
            text(quote,'clause_quote',10000)
            if quote not in contract:fail('clause_quote_not_in_contract')
            text(item.get('analysis'),'clause_analysis',4000)
        elif quote is not None:fail('unknown_clause_quote_must_be_null')
        checklist.append(item)
    amount=_n(c.get('amount'),'contract_amount');fx=_n(c.get('fx_rate'),'fx_rate',D('0.00000001'));currency=text(c.get('currency'),'currency',3)
    if not re.fullmatch('[A-Z]{3}',currency):fail('currency_code')
    if currency=='RUB' and fx!=1:fail('rub_fx_identity_required')
    fxdate=_date(c.get('fx_date'),'fx_date')
    if fxdate>asof:fail('future_fx_rate')
    _refs(c.get('fx_evidence_refs'),'fx_refs');registration=c.get('bank_rule');threshold=None;required=None;rule=None
    with localcontext(Context(prec=60)) as ctx:
        ctx.prec=60;rub=amount*fx
        if registration is not None:
            rule=_rule(registration,asof)
            if rule.get('direction')!=c['direction']:fail('bank_rule_direction_mismatch')
            threshold=_n(rule.get('threshold_rub'),'bank_threshold',D('0.00000001'))
            if rule.get('comparator') not in ('>=','>'):fail('bank_threshold_comparator')
            if _date(rule.get('valuation_date'),'bank_valuation_date')!=fxdate:fail('bank_fx_valuation_date_mismatch')
            required=rub>=threshold if rule['comparator']=='>=' else rub>threshold
        multipliers=(D(1),) if currency=='RUB' else (D('.9'),D(1),D('1.1'))
        scenarios=[{'multiplier':str(mult),'fx_rate':str(fx*mult),'amount_rub':_money(rub*mult),'assumption':True} for mult in multipliers]
    dates=[]
    for entry in _list(c.get('repatriation_dates'),'repatriation_dates',0,100):
        mapping(entry,'repatriation_obligation')
        text(entry.get('description'),'obligation_description',2000);text(entry.get('source_reference'),'obligation_source',1000)
        _date(entry.get('due_date'),'obligation_due_date');_rule(entry.get('rule'),asof);dates.append(deepcopy(entry))
    return dict(clause_checks=checklist,missing_or_unclear_sections=[r['topic'] for r in checklist if r['status']=='unknown'],direction=c['direction'],amount_original=str(amount),currency=currency,fx_rate=str(fx),amount_rub=_money(rub),fx_date=fxdate.isoformat(),fx_scenarios=scenarios,bank_rule=rule,bank_registration_threshold_rub=None if threshold is None else _money(threshold),bank_registration_required_preliminary=required,repatriation_dates=dates,repatriation_review_complete=False,currency_documents=_documents(c.get('currency_documents'),'currency_documents',asof),human_signature_required=True,contract_legality_confirmed=False,rule_applicability_verified=False,bank_submission_performed=False)

def _calendar(c):
    cal=mapping(c,'explicit_calendar');start=_date(cal.get('start'),'calendar_start');end=_date(cal.get('end'),'calendar_end')
    if end<start:fail('calendar_range')
    days=mapping(cal.get('days'),'calendar_days');_refs(cal.get('evidence_refs'),'calendar_refs')
    if len(days)>40000:fail('calendar_size_limit')
    for key,value in days.items():
        if not start<=_date(key,'calendar_day')<=end:fail('calendar_day_outside_range')
        boolean(value,'calendar_working_day')
    return days

def _day_deadline(received,days,mode,include,roll,calendar):
    if days!=days.to_integral_value():fail('response_days_integer')
    if mode not in ('calendar','working'):fail('explicit_day_kind_required')
    include=boolean(include,'include_received_day')
    if roll not in ('none','next_working'):fail('deadline_roll_policy')
    cal=_calendar(calendar) if mode=='working' or roll=='next_working' else None
    def working(d):
        if d.isoformat() not in cal:fail('calendar_day_missing')
        return cal[d.isoformat()]
    deadline=received;count=0
    try:
        if int(days)>0:
            deadline=received if include else received+timedelta(days=1)
            for _ in range(40000):
                if mode=='calendar' or working(deadline):count+=1
                if count==int(days):break
                deadline+=timedelta(days=1)
            else:fail('deadline_horizon_limit')
        if roll=='next_working':
            for _ in range(40000):
                if working(deadline):break
                deadline+=timedelta(days=1)
            else:fail('deadline_roll_limit')
    except OverflowError:fail('response_deadline_range')
    return deadline


def _appeal(src,asof):
    src=mapping(src,'appeal');decision=deepcopy(mapping(src.get('challenged_decision'),'challenged_decision'))
    route=src.get('route')
    if route not in ('administrative','judicial'):fail('appeal_route_required')
    for field in ('number','issuer','source_reference'):text(decision.get(field),'decision_'+field,2000)
    decided=_date(decision.get('date'),'decision_date')
    if decided>asof:fail('future_challenged_decision')
    applicant=text(src.get('applicant'),'appeal_applicant',4000);addressee=text(src.get('addressee'),'appeal_addressee',4000)
    demands=[text(x,'appeal_demand',4000) for x in _list(src.get('demands'),'appeal_demands',1,30)]
    grounds=[]
    for item in _list(src.get('grounds'),'appeal_grounds',1,30):
        mapping(item,'appeal_ground');grounds.append(dict(argument=text(item.get('argument'),'appeal_argument',4000),evidence_refs=_refs(item.get('evidence_refs'),'appeal_ground_refs'),rule=_rule(item.get('rule'),asof)))
    spec=deepcopy(mapping(src.get('deadline'),'appeal_deadline'));event=_date(spec.get('event_date'),'appeal_event_date')
    if not decided<=event<=asof:fail('appeal_event_date_range')
    for field in ('event_description','event_reference'):text(spec.get(field),'appeal_'+field,2000)
    spec['rule']=_rule(spec.get('rule'),event)
    if spec['rule'].get('route')!=route:fail('appeal_deadline_rule_route_mismatch')
    count=_n(spec.get('period_count'),'appeal_period_count',D(1),D(10000))
    if count!=count.to_integral_value():fail('appeal_period_integer')
    include=boolean(spec.get('include_event_day'),'appeal_include_event_day');roll=spec.get('roll_forward');unit=spec.get('period_unit')
    if roll not in ('none','next_working'):fail('appeal_roll_policy')
    if unit in ('calendar_days','working_days'):
        if spec.get('month_end_policy')!='not_applicable':fail('day_period_month_policy')
        deadline=_day_deadline(event,count,'calendar' if unit=='calendar_days' else 'working',include,roll,spec.get('calendar'))
    elif unit=='calendar_months':
        if include:fail('monthly_period_cannot_include_event_day')
        policy=spec.get('month_end_policy')
        if policy not in ('last_day','reject'):fail('explicit_month_end_policy')
        monthindex=event.year*12+event.month-1+int(count);year,month=divmod(monthindex,12);month+=1
        if not 1<=year<=9999:fail('appeal_month_range')
        last=monthrange(year,month)[1]
        if event.day>last and policy=='reject':fail('appeal_month_target_day_missing')
        deadline=date(year,month,min(event.day,last))
        if roll=='next_working':deadline=_day_deadline(deadline,D(0),'calendar',False,roll,spec.get('calendar'))
    else:fail('appeal_period_unit')
    spec['period_count']=str(count);spec['calculated_deadline']=deadline.isoformat();spec['deadline_expired_as_of']=deadline<asof
    return dict(route=route,challenged_decision=decision,applicant=applicant,addressee=addressee,demands=demands,grounds=grounds,document_refs=_refs(src.get('document_refs'),'appeal_document_refs'),deadline=spec,preparatory_status='draft_requires_review',submission_performed=False,outcome_not_promised=True,deadline_restoration_not_assumed=True,rule_applicability_verified=False)


def post_clearance(c):
    asof=_date(c.get('as_of'),'as_of');request=text(c.get('request_text'),'request_text',100000)
    workflow=c.get('mode','response')
    if workflow not in ('response','appeal','combined'):fail('post_clearance_mode')
    if (workflow in ('appeal','combined'))!=(c.get('appeal') is not None):fail('appeal_mode_object_mismatch')
    appeal=_appeal(c['appeal'],asof) if workflow in ('appeal','combined') else None
    if workflow=='appeal':
        forbidden={'received_date','response_days','day_kind','include_received_day','roll_forward','calendar','deadline_rule'}
        if forbidden & set(c):fail('appeal_only_must_not_reuse_response_deadline')
        received=rule=deadline=deadline_method=None
    else:
        received=_date(c.get('received_date'),'received_date')
        if received>asof:fail('future_received_date')
        rule=_rule(c.get('deadline_rule'),received);days=_n(c.get('response_days'),'response_days',D(0),D(10000))
        mode=c.get('day_kind');include=c.get('include_received_day');roll=c.get('roll_forward')
        deadline=_day_deadline(received,days,mode,include,roll,c.get('calendar'))
        deadline_method=dict(day_kind=mode,include_received_day=include,roll_forward=roll,response_days=int(days),calendar=deepcopy(c.get('calendar')))
    docs=[]
    for doc in _list(c.get('documents'),'requested_documents',0 if workflow=='appeal' else 1,100):
        row=deepcopy(mapping(doc,'requested_document'));text(row.get('requested'),'requested',2000);text(row.get('explanation'),'explanation',4000)
        if row.get('status') not in ('available','missing','alternative'):fail('document_status')
        if row['status']!='missing':text(row.get('available_reference'),'available_reference',1000);_refs(row.get('evidence_refs'),'document_refs')
        else:
            if row.get('available_reference') is not None:fail('missing_document_has_reference')
            text(row.get('replacement_plan'),'replacement_plan',2000)
        docs.append(row)
    arguments=[]
    for arg in _list(c.get('legal_arguments'),'legal_arguments',0 if workflow=='appeal' else 1,30):
        mapping(arg,'legal_argument')
        text(arg.get('argument'),'legal_argument',3000);_refs(arg.get('evidence_refs'),'argument_refs');_rule(arg.get('rule'),asof);arguments.append(deepcopy(arg))
    penalty=None
    if c.get('penalty') is not None:
        p=mapping(c['penalty'],'penalty');start=_date(p.get('period_start'),'penalty_start');end=_date(p.get('period_end'),'penalty_end')
        if start>end or end>asof:fail('penalty_period')
        parts=_list(p.get('periods'),'penalty_periods',1,500);cursor=start;out=[];total=D(0)
        with localcontext(Context(prec=60)) as ctx:
            ctx.prec=60
            for part in parts:
                mapping(part,'penalty_period')
                a=_date(part.get('start'),'penalty_segment_start');b=_date(part.get('end'),'penalty_segment_end')
                if a!=cursor or b<a or b>end:fail('penalty_segments_overlap_gap_or_range')
                _rule(part.get('rule'),a)
                if part['rule'].get('effective_to') is not None and b>_date(part['rule']['effective_to'],'rate_effective_to'):fail('penalty_rate_expires_inside_segment')
                principal=_n(part.get('principal'),'penalty_principal');rate=_n(part.get('annual_rate_percent'),'annual_rate',D(0),D(10000))
                numerator=_n(part.get('fraction_numerator'),'fraction_numerator',D('0.00000001'));denominator=_n(part.get('fraction_denominator'),'fraction_denominator',D('0.00000001'))
                _refs(part.get('evidence_refs'),'penalty_refs');n=(b-a).days+1;value=principal*rate/100*numerator/denominator*n;total+=value
                out.append(dict(start=a.isoformat(),end=b.isoformat(),days=n,principal=str(principal),annual_rate_percent=str(rate),fraction_numerator=str(numerator),fraction_denominator=str(denominator),amount_unrounded=str(value),amount=_money(value),evidence_refs=deepcopy(part['evidence_refs']),rule=deepcopy(part['rule'])))
                if b==end:cursor=None
                else:cursor=b+timedelta(days=1)
            if cursor is not None:fail('penalty_period_not_fully_covered')
        penalty=dict(periods=out,amount=_money(total),rounding='HALF_UP_2_total',formula='sum(principal * annual_rate/100 * numerator/denominator * inclusive_calendar_days)',rate_and_days_verification_required=True)
    return dict(request=request,mode=workflow,received_date=received.isoformat() if received else None,response_deadline=deadline.isoformat() if deadline else None,deadline_rule=rule,deadline_method=deadline_method,documents=docs,legal_arguments=arguments,penalty=penalty,appeal=appeal,submission='human_only',outcome_not_promised=True,rule_applicability_verified=False)

def input_units(function_id,c):
    """Expected domain units for numeric evidence binding; never trust a proposed unit."""
    mapping(c,'scenario_input')
    units={}
    if function_id=='declaration':
        units={'/customs_value_rub':'RUB','/payments':'RUB','/net_weight_kg':'kg','/release_hours':'hour'}
        for key in ('customs_value_rub','payments','net_weight_kg'):
            if key in c.get('source_expected',{}):units['/source_expected/'+key]='kg' if key=='net_weight_kg' else 'RUB'
        if c.get('correction') is not None:
            correction=mapping(c['correction'],'correction')
            for i,row in enumerate(_list(correction.get('changes'),'correction_changes',1,30)):
                mapping(row,'correction_change');field=row.get('field')
                if field in ('customs_value_rub','payments','net_weight_kg'):
                    for key in ('old_value','new_value'):units['/correction/changes/'+str(i)+'/'+key]='kg' if field=='net_weight_kg' else 'RUB'
    elif function_id=='origin':
        currency=text(c.get('currency'),'origin_currency',3)
        if not re.fullmatch('[A-Z]{3}',currency):fail('currency_code')
        units.update({'/materials/'+str(i)+'/value':currency for i,_ in enumerate(_list(c.get('materials'),'materials',0,200))})
        method=mapping(c.get('method'),'origin_method')
        for i,criterion in enumerate(_list(method.get('criteria'),'origin_criteria',1,4)):
            mapping(criterion,'origin_criterion')
            if criterion.get('kind')=='value_content':units['/method/criteria/'+str(i)+'/denominator_value']=currency;units['/method/criteria/'+str(i)+'/threshold_percent']='percent'
    elif function_id=='trade_contract':
        currency=text(c.get('currency'),'currency',3)
        if not re.fullmatch('[A-Z]{3}',currency):fail('currency_code')
        units={'/amount':currency,'/fx_rate':{'unit':'RUB/'+currency,'effective_date':c.get('fx_date')}}
        if c.get('bank_rule') is not None:units['/bank_rule/threshold_rub']='RUB'
    elif function_id=='post_clearance':
        units={} if c.get('mode')=='appeal' else {'/response_days':'day'}
        if c.get('appeal') is not None:
            appeal=mapping(c['appeal'],'appeal');deadline=mapping(appeal.get('deadline'),'appeal_deadline')
            period=deadline.get('period_unit')
            if period not in ('calendar_days','working_days','calendar_months'):fail('appeal_period_unit')
            units['/appeal/deadline/period_count']='month' if period=='calendar_months' else 'day'
        penalty=c.get('penalty')
        periods=[] if penalty is None else _list(mapping(penalty,'penalty').get('periods'),'penalty_periods',1,500)
        for i,_ in enumerate(periods):
            for key,unit in [('principal','RUB'),('annual_rate_percent','percent'),('fraction_numerator','fraction'),('fraction_denominator','fraction')]:units['/penalty/periods/'+str(i)+'/'+key]=unit
    elif function_id not in ('tnved_classification','non_tariff'):fail('unknown_scenario_function')
    return units

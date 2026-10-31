"""Local investment research workflows, not publication, brokerage or tax filing.

Selected quotations establish occurrence only. Declared publicness, rule coverage
and a disclaimer never establish legal permission or an investor's qualification.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal, Context, localcontext, ROUND_HALF_UP
from functools import wraps
import re

D = Decimal
CTX = Context(prec=100, rounding=ROUND_HALF_UP)
FUNCTIONS = ('issuer_disclosure', 'research_report', 'investor_status', 'insider_compliance', 'investor_tax')
COMPLIANCE_TOPICS = {
    'source_publicness': 'Obtain the primary public-disclosure evidence for each source; keep unknown sources restricted.',
    'insider_list_and_access': 'Reconcile the insider list, access rights and applicable internal trading restrictions with compliance.',
    'author_positions': 'Reconcile the author holdings and related interests through the restricted compliance channel.',
    'company_positions': 'Reconcile the firm holdings and issuer relationships through the restricted compliance channel.',
    'planned_transactions': 'Submit planned transactions for the applicable internal review; this checklist gives no trade authorization.',
    'conflict_disclosure': 'Compare the proposed conflict disclosure with the actual author and firm interests before release.',
    'publication_and_manipulation': 'Review the complete publication and relevant trading conduct; a keyword screen is not a manipulation finding.'
}

def fail(code): raise ValueError(code)
def obj(v, n):
    if type(v) is not dict: fail(n+'_object_required')
    return v
def seq(v,n,minimum=0,maximum=100):
    if type(v) is not list or not minimum <= len(v) <= maximum: fail(n+'_list_required')
    return v
def text(v,n,maximum=12000):
    if type(v) is not str or not v.strip() or len(v)>maximum or any(ord(c)<32 and c not in '\n\t\r' for c in v): fail(n+'_text_required')
    return v.strip()
def day(v,n):
    if type(v) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',v): fail(n+'_iso_date_required')
    try: return date.fromisoformat(v)
    except ValueError: fail(n+'_invalid_date')
def num(v,n,low='0',high='1e20'):
    if type(v) not in (str,int,Decimal) or not re.fullmatch(r'-?(?:0|[1-9]\d{0,20})(?:\.\d{1,8})?',str(v)): fail(n+'_exact_decimal_required')
    result=D(v)
    if not result.is_finite() or not D(low)<=result<=D(high): fail(n+'_range')
    return result
def ref(v,n='source_reference'): return text(v,n,1000)
def refs(v,n='evidence_refs',minimum=1):
    a=seq(v,n,minimum)
    for x in a: ref(x,n)
    if len(set(a)) != len(a): fail(n+'_duplicates')
    return deepcopy(a)
def choice(v,values,n):
    if v not in values or type(v) is not str: fail(n+'_invalid')
    return v
def strings(v,n,minimum=0):
    a=seq(v,n,minimum)
    return [text(x,n,5000) for x in a]
def dated_rule(v,event):
    r=deepcopy(obj(v,'rule'))
    for k in ('source_reference','edition','scope'): text(r.get(k),'rule_'+k,4000)
    start=day(r.get('effective_from'),'rule_effective_from')
    end=day(r['effective_to'],'rule_effective_to') if r.get('effective_to') is not None else None
    published=day(r.get('published_at'),'rule_published_at')
    if published>event or start>event or (end is not None and (end<start or event>end)): fail('rule_not_effective_on_event_date')
    return r
def assessment(v,n,asof):
    r=deepcopy(obj(v,n));state=choice(r.get('status'),('provided','missing','unknown','not_applicable'),n+'_status')
    text(r.get('analysis'),n+'_analysis',8000)
    r['evidence_refs']=refs(r.get('evidence_refs'),n+'_refs',1 if state in ('provided','not_applicable') else 0)
    if r.get('document_date') is not None and day(r['document_date'],n+'_document_date')>asof: fail('future_assessment_document')
    return r
def base(c):
    obj(c,'data');asof=day(c.get('as_of'),'as_of')
    if c.get('jurisdiction')!='RU': fail('russian_jurisdiction_required')
    return asof
def finish(c,result,gaps,next_steps):
    result.update(as_of=c['as_of'],gaps=sorted(set(gaps)),next_steps=next_steps,
        source_declarations_are_not_verification=True,current_rule_chain_complete=False,
        actual_weekly_update_performed=False,last_confirmed_database=None,
        external_actions=False,publication_performed=False)
    return result
def guarded(fn):
    @wraps(fn)
    def run(data):
        try:
            with localcontext(CTX): return fn(deepcopy(obj(data,'data')))
        except (KeyError,AttributeError,TypeError,IndexError):
            raise ValueError('invalid_'+fn.__name__+'_structure') from None
    return run

@guarded
def issuer_disclosure(c):
    asof=base(c);issuer=deepcopy(obj(c.get('issuer'),'issuer'))
    for k in ('name','ticker'): text(issuer.get(k),'issuer_'+k,1000)
    inn=text(issuer.get('inn'),'issuer_inn',12)
    if not re.fullmatch(r'\d{10}|\d{12}',inn): fail('issuer_inn_format')
    period=text(c.get('period'),'period',100)
    documents=[];gaps=[];kinds=set();ids=set()
    for i,r0 in enumerate(seq(c.get('documents'),'documents',1)):
        r=deepcopy(obj(r0,'document'));identity=text(r.get('id'),'document_id',200)
        if identity in ids: fail('duplicate_document_id')
        ids.add(identity)
        kind=choice(r.get('kind'),('issuer_report','material_facts','rsbu','ifrs','prospectus','issue_decision','news','other'),'document_kind')
        state=choice(r.get('status'),('provided','missing','restricted','not_applicable'),'document_status')
        text(r.get('analysis'),'document_analysis',8000)
        if state=='provided':
            if kind=='news': fail('news_cannot_replace_disclosure')
            if day(r.get('date'),'document_date')>asof: fail('future_disclosure_document')
            text(r.get('period'),'document_period',100);text(r.get('standard'),'document_standard',100)
            ref(r.get('source_reference'));text(r.get('quote'),'document_quote',100000)
            metrics=seq(r.get('metrics',[]),'document_metrics',0)
            names=set()
            for m in metrics:
                obj(m,'metric');name=text(m.get('name'),'metric_name',300)
                if name in names: fail('duplicate_metric_name')
                names.add(name);num(m.get('value'),'metric_value','-1e20');text(m.get('unit'),'metric_unit',100)
                text(m.get('quote'),'metric_quote',10000);ref(m.get('source_reference'))
            kinds.add(kind)
        elif any(r.get(k) is not None for k in ('source_reference','quote','metrics','date')):
            fail('absent_disclosure_has_claimed_content')
        if state in ('missing','restricted'): gaps.append(kind+'_'+state)
        documents.append(r)
    required=seq(c.get('required_document_kinds'),'required_document_kinds',1,7)
    for k in required: choice(k,('issuer_report','material_facts','rsbu','ifrs','prospectus','issue_decision'),'required_kind')
    if len(set(required))!=len(required): fail('duplicate_required_kind')
    missing=[k for k in required if k not in kinds]
    gaps.extend(k+'_primary_document_not_provided' for k in missing)
    facts=[]
    for r0 in seq(c.get('material_facts'),'material_facts'):
        r=deepcopy(obj(r0,'material_fact'));text(r.get('quote'),'material_fact_quote',10000);ref(r.get('source_reference'))
        if day(r.get('date'),'material_fact_date')>asof: fail('future_material_fact')
        facts.append(r)
    ratings=[]
    for r0 in seq(c.get('ratings'),'ratings'):
        r=deepcopy(obj(r0,'rating'))
        for k in ('agency','grade','source_reference'): text(r.get(k),'rating_'+k,1000)
        if day(r.get('date'),'rating_date')>asof: fail('future_rating')
        r['agency_registry_evidence']=assessment(r.get('agency_registry_evidence'),'agency_registry',asof)
        if r['agency_registry_evidence']['status']!='provided': gaps.append('rating_agency_registry_not_documented')
        ratings.append(r)
    limitations=strings(c.get('disclosure_limitations'),'disclosure_limitations')
    if limitations:gaps.append('disclosure_is_incomplete_or_restricted')
    return finish(c,dict(function='issuer_disclosure',status='evidence_compiled_with_gaps' if gaps else 'evidence_compiled',issuer=issuer,period=period,
        documents=documents,material_facts=facts,ratings=ratings,disclosure_limitations=limitations,missing_primary_documents=missing,
        complete_disclosure_established=False),gaps,['Obtain missing primary issuer filings and dated market observations.','A disclosure restriction does not establish the absent figures.'])

def sources(c,asof):
    result=[];ids=set()
    for r0 in seq(c.get('sources'),'sources',1):
        r=deepcopy(obj(r0,'source'));identity=text(r.get('id'),'source_id',200)
        if identity in ids:fail('duplicate_source_id')
        ids.add(identity)
        choice(r.get('public_status'),('publicly_disclosed','nonpublic','unknown'),'source_public_status')
        ref(r.get('source_reference'));text(r.get('description'),'source_description',4000)
        when=day(r.get('document_date'),'source_document_date')
        if when>asof:fail('future_source_document')
        if r['public_status']=='publicly_disclosed':
            text(r.get('public_location'),'source_public_location',2000)
            if day(r.get('disclosed_on'),'source_disclosed_on')>asof:fail('future_public_disclosure')
        result.append(r)
    return result

@guarded
def research_report(c):
    asof=base(c);data_date=day(c.get('data_date'),'data_date')
    if data_date>asof:fail('future_research_data_date')
    audience=choice(c.get('audience'),('internal','broker_clients','public'),'audience')
    issuer=text(c.get('issuer'),'issuer',1000);src=sources(c,asof)
    personal=choice(c.get('personalization'),('general','specific_person_or_portfolio','unknown'),'personalization')
    purpose=choice(c.get('material_purpose'),('analysis','advertising','unknown'),'material_purpose')
    narrative=deepcopy(obj(c.get('narrative'),'narrative'))
    for k in ('thesis','valuation','conflict_disclosure'):text(narrative.get(k),'narrative_'+k,16000)
    for k in ('risks','catalysts','falsifiers'): narrative[k]=strings(narrative.get(k),k,1)
    facts=[];source_by_id={x['id']:x for x in src}
    for r0 in seq(c.get('facts'),'research_facts',1):
        r=deepcopy(obj(r0,'research_fact'));text(r.get('quote'),'fact_quote',12000);ref(r.get('source_reference'))
        if r.get('source_id') not in source_by_id:fail('fact_source_id_missing')
        if r['source_reference']!=source_by_id[r['source_id']]['source_reference']:fail('fact_source_reference_mismatch')
        if day(r.get('date'),'fact_date')>data_date:fail('fact_after_research_date')
        facts.append(r)
    for s in src:
        if day(s['document_date'],'source_document_date')>data_date or (s.get('disclosed_on') and day(s['disclosed_on'],'source_disclosed_on')>data_date):fail('source_after_research_date')
    sensitive=any(x['public_status']!='publicly_disclosed' for x in src)
    gaps=[]
    if sensitive:gaps.append('nonpublic_or_unknown_sources_exclude_public_narrative')
    if personal!='general':gaps.append('personalized_or_unknown_context_requires_investment_adviser_review')
    if purpose!='analysis':gaps.append('advertising_or_unknown_purpose_requires_separate_legal_review')
    combined=' '.join([str(narrative),str(facts)]).lower()
    flags=[s for s in ('guaranteed return','risk free','без риска','гарантирован','保证收益','无风险') if s in combined]
    if flags:gaps.append('possible_return_promise_language_requires_review')
    withheld=sensitive or personal!='general'
    return finish(c,dict(function='research_report',status='content_withheld' if withheld else 'private_research_draft',audience=audience,issuer=issuer,data_date=c['data_date'],
        content_withheld=withheld,narrative=None if withheld else narrative,public_facts=[] if withheld else facts,
        source_inventory=[{'id':s['id'],'source_reference':s['source_reference'],'public_status':s['public_status']} for s in src],
        publication_draft_allowed=False,publication_clearance=None,personalization=personal,material_purpose=purpose,
        language_screen_flags=flags,language_screen_is_not_legal_analysis=True,
        disclaimer_is_not_publication_permission=True,individual_recommendation_classification=None),gaps,
        ['Keep the draft local; obtain compliance review of sources, conflicts, advertising and recommendation classification.','A non-IIR label does not change personalized substance or authorize publication.'])

@guarded
def investor_status(c):
    asof=base(c);entity=choice(c.get('entity_type'),('individual','legal_entity'),'entity_type')
    instrument=text(c.get('instrument'),'instrument',2000)
    review=deepcopy(obj(c.get('instrument_review'),'instrument_review'))
    choice(review.get('qualified_status_required'),('required','not_required','unknown'),'qualified_status_requirement')
    text(review.get('analysis'),'instrument_review_analysis',8000);refs(review.get('evidence_refs'),'instrument_review_refs',0 if review['qualified_status_required']=='unknown' else 1)
    rules=[dated_rule(r,asof) for r in seq(c.get('rules'),'rules',1,20)]
    groups=[];gaps=[];group_ids=set()
    for g0 in seq(c.get('criteria_groups'),'criteria_groups',1,20):
        g=deepcopy(obj(g0,'criteria_group'));identity=text(g.get('id'),'criteria_group_id',100)
        if identity in group_ids:fail('duplicate_criteria_group_id')
        group_ids.add(identity);text(g.get('description'),'criteria_group_description',5000);ref(g.get('source_reference'))
        criteria=[];seen=set()
        for r0 in seq(g.get('criteria'),'criteria',1,30):
            r=deepcopy(obj(r0,'criterion'));kind=choice(r.get('kind'),('assets','income','transactions','experience','education','certificate','exam','legal_entity_criterion','other'),'criterion_kind')
            identity=text(r.get('id'),'criterion_id',100)
            if identity in seen:fail('duplicate_criterion_id')
            seen.add(identity);text(r.get('description'),'criterion_description',5000);ref(r.get('source_reference'))
            r['documentation']=assessment(r.get('documentation'),'criterion_documentation',asof)
            if r['documentation']['status']!='provided':gaps.append(g['id']+':'+identity+':documentation_'+r['documentation']['status'])
            if 'threshold' in r or 'observed' in r:
                num(r.get('threshold'),'criterion_threshold');num(r.get('observed'),'criterion_observed');text(r.get('unit'),'criterion_unit',100)
                choice(r.get('comparison'),('at_least','at_most'),'criterion_comparison')
                r['arithmetic_comparison']=num(r['observed'],'observed')>=num(r['threshold'],'threshold') if r['comparison']=='at_least' else num(r['observed'],'observed')<=num(r['threshold'],'threshold')
                r['arithmetic_does_not_establish_criterion']=True
            criteria.append(r)
        g['criteria']=criteria;g['logic']='all_conditions_in_group; alternative_groups_are_not_auto_qualification';groups.append(g)
    testing=deepcopy(obj(c.get('testing'),'testing'))
    choice(testing.get('requirement'),('required','not_required','unknown'),'testing_requirement');text(testing.get('analysis'),'testing_analysis',8000)
    testing['evidence_refs']=refs(testing.get('evidence_refs'),'testing_refs',0 if testing['requirement']=='unknown' else 1)
    testing['result_document']=assessment(testing.get('result_document'),'test_result_document',asof)
    if testing['requirement']=='unknown':gaps.append('testing_requirement_not_established')
    elif testing['requirement']=='required' and testing['result_document']['status']!='provided':gaps.append('required_test_result_missing_or_unknown')
    if review['qualified_status_required']=='unknown':gaps.append('instrument_status_requirement_unknown')
    scope=text(c.get('recognition_scope'),'recognition_scope',8000)
    return finish(c,dict(function='investor_status',status='broker_review_required',entity_type=entity,instrument=instrument,instrument_review=review,
        criteria_groups=groups,testing=testing,rules=rules,recognition_scope=scope,qualification_decision=None,testing_passed=None,
        recognition_automatic=False,decision_maker='broker_or_other_legally_authorized_recognizing_person',evidence_gaps=sorted(set(gaps))),gaps,
        ['Check the effective rule edition, instrument restrictions and recognition scope with the recognizing organization.','Provide the actual criterion and test documents; this tool does not issue qualified status.'])

@guarded
def insider_compliance(c):
    asof=base(c);src=sources(c,asof);publication=text(c.get('publication_text'),'publication_text',200000)
    refs(c.get('publication_refs'),'publication_refs')
    status=choice(c.get('insider_list_status'),('listed','not_listed','unknown'),'insider_list_status')
    text(c.get('conflict_disclosure'),'conflict_disclosure',12000)
    for k in ('author_positions','company_positions','planned_transactions'):
        strings(c.get(k),k)
    rules=[dated_rule(r,asof) for r in seq(c.get('rules'),'rules',1,20)]
    checks={}
    for r in seq(c.get('compliance_checks',[]),'compliance_checks',0,len(COMPLIANCE_TOPICS)):
        obj(r,'compliance_check');topic=choice(r.get('topic'),tuple(COMPLIANCE_TOPICS),'compliance_topic')
        if topic in checks:fail('duplicate_compliance_topic')
        check=assessment(r,'compliance_check',asof)
        # Do not echo a private position, transaction plan or source narrative
        # from the draft into a publication-facing result. Keep only the local
        # evidence pointers and a safe action, never an approval conclusion.
        checks[topic]={'topic':topic,'status':check['status'],'evidence_refs':check['evidence_refs'],
            'document_date':check.get('document_date'),'next_action':COMPLIANCE_TOPICS[topic]}
    checklist=[checks.get(topic,{'topic':topic,'status':'unknown','evidence_refs':[],
        'document_date':None,'next_action':action}) for topic,action in COMPLIANCE_TOPICS.items()]
    sensitive=any(s['public_status']!='publicly_disclosed' for s in src)
    flags=[s for s in ('guaranteed','risk free','secret information','без риска','точно вырастет','секретная информация','гарантирован','保证收益','内幕消息') if s in publication.lower()]
    gaps=['compliance_must_determine_inside_information_and_market_manipulation']
    if sensitive:gaps.append('nonpublic_or_unknown_information_requires_restricted_compliance_channel')
    if flags:gaps.append('language_screen_flags_require_review')
    if status=='unknown':gaps.append('insider_list_status_unknown')
    gaps.extend('compliance_topic:'+r['topic']+':'+r['status'] for r in checklist if r['status'] in ('missing','unknown'))
    return finish(c,dict(function='insider_compliance',status='restricted_compliance_review' if sensitive else 'compliance_review_required',
        sources=[{'id':s['id'],'source_reference':s['source_reference'],'public_status':s['public_status']} for s in src],
        publication_text=None,publication_refs=deepcopy(c['publication_refs']),sensitive_content_withheld=sensitive,
        insider_list_status=status,language_screen_flags=flags,language_screen_is_not_legal_analysis=True,
        publication_blocked=True,publication_clearance=None,inside_information_determination=None,manipulation_determination=None,
        conflict_review_required=True,positions_and_transactions_require_restricted_review=True,rules=rules,
        compliance_checklist=checklist,checklist_documents_do_not_establish_clearance=True),gaps,
        ['Do not publish or trade on unreviewed nonpublic information; refer only through the authorized restricted compliance route.','A public-source declaration or a clean keyword screen is not legal clearance.'])

def account_conditions(account,income_type):
    result=['Select the effective Tax Code edition, residence and income basket; foreign-currency amounts need dated RUB conversion evidence.','Tax-agent withholding and final annual tax may differ; reconcile all agents and declaration duties.']
    if account=='iis_a':result.append('Legacy IIS contribution deduction: check opening date, qualifying contributions, eligible income tax base, prior claims and early closure consequences.')
    elif account=='iis_b':result.append('Legacy IIS income exemption: check holding period, prior contribution deductions, excluded income and tax-agent documents; dividends are separate.')
    elif account=='iis3':result.append('IIS-3: check opening/conversion date, transition holding period, concurrent-account restrictions, shared long-term-savings contribution limit, termination-income cap and excluded dividends; do not reuse legacy conditions.')
    else:result.append('Ordinary brokerage account: inspect long-term ownership relief separately by security eligibility, acquisition/sale dates, holding period and cap; no automatic exemption.')
    if income_type=='dividend':result.append('Dividend income is a separate basket: do not offset acquisition costs, securities losses or IIS income relief automatically.')
    if income_type in ('security_sale','derivative'):result.append('Verify documented acquisition costs, fees and loss-netting categories/periods; not every loss can be combined with every income.')
    return result

@guarded
def investor_tax(c):
    asof=base(c);mode=choice(c.get('mode'),('overview','conditional_calculation'),'tax_mode')
    income=choice(c.get('income_type'),('dividend','coupon','security_sale','derivative','other'),'income_type')
    residency=choice(c.get('residency'),('resident','nonresident','unknown'),'residency')
    account=choice(c.get('account'),('brokerage','iis_a','iis_b','iis3'),'account')
    year=text(c.get('tax_period'),'tax_period',4)
    if not re.fullmatch(r'\d{4}',year) or not 1900<=int(year)<=asof.year:fail('tax_period_range')
    event=day(c.get('income_date'),'income_date')
    if event>asof or event.year!=int(year):fail('income_date_tax_period_mismatch')
    if account!='brokerage':
        opened=day(c.get('account_opened_on'),'account_opened_on')
        if opened>event:fail('account_opened_after_income')
        # A 2024 account may have elected the legacy deduction regime under a
        # transitional rule. Never reject it solely from its opening year.
        if account in ('iis_a','iis_b') and opened>=date(2024,1,1):
            legacy=assessment(c.get('legacy_regime_documentation'),'legacy_regime',asof)
            if legacy['status']!='provided':fail('legacy_regime_transition_documentation_required')
        if account=='iis3' and opened<date(2024,1,1) and c.get('conversion_documentation') is None:fail('iis3_legacy_conversion_documentation_required')
        if c.get('conversion_documentation') is not None:assessment(c['conversion_documentation'],'iis_conversion',asof)
    rules=[dated_rule(r,event) for r in seq(c.get('rules'),'rules',1,20)]
    conditions=account_conditions(account,income);gaps=['tax_rule_chain_and_relief_eligibility_require_review']
    if residency=='unknown':gaps.append('tax_residency_unknown')
    conditions.extend(strings(c.get('case_conditions'),'case_conditions',1))
    calc=None
    if mode=='conditional_calculation':
        if residency=='unknown' or income=='other':fail('tax_calculation_requires_known_residency_and_supported_income')
        if c.get('currency')!='RUB':fail('tax_calculation_rub_only')
        schedule=deepcopy(obj(c.get('rate_schedule'),'rate_schedule'));dated_rule(schedule,event)
        if schedule.get('residency')!=residency or schedule.get('income_type')!=income or schedule.get('tax_period')!=year:fail('tax_schedule_scope_mismatch')
        ref(c.get('aggregation_basis_reference'))
        gross=num(c.get('income_amount'),'income_amount');costs=num(c.get('documented_costs'),'documented_costs');fees=num(c.get('documented_fees'),'documented_fees')
        losses=num(c.get('loss_offset'),'loss_offset');relief=num(c.get('relief_amount'),'relief_amount');other=num(c.get('same_basket_other_base'),'same_basket_other_base');withheld=num(c.get('withheld_tax'),'withheld_tax')
        if income in ('dividend','coupon') and (costs or fees or losses):fail('income_basket_does_not_allow_generic_cost_or_loss_offset')
        relief_kind=choice(c.get('relief_kind'),('none','long_term_ownership','iis_income_exemption','documented_other'),'relief_kind')
        if relief_kind=='none' and relief:fail('relief_amount_without_kind')
        if income=='dividend' and relief:fail('dividend_relief_not_supported')
        if relief_kind=='long_term_ownership' and (income!='security_sale' or account!='brokerage'):fail('long_term_relief_scope_unsupported')
        if relief_kind=='iis_income_exemption' and account not in ('iis_b','iis3'):fail('iis_income_relief_account_mismatch')
        if losses:ref(c.get('loss_basis_reference'))
        if relief:ref(c.get('relief_basis_reference'))
        before=max(D(0),gross-costs-fees-losses)
        if relief>before:fail('relief_exceeds_calculated_base')
        after=before-relief;brackets=[];previous=D(0)
        for index,r in enumerate(seq(schedule.get('brackets'),'tax_brackets',1,20)):
            obj(r,'tax_bracket');rate=num(r.get('rate'),'tax_bracket_rate','0','1');ref(r.get('source_reference'))
            cap=num(r['up_to'],'tax_bracket_up_to','0.00000001') if r.get('up_to') is not None else None
            if cap is not None and cap<=previous:fail('tax_bracket_caps_must_increase')
            if cap is None and index!=len(schedule['brackets'])-1:fail('unbounded_tax_bracket_must_be_last')
            brackets.append((cap,rate))
            if cap is not None:previous=cap
        if brackets[-1][0] is not None:fail('tax_schedule_requires_unbounded_final_bracket')
        rounding=choice(c.get('rounding'),('kopecks','whole_rubles'),'tax_rounding')
        quantum=D('.01') if rounding=='kopecks' else D('1')
        def liability(base):
            total=D(0);floor=D(0)
            for cap,rate in brackets:
                taxable=max(D(0),base-floor) if cap is None else max(D(0),min(base,cap)-floor)
                total+=taxable*rate
                if cap is not None:floor=cap
            return total
        marginal_before=liability(other+before)-liability(other);marginal_after=liability(other+after)-liability(other)
        fmt=lambda n:str(n.quantize(quantum,rounding=ROUND_HALF_UP))
        calc=dict(gross_income_rub=str(gross),documented_costs_rub=str(costs),documented_fees_rub=str(fees),loss_offset_rub=str(losses),
            base_before_relief_rub=str(before),relief_amount_rub=str(relief),base_after_relief_rub=str(after),same_basket_other_base_rub=str(other),
            marginal_tax_before_relief_rub=fmt(marginal_before),marginal_tax_after_relief_rub=fmt(marginal_after),withheld_tax_rub=str(withheld),
            balance_to_review_rub=fmt(marginal_after-withheld),rounding=rounding,rate_schedule=schedule,relief_kind=relief_kind,
            conditional_on_supplied_rule_and_eligibility=True,final_personal_tax=False)
        if losses or relief:gaps.append('claimed_offset_or_relief_is_conditional_not_granted')
    elif any(k in c for k in ('rate_schedule','income_amount','documented_costs','documented_fees','loss_offset','relief_amount','same_basket_other_base','withheld_tax')):fail('overview_must_not_contain_ignored_calculation_inputs')
    return finish(c,dict(function='investor_tax',status='conditional_arithmetic' if calc else 'general_tax_review',mode=mode,income_type=income,residency=residency,
        tax_period=year,account=account,income_date=c['income_date'],account_opened_on=c.get('account_opened_on'),conditions=conditions,rules=rules,calculation=calc,
        tax_agent_assessment=assessment(c.get('tax_agent_assessment'),'tax_agent',asof),relief_eligibility=None,return_filed=False),gaps,
        ['Reconcile the selected tax basket, broker documents, residency and all claimed relief conditions locally.','These conditional numbers are not a grant of a deduction, an assessment by the tax authority or a filed declaration.'])

def input_units(function,data):
    obj(data,'data');out={}
    if function=='issuer_disclosure':
        for i,r in enumerate(seq(data.get('documents'),'documents',1)):
            obj(r,'document')
            if r.get('status')=='provided':
                for j,m in enumerate(seq(r.get('metrics',[]),'metrics')):
                    obj(m,'metric');out[f'/documents/{i}/metrics/{j}/value']={'unit':text(m.get('unit'),'metric_unit',100),'not_after':data['as_of']}
    elif function=='investor_status':
        for i,g in enumerate(seq(data.get('criteria_groups'),'criteria_groups',1)):
            for j,r in enumerate(seq(obj(g,'group').get('criteria'),'criteria',1)):
                obj(r,'criterion')
                if 'threshold' in r or 'observed' in r:
                    unit=text(r.get('unit'),'criterion_unit',100)
                    out[f'/criteria_groups/{i}/criteria/{j}/threshold']=unit
                    out[f'/criteria_groups/{i}/criteria/{j}/observed']=unit
    elif function=='investor_tax' and data.get('mode')=='conditional_calculation':
        for k in ('income_amount','documented_costs','documented_fees','loss_offset','relief_amount','same_basket_other_base','withheld_tax'):out['/'+k]='RUB'
        for i,r in enumerate(seq(obj(data.get('rate_schedule'),'rate_schedule').get('brackets'),'brackets',1)):
            obj(r,'bracket');out[f'/rate_schedule/brackets/{i}/rate']={'unit':'ratio','effective_date':data['rate_schedule']['effective_from'],'not_after':data['income_date']}
            if r.get('up_to') is not None:out[f'/rate_schedule/brackets/{i}/up_to']={'unit':'RUB','effective_date':data['rate_schedule']['effective_from'],'not_after':data['income_date']}
    elif function not in FUNCTIONS:fail('unknown_investment_scenario')
    return out

def selected_texts(function,data):
    # Generic binding also verifies every quote/excerpt against its specifically
    # referenced selected file. The publication itself is an authored draft, not
    # a source quotation, and is deliberately not promoted into source evidence.
    return {}

"""Bounded selected-source tax practice drafts. No legal, filing or authority grant.

Document metadata is declared, source occurrence is checked by the host binding,
and neither establishes a complete normative chain. All arithmetic predicates use
exact rational operands; decimal rendering uses a private context.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal, Context, localcontext, InvalidOperation
from fractions import Fraction
import re

from .privacy import reject_known_secret_material

FUNCTIONS = ('law_monitoring', 'tax_accounting_method', 'client_engagement')
KINDS = ('norm', 'letter', 'court', 'bill', 'news', 'client_record')
TOPICS = ('general', 'income_expenses', 'depreciation', 'reserves', 'vat', 'registers', 'branches', 'usn_expenses')
CLAUSES = ('subject', 'result', 'inputs', 'deadlines', 'price', 'confidentiality', 'liability', 'power_of_attorney', 'quality', 'language', 'document_exchange', 'termination')
REVIEW_TOPICS = ('subject', 'result', 'inputs', 'deadlines', 'price', 'confidentiality', 'liability')


def fail(code):
    raise ValueError(code)


def obj(value, required=(), optional=()):
    if type(value) is not dict or set(value)-set(required)-set(optional) or not set(required)<=set(value):
        fail('invalid_practice_object_fields')
    return value


def text(value, maximum=12000, empty=False):
    if type(value) is not str or len(value)>maximum or (not empty and not value.strip()):
        fail('invalid_practice_text')
    if any(ord(c)<32 and c not in '\t\r\n' for c in value):
        fail('unsupported_practice_text_control')
    return value


def enum(value, choices):
    text(value, 150)
    if value not in choices:
        fail('unsupported_practice_choice')
    return value


def day(value):
    if type(value) is not str:
        fail('ISO_date_required')
    try:
        result=date.fromisoformat(value)
    except ValueError:
        fail('ISO_date_required')
    if result.isoformat()!=value:
        fail('ISO_date_required')
    return result


def seq(value, maximum=100, minimum=0):
    if type(value) is not list or not minimum<=len(value)<=maximum:
        fail('bounded_practice_list_required')
    return value


def strings(value, maximum=100):
    result=[text(x, 2000) for x in seq(value, maximum)]
    if len(result)!=len(set(result)):
        fail('duplicate_practice_identifier')
    return result


def sid(value):
    return text(value, 200)


def dec(value):
    if type(value) is not str or len(value)>80 or not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?', value):
        fail('bounded_decimal_string_required')
    try:
        result=Decimal(value)
    except InvalidOperation:
        fail('bounded_decimal_string_required')
    if not result.is_finite() or len(result.as_tuple().digits)>40 or abs(result.as_tuple().exponent)>140 or (result and abs(result.adjusted())>100):
        fail('decimal_source_precision_limit')
    return result


def exact(value):
    if isinstance(value, Fraction):
        with localcontext(Context(prec=180)):
            return str(Decimal(value.numerator)/Decimal(value.denominator))
    return str(value)


class Reader:
    def __init__(self, data):
        self.data=data; self.units={}; self.texts={}; self.gaps=[]
        self.as_of=day(data['as_of'])

    def literal(self, path, value, ref):
        text(value); sid(ref)
        self.texts[path]={'text':value, 'source_references':[ref]}
        return value

    def date_literal(self,path,value,ref):
        day(value)
        self.literal(path,value,ref)
        self.texts[path]['date_format']='iso_or_dmy_dot'
        return value

    def q(self, value, path, unit, low=Fraction(0), high=None):
        obj(value, ('value','unit','source_reference'), ('observed_at',))
        if value['unit']!=unit:
            fail('quantity_unit_mismatch')
        number=dec(value['value']); fraction=Fraction(number)
        if fraction<low or (high is not None and fraction>high):
            fail('quantity_out_of_selected_domain')
        ref=sid(value['source_reference'])
        spec={'unit':unit, 'effective_not_after':self.data['as_of'], 'published_not_after':self.data['as_of'], 'source_references':[ref]}
        if 'observed_at' in value:
            if day(value['observed_at'])>self.as_of:
                fail('observation_after_information_cutoff')
            spec['effective_date']=value['observed_at']
            self.date_literal(path+'/observed_at', value['observed_at'], ref)
        self.units[path+'/value']=spec
        return fraction

    def record(self, value, path):
        obj(value, ('source_reference','excerpt'), ('recorded_at',))
        ref=sid(value['source_reference']); self.literal(path+'/excerpt',value['excerpt'],ref)
        if value.get('recorded_at') is not None:
            if day(value['recorded_at'])>self.as_of:
                fail('record_after_information_cutoff')
            self.date_literal(path+'/recorded_at',value['recorded_at'],ref)
        return deepcopy(value)

    def gap(self, code, identifier=None):
        item={'kind':code}
        if identifier is not None:item['id']=identifier
        if item not in self.gaps:self.gaps.append(item)


def documents(r):
    rows=seq(r.data.get('documents',[]),100); out=[]; ids=set()
    for i,v in enumerate(rows):
        obj(v, ('id','kind','document_identity','edition','publication_date','effective_from','effective_to','clause','excerpt','source_reference'), ('supersedes','history_group','date_source_reference'))
        identifier=sid(v['id'])
        if identifier in ids:fail('duplicate_document_id')
        ids.add(identifier); enum(v['kind'],KINDS)
        for key in ('document_identity','clause'):
            r.literal(f'/documents/{i}/{key}',v[key],v['source_reference'])
        if v['edition'] is not None:r.literal(f'/documents/{i}/edition',v['edition'],v['source_reference'])
        r.literal(f'/documents/{i}/excerpt',v['excerpt'],v['source_reference'])
        date_ref=sid(v.get('date_source_reference',v['source_reference']))
        for key in ('publication_date','effective_from','effective_to'):
            if v[key] is not None:
                day(v[key]);r.date_literal(f'/documents/{i}/{key}',v[key],date_ref)
        if v['publication_date'] is not None and day(v['publication_date'])>r.as_of:
            fail('document_publication_after_information_cutoff')
        if v['effective_from'] is not None and v['effective_to'] is not None and day(v['effective_to'])<day(v['effective_from']):
            fail('inverted_selected_effective_window')
        for key in ('edition','publication_date','effective_from','effective_to'):
            if v[key] is None:r.gap('selected_document_metadata_unknown',identifier+':'+key)
        if 'history_group' in v:text(v['history_group'],300)
        strings(v.get('supersedes',[]),100)
        out.append(deepcopy(v))
    byid={x['id']:x for x in out}
    for v in out:
        for previous in v.get('supersedes',[]):
            if previous not in byid:r.gap('history_reference_not_selected',v['id']+':'+previous)
    # Iterative graph review; no recursion and no implicit winner.
    indegree={k:0 for k in byid}; edges={k:[] for k in byid}
    for v in out:
        for target in v.get('supersedes',[]):
            if target in byid:edges[v['id']].append(target);indegree[target]+=1
    queue=[k for k,n in indegree.items() if n==0]; position=0
    while position<len(queue):
        node=queue[position];position+=1
        for target in edges[node]:
            indegree[target]-=1
            if indegree[target]==0:queue.append(target)
    if position<len(byid):r.gap('cyclic_selected_version_history')
    return out,byid


def temporal(doc, selected_date):
    if selected_date is None:return 'applicability_date_not_selected'
    at=day(selected_date)
    if doc['effective_from'] is None:return 'effective_start_unknown'
    if at<day(doc['effective_from']):return 'before_selected_effective_start'
    if doc['effective_to'] is not None and at>day(doc['effective_to']):return 'after_selected_effective_end'
    return 'within_declared_inclusive_window' if doc['effective_to'] is not None else 'after_start_end_unknown'


def _client(r):
    v=r.data.get('client')
    if v is None:return None
    obj(v, ('source_reference','excerpt'), ('regime','okved','foreign_trade','revenue','employees','name'))
    ref=sid(v['source_reference']);r.literal('/client/excerpt',v['excerpt'],ref)
    for k in ('regime','name'):
        if k in v:r.literal('/client/'+k,v[k],ref)
    if 'okved' in v:
        for i,x in enumerate(strings(v['okved'],50)):r.literal('/client/okved/'+str(i),x,ref)
    if 'foreign_trade' in v:
        enum(v['foreign_trade'],('yes','no','unknown'))
    for k,u in [('revenue','RUB'),('employees','count')]:
        if k in v:
            number=r.q(v[k],'/client/'+k,u)
            if k=='employees' and number.denominator!=1:fail('whole_employee_count_required')
    return deepcopy(v)


def _condition(r,v,path,client,rule_reference):
    obj(v, ('field','operator','expected'), ())
    field=enum(v['field'],('regime','okved','foreign_trade','revenue','employees'))
    op=v['operator']; actual=None if client is None else client.get(field)
    if field in ('revenue','employees'):
        enum(op,('lt','lte','gt','gte','eq'))
        if v['expected'].get('source_reference')!=rule_reference:fail('condition_threshold_document_source_mismatch')
        bound=r.q(v['expected'],path+'/expected','RUB' if field=='revenue' else 'count')
        if actual is None:return None
        number=Fraction(dec(actual['value']))
        return {'lt':number<bound,'lte':number<=bound,'gt':number>bound,'gte':number>=bound,'eq':number==bound}[op]
    enum(op,('eq','in','prefix'))
    if op=='prefix' and field!='okved':fail('prefix_only_for_selected_OKVED_text')
    expected=strings(v['expected'],50) if op=='in' else text(v['expected'],300)
    if field!='foreign_trade':
        for j,item in enumerate(expected if type(expected)is list else [expected]):
            r.literal(path+'/expected'+('/'+str(j) if type(expected)is list else ''),item,rule_reference)
    if actual is None or actual=='unknown':return None
    values=actual if field=='okved' else [actual]
    if op=='eq':return any(x==expected for x in values)
    if op=='in':return any(x in expected for x in values)
    return any(x==expected or x.startswith(expected+'.') for x in values)


def law_monitoring(r):
    obj(r.data,('as_of','jurisdiction','mode'),('client','applicability_date','documents','changes','source_conflicts'))
    mode=enum(r.data['mode'],('questions','review')); client=_client(r); docs,byid=documents(r)
    at=r.data.get('applicability_date')
    if at is not None:day(at)
    reviewed=[]
    for i,v in enumerate(seq(r.data.get('changes',[]),100)):
        obj(v,('id','document_id','topic','summary','conditions','proposed_action'),('owner','target_date','related_document_ids'))
        identifier=sid(v['id']); doc=byid.get(v['document_id'])
        if doc is None:fail('change_document_not_selected')
        for k in ('topic','summary','proposed_action'):text(v[k])
        if 'owner'in v:text(v['owner'],1000)
        if v.get('target_date') is not None:day(v['target_date'])
        states=[_condition(r,x,f'/changes/{i}/conditions/{j}',client,doc['source_reference']) for j,x in enumerate(seq(v['conditions'],30))]
        applicable=False if False in states else None if None in states or not states else True
        if applicable is None:r.gap('client_conditions_not_established',identifier)
        if not states:r.gap('no_selected_client_conditions',identifier)
        if doc['kind'] in ('bill','news'):r.gap('proposal_or_news_not_enacted_rule',identifier)
        if doc['kind']=='letter':r.gap('department_letter_is_not_statutory_norm',identifier)
        related=strings(v.get('related_document_ids',[]),100)
        if any(x not in byid for x in related):fail('related_document_not_selected')
        reviewed.append({**deepcopy(v),'document_kind':doc['kind'],'document_metadata':deepcopy(doc),'condition_results':states,'selected_client_conditions_match':applicable,'temporal_status':temporal(doc,at),'legal_applicability_established':False})
    if len({x['id'] for x in reviewed})!=len(reviewed):fail('duplicate_change_id')
    conflicts=[]
    for v in seq(r.data.get('source_conflicts',[]),100):
        obj(v,('id','document_ids','issue'),('proposed_follow_up',))
        linked=strings(v['document_ids'],100)
        if len(linked)<2 or any(x not in byid for x in linked):fail('conflict_selected_documents_required')
        text(v['issue']);conflicts.append(deepcopy(v));r.gap('unresolved_selected_source_conflict',v['id'])
    # Multiple selected entries on one topic remain visible, not automatically resolved by newest date.
    topics={}
    for v in reviewed:
        topics.setdefault(v['topic'],[]).append(v['id'])
    duplicate_topics=[{'topic':k,'change_ids':v} for k,v in topics.items() if len(v)>1]
    if duplicate_topics:r.gap('multiple_selected_positions_need_comparison')
    if not reviewed:r.gap('change_records_not_selected')
    if at is None:r.gap('applicability_date_not_selected')
    return {'mode':mode,'client':client,'applicability_date':at,'documents':docs,'changes':reviewed,'source_conflicts':conflicts,'topic_comparison':duplicate_topics,'weekly_update_status':'host_check_receipt_not_supplied_to_pure_tool','complete_rule_chain_established':False,'questions':['select_client_scope','select_dated_source_chain','select_applicability_date'] if mode=='questions' else []}


def tax_accounting_method(r):
    obj(r.data,('as_of','jurisdiction','mode'),('client','policy_period','documents','choices','required_topics','vat_cost_share','registers','branch_method','general_provisions'))
    mode=enum(r.data['mode'],('questions','draft','review'));client=_client(r);docs,byid=documents(r)
    period=r.data.get('policy_period')
    if period is not None:
        obj(period,('start','end'))
        if day(period['end'])<day(period['start']):fail('inverted_policy_period')
    choices=[]
    for i,v in enumerate(seq(r.data.get('choices',[]),100)):
        obj(v,('id','topic','text','authorship','trigger'),('document_id','record','requested_from','selected_start_constraint','consequences'))
        identifier=sid(v['id']);enum(v['topic'],TOPICS);enum(v['authorship'],('proposed_draft','selected_existing'));text(v['text'])
        enum(v['trigger'],('method_change','legislation_change','new_activity','initial','unknown'))
        if v['authorship']=='selected_existing':
            rec=r.record(v.get('record'),f'/choices/{i}/record');r.literal(f'/choices/{i}/text',v['text'],rec['source_reference'])
        elif 'record'in v:r.record(v['record'],f'/choices/{i}/record')
        doc=byid.get(v.get('document_id'))
        if 'document_id'in v and doc is None:fail('policy_document_not_selected')
        if doc is None:r.gap('choice_rule_not_selected',identifier)
        requested=v.get('requested_from')
        if requested is not None:day(requested)
        basis=v.get('selected_start_constraint');status='start_constraint_not_selected'
        if basis is not None:
            obj(basis,('kind','date','source_reference','excerpt'))
            enum(basis['kind'],('not_before_date','period_start','selected_date'))
            day(basis['date']);r.date_literal(f'/choices/{i}/selected_start_constraint/date',basis['date'],basis['source_reference']);r.literal(f'/choices/{i}/selected_start_constraint/excerpt',basis['excerpt'],basis['source_reference'])
            if requested is None:status='proposed_start_not_selected'
            elif basis['kind']=='not_before_date':status='matches_selected_date_constraint' if day(requested)>=day(basis['date']) else 'conflicts_with_selected_date_constraint'
            else:status='matches_selected_date_constraint' if requested==basis['date'] else 'conflicts_with_selected_date_constraint'
        if status!='matches_selected_date_constraint':r.gap(status,identifier)
        if 'consequences'in v:text(v['consequences'])
        choices.append({**deepcopy(v),'start_review':status,'rule_temporal_status':temporal(doc,requested) if doc else 'rule_not_selected','approval_status':'proposed_not_approved'})
    if len({x['id'] for x in choices})!=len(choices):fail('duplicate_policy_choice_id')
    required=strings(r.data.get('required_topics',[]),len(TOPICS))
    if any(x not in TOPICS for x in required):fail('unsupported_policy_topic')
    absent=[x for x in required if not any(c['topic']==x for c in choices)]
    for x in absent:r.gap('selected_required_policy_topic_missing',x)
    ratio=None;v=r.data.get('vat_cost_share')
    if v is not None:
        obj(v,('period_start','period_end','scope','numerator','denominator','threshold','comparison','document_id','cost_scope_note'),('direct_exempt_input_vat',))
        if day(v['period_end'])<day(v['period_start']):fail('inverted_cost_period')
        enum(v['scope'],('aggregate_expenses_for_selected_period',));enum(v['comparison'],('lt','lte'))
        if v['document_id'] not in byid:fail('VAT_cost_rule_not_selected')
        if v['threshold'].get('source_reference')!=byid[v['document_id']]['source_reference']:fail('VAT_threshold_document_source_mismatch')
        numerator=r.q(v['numerator'],'/vat_cost_share/numerator','RUB');denominator=r.q(v['denominator'],'/vat_cost_share/denominator','RUB')
        threshold=r.q(v['threshold'],'/vat_cost_share/threshold','ratio',high=Fraction(1))
        if numerator>denominator:fail('exempt_cost_exceeds_selected_total')
        if denominator==0:
            share=None;within=None;status='undefined_zero_selected_total';r.gap(status)
        else:
            share=numerator/denominator;within=share<=threshold if v['comparison']=='lte' else share<threshold;status='conditional_arithmetic_only'
        if 'direct_exempt_input_vat'in v:r.q(v['direct_exempt_input_vat'],'/vat_cost_share/direct_exempt_input_vat','RUB')
        text(v['cost_scope_note'])
        ratio={**deepcopy(v),'share':None if share is None else exact(share),'within_selected_threshold':within,'status':status,'comparison_operands':{'numerator':exact(numerator),'denominator':exact(denominator),'threshold':exact(threshold)},'input_VAT_deductibility_determined':False,'separate_accounting_waiver_determined':False,'rule_temporal_status':temporal(byid[v['document_id']],v['period_end'])}
    registers=[]
    for v in seq(r.data.get('registers',[]),100):
        obj(v,('id','purpose','fields','proposed_procedure'),('owner',))
        sid(v['id']);text(v['purpose']);strings(v['fields'],100);text(v['proposed_procedure']);registers.append(deepcopy(v))
    for k in ('general_provisions','branch_method'):
        if k in r.data:text(r.data[k])
    if not choices:r.gap('policy_choices_not_selected')
    return {'mode':mode,'client':client,'policy_period':deepcopy(period),'general_provisions':r.data.get('general_provisions'),'documents':docs,'choices':choices,'selected_required_topics':required,'missing_selected_topics':absent,'vat_cost_share':ratio,'registers':registers,'branch_method':r.data.get('branch_method'),'change_timing_scope':'trigger_and_selected_rule_specific_not_blanket_new_year','questions':['select_actual_policy_scope','select_method_and_change_trigger','select_source_and_start_constraint'] if mode=='questions' else []}


def client_engagement(r):
    obj(r.data,('as_of','jurisdiction','mode'),('brief','parties','clauses','required_topics','fee','representation_date','power','quality_checks','documents'))
    mode=enum(r.data['mode'],('questions','draft','review'));docs,byid=documents(r)
    brief=r.data.get('brief')
    if brief is not None:
        obj(brief,('text','source_reference'));r.literal('/brief/text',brief['text'],brief['source_reference'])
    parties=[]
    for i,v in enumerate(seq(r.data.get('parties',[]),20)):
        obj(v,('role','name','source_reference','excerpt'),('identifier',))
        enum(v['role'],('client','consultant','representative'));r.literal(f'/parties/{i}/name',v['name'],v['source_reference']);r.literal(f'/parties/{i}/excerpt',v['excerpt'],v['source_reference'])
        if 'identifier'in v:r.literal(f'/parties/{i}/identifier',v['identifier'],v['source_reference'])
        parties.append(deepcopy(v))
    clauses=[];topicmap={}
    for i,v in enumerate(seq(r.data.get('clauses',[]),100)):
        obj(v,('id','topic','text','authorship'),('record','document_id','proposed_follow_up'))
        identifier=sid(v['id']);enum(v['topic'],CLAUSES);enum(v['authorship'],('proposed_draft','selected_existing'));text(v['text'])
        if v['authorship']=='selected_existing':
            rec=r.record(v.get('record'),f'/clauses/{i}/record');r.literal(f'/clauses/{i}/text',v['text'],rec['source_reference'])
        elif 'record'in v:r.record(v['record'],f'/clauses/{i}/record')
        if 'document_id'in v and v['document_id'] not in byid:fail('clause_document_not_selected')
        if 'proposed_follow_up'in v:text(v['proposed_follow_up'])
        topicmap.setdefault(v['topic'],[]).append(identifier)
        clauses.append({**deepcopy(v),'review_status':'proposed_wording_requires_review' if v['authorship']=='proposed_draft' else 'selected_wording_only_not_legal_clearance'})
    if len({x['id'] for x in clauses})!=len(clauses):fail('duplicate_engagement_clause_id')
    required=strings(r.data.get('required_topics',list(REVIEW_TOPICS)),len(CLAUSES))
    if any(x not in CLAUSES for x in required):fail('unsupported_contract_review_topic')
    missing=[x for x in required if x not in topicmap]
    for x in missing:r.gap('selected_review_topic_not_documented',x)
    conflicts=[{'topic':k,'clause_ids':v} for k,v in topicmap.items() if len(v)>1]
    if conflicts:r.gap('multiple_clauses_on_topic_require_comparison')
    fee=r.data.get('fee')
    if fee is not None:
        obj(fee,('amount','price_basis','tax_treatment'),('vat_rate',))
        r.q(fee['amount'],'/fee/amount','RUB');enum(fee['price_basis'],('net','gross','not_selected'));text(fee['tax_treatment'])
        if 'vat_rate'in fee:r.q(fee['vat_rate'],'/fee/vat_rate','ratio',high=Fraction(1))
    at=r.data.get('representation_date')
    if at is not None:day(at)
    power=r.data.get('power');powerout=None
    if power is not None:
        obj(power,('form','identifier','principal','representative','valid_from','valid_to','power_ids','requested_power_ids','record'),('issued_at','status_record'))
        enum(power['form'],('paper','MChD','unknown'));rec=r.record(power['record'],'/power/record')
        for k in ('identifier','principal','representative'):r.literal('/power/'+k,power[k],rec['source_reference'])
        for k in ('issued_at','valid_from','valid_to'):
            if power.get(k) is not None:day(power[k]);r.date_literal('/power/'+k,power[k],rec['source_reference'])
        if power['valid_from'] and power['valid_to'] and day(power['valid_to'])<day(power['valid_from']):fail('inverted_power_window')
        if power.get('issued_at') is not None:
            if day(power['issued_at'])>r.as_of:fail('power_issue_after_information_cutoff')
            if power['valid_from'] is not None and day(power['valid_from'])<day(power['issued_at']):r.gap('selected_power_chronology_requires_review')
        powers=strings(power['power_ids'],100);requested=strings(power['requested_power_ids'],100)
        for i,value in enumerate(powers):r.literal('/power/power_ids/'+str(i),value,rec['source_reference'])
        absent=[x for x in requested if x not in powers]
        window=None
        if at is not None and power['valid_from'] is not None and power['valid_to'] is not None:window=day(power['valid_from'])<=day(at)<=day(power['valid_to'])
        else:r.gap('power_date_window_not_established')
        status='status_record_not_selected';sr=power.get('status_record')
        if sr is not None:
            obj(sr,('status','recorded_at','source_reference','excerpt'));enum(sr['status'],('active','revoked','unknown'));r.record({k:sr[k] for k in ('recorded_at','source_reference','excerpt')},'/power/status_record');status=sr['status']
            if power.get('issued_at') is not None and day(sr['recorded_at'])<day(power['issued_at']):r.gap('selected_power_chronology_requires_review')
        if status!='active':r.gap('power_registry_or_revocation_status_not_clear')
        if absent:r.gap('requested_power_ids_not_in_selected_record')
        if window is False:r.gap('representation_outside_selected_power_window')
        powerout={**deepcopy(power),'selected_ids_missing':absent,'within_declared_inclusive_window':window,'selected_status':status,'scope_comparison':'exact_identifier_membership_not_legal_interpretation','authority_established':False,'signature_validation_performed':False,'registry_lookup_performed':False}
    elif 'power_of_attorney'in required:r.gap('power_record_not_selected')
    quality=[]
    for i,v in enumerate(seq(r.data.get('quality_checks',[]),100)):
        obj(v,('id','check','proposed_follow_up'),('owner','record'))
        sid(v['id']);text(v['check']);text(v['proposed_follow_up'])
        if 'owner'in v:text(v['owner'],1000)
        if 'record'in v:r.record(v['record'],f'/quality_checks/{i}/record')
        quality.append(deepcopy(v))
    return {'mode':mode,'brief':deepcopy(brief),'parties':parties,'documents':docs,'clauses':clauses,'selected_required_topics':required,'missing_selected_topics':missing,'clause_topic_conflicts':conflicts,'fee':deepcopy(fee),'representation_date':at,'power_review':powerout,'quality_checks':quality,'contract_confidentiality_scope':'contractual_terms_not_automatic_tax_authority_secrecy_under_Article102','professional_care_scope':'no_outcome_guarantee_does_not_excuse_unprofessional_services','contract_validity_established':False,'questions':['select_subject_and_deliverable','select_inputs_deadlines_price','select_confidentiality_care_and_representation_scope'] if mode=='questions' else []}


def _run(function,data):
    if function not in FUNCTIONS:fail('unknown_tax_practice_function')
    from .core import common, reject_proposed_authority, strict_snapshot
    reject_proposed_authority(data);reject_known_secret_material(data);common(data)
    data,_=strict_snapshot(data)
    with localcontext(Context(prec=180)):
        r=Reader(data)
        try:result=globals()[function](r)
        except (KeyError,AttributeError,TypeError,IndexError):fail('invalid_tax_practice_structure')
        result.update(as_of=data['as_of'],jurisdiction='RU',assisted_draft=True,evidence_gaps=r.gaps,source_semantics_verified=False,current_legal_applicability_verified=False,analysis_only=True)
    return result,r


def execute(function,data):
    return _run(function,data)[0]


def input_units(function,data):
    return _run(function,data)[1].units


def selected_texts(function,data):
    return _run(function,data)[1].texts

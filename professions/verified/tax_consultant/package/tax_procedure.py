"""Selected-rule tax procedure arithmetic and drafts; no external operations.

Fractions preserve finite input arithmetic and inequalities. Decimal180 only
renders derived numbers. Source occurrence does not establish legal meaning.
"""
from copy import deepcopy
from datetime import date,timedelta
from calendar import monthrange
from decimal import Decimal,Context,localcontext,DecimalException
from fractions import Fraction as F
import re
from .privacy import reject_known_secret_material

FUNCTIONS=('tax_audit_support','objections_appeal','penalties_mitigation','ens_dispute')
CTX=Context(prec=180,Emin=-999999,Emax=999999)
NUM=re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z')

def fail(code):raise ValueError(code)
def obj(x,required=(),optional=()):
    if type(x) is not dict or set(required)-set(x) or set(x)-set(required)-set(optional):fail('bounded_object_fields_required')
    return x
def rows(x,maximum=40,minimum=0):
    if type(x) is not list or not minimum<=len(x)<=maximum:fail('bounded_array_required')
    return x
def text(x,maximum=6000):
    if type(x) is not str or not x.strip() or len(x)>maximum or any(ord(c)<32 and c not in '\n\r\t' for c in x):fail('bounded_nonempty_text_required')
    return x
def enum(x,values):
    if type(x) is not str or x not in values:fail('unsupported_selected_model_or_option')
    return x
def iso(x):
    if type(x) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',x):fail('ISO_date_required')
    try:date.fromisoformat(x)
    except ValueError:fail('ISO_date_required')
    return x
def unique(x):
    if len({text(v['id'],160) for v in x})!=len(x):fail('duplicate_identity')
def serial(x):
    if isinstance(x,F):
        with localcontext(CTX):return '0' if not x else str((Decimal(x.numerator)/Decimal(x.denominator)).normalize())
    if type(x) is dict:return {k:serial(v) for k,v in x.items()}
    if type(x) is list:return [serial(v) for v in x]
    return x

class Read:
    def __init__(self,data):
        self.asof=iso(data['as_of'])
        if data['jurisdiction']!='RU':fail('RU_jurisdiction_required')
        self.units={};self.literals={};self.gaps=[]
    def gap(self,kind,path=''):
        row=dict(kind=kind,path=path)
        if row not in self.gaps:self.gaps.append(row)
    def literal(self,v,p,source):
        text(v,20000);text(source,80);self.literals[p]=dict(text=v,source_references=[source])
    def fact_date(self,v,p,source,actual=True):
        iso(v);self.literal(v,p,source)
        self.literals[p]['date_format']='iso_or_dmy_dot'
        if actual and v>self.asof:fail('actual_fact_after_information_cutoff')
        return v
    def q(self,x,p,unit,lo=None,hi=None,integer=False,cutoff=None):
        obj(x,('value','unit','source_reference'),('observed_date',));v=x['value']
        if type(v) is not str or len(v)>170 or not NUM.fullmatch(v):fail('exact_decimal_string_required')
        if 'e' in v.lower() and abs(int(v.lower().split('e')[1]))>100:fail('numeric_exponent_bound')
        d=Decimal(v)
        if not d.is_finite() or len(d.as_tuple().digits)>40 or abs(d.as_tuple().exponent)>140 or d and not -100<=d.adjusted()<=100:fail('numeric_precision_bound')
        n=F(d)
        if x['unit']!=unit:fail('explicit_supported_unit_required')
        if lo is not None and n<lo or hi is not None and n>hi or integer and n.denominator!=1:fail('numeric_domain_bound')
        bound=min(self.asof,iso(cutoff)) if cutoff else self.asof
        text(x['source_reference'],80);spec=dict(unit=unit,effective_not_after=bound,published_not_after=self.asof,source_references=[x['source_reference']])
        if 'observed_date' in x:
            observed=self.fact_date(x['observed_date'],p+'/observed_date',x['source_reference'])
            if observed>bound:fail('actual_observation_after_selected_cutoff')
            spec['effective_date']=observed
        self.units[p+'/value']=spec
        if len(self.units)>700:fail('numeric_budget_700')
        return n
    def note(self,x,p):
        obj(x,('text','source_reference'));self.literal(x['text'],p+'/text',x['source_reference']);return deepcopy(x)
    def rule(self,x,p,event_date=None):
        obj(x,('id','kind','document_identity','edition','publication_date','effective_from','effective_to','clause','scope','excerpt','source_reference'))
        text(x['id'],160);enum(x['kind'],('enacted_norm','official_guidance','case_record','selected_method','calendar'))
        for k in ('document_identity','edition','clause','scope','excerpt'):self.literal(x[k],p+'/'+k,x['source_reference'])
        pub=self.fact_date(x['publication_date'],p+'/publication_date',x['source_reference']);start=self.fact_date(x['effective_from'],p+'/effective_from',x['source_reference'],False)
        end=self.fact_date(x['effective_to'],p+'/effective_to',x['source_reference'],False) if x['effective_to'] is not None else None
        if end and end<start:fail('rule_effective_window_inverted')
        event=event_date or self.asof
        if event<start or end and event>end:self.gap('selected_rule_outside_declared_window',p)
        if pub>event:self.gap('selected_rule_published_after_event_manual_retroactivity_review',p)
        if x['kind']!='enacted_norm':self.gap('selected_source_is_not_enacted_norm',p)
        return deepcopy(x)

def calendar(r,x,p):
    obj(x,('basis','days'));r.rule(x['basis'],p+'/basis');out={}
    for i,z in enumerate(rows(x['days'],740,1)):
        q=p+'/days/'+str(i);obj(z,('date','state','source_reference'));day=r.fact_date(z['date'],q+'/date',z['source_reference'],False);enum(z['state'],('working','nonworking','unknown'))
        if day in out:fail('duplicate_calendar_date')
        out[day]=z['state']
    ordered=sorted(out)
    if (date.fromisoformat(ordered[-1])-date.fromisoformat(ordered[0])).days+1!=len(out):fail('calendar_must_classify_every_day_in_declared_window')
    return out

def add_months(start,n):
    index=start.year*12+start.month-1+n;year,month=divmod(index,12)
    return date(year,month+1,min(start.day,monthrange(year,month+1)[1]))

def events(r,values):
    result=[]
    for i,x in enumerate(rows(values,16)):
        p='/events/'+str(i);obj(x,('id','role','trigger','event_date','source_reference','excerpt','rule','duration','count_start','roll','owner','status'),('service','calendar','extension','suspensions'))
        text(x['id'],160);enum(x['role'],('desk_vat_end','desk_other_end','field_audit_end','requirement_reply','explanations','objections','appeal','other_selected_deadline'));enum(x['trigger'],('declaration_filed','decision_issued','requirement_received','act_received','decision_served','other_selected_event'))
        r.literal(x['excerpt'],p+'/excerpt',x['source_reference'])
        expected_trigger={'desk_vat_end':'declaration_filed','desk_other_end':'declaration_filed','field_audit_end':'decision_issued','requirement_reply':'requirement_received','explanations':'requirement_received','objections':'act_received','appeal':'decision_served'}.get(x['role'])
        if expected_trigger and x['trigger']!=expected_trigger:fail('event_role_trigger_conflict')
        start=r.fact_date(x['event_date'],p+'/event_date',x['source_reference']);rule=r.rule(x['rule'],p+'/rule',start);text(x['owner']);text(x['status'])
        enum(x['count_start'],('next_day','include_event'));enum(x['roll'],('none','next_working_day'));unit=x['duration']['unit'];enum(unit,('calendar_month','calendar_day','working_day'));duration=r.q(x['duration'],p+'/duration',unit,1,60 if unit=='calendar_month' else 730,True)
        selected=duration;extension=None
        if 'extension' in x:
            z=obj(x['extension'],('date','replacement_duration','rule','source_reference','excerpt'));r.fact_date(z['date'],p+'/extension/date',z['source_reference']);r.literal(z['excerpt'],p+'/extension/excerpt',z['source_reference']);r.rule(z['rule'],p+'/extension/rule',z['date']);selected=r.q(z['replacement_duration'],p+'/extension/replacement_duration',unit,duration,60 if unit=='calendar_month' else 730,True);extension=deepcopy(z)
        service=None
        if 'service' in x:
            z=obj(x['service'],('state',),('date','method','record_identity','source_reference','excerpt'));enum(z['state'],('provided','missing','unknown'));service=deepcopy(z)
            if z['state']=='provided':
                for k in ('method','record_identity','excerpt'):r.literal(z[k],p+'/service/'+k,z['source_reference'])
                r.fact_date(z['date'],p+'/service/date',z['source_reference'])
                if z['date']!=start:r.gap('service_date_differs_from_selected_trigger',p)
            else:r.gap('service_evidence_missing_or_unknown',p)
        elif x['trigger'] in ('requirement_received','act_received','decision_served'):r.gap('service_evidence_missing_or_unknown',p)
        cal=calendar(r,x['calendar'],p+'/calendar') if 'calendar' in x else {}
        day=date.fromisoformat(start);raw=None;problem=None
        if unit=='calendar_month':
            if x['count_start']!='next_day':fail('month_model_requires_event_corresponding_date_next_day_rule')
            raw=add_months(day,int(selected))
        elif unit=='calendar_day':raw=day+timedelta(days=int(selected)-(x['count_start']=='include_event'))
        else:
            cursor=day+timedelta(days=x['count_start']=='next_day');left=int(selected)
            for _ in range(741):
                state=cal.get(cursor.isoformat())
                if state not in ('working','nonworking'):problem='working_calendar_missing_or_unknown';break
                left-=state=='working'
                if not left:raw=cursor;break
                cursor+=timedelta(days=1)
            if raw is None and problem is None:problem='deadline_calendar_resource_limit'
        pauses=[]
        for j,z in enumerate(rows(x.get('suspensions',[]),12)):
            pp=p+'/suspensions/'+str(j);obj(z,('start_date','end_date','source_reference','excerpt','rule'))
            if x['role']!='field_audit_end' or unit=='working_day':fail('suspension_model_only_selected_field_calendar_deadline')
            a=r.fact_date(z['start_date'],pp+'/start_date',z['source_reference']);b=r.fact_date(z['end_date'],pp+'/end_date',z['source_reference']);r.literal(z['excerpt'],pp+'/excerpt',z['source_reference']);r.rule(z['rule'],pp+'/rule',a)
            if b<a or a<=start:fail('suspension_chronology_invalid')
            pauses.append((date.fromisoformat(a),date.fromisoformat(b)))
        pauses.sort()
        if any(b>=c for (a,b),(c,d) in zip(pauses,pauses[1:])):fail('suspensions_overlap')
        base_due=raw
        if raw is not None:
            for a,b in pauses:
                if a<=raw:raw+=timedelta(days=(b-a).days+1)
        unshifted=raw;due=raw
        if due is not None and x['roll']=='next_working_day':
            for _ in range(741):
                state=cal.get(due.isoformat())
                if state=='working':break
                if state!='nonworking':due=None;problem='working_calendar_missing_or_unknown';break
                due+=timedelta(days=1)
            else:due=None;problem='deadline_calendar_resource_limit'
        if problem:r.gap(problem,p)
        result.append(dict(id=x['id'],role=x['role'],trigger=x['trigger'],event_date=start,source_reference=x['source_reference'],excerpt=x['excerpt'],selected_rule=rule,selected_duration=selected,duration_unit=unit,count_start=x['count_start'],roll=x['roll'],base_candidate_date=None if base_due is None else base_due.isoformat(),candidate_before_roll=None if unshifted is None else unshifted.isoformat(),candidate_deadline=None if due is None else due.isoformat(),calculation_status='conditional_candidate' if due is not None else 'unresolved_calendar',owner=x['owner'],provided_status=x['status'],service=service,extension=extension,suspension_records=deepcopy(x.get('suspensions',[])),legal_deadline_established=False))
    unique(result);return result

def rounded(r,value,x,p):
    if x is None:return dict(exact_amount=value,rounded_amount=None,rounding=None)
    obj(x,('increment','mode','rule'));step=r.q(x['increment'],p+'/increment','RUB',F(1,10**100));mode=enum(x['mode'],('half_up','floor','ceiling'));r.rule(x['rule'],p+'/rule');ratio=value/step;floor=ratio.numerator//ratio.denominator
    n=floor+(ratio-floor>=F(1,2)) if mode=='half_up' else floor if mode=='floor' else -(-ratio.numerator//ratio.denominator)
    return dict(exact_amount=value,rounded_amount=n*step,rounding=deepcopy(x))

def fine(r,x,p='/fine'):
    obj(x,('model','violation_date','source_reference','excerpt','rule','parameters'),('repeat','mitigation','exemption','exemption_review','rounding'))
    model=enum(x['model'],('standard_119','selected_122_rate','standard_126_per_document'));when=r.fact_date(x['violation_date'],p+'/violation_date',x['source_reference']);r.literal(x['excerpt'],p+'/excerpt',x['source_reference']);r.rule(x['rule'],p+'/rule',when);a=x['parameters'];components={}
    if model=='standard_119':
        obj(a,('unpaid_tax','months','monthly_rate','cap_ratio','minimum'));amount=r.q(a['unpaid_tax'],p+'/parameters/unpaid_tax','RUB',0);months=r.q(a['months'],p+'/parameters/months','month',1,120,True);rate=r.q(a['monthly_rate'],p+'/parameters/monthly_rate','ratio',0,1);cap=r.q(a['cap_ratio'],p+'/parameters/cap_ratio','ratio',0,1);minimum=r.q(a['minimum'],p+'/parameters/minimum','RUB',0)
        base=max(minimum,min(amount*rate*months,amount*cap));components=dict(unpaid_tax=amount,months=months,uncapped_amount=amount*rate*months,cap_amount=amount*cap,minimum=minimum)
    elif model=='selected_122_rate':
        obj(a,('unpaid_tax','rate','mental_state'));amount=r.q(a['unpaid_tax'],p+'/parameters/unpaid_tax','RUB',0);rate=r.q(a['rate'],p+'/parameters/rate','ratio',0,1);enum(a['mental_state'],('provided_intentional','provided_negligent','unknown'));base=amount*rate;components=dict(unpaid_tax=amount,selected_rate=rate,provided_mental_state=a['mental_state'])
        r.gap('offence_and_mental_state_not_established',p)
    else:
        obj(a,('documents','per_document'));count=r.q(a['documents'],p+'/parameters/documents','count',0,1000000,True);rate=r.q(a['per_document'],p+'/parameters/per_document','RUB',0);base=count*rate;components=dict(documents=count,per_document=rate)
    repeated=base
    if 'repeat' in x:
        z=obj(x['repeat'],('multiplier','rule','evidence'));r.rule(z['rule'],p+'/repeat/rule',when);r.note(z['evidence'],p+'/repeat/evidence');repeated*=r.q(z['multiplier'],p+'/repeat/multiplier','ratio',1,100)
        r.gap('repeat_offence_qualification_not_established',p)
    reduced=repeated;divisor=None
    if 'mitigation' in x:
        z=obj(x['mitigation'],('divisor','minimum_divisor','maximum_divisor','rule','circumstances'));r.rule(z['rule'],p+'/mitigation/rule',when);low=r.q(z['minimum_divisor'],p+'/mitigation/minimum_divisor','ratio',1);high=None if z['maximum_divisor'] is None else r.q(z['maximum_divisor'],p+'/mitigation/maximum_divisor','ratio',low);divisor=r.q(z['divisor'],p+'/mitigation/divisor','ratio',low,high);reduced=repeated/divisor
        for i,n in enumerate(rows(z['circumstances'],12,1)):r.note(n,p+'/mitigation/circumstances/'+str(i))
        r.gap('mitigation_is_proposed_not_granted',p)
    exemption=None
    if 'exemption_review' in x:
        z=obj(x['exemption_review'],('state','analysis'),('basis',));enum(z['state'],('not_selected','potential','selected_for_separate_review'));text(z['analysis']);exemption=deepcopy(z)
        if 'basis' in z:r.rule(z['basis'],p+'/exemption_review/basis',when)
        if z['state']!='not_selected':r.gap('exemption_requires_separate_applicability_review_conditional_fine_only',p)
    selected_exemption=None;after_exemption=reduced
    if 'exemption' in x:
        if model!='standard_119':fail('selected_p3_exemption_only_standard119')
        z=obj(x['exemption'],('model','declared_tax_payable','criteria_basis','temporal_state','analysis'),('temporal_basis',));enum(z['model'],('selected_119_p3_no_declared_tax_due',));enum(z['temporal_state'],('selected_window','unknown_or_conflicted'));text(z['analysis'])
        declared=r.q(z['declared_tax_payable'],p+'/exemption/declared_tax_payable','RUB',0);r.rule(z['criteria_basis'],p+'/exemption/criteria_basis',when)
        temporal=None
        if 'temporal_basis' in z:temporal=r.rule(z['temporal_basis'],p+'/exemption/temporal_basis',when)
        def in_window(b):return b['effective_from']<=when and (b['effective_to'] is None or when<=b['effective_to'])
        known=z['temporal_state']=='selected_window' and temporal is not None and in_window(temporal) and in_window(z['criteria_basis'])
        if declared!=0:status='criterion_not_met_declared_tax_payable_positive';after_exemption=reduced
        elif known:status='conditional_exemption_under_selected_model';after_exemption=F()
        else:status='temporal_basis_unknown_or_conflicted';after_exemption=None;r.gap('exemption_temporal_basis_unknown_not_automatic_zero',p+'/exemption')
        selected_exemption=dict(provided=deepcopy(z),declared_tax_payable=declared,status=status,actual_exemption_granted=False)
    r.gap('selected_standard_fine_not_official_assessment',p)
    return dict(model=model,violation_date=when,selected_rule=deepcopy(x['rule']),parameters=deepcopy(a),calculation_components=components,base_conditional_fine=base,after_selected_repeat_multiplier=repeated,selected_mitigation_divisor=divisor,conditional_after_mitigation=reduced,amount=rounded(r,reduced,x.get('rounding'),p+'/rounding'),repeat=deepcopy(x.get('repeat')),mitigation=deepcopy(x.get('mitigation')),exemption_review=exemption,selected_exemption=selected_exemption,conditional_after_selected_exemption=after_exemption,final_conditional_amount=None if after_exemption is None else rounded(r,after_exemption,x.get('rounding'),p+'/rounding'),penalty_imposed=False)

def accrual(r,x,p,kind):
    obj(x,('coverage_from','coverage_to','source_reference','periods'),('cap','rounding'))
    start=r.fact_date(x['coverage_from'],p+'/coverage_from',x['source_reference']);end=r.fact_date(x['coverage_to'],p+'/coverage_to',x['source_reference'])
    if end<start or (date.fromisoformat(end)-date.fromisoformat(start)).days>3659:fail('accrual_window_invalid')
    total=F();out=[];occupied={};intervals={}
    for i,z in enumerate(rows(x['periods'],60)):
        q=p+'/periods/'+str(i);obj(z,('id','obligation_id','start_date','end_date','principal','key_rate','denominator','exclusions','basis','source_reference','excerpt'))
        text(z['id'],160);text(z['obligation_id'],160)
        for key in ('obligation_id','excerpt'):r.literal(z[key],q+'/'+key,z['source_reference'])
        a=r.fact_date(z['start_date'],q+'/start_date',z['source_reference']);b=r.fact_date(z['end_date'],q+'/end_date',z['source_reference'])
        if b<a or a<start or b>end:fail('accrual_period_outside_window')
        r.rule(z['basis'],q+'/basis',a)
        principal=r.q(z['principal'],q+'/principal','RUB',0);rate=r.q(z['key_rate'],q+'/key_rate','ratio',0,10);den=r.q(z['denominator'],q+'/denominator','day',1,100000,True);excluded=F()
        for j,e in enumerate(rows(z['exclusions'],4)):
            pp=q+'/exclusions/'+str(j);obj(e,('kind','amount','evidence'));enum(e['kind'],('ens_positive','earmarked','selected_nonaccrual','other_selected'));excluded+=r.q(e['amount'],pp+'/amount','RUB',0);r.note(e['evidence'],pp+'/evidence')
        base=max(F(),principal-excluded);days=(date.fromisoformat(b)-date.fromisoformat(a)).days+1;amount=base*rate*days/den;total+=amount
        span=set(range(date.fromisoformat(a).toordinal(),date.fromisoformat(b).toordinal()+1));key=z['obligation_id']
        if occupied.setdefault(key,set())&span:fail('accrual_period_overlap_for_obligation')
        occupied[key]|=span;intervals[key]=intervals.get(key,0)+days
        out.append(dict(id=z['id'],obligation_id=key,start_date=a,end_date=b,calendar_days=days,outstanding_principal=principal,selected_exclusions=excluded,conditional_accrual_base=base,key_rate_ratio=rate,selected_denominator_days=den,exact_amount=amount,basis=deepcopy(z['basis']),source_reference=z['source_reference'],excerpt=z['excerpt'],exclusion_records=deepcopy(z['exclusions'])))
    unique(out);window=set(range(date.fromisoformat(start).toordinal(),date.fromisoformat(end).toordinal()+1));missing={key:len(window-span) for key,span in occupied.items() if window-span}
    if not out:r.gap('accrual_period_evidence_missing',p)
    if missing:r.gap('accrual_window_has_unprovided_days_not_zero_accrual',p)
    capped=total;cap_record=None
    if 'cap' in x:
        z=obj(x['cap'],('amount','basis'));cap_value=r.q(z['amount'],p+'/cap/amount','RUB',0);r.rule(z['basis'],p+'/cap/basis',start);capped=min(total,cap_value);cap_record=deepcopy(z)
    r.gap('actual_outstanding_exclusions_rate_schedule_and_allocation_not_legally_established',p)
    return dict(kind=kind,coverage_from=start,coverage_to=end,periods=out,missing_days_by_obligation=missing,coverage_status='unprovided_periods' if missing or not out else 'complete_per_supplied_obligations',uncapped_exact_total=total,cap=cap_record,provided_period_conditional_total=capped,conditional_total=None if missing or not out else capped,amount=rounded(r,capped,x.get('rounding'),p+'/rounding'),scope='selected_outstanding_period_ledger_not_official_ENS_accrual',actual_accrual_established=False)

def request(r,x,p='/request_reply'):
    obj(x,('request_record','requested_items','provided_items','inventory','scope_analysis','extension_or_refusal','draft_text'),('interview_memo',))
    r.note(x['request_record'],p+'/request_record')
    for key in ('requested_items','provided_items','inventory'):
        for i,n in enumerate(rows(x[key],30)):r.note(n,p+'/'+key+'/'+str(i))
    for k in ('scope_analysis','extension_or_refusal','draft_text'):text(x[k],12000)
    if 'interview_memo' in x:
        z=obj(x['interview_memo'],('rights_basis','draft_notes'));r.rule(z['rights_basis'],p+'/interview_memo/rights_basis');text(z['draft_notes'],12000)
    return dict(provided=deepcopy(x),draft_only=True,request_scope_legality_established=False)

def episodes(r,values):
    out=[]
    for i,z in enumerate(rows(values,20)):
        p='/episodes/'+str(i);obj(z,('id','inspector_position','objection','norms','evidence','court_records'),('mitigation_notes',));text(z['id'],160);r.note(z['inspector_position'],p+'/inspector_position');text(z['objection'],12000)
        for j,a in enumerate(rows(z['norms'],6)):r.rule(a,p+'/norms/'+str(j))
        for j,a in enumerate(rows(z['evidence'],12)):r.note(a,p+'/evidence/'+str(j))
        for j,a in enumerate(rows(z['court_records'],6)):
            pp=p+'/court_records/'+str(j);obj(a,('case_number','court','decision_date','selected_text','source_reference','scope_analysis'))
            for k in ('case_number','court','selected_text'):r.literal(a[k],pp+'/'+k,a['source_reference'])
            r.fact_date(a['decision_date'],pp+'/decision_date',a['source_reference']);text(a['scope_analysis'])
        if 'mitigation_notes' in z:
            for t in rows(z['mitigation_notes'],12):text(t)
        out.append(dict(provided=deepcopy(z),case_identity_authenticity_or_applicability_established=False))
    unique([v['provided'] for v in out]);return out

def ens(r,x,p='/ledger'):
    obj(x,('from_date','to_date','source_reference','opening_balance','statement_balance','entries','adjustments'))
    start=r.fact_date(x['from_date'],p+'/from_date',x['source_reference']);end=r.fact_date(x['to_date'],p+'/to_date',x['source_reference'])
    if end<start:fail('ENS_window_inverted')
    opening=r.q(x['opening_balance'],p+'/opening_balance','RUB');statement=r.q(x['statement_balance'],p+'/statement_balance','RUB');total=opening;entries=[];ids=set();anchors={}
    for i,z in enumerate(rows(x['entries'],60)):
        q=p+'/entries/'+str(i);obj(z,('id','date','kind','delta','record_identity','source_reference','excerpt'));text(z['id'],160);d=r.fact_date(z['date'],q+'/date',z['source_reference'])
        if not start<=d<=end:fail('ENS_entry_outside_window')
        enum(z['kind'],('payment_credit','obligation_debit','refund_debit','offset_debit','other_selected_delta'))
        for key in ('record_identity','excerpt'):r.literal(z[key],q+'/'+key,z['source_reference'])
        amount=r.q(z['delta'],q+'/delta','RUB')
        if z['kind']=='payment_credit' and amount<0 or z['kind'] in ('obligation_debit','refund_debit','offset_debit') and amount>0:fail('ENS_kind_signed_delta_conflict')
        total+=amount;entries.append(dict(provided=deepcopy(z),delta=amount));anchors[z['record_identity']]=anchors.get(z['record_identity'],0)+1;ids.add(z['id'])
    unique([v['provided'] for v in entries]);posted=F();proposed=F();adjustments=[]
    for i,z in enumerate(rows(x['adjustments'],30)):
        q=p+'/adjustments/'+str(i);obj(z,('id','state','related_entry_id','delta','reason'),('evidence','date'));text(z['id'],160);enum(z['state'],('provided_posted','proposed'));text(z['reason'])
        if z['related_entry_id'] is not None and z['related_entry_id'] not in ids:fail('ENS_adjustment_unknown_entry')
        amount=r.q(z['delta'],q+'/delta','RUB')
        if z['state']=='provided_posted':
            n=r.note(z['evidence'],q+'/evidence');d=r.fact_date(z['date'],q+'/date',n['source_reference'])
            if not start<=d<=end:fail('ENS_posted_adjustment_outside_window')
            posted+=amount
        else:
            if 'evidence' in z:r.note(z['evidence'],q+'/evidence')
            if 'date' in z:fail('proposed_adjustment_has_actual_date')
            proposed+=amount
        adjustments.append(dict(provided=deepcopy(z),delta=amount))
    unique([v['provided'] for v in adjustments]);duplicate_anchors=[a for a,n in anchors.items() if n>1]
    if duplicate_anchors:r.gap('ENS_repeated_external_record_identity_no_automatic_dedup',p)
    actual=total+posted;candidate=actual+proposed;r.gap('ENS_ledger_not_live_FNS_balance_or_legal_refund_right',p)
    return dict(from_date=start,to_date=end,opening_balance=opening,statement_balance=statement,entries=entries,adjustments=adjustments,reconstructed_balance=actual,statement_minus_reconstructed=statement-actual,proposed_adjustment_delta=proposed,candidate_after_proposed_adjustments=candidate,repeated_external_record_identities=duplicate_anchors,balance_interpretation='positive_credit_negative_debt_on_supplied_ledger',actual_FNS_balance_established=False)

def _run(function,data):
    if function not in FUNCTIONS:fail('unknown_tax_procedure_function')
    try:
        reject_known_secret_material(data)
        with localcontext(CTX):
            common=('context','events');options={'tax_audit_support':('audit_kind','audit_record','request_reply'),'objections_appeal':('act_record','decision_record','episodes','appeal_draft'),'penalties_mitigation':('violation','fine','penalty_ledger','circumstances','request_draft'),'ens_dispute':('ledger','claim','penalty_ledger','refund_interest','request_draft')}
            obj(data,('as_of','jurisdiction','mode'),common+options[function]);r=Read(data);mode=enum(data['mode'],('questions','draft','review'));out=dict(mode=mode,context=None,events=[],questions=[])
            if 'context' in data:out['context']=text(data['context'],12000)
            if mode=='questions':
                if any(k not in ('as_of','jurisdiction','mode','context') for k in data):fail('questions_mode_has_unselected_calculations')
                out['questions']={'tax_audit_support':['select_audit_type_scope_declaration_decision_and_actual_service_records','select_event_rule_calendar_extension_suspension_and_responsible_person'],'objections_appeal':['select_act_decision_service_evidence_and_episodes','select_procedural_stage_rule_court_text_and_appendices'],'penalties_mitigation':['select_offence_date_standard_or_exemption_rule_and_evidence','select_only_needed_fine_or_actual_outstanding_penalty_ledger'],'ens_dispute':['select_ENS_statement_operations_own_obligations_and_cutoff','select_refund_offset_or_inquiry_and_bank_evidence_if_needed']}[function]
            else:
                out['events']=events(r,data.get('events',[]))
                if function=='tax_audit_support':
                    out['audit_kind']=enum(data['audit_kind'],('desk_vat','desk_other','field','unknown')) if 'audit_kind' in data else None;out['audit_record']=r.note(data['audit_record'],'/audit_record') if 'audit_record' in data else None;out['request_reply']=request(r,data['request_reply']) if 'request_reply' in data else None
                    for event in out['events']:
                        required={'desk_vat_end':'desk_vat','desk_other_end':'desk_other','field_audit_end':'field'}.get(event['role'])
                        if required and out['audit_kind']!=required:r.gap('audit_type_event_role_mismatch','/events/'+event['id'])
                elif function=='objections_appeal':
                    for k in ('act_record','decision_record'):out[k]=r.note(data[k],'/'+k) if k in data else None
                    out['episodes']=episodes(r,data.get('episodes',[]));out['appeal_draft']=None
                    if 'appeal_draft' in data:
                        z=obj(data['appeal_draft'],('stage','recipient','violated_rights','grounds','requests','appendices','pretrial_review'));enum(z['stage'],('objections','administrative_appeal','ordinary_complaint','court_preparation'));out['appeal_draft']=deepcopy(z)
                        for k in ('recipient','violated_rights','grounds','requests','pretrial_review'):text(z[k],12000)
                        for j,n in enumerate(rows(z['appendices'],30)):r.note(n,'/appeal_draft/appendices/'+str(j))
                    r.gap('pretrial_stage_service_case_identity_and_filing_format_require_selected_review','/appeal_draft')
                elif function=='penalties_mitigation':
                    out['violation']=r.note(data['violation'],'/violation') if 'violation' in data else None;out['fine']=fine(r,data['fine']) if 'fine' in data else None;out['penalty_ledger']=accrual(r,data['penalty_ledger'],'/penalty_ledger','tax_penalty') if 'penalty_ledger' in data else None;out['circumstances']=[]
                    for i,n in enumerate(rows(data.get('circumstances',[]),20)):out['circumstances'].append(r.note(n,'/circumstances/'+str(i)))
                    out['request_draft']=text(data['request_draft'],12000) if 'request_draft' in data else None
                else:
                    out['ledger']=ens(r,data['ledger']) if 'ledger' in data else None;out['claim']=None
                    if 'claim' in data:
                        z=obj(data['claim'],('action','basis','draft_text'),('requested_amount','balance_basis','bank_record'));enum(z['action'],('inquiry','refund','offset'));r.rule(z['basis'],'/claim/basis');text(z['draft_text'],12000);claim=deepcopy(z);claim.update(selected_positive_balance=None,within_selected_positive_balance=None,legal_right_established=False)
                        if 'bank_record' in z:r.note(z['bank_record'],'/claim/bank_record')
                        if 'requested_amount' in z:
                            amount=r.q(z['requested_amount'],'/claim/requested_amount','RUB',0);which=enum(z.get('balance_basis'),('statement_balance','reconstructed_balance','candidate_after_proposed_adjustments'));available=None if out['ledger'] is None else max(F(),out['ledger'][which]);claim.update(selected_positive_balance=available,within_selected_positive_balance=None if available is None else amount<=available)
                            if available is None or amount>available:r.gap('claim_amount_or_positive_balance_unresolved_or_exceeded','/claim')
                        out['claim']=claim
                    out['penalty_ledger']=accrual(r,data['penalty_ledger'],'/penalty_ledger','tax_penalty') if 'penalty_ledger' in data else None;out['refund_interest']=accrual(r,data['refund_interest'],'/refund_interest','selected_refund_interest') if 'refund_interest' in data else None;out['request_draft']=text(data['request_draft'],12000) if 'request_draft' in data else None
            if len(r.units)+len(r.literals)>900:fail('numeric_literal_budget_900')
            out.update(as_of=r.asof,jurisdiction='RU',evidence_gaps=r.gaps,analysis_only=True,arithmetic_precision='exact_rational_predicates_Decimal180_display',source_semantics_established=False,legal_applicability_established=False,filing_performed=False,payment_performed=False,signature_applied=False,representation_performed=False,network_used=False)
            return serial(out),r
    except (KeyError,TypeError,AttributeError,IndexError,DecimalException,OverflowError,ZeroDivisionError,RecursionError):raise ValueError('malformed_or_unbounded_tax_procedure_input') from None

def execute(function,data):return _run(function,deepcopy(data))[0]
def input_units(function,data):return _run(function,deepcopy(data))[1].units
def selected_texts(function,data):return _run(function,deepcopy(data))[1].literals

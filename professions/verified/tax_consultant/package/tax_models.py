"""Bounded, inert tax drafts from explicitly selected rules. No current-law defaults.

Exact Fraction arithmetic; Decimal180 is a presentation format, never a predicate.
All quantities are consumed through Read.q, also used for source callbacks.
"""
from calendar import monthrange
from datetime import date,timedelta
from decimal import Decimal, Context, localcontext, InvalidOperation
from fractions import Fraction
import json, re
from .privacy import reject_known_secret_material

FUNCTIONS=('regime_choice','transaction_structuring','individual_3ndfl')
CTX=Context(prec=180)
NUM=re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z')

def fail(code):raise ValueError(code)
def obj(x):
 if type(x) is not dict:fail('tax_object_required')
 return x
def rows(x,maximum=40,minimum=0):
 if type(x) is not list or not minimum<=len(x)<=maximum:fail('tax_collection_bound')
 return x
def text(x,limit=12000):
 if type(x) is not str or not x.strip() or len(x)>limit:fail('tax_text_required')
 return x
def choice(x,options):
 if x not in options or type(x) is not str:fail('unsupported_selected_tax_model')
 return x
def dt(x):
 text(x,10)
 try:d=date.fromisoformat(x)
 except (ValueError,TypeError):fail('tax_ISO_date_required')
 if d.isoformat()!=x:fail('tax_ISO_date_required')
 return d
def num(x):
 if type(x) is not str or len(x)>160 or not NUM.fullmatch(x):fail('tax_decimal_string_required')
 try:d=Decimal(x)
 except InvalidOperation:fail('tax_numeric_bound')
 t=d.as_tuple()
 if not d.is_finite() or abs(t.exponent)>100 or len(t.digits)>40 or (d and not -100<=d.adjusted()<=100):fail('tax_numeric_bound')
 return Fraction(d)
def fmt(x):
 if x is None:return None
 x=Fraction(x)
 with localcontext(CTX):v=Decimal(x.numerator)/Decimal(x.denominator)
 if Fraction(v)!=x:
  # A selected finite quantum must survive serialization even when a large
  # whole amount plus a tiny remainder needs more than180 significant digits.
  # Repeating rationals retain the documented Decimal180 presentation.
  denominator=x.denominator;twos=fives=0
  while denominator%2==0:twos+=1;denominator//=2
  while denominator%5==0:fives+=1;denominator//=5
  if denominator==1:
   scale=max(twos,fives);coefficient=abs(x.numerator)*2**(scale-twos)*5**(scale-fives);exponent=-scale
   while coefficient and coefficient%10==0:coefficient//=10;exponent+=1
   exact=Decimal((int(x<0),tuple(int(c) for c in str(coefficient)),exponent))
   return str(exact)
 return '0' if not v else str(v.normalize(context=CTX))
def unique(items,key='id'):
 ids=[text(obj(x).get(key),150) for x in items]
 if len(ids)!=len(set(ids)):fail('duplicate_tax_record_id')
 return ids
def bounded_json(x):
 try:s=json.dumps(x,ensure_ascii=False,allow_nan=False)
 except (TypeError,ValueError,RecursionError):fail('tax_bounded_JSON_required')
 if len(s.encode('utf8'))>2_000_000:fail('tax_proposal_size_bound')
 def walk(v,depth=0):
  if depth>30:fail('tax_nesting_bound')
  if type(v) is dict:
   for k,a in v.items():
    if type(k) is not str:fail('tax_string_keys_required')
    walk(a,depth+1)
  elif type(v) is list:
   for a in v:walk(a,depth+1)
  elif type(v) not in (str,bool,type(None)):fail('tax_numbers_require_quantity_strings')
 walk(x)

class Read:
 def __init__(self,data):
  self.data=obj(data);self.asof=dt(data.get('as_of'));self.units={};self.literals={};self.gaps=[]
  if data.get('jurisdiction')!='RU':fail('explicit_RU_jurisdiction_required')
 def literal(self,value,path,refs):
  text(value)
  if type(refs) is str:refs=[refs]
  if not refs or len(refs)!=len(set(refs)):fail('tax_source_references_required')
  for x in refs:text(x,80)
  self.literals[path]={'text':value,'source_references':refs}
  return value
 def date_literal(self,value,path,refs):
  dt(value);self.literal(value,path,refs)
  self.literals[path]['date_format']='iso_or_dmy_dot'
  return value
 def q(self,value,path,unit='RUB',low=0,high=None,cutoff=None):
  q=obj(value)
  if set(q)-{'value','unit','source_reference','observed_at'}:fail('unsupported_tax_quantity_metadata')
  if q.get('unit')!=unit:fail('tax_quantity_unit_mismatch')
  n=num(q.get('value'));ref=text(q.get('source_reference'),80)
  if low is not None and n<low or high is not None and n>high:fail('tax_quantity_range')
  bound=min(cutoff or self.asof,self.asof)
  spec={'unit':unit,'source_references':[ref],'effective_not_after':bound.isoformat(),'published_not_after':self.asof.isoformat()}
  if 'observed_at' in q:
   observed=dt(q['observed_at'])
   if observed>bound:fail('tax_future_observation')
   spec['effective_date']=observed.isoformat();self.date_literal(q['observed_at'],path+'/observed_at',ref)
  self.units[path+'/value']=spec
  return n
 def basis(self,value,path,start=None,end=None):
  b=obj(value);ref=text(b.get('source_reference'),80)
  if set(b)!={'id','kind','document_identity','edition','publication_date','effective_from','effective_to','clause','excerpt','source_reference'}:fail('unsupported_tax_basis_metadata')
  text(b.get('id'),150);text(b.get('kind'),80)
  for k in ('document_identity','edition','clause','excerpt'):
   self.literal(text(b.get(k)),path+'/'+k,ref)
  pub=dt(b.get('publication_date'));ef=dt(b.get('effective_from'));et=dt(b['effective_to']) if b.get('effective_to') is not None else None
  if pub>self.asof or et and et<ef:fail('tax_selected_rule_dates_invalid')
  self.date_literal(b['publication_date'],path+'/publication_date',ref);self.date_literal(b['effective_from'],path+'/effective_from',ref)
  if et:self.date_literal(b['effective_to'],path+'/effective_to',ref)
  if start and ef>start or end and et and et<end:fail('selected_rule_does_not_cover_period')
  if end and pub>end:self.gaps.append('rule_published_after_tax_period_selected_historical_interpretation_requires_review')
  if b['kind'] not in ('law','regional_law','official_explanation','letter','contract','hypothesis','selected_method'):fail('tax_rule_kind_invalid')
  if b['kind'] in ('official_explanation','letter','hypothesis','contract'):self.gaps.append('selected_basis_is_not_enacted_tax_law_proof')
  return b
 def period(self,value,path,kind=None):
  p=obj(value);a=dt(p.get('start'));b=dt(p.get('end'))
  if b<a:fail('tax_period_chronology')
  if kind=='calendar_year' and (a.month,a.day,b.month,b.day,a.year==b.year)!=(1,1,12,31,True):fail('full_calendar_year_required')
  if kind=='calendar_month' and (a.year!=b.year or a.month!=b.month or a.day!=1 or b.day!=monthrange(b.year,b.month)[1]):fail('full_calendar_month_required')
  return a,b
 def evidence(self,items,path):
  out=[]
  for i,v in enumerate(rows(items,30)):
   v=obj(v);ref=text(v.get('source_reference'),80);self.literal(v.get('text'),f'{path}/{i}/text',ref);out.append(v)
  return out

def rounding(r,value,p):
 v=obj(value);q=r.q(v.get('quantum'),p+'/quantum',low=Fraction(1,10**100));method=choice(v.get('method'),('half_up','half_even','down'))
 b=r.basis(v.get('basis'),p+'/basis')
 return q,method,b
def rounded(x,rule):
 q,method,_=rule
 sign=-1 if x<0 else 1;n,d=abs(x/q).as_integer_ratio();a,b=divmod(n,d)
 if method=='half_up' and b*2>=d or method=='half_even' and (b*2>d or b*2==d and a%2):a+=1
 return sign*a*q

def scale(r,bands,p):
 bands=rows(bands,8,1);out=[];last=Fraction(0)
 for i,b in enumerate(bands):
  b=obj(b);up=None if b.get('upper') is None else r.q(b['upper'],f'{p}/{i}/upper')
  rate=r.q(b.get('rate'),f'{p}/{i}/rate','ratio',high=1)
  if up is None and i!=len(bands)-1 or up is not None and up<=last:fail('progressive_band_order')
  out.append((up,rate));last=up if up is not None else last
 if out[-1][0] is not None:fail('progressive_open_top_band_required')
 return out
def tax_scale(base,bands):
 tax=Fraction(0);lower=Fraction(0);steps=[]
 for up,rate in bands:
  taxable=max(0,min(base,up) - lower) if up is not None else max(0,base-lower)
  piece=taxable*rate;tax+=piece;steps.append({'lower':fmt(lower),'upper':fmt(up),'rate':fmt(rate),'taxable_slice':fmt(taxable),'tax':fmt(piece)})
  if up is not None:lower=up
 return tax,steps

def vat(r,value,p):
 v=obj(value);a,b=r.period(v.get('period'),p+'/period');basis=r.basis(v.get('basis'),p+'/basis',a,b)
 items=rows(v.get('entries'),40);unique(items);out=[];receipts={};available_from_dates={};offsets={};offset_dates=[];total=Fraction(0);opening=[]
 for i,e in enumerate(rows(v.get('opening_advances',[]),20)):
  e=obj(e);eid=text(e.get('id'),150)
  if eid in receipts:fail('duplicate_opening_advance')
  # Opening stock can be observed on the first day; its snapshot date is not
  # the historical cash-receipt date. The provided stock is available at start.
  amount=r.q(e.get('available_VAT'),f'{p}/opening_advances/{i}/available_VAT',cutoff=a)
  receipts[eid]=amount;available_from_dates[eid]=a;opening.append({'id':eid,'available_VAT':fmt(amount),'source_reference':e['available_VAT']['source_reference']})
 for i,e in enumerate(items):
  e=obj(e);ep=f'{p}/entries/{i}';kind=choice(e.get('kind'),('supply','advance_receipt','advance_offset','purchase','restore'))
  mode=choice(e.get('amount_basis'),('net','gross','vat_only'));amount=r.q(e.get('amount'),ep+'/amount',cutoff=b)
  if mode=='vat_only':rate=None;vatamount=amount;net=None;gross=None
  else:
   rate=r.q(e.get('rate'),ep+'/rate','ratio',high=1);vatamount=amount*rate if mode=='net' else amount*rate/(1+rate);net=amount if mode=='net' else amount-vatamount;gross=amount+vatamount if mode=='net' else amount
  event=dt(e.get('event_date'))
  if not a<=event<=b:fail('VAT_event_outside_selected_period')
  record=choice(e.get('record_kind'),('observed','planned'))
  if record=='observed':
   if event>r.asof:fail('future_actual_VAT_event')
   r.date_literal(e['event_date'],ep+'/event_date',e['amount']['source_reference'])
  else:r.gaps.append('planned_transaction_is_conditional_hypothesis')
  applied=vatamount
  if kind=='purchase':applied*=r.q(e.get('deductible_fraction'),ep+'/deductible_fraction','ratio',high=1)
  if kind=='advance_receipt':
   if e['id'] in receipts:fail('duplicate_advance_across_opening_and_period')
   receipts[e['id']]=vatamount;available_from_dates[e['id']]=event
  if kind=='advance_offset':
   aid=text(e.get('advance_id'),150);offsets[aid]=offsets.get(aid,0)+vatamount;offset_dates.append((aid,event))
  signed=-applied if kind in ('purchase','advance_offset') else applied;total+=signed
  out.append({'id':e['id'],'kind':kind,'record_kind':record,'event_date':e['event_date'],'amount_basis':mode,'amount':fmt(amount),'rate':fmt(rate),'net_amount':fmt(net),'gross_amount':fmt(gross),'VAT_amount':fmt(vatamount),'applied_VAT':fmt(applied),'signed_balance_effect':fmt(signed),'source_reference':e['amount']['source_reference'],'advance_id':e.get('advance_id')})
 for aid,amount in offsets.items():
  if aid not in receipts or amount>receipts[aid]:fail('VAT_advance_offset_requires_sufficient_selected_receipt')
 for aid,event in offset_dates:
  if event<available_from_dates[aid]:fail('VAT_advance_offset_precedes_selected_receipt')
 closing=[{'id':key,'unoffset_selected_VAT':fmt(amount-offsets.get(key,0))} for key,amount in receipts.items()]
 rt=None if v.get('rounding') is None else rounding(r,v['rounding'],p+'/rounding');settled=None if rt is None else rounded(total,rt)
 return {'period':v['period'],'basis':basis,'opening_advances':opening,'entries':out,'closing_advances':closing,'signed_VAT_balance':fmt(total),'VAT_due_before_selected_rounding':fmt(max(0,total)),'potential_VAT_credit':fmt(max(0,-total)),'rounding':v.get('rounding'),'signed_VAT_after_selected_rounding':fmt(settled),'refund_authorized':False,'balance_interpretation':'selected_ledger_not_tax_return_or_cash_refund'},total

def contributions(r,period,p,expense_model):
 items=rows(period.get('contributions',[]),12);unique(items);out=[];cash=deduct=credit=Fraction(0)
 composition='not_used_in_selected_model' if not expense_model and period.get('expenses_contribution_basis') is None else choice(period.get('expenses_contribution_basis'),('excludes_all_contributions','includes_deductible_contributions'))
 for i,c in enumerate(items):
  c=obj(c);amount=r.q(c.get('amount'),f'{p}/contributions/{i}/amount');t=choice(c.get('treatment'),('deductible_expense','tax_credit','not_deductible'))
  choice(c.get('kind'),('employer','self','injury','other'));cash+=amount
  if t=='deductible_expense':deduct+=amount
  if t=='tax_credit':credit+=amount
  out.append({'id':c['id'],'kind':c['kind'],'amount':fmt(amount),'treatment':t,'source_reference':c['amount']['source_reference']})
 return out,cash,deduct if composition=='excludes_all_contributions' else Fraction(0),credit,composition

REGIMES=('OSNO_organization','OSNO_individual','USN_income','USN_expense','PSN','AUSN_income','AUSN_expense','NPD')
def regime(r,data):
 choice(data.get('mode'),('comparison',));entity=choice(data.get('entity_type'),('organization','individual_entrepreneur','individual'))
 scenarios=rows(data.get('scenarios'),8,1);unique(scenarios);out=[]
 for i,s in enumerate(scenarios):
  s=obj(s);sp=f'/scenarios/{i}';model=choice(s.get('regime'),REGIMES)
  if model in ('PSN','OSNO_individual') and entity!='individual_entrepreneur' or model=='OSNO_organization' and entity!='organization' or model=='NPD' and entity=='organization':fail('selected_entity_model_incompatible')
  ps=rows(s.get('periods'),12,1);unique(ps);periodout=[];total=totalcash=Fraction(0);lastend=None;coverage_gaps=[];prior_NPD_credit=None;used_contribution_ids=set()
  for j,v in enumerate(ps):
   v=obj(v);p=f'{sp}/periods/{j}';pk=choice(v.get('period_kind'),('calendar_year','calendar_month','patent_period','reporting_period'));a,b=r.period(v.get('period'),p+'/period',pk)
   if lastend and a<=lastend:fail('overlapping_or_unordered_tax_periods')
   contiguous=lastend is None or a==lastend+timedelta(days=1)
   if lastend and not contiguous:coverage_gaps.append({'start':(lastend+timedelta(days=1)).isoformat(),'end':(a-timedelta(days=1)).isoformat()})
   lastend=b
   if model.startswith('AUSN') or model=='NPD':
    if pk!='calendar_month':fail('selected_model_requires_calendar_month')
   if model=='PSN' and (pk!='patent_period' or a.year!=b.year):fail('patent_period_within_one_year_required')
   basis=r.basis(v.get('basis'),p+'/basis',a,b);roundrule=rounding(r,v.get('rounding'),p+'/rounding')
   c,cash,addexpense,credit,composition=contributions(r,v,p,model in ('OSNO_organization','OSNO_individual','USN_expense','AUSN_expense'))
   for component in c:
    if component['id'] in used_contribution_ids:fail('contribution_component_reused_across_periods')
    used_contribution_ids.add(component['id'])
   revenue=expenses=base=minimum=taxbefore=creditused=Fraction(0);details={};bands=None
   if model=='NPD':
    if any(x['treatment']!='not_deductible' for x in c):fail('NPD_contributions_are_not_selected_tax_credit_or_expense')
    opening=r.q(v.get('deduction_credit_opening'),p+'/deduction_credit_opening');remaining=opening;receipts=rows(v.get('receipts'),20);unique(receipts);rr=[]
    if prior_NPD_credit is not None and contiguous and opening!=prior_NPD_credit:fail('NPD_credit_rollforward_mismatch')
    if prior_NPD_credit is not None and not contiguous:r.gaps.append('NPD_credit_opening_after_unprovided_months_not_reconciled')
    for k,e in enumerate(receipts):
     ep=f'{p}/receipts/{k}';e=obj(e);amount=r.q(e.get('amount'),ep+'/amount',cutoff=b);rate=r.q(e.get('rate'),ep+'/rate','ratio',high=1);red=r.q(e.get('credit_reduction_rate'),ep+'/credit_reduction_rate','ratio',high=rate);buyer=choice(e.get('buyer_type'),('individual','organization_or_IP'))
     raw=amount*rate;used=min(remaining,amount*red);remaining-=used;taxbefore+=raw;creditused+=used;revenue+=amount
     rr.append({'id':e['id'],'buyer_type':buyer,'amount':fmt(amount),'rate':fmt(rate),'credit_reduction_rate':fmt(red),'tax_before_credit':fmt(raw),'credit_used':fmt(used)})
    base=revenue;details={'receipts':rr,'credit_opening':fmt(opening),'credit_closing':fmt(remaining)};prior_NPD_credit=remaining
   elif model=='PSN':
    if any(x['treatment']=='deductible_expense' for x in c):fail('patent_expense_deduction_unsupported')
    potential=r.q(v.get('annual_potential_income'),p+'/annual_potential_income');rate=r.q(v.get('rate'),p+'/rate','ratio',high=1);days=(b-a).days+1;year_days=366 if monthrange(a.year,2)[1]==29 else 365
    base=potential*Fraction(days,year_days);taxbefore=base*rate;cap=r.q(v.get('credit_cap_ratio'),p+'/credit_cap_ratio','ratio',high=1);creditused=min(credit,taxbefore*cap)
    details={'annual_potential_income':fmt(potential),'rate':fmt(rate),'patent_days':str(days),'calendar_year_days':str(year_days),'prorating_model':'inclusive_actual_days_over_actual_calendar_year','credit_cap_ratio':fmt(cap)}
   else:
    revenue=r.q(v.get('revenue'),p+'/revenue',cutoff=b)
    if model in ('USN_income','AUSN_income'):
     base=revenue;expenses=None if v.get('expenses') is None else r.q(v['expenses'],p+'/expenses',cutoff=b)
    else:
     expenses=r.q(v.get('expenses'),p+'/expenses',cutoff=b);base=max(0,revenue-expenses-addexpense)
    if model=='OSNO_individual':
     bands=scale(r,v.get('bands'),p+'/bands');taxbefore,steps=tax_scale(base,bands);details['scale_steps']=steps
    else:
     rate=r.q(v.get('rate'),p+'/rate','ratio',high=1);taxbefore=base*rate;details['rate']=fmt(rate)
    if model=='USN_income':
     if any(x['treatment']=='deductible_expense' for x in c):fail('income_model_contribution_expense_not_used')
     cap=r.q(v.get('credit_cap_ratio'),p+'/credit_cap_ratio','ratio',high=1);creditused=min(credit,taxbefore*cap);details['credit_cap_ratio']=fmt(cap)
    elif credit:fail('tax_credit_not_supported_in_selected_regime_model')
    if model=='USN_expense' and v.get('minimum_rate') is not None:
     if pk!='calendar_year':fail('USN_minimum_tax_requires_full_calendar_year')
     minimum=revenue*r.q(v['minimum_rate'],p+'/minimum_rate','ratio',high=1)
    if model=='AUSN_expense':minimum=revenue*r.q(v.get('minimum_rate'),p+'/minimum_rate','ratio',high=1)
    if model=='AUSN_income' and any(x['treatment']!='not_deductible' for x in c):fail('AUSN_income_no_contribution_credit_in_this_model')
    details.update(revenue=fmt(revenue),recognized_expenses=fmt(expenses),additional_deductible_contributions=fmt(addexpense))
   after=max(taxbefore-creditused,minimum);tax=rounded(after,roundrule);total+=tax;totalcash+=cash
   periodout.append({'id':v['id'],'period_kind':pk,'period':v['period'],'basis':basis,'contributions':c,'expenses_contribution_basis':composition,'contributions_cash':fmt(cash),'tax_base':fmt(base),'tax_before_credit_and_minimum':fmt(taxbefore),'tax_credit_applied':fmt(creditused),'minimum_tax':fmt(minimum),'tax_before_rounding':fmt(after),'tax':fmt(tax),'rounding':v['rounding'],'details':details})
  elig=[]
  for j,e in enumerate(rows(s.get('eligibility_conditions',[]),15)):
   e=obj(e);p=f'{sp}/eligibility_conditions/{j}';ba=r.basis(e.get('basis'),p+'/basis');unit=text(e.get('unit'),80);actual=r.q(e.get('actual'),p+'/actual',unit);limit=r.q(e.get('limit'),p+'/limit',unit);op=choice(e.get('operator'),('lt','le','eq','ge','gt'));ok={'lt':actual<limit,'le':actual<=limit,'eq':actual==limit,'ge':actual>=limit,'gt':actual>limit}[op]
   elig.append({'id':text(e.get('id'),150),'actual':fmt(actual),'limit':fmt(limit),'unit':unit,'operator':op,'selected_numeric_condition_met':ok,'basis':ba})
  vo=None;vb=Fraction(0)
  if s.get('VAT') is not None:vo,vb=vat(r,s['VAT'],sp+'/VAT')
  totalperiod={'start':ps[0]['period']['start'],'end':ps[-1]['period']['end']}
  vat_matches=None if vo is None else vo['period']==totalperiod and not coverage_gaps
  if vat_matches is False:r.gaps.append('VAT_and_direct_tax_periods_differ_not_summed')
  transitions=[]
  for j,t in enumerate(rows(s.get('transition_reviews',[]),8)):
   t=obj(t);tp=f'{sp}/transition_reviews/{j}';ba=r.basis(t.get('basis'),tp+'/basis');deadline=None
   if t.get('deadline_from_record') is not None:
    d=obj(t['deadline_from_record']);dt(d.get('date'));ref=text(d.get('source_reference'),80);r.date_literal(d['date'],tp+'/deadline_from_record/date',ref);deadline=d
   transitions.append({'basis':ba,'deadline_from_record':deadline,'draft_action':text(t.get('draft_action')),'conditions_review':text(t.get('conditions_review')),'transition_performed':False})
  assumptions=[text(x) for x in rows(s.get('assumptions',[]),12)]
  out.append({'id':s['id'],'regime':model,'periods':periodout,'covered_span':totalperiod,'selected_period_count':str(len(ps)),'unprovided_period_intervals':coverage_gaps,'tax_total':fmt(total),'contributions_cash_total':fmt(totalcash),'VAT':vo,'VAT_period_matches_tax_span':vat_matches,'conditional_signed_accrual_total':None if vat_matches is False else fmt(total+totalcash+vb),'positive_VAT_due_separate_from_credit':fmt(max(0,vb)),'unconfirmed_VAT_credit':fmt(max(0,-vb)),'eligibility_conditions':elig,'eligibility_status':'selected_conditions_not_legal_eligibility','eligibility_confirmed':False,'assumptions':assumptions,'transition_reviews':transitions})
 same=len({json.dumps(x['covered_span'],sort_keys=True) for x in out})==1
 coverage_equal=len({json.dumps([p['period'] for p in x['periods']],sort_keys=True) for x in out})==1
 return {'mode':'comparison','entity_type':entity,'client_context':r.evidence(data.get('client_context',[]),'/client_context'),'scenarios':out,'comparison_span_equal':same,'comparison_period_coverage_equal':coverage_equal,'automatic_regime_selected':None,'comparison_limitations':['only_selected_tax_bases_and_periods','VAT_credit_not_assumed_refunded','other_taxes_and_transition_costs_not_automatically_included']+([] if same else ['different_period_spans_not_directly_comparable'])+([] if coverage_equal else ['different_selected_period_sets_require_comparison_review'])}

def ids_review(r,value,p):
 v=obj(value);kind=choice(v.get('entity_type'),('organization','individual_entrepreneur','individual'));ref=text(v.get('source_reference'),80);out={'entity_type':kind,'source_reference':ref,'registry_lookup_performed':False}
 for key in ('inn','ogrn','ogrnip','kpp'):
  if key not in v:continue
  token=r.literal(v[key],p+'/'+key,ref);valid=None
  if key=='inn':
   if not re.fullmatch(r'[0-9]{10}|[0-9]{12}',token):fail('INN_digit_length')
   d=list(map(int,token));weights10=(2,4,10,3,5,9,4,6,8);w11=(7,2,4,10,3,5,9,4,6,8);w12=(3,7,2,4,10,3,5,9,4,6,8)
   valid=sum(a*b for a,b in zip(d,weights10))%11%10==d[-1] if len(d)==10 else sum(a*b for a,b in zip(d,w11))%11%10==d[10] and sum(a*b for a,b in zip(d,w12))%11%10==d[11]
   if kind=='organization' and len(d)!=10 or kind!='organization' and len(d)!=12:fail('INN_entity_type_mismatch')
  elif key in ('ogrn','ogrnip'):
   length=13 if key=='ogrn' else 15
   if not re.fullmatch(r'[0-9]{'+str(length)+'}',token):fail('registration_ID_digit_length')
   if key=='ogrn' and kind!='organization' or key=='ogrnip' and kind!='individual_entrepreneur':fail('registration_ID_entity_type_mismatch')
   valid=int(token[:-1])%(11 if key=='ogrn' else 13)%10==int(token[-1])
  else:
   if kind!='organization':fail('KPP_not_for_selected_entity')
   valid=bool(re.fullmatch(r'[0-9]{4}[A-Z0-9]{2}[0-9]{3}',token))
  out[key]=token;out[key+'_format_or_checksum_matches']=valid
 return out

def transaction(r,data):
 choice(data.get('mode'),('analysis',));question=text(data.get('question'));facts=r.evidence(data.get('facts',[]),'/facts');purpose=text(data.get('business_purpose'))
 out={'mode':'analysis','question':question,'facts':facts,'business_purpose':purpose,'authored_conclusion':text(data.get('draft_conclusion')),'counterparties':[],'VAT':None,'direct_tax':None,'withholding':None,'risk_reviews':[]}
 for i,v in enumerate(rows(data.get('counterparties',[]),8)):out['counterparties'].append(ids_review(r,v,f'/counterparties/{i}'))
 if data.get('VAT') is not None:out['VAT'],_=vat(r,data['VAT'],'/VAT')
 if data.get('direct_tax') is not None:
  v=obj(data['direct_tax']);a,b=r.period(v.get('period'),'/direct_tax/period');basis=r.basis(v.get('basis'),'/direct_tax/basis',a,b);method=choice(v.get('recognition_method'),('selected_accrual_entries','selected_cash_entries'));entries=rows(v.get('entries'),40);unique(entries);inc=exp=Fraction(0);eo=[]
  for i,e in enumerate(entries):
   e=obj(e);ep=f'/direct_tax/entries/{i}';kind=choice(e.get('kind'),('income','expense'));amount=r.q(e.get('amount'),ep+'/amount',cutoff=b);event=dt(e.get('recognition_date'))
   if not a<=event<=b or event>r.asof:fail('direct_tax_recognition_date_invalid')
   r.date_literal(e['recognition_date'],ep+'/recognition_date',e['amount']['source_reference']);text(e.get('recognition_rationale'))
   if kind=='income':inc+=amount
   else:exp+=amount
   eo.append({'id':e['id'],'kind':kind,'amount':fmt(amount),'recognition_date':e['recognition_date'],'recognition_rationale':e['recognition_rationale'],'source_reference':e['amount']['source_reference']})
  base=max(0,inc-exp);tax,steps=tax_scale(base,scale(r,v.get('bands'),'/direct_tax/bands'));rr=rounding(r,v.get('rounding'),'/direct_tax/rounding')
  out['direct_tax']={'period':v['period'],'basis':basis,'recognition_method':method,'entries':eo,'income':fmt(inc),'expense':fmt(exp),'signed_income_less_expense':fmt(inc-exp),'tax_base':fmt(base),'scale_steps':steps,'tax_before_rounding':fmt(tax),'tax':fmt(rounded(tax,rr)),'rounding':v['rounding'],'recognition_legality_established':False}
 if data.get('withholding') is not None:
  v=obj(data['withholding']);basis=r.basis(v.get('basis'),'/withholding/basis');gross=r.q(v.get('gross_payment'),'/withholding/gross_payment');rate=r.q(v.get('rate'),'/withholding/rate','ratio',high=1);contrib=r.q(v.get('contribution_base'),'/withholding/contribution_base');cr=r.q(v.get('contribution_rate'),'/withholding/contribution_rate','ratio',high=1);rr=rounding(r,v.get('rounding'),'/withholding/rounding');tax=rounded(gross*rate,rr)
  out['withholding']={'basis':basis,'gross_payment':fmt(gross),'tax_before_rounding':fmt(gross*rate),'tax':fmt(tax),'net_payment':fmt(gross-tax),'contribution_base':fmt(contrib),'contribution_rate':fmt(cr),'contributions_before_rounding':fmt(contrib*cr),'classification':'selected_flat_withholding_and_contribution_scenario_not_worker_classification'}
 for i,v in enumerate(rows(data.get('risk_reviews',[]),12)):
  v=obj(v);p=f'/risk_reviews/{i}';topic=choice(v.get('topic'),('business_purpose','actual_performer','related_parties','splitting','controlled_transaction','other'));status=choice(v.get('evidence_status'),('supported','contradicted','unknown'));basis=r.basis(v.get('basis'),p+'/basis');evidence=r.evidence(v.get('evidence',[]),p+'/evidence');out['risk_reviews'].append({'topic':topic,'evidence_status':status,'basis':basis,'evidence':evidence,'draft_analysis':text(v.get('draft_analysis'))})
 return out

def addmonths(d,n,policy):
 y,m=divmod(d.year*12+d.month-1+n,12);m+=1;last=monthrange(y,m)[1]
 if d.day>last and policy=='reject_missing_anniversary':fail('property_anniversary_requires_selected_end_of_month_policy')
 return date(y,m,min(d.day,last))
def property_sale(r,v,p,year_start,year_end):
 v=obj(v);acq=dt(v.get('acquired'));sold=dt(v.get('sold'))
 if sold<acq or sold>r.asof:fail('property_sale_chronology')
 if not year_start<=sold<=year_end:fail('property_sale_outside_selected_tax_year')
 basis=r.basis(v.get('basis'),p+'/basis',sold,sold)
 ref=text(v.get('source_reference'),80);r.date_literal(v['acquired'],p+'/acquired',ref);r.date_literal(v['sold'],p+'/sold',ref)
 months=r.q(v.get('minimum_holding_months'),p+'/minimum_holding_months','month',high=1200)
 if months.denominator!=1:fail('integer_calendar_months_required')
 policy=choice(v.get('anniversary_policy'),('end_of_month_clamp','reject_missing_anniversary'));end=addmonths(acq,int(months),policy);met=sold>=end
 amount=r.q(v.get('sale_price'),p+'/sale_price',cutoff=sold);floor=None
 if v.get('cadastral_value') is not None:floor=r.q(v['cadastral_value'],p+'/cadastral_value',cutoff=sold)*r.q(v.get('cadastral_coefficient'),p+'/cadastral_coefficient','ratio',high=1)
 recognized=max(amount,floor or 0);treatment=choice(v.get('exemption_treatment'),('apply_selected_exemption','not_applied'));others=choice(v.get('other_exemption_conditions'),('supported','unknown','not_met'))
 if treatment=='apply_selected_exemption' and (not met or others!='supported'):fail('selected_property_exemption_conditions_not_supported')
 method=choice(v.get('cost_method'),('documented_expenses','fixed_deduction','none'));deduct=Fraction(0)
 if method!='none':deduct=r.q(v.get('cost_or_deduction'),p+'/cost_or_deduction',cutoff=sold)
 taxable=Fraction(0) if treatment=='apply_selected_exemption' else max(0,recognized-deduct)
 return taxable,{'basis':basis,'acquired':v['acquired'],'sold':v['sold'],'minimum_holding_months':fmt(months),'minimum_holding_anniversary':end.isoformat(),'anniversary_policy':policy,'calendar_holding_condition_met':met,'other_exemption_conditions':others,'exemption_treatment':treatment,'sale_price':fmt(amount),'cadastral_floor':fmt(floor),'recognized_sale_income':fmt(recognized),'cost_method':method,'cost_or_deduction':fmt(deduct),'taxable_after_selected_treatment':fmt(taxable),'legal_exemption_confirmed':False}

def personal(r,data):
 choice(data.get('mode'),('draft_calculation',));year=text(data.get('tax_year'),4)
 if not re.fullmatch(r'[0-9]{4}',year) or not 1900<=int(year)<=2199:fail('tax_year_bound')
 start=date(int(year),1,1);end=date(int(year),12,31);res=obj(data.get('residency'));ra,rb=r.period(res.get('window'),'/residency/window');basis=r.basis(res.get('basis'),'/residency/basis');days=r.q(res.get('days'),'/residency/days','day',high=(rb-ra).days+1,cutoff=rb);threshold=r.q(res.get('threshold'),'/residency/threshold','day',high=(rb-ra).days+1);status=choice(res.get('selected_status'),('resident','nonresident','special_category'))
 if days.denominator!=1 or threshold.denominator!=1:fail('residency_integer_days_required')
 condition=days>=threshold
 if status=='resident' and not condition or status=='nonresident' and condition:r.gaps.append('selected_residency_status_differs_from_day_test_review_special_rules')
 groups=rows(data.get('groups'),8,1);gids=unique(groups);parsed={};output=[];income_ids=set()
 for i,g in enumerate(groups):
  g=obj(g);p=f'/groups/{i}';ba=r.basis(g.get('basis'),p+'/basis',start,end);bands=scale(r,g.get('bands'),p+'/bands');rr=rounding(r,g.get('rounding'),p+'/rounding');incomes=rows(g.get('incomes'),30);unique(incomes);gross=base=exempt=Fraction(0);io=[]
  for j,e in enumerate(incomes):
   e=obj(e);ep=f'{p}/incomes/{j}';kind=choice(e.get('treatment'),('taxable','selected_exempt','property_sale'));pr=None
   if e['id'] in income_ids:fail('income_id_repeated_across_tax_groups')
   income_ids.add(e['id'])
   if kind=='property_sale':taxable,pr=property_sale(r,e.get('property'),ep+'/property',start,end);amount=Fraction(pr['recognized_sale_income'])
   else:
    amount=r.q(e.get('amount'),ep+'/amount',cutoff=end);taxable=amount
    if kind=='selected_exempt':r.basis(e.get('exemption_basis'),ep+'/exemption_basis',start,end);taxable=Fraction(0)
   if e.get('received') is not None:
    event=dt(e['received'])
    if not start<=event<=end or event>r.asof:fail('income_received_date_invalid')
    ref=e['property']['source_reference'] if kind=='property_sale' else e['amount']['source_reference']
    r.date_literal(e['received'],ep+'/received',ref)
   gross+=amount;base+=taxable;exempt+=amount-taxable
   io.append({'id':e['id'],'treatment':kind,'amount':fmt(amount),'taxable_before_group_deductions':fmt(taxable),'received':e.get('received'),'exemption_basis':e.get('exemption_basis'),'property':pr,'source_reference':e['property']['source_reference'] if kind=='property_sale' else e.get('amount',{}).get('source_reference')})
  parsed[g['id']]={'base':base,'bands':bands,'rounding':rr,'deducted':Fraction(0)}
  output.append({'id':g['id'],'basis':ba,'incomes':io,'gross_income':fmt(gross),'selected_exempt_and_property_reduction':fmt(exempt),'taxable_before_group_deductions':fmt(base),'deductions_applied':None,'tax_base':None,'scale_steps':None,'tax_before_rounding':None,'tax':None,'rounding':g['rounding']})
 pools=rows(data.get('deduction_pools',[]),12);unique(pools);po=[]
 for i,v in enumerate(pools):
  v=obj(v);p=f'/deduction_pools/{i}';ba=r.basis(v.get('basis'),p+'/basis');cap=r.q(v.get('cap'),p+'/cap');prior=r.q(v.get('previously_used'),p+'/previously_used');remaining=max(0,cap-prior);alloc=[]
  if prior>cap:r.gaps.append('deduction_previously_used_exceeds_selected_cap')
  for j,e in enumerate(rows(v.get('allocations'),12,1)):
   e=obj(e);gid=text(e.get('group_id'),150)
   if gid not in parsed:fail('deduction_unknown_group')
   claimed=r.q(e.get('claimed'),f'{p}/allocations/{j}/claimed');g=parsed[gid];applied=min(claimed,remaining,max(0,g['base']-g['deducted']));remaining-=applied;g['deducted']+=applied
   alloc.append({'group_id':gid,'category':text(e.get('category'),150),'claimed':fmt(claimed),'applied':fmt(applied),'unapplied':fmt(claimed-applied)})
  po.append({'id':v['id'],'basis':ba,'cap':fmt(cap),'previously_used':fmt(prior),'remaining_after_selected_allocations':fmt(remaining),'allocations':alloc,'allocation_model':'provided_order_not_optimized_or_eligibility_granted'})
 total=Fraction(0)
 for out in output:
  g=parsed[out['id']];base=max(0,g['base']-g['deducted']);raw,steps=tax_scale(base,g['bands']);tax=rounded(raw,g['rounding']);g['tax']=tax;g['foreign']=Fraction(0);total+=tax
  out.update(deductions_applied=fmt(g['deducted']),tax_base=fmt(base),scale_steps=steps,tax_before_rounding=fmt(raw),tax=fmt(tax))
 foreign=Fraction(0);fo=[];foreign_groups=set()
 for i,v in enumerate(rows(data.get('foreign_tax_credits',[]),15)):
  v=obj(v);p=f'/foreign_tax_credits/{i}';gid=text(v.get('group_id'),150)
  if gid not in parsed:fail('foreign_credit_unknown_group')
  if gid in foreign_groups:fail('one_prepared_foreign_credit_pool_per_group_required')
  foreign_groups.add(gid)
  ba=r.basis(v.get('basis'),p+'/basis');amount=r.q(v.get('amount'),p+'/amount');cap=r.q(v.get('Russian_tax_attributable_cap'),p+'/Russian_tax_attributable_cap');g=parsed[gid];applied=min(amount,cap,g['tax']);g['foreign']+=applied;foreign+=applied;fo.append({'group_id':gid,'amount':fmt(amount),'Russian_tax_attributable_cap':fmt(cap),'applied':fmt(applied),'unapplied':fmt(amount-applied),'basis':ba,'attribution_model':'provided_prepared_foreign_income_cap_not_entire_group_tax_automatically'})
 withheld=r.q(data.get('withheld'),'/withheld');adv=r.q(data.get('domestic_advance_paid'),'/domestic_advance_paid');balance=total-foreign-withheld-adv
 filing=None
 if data.get('filing_review') is not None:
  v=obj(data['filing_review']);ba=r.basis(v.get('basis'),'/filing_review/basis');kind=choice(v.get('case'),('required_filing','deduction_only','unknown'));filing={'case':kind,'basis':ba,'selected_filing_deadline':v.get('filing_deadline'),'selected_payment_deadline':v.get('payment_deadline'),'calendar_legally_verified':False}
  for k in ('filing_deadline','payment_deadline'):
   if v.get(k) is not None:dt(v[k]);r.date_literal(v[k],'/filing_review/'+k,ba['source_reference'])
 return {'mode':'draft_calculation','tax_year':year,'residency':{'window':res['window'],'days':fmt(days),'threshold':fmt(threshold),'selected_status':status,'selected_day_condition_met':condition,'basis':basis,'residency_legally_confirmed':False},'groups':output,'deduction_pools':po,'foreign_tax_credits':fo,'tax_total':fmt(total),'foreign_tax_credit_applied':fmt(foreign),'withheld':fmt(withheld),'domestic_advance_paid':fmt(adv),'signed_settlement':fmt(balance),'potential_amount_due':fmt(max(0,balance)),'potential_refund':fmt(max(0,-balance)),'refund_authorized':False,'filing_review':filing,'documents':r.evidence(data.get('documents',[]),'/documents'),'official_declaration_XML_generated':False}

QUESTION_INPUTS={
 'regime_choice':['entity_region_activity_and_period','recognized_revenue_expense_and_contribution_composition','selected_rates_thresholds_eligibility_and_transition_rules','VAT_buyer_and_input_deduction_scenarios'],
 'transaction_structuring':['question_and_business_purpose','actual_parties_performance_documents_and_dates','selected_recognition_VAT_and_direct_tax_rules','related_party_splitting_and_controlled_transaction_evidence'],
 'individual_3ndfl':['tax_year_income_sources_and_residency_window','selected_group_scales_exemptions_and_deduction_pools','withheld_domestic_and_foreign_tax_documents','property_holding_and_selected_deadline_rules']}
def _run(function,data):
 if function not in FUNCTIONS:fail('unknown_tax_model_function')
 from .core import reject_proposed_authority
 reject_proposed_authority(data);reject_known_secret_material(data);bounded_json(data);r=Read(data)
 if data.get('mode')=='questions':result={'mode':'questions','function':function,'question':text(data.get('question')),'required_inputs':QUESTION_INPUTS[function],'calculation':None}
 else:result={'regime_choice':regime,'transaction_structuring':transaction,'individual_3ndfl':personal}[function](r,data)
 if len(r.units)+len(r.literals)>1000:fail('tax_source_contract_fact_bound')
 result.update(as_of=data['as_of'],jurisdiction='RU',draft_status='conditional_selected_source_draft',gaps=list(dict.fromkeys(r.gaps)),current_legal_chain_established=False,source_semantics_established=False,legal_eligibility_granted=False,filing_performed=False,payment_performed=False)
 reject_known_secret_material(result)
 return result,r
def execute(function,data):
 with localcontext(CTX):
  try:return _run(function,data)[0]
  except (KeyError,TypeError,AttributeError,IndexError,OverflowError,InvalidOperation):raise ValueError('malformed_tax_model_input') from None
def input_units(function,data):
 with localcontext(CTX):
  try:return _run(function,data)[1].units
  except (KeyError,TypeError,AttributeError,IndexError,OverflowError,InvalidOperation):raise ValueError('malformed_tax_model_input') from None
def selected_texts(function,data):
 with localcontext(CTX):
  try:return _run(function,data)[1].literals
  except (KeyError,TypeError,AttributeError,IndexError,OverflowError,InvalidOperation):raise ValueError('malformed_tax_model_input') from None

"""Bounded deterministic actuarial drafts on local selected records.

No tariff/reserve approval, actuarial signature, external code or registry access.
All monetary amounts retain Decimal arithmetic precision; display rounding is a
separate host/document choice. Conditional models do not establish compliance.
"""
from copy import deepcopy
from datetime import date,timedelta
from calendar import monthrange
from decimal import Decimal,Context,localcontext,DecimalException,ROUND_HALF_UP
import re

D=Decimal
CTX=Context(prec=180,rounding=ROUND_HALF_UP,Emin=-9999,Emax=9999)
ZERO=D(0);ONE=D(1)
FUNCTIONS=('tariff','reserves','life_pension')
COMMON=('as_of','jurisdiction','valuation_date','data_scope','currency','mode')

def fail(message):raise ValueError(message)
def obj(v,name,required,optional=()):
    if type(v) is not dict or not set(required)<=set(v) or set(v)-set(required)-set(optional):fail(name+'_fields')
    return v
def rows(v,name,low=0,high=40):
    if type(v) is not list or not low<=len(v)<=high:fail(name+'_bounded_list_required')
    return v
def text(v,name,limit=12000):
    if type(v) is not str or not v.strip() or len(v)>limit or any(ord(c)<32 and c not in '\r\n\t' for c in v):fail(name+'_text_required')
    return v
def boolean(v,name):
    if type(v) is not bool:fail(name+'_boolean_required')
    return v
def day(v,name):
    if type(v) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',v):fail(name+'_ISO_date_required')
    try:return date.fromisoformat(v)
    except ValueError:fail(name+'_invalid_date')
def exact(v):
    if not v.is_finite() or v and not D('1e-1000')<=abs(v)<=D('1e1000'):fail('derived_value_outside_supported_range')
    return str(v)
def ref(v):return text(v,'source_reference',200)
def unique(items,key='id'):
    names=[r[key] for r in items]
    if len(set(names))!=len(names):fail('duplicate_'+key)
def addmonths(value,months):
    total=value.year*12+value.month-1+months;year,month=divmod(total,12);month+=1
    if not 1<=year<=9999:fail('date_outside_supported_range')
    last=monthrange(year,month)[1]
    return date(year,month,last if value.day==monthrange(value.year,value.month)[1] else min(value.day,last))
def tree(v,depth=0,budget=None):
    if budget is None:budget=[0]
    budget[0]+=1
    if depth>16 or budget[0]>14000:fail('actuarial_structure_limit')
    if type(v) is dict:
        if len(v)>80 or any(type(k) is not str for k in v):fail('invalid_object_keys')
        for x in v.values():tree(x,depth+1,budget)
    elif type(v) is list:
        if len(v)>200:fail('actuarial_list_limit')
        for x in v:tree(x,depth+1,budget)
    elif type(v) is str:
        if len(v)>30000:fail('actuarial_text_limit')
    elif v is not None and type(v) not in (bool,int,D):fail('exact_JSON_values_required')

class Reader:
    def __init__(self,data):
        tree(data);self.data=deepcopy(data);self.units={}
        if type(data) is not dict:fail('data_object_required')
        self.asof=day(data.get('as_of'),'as_of');self.valuation=day(data.get('valuation_date'),'valuation_date')
        if self.valuation>self.asof:fail('valuation_after_as_of')
        if data.get('jurisdiction')!='RU' or data.get('currency')!='RUB':fail('supported_RU_RUB_scope_required')
        text(data.get('data_scope'),'data_scope',500)
    def n(self,v,path,unit,low=None,high=None,integer=False):
        if type(v) not in (str,int,D) or len(str(v))>160 or not re.fullmatch(r'[+-]?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d{1,3})?',str(v)):fail('exact_decimal_required:'+path)
        value=D(v)
        if not value.is_finite() or len(value.as_tuple().digits)>40 or abs(value)>D('1e100') or value and abs(value)<D('1e-100'):fail('decimal_range:'+path)
        if low is not None and value<D(low) or high is not None and value>D(high):fail('numeric_bound:'+path)
        if integer and value!=int(value):fail('integer_required:'+path)
        self.units[path]={'unit':unit,'effective_not_after':self.data['valuation_date'],'published_not_after':self.data['as_of']}
        return int(value) if integer else value
    def observed(self,v,name):
        result=day(v,name)
        if result>self.valuation:fail(name+'_after_valuation')
        return result
    def metadata(self,v,name,rule=False):
        required=('document_identity','edition','publication_date','source_reference')
        obj(v,name,(*required,'effective_from','effective_to') if rule else (*required,'reference_date'),('excerpt',))
        text(v['document_identity'],name+'_identity');text(v['edition'],name+'_edition');ref(v['source_reference'])
        publication=day(v['publication_date'],name+'_publication_date')
        if publication>self.asof:fail(name+'_publication_after_as_of')
        if rule:
            start=day(v['effective_from'],'effective_from');end=day(v['effective_to'],'effective_to') if v['effective_to'] is not None else None
            if end and end<start:fail('invalid_selected_rule_window')
            if start>self.valuation or end and self.valuation>end:fail('selected_rule_outside_valuation_window')
        else:self.observed(v['reference_date'],name+'_reference_date')
        if 'excerpt' in v:text(v['excerpt'],name+'_excerpt')
        return dict(deepcopy(v),publication_after_valuation=publication>self.valuation,publication_cutoff=self.data['as_of'],effective_observation_cutoff=self.data['valuation_date'])

def _tariff(c,r):
    if c['mode']=='osago_review':
        obj(c,'osago_review',(*COMMON,'insurance_class','selected_rule','category','corridor','selected_base_rate','coefficients','required_coefficient_codes'))
        meta=r.metadata(c['selected_rule'],'selected_rule',True);text(c['insurance_class'],'insurance_class');text(c['category'],'category')
        corridor=obj(c['corridor'],'corridor',('minimum','maximum','minimum_inclusive','maximum_inclusive','source_reference'))
        low=r.n(corridor['minimum'],'/corridor/minimum','RUB','0');high=r.n(corridor['maximum'],'/corridor/maximum','RUB','0')
        if low>high:fail('invalid_corridor')
        loinc=boolean(corridor['minimum_inclusive'],'minimum_inclusive');hiinc=boolean(corridor['maximum_inclusive'],'maximum_inclusive');ref(corridor['source_reference'])
        base=r.n(c['selected_base_rate'],'/selected_base_rate','RUB','0');within=(base>low or loinc and base==low) and (base<high or hiinc and base==high)
        required=[text(x,'coefficient_code',100) for x in rows(c['required_coefficient_codes'],'required_codes',1,15)]
        if len(set(required))!=len(required):fail('duplicate_required_coefficient')
        factors=[];product=ONE
        for i,row in enumerate(rows(c['coefficients'],'coefficients',1,15)):
            obj(row,'coefficient',('id','value','allowed_values','selection_rationale','source_reference'))
            text(row['id'],'coefficient_id',100);text(row['selection_rationale'],'selection_rationale');ref(row['source_reference'])
            value=r.n(row['value'],f'/coefficients/{i}/value','ratio','0')
            allowed=[r.n(v,f'/coefficients/{i}/allowed_values/{j}','ratio','0') for j,v in enumerate(rows(row['allowed_values'],'allowed_values',1,20))]
            factors.append(dict(row,selected_value_in_selected_table=value in allowed));product*=value
        unique(factors)
        if set(required)!={x['id'] for x in factors}:fail('selected_rule_coefficient_set_mismatch')
        return dict(mode=c['mode'],insurance_class=c['insurance_class'],osago_review=dict(category=c['category'],selected_rule=meta,corridor=deepcopy(corridor),selected_base_rate=exact(base),base_within_selected_corridor=within,coefficients=factors,coefficient_product=exact(product),premium_factor_product_draft=exact(base*product),selected_table_arithmetic_matches=within and all(x['selected_value_in_selected_table'] for x in factors),other_premium_caps_and_applicability_not_established=True),proposal_insurer_decision_only=True,evidence_gaps=['current_complete_CBR_amendment_chain_and_category_applicability_not_established'])
    if c['mode']!='experience':fail('supported_tariff_mode_required')
    obj(c,'tariff_experience',(*COMMON,'insurance_class','experience','target_cost_date','trend_day_count','loss_basis','credibility','risk_loading','loads','output_basis','reliability','sensitivity'),('reference_sum_insured_per_policy',))
    text(c['insurance_class'],'insurance_class');target=day(c['target_cost_date'],'target_cost_date')
    if c['trend_day_count']!='actual_365_fixed':fail('supported_trend_day_count_required')
    basis=obj(c['loss_basis'],'loss_basis',('amount_basis','gross_net','deductible','limit','description','source_reference'))
    if basis['amount_basis']!='covered_losses_after_policy_terms' or basis['gross_net'] not in ('gross','net'):fail('explicit_covered_loss_basis_required')
    deductible=r.n(basis['deductible'],'/loss_basis/deductible','RUB','0');limit=r.n(basis['limit'],'/loss_basis/limit','RUB','1e-100')
    text(basis['description'],'loss_basis_description');ref(basis['source_reference'])
    experience=[];exposure=ZERO;count=ZERO;total=ZERO;adjusted=ZERO
    for i,row in enumerate(rows(c['experience'],'experience',1,12)):
        obj(row,'experience_period',('id','period_start','period_end','loss_cost_date','earned_exposure','claims_count','claims_total','annual_severity_trend','observation_date','source_reference'))
        text(row['id'],'period_id',100);start=day(row['period_start'],'period_start');end=r.observed(row['period_end'],'period_end');obs=r.observed(row['observation_date'],'observation_date');cost=day(row['loss_cost_date'],'loss_cost_date')
        if not start<=cost<=end<=obs or target<cost:fail('invalid_experience_dates')
        e=r.n(row['earned_exposure'],f'/experience/{i}/earned_exposure','policy_year','1e-100');n=r.n(row['claims_count'],f'/experience/{i}/claims_count','claim','0','1000000000000',True)
        amount=r.n(row['claims_total'],f'/experience/{i}/claims_total','RUB','0');trend=r.n(row['annual_severity_trend'],f'/experience/{i}/annual_severity_trend','ratio','-0.9999999999','10');ref(row['source_reference'])
        if n==0 and amount!=0:fail('zero_matched_claim_count_requires_zero_total')
        years=D((target-cost).days)/D(365);factor=(ONE+trend)**years;costed=amount*factor
        experience.append(dict(row,trend_years=exact(years),trend_factor=exact(factor),trended_claims_total=exact(costed),frequency=exact(D(n)/e),average_claim=exact(amount/n) if n else None,average_claim_status='defined' if n else 'undefined_zero_claim_count'))
        exposure+=e;count+=n;total+=amount;adjusted+=costed
    unique(experience)
    ordered=sorted(experience,key=lambda x:x['period_start'])
    if any(ordered[i]['period_end']>=ordered[i+1]['period_start'] for i in range(len(ordered)-1)):fail('overlapping_experience_periods')
    loss_cost=adjusted/exposure
    cred=obj(c['credibility'],'credibility',('mode','rationale','source_reference'),('K','prior_loss_cost'))
    text(cred['rationale'],'credibility_rationale');ref(cred['source_reference']);z=None;prior=None
    if cred['mode']=='buhlmann_straub_selected_K':
        if set(cred)!=set(('mode','rationale','source_reference','K','prior_loss_cost')):fail('selected_K_and_prior_required')
        K=r.n(cred['K'],'/credibility/K','policy_year','1e-100');prior=r.n(cred['prior_loss_cost'],'/credibility/prior_loss_cost','RUB/policy_year','0');z=exposure/(exposure+K);blended=z*loss_cost+(ONE-z)*prior
    elif cred['mode']=='not_estimated':
        if set(cred)!=set(('mode','rationale','source_reference')):fail('irrelevant_credibility_fields')
        blended=loss_cost
    else:fail('supported_credibility_model_required')
    risk=obj(c['risk_loading'],'risk_loading',('model','ratio','rationale','source_reference'))
    if risk['model']!='selected_ratio_of_blended_loss_cost':fail('supported_risk_loading_model_required')
    riskratio=r.n(risk['ratio'],'/risk_loading/ratio','ratio','0','10');text(risk['rationale'],'risk_rationale');ref(risk['source_reference'])
    loads=obj(c['loads'],'loads',('commission_ratio','admin_ratio','profit_ratio','fixed_expense_per_policy_year','source_reference'))
    loadsum=ZERO
    for key in ('commission_ratio','admin_ratio','profit_ratio'):loadsum+=r.n(loads[key],'/loads/'+key,'ratio','0','1')
    if loadsum>=ONE:fail('premium_denominator_load_must_be_less_than_one')
    fixed=r.n(loads['fixed_expense_per_policy_year'],'/loads/fixed_expense_per_policy_year','RUB/policy_year','0');ref(loads['source_reference'])
    riskadd=blended*riskratio;gross=(blended+riskadd+fixed)/(ONE-loadsum);suminsured=None
    if c['output_basis']=='per_insured_sum':suminsured=r.n(c.get('reference_sum_insured_per_policy'),'/reference_sum_insured_per_policy','RUB/policy','1e-100')
    elif c['output_basis']!='per_policy_year' or 'reference_sum_insured_per_policy' in c:fail('explicit_output_rate_basis_required')
    reliability=obj(c['reliability'],'reliability',('minimum_claims','rationale','source_reference'));threshold=r.n(reliability['minimum_claims'],'/reliability/minimum_claims','claim','0','1000000000000',True);text(reliability['rationale'],'reliability_rationale');ref(reliability['source_reference'])
    sensitivity=[]
    for i,s in enumerate(rows(c['sensitivity'],'tariff_sensitivity',1,4)):
        obj(s,'tariff_stress',('id','annual_trend_delta','source_reference'));ref(s['source_reference']);text(s['id'],'stress_id',100);delta=r.n(s['annual_trend_delta'],f'/sensitivity/{i}/annual_trend_delta','ratio','-10','10');changed=ZERO
        for row in experience:
            rate=D(row['annual_severity_trend'])+delta
            if rate<=-ONE:fail('stressed_trend_outside_domain')
            changed+=D(row['claims_total'])*(ONE+rate)**D(row['trend_years'])
        newcost=changed/exposure;newblend=z*newcost+(ONE-z)*prior if z is not None else newcost
        newgross=(newblend*(ONE+riskratio)+fixed)/(ONE-loadsum)
        sensitivity.append(dict(s,gross_premium_per_policy_year=exact(newgross),change=exact(newgross-gross)))
    unique(sensitivity)
    return dict(mode=c['mode'],insurance_class=c['insurance_class'],experience_rows=experience,loss_basis=deepcopy(basis),trend_convention=c['trend_day_count'],target_cost_date=c['target_cost_date'],earned_exposure=exact(exposure),claims_count=exact(count),claims_total=exact(total),trended_claims_total=exact(adjusted),frequency=exact(count/exposure),frequency_unit='claim/policy_year',average_claim=exact(total/count) if count else None,trended_average_claim=exact(adjusted/count) if count else None,average_claim_status='defined' if count else 'undefined_zero_claim_count',experience_loss_cost=exact(loss_cost),credibility=dict(cred,weight=exact(z) if z is not None else None,model_parameters_estimated_from_data=False),net_loss_cost=exact(blended),risk_loading=dict(risk,addition_per_policy_year=exact(riskadd),statistical_confidence_level_not_inferred=True),loads=dict(loads,total_premium_fraction=exact(loadsum),denominator_basis='gross_premium'),gross_premium_per_policy_year=exact(gross),premium_unit='RUB/policy_year',insured_sum_rate=exact(gross/suminsured) if suminsured is not None else None,insured_sum_rate_unit='ratio/year' if suminsured is not None else None,reliability=dict(reliability,below_selected_claim_count=count<threshold,selected_threshold_not_legal_or_statistical_proof=True),sensitivity=sensitivity,proposal_insurer_decision_only=True,claim_development_not_estimated=True,evidence_gaps=(['credibility_not_estimated'] if z is None else ['selected_K_model_applicability_not_established'])+['ultimate_claim_development_and_coverage_match_not_established']+(['single_experience_period_not_long_history'] if len(experience)==1 else []))

def _upr(value,r):
    value=obj(value,'unearned_premium',('earning_pattern','valuation_boundary','premium_basis','policies','source_reference'))
    if value['earning_pattern']!='uniform_actual_days' or value['valuation_boundary'] not in ('start_of_day','end_of_day') or value['premium_basis'] not in ('written_gross','net_of_selected_acquisition_expense'):fail('supported_UPR_convention_required')
    ref(value['source_reference']);cutoff=r.valuation+timedelta(days=int(value['valuation_boundary']=='end_of_day'));output=[];total=ZERO
    for i,p in enumerate(rows(value['policies'],'policies',1,40)):
        obj(p,'UPR_policy',('id','start_date','end_date','premium','observation_date','source_reference'),('acquisition_expense',))
        text(p['id'],'policy_id',100);start=day(p['start_date'],'policy_start');end=day(p['end_date'],'policy_end');r.observed(p['observation_date'],'premium_observation');ref(p['source_reference'])
        if start>=end:fail('positive_policy_term_required')
        premium=r.n(p['premium'],f'/unearned_premium/policies/{i}/premium','RUB','0');expense=ZERO
        if value['premium_basis']=='net_of_selected_acquisition_expense':expense=r.n(p.get('acquisition_expense'),f'/unearned_premium/policies/{i}/acquisition_expense','RUB','0',premium)
        elif 'acquisition_expense' in p:fail('irrelevant_acquisition_expense')
        remaining=max(0,(end-max(start,cutoff)).days);duration=(end-start).days;share=D(remaining)/duration;reserve=(premium-expense)*share;total+=reserve
        output.append(dict(p,day_interval='start_inclusive_end_exclusive',total_days=duration,unearned_days=remaining,unearned_share=exact(share),premium_reserving_basis=exact(premium-expense),unearned_premium=exact(reserve)))
    unique(output)
    return dict(earning_pattern=value['earning_pattern'],valuation_boundary=value['valuation_boundary'],premium_basis=value['premium_basis'],rows=output,total=exact(total),regulatory_reserve_equivalence_not_established=True)

def _claims(value,r):
    value=obj(value,'claims',('basis','triangle','selection','settlement_expenses','uncertainty'),('reinsurance_recoverables','runoff'))
    basis=obj(value['basis'],'claim_basis',('gross_net','amount_basis','description','source_reference'))
    if basis['gross_net'] not in ('gross','net') or basis['amount_basis']!='losses_excluding_settlement_expenses':fail('supported_claim_basis_required')
    text(basis['description'],'basis_description');ref(basis['source_reference'])
    tri=obj(value['triangle'],'triangle',('period_months','development_ages','origins','source_reference'))
    step=r.n(tri['period_months'],'/claims/triangle/period_months','month','1','12',True)
    ages=[r.n(a,f'/claims/triangle/development_ages/{i}','month','1','1200',True) for i,a in enumerate(rows(tri['development_ages'],'development_ages',2,12))]
    if any(a!=(i+1)*step for i,a in enumerate(ages)):fail('regular_development_ages_required')
    ref(tri['source_reference']);origins=[];cells={};latest={};premiums={};prior={};exposures={}
    for i,o in enumerate(rows(tri['origins'],'triangle_origins',2,12)):
        obj(o,'origin',('id','origin_end_date','cells','source_reference'),('earned_premium','prior_ELR','earned_exposure'))
        identity=text(o['id'],'origin_id',100);end=r.observed(o['origin_end_date'],'origin_end_date');ref(o['source_reference'])
        premiums[identity]=r.n(o['earned_premium'],f'/claims/triangle/origins/{i}/earned_premium','RUB','0') if 'earned_premium' in o else None
        prior[identity]=r.n(o['prior_ELR'],f'/claims/triangle/origins/{i}/prior_ELR','ratio','0','100') if 'prior_ELR' in o else None
        exposures[identity]=r.n(o['earned_exposure'],f'/claims/triangle/origins/{i}/earned_exposure','policy_year','0') if 'earned_exposure' in o else None
        prepared=[]
        for j,cell in enumerate(rows(o['cells'],'triangle_cells',1,len(ages))):
            obj(cell,'triangle_cell',('age_months','observation_date','paid','reported'))
            age=r.n(cell['age_months'],f'/claims/triangle/origins/{i}/cells/{j}/age_months','month','1','1200',True)
            observed=r.observed(cell['observation_date'],'cell_observation_date')
            if age!=ages[j] or observed!=addmonths(end,age-step):fail('triangle_age_date_mismatch')
            paid=r.n(cell['paid'],f'/claims/triangle/origins/{i}/cells/{j}/paid','RUB','0');reported=r.n(cell['reported'],f'/claims/triangle/origins/{i}/cells/{j}/reported','RUB','0')
            if reported<paid:fail('reported_including_paid_must_cover_paid')
            prepared.append(dict(cell,age_months=age,paid=exact(paid),reported=exact(reported)))
        if day(prepared[-1]['observation_date'],'latest_cell_date')!=r.valuation:fail('latest_diagonal_must_match_valuation')
        cells[identity]={x['age_months']:x for x in prepared};latest[identity]=prepared[-1]
        origins.append(dict(o,cells=prepared))
    unique(origins)
    enddates=[day(o['origin_end_date'],'origin_end') for o in origins]
    if len(set(enddates))!=len(enddates):fail('duplicate_origin_date')
    selection=obj(value['selection'],'reserve_selection',('factors','tail_factors','methods','rationale','source_reference'))
    text(selection['rationale'],'selection_rationale');ref(selection['source_reference']);overrides={}
    for i,s in enumerate(rows(selection['factors'],'selected_factors',0,22)):
        obj(s,'factor_override',('basis','from_age','to_age','factor','rationale','source_reference'))
        if s['basis'] not in ('paid','reported'):fail('factor_basis_required')
        a=r.n(s['from_age'],f'/claims/selection/factors/{i}/from_age','month','1','1200',True);b=r.n(s['to_age'],f'/claims/selection/factors/{i}/to_age','month','1','1200',True)
        factor=r.n(s['factor'],f'/claims/selection/factors/{i}/factor','ratio','1e-100','100');text(s['rationale'],'factor_rationale');ref(s['source_reference'])
        if a not in ages[:-1] or b!=ages[ages.index(a)+1] or (s['basis'],a) in overrides:fail('invalid_or_duplicate_factor_override')
        overrides[s['basis'],a]=factor
    tailobj=obj(selection['tail_factors'],'tail_factors',('paid','reported','rationale','source_reference'));text(tailobj['rationale'],'tail_rationale');ref(tailobj['source_reference'])
    tails={basis_:r.n(tailobj[basis_],'/claims/selection/tail_factors/'+basis_,'ratio','1','100') for basis_ in ('paid','reported')}
    factors=[];cdf={}
    for basis_ in ('paid','reported'):
        chosen=[]
        for a,b in zip(ages[:-1],ages[1:]):
            pair=[(D(cell[a][basis_]),D(cell[b][basis_])) for cell in cells.values() if a in cell and b in cell]
            denominator=sum((x for x,y in pair),ZERO);numerator=sum((y for x,y in pair),ZERO)
            observed=numerator/denominator if denominator else None;selected=overrides.get((basis_,a),observed)
            if selected is None or selected<=0:fail('development_factor_unestimable_requires_explicit_positive_selection')
            chosen.append(selected);factors.append(dict(basis=basis_,from_age=a,to_age=b,paired_origins=len(pair),denominator=exact(denominator),numerator=exact(numerator),observed_factor=exact(observed) if observed is not None else None,selected_factor=exact(selected),selection_basis='explicit_override' if (basis_,a) in overrides else 'volume_weighted_observed',paired_origin_count_below_two=len(pair)<2))
        product=tails[basis_];cdf[basis_,ages[-1]]=product
        for a,factor in reversed(list(zip(ages[:-1],chosen))):product*=factor;cdf[basis_,a]=product
    methods={}
    for s in rows(selection['methods'],'selected_methods',len(origins),len(origins)):
        obj(s,'origin_method',('origin_id','method','basis','rationale','source_reference'));text(s['rationale'],'method_rationale');ref(s['source_reference'])
        if s['origin_id'] not in latest or s['origin_id'] in methods or s['method'] not in ('chain_ladder','bornhuetter_ferguson') or s['basis'] not in ('paid','reported'):fail('selected_method_required_per_origin')
        methods[s['origin_id']]=s
    comparison=[];selected=[];total=ZERO
    for o in origins:
        identity=o['id'];cell=latest[identity];paid=D(cell['paid']);reported=D(cell['reported']);age=cell['age_months'];priorultimate=premiums[identity]*prior[identity] if premiums[identity] is not None and prior[identity] is not None else None;candidates={}
        for basis_ in ('paid','reported'):
            known=D(cell[basis_]);factor=cdf[basis_,age]
            for method in ('chain_ladder','bornhuetter_ferguson'):
                ultimate=known*factor if method=='chain_ladder' else known+priorultimate*(ONE-ONE/factor) if factor>=ONE and priorultimate is not None else None
                row=dict(origin_id=identity,method=method,basis=basis_,development_age=age,cumulative_factor=exact(factor),prior_expected_ultimate=exact(priorultimate) if priorultimate is not None else None,ultimate=exact(ultimate) if ultimate is not None else None,RBNS=exact(reported-paid),IBNR=exact(ultimate-reported) if ultimate is not None else None,unpaid=exact(ultimate-paid) if ultimate is not None else None,status='computed_conditional' if ultimate is not None else 'BF_prior_not_supplied' if priorultimate is None else 'BF_nonnegative_unemerged_fraction_not_satisfied')
                candidates[method,basis_]=row;comparison.append(row)
        decision=methods[identity];row=candidates[decision['method'],decision['basis']]
        if row['ultimate'] is None:fail('selected_BF_requires_prior_and_factor_at_least_one')
        selected.append(dict(row,selection_rationale=decision['rationale'],source_reference=decision['source_reference']));total+=D(row['unpaid'])
    expense=obj(value['settlement_expenses'],'settlement_expenses',('mode','rationale','source_reference'),('ratio','amount'));text(expense['rationale'],'expense_rationale');ref(expense['source_reference'])
    expensebase=sum((max(ZERO,D(x['unpaid'])) for x in selected),ZERO)
    if expense['mode']=='selected_ratio_of_positive_unpaid':
        obj(expense,'ratio_expense',('mode','ratio','rationale','source_reference'));expenseamount=expensebase*r.n(expense['ratio'],'/claims/settlement_expenses/ratio','ratio','0','10')
    elif expense['mode']=='selected_amount':
        obj(expense,'amount_expense',('mode','amount','rationale','source_reference'));expenseamount=r.n(expense['amount'],'/claims/settlement_expenses/amount','RUB','0')
    elif expense['mode']=='none_selected':
        obj(expense,'no_expense',('mode','rationale','source_reference'));expenseamount=ZERO
    else:fail('supported_expense_mode_required')
    recoverables=[];ceded=ZERO
    if 'reinsurance_recoverables' in value:
        if basis['gross_net']!='gross':fail('cannot_deduct_reinsurance_twice_from_net_input')
        for i,x in enumerate(rows(value['reinsurance_recoverables'],'recoverables',len(origins),len(origins))):
            obj(x,'recoverable',('origin_id','amount','observation_date','source_reference'));ref(x['source_reference']);r.observed(x['observation_date'],'recoverable_observation')
            if x['origin_id'] not in latest:fail('unknown_recoverable_origin')
            amount=r.n(x['amount'],f'/claims/reinsurance_recoverables/{i}/amount','RUB','0');ceded+=amount;recoverables.append(deepcopy(x))
        unique(recoverables,'origin_id')
    runoff=[]
    if 'runoff' in value:
        run=obj(value['runoff'],'runoff',('previous_valuation_date','gross_net','amount_basis','rows','source_reference'));previous=r.observed(run['previous_valuation_date'],'previous_valuation');ref(run['source_reference'])
        if run['gross_net']!=basis['gross_net'] or run['amount_basis']!='unpaid_losses_excluding_settlement_expenses':fail('runoff_basis_mismatch')
        if previous>=r.valuation:fail('prior_runoff_valuation_required')
        for i,x in enumerate(rows(run['rows'],'runoff_rows',1,len(origins))):
            obj(x,'runoff_row',('origin_id','prior_paid','prior_unpaid','previous_method','method_change_note','source_reference'));ref(x['source_reference']);text(x['previous_method'],'previous_method');text(x['method_change_note'],'method_change_note')
            identity=x['origin_id']
            if identity not in latest or day(next(o['origin_end_date'] for o in origins if o['id']==identity),'origin_end')>previous:fail('runoff_origin_not_in_prior_cohort')
            oldpaid=r.n(x['prior_paid'],f'/claims/runoff/rows/{i}/prior_paid','RUB','0');oldunpaid=r.n(x['prior_unpaid'],f'/claims/runoff/rows/{i}/prior_unpaid','RUB')
            historic=[cell for cell in cells[identity].values() if cell['observation_date']==run['previous_valuation_date']]
            if historic and oldpaid!=D(historic[0]['paid']):fail('prior_paid_does_not_reconcile_triangle')
            current=next(s for s in selected if s['origin_id']==identity);paidchange=D(latest[identity]['paid'])-oldpaid;remaining=D(current['unpaid']);favourable=oldunpaid-paidchange-remaining
            runoff.append(dict(x,paid_since_previous=exact(paidchange),current_unpaid=exact(remaining),favourable_development=exact(favourable),comparison='prior_unpaid_minus_actual_paid_change_minus_current_unpaid'))
        unique(runoff,'origin_id')
    uncertainty=obj(value['uncertainty'],'reserve_uncertainty',('statement','tail_scenarios','source_reference'));text(uncertainty['statement'],'uncertainty_statement');ref(uncertainty['source_reference']);stresses=[]
    for i,x in enumerate(rows(uncertainty['tail_scenarios'],'tail_scenarios',1,4)):
        obj(x,'tail_scenario',('id','paid','reported','source_reference'));text(x['id'],'tail_scenario_id',100);ref(x['source_reference']);stress={b:r.n(x[b],f'/claims/uncertainty/tail_scenarios/{i}/{b}','ratio','1','100') for b in ('paid','reported')};unpaid=ZERO
        for row in selected:
            basis_=row['basis'];identity=row['origin_id'];factor=cdf[basis_,row['development_age']]*stress[basis_]/tails[basis_];known=D(latest[identity][basis_])
            if row['method']=='bornhuetter_ferguson' and factor<ONE:fail('stressed_BF_factor_below_one')
            ultimate=known*factor if row['method']=='chain_ladder' else known+premiums[identity]*prior[identity]*(ONE-ONE/factor)
            unpaid+=ultimate-D(latest[identity]['paid'])
        stresses.append(dict(x,selected_unpaid=exact(unpaid),change=exact(unpaid-total)))
    unique(stresses)
    return dict(basis=deepcopy(basis),triangle_rows=origins,triangle_age_date_convention='calendar_month_end_preserved_otherwise_day_clamped',development_factors=factors,cumulative_factors=[dict(basis=b,development_age=a,factor=exact(v)) for (b,a),v in cdf.items()],method_comparison=comparison,selected_reserves=selected,selected_unpaid=exact(total),settlement_expenses=dict(expense,positive_unpaid_base=exact(expensebase),amount=exact(expenseamount)),total_with_settlement_expenses=exact(total+expenseamount),reinsurance_review=dict(input_basis=basis['gross_net'],provided_recoverables=recoverables,provided_recoverable_total=exact(ceded) if recoverables else None,gross_unpaid=exact(total) if basis['gross_net']=='gross' else None,net_unpaid=exact(total-ceded) if recoverables else exact(total) if basis['gross_net']=='net' else None,collectability_and_treaty_response_not_established=True),runoff=runoff,uncertainty=dict(uncertainty,tail_scenarios=stresses,statistical_standard_error=None,confidence_interval=None,Mack_estimate_not_performed=True),evidence_gaps=([] if runoff else ['runoff_not_supplied'])+['deterministic_method_and_tail_uncertainty_not_a_statistical_interval'])

def _reserves(c,r):
    if c['mode'] not in ('claims','unearned_premium','comprehensive'):fail('supported_reserve_mode_required')
    required=(*COMMON,*(['claims'] if c['mode']=='claims' else ['unearned_premium'] if c['mode']=='unearned_premium' else ['claims','unearned_premium']))
    obj(c,'reserves',required);claims=_claims(c['claims'],r) if 'claims' in c else None;upr=_upr(c['unearned_premium'],r) if 'unearned_premium' in c else None
    return dict(mode=c['mode'],claims=claims,unearned_premium=upr,regulatory_reserve_compliance_not_established=True,reserve_selection_requires_insurer_and_actuary_review=True)

def _life(c,r):
    if c['mode'] not in ('term_life','annuity','employer_pension'):fail('supported_life_model_required')
    obj(c,'life_pension',(*COMMON,'horizon_years','payment_timing','mortality_tables','mortality_adjustment','discount_curve','participants','sensitivity','model_scope'))
    horizon=r.n(c['horizon_years'],'/horizon_years','year','1','40',True);text(c['model_scope'],'model_scope')
    timing=c['payment_timing']
    if timing not in ('beginning_of_year','end_of_year') or c['mode']=='term_life' and timing!='end_of_year':fail('supported_benefit_timing_required')
    adjustment=obj(c['mortality_adjustment'],'mortality_adjustment',('qx_multiplier','rationale','source_reference'));base_mult=r.n(adjustment['qx_multiplier'],'/mortality_adjustment/qx_multiplier','ratio','0','10');text(adjustment['rationale'],'mortality_adjustment_rationale');ref(adjustment['source_reference'])
    tables={};metadata=[]
    for i,t in enumerate(rows(c['mortality_tables'],'mortality_tables',1,2)):
        obj(t,'mortality_table',('id','sex','metadata','population','rows'))
        identity=text(t['id'],'table_id',100)
        if identity in tables or t['sex'] not in ('male','female','unisex'):fail('unique_table_and_explicit_sex_required')
        meta=r.metadata(t['metadata'],'mortality_metadata');text(t['population'],'mortality_population');qx={}
        for j,x in enumerate(rows(t['rows'],'mortality_rows',1,80)):
            obj(x,'mortality_qx',('age','qx'));age=r.n(x['age'],f'/mortality_tables/{i}/rows/{j}/age','year','0','130',True);q=r.n(x['qx'],f'/mortality_tables/{i}/rows/{j}/qx','ratio','0','1')
            if age in qx:fail('duplicate_mortality_age')
            qx[age]=q
        tables[identity]=(t['sex'],qx);metadata.append(dict(id=identity,sex=t['sex'],metadata=meta,population=t['population'],rows=deepcopy(t['rows'])))
    curve=obj(c['discount_curve'],'discount_curve',('metadata','compounding','points'));curve_meta=r.metadata(curve['metadata'],'discount_metadata')
    if curve['compounding']!='annual_effective_zero':fail('annual_effective_zero_curve_required')
    rates={}
    for i,p in enumerate(rows(curve['points'],'discount_points',horizon,horizon)):
        obj(p,'discount_point',('year','rate'));year=r.n(p['year'],f'/discount_curve/points/{i}/year','year','1',str(horizon),True);rate=r.n(p['rate'],f'/discount_curve/points/{i}/rate','ratio','-0.9999999999','10')
        if year in rates:fail('duplicate_discount_year')
        rates[year]=rate
    if set(rates)!=set(range(1,horizon+1)):fail('complete_curve_no_extrapolation_required')
    prepared=[]
    for i,p in enumerate(rows(c['participants'],'participants',1,5)):
        common=('id','sex','age','table_id','number_of_lives','deferral_years','payment_years','lapse','observation_date','source_reference')
        extra=('annual_payment',) if c['mode']=='annuity' else ('death_benefit','future_premiums','expenses') if c['mode']=='term_life' else ('salary','salary_growth','accrued_service_years','accrual_rate','benefit_formula')
        obj(p,'participant',(*common,*extra));text(p['id'],'anonymous_participant_id',100);ref(p['source_reference']);r.observed(p['observation_date'],'participant_observation')
        age=r.n(p['age'],f'/participants/{i}/age','year','0','130',True);lives=r.n(p['number_of_lives'],f'/participants/{i}/number_of_lives','life','1','1000000000',True);defer=r.n(p['deferral_years'],f'/participants/{i}/deferral_years','year','0',str(horizon),True);term=r.n(p['payment_years'],f'/participants/{i}/payment_years','year','1',str(horizon),True)
        if defer+term>horizon:fail('complete_horizon_must_cover_benefit_term')
        if p['table_id'] not in tables or tables[p['table_id']][0]!=p['sex']:fail('participant_mortality_table_sex_mismatch')
        qx=tables[p['table_id']][1]
        lifehorizon=defer+term
        if any(age+t not in qx for t in range(lifehorizon)):fail('missing_age_specific_qx_no_extrapolation')
        lapse=obj(p['lapse'],'lapse',('mode','rationale','source_reference'),('probabilities',));text(lapse['rationale'],'lapse_rationale');ref(lapse['source_reference']);lapses={t:ZERO for t in range(1,lifehorizon+1)}
        if lapse['mode']=='competing_decrements':
            for j,x in enumerate(rows(lapse.get('probabilities'),'lapse_probabilities',lifehorizon,lifehorizon)):
                obj(x,'lapse_probability',('year','probability'));year=r.n(x['year'],f'/participants/{i}/lapse/probabilities/{j}/year','year','1',str(horizon),True);prob=r.n(x['probability'],f'/participants/{i}/lapse/probabilities/{j}/probability','ratio','0','1')
                if year!=j+1:fail('ordered_complete_lapse_probabilities_required')
                if c['mode']=='employer_pension' and year>defer and prob!=ZERO:fail('employment_lapse_cannot_remove_retired_benefit')
                lapses[year]=prob
        elif lapse['mode']!='none_selected' or 'probabilities' in lapse:fail('explicit_lapse_model_required')
        extra_values={}
        if c['mode']=='annuity':extra_values['annual_payment']=r.n(p['annual_payment'],f'/participants/{i}/annual_payment','RUB','0')
        elif c['mode']=='term_life':
            extra_values['death_benefit']=r.n(p['death_benefit'],f'/participants/{i}/death_benefit','RUB','0')
            premium=obj(p['future_premiums'],'future_premiums',('annual_amount','years','timing','source_reference'));ref(premium['source_reference'])
            if premium['timing'] not in ('beginning_of_year','end_of_year'):fail('premium_timing_required')
            extra_values['annual_premium']=r.n(premium['annual_amount'],f'/participants/{i}/future_premiums/annual_amount','RUB','0');extra_values['premium_years']=r.n(premium['years'],f'/participants/{i}/future_premiums/years','year','0',str(lifehorizon),True)
            expense=obj(p['expenses'],'life_expenses',('annual_amount','timing','source_reference'));ref(expense['source_reference'])
            if expense['timing'] not in ('beginning_of_year','end_of_year'):fail('expense_timing_required')
            extra_values['annual_expense']=r.n(expense['annual_amount'],f'/participants/{i}/expenses/annual_amount','RUB','0')
        else:
            if p['benefit_formula']!='final_salary_linear_accrued_service_annual_pension':fail('supported_projected_unit_credit_formula_required')
            extra_values['salary']=r.n(p['salary'],f'/participants/{i}/salary','RUB','0');extra_values['salary_growth']=r.n(p['salary_growth'],f'/participants/{i}/salary_growth','ratio','-0.9999999999','10');extra_values['accrued_service_years']=r.n(p['accrued_service_years'],f'/participants/{i}/accrued_service_years','year','0','80');extra_values['accrual_rate']=r.n(p['accrual_rate'],f'/participants/{i}/accrual_rate','ratio','0','1')
        prepared.append((p,age,lives,defer,term,qx,lapses,extra_values))
    unique([x[0] for x in prepared])
    if max(x[3]+x[4] for x in prepared)!=horizon:fail('horizon_must_equal_latest_selected_benefit_end')
    def project(rate_delta,mortality_mult,detail):
        result=[];total=ZERO
        for p,age,lives,defer,term,qx,lapses,extra in prepared:
            active=ONE;flows=[];benefitpv=ZERO;premiumpv=ZERO;expensepv=ZERO;employer=None
            if c['mode']=='employer_pension':
                salary=extra['salary']*(ONE+extra['salary_growth'])**defer;annual=salary*extra['accrual_rate']*extra['accrued_service_years'];projected=salary*extra['accrual_rate']*(extra['accrued_service_years']+defer)
                employer=dict(projected_retirement_salary=exact(salary),total_projected_annual_pension=exact(projected),attributed_accrued_annual_pension=exact(annual),attribution='linear_service_only_no_additional_vesting_or_benefit_cap_model')
            elif c['mode']=='annuity':annual=extra['annual_payment']
            for t in range(1,defer+term+1):
                q=qx[age+t-1]*base_mult*mortality_mult;l=lapses[t]
                if q<ZERO or q>ONE or q+l>ONE:fail('stressed_competing_probabilities_outside_unit_simplex')
                rate=rates[t]+rate_delta
                if rate<=-ONE:fail('stressed_discount_rate_outside_domain')
                df=(ONE+rate)**(-t);dfstart=ONE if t==1 else (ONE+rates[t-1]+rate_delta)**(-(t-1))
                endactive=active*(ONE-q-l);deathprob=active*q;lapseprob=active*l;eligible=defer<t<=defer+term
                benefit=ZERO;premium=ZERO;expense=ZERO
                if c['mode']=='term_life':
                    benefit=extra['death_benefit']*deathprob*df if eligible else ZERO
                    premstart=p['future_premiums']['timing']=='beginning_of_year';expstart=p['expenses']['timing']=='beginning_of_year'
                    if t<=extra['premium_years']:premium=extra['annual_premium']*(active if premstart else endactive)*(dfstart if premstart else df)
                    expense=extra['annual_expense']*(active if expstart else endactive)*(dfstart if expstart else df)
                elif eligible:benefit=annual*(active if timing=='beginning_of_year' else endactive)*(dfstart if timing=='beginning_of_year' else df)
                benefitpv+=benefit;premiumpv+=premium;expensepv+=expense
                if detail:flows.append(dict(year=t,attained_age=age+t-1,q_death=exact(q),q_lapse=exact(l),active_probability_start=exact(active),active_probability_end=exact(endactive),death_probability=exact(deathprob),lapse_probability=exact(lapseprob),discount_factor_end=exact(df),discount_factor_start=exact(dfstart),benefit_eligible=eligible,benefit_present_value_per_life=exact(benefit),premium_present_value_per_life=exact(premium),expense_present_value_per_life=exact(expense)))
                active=endactive
            reserve=(benefitpv+expensepv-premiumpv)*lives;total+=reserve
            if detail:result.append(dict(id=p['id'],sex=p['sex'],age=age,table_id=p['table_id'],number_of_lives=lives,benefit_timing=timing,deferral_years=defer,payment_years=term,source_reference=p['source_reference'],lapse_model=deepcopy(p['lapse']),employer_benefit_attribution=employer,projection_rows=flows,benefit_present_value=exact(benefitpv*lives),premium_present_value=exact(premiumpv*lives),expense_present_value=exact(expensepv*lives),present_value=exact(reserve)))
        return total,result
    total,participants=project(ZERO,ONE,True);sensitivity=[]
    for i,x in enumerate(rows(c['sensitivity'],'life_sensitivity',2,6)):
        obj(x,'life_stress',('id','discount_rate_delta','mortality_multiplier','rationale','source_reference'));text(x['id'],'stress_id',100);text(x['rationale'],'stress_rationale');ref(x['source_reference']);delta=r.n(x['discount_rate_delta'],f'/sensitivity/{i}/discount_rate_delta','ratio','-10','10');mult=r.n(x['mortality_multiplier'],f'/sensitivity/{i}/mortality_multiplier','ratio','0','10');stressed,_=project(delta,mult,False)
        sensitivity.append(dict(x,present_value=exact(stressed),change=exact(stressed-total)))
    unique(sensitivity)
    return dict(mode=c['mode'],model_scope=c['model_scope'],horizon_years=horizon,payment_timing=timing,assumption_metadata=dict(mortality_adjustment=deepcopy(adjustment),discount_curve_metadata=curve_meta,mortality_projection='selected_static_age_specific_qx_no_automatic_improvement'),mortality_tables=metadata,discount_curve=deepcopy(curve),participant_results=participants,present_value=exact(total),present_value_basis='benefits_plus_selected_expenses_minus_selected_future_premiums' if c['mode']=='term_life' else 'conditional_expected_benefit_cashflows',sensitivity=sensitivity,personal_data_local_only=True,IAS19_or_NPF_or_insurance_compliance_not_established=True,evidence_gaps=['mortality_population_fit_curve_market_basis_and_model_adequacy_not_established','no_automatic_mortality_extrapolation_or_unselected_stresses'])

def _run(function,data,units=False):
    if function not in FUNCTIONS:fail('unknown_actuarial_calculation')
    with localcontext(CTX):
        r=Reader(data)
        try:result={'tariff':_tariff,'reserves':_reserves,'life_pension':_life}[function](r.data,r)
        except (KeyError,TypeError,IndexError,AttributeError,OverflowError,RecursionError):raise ValueError('invalid_'+function+'_structure') from None
        except DecimalException:raise ValueError('unsupported_'+function+'_numeric_condition') from None
        if units:return r.units
        result.update(as_of=data['as_of'],valuation_date=data['valuation_date'],jurisdiction='RU',data_scope=data['data_scope'],currency='RUB',assisted_draft=True,analysis_only=True,arithmetic_precision_digits=CTX.prec,source_semantics_verified=False,current_legal_applicability_verified=False,external_network_used=False,external_code_executed=False,human_review_required=True)
        return result
def tariff(data):return _run('tariff',data)
def reserves(data):return _run('reserves',data)
def life_pension(data):return _run('life_pension',data)
def input_units(function,data):return _run(function,data,True)
def selected_texts(function,data):
    _run(function,data);selected={}
    def visit(value,path=''):
        if type(value) is dict:
            for key,item in value.items():
                pointer=path+'/'+key
                if key=='excerpt':selected[pointer]=text(item,'selected_excerpt')
                else:visit(item,pointer)
        elif type(value) is list:
            for i,item in enumerate(value):visit(item,path+'/'+str(i))
    visit(data);return selected

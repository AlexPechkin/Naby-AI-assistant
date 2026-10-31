"""Bounded local appraisal arithmetic. Evidence and agreement are host-owned."""
from copy import deepcopy
from datetime import date
from decimal import Decimal,Context,localcontext,ROUND_HALF_UP,ROUND_FLOOR
from functools import wraps
import re
D=Decimal
CTX=Context(prec=128,rounding=ROUND_HALF_UP)
ORDER=('bargain','date','location','area','floor','condition')
def fail(code):raise ValueError(code)
def obj(v,name):
    if type(v) is not dict:fail(name+'_object_required')
    return v
def arr(v,name,minimum=0,maximum=100):
    if type(v) is not list or not minimum<=len(v)<=maximum:fail(name+'_list_required')
    return v
def text(v,name,limit=4000):
    if type(v) is not str or not v.strip() or len(v)>limit:fail(name+'_text_required')
    return v.strip()
def num(v,name,low='0',high='1e20'):
    if type(v) not in (str,int,Decimal) or not re.fullmatch(r'-?(?:0|[1-9]\d{0,20})(?:\.\d{1,8})?',str(v)):fail(name+'_exact_decimal_required')
    n=D(v)
    if not n.is_finite() or not D(low)<=n<=D(high):fail(name+'_range')
    return n
def day(v,name):
    if type(v) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',v):fail(name+'_iso_date_required')
    try:return date.fromisoformat(v)
    except ValueError:fail(name+'_invalid_date')
def tri(v,name):
    if v is not None and type(v) is not bool:fail(name+'_boolean_or_unknown')
    return v
def ref(v,name):return text(v,name,1000)
def money(v):return str(v.quantize(D('.01'),rounding=ROUND_HALF_UP))
def guard(fn):
    @wraps(fn)
    def wrapped(data):
        with localcontext(CTX):
            c=deepcopy(obj(data,'data'));result=fn(c)
            unresolved=[r['id'] for r in result.get('comparables',[]) if r.get('tax_basis_gap')]
            if c['tax_basis'] in ('unknown','observed_market_prices'):unresolved.insert(0,'task_tax_basis_unresolved')
            conditional=c['tax_basis'] in ('unknown','observed_market_prices') or any(r.get('tax_basis_gap') and r['included'] for r in result.get('comparables',[]))
            result.update(task_scope=deepcopy(c['task_scope']),assignment_reference=c['assignment_reference'],rights=c['rights'],purpose=c['purpose'],value_type=c['value_type'],tax_basis=c['tax_basis'],tax_basis_reference=c['tax_basis_reference'],tax_basis_policy=deepcopy(c['tax_basis_policy']),tax_basis_is_declared_not_legally_validated=True,unresolved_tax_basis=unresolved,conditional_arithmetic=conditional)
            return result
    return wrapped
def base(c):
    asof=day(c.get('as_of'),'as_of');valued=day(c.get('valuation_date'),'valuation_date')
    if valued>asof:fail('valuation_after_analysis_date')
    if c.get('currency')!='RUB':fail('only_rub_supported')
    if c.get('tax_basis') not in ('vat_included','vat_excluded','not_applicable','unknown','observed_market_prices'):fail('explicit_tax_basis_required')
    ref(c.get('tax_basis_reference'),'tax_basis_reference')
    taxpolicy=obj(c.get('tax_basis_policy'),'tax_basis_policy')
    if taxpolicy.get('unknown_handling') not in ('retain_for_conditional_arithmetic','exclude'):fail('unknown_tax_basis_policy')
    ref(taxpolicy.get('source_reference'),'tax_policy_source');text(taxpolicy.get('rationale'),'tax_policy_rationale')
    ident=text(c.get('object_id'),'object_id',500);rights=text(c.get('rights'),'rights',1000)
    purpose=text(c.get('purpose'),'purpose',1000);value_type=c.get('value_type')
    if value_type!='market':fail('only_market_value_approach_supported')
    scope=obj(c.get('task_scope'),'task_scope')
    if scope!=dict(object_id=ident,rights=rights,valuation_date=valued.isoformat(),currency='RUB',purpose=purpose,value_type=value_type):fail('task_scope_mismatch')
    ref(c.get('assignment_reference'),'assignment_reference')
    return asof,valued
def target(c):
    t=obj(c.get('target'),'target')
    if c.get('quantity_unit') not in ('m2','m3'):fail('quantity_unit_required')
    if t.get('object_id')!=c['object_id'] or t.get('rights')!=c['rights']:fail('target_task_mismatch')
    for key in ('segment','location','condition'):text(t.get(key),'target_'+key)
    return t,num(t.get('area'),'target_area','0.00000001')
def median(values):
    v=sorted(values);n=len(v)
    return v[n//2] if n%2 else (v[n//2-1]+v[n//2])/2
def comparables(c):
    _,valued=base(c);t,area=target(c);p=obj(c.get('comparability_policy'),'comparability_policy')
    low=num(p.get('area_ratio_min'),'area_ratio_min','0.00000001','1000');high=num(p.get('area_ratio_max'),'area_ratio_max','0.00000001','1000')
    if low>high:fail('area_ratio_bounds')
    minimum=num(p.get('minimum_count'),'minimum_count','1','100')
    if minimum!=minimum.to_integral_value():fail('minimum_count_integer')
    ref(p.get('source_reference'),'comparability_policy_source');text(p.get('explanation'),'comparability_policy_explanation')
    result=[];ids=set()
    for x in arr(c.get('comparables'),'comparables',1,100):
        obj(x,'comparable');ident=text(x.get('id'),'comparable_id',200);property_id=text(x.get('property_id'),'property_id',500)
        if ident in ids:fail('duplicate_comparable_id')
        ids.add(ident);ref(x.get('source_reference'),'comparable_source');when=day(x.get('date'),'comparable_date')
        if when>valued:fail('comparable_after_valuation_date')
        if x.get('price_type') not in ('offer','transaction') or x.get('price_basis') not in ('total','per_unit'):fail('comparable_price_basis_type')
        price=num(x.get('price'),'comparable_price','0.00000001');a=num(x.get('area'),'comparable_area','0.00000001')
        if x.get('quantity_unit')!=c['quantity_unit']:fail('comparable_quantity_unit_mismatch')
        for key in ('segment','rights','location','condition','characteristics'):text(x.get(key),'comparable_'+key)
        location=tri(x.get('location_comparable'),'location_comparable');condition=tri(x.get('condition_comparable'),'condition_comparable')
        text(x.get('comparability_reason'),'comparability_reason');ref(x.get('comparability_reference'),'comparability_reference')
        reasons=[]
        if x['segment']!=t['segment']:reasons.append('different_segment')
        if x['rights']!=t['rights']:reasons.append('different_rights')
        known=('vat_included','vat_excluded','not_applicable');rowbasis=x.get('tax_basis')
        if rowbasis is not None and rowbasis not in known+('unknown','observed_market_prices'):fail('comparable_tax_basis_enum')
        taxgap=rowbasis not in known
        if taxgap:
            if c['tax_basis_policy']['unknown_handling']=='exclude':reasons.append('different_or_unknown_tax_basis_requires_normalization')
        elif c['tax_basis'] in known and rowbasis!=c['tax_basis']:reasons.append('different_or_unknown_tax_basis_requires_normalization')
        if not low<=a/area<=high:reasons.append('outside_supplied_area_ratio')
        for key,v in (('location',location),('condition',condition)):
            if v is not True:reasons.append(key+('_not_comparable' if v is False else '_comparability_unknown'))
        unit=price/a if x['price_basis']=='total' else price
        result.append(dict(x,price=str(price),area=str(a),unit_price=str(unit),total_price=str(price if x['price_basis']=='total' else price*a),tax_basis_gap=taxgap,excluded_reasons=reasons,included=not reasons,status='included_pending_appraiser_review' if not reasons else 'excluded_under_supplied_policy'))
    if c['tax_basis'] in ('unknown','observed_market_prices'):
        knownbases={r.get('tax_basis') for r in result if r['included'] and not r['tax_basis_gap']}
        if len(knownbases)>1:
            for row in result:
                if row['included'] and not row['tax_basis_gap']:row['included']=False;row['excluded_reasons'].append('mixed_known_tax_bases_require_normalization');row['status']='excluded_under_supplied_policy'
    groups={}
    for row in result:groups.setdefault(row['property_id'],[]).append(row)
    fields=('date','price_type','area','unit_price','segment','rights','location','condition','location_comparable','condition_comparable','tax_basis')
    for group in groups.values():
        if len(group)<2:continue
        identical=all(all(row.get(k)==group[0].get(k) for k in fields) and row.get('adjustments')==group[0].get('adjustments') for row in group[1:])
        for row in group[1:] if identical else group:
            row['included']=False;row['excluded_reasons'].append('duplicate_property' if identical else 'duplicate_property_conflict_requires_resolution');row['status']='excluded_under_supplied_policy'
    return result,area
def outliers(rows,policy):
    p=obj(policy,'outlier_policy');method=p.get('method')
    if method not in ('none','iqr'):fail('outlier_method')
    ref(p.get('source_reference'),'outlier_source');text(p.get('rationale'),'outlier_rationale')
    if method=='none':return dict(method=method,applicable=False,reason='no_statistical_exclusion_requested')
    factor=num(p.get('multiplier'),'outlier_multiplier','0.00000001','100');values=sorted(D(r['unit_price']) for r in rows if r['included']);n=len(values)
    if n<4:return dict(method=method,applicable=False,reason='fewer_than_four_eligible_comparables',multiplier=str(factor))
    q1=median(values[:n//2]);q3=median(values[(n+1)//2:]);iqr=q3-q1
    if iqr==0:return dict(method=method,applicable=False,reason='zero_iqr_requires_review',q1=str(q1),q3=str(q3))
    low=q1-factor*iqr;high=q3+factor*iqr
    for r in rows:
        if r['included'] and not low<=D(r['unit_price'])<=high:r['included']=False;r['excluded_reasons'].append('outside_supplied_iqr_fence');r['status']='excluded_under_supplied_policy'
    return dict(method=method,applicable=True,multiplier=str(factor),q1=str(q1),q3=str(q3),lower=str(low),upper=str(high),formula='Tukey median of halves; omit central observation when odd')
@guard
def market_analysis(c):
    rows,area=comparables(c);stat=outliers(rows,c.get('outlier_policy'));discount=obj(c.get('bargain_discount'),'bargain_discount')
    pct=num(discount.get('percent'),'bargain_percent','0','99.99999999');ref(discount.get('source_reference'),'bargain_source');when=day(discount.get('date'),'bargain_date')
    if when>day(c['valuation_date'],'valuation_date'):fail('bargain_source_after_valuation')
    if discount.get('year')!=str(when.year):fail('bargain_source_year_mismatch')
    for row in rows:row.update(indicative_net_unit_price=str(D(row['unit_price'])*(1-pct/100) if row['price_type']=='offer' else D(row['unit_price'])),bargain_adjustment_applied=row['price_type']=='offer')
    values=[D(r['indicative_net_unit_price']) for r in rows if r['included']]
    if not values:fail('no_eligible_comparables')
    return dict(as_of=c['as_of'],valuation_date=c['valuation_date'],object_id=c['object_id'],currency='RUB',quantity_unit=c['quantity_unit'],region=text(c.get('region'),'region'),segment=c['target']['segment'],macro_factors=[text(x,'macro_factor') for x in arr(c.get('macro_factors'),'macro_factors',1,30)],pricing_factors=[text(x,'pricing_factor') for x in arr(c.get('pricing_factors'),'pricing_factors',1,30)],comparables=rows,bargain_discount=discount,outlier_analysis=stat,range=[money(min(values)),money(max(values))],range_unit='RUB/'+c['quantity_unit'],arithmetic_mean=money(sum(values)/len(values)),included_count=len(values),excluded_count=len(rows)-len(values),insufficient_comparables_under_supplied_policy=len(values)<int(c['comparability_policy']['minimum_count']),mean_is_not_final_value=True,selection_policy_is_declared=True,assignment_approval_established=False)
@guard
def sales_comparison(c):
    rows,area=comparables(c);stat=outliers(rows,c.get('outlier_policy'));w=obj(c.get('weighting'),'weighting');mode=w.get('method')
    if mode not in ('inverse_gross_adjustment','supplied'):fail('weighting_method')
    ref(w.get('source_reference'),'weighting_source');text(w.get('rationale'),'weighting_rationale');eligible=[]
    for row in rows:
        if not row['included']:continue
        current=original=D(row['unit_price']);gross=D(0);changes=[];kinds=[]
        for a in arr(row.get('adjustments'),'adjustments',len(ORDER),len(ORDER)):
            obj(a,'adjustment');kind=a.get('kind');kinds.append(kind)
            if kind not in ORDER:fail('adjustment_kind')
            ref(a.get('source_reference'),'adjustment_source');when=day(a.get('date'),'adjustment_date')
            if when>day(c['valuation_date'],'valuation_date'):fail('adjustment_after_valuation')
            if a.get('year')!=str(when.year):fail('adjustment_year_mismatch')
            text(a.get('rationale'),'adjustment_rationale');form=a.get('mode');before=current
            if form=='not_applicable':
                if 'value' in a:fail('not_applicable_adjustment_has_value')
            elif form=='factor':current*=num(a.get('value'),'adjustment_factor','0.00000001','100')
            elif form=='amount_per_unit':current+=num(a.get('value'),'adjustment_amount','-1e20','1e20')
            else:fail('adjustment_mode')
            if kind=='bargain' and row['price_type']=='transaction' and current!=before:fail('transaction_cannot_receive_offer_discount')
            if current<=0:fail('adjusted_price_not_positive')
            gross+=abs(current-before)/original;changes.append(dict(a,before=str(before),after=str(current),change=str(current-before)))
        if tuple(kinds)!=ORDER:fail('adjustment_order_and_full_coverage_required')
        raw=1/(1+gross) if mode=='inverse_gross_adjustment' else num(row.get('weight'),'supplied_weight')
        row.update(adjustments=changes,adjusted_unit_price=str(current),adjusted_price=money(current*area),gross_relative_adjustment=str(gross),weight_raw=str(raw),total_factor=str(current/original));eligible.append(row)
    if not eligible:fail('no_eligible_comparables')
    total=sum(D(r['weight_raw']) for r in eligible)
    if total<=0:fail('weights_not_positive')
    weighted=sum(D(r['adjusted_unit_price'])*D(r['weight_raw']) for r in eligible)/total;weights=[D(r['weight_raw'])/total for r in eligible];scale=D(1000000)
    floors=[(v*scale).to_integral_value(rounding=ROUND_FLOOR) for v in weights];remainder=int(scale-sum(floors));indices=sorted(range(len(eligible)),key=lambda i:(-(weights[i]*scale-floors[i]),i))
    for i in indices[:remainder]:floors[i]+=1
    for i,row in enumerate(eligible):row.update(weight=str(weights[i]),display_weight=str((floors[i]/scale).quantize(D('.000001'))))
    mean=sum(D(r['adjusted_unit_price']) for r in eligible)/len(eligible)
    policy=obj(c.get('cv_policy'),'cv_policy');threshold=num(policy.get('threshold'),'cv_threshold','0','100');ref(policy.get('source_reference'),'cv_source');text(policy.get('rationale'),'cv_rationale')
    if policy.get('threshold_unit') not in ('fraction','percent'):fail('cv_threshold_unit')
    if policy['threshold_unit']=='percent':threshold/=100
    if policy.get('variance_basis') not in ('population','sample'):fail('cv_variance_basis')
    denominator=len(eligible)-(1 if policy['variance_basis']=='sample' else 0)
    cv=None if denominator==0 else (sum((D(r['adjusted_unit_price'])-mean)**2 for r in eligible)/denominator).sqrt()/mean
    insufficient=len(eligible)<int(c['comparability_policy']['minimum_count'])
    return dict(as_of=c['as_of'],valuation_date=c['valuation_date'],object_id=c['object_id'],currency='RUB',quantity_unit=c['quantity_unit'],target_quantity=str(area),comparables=rows,outlier_analysis=stat,weighting=w,weighted_unit_price=str(weighted),weighted_unit_price_rounded=money(weighted),weighted_value=money(weighted*area),coefficient_of_variation=None if cv is None else str(cv),coefficient_of_variation_percent=None if cv is None else str(cv*100),cv_policy=policy,display_weights_sum=str(sum(floors)/scale),weight_rounding_used_for_value=False,review_comparables_required=insufficient or cv is None or cv>threshold,insufficient_comparables_under_supplied_policy=insufficient,single_observation_is_not_market_representativeness=len(eligible)==1,intermediate_result_not_final_value=True,assignment_approval_established=False)

def rate(c,key,valued):
    amount=num(c.get(key),key,'0.00000001','2');basis=obj(obj(c.get('rate_basis'),'rate_basis').get(key),key+'_basis')
    if basis.get('method') not in ('market','cumulative'):fail('rate_basis_method')
    ref(basis.get('source_reference'),key+'_source');when=day(basis.get('date'),key+'_date')
    if when>valued:fail('rate_after_valuation_date')
    text(basis.get('explanation'),key+'_explanation')
    if basis['method']=='cumulative':
        total=D(0);kinds=[]
        for part in arr(basis.get('components'),'rate_components',1,30):
            obj(part,'rate_component');text(part.get('label'),'component_label');ref(part.get('source_reference'),'component_source')
            if part.get('kind') not in ('risk_free','premium','growth_adjustment','other'):fail('rate_component_kind')
            if day(part.get('date'),'rate_component_date')>valued:fail('rate_component_after_valuation_date')
            kinds.append(part['kind']);total+=num(part.get('value'),'component_value','-2','2')
        if kinds.count('risk_free')!=1 or total!=amount:fail('cumulative_rate_sum_or_risk_free')
    return amount,deepcopy(basis)
def rental(c):
    legacy='market_rent_annual' in c;normalized='rent_input' in c
    if legacy==normalized:fail('choose_annual_rent_or_original_rent_input')
    if legacy:
        value=num(c['market_rent_annual'],'market_rent_annual','0.00000001');ref(c.get('rent_source_reference'),'rent_source')
        return value,dict(source_amount=str(value),source_unit='RUB/year',annual_period_factor='1',quantity_factor='1',annual_rent_unrounded=str(value),source_reference=c['rent_source_reference'])
    r=obj(c['rent_input'],'rent_input');amount=num(r.get('amount'),'original_rent_amount','0.00000001');ref(r.get('source_reference'),'original_rent_source')
    if r.get('period') not in ('month','year') or r.get('basis') not in ('total','per_unit'):fail('original_rent_period_or_basis')
    period=D(12) if r['period']=='month' else D(1);quantity=D(1)
    if r['basis']=='per_unit':
        if r.get('quantity_unit')!='m2':fail('only_m2_rent_normalization_supported')
        quantity=num(r.get('area'),'rented_area','0.00000001')
    elif 'area' in r or 'quantity_unit' in r:fail('total_rent_must_not_have_quantity_multiplier')
    value=amount*period*quantity;unit='RUB/'+('m2/' if r['basis']=='per_unit' else '')+r['period']
    return value,dict(source_amount=str(amount),source_unit=unit,annual_period_factor=str(period),quantity_factor=str(quantity),annual_rent_unrounded=str(value),source_reference=r['source_reference'])
def operating(c,occupancy):
    rent,derivation=rental(c);other=num(c.get('other_income_annual'),'other_income');flag=c.get('other_income_occupancy_sensitive')
    if type(flag) is not bool:fail('other_income_occupancy_sensitive_boolean')
    pgi=rent+other;egi=rent*occupancy+other*(occupancy if flag else 1);expense=D(0);rows=[];taxes=set();ids=set()
    for row in arr(c.get('operating_expenses'),'operating_expenses',2,100):
        obj(row,'operating_expense');ident=text(row.get('id'),'expense_id',200)
        if ident in ids:fail('duplicate_expense_id')
        ids.add(ident);kind=row.get('category')
        if kind not in ('operating','property_tax','land_tax'):fail('expense_category')
        ref(row.get('source_reference'),'expense_source');text(row.get('basis'),'expense_basis')
        if kind in ('property_tax','land_tax'):
            if kind in taxes:fail('duplicate_tax_expense')
            taxes.add(kind)
        mode=row.get('mode')
        if mode=='fixed_annual':value=num(row.get('amount'),'expense_amount')
        elif mode=='fraction_of_egi':value=egi*num(row.get('fraction'),'expense_fraction','0','1')
        else:fail('expense_mode')
        expense+=value;rows.append(dict(row,annual_amount=str(value)))
    if taxes!={'property_tax','land_tax'}:fail('explicit_property_and_land_tax_rows_required')
    return rent,other,pgi,egi,expense,egi-expense,rows,derivation
def income_result(c,occupancy,rates):
    rent,other,pgi,egi,expense,noi,expenses,derivation=operating(c,occupancy);mode=c['method'];direct=dcf=None;flows=[];reversion=discounted_reversion=None;limits=[]
    if mode in ('direct','both'):
        if noi>0:direct=noi/rates['cap_rate']
        else:limits.append('direct_capitalization_not_applicable_to_nonpositive_noi')
    if mode in ('dcf','both'):
        years=num(c.get('years'),'years','1','50')
        if years!=years.to_integral_value():fail('years_integer')
        years=int(years)
        if c.get('cashflow_timing')!='end_year':fail('only_explicit_end_year_timing_supported')
        flowmode=c.get('cashflow_model');growth=num(c.get('growth_rate'),'growth_rate','-0.99','2');capex=num(c.get('capital_expenditure_annual'),'capital_expenditure_annual');supplied=c.get('cashflows')
        if flowmode=='explicit':arr(supplied,'cashflows',years,years)
        elif flowmode!='projected_noi':fail('cashflow_model')
        pv=D(0)
        for i in range(1,years+1):
            if flowmode=='explicit':
                item=obj(supplied[i-1],'cashflow')
                if type(item.get('year')) is not int or item['year']!=i:fail('cashflow_year_sequence')
                ref(item.get('source_reference'),'cashflow_source');n=num(item.get('noi'),'cashflow_noi','-1e20');ex=num(item.get('capital_expenditure'),'cashflow_capex')
            else:n=noi*(1+growth)**(i-1);ex=capex
            net=n-ex;discounted=net/(1+rates['discount_rate'])**i;pv+=discounted;flows.append(dict(year=i,noi=str(n),capital_expenditure=str(ex),net_cashflow=str(net),discounted=str(discounted),display_discounted=money(discounted)))
        terminal=num(c.get('terminal_noi'),'terminal_noi','0.00000001') if flowmode=='explicit' else noi*(1+growth)**years;exitcost=num(c.get('exit_cost_fraction'),'exit_cost_fraction','0','0.99999999')
        if terminal<=0:limits.append('positive_terminal_noi_required_for_capitalized_reversion')
        else:reversion=terminal/rates['exit_cap_rate']*(1-exitcost);discounted_reversion=reversion/(1+rates['discount_rate'])**years;dcf=pv+discounted_reversion
    return dict(market_rent_annual=money(rent),rental_derivation=derivation,other_income_annual=money(other),occupancy=str(occupancy),operating_expenses=money(expense),expense_lines=expenses,pgi=money(pgi),egi=money(egi),noi=money(noi),noi_unrounded=str(noi),unrounded=dict(pgi=str(pgi),egi=str(egi),operating_expenses=str(expense),noi=str(noi)),noi_display_rounding_adjustment=money(D(money(noi))-(D(money(egi))-D(money(expense)))),direct_capitalization_value=None if direct is None else money(direct),cashflows=flows,reversion=None if reversion is None else money(reversion),discounted_reversion=None if discounted_reversion is None else money(discounted_reversion),dcf_value=None if dcf is None else money(dcf),limitations=limits)
@guard
def income_approach(c):
    _,valued=base(c);mode=c.get('method')
    if c.get('inputs_on_declared_tax_basis') is not True:fail('income_tax_basis_alignment_required')
    if c['tax_basis'] in ('unknown','observed_market_prices') and c['tax_basis_policy']['unknown_handling']=='exclude':fail('unknown_income_tax_basis_excluded_by_policy')
    if mode not in ('direct','dcf','both'):fail('income_method')
    occupancy=num(c.get('occupancy'),'occupancy','0','1')
    for key in ('occupancy_source_reference','other_income_source_reference'):ref(c.get(key),key)
    keys=('cap_rate',) if mode=='direct' else ('discount_rate','exit_cap_rate') if mode=='dcf' else ('cap_rate','discount_rate','exit_cap_rate');rates={};basis={}
    for key in keys:rates[key],basis[key]=rate(c,key,valued)
    result=income_result(c,occupancy,rates);sensitivity=[];ids=set()
    for s in arr(c.get('sensitivity_scenarios'),'sensitivity_scenarios',1,30):
        obj(s,'sensitivity');ident=text(s.get('id'),'sensitivity_id',200)
        if ident in ids:fail('duplicate_sensitivity_id')
        ids.add(ident);occ=num(s.get('occupancy'),'sensitivity_occupancy','0','1');var={key:num(s.get(key),'sensitivity_'+key,'0.00000001','2') for key in keys};alternative=deepcopy(c)
        if mode in ('dcf','both') and c.get('cashflow_model')=='explicit':
            override='cashflows' in s or 'terminal_noi' in s
            if occ!=occupancy and not override:fail('explicit_cashflow_occupancy_sensitivity_requires_scenario_forecast')
            if override:
                if 'cashflows' not in s or 'terminal_noi' not in s:fail('complete_scenario_forecast_required')
                alternative['cashflows']=s['cashflows'];alternative['terminal_noi']=s['terminal_noi']
        alternate=income_result(alternative,occ,var)
        sensitivity.append(dict(id=ident,occupancy=str(occ),**{k:str(v) for k,v in var.items()},direct_value=alternate['direct_capitalization_value'],dcf_value=alternate['dcf_value'],cashflows=alternate['cashflows'],assumption=True))
    result.update(as_of=c['as_of'],valuation_date=c['valuation_date'],object_id=c['object_id'],currency='RUB',method=mode,**{k:str(v) for k,v in rates.items()},rate_basis=basis,sensitivity=sensitivity,assignment_approval_established=False,intermediate_result_not_final_value=True,cashflow_timing=c.get('cashflow_timing'))
    return result
@guard
def cost_approach(c):
    _,valued=base(c);quantity=num(c.get('quantity'),'quantity','0.00000001');unit=num(c.get('unit_cost'),'unit_cost','0.00000001');land=num(c.get('land_value'),'land_value')
    if c.get('inputs_on_declared_tax_basis') is not True:fail('cost_tax_basis_alignment_required')
    if c['tax_basis'] in ('unknown','observed_market_prices') and c['tax_basis_policy']['unknown_handling']=='exclude':fail('unknown_cost_tax_basis_excluded_by_policy')
    if c.get('quantity_unit') not in ('m2','m3'):fail('cost_quantity_unit')
    if c.get('unit_cost_excludes_land') is not True:fail('unit_cost_land_split_required')
    if day(c.get('land_valuation_date'),'land_valuation_date')!=valued:fail('land_valuation_date_mismatch')
    ref(c.get('land_source_reference'),'land_source');h=obj(c.get('handbook'),'handbook')
    for key in ('title','edition','source_reference'):text(h.get(key),'handbook_'+key)
    if h.get('cost_type') not in ('replacement','reproduction'):fail('replacement_or_reproduction_required')
    if day(h.get('published_at'),'handbook_publication')>valued or day(h.get('price_date'),'handbook_price_date')>valued:fail('handbook_after_valuation_date')
    text(c.get('region'),'region');text(h.get('region'),'handbook_region')
    indices=arr(c.get('indices'),'indices',2,12);factor=D(1);kinds=[];ids=set()
    for index in indices:
        obj(index,'index');ident=text(index.get('id'),'index_id',200)
        if ident in ids:fail('duplicate_index_id')
        ids.add(ident);kind=index.get('kind');kinds.append(kind)
        if kind not in ('regional','temporal','other'):fail('index_kind')
        factor*=num(index.get('factor'),'index_factor','0.00000001','10000');ref(index.get('source_reference'),'index_source');text(index.get('basis'),'index_basis')
        if day(index.get('date'),'index_date')>valued:fail('index_after_valuation_date')
        if kind=='temporal' and (index.get('base_date')!=h['price_date'] or index['date']!=c['valuation_date']):fail('temporal_index_base_or_target_date_mismatch')
        if kind=='regional' and (index.get('from_region')!=h['region'] or index.get('to_region')!=c['region']):fail('regional_index_scope_mismatch')
    if kinds.count('regional')!=1 or kinds.count('temporal')!=1:fail('one_regional_and_temporal_index_required')
    gross=quantity*unit*factor;dep=obj(c.get('depreciation'),'depreciation');method=dep.get('method')
    if method not in ('sequential_percent','additive_percent'):fail('depreciation_method')
    parts={}
    for kind in ('physical','functional','external'):
        row=obj(dep.get(kind),'depreciation_'+kind);parts[kind]=num(row.get('percent'),'depreciation_percent','0','100')/100;text(row.get('basis'),'depreciation_basis');ref(row.get('source_reference'),'depreciation_source')
    if method=='additive_percent':
        total=sum(parts.values())
        if total>1:fail('additive_depreciation_exceeds_100_percent')
        remaining=1-total
    else:
        remaining=D(1)
        for value in parts.values():remaining*=1-value
        total=1-remaining
    profit=obj(c.get('entrepreneurial_profit'),'entrepreneurial_profit');pct=num(profit.get('percent'),'profit_percent','0','1000')/100;ref(profit.get('source_reference'),'profit_source');text(profit.get('basis'),'profit_basis');included=profit.get('included_in_unit_cost')
    if type(included) is not bool:fail('profit_included_boolean')
    if included and pct!=0:fail('entrepreneurial_profit_double_count')
    mode=profit.get('calculation_base')
    if mode not in ('replacement_before_depreciation','depreciated_improvements'):fail('profit_calculation_base')
    profit_amount=gross*pct if mode=='replacement_before_depreciation' else gross*remaining*pct;improved=(gross+profit_amount)*remaining if mode=='replacement_before_depreciation' else gross*remaining+profit_amount
    year=num(c.get('building_year'),'building_year','1','9999')
    if year!=year.to_integral_value() or year>valued.year:fail('building_year_range')
    market=c.get('construction_market_status')
    if market not in ('active','limited','unknown'):fail('construction_market_status')
    review=obj(c.get('applicability_review'),'applicability_review')
    if review.get('status') not in ('suitable','limited','unknown'):fail('cost_applicability_status')
    text(review.get('rationale'),'applicability_rationale');ref(review.get('source_reference'),'applicability_source')
    return dict(as_of=c['as_of'],valuation_date=c['valuation_date'],object_id=c['object_id'],currency='RUB',quantity=str(quantity),quantity_unit=c['quantity_unit'],unit_cost=str(unit),land_value=money(land),index=str(factor),indices=indices,handbook=h,gross_replacement_cost=money(gross),gross_replacement_cost_unrounded=str(gross),depreciation=dep,depreciation_fractions={k:str(v) for k,v in parts.items()},total_depreciation=str(total),depreciated_replacement_cost=money(gross*remaining),entrepreneurial_profit_percent=str(pct*100),entrepreneurial_profit=profit,calculated_profit_on_selected_base=money(profit_amount),entrepreneurial_profit_amount=money(improved-gross*remaining),improvements_value=money(improved),total_value=money(land+improved),rounding_adjustment=money(D(money(land+improved))-D(money(land))-D(money(gross*remaining))-D(money(improved-gross*remaining))),unrounded=dict(land_value=str(land),depreciated_replacement_cost=str(gross*remaining),entrepreneurial_profit_amount=str(improved-gross*remaining),total_value=str(land+improved)),building_age_years=valued.year-int(year),construction_market_status=market,applicability_review=review,limited_applicability=market!='active' or review['status']!='suitable',assignment_approval_established=False,intermediate_result_not_final_value=True)

def input_units(function_id,c):
    obj(c,'data');base(c);out={}
    if function_id in ('market_analysis','sales_comparison'):
        target(c);unit=c['quantity_unit'];out['/target/area']=unit;p=obj(c.get('comparability_policy'),'comparability_policy')
        out.update({'/comparability_policy/area_ratio_min':'fraction','/comparability_policy/area_ratio_max':'fraction','/comparability_policy/minimum_count':'count'})
        if obj(c.get('outlier_policy'),'outlier_policy').get('method')=='iqr':out['/outlier_policy/multiplier']='factor'
        for i,row in enumerate(arr(c.get('comparables'),'comparables',1,100)):
            obj(row,'comparable');p='/comparables/'+str(i);out[p+'/price']={'unit':'RUB' if row.get('price_basis')=='total' else 'RUB/'+unit,'effective_date':row.get('date')};out[p+'/area']=unit
            if function_id=='sales_comparison':
                if obj(c.get('weighting'),'weighting').get('method')=='supplied':out[p+'/weight']='weight'
                for j,a in enumerate(arr(row.get('adjustments',[]),'adjustments',0,6)):
                    obj(a,'adjustment')
                    if a.get('mode')!='not_applicable':out[p+'/adjustments/'+str(j)+'/value']={'unit':'factor' if a.get('mode')=='factor' else 'RUB/'+unit,'effective_date':a.get('date')}
        if function_id=='market_analysis':out['/bargain_discount/percent']={'unit':'percent','effective_date':obj(c.get('bargain_discount'),'bargain_discount').get('date')}
        else:out['/cv_policy/threshold']=obj(c.get('cv_policy'),'cv_policy').get('threshold_unit')
    elif function_id=='income_approach':
        if ('market_rent_annual' in c)==('rent_input' in c):fail('choose_annual_rent_or_original_rent_input')
        observed=lambda unit:{'unit':unit,'not_after':c['valuation_date']}
        out.update({'/other_income_annual':observed('RUB/year'),'/occupancy':observed('fraction')})
        if 'market_rent_annual' in c:out['/market_rent_annual']=observed('RUB/year')
        else:
            r=obj(c['rent_input'],'rent_input')
            if r.get('period') not in ('month','year') or r.get('basis') not in ('total','per_unit'):fail('original_rent_period_or_basis')
            out['/rent_input/amount']=observed('RUB/'+('m2/' if r['basis']=='per_unit' else '')+r['period'])
            if r['basis']=='per_unit':out['/rent_input/area']='m2'
        mode=c.get('method');keys=('cap_rate',) if mode=='direct' else ('discount_rate','exit_cap_rate') if mode=='dcf' else ('cap_rate','discount_rate','exit_cap_rate')
        for key in keys:
            basis=obj(obj(c.get('rate_basis'),'rate_basis').get(key),'rate_basis_'+key);out['/'+key]={'unit':'fraction','effective_date':basis.get('date')}
            for j,part in enumerate(arr(basis.get('components',[]),'rate_components',0,30)):obj(part,'rate_component');out['/rate_basis/'+key+'/components/'+str(j)+'/value']={'unit':'fraction','effective_date':part.get('date')}
        for i,row in enumerate(arr(c.get('operating_expenses'),'operating_expenses',2,100)):
            obj(row,'operating_expense');key='amount' if row.get('mode')=='fixed_annual' else 'fraction';out['/operating_expenses/'+str(i)+'/'+key]=observed('RUB/year' if key=='amount' else 'fraction')
        if mode in ('dcf','both'):
            out.update({'/years':'year','/growth_rate':'fraction','/capital_expenditure_annual':'RUB/year','/exit_cost_fraction':'fraction'})
            if c.get('cashflow_model')=='explicit':
                out['/terminal_noi']='RUB/year'
                for i,row in enumerate(arr(c.get('cashflows'),'cashflows',1,50)):
                    obj(row,'cashflow')
                    for key in ('noi','capital_expenditure'):out['/cashflows/'+str(i)+'/'+key]='RUB/year'
        for i,row in enumerate(arr(c.get('sensitivity_scenarios'),'sensitivity_scenarios',1,30)):
            obj(row,'sensitivity')
            for key in ('occupancy',)+keys:out['/sensitivity_scenarios/'+str(i)+'/'+key]='fraction'
            if 'terminal_noi' in row:out['/sensitivity_scenarios/'+str(i)+'/terminal_noi']='RUB/year'
            for j,flow in enumerate(arr(row.get('cashflows',[]),'scenario_cashflows',0,50)):
                obj(flow,'scenario_cashflow')
                for key in ('noi','capital_expenditure'):out['/sensitivity_scenarios/'+str(i)+'/cashflows/'+str(j)+'/'+key]='RUB/year'
    elif function_id=='cost_approach':
        unit=c.get('quantity_unit')
        if unit not in ('m2','m3'):fail('cost_quantity_unit')
        out.update({'/quantity':unit,'/unit_cost':{'unit':'RUB/'+unit,'effective_date':obj(c.get('handbook'),'handbook').get('price_date')},'/land_value':{'unit':'RUB','effective_date':c.get('land_valuation_date')},'/building_year':'calendar_year','/entrepreneurial_profit/percent':'percent'})
        for i,row in enumerate(arr(c.get('indices'),'indices',2,12)):obj(row,'index');out['/indices/'+str(i)+'/factor']={'unit':'factor','effective_date':row.get('date')}
        for key in ('physical','functional','external'):out['/depreciation/'+key+'/percent']='percent'
    else:fail('unknown_calculation_function')
    return out

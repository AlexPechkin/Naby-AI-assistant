"""Bounded investment arithmetic; no orders, prices, credentials or network actions.

All rates are decimal fractions. Arithmetic conventions are deliberately explicit.
Source identity is enforced by the profession binding layer, not by these helpers.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal, Context, localcontext, ROUND_HALF_UP, DecimalException
from functools import wraps
import re

D=Decimal
CTX=Context(prec=80,rounding=ROUND_HALF_UP)
ZERO=D(0); ONE=D(1)
FUNCTIONS=('valuation_model','peer_comparison','bond_analysis','portfolio_scenarios')

def fail(code):raise ValueError(code)
def obj(v,n):
    if type(v) is not dict:fail(n+'_object_required')
    return v
def rows(v,n,lo=0,hi=100):
    if type(v) is not list or not lo<=len(v)<=hi:fail(n+'_bounded_list_required')
    return v
def text(v,n,limit=5000):
    if type(v) is not str or not v.strip() or len(v)>limit:fail(n+'_text_required')
    return v.strip()
def boolean(v,n):
    if type(v) is not bool:fail(n+'_boolean_required')
    return v
def num(v,n,lo='-1e20',hi='1e20'):
    if type(v) not in (str,int,D) or not re.fullmatch(r'-?(?:0|[1-9]\d{0,14})(?:\.\d{1,8})?',str(v)):fail(n+'_exact_decimal_required')
    r=D(v)
    if not r.is_finite() or not D(lo)<=r<=D(hi):fail(n+'_range')
    return r
def integer(v,n,lo=1,hi=30):
    r=num(v,n,str(lo),str(hi))
    if r!=int(r):fail(n+'_integer_required')
    return int(r)
def day(v,n):
    if type(v) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',v):fail(n+'_iso_date_required')
    try:return date.fromisoformat(v)
    except ValueError:fail(n+'_invalid_date')
def money(v):return str(v.quantize(D('.01')))
def ratio(v):return str(v.quantize(D('.000000000001')))
def exact(v):return format(v,'f')
def currency(v,n='currency'):
    if type(v) is not str or not re.fullmatch('[A-Z]{3}',v):fail(n+'_iso_code_required')
    return v
def ref(v,n='source_reference'):return text(v,n,1000)
def common(c):
    asof=day(c.get('as_of'),'as_of');currency(c.get('currency'));return asof
def historic(v,n,asof):
    value=day(v,n)
    if value>asof:fail(n+'_after_analysis_date')
    return value
def guard(fn):
    @wraps(fn)
    def wrapped(data):
        with localcontext(CTX):
            c=deepcopy(obj(data,'data'))
            try:r=fn(c)
            except (KeyError,TypeError,AttributeError,IndexError):raise ValueError('invalid_'+fn.__name__+'_structure') from None
            except DecimalException:raise ValueError('unsupported_numeric_condition_'+fn.__name__) from None
            r.update(currency=c['currency'],as_of=c['as_of'],not_individual_investment_advice=True,
                     trading_actions=False,source_semantics_verified=False,current_legal_applicability_verified=False)
            return r
    return wrapped

def _discount(c,asof):
    row=obj(c,'discounting');kind=row.get('method')
    historic(row.get('observation_date'),'rate_observation_date',asof)
    ref(row.get('source_reference'));text(row.get('rationale'),'discount_rationale')
    if kind=='supplied_wacc':
        rate=num(row.get('rate'),'discount_rate','0.00000001','3')
        return rate,{'method':kind,'rate':exact(rate),'rationale':row['rationale'],'source_reference':row['source_reference'],'observation_date':row['observation_date']}
    if kind!='component_wacc':fail('discount_method_required')
    if 'rate' in row:fail('component_wacc_cannot_include_supplied_rate')
    risk_free=num(row.get('risk_free_rate'),'risk_free_rate','-0.5','3')
    premium=num(row.get('equity_risk_premium'),'equity_risk_premium','0','3')
    beta=num(row.get('beta'),'beta','-5','10')
    debt_rate=num(row.get('pre_tax_cost_of_debt'),'pre_tax_cost_of_debt','0','5')
    debt_weight=num(row.get('debt_weight'),'debt_weight','0','1')
    tax=num(row.get('debt_tax_shield_rate'),'debt_tax_shield_rate','0','1')
    num(row.get('risk_free_tenor_years'),'risk_free_tenor_years','0.00000001','100')
    for key in ('risk_free_reference','premium_reference','beta_reference','debt_cost_reference','weights_reference','tax_reference'):ref(row.get(key),key)
    cost_equity=risk_free+beta*premium
    rate=cost_equity*(ONE-debt_weight)+debt_rate*(ONE-tax)*debt_weight
    if not ZERO<rate<=D(3):fail('computed_wacc_out_of_range')
    return rate,{**deepcopy(row),'rate':exact(rate),'cost_of_equity':exact(cost_equity),'equity_weight':exact(ONE-debt_weight)}

def _projection(s,asof,opening_ppe,opening_nwc,opening_balance,rate_override=None,margin_delta=ZERO):
    s=obj(s,'scenario');name=text(s.get('id'),'scenario_id',100)
    rate,discount=_discount(s.get('discounting'),asof)
    if rate_override is not None:
        rate=rate_override
        if not ZERO<rate<=D(3):fail('sensitivity_discount_out_of_range')
        discount={**discount,'rate':exact(rate),'sensitivity_override':True}
    growth=num(s.get('terminal_growth'),'terminal_growth','-0.99','1')
    if rate<=growth:fail('discount_must_exceed_terminal_growth')
    taxloss=s.get('tax_loss_policy')
    if taxloss not in ('no_tax_benefit','signed_tax_shield'):fail('explicit_tax_loss_policy_required')
    text(s.get('rationale'),'scenario_rationale');ref(s.get('source_reference'))
    forecast=rows(s.get('forecast'),'forecast',1,15)
    prepared=[];pv=ZERO;ppe=opening_ppe;nwc=opening_nwc
    book_cash,book_debt,book_equity,other_net_assets=opening_balance
    for i,row in enumerate(forecast):
        row=obj(row,'forecast_row')
        year=integer(row.get('year'),'forecast_year',1,15)
        if year!=i+1:fail('consecutive_forecast_years_required')
        revenue=num(row.get('revenue'),'revenue','0')
        cash_opex=num(row.get('cash_opex'),'cash_opex','0')-revenue*margin_delta
        if cash_opex<ZERO:fail('sensitivity_negative_cash_opex')
        depreciation=num(row.get('depreciation'),'depreciation','0')
        capex=num(row.get('capex'),'capex','0')
        delta=num(row.get('working_capital_delta'),'working_capital_delta')
        tax=num(row.get('tax_rate'),'tax_rate','0','1')
        ebitda=revenue-cash_opex;ebit=ebitda-depreciation
        cash_tax=(max(ebit,ZERO) if taxloss=='no_tax_benefit' else ebit)*tax
        fcff=ebit-cash_tax+depreciation-capex-delta
        discounted=fcff/(ONE+rate)**year
        ppe+=capex-depreciation;nwc+=delta
        if ppe<ZERO:fail('negative_projected_net_ppe')
        finance=obj(row.get('financing'),'financing')
        interest=num(finance.get('interest_expense'),'interest_expense','0')
        actual_tax=num(finance.get('cash_tax_after_financing'),'cash_tax_after_financing','0')
        borrowing=num(finance.get('net_borrowing'),'net_borrowing')
        distributions=num(finance.get('distributions'),'distributions','0')
        contributions=num(finance.get('equity_contributions'),'equity_contributions','0')
        other_cash=num(finance.get('other_cash_adjustments'),'other_cash_adjustments')
        other_equity=num(finance.get('other_equity_adjustments'),'other_equity_adjustments')
        text(finance.get('rationale'),'financing_rationale')
        net_income=ebit-interest-actual_tax
        cash_change=ebitda-interest-actual_tax-capex-delta+borrowing-distributions+contributions+other_cash
        book_cash+=cash_change;book_debt+=borrowing
        if book_debt<ZERO:fail('negative_projected_financial_debt')
        book_equity+=net_income-distributions+contributions+other_equity
        residual=book_cash+ppe+nwc+other_net_assets-book_debt-book_equity
        pv+=discounted
        prepared.append(dict(year=year,revenue=money(revenue),cash_opex=money(cash_opex),ebitda=money(ebitda),
          depreciation=money(depreciation),ebit=money(ebit),tax_rate=exact(tax),cash_tax=money(cash_tax),capex=money(capex),
          working_capital_delta=money(delta),fcff=money(fcff),fcff_unrounded=exact(fcff),discounted=money(discounted),
          projected_net_ppe=money(ppe),projected_net_working_capital=money(nwc),
          interest_expense=money(interest),cash_tax_after_financing=money(actual_tax),net_income=money(net_income),
          net_borrowing=money(borrowing),distributions=money(distributions),equity_contributions=money(contributions),
          other_cash_adjustments=money(other_cash),other_equity_adjustments=money(other_equity),
          cash_change=money(cash_change),projected_cash=money(book_cash),projected_financial_debt=money(book_debt),
          projected_total_book_equity=money(book_equity),projected_other_net_operating_assets=money(other_net_assets),
          balance_residual=money(residual),balance_identity_holds=residual==ZERO,financing_gap=book_cash<ZERO,
          financing_rationale=finance['rationale']))
    # Use the unrounded terminal-year FCFF. Output rounding never feeds arithmetic.
    terminal_fcff=fcff*(ONE+growth);terminal=terminal_fcff/(rate-growth)
    terminal_pv=terminal/(ONE+rate)**len(prepared)
    return dict(id=name,rationale=s['rationale'],source_reference=s['source_reference'],discounting=discount,
      tax_loss_policy=taxloss,terminal_growth=exact(growth),flows=prepared,terminal_fcff=money(terminal_fcff),
      terminal_value=money(terminal),terminal_present_value=money(terminal_pv),explicit_period_present_value=money(pv),
      enterprise_value_unrounded=exact(pv+terminal_pv),enterprise_value=money(pv+terminal_pv))

@guard
def valuation_model(c):
    asof=common(c);valued=historic(c.get('valuation_date'),'valuation_date',asof)
    text(c.get('issuer'),'issuer');ref(c.get('assignment_reference'))
    debt=num(c.get('debt'),'debt','0');cash=num(c.get('cash'),'cash','0')
    nonop=num(c.get('non_operating_assets'),'non_operating_assets','0')
    minority=num(c.get('minority_interest'),'minority_interest','0')
    preferred=num(c.get('preferred_equity'),'preferred_equity','0')
    shares=num(c.get('diluted_shares'),'diluted_shares','0.00000001')
    opening_ppe=num(c.get('opening_net_ppe'),'opening_net_ppe','0')
    opening_nwc=num(c.get('opening_net_working_capital'),'opening_net_working_capital')
    opening_equity=num(c.get('opening_total_book_equity'),'opening_total_book_equity')
    other_assets=num(c.get('opening_other_net_operating_assets'),'opening_other_net_operating_assets')
    opening_residual=cash+opening_ppe+opening_nwc+other_assets-debt-opening_equity
    opening_balance=(cash,debt,opening_equity,other_assets)
    scenarios=rows(c.get('scenarios'),'scenarios',3,3)
    result={}
    for s in scenarios:
        r=_projection(s,valued,opening_ppe,opening_nwc,opening_balance)
        if r['id'] not in ('base','optimistic','pessimistic') or r['id'] in result:fail('three_named_scenarios_required')
        equity=D(r['enterprise_value_unrounded'])-debt+cash+nonop-minority-preferred
        r.update(equity_value=money(equity),value_per_share=money(equity/shares),value_per_share_unrounded=exact(equity/shares))
        result[r['id']]=r
    if len({len(s['flows']) for s in result.values()})!=1:fail('scenario_horizons_must_match')
    sensitivity=[];sensitivity_ids=set();sensitivity_changes=set()
    base=next(s for s in scenarios if s['id']=='base')
    for row in rows(c.get('sensitivity'),'sensitivity',1,40):
        row=obj(row,'sensitivity_row');text(row.get('id'),'sensitivity_id',100)
        if row['id'] in sensitivity_ids:fail('duplicate_sensitivity_id')
        sensitivity_ids.add(row['id'])
        dr=num(row.get('discount_delta'),'discount_delta','-1','1')
        margin=num(row.get('ebitda_margin_delta'),'ebitda_margin_delta','-1','1')
        if dr!=ZERO:sensitivity_changes.add('rate')
        if margin!=ZERO:sensitivity_changes.add('margin')
        text(row.get('rationale'),'sensitivity_rationale')
        rate=D(result['base']['discounting']['rate'])+dr
        r=_projection(base,valued,opening_ppe,opening_nwc,opening_balance,rate_override=rate,margin_delta=margin)
        equity=D(r['enterprise_value_unrounded'])-debt+cash+nonop-minority-preferred
        sensitivity.append(dict(id=row['id'],discount_delta=exact(dr),ebitda_margin_delta=exact(margin),
          rationale=row['rationale'],enterprise_value=r['enterprise_value'],equity_value=money(equity),value_per_share=money(equity/shares)))
    if sensitivity_changes!={'rate','margin'}:fail('both_rate_and_margin_sensitivity_required')
    cross=obj(c.get('multiple_crosscheck'),'multiple_crosscheck');text(cross.get('rationale'),'multiple_crosscheck_rationale')
    status=cross.get('status')
    if status not in ('provided','not_applied'):fail('multiple_crosscheck_status_required')
    multiple_crosscheck=deepcopy(cross)
    if status=='provided':
        if cross.get('basis') not in ('historical','forecast'):fail('multiple_ebitda_basis_required')
        text(cross.get('ebitda_period'),'multiple_ebitda_period',200)
        if historic(cross.get('observation_date'),'multiple_observation_date',valued)!=valued:fail('multiple_observation_date_mismatch')
        ref(cross.get('multiple_reference'));ref(cross.get('ebitda_reference'))
        multiple=num(cross.get('ev_ebitda'),'selected_ev_ebitda','0.00000001','1000')
        selected_ebitda=num(cross.get('ebitda'),'multiple_ebitda','0.00000001')
        multiple_ev=multiple*selected_ebitda;multiple_equity=multiple_ev-debt+cash+nonop-minority-preferred
        multiple_crosscheck.update(enterprise_value=money(multiple_ev),equity_value=money(multiple_equity),value_per_share=money(multiple_equity/shares),independent_selected_multiple=True)
    prices=[D(s['value_per_share_unrounded']) for s in result.values()]
    return dict(issuer=c['issuer'],valuation_date=c['valuation_date'],scenarios=result,sensitivity=sensitivity,multiple_crosscheck=multiple_crosscheck,
      range_per_share=[money(min(prices)),money(max(prices))],enterprise_to_equity_bridge=dict(debt=money(debt),cash=money(cash),
      non_operating_assets=money(nonop),minority_interest=money(minority),preferred_equity=money(preferred),diluted_shares=exact(shares)),
      opening_balance_residual=money(opening_residual),opening_balance_identity_holds=opening_residual==ZERO,
      selected_balance_projection=True,statutory_full_balance_sheet_not_modeled=True,
      any_balance_gaps=opening_residual!=ZERO or any(not f['balance_identity_holds'] or f['financing_gap'] for s in result.values() for f in s['flows']),
      limitations=['end_year_discounting','terminal_growth_is_assumption','no_loss_carryforward_engine','not_a_target_price_or_order',
      'book_equity_and_market_equity_are_different','financing_taxes_and_other_adjustments_supplied_separately','sensitivity_does_not_reforecast_financing_taxes'])

def median(values):
    v=sorted(values);n=len(v)
    return v[n//2] if n%2 else (v[n//2-1]+v[n//2])/2

@guard
def peer_comparison(c):
    asof=common(c);compared=historic(c.get('comparison_date'),'comparison_date',asof)
    standard=text(c.get('target_standard'),'target_standard',100);period=text(c.get('target_period'),'target_period',100)
    policy=obj(c.get('comparison_policy'),'comparison_policy');ref(policy.get('source_reference'))
    if policy.get('mismatch_handling') not in ('exclude','conditional'):fail('comparison_mismatch_policy_required')
    outliers=policy.get('outlier_method')
    if outliers not in ('none','median_relative'):fail('outlier_method_required')
    if outliers=='median_relative':
        lower=num(policy.get('lower_factor'),'lower_factor','0','1');upper=num(policy.get('upper_factor'),'upper_factor','1','100')
        if lower==upper:fail('outlier_factors_must_differ')
    text(policy.get('rationale'),'comparison_policy_rationale')
    prepared=[];seen=set();eligible=[]
    for item in rows(c.get('peers'),'peers',1,60):
        item=obj(item,'peer');ident=text(item.get('id'),'peer_id',100)
        if ident in seen:fail('duplicate_peer_id')
        seen.add(ident)
        selected=boolean(item.get('selected'),'peer_selected');text(item.get('selection_rationale'),'selection_rationale')
        issuer=text(item.get('issuer'),'issuer',500);curr=currency(item.get('currency'),'peer_currency')
        price_date=historic(item.get('price_date'),'peer_price_date',asof)
        historic(item.get('financial_publication_date'),'financial_publication_date',compared)
        current_period=text(item.get('period'),'peer_period',100);current_standard=text(item.get('standard'),'peer_standard',100)
        ref(item.get('source_reference'))
        price=num(item.get('price'),'price','0.00000001');shares=num(item.get('shares'),'shares','0.00000001')
        debt=num(item.get('debt'),'debt','0');cash=num(item.get('cash'),'cash','0')
        minority=num(item.get('minority_interest'),'minority_interest','0');preferred=num(item.get('preferred_equity'),'preferred_equity','0')
        ebitda=num(item.get('ebitda'),'ebitda');income=num(item.get('net_income'),'net_income')
        dividend=num(item.get('dividend_per_share'),'dividend_per_share','0')
        cap=price*shares;ev=cap+debt-cash+minority+preferred
        mismatches=[]
        if curr!=c['currency']:mismatches.append('currency')
        if price_date!=compared:mismatches.append('price_date')
        if current_period!=period:mismatches.append('period')
        if current_standard!=standard:mismatches.append('standard')
        included=selected and (not mismatches or policy['mismatch_handling']=='conditional')
        # Different currency financial amounts cannot enter a common median implicitly.
        if curr!=c['currency']:included=False
        value=ev/ebitda if ebitda>ZERO and ev>ZERO else None
        if included and value is not None:eligible.append(value)
        prepared.append(dict(id=ident,issuer=issuer,selected=selected,included=included,mismatches=mismatches,
          selection_rationale=item['selection_rationale'],source_reference=item['source_reference'],currency=curr,
          price_date=item['price_date'],period=current_period,standard=current_standard,market_cap=money(cap),ev=money(ev),
          ebitda=money(ebitda),net_income=money(income),ev_ebitda=ratio(value) if value is not None else None,
          pe=ratio(cap/income) if income>ZERO else None,net_debt_ebitda=ratio((debt-cash)/ebitda) if ebitda>ZERO else None,
          dividend_yield=ratio(dividend/price),outlier=None,_multiple=value))
    med=median(eligible) if eligible else None
    for row in prepared:
        value=row.pop('_multiple')
        if row['included'] and value is not None and med is not None:
            row['outlier']=(value<med*lower or value>med*upper) if outliers=='median_relative' else False
    return dict(comparison_date=c['comparison_date'],target_period=period,target_standard=standard,comparison_policy=deepcopy(policy),
      peers=prepared,median_ev_ebitda=ratio(med) if med is not None else None,median_peer_count=len(eligible),
      conditional_comparison=any(p['included'] and p['mismatches'] for p in prepared),
      nonpositive_denominators_not_meaningful=True,outliers_not_automatically_removed=True,
      limitations=['not_a_cross_currency_valuation','no_automatic_peer_selection','trailing_dividend_yield_not_forecast'])

@guard
def bond_analysis(c):
    asof=common(c);settlement=historic(c.get('settlement_date'),'settlement_date',asof)
    price_date=historic(c.get('price_date'),'price_date',settlement)
    if price_date!=settlement:fail('price_and_settlement_dates_must_match_for_snapshot')
    target=day(c.get('target_date'),'target_date')
    if target<=settlement:fail('future_bond_target_required')
    if (target-settlement).days>36525:fail('bond_horizon_exceeds_100_years')
    text(c.get('isin'),'isin',40);ref(c.get('terms_reference'));ref(c.get('price_reference'))
    outstanding=num(c.get('outstanding_principal'),'outstanding_principal','0.00000001')
    quoted=num(c.get('price'),'price','0.00000001');accrued=num(c.get('accrued_interest'),'accrued_interest','0')
    price_units=c.get('price_units');price_kind=c.get('price_kind')
    if price_units not in ('percent_of_outstanding','currency_amount') or price_kind not in ('clean','dirty'):fail('explicit_price_convention_required')
    amount=quoted*outstanding/100 if price_units=='percent_of_outstanding' else quoted
    dirty=amount+accrued if price_kind=='clean' else amount
    clean=amount if price_kind=='clean' else amount-accrued
    if clean<=ZERO:fail('nonpositive_clean_price')
    basis=c.get('day_count')
    if basis not in ('ACT/365F','ACT/360'):fail('supported_day_count_required')
    denominator=D(365 if basis=='ACT/365F' else 360)
    compounding=c.get('compounding')
    if compounding not in ('effective_annual','nominal_periodic'):fail('compounding_required')
    freq=integer(c.get('frequency'),'frequency',1,12)
    if compounding=='effective_annual' and freq!=1:fail('annual_effective_frequency_must_be_one')
    coupon_type=c.get('coupon_type')
    if coupon_type not in ('fixed','floating_scenario','zero_coupon'):fail('coupon_type_required')
    if coupon_type=='floating_scenario':
        text(c.get('floating_assumptions'),'floating_assumptions');ref(c.get('floating_reference'))
    target_kind=c.get('target_kind')
    if target_kind not in ('maturity','put_offer_scenario','call_offer_scenario'):fail('target_kind_required')
    if target_kind!='maturity':ref(c.get('offer_reference'));text(c.get('exercise_assumption'),'exercise_assumption')
    flows=[];principal_sum=ZERO;previous=settlement
    for row in rows(c.get('cashflows'),'cashflows',1,200):
        row=obj(row,'cashflow');payment=day(row.get('date'),'cashflow_date')
        if not previous<payment<=target:fail('ordered_future_cashflows_required')
        previous=payment
        coupon=num(row.get('coupon'),'coupon','0');principal=num(row.get('principal'),'principal','0')
        if coupon+principal<=ZERO:fail('positive_bond_cashflow_required')
        if coupon_type=='zero_coupon' and coupon!=ZERO:fail('zero_coupon_has_coupon')
        ref(row.get('source_reference'));principal_sum+=principal
        if principal_sum>outstanding:fail('redemptions_exceed_outstanding_principal')
        flows.append(dict(date=row['date'],coupon=coupon,principal=principal,amount=coupon+principal,time=D((payment-settlement).days)/denominator,source_reference=row['source_reference']))
    if previous!=target or principal_sum!=outstanding:fail('cashflows_must_redeem_outstanding_at_target')
    solver=obj(c.get('yield_bracket'),'yield_bracket')
    low=num(solver.get('low'),'yield_low','-0.99999999','100');high=num(solver.get('high'),'yield_high','-0.99999999','100')
    if low>=high:fail('yield_bracket_order')
    factor=D(freq) if compounding=='nominal_periodic' else ONE
    def present(y):
        base=ONE+y/factor
        if base<=ZERO:fail('yield_discount_base')
        return sum((f['amount']/base**(f['time']*factor) for f in flows),ZERO)
    lower_value=present(low)-dirty;upper_value=present(high)-dirty
    if lower_value<ZERO or upper_value>ZERO:fail('yield_not_bracketed')
    left,right=low,high
    iterations=0
    for _ in range(90):
        iterations+=1
        mid=(left+right)/2
        residual=present(mid)-dirty
        if abs(residual)<=dirty*D('1e-16'):
            left=right=mid;break
        if residual>ZERO:left=mid
        else:right=mid
        if right-left<=D('1e-18'):break
    y=(left+right)/2;pv=present(y)
    duration=sum((f['time']*f['amount']/(ONE+y/factor)**(f['time']*factor) for f in flows),ZERO)/pv
    modified=duration/(ONE+y/factor)
    convexity=sum((f['time']*(f['time']+ONE/factor)*f['amount']/(ONE+y/factor)**(f['time']*factor+2) for f in flows),ZERO)/pv
    benchmark=obj(c.get('benchmark'),'benchmark');ref(benchmark.get('source_reference'))
    if historic(benchmark.get('observation_date'),'benchmark_date',asof)!=price_date:fail('benchmark_date_mismatch')
    if benchmark.get('compounding')!=compounding or benchmark.get('day_count')!=basis or integer(benchmark.get('frequency'),'benchmark_frequency',1,12)!=freq:fail('benchmark_yield_basis_mismatch')
    benchmark_yield=num(benchmark.get('yield'),'benchmark_yield','-0.99','100')
    tenor=num(benchmark.get('tenor_years'),'benchmark_tenor','0.00000001','100')
    text(benchmark.get('tenor_matching_rationale'),'benchmark_tenor_matching_rationale')
    ratings=[]
    for rating in rows(c.get('ratings'),'ratings',0,20):
        rating=obj(rating,'rating');historic(rating.get('date'),'rating_date',asof)
        for key in ('agency','rating','source_reference','agency_registry_reference'):text(rating.get(key),'rating_'+key)
        ratings.append(deepcopy(rating))
    for key in ('covenants','subordination','currency_risk'):text(c.get(key),key)
    return dict(isin=c['isin'],settlement_date=c['settlement_date'],target_date=c['target_date'],target_kind=target_kind,
      coupon_type=coupon_type,scenario_yield=coupon_type=='floating_scenario' or target_kind!='maturity',
      clean_price=money(clean),dirty_price=money(dirty),accrued_interest=money(accrued),price_convention=dict(units=price_units,kind=price_kind),
      day_count=basis,compounding=compounding,frequency=freq,ytm=ratio(y),yield_unrounded=exact(y),
      macaulay_duration_years=ratio(duration),modified_duration_years=ratio(modified),convexity=ratio(convexity),
      yield_price_residual=exact(pv-dirty),yield_solver_bracket=deepcopy(solver),benchmark=deepcopy(benchmark),
      yield_solver_iterations=iterations,yield_solver_absolute_tolerance=exact(dirty*D('1e-16')),
      simple_yield_spread=ratio(y-benchmark_yield),spread_basis='same_selected_yield_convention_not_zspread_or_credit_spread',
      cashflows=[{**f,'coupon':money(f['coupon']),'principal':money(f['principal']),'amount':money(f['amount']),'time':exact(f['time'])} for f in flows],
      ratings=ratings,covenants=c['covenants'],subordination=c['subordination'],currency_risk=c['currency_risk'],
      rating_registry_membership_not_established=True,
      limitations=['dated_cashflow_schedule_required','no_default_or_option_pricing','accrued_interest_supplied_not_reconstructed','no_automatic_coupon_forecast'])

@guard
def portfolio_scenarios(c):
    asof=common(c);priced=historic(c.get('price_date'),'price_date',asof)
    text(c.get('portfolio_id'),'portfolio_id',200);text(c.get('horizon'),'horizon',500)
    if c.get('portfolio_kind')!='model_long_only':fail('only_model_long_only_portfolio_supported')
    positions=[];seen=set();total=ZERO
    for row in rows(c.get('positions'),'positions',1,50):
        row=obj(row,'position');ident=text(row.get('id'),'position_id',100)
        if ident in seen:fail('duplicate_position_id')
        seen.add(ident)
        for key in ('issuer','sector','source_reference'):text(row.get(key),'position_'+key)
        curr=currency(row.get('currency'),'position_currency')
        if historic(row.get('price_date'),'position_price_date',asof)!=priced:fail('position_price_date_mismatch')
        local=num(row.get('local_value'),'local_value','0.00000001');fx=num(row.get('fx_to_base'),'fx_to_base','0.00000001')
        historic(row.get('fx_date'),'fx_date',priced)
        if row['fx_date']!=c['price_date']:fail('fx_date_mismatch')
        if curr==c['currency'] and fx!=ONE:fail('base_currency_fx_must_be_one')
        duration=num(row.get('modified_duration'),'modified_duration','0','100')
        kind=row.get('asset_class')
        if kind not in ('equity','bond','cash'):fail('portfolio_asset_class_required')
        if kind!='bond' and duration!=ZERO:fail('duration_only_for_bond')
        val=local*fx;total+=val
        positions.append(dict(id=ident,issuer=row['issuer'],sector=row['sector'],currency=curr,asset_class=kind,
          local_value=money(local),fx_to_base=exact(fx),base_value_unrounded=exact(val),base_value=money(val),
          modified_duration=exact(duration),source_reference=row['source_reference']))
    groups={key:{} for key in ('issuer','sector','currency')};weighted_duration=ZERO;bondvalue=ZERO
    for row in positions:
        value=D(row['base_value_unrounded']);weight=value/total;row['weight']=ratio(weight)
        for key in groups:groups[key][row[key]]=groups[key].get(row[key],ZERO)+value
        if row['asset_class']=='bond':weighted_duration+=value*D(row['modified_duration']);bondvalue+=value
    scenarios=[];ids=set()
    for s in rows(c.get('scenarios'),'scenarios',1,5):
        s=obj(s,'portfolio_scenario');ident=text(s.get('id'),'scenario_id',100)
        if ident in ids:fail('duplicate_scenario_id')
        ids.add(ident);text(s.get('rationale'),'scenario_rationale');ref(s.get('source_reference'))
        asset=obj(s.get('asset_returns'),'asset_returns');fx=obj(s.get('currency_returns'),'currency_returns')
        if set(asset)!=seen or set(fx)!={p['currency'] for p in positions}:fail('complete_stress_coverage_required')
        if c['currency'] in fx and num(fx[c['currency']],'base_currency_return','-1','10')!=ZERO:fail('base_currency_shock_must_be_zero')
        shift=num(s.get('yield_shift'),'yield_shift','-1','1')
        stressed=ZERO;detail=[]
        for row in positions:
            nonrate=num(asset[row['id']],'asset_return','-1','10');fxreturn=num(fx[row['currency']],'currency_return','-0.99999999','10')
            rate_return=-D(row['modified_duration'])*shift if row['asset_class']=='bond' else ZERO
            local_return=nonrate+rate_return
            if local_return < -ONE:fail('linear_stress_implies_negative_asset_value')
            combined=(ONE+local_return)*(ONE+fxreturn)-ONE
            value=D(row['base_value_unrounded'])*(ONE+combined);stressed+=value
            detail.append(dict(id=row['id'],non_rate_asset_return=exact(nonrate),duration_approximation_return=exact(rate_return),
              currency_return=exact(fxreturn),combined_base_return=exact(combined),stressed_base_value=money(value)))
        scenarios.append(dict(id=ident,rationale=s['rationale'],yield_shift=exact(shift),source_reference=s['source_reference'],
          stressed_value=money(stressed),pnl=money(stressed-total),portfolio_return=ratio(stressed/total-ONE),positions=detail))
    return dict(portfolio_id=c['portfolio_id'],price_date=c['price_date'],horizon=c['horizon'],positions=positions,total_base_value=money(total),
      concentrations={key:[dict(name=name,value=money(value),weight=ratio(value/total)) for name,value in sorted(values.items())] for key,values in groups.items()},
      portfolio_modified_duration=ratio(weighted_duration/total),bond_sleeve_modified_duration=ratio(weighted_duration/bondvalue) if bondvalue else None,
      scenarios=scenarios,weights_computed_from_values=True,
      limitations=['model_long_only_no_leverage','duration_is_first_order_parallel_yield_shock','non_rate_asset_returns_exclude_duration_component',
      'fx_shock_multiplies_local_return','no_correlation_var_or_liquidity_model','past_performance_not_a_guarantee'])

def input_units(function,data):
    """All variable numeric input paths; conventions are algorithm constants."""
    c=obj(data,'data');units={};curr=currency(c.get('currency'))
    def put(path,unit,not_after=None):
        units[path]={'unit':unit,'not_after':not_after} if not_after else unit
    if function=='valuation_model':
        date_=c.get('valuation_date')
        for k in ('debt','cash','non_operating_assets','minority_interest','preferred_equity','opening_net_ppe','opening_net_working_capital','opening_total_book_equity','opening_other_net_operating_assets'):put('/'+k,curr,date_)
        put('/diluted_shares','share',date_)
        if obj(c.get('multiple_crosscheck'),'multiple_crosscheck').get('status')=='provided':
            put('/multiple_crosscheck/ev_ebitda','ratio',date_);put('/multiple_crosscheck/ebitda',curr,date_)
        for i,s in enumerate(rows(c.get('scenarios'),'scenarios',3,3)):
            p=f'/scenarios/{i}';put(p+'/terminal_growth','ratio')
            d=obj(s.get('discounting'),'discounting');p2=p+'/discounting'
            if d.get('method')=='supplied_wacc':put(p2+'/rate','ratio',date_)
            else:
                for k in ('risk_free_rate','equity_risk_premium','beta','pre_tax_cost_of_debt','debt_weight','debt_tax_shield_rate'):put(p2+'/'+k,'ratio',date_)
                put(p2+'/risk_free_tenor_years','year',date_)
            for j,row in enumerate(rows(s.get('forecast'),'forecast',1,15)):
                p3=p+f'/forecast/{j}';put(p3+'/year','year')
                for k in ('revenue','cash_opex','depreciation','capex','working_capital_delta'):put(p3+'/'+k,curr)
                put(p3+'/tax_rate','ratio')
                for k in ('interest_expense','cash_tax_after_financing','net_borrowing','distributions','equity_contributions','other_cash_adjustments','other_equity_adjustments'):put(p3+'/financing/'+k,curr)
        for i,row in enumerate(rows(c.get('sensitivity'),'sensitivity',1,40)):
            for k in ('discount_delta','ebitda_margin_delta'):put(f'/sensitivity/{i}/'+k,'ratio')
    elif function=='peer_comparison':
        policy=obj(c.get('comparison_policy'),'comparison_policy')
        if policy.get('outlier_method')=='median_relative':
            for k in ('lower_factor','upper_factor'):put('/comparison_policy/'+k,'ratio')
        for i,row in enumerate(rows(c.get('peers'),'peers',1,60)):
            pcurr=currency(row.get('currency'));p=f'/peers/{i}/'
            for k in ('price','debt','cash','minority_interest','preferred_equity','ebitda','net_income','dividend_per_share'):put(p+k,pcurr+'/share' if k in ('price','dividend_per_share') else pcurr,row.get('price_date') if k in ('price','dividend_per_share') else c.get('comparison_date'))
            put(p+'shares','share',row.get('price_date'))
    elif function=='bond_analysis':
        put('/outstanding_principal',curr,c.get('settlement_date'));put('/price','percent' if c.get('price_units')=='percent_of_outstanding' else curr,c.get('price_date'));put('/accrued_interest',curr,c.get('settlement_date'))
        put('/frequency','count')
        for i,row in enumerate(rows(c.get('cashflows'),'cashflows',1,200)):
            for k in ('coupon','principal'):put(f'/cashflows/{i}/'+k,curr)
        for k in ('low','high'):put('/yield_bracket/'+k,'ratio')
        for k,u in (('yield','ratio'),('frequency','count'),('tenor_years','year')):put('/benchmark/'+k,u,c.get('price_date'))
    elif function=='portfolio_scenarios':
        for i,row in enumerate(rows(c.get('positions'),'positions',1,50)):
            p=f'/positions/{i}/';put(p+'local_value',currency(row.get('currency')),row.get('price_date'))
            put(p+'fx_to_base',curr+'/'+row['currency'],row.get('fx_date'));put(p+'modified_duration','year',row.get('price_date'))
        for i,s in enumerate(rows(c.get('scenarios'),'scenarios',1,5)):
            p=f'/scenarios/{i}/';put(p+'yield_shift','ratio')
            for key in ('asset_returns','currency_returns'):
                for ident in obj(s.get(key),key):put(p+key+'/'+ident.replace('~','~0').replace('/','~1'),'ratio')
    else:fail('unknown_calculation_function')
    return units

def selected_texts(function,data):
    # Model forecasts/analyst rationale are not quotations. Only explicit quoted
    # fields are additionally located by the common binding layer.
    return {}

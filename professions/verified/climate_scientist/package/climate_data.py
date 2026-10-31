"""Bounded, deterministic climate calculations from explicitly selected evidence.

No downloads, file reads, solver calls or execution of third party climate engines.
Finite input arithmetic and all threshold decisions use rational numbers. Decimal
transcendentals / nonterminating results are rendered with 180 significant digits.
Those digits describe arithmetic, not measurement precision.
"""
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal, Context, InvalidOperation, localcontext, DecimalException
from fractions import Fraction as F
from math import erfc, isfinite, isqrt
import calendar
import re

FUNCTIONS=('data_provenance','normals_anomalies','trends_extremes','scenarios_downscaling')
CTX=Context(prec=180,Emin=-999999,Emax=999999)
NUM=re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z')
# 200 decimal places, mathematical constant (NIST DLMF 5.2.3 -> OEIS A001620).
EULER=Decimal('0.57721566490153286060651209008240243104215933593992359880576723488486772677766467093694706329174674951463144724980708248096050401448654283622417399764492353625350033374293733773767394279259525824709491')

def obj(x):
    if type(x) is not dict:raise ValueError('object_required')
    return x
def arr(x,lo=0,hi=800):
    if type(x) is not list or not lo<=len(x)<=hi:raise ValueError('bounded_array_required')
    return x
def text(x):
    if type(x) is not str or not x.strip() or len(x)>12000:raise ValueError('nonempty_bounded_text_required')
    return x
def enum(x,choices):
    if type(x) is not str or x not in choices:raise ValueError('unsupported_selected_option')
    return x
def boolean(x):
    if type(x) is not bool:raise ValueError('boolean_required')
    return x
def iso(x):
    text(x)
    try:d=date.fromisoformat(x)
    except ValueError:raise ValueError('ISO_date_required') from None
    if d.isoformat()!=x:raise ValueError('ISO_date_required')
    return d
def dec(x):
    if isinstance(x,F):return Decimal(x.numerator)/Decimal(x.denominator)
    return Decimal(x)
def fmt(x):
    if x is None:return None
    with localcontext(CTX):
        y=+dec(x)
        if not y.is_finite():raise ValueError('finite_result_required')
        if not y:return '0'
        return str(y.normalize())
def mean(xs):return sum(xs,F())/len(xs)
def median(xs):
    ys=sorted(xs);n=len(ys)
    return ys[n//2] if n%2 else (ys[n//2-1]+ys[n//2])/2
def sqrt(x):
    with localcontext(CTX):return dec(x).sqrt()
def calc(fn):
    with localcontext(CTX):return fn()
def esc(x):return str(x).replace('~','~0').replace('/','~1')

class Read:
    def __init__(self,data):
        self.data=obj(data);self.as_of=iso(data['as_of'])
        if data.get('jurisdiction')!='RU':raise ValueError('RU_jurisdiction_required')
        self.units={};self.gaps=[]
    def n(self,value,path,unit='1',ref=None,observed=None,lo=None,hi=None,integer=False,effective_not_after=None):
        if type(value) not in (str,int) or isinstance(value,bool):raise ValueError('exact_numeric_string_required')
        s=str(value)
        if len(s)>180 or not NUM.fullmatch(s):raise ValueError('bounded_decimal_required')
        if 'e' in s.lower() and abs(int(s.lower().split('e')[1]))>100:raise ValueError('numeric_precision_or_exponent_bound')
        try:d=Decimal(s)
        except InvalidOperation:raise ValueError('bounded_decimal_required') from None
        # Tuple/exponent inspection must precede any context-sensitive operation,
        # including abs(Decimal), and includes zero with a malicious exponent.
        t=d.as_tuple()
        if not d.is_finite() or abs(t.exponent)>140 or len(t.digits)>40 or (d and not -100<=d.adjusted()<=100):raise ValueError('numeric_precision_or_exponent_bound')
        v=F(d)
        if (lo is not None and v<lo) or (hi is not None and v>hi) or (integer and v.denominator!=1):raise ValueError('numeric_domain_bound')
        cutoff=self.as_of if effective_not_after is None else min(self.as_of,iso(effective_not_after))
        spec={'unit':text(unit),'effective_not_after':cutoff.isoformat(),'published_not_after':self.as_of.isoformat()}
        if ref is not None:spec['source_references']=[text(ref)]
        if observed is not None:
            od=iso(observed)
            if od>cutoff:raise ValueError('future_observation_or_run_date')
            spec['effective_date']=od.isoformat()
        self.units[path]=spec
        if len(self.units)>900:raise ValueError('bounded_numeric_budget_900')
        return int(v) if integer else v
    def gap(self,x):
        if x not in self.gaps:self.gaps.append(x)
    def result(self,**items):
        return dict(**items,evidence_gaps=self.gaps,interpretation='conditional_selected_data_analysis',arithmetic_precision='exact_finite_inputs_rational_predicates_decimal180_transcendentals',engine_executed=False)

def source(r,s):
    s=obj(s)
    for k in ('id','source_reference','version','location','variable','unit'):text(s[k])
    enum(s['kind'],('station','reanalysis','satellite','model','external_derived'))
    enum(s['calendar'],('gregorian','365_day','360_day'))
    rd=iso(s['reference_date'])
    if rd>r.as_of:raise ValueError('future_source_reference_date')
    if s['kind']!='station':r.gap('gridded_or_derived_data_are_not_station_observations')
    if not s.get('homogeneity_evidence_reference'):r.gap('homogeneity_not_established')
    if not s.get('license_reference'):r.gap('reuse_permission_not_established')
    return s

def month_days(y,m,cal):
    if cal=='360_day':return 30
    return 28 if m==2 and cal=='365_day' else calendar.monthrange(y,m)[1]
def coord(s,frequency,cal):
    text(s)
    pattern={'annual':r'\d{4}','monthly':r'\d{4}-\d{2}','daily':r'\d{4}-\d{2}-\d{2}'}[frequency]
    if not re.fullmatch(pattern,s):raise ValueError('climate_coordinate_format')
    bits=list(map(int,s.split('-')));y=bits[0]
    if not 1<=y<=9998:raise ValueError('coordinate_year_bound')
    if len(bits)>1 and not 1<=bits[1]<=12:raise ValueError('coordinate_month_bound')
    if len(bits)>2 and not 1<=bits[2]<=month_days(y,bits[1],cal):raise ValueError('coordinate_day_bound')
    return tuple(bits)
def next_coord(t,freq,cal):
    y=t[0]
    if freq=='annual':return (y+1,)
    m=t[1]
    if freq=='monthly':return (y+1,1) if m==12 else (y,m+1)
    d=t[2]
    if d<month_days(y,m,cal):return (y,m,d+1)
    return (y+1,1,1) if m==12 else (y,m+1,1)
def key(t):return '-'.join(str(v).zfill(4 if i==0 else 2) for i,v in enumerate(t))
def coordinates(start,end,freq,cal,cap=800):
    a=coord(start,freq,cal);b=coord(end,freq,cal)
    if a>b:raise ValueError('period_order')
    out=[]
    while a<=b:
        out.append(key(a))
        if len(out)>cap:raise ValueError('coordinate_count_bound')
        a=next_coord(a,freq,cal)
    return out

def records(r,rows,path,s,freq,allow_duplicates=False):
    rows=arr(rows,1,750);groups=defaultdict(list)
    for i,row in enumerate(rows):
        row=obj(row);p=path+'/'+str(i);c=coord(row['period'],freq,s['calendar'])
        historical=s['kind'] in ('station','reanalysis','satellite')
        if historical and key(c)>r.as_of.isoformat()[:len(key(c))]:raise ValueError('future_observed_coordinate')
        q=enum(row['quality'],('valid','suspect','missing','unreviewed'))
        end=None
        if historical:
            y=c[0];m=c[1] if len(c)>1 else 12
            # A monthly/yearly coordinate is a period, not an invented exact
            # observation date. Gregorian end bounds effective evidence dates;
            # explicit observed_date, when supplied, remains separately bound.
            if s['calendar']=='gregorian':end=date(y,m,c[2] if len(c)>2 else calendar.monthrange(y,m)[1]).isoformat()
        observed=row.get('observed_date') if historical else s['reference_date']
        if historical and observed is not None and iso(observed).isoformat()[:len(key(c))]!=key(c):raise ValueError('observed_date_outside_coordinate_period')
        if freq=='annual':r.n(row['period'],p+'/period','year',s['source_reference'],observed,lo=1,hi=9998,integer=True,effective_not_after=end)
        value=None if row.get('value') is None else r.n(row['value'],p+'/value',s['unit'],s['source_reference'],observed,effective_not_after=end)
        if q=='valid' and value is None:raise ValueError('valid_record_requires_value')
        if q=='missing' and value is not None:raise ValueError('missing_record_cannot_have_value')
        groups[row['period']].append((value,q,row))
    duplicates=[dict(period=k,count=len(v),conflicting=len({(a,b) for a,b,_ in v})>1) for k,v in sorted(groups.items()) if len(v)>1]
    if duplicates and not allow_duplicates:raise ValueError('duplicate_climate_coordinates')
    # A duplicated coordinate is excluded, even if copies agree. No automatic
    # adjudication of which version/record represents the observation.
    usable={k:v[0][0] for k,v in groups.items() if len(v)==1 and v[0][1]=='valid'}
    return groups,usable,duplicates

def provenance(r,d):
    mode=enum(d['mode'],('questions','review'))
    if mode=='questions':return r.result(mode=mode,questions=['purpose_variable_period_resolution','selected_station_grid_versions_units_calendar','missing_quality_flags_station_moves_homogeneity','license_citation_update_date'],datasets=[])
    output=[]
    for j,s0 in enumerate(arr(d['datasets'],1,5)):
        s=source(r,s0);p='/datasets/'+str(j)
        freq=enum(s['frequency'],('daily','monthly','annual'))
        expected=coordinates(s['start'],s['end'],freq,s['calendar'])
        groups,valid,dups=records(r,s['records'],p+'/records',s,freq,True)
        outside=sorted(set(groups)-set(expected));missing=[k for k in expected if k not in valid]
        if outside:r.gap('records_outside_selected_period')
        if dups:r.gap('duplicate_coordinates_excluded_pending_resolution')
        if missing:r.gap('selected_period_has_missing_or_unusable_records')
        ranges=[];selected_range=None
        if s.get('range_check') is not None:
            rule=obj(s['range_check']);ref=text(rule['source_reference'])
            lo=r.n(rule['minimum'],p+'/range_check/minimum',s['unit'],ref)
            hi=r.n(rule['maximum'],p+'/range_check/maximum',s['unit'],ref)
            if lo>hi:raise ValueError('selected_range_order')
            selected_range=dict(minimum=fmt(lo),maximum=fmt(hi),unit=s['unit'],source_reference=ref)
            ranges=[dict(period=k,value=fmt(v)) for k,v in sorted(valid.items()) if v<lo or v>hi]
            if ranges:r.gap('selected_range_flags_require_review_no_automatic_deletion')
        moves=[]
        for item in arr(s.get('station_changes',[]),0,20):
            item=obj(item);dt=iso(item['date'])
            if dt>r.as_of:raise ValueError('future_station_change')
            moves.append(dict(date=item['date'],description=text(item['description']),source_reference=text(item['source_reference'])))
        output.append(dict(id=s['id'],kind=s['kind'],version=s['version'],variable=s['variable'],unit=s['unit'],calendar=s['calendar'],location=s['location'],reference_date=s['reference_date'],source_reference=s['source_reference'],license_reference=text(s['license_reference']) if s.get('license_reference') is not None else None,homogeneity_evidence_reference=text(s['homogeneity_evidence_reference']) if s.get('homogeneity_evidence_reference') is not None else None,limitations=text(s['limitations']) if s.get('limitations') is not None else None,frequency=freq,start=s['start'],end=s['end'],expected_records=len(expected),provided_records=len(s['records']),usable_unique_records=len(set(expected)&set(valid)),coverage_ratio=fmt(F(len(set(expected)&set(valid)),len(expected))),missing_or_unusable_periods=missing,outside_periods=outside,quality_counts=dict(Counter(v[0][1] for v in groups.values() if len(v)==1)),duplicate_groups=dups,selected_range_check=selected_range,range_flags=ranges,station_changes=moves,automatic_imputation_performed=False,homogenization_performed=False))
    return r.result(mode=mode,datasets=output)

SEASONS={'DJF':(12,1,2),'MAM':(3,4,5),'JJA':(6,7,8),'SON':(9,10,11),'annual':tuple(range(1,13))}
def aggregate(values,periods,policy,cal):
    if policy=='monthly_total_sum':return sum(values,F())
    weights=[F(month_days(*coord(p,'monthly',cal),cal)) for p in periods] if policy=='calendar_day_weighted_mean' else [F(1)]*len(values)
    return sum((v*w for v,w in zip(values,weights)),F())/sum(weights)
def normals(r,d):
    s=source(r,d['series']);p='/series';groups,valid,dups=records(r,s['records'],p+'/records',s,'monthly')
    policy=enum(d['aggregation'],('equal_month_mean','calendar_day_weighted_mean','monthly_total_sum'))
    basis=enum(s['value_basis'],('monthly_mean','monthly_total'))
    if (policy=='monthly_total_sum')!=(basis=='monthly_total'):raise ValueError('aggregation_must_match_monthly_value_basis')
    if basis=='monthly_total' and s['unit'] in ('degC','K'):raise ValueError('temperature_monthly_sum_not_supported')
    if s['unit']=='mm' and any(v<0 for v in valid.values()):raise ValueError('negative_monthly_precipitation')
    rule=obj(d['coverage_rule']);ref=text(rule['source_reference'])
    ratio=r.n(rule['minimum_year_fraction'],'/coverage_rule/minimum_year_fraction','ratio',ref,lo=F(0),hi=F(1))
    if ratio<=0:raise ValueError('positive_completeness_fraction')
    b=obj(d['baseline']);y0=r.n(b['start_year'],'/baseline/start_year','year',lo=1,hi=9997,integer=True);y1=r.n(b['end_year'],'/baseline/end_year','year',lo=y0,hi=min(y0+39,9998),integer=True)
    kind=enum(b['kind'],('standard_normal_candidate','selected_period_average'))
    if kind=='standard_normal_candidate' and (y1-y0+1!=30 or y1%10):raise ValueError('standard_candidate_requires_30_year_end_zero')
    if (y1,12)>tuple((r.as_of.year,r.as_of.month)):raise ValueError('future_observed_baseline')
    monthly=[];norm={};n_years=y1-y0+1
    for m in range(1,13):
        vals=[valid[f'{y:04d}-{m:02d}'] for y in range(y0,y1+1) if f'{y:04d}-{m:02d}' in valid]
        enough=F(len(vals),n_years)>=ratio
        norm[m]=mean(vals) if enough and vals else None
        monthly.append(dict(month=m,valid_years=len(vals),expected_years=n_years,coverage_ratio=fmt(F(len(vals),n_years)),normal=fmt(norm[m]),status='selected_completeness_met' if norm[m] is not None else 'normal_unavailable_insufficient_years'))
    if any(v is None for v in norm.values()):r.gap('some_monthly_normals_unavailable')
    r.gap('monthly_provider_quality_not_recomputed_from_raw_daily_data')
    r.gap('station_homogeneity_and_official_normal_status_not_established')
    # Calendar-weighted normal uses average baseline calendar-month lengths,
    # preserving the declared estimand instead of choosing a hidden leap year.
    def normal_for(months):
        if any(norm[m] is None for m in months):return None
        if policy=='monthly_total_sum':return sum((norm[m] for m in months),F())
        w=[sum((F(month_days(y,m,s['calendar'])) for y in range(y0,y1+1)),F())/n_years if policy=='calendar_day_weighted_mean' else F(1) for m in months]
        return sum((norm[m]*v for m,v in zip(months,w)),F())/sum(w)
    targets=[]
    for j,t in enumerate(arr(d['targets'],1,40)):
        t=obj(t);yr=r.n(t['year'],f'/targets/{j}/year','year',lo=2,hi=9998,integer=True)
        period=enum(t['period'],tuple(SEASONS)+('month',))
        if period=='month':months=(r.n(t['month'],f'/targets/{j}/month','month',lo=1,hi=12,integer=True),)
        else:months=SEASONS[period]
        periods=[f'{yr-1 if period=="DJF" and m==12 else yr:04d}-{m:02d}' for m in months]
        vals=[valid.get(k) for k in periods];value=None if any(v is None for v in vals) else aggregate(vals,periods,policy,s['calendar'])
        normal=normal_for(months);anomaly=None if value is None or normal is None else value-normal
        pc=None if anomaly is None or not normal else anomaly/abs(normal)*100
        if anomaly is not None and not normal:r.gap('percent_anomaly_undefined_zero_normal')
        # Comparison membership is explicit and never implicitly limited to
        # years outside the baseline.
        cy=arr(t.get('comparison_years',[]),0,80);comparison=[]
        for z,c in enumerate(cy):
            yy=r.n(c,f'/targets/{j}/comparison_years/{z}','year',lo=2,hi=9998,integer=True)
            keys=[f'{yy-1 if period=="DJF" and m==12 else yy:04d}-{m:02d}' for m in months]
            vs=[valid.get(k) for k in keys]
            comparison.append((yy,None if any(v is None for v in vs) else aggregate(vs,keys,policy,s['calendar'])))
        if len({y for y,_ in comparison})!=len(comparison):raise ValueError('duplicate_comparison_years')
        cv=[v for _,v in comparison if v is not None]
        rank=None if value is None or not cv else 1+sum(v>value for v in cv)
        if cy and (yr not in [y for y,_ in comparison]):raise ValueError('rank_target_must_belong_to_comparison_set')
        if any(v is None for _,v in comparison):r.gap('rank_comparison_incomplete_members_visible')
        targets.append(dict(year=yr,period=period,months=list(months),selected_coordinates=periods,value=fmt(value),normal=fmt(normal),anomaly=fmt(anomaly),percent_anomaly=fmt(pc) if policy=='monthly_total_sum' else None,comparison=[dict(year=y,value=fmt(v)) for y,v in comparison],rank_descending_competition=rank,rank_population=len(cv),rank_tie_count=None if value is None else sum(v==value for v in cv),rank_scope='explicit_selected_comparison_years',status='computed' if anomaly is not None else 'unavailable_missing_target_or_normal'))
    return r.result(series={k:s[k] for k in ('id','source_reference','version','variable','unit','calendar','location','reference_date')},baseline=dict(start_year=y0,end_year=y1,kind=kind,official_standard_status_established=False),aggregation=policy,coverage_rule=dict(minimum_year_fraction=fmt(ratio),source_reference=ref),monthly_normals=monthly,targets=targets,source_record_count=len(s['records']),unusable_record_count=len(groups)-len(valid))

def ranks(xs):return [F(1+sum(y<x for y in xs))+F(sum(y==x for y in xs)-1,2) for x in xs]
def outward_ranks(N,square):
    """floor((N-sqrt(square))/2), ceil((N+sqrt(square))/2), exactly."""
    root=isqrt(square.numerator//square.denominator)
    lower=(N-root)//2;upper=(N+root+1)//2
    while N-2*lower<0 or F((N-2*lower)**2)<square:lower-=1
    while N-2*(lower+1)>=0 and F((N-2*(lower+1))**2)>=square:lower+=1
    while 2*upper-N<0 or F((2*upper-N)**2)<square:upper+=1
    while 2*(upper-1)-N>=0 and F((2*(upper-1)-N)**2)>=square:upper-=1
    return lower,upper
def trend(r,t,p='/trend'):
    t=obj(t);s=source(r,t['series']);groups,valid,_=records(r,s['records'],p+'/series/records',s,'annual')
    pairs=sorted((int(k),v) for k,v in valid.items());n=len(pairs)
    if not 4<=n<=120:raise ValueError('trend_requires_4_to_120_valid_years')
    ys=[y for y,_ in pairs];xs=[v for _,v in pairs]
    slopes=sorted((xs[j]-xs[i])/F(ys[j]-ys[i]) for i in range(n) for j in range(i+1,n));slope=median(slopes)
    score=sum((xs[j]>xs[i])-(xs[j]<xs[i]) for i in range(n) for j in range(i+1,n))
    counts=Counter(xs);var=F(n*(n-1)*(2*n+5)-sum(k*(k-1)*(2*k+5) for k in counts.values()),18)
    critical=r.n(t['critical_z'],p+'/critical_z','1',t['test_rule_reference'],lo=F(1,100),hi=10)
    correction=enum(t['dependence'],('iid_assumed','hamed_rao_rank_variance'))
    regular=all(b-a==1 for a,b in zip(ys,ys[1:]));factor=F(1);acf=[];available=True;status='conditional_asymptotic_test'
    if correction=='hamed_rao_rank_variance':
        lag=r.n(t['maximum_lag'],p+'/maximum_lag','year',t['test_rule_reference'],lo=1,hi=n-1,integer=True)
        if not regular:
            available=False;status='correction_unavailable_irregular_years';r.gap('index_lag_is_not_one_year_for_irregular_series')
        else:
            residual=[v-slope*(y-ys[0]) for y,v in pairs];rr=ranks(residual);mu=mean(rr);den=sum(((v-mu)**2 for v in rr),F())
            if not den:
                available=False;status='rank_correlation_unavailable_constant_detrended_series';r.gap('dependence_correction_not_estimable')
            else:
                weighted=F()
                for k in range(1,lag+1):
                    rho=sum(((rr[i]-mu)*(rr[i+k]-mu) for i in range(n-k)),F())/den
                    use=rho*rho*n>critical*critical
                    acf.append(dict(lag_years=k,rank_autocorrelation=fmt(rho),selected_by_critical_rule=use))
                    if use:weighted+=(n-k)*(n-k-1)*(n-k-2)*rho
                # Signed correction, including negative serial dependence;
                # nonpositive factors are unavailable, never abs()/clamped.
                factor=1+F(2,n*(n-1)*(n-2))*weighted
                if factor<=0:available=False;status='nonpositive_variance_correction_unavailable';r.gap('dependence_correction_not_estimable')
    vv=var*factor if available else None
    if var==0:available=False;status='constant_series_test_unavailable';vv=None;r.gap('constant_series_no_test_variance')
    z=None;pv=None;significant=None;ci=None
    if available:
        sc=score-1 if score>0 else score+1 if score<0 else 0
        z=calc(lambda:dec(sc)/sqrt(vv));significant=F(sc*sc)>critical*critical*vv
        zfloat=float(z)
        if isfinite(zfloat):
            pp=erfc(abs(zfloat)/(2**0.5))
            if pp>0:pv=str(pp)
            else:r.gap('asymptotic_p_underflow_not_reported_as_zero')
        # Conservative outward-rounded Sen order-statistic interval using
        # selected normal critical value and selected variance model.
        N=len(slopes);left,right=outward_ranks(N,critical*critical*vv)
        lo=max(0,min(N-1,left-1));hi=max(0,min(N-1,right))
        ci=dict(lower=fmt(slopes[lo]),upper=fmt(slopes[hi]),lower_zero_based_rank=lo,upper_zero_based_rank=hi,method='conservative_outward_sen_rank_normal_approximation',nominal_coverage_established=False)
    if n<20:r.gap('small_sample_asymptotic_trend_inference')
    if not regular:r.gap('trend_years_irregular_sen_uses_actual_year_distances')
    return dict(series={k:s[k] for k in ('id','unit','calendar','reference_date','source_reference')},test_rule_reference=t['test_rule_reference'],selected_years=ys,valid_count=n,provided_count=len(t['series']['records']),missing_or_unusable_years=sorted(set(range(min(ys),max(ys)+1))-set(ys)),sen_slope_per_year=fmt(slope),sen_slope_per_decade=fmt(slope*10),intercept_at_first_year=fmt(median([v-slope*(y-ys[0]) for y,v in pairs])),mann_kendall_s=score,kendall_tau=fmt(F(score,len(slopes))),tau_definition='tau_a_S_over_all_pairs',iid_variance_s=fmt(var),dependence=correction,annual_spacing_regular=regular,rank_autocorrelations=acf,variance_multiplier=fmt(factor) if available else None,selected_variance_s=fmt(vv),critical_z=fmt(critical),z=fmt(z),asymptotic_two_sided_p=pv,p_method='binary64_erfc_of_decimal_z_approximation',exceeds_selected_critical_value=significant,slope_interval=ci,status=status,causal_attribution_established=False)

PRECIP={'Rx1day','Rx5day','SDII','R10mm','R20mm','CDD','CWD','PRCPTOT'}
TEMP={'FD','SU','ID','TR','TXx','TNx','TXn','TNn','DTR'}
def daily_indices(r,t,p='/daily_indices'):
    t=obj(t);s=source(r,t['series']);freq='daily'
    expected=coordinates(t['start'],t['end'],freq,s['calendar'],cap=366)
    selection=arr(t['indices'],1,17)
    if len(set(selection))!=len(selection):raise ValueError('duplicate_index_selection')
    if any(v not in PRECIP|TEMP for v in selection):raise ValueError('only_17_absolute_threshold_indices_supported')
    channels=obj(t['channels']);parsed={}
    allowed={'pr','tx','tn'}
    if not set(channels)<=allowed or not 1<=len(channels)<=2:raise ValueError('one_or_two_daily_channels')
    for name,rows in channels.items():
        ss=dict(s,records=rows,unit='mm' if name=='pr' else 'degC')
        _,values,_=records(r,rows,p+'/channels/'+name,ss,'daily')
        if set(values)-set(expected):raise ValueError('daily_records_outside_selected_window')
        if name=='pr' and any(v<0 for v in values.values()):raise ValueError('negative_daily_precipitation')
        parsed[name]=values
    req={name for name in ('pr','tx','tn') if any((i in PRECIP and name=='pr') or (i in {'SU','ID','TXx','TXn','DTR'} and name=='tx') or (i in {'FD','TR','TNx','TNn','DTR'} and name=='tn') for i in selection)}
    if not req<=set(parsed):raise ValueError('selected_index_channel_missing')
    if 'tx' in parsed and 'tn' in parsed and any(parsed['tx'][k]<parsed['tn'][k] for k in set(parsed['tx'])&set(parsed['tn'])):raise ValueError('daily_tx_below_tn')
    thresholds={};controls=obj(t.get('thresholds',{}))
    needed={'wet_day_mm':F(1)} if set(selection)&{'SDII','CDD','CWD','PRCPTOT'} else {}
    for code,field,value in (('FD','frost_degC',0),('SU','summer_degC',25),('ID','ice_degC',0),('TR','tropical_degC',20),('R10mm','heavy_mm',10),('R20mm','very_heavy_mm',20)):
        if code in selection:needed[field]=F(value)
    ref=text(t['definition_reference'])
    for field,canonical in needed.items():
        value=r.n(controls[field],p+'/thresholds/'+field,'mm' if field.endswith('_mm') else 'degC',ref)
        if value!=canonical:raise ValueError('ETCCDI_named_index_requires_canonical_selected_threshold')
        thresholds[field]=value
    policy=enum(t['window_policy'],('complete_selected_window','observed_segments_only'))
    results=[];coverage=[]
    for name in sorted(parsed):coverage.append(dict(channel=name,provided_valid_days=len(parsed[name]),expected_days=len(expected),missing_dates=[k for k in expected if k not in parsed[name]]))
    for code in selection:
        ch='pr' if code in PRECIP else 'tx' if code in {'SU','ID','TXx','TXn'} else 'tn'
        keys=[k for k in expected if k in parsed.get(ch,{})]
        complete=all(k in parsed[c] for c in ({'tx','tn'} if code=='DTR' else {ch}) for k in expected)
        vals=[parsed[ch][k] for k in keys];v=None;candidate=None
        if code=='DTR':
            both=[k for k in expected if k in parsed['tx'] and k in parsed['tn']]
            candidate=mean([parsed['tx'][k]-parsed['tn'][k] for k in both]) if both else None
        elif vals:
            if code in {'TXx','TNx','Rx1day'}:candidate=max(vals)
            elif code in {'TXn','TNn'}:candidate=min(vals)
            elif code in {'FD','ID'}:candidate=F(sum(x<0 for x in vals))
            elif code=='SU':candidate=F(sum(x>25 for x in vals))
            elif code=='TR':candidate=F(sum(x>20 for x in vals))
            elif code=='R10mm':candidate=F(sum(x>=10 for x in vals))
            elif code=='R20mm':candidate=F(sum(x>=20 for x in vals))
            elif code in {'SDII','PRCPTOT'}:
                wet=[x for x in vals if x>=thresholds['wet_day_mm']]
                candidate=sum(wet,F()) if code=='PRCPTOT' else mean(wet) if wet else None
            elif code=='Rx5day':
                sums=[sum((parsed['pr'][k] for k in expected[i:i+5]),F()) for i in range(len(expected)-4) if all(k in parsed['pr'] for k in expected[i:i+5])]
                candidate=max(sums) if sums else None
            elif code in {'CDD','CWD'}:
                longest=run=0
                for k in expected:
                    x=parsed['pr'].get(k)
                    hit=x is not None and (x<thresholds['wet_day_mm'] if code=='CDD' else x>=thresholds['wet_day_mm'])
                    run=run+1 if hit else 0;longest=max(longest,run)
                candidate=F(longest)
        if complete:v=candidate
        else:r.gap('daily_missing_dates_no_annual_or_complete_window_claim')
        results.append(dict(index=code,value=fmt(v),observed_segment_statistic=fmt(candidate) if policy=='observed_segments_only' else None,status='complete_selected_window' if complete and v is not None else 'undefined_no_wet_days' if complete and code=='SDII' else 'unavailable_incomplete_or_insufficient_window',unit='day' if code in {'FD','SU','ID','TR','R10mm','R20mm','CDD','CWD'} else 'mm/day' if code=='SDII' else 'mm' if code in PRECIP else 'degC',annual_index_claim=complete and coord(t['start'],'daily',s['calendar'])[1:]==(1,1) and coord(t['end'],'daily',s['calendar'])[1:]==(12,month_days(coord(t['end'],'daily',s['calendar'])[0],12,s['calendar']))))
    return dict(series={k:s[k] for k in ('id','calendar','reference_date','source_reference')},definition_reference=ref,start=t['start'],end=t['end'],window_policy=policy,run_boundary='reset_at_selected_window_no_gap_bridging',coverage=coverage,thresholds={k:fmt(v) for k,v in thresholds.items()},indices=results,all_27_ETCCDI_computed=False,imputation_performed=False)

def gumbel_fit(xs):
    n=len(xs);ordered=sorted(xs);l1=mean(xs);l2=sum(((2*i-n-1)*v for i,v in enumerate(ordered,1)),F())/F(n*(n-1))
    if l2<=0:return None
    with localcontext(CTX):
        scale=dec(l2)/Decimal(2).ln();loc=dec(l1)-EULER*scale
    return loc,scale,Decimal(0)
def expm1_stable(x):
    """Decimal exp(x)-1 without cancellation for near-zero GEV shape."""
    if x.copy_abs()>Decimal('0.5'):return x.exp()-1
    term=total=x
    for n in range(2,1000):
        term=term*x/n;new=total+term
        if new==total:return total
        total=new
    raise ValueError('bounded_expm1_convergence_required')
def quantile(params,T):
    mu,sigma,xi=params
    with localcontext(Context(prec=240,Emin=-999999,Emax=999999)):
        z=-(Decimal(1)-Decimal(1)/dec(T)).ln()
        if z<=0:raise ValueError('return_probability_resolution_bound')
        return mu-sigma*z.ln() if not xi else mu+sigma/xi*expm1_stable(-xi*z.ln())
def returns(r,t,p='/return_levels'):
    t=obj(t);mode=enum(t['mode'],('gumbel_l_moments','selected_gev_parameters'))
    unit=text(t['unit']);ref=text(t['source_reference']);periods=[r.n(x,f'{p}/return_periods/{i}','year',ref,lo=F(1000001,1000000),hi=1000000) for i,x in enumerate(arr(t['return_periods'],1,12))]
    if len(set(periods))!=len(periods):raise ValueError('duplicate_return_periods')
    critical=r.n(t['critical_z'],p+'/critical_z','1',t['uncertainty_rule_reference'],lo=F(1,100),hi=10) if mode=='gumbel_l_moments' else None
    reps=[];status='selected_fit';years=[];params=None
    if mode=='gumbel_l_moments':
        enum(t['block_basis'],('provided_annual_maxima',))
        s=source(r,t['series']);_,valid,_=records(r,s['records'],p+'/series/records',s,'annual')
        years=sorted(valid);xs=[valid[y] for y in years]
        if not 10<=len(xs)<=100:raise ValueError('gumbel_requires_10_to_100_annual_block_maxima')
        if s['unit']!=unit:raise ValueError('return_series_unit_mismatch')
        params=gumbel_fit(xs);status='fitted_gumbel_l_moments' if params else 'fit_unavailable_constant_blocks'
        if params:
            reps=[gumbel_fit(xs[:i]+xs[i+1:]) for i in range(len(xs))]
            if any(v is None for v in reps):reps=[];r.gap('jackknife_fit_degenerate_interval_unavailable')
    else:
        run=obj(t['fit_provenance'])
        for k in ('engine','version','configuration_sha256','data_sha256'):text(run[k])
        if any(not re.fullmatch(r'[0-9a-f]{64}',run[k]) for k in ('configuration_sha256','data_sha256')):raise ValueError('external_run_SHA256_required')
        if iso(run['run_date'])>r.as_of:raise ValueError('future_fit_run')
        def readpars(x,path):
            x=obj(x);mu=r.n(x['location'],path+'/location',unit,ref,run['run_date']);sigma=r.n(x['scale'],path+'/scale',unit,ref,run['run_date'],lo=F(1,10**100));xi=r.n(x['shape'],path+'/shape','1',ref,run['run_date'],lo=-1,hi=1)
            return dec(mu),dec(sigma),dec(xi)
        params=readpars(t['parameters'],p+'/parameters')
        for i,v in enumerate(arr(t.get('replicate_parameters',[]),0,80)):reps.append(readpars(v,f'{p}/replicate_parameters/{i}'))
        if not reps:r.gap('selected_gev_parameter_uncertainty_not_supplied')
    results=[]
    for T in periods:
        value=quantile(params,T) if params else None;lower=upper=None
        if params and reps:
            qs=[quantile(v,T) for v in reps];n=len(qs)
            with localcontext(CTX):
                avg=sum(qs)/n
                if mode=='gumbel_l_moments':
                    se=(Decimal(n-1)/n*sum((x-avg)**2 for x in qs)).sqrt();lower=value-dec(critical)*se;upper=value+dec(critical)*se
                else:
                    # Provided replicates are an empirical diagnostic range;
                    # no bootstrap percentile coverage is invented here.
                    lower=min(qs);upper=max(qs)
        results.append(dict(return_period_years=fmt(T),nonexceedance_probability=fmt(1-1/T),return_level=fmt(value),unit=unit,lower=fmt(lower),upper=fmt(upper),uncertainty_method='delete_one_jackknife_normal_approximation' if mode=='gumbel_l_moments' else 'provided_replicate_min_max_not_confidence_interval',coverage_established=False,extrapolation_ratio_to_record_length=fmt(T/len(years)) if years else None))
    r.gap('stationarity_annual_block_independence_and_tail_model_not_established')
    return dict(mode=mode,status=status,source_reference=ref,uncertainty_rule_reference=t.get('uncertainty_rule_reference') if mode=='gumbel_l_moments' else None,fit_provenance=dict(t['fit_provenance']) if mode=='selected_gev_parameters' else None,annual_block_years=years,block_completeness_recomputed=False,selected_parameters=None if params is None else dict(location=fmt(params[0]),scale=fmt(params[1]),shape=fmt(params[2])),shape_convention='GEV_xi_positive_heavy_tail_gumbel_xi_zero',critical_z=fmt(critical),replicate_count=len(reps),return_levels=results,weather_forecast=False)

def external_review(r,t,p):
    t=obj(t)
    for k in ('engine','version','configuration_sha256','data_sha256','source_reference','calendar','baseline','method'):text(t[k])
    if any(not re.fullmatch(r'[0-9a-f]{64}',t[k]) for k in ('configuration_sha256','data_sha256')):raise ValueError('external_run_SHA256_required')
    if iso(t['run_date'])>r.as_of:raise ValueError('future_external_run')
    rows=[]
    for i,x in enumerate(arr(t['results'],1,120)):
        x=obj(x);v=r.n(x['value'],f'{p}/results/{i}/value',x['unit'],t['source_reference'],t['run_date'])
        rows.append(dict(name=text(x['name']),period=text(x['period']),value=fmt(v),unit=x['unit']))
    r.gap('external_engine_results_reviewed_not_recomputed')
    return {**{k:t[k] for k in ('engine','version','configuration_sha256','data_sha256','source_reference','calendar','baseline','method','run_date')},'results':rows,'engine_executed_here':False}

def extremes(r,d):
    if not any(d.get(k) is not None for k in ('trend','daily_indices','return_levels','external_results')):raise ValueError('select_at_least_one_independent_analysis')
    return r.result(trend=trend(r,d['trend']) if d.get('trend') is not None else None,daily_indices=daily_indices(r,d['daily_indices']) if d.get('daily_indices') is not None else None,return_levels=returns(r,d['return_levels']) if d.get('return_levels') is not None else None,external_results=external_review(r,d['external_results'],'/external_results') if d.get('external_results') is not None else None)

def metrics(observed,model):
    delta=[b-a for a,b in zip(observed,model)]
    return dict(count=len(delta),bias=fmt(mean(delta)),mae=fmt(mean([abs(v) for v in delta])),rmse=fmt(sqrt(mean([v*v for v in delta]))))
def downscaling(r,d):
    mode=enum(d['mode'],('calibrate_and_project','external_results_review'))
    if mode=='external_results_review':return r.result(mode=mode,external_results=external_review(r,d['external_results'],'/external_results'))
    method=enum(d['method'],('additive_mean','multiplicative_mean'))
    unit=text(d['unit']);cal=enum(d['calendar'],('gregorian','365_day','360_day'))
    if method=='additive_mean' and unit not in ('degC','K'):raise ValueError('bounded_additive_temperature_only')
    if method=='multiplicative_mean' and unit not in ('mm','mm/day'):raise ValueError('bounded_multiplicative_precipitation_only')
    enum(d['training_weighting'],('equal_selected_months',))
    calibration={};model_out=[];source_ids=set()
    for i,m in enumerate(arr(d['models'],1,6)):
        m=obj(m);p=f'/models/{i}';identity=text(m['id'])
        if identity in calibration:raise ValueError('duplicate_model_id')
        for field in ('source_id','variant_label','grid_label','version','source_reference','observation_reference'):text(m[field])
        if m['source_id'] in source_ids:raise ValueError('bounded_one_variant_grid_per_source_model')
        source_ids.add(m['source_id'])
        rd=m['reference_date']
        if iso(rd)>r.as_of:raise ValueError('future_model_run_date')
        if iso(m['observation_reference_date'])>r.as_of:raise ValueError('future_observation_dataset_reference_date')
        training=[];validation=[];seen=set()
        for group,target in (('training',training),('validation',validation)):
            rows=arr(m[group],2,96)
            for j,row in enumerate(rows):
                row=obj(row);period=row['period'];coord(period,'monthly',cal)
                if period in seen:raise ValueError('overlapping_or_duplicate_calibration_validation_month')
                seen.add(period)
                y,month=coord(period,'monthly',cal)
                cutoff=date(y,month,calendar.monthrange(y,month)[1]).isoformat()
                actual=row.get('observed_date')
                if actual is not None and iso(actual).isoformat()[:7]!=period:raise ValueError('observed_date_outside_coordinate_period')
                a=r.n(row['observed'],f'{p}/{group}/{j}/observed',unit,m['observation_reference'],actual,effective_not_after=cutoff)
                b=r.n(row['model'],f'{p}/{group}/{j}/model',unit,m['source_reference'],rd)
                if method=='multiplicative_mean' and (a<0 or b<0):raise ValueError('negative_precipitation_in_calibration')
                if unit=='K' and (a<0 or b<0):raise ValueError('negative_absolute_temperature')
                if period>r.as_of.isoformat()[:7]:raise ValueError('future_training_or_validation_month')
                target.append((period,a,b))
        train_o=[v[1] for v in training];train_m=[v[2] for v in training];obsmean=mean(train_o);histmean=mean(train_m)
        if method=='multiplicative_mean' and histmean<=0:raise ValueError('multiplicative_model_training_mean_positive')
        parameter=obsmean-histmean if method=='additive_mean' else obsmean/histmean
        adjust=lambda x,parameter=parameter:x+parameter if method=='additive_mean' else x*parameter
        val_o=[v[1] for v in validation];val_m=[v[2] for v in validation]
        weight=r.n(m['weight'],p+'/weight','ratio',m['weight_reference'],lo=F(1,10**100))
        calibration[identity]=dict(parameter=parameter,obsmean=obsmean,histmean=histmean,weight=weight,adjust=adjust)
        months=Counter(int(v[0][-2:]) for v in training)
        if len(months)<12:r.gap('calibration_does_not_cover_all_calendar_months')
        if len(training)<360:r.gap('compact_calibration_is_not_a_30_year_climatology')
        r.gap('bias_adjustment_does_not_establish_spatial_downscaling_skill')
        model_out.append(dict(id=identity,source_id=m['source_id'],variant_label=m['variant_label'],grid_label=m['grid_label'],version=m['version'],reference_date=rd,observation_dataset_reference_date=m['observation_reference_date'],source_reference=m['source_reference'],observation_reference=m['observation_reference'],training_periods=[v[0] for v in training],validation_periods=[v[0] for v in validation],training_count=len(training),validation_count=len(validation),training_observed_mean=fmt(obsmean),training_model_mean=fmt(histmean),correction_parameter=fmt(parameter),parameter_unit=unit if method=='additive_mean' else 'ratio',weight=fmt(weight),validation_before=metrics(val_o,val_m),validation_after=metrics(val_o,[adjust(v) for v in val_m]),calibration_validation_disjoint=True))
    scenarios={}
    for i,s in enumerate(arr(d['scenarios'],1,6)):
        s=obj(s);sid=text(s['id'])
        if sid in scenarios:raise ValueError('duplicate_scenario_id')
        scenarios[sid]=r.n(s['weight'],f'/scenarios/{i}/weight','ratio',s['source_reference'],lo=F(1,10**100))
    projections=[];groups=defaultdict(dict);seen=set()
    for i,x in enumerate(arr(d['projections'],1,72)):
        x=obj(x);mid=text(x['model_id']);sid=text(x['scenario_id']);horizon=text(x['horizon']);p=f'/projections/{i}'
        if mid not in calibration or sid not in scenarios:raise ValueError('projection_unknown_model_or_scenario')
        if not re.fullmatch(r'\d{4}-\d{4}',horizon):raise ValueError('horizon_year_range_required')
        h0,h1=map(int,horizon.split('-'))
        if not 1<=h0<=h1<=9998:raise ValueError('horizon_order')
        ident=(mid,sid,horizon)
        if ident in seen:raise ValueError('duplicate_projection_identity')
        seen.add(ident);c=calibration[mid]
        val=r.n(x['value'],p+'/value',unit,x['source_reference'],x['reference_date'])
        if method=='multiplicative_mean' and val<0:raise ValueError('negative_precipitation_projection')
        if unit=='K' and val<0:raise ValueError('negative_absolute_temperature')
        adj=c['adjust'](val);change=adj-c['obsmean'];pc=change/c['obsmean']*100 if c['obsmean'] else None
        sd=None if x.get('internal_standard_deviation') is None else r.n(x['internal_standard_deviation'],p+'/internal_standard_deviation',unit,x['source_reference'],x['reference_date'],lo=0)
        # Supplied internal spread must be on the corrected-change scale.
        if sd is not None and x.get('internal_spread_basis')!='corrected_change':raise ValueError('internal_spread_corrected_change_basis_required')
        groups[(horizon,sid)][mid]=(change,sd)
        projections.append(dict(model_id=mid,scenario_id=sid,horizon=horizon,raw_value=fmt(val),adjusted_value=fmt(adj),reference_value=fmt(c['obsmean']),change=fmt(change),percent_change=fmt(pc) if method=='multiplicative_mean' else None,internal_standard_deviation=fmt(sd),unit=unit,source_reference=x['source_reference'],reference_date=x['reference_date']))
    panel=enum(d['panel_policy'],('require_complete','renormalize_visible_missing'))
    summaries=[]
    for horizon in sorted({h for h,_ in groups}):
        conditional=[]
        for sid,sw in scenarios.items():
            rows=groups.get((horizon,sid),{});missing=sorted(set(calibration)-set(rows))
            if missing and panel=='require_complete':raise ValueError('incomplete_scenario_model_panel')
            if missing:r.gap('ensemble_weights_renormalized_over_visible_selected_models')
            if not rows:raise ValueError('scenario_without_projection_at_horizon')
            den=sum((calibration[m]['weight'] for m in rows),F());weights={m:calibration[m]['weight']/den for m in rows};mu=sum((weights[m]*rows[m][0] for m in rows),F())
            var=sum((weights[m]*(rows[m][0]-mu)**2 for m in rows),F())
            internal=sum((weights[m]*rows[m][1]**2 for m in rows),F()) if all(v[1] is not None for v in rows.values()) else None
            conditional.append((sid,sw,mu,var,internal,missing,weights))
        den=sum((s[1] for s in conditional),F());mu=sum((s[1]*s[2] for s in conditional),F())/den
        sv=sum((s[1]*(s[2]-mu)**2 for s in conditional),F())/den;mv=sum((s[1]*s[3] for s in conditional),F())/den
        iv=sum((s[1]*s[4] for s in conditional),F())/den if all(s[4] is not None for s in conditional) else None
        if iv is None:r.gap('internal_variability_not_quantified_from_single_or_incomplete_realizations')
        summaries.append(dict(horizon=horizon,weighted_change=fmt(mu),unit=unit,scenario_variance=fmt(sv),conditional_model_variance=fmt(mv),internal_variance=fmt(iv),total_descriptive_variance=fmt(sv+mv+iv) if iv is not None else None,variance_unit=unit+'^2',scenario_summaries=[dict(scenario_id=sid,normalized_scenario_weight=fmt(sw/den),weighted_change=fmt(mm),model_variance=fmt(vv),internal_variance=fmt(ii),missing_model_ids=missing,normalized_model_weights={m:fmt(w) for m,w in weights.items()}) for sid,sw,mm,vv,ii,missing,weights in conditional],spread_interpretation='selected_hierarchical_descriptive_moments_not_probabilities_or_causal_partition'))
    r.gap('model_independence_and_projection_skill_not_established')
    return r.result(mode=mode,method=method,unit=unit,calendar=cal,training_weighting=d['training_weighting'],panel_policy=panel,models=model_out,projections=projections,ensemble=summaries,weather_forecast=False)

def _run(function,data):
    if function not in FUNCTIONS:raise ValueError('unknown_climate_data_function')
    r=Read(data)
    try:
        with localcontext(CTX):result=dict(data_provenance=provenance,normals_anomalies=normals,trends_extremes=extremes,scenarios_downscaling=downscaling)[function](r,data)
    except (KeyError,TypeError,AttributeError,IndexError):raise ValueError('malformed_climate_data_structure') from None
    except (DecimalException,OverflowError,ZeroDivisionError):raise ValueError('bounded_climate_arithmetic_required') from None
    return result,r.units
def execute(function,data):return _run(function,data)[0]
def input_units(function,data):return _run(function,data)[1]
def selected_texts(function,data):
    if function not in FUNCTIONS:raise ValueError('unknown_climate_data_function')
    out={};seen=set()
    def put(path,value,refs):
        text(value);refs=list(dict.fromkeys(text(x) for x in refs));ident=(tuple(refs),value)
        if ident not in seen:out[path]=dict(text=value,source_references=refs);seen.add(ident)
    def series_dates(s,path,rows=None,record_path=None):
        s=obj(s);refs=[s['source_reference']];put(path+'/reference_date',s['reference_date'],refs)
        for i,row in enumerate(arr(s.get('records',[]) if rows is None else rows,0,750)):
            row=obj(row);rp=(path+'/records' if record_path is None else record_path)+'/'+str(i)
            period=text(row['period'])
            if not re.fullmatch(r'\d{4}',period):put(rp+'/period',period,refs)
            if row.get('observed_date') is not None:put(rp+'/observed_date',row['observed_date'],refs)
    def external_dates(t,path):
        t=obj(t);put(path+'/run_date',t['run_date'],[t['source_reference']])
        for i,row in enumerate(arr(t['results'],1,120)):put(f'{path}/results/{i}/period',obj(row)['period'],[t['source_reference']])
    data=obj(data)
    try:
        if function=='data_provenance' and data.get('mode')=='review':
            for i,s in enumerate(arr(data['datasets'],1,5)):
                series_dates(s,f'/datasets/{i}')
                for j,x in enumerate(arr(s.get('station_changes',[]),0,20)):put(f'/datasets/{i}/station_changes/{j}/date',obj(x)['date'],[x['source_reference']])
        elif function=='normals_anomalies':series_dates(data['series'],'/series')
        elif function=='trends_extremes':
            if data.get('trend') is not None:series_dates(obj(data['trend'])['series'],'/trend/series')
            if data.get('daily_indices') is not None:
                t=obj(data['daily_indices']);s=obj(t['series']);put('/daily_indices/series/reference_date',s['reference_date'],[s['source_reference']])
                for name,rows in obj(t['channels']).items():series_dates(s,'/daily_indices/series',rows,'/daily_indices/channels/'+esc(name))
            if data.get('return_levels') is not None:
                t=obj(data['return_levels'])
                if t.get('mode')=='gumbel_l_moments':series_dates(t['series'],'/return_levels/series')
                else:put('/return_levels/fit_provenance/run_date',obj(t['fit_provenance'])['run_date'],[t['source_reference']])
            if data.get('external_results') is not None:external_dates(data['external_results'],'/external_results')
        elif function=='scenarios_downscaling':
            if data.get('mode')=='external_results_review':external_dates(data['external_results'],'/external_results')
            else:
                for i,m in enumerate(arr(data['models'],1,6)):
                    m=obj(m);p=f'/models/{i}';put(p+'/reference_date',m['reference_date'],[m['source_reference']]);put(p+'/observation_reference_date',m['observation_reference_date'],[m['observation_reference']])
                    for group in ('training','validation'):
                        for j,row in enumerate(arr(m[group],2,96)):
                            row=obj(row);put(f'{p}/{group}/{j}/period',row['period'],[m['source_reference'],m['observation_reference']])
                            if row.get('observed_date') is not None:put(f'{p}/{group}/{j}/observed_date',row['observed_date'],[m['observation_reference']])
                for i,x in enumerate(arr(data['projections'],1,72)):put(f'/projections/{i}/reference_date',obj(x)['reference_date'],[x['source_reference']])
    except (KeyError,TypeError,AttributeError,IndexError):raise ValueError('malformed_selected_coordinate_structure') from None
    # Only designated literal excerpts, never authored rationale/analysis.
    def walk(value,path,depth):
        if depth>28:raise ValueError('nested_input_bound')
        if type(value) is dict:
            for k,v in value.items():
                if type(k) is not str:raise ValueError('string_keys_required')
                q=path+'/'+esc(k)
                if k in ('excerpt','selected_excerpt','original_text'):
                    out[q]=text(v)
                else:walk(v,q,depth+1)
        elif type(value) is list:
            if len(value)>800:raise ValueError('bounded_array_required')
            for i,v in enumerate(value):walk(v,path+'/'+str(i),depth+1)
    walk(obj(data),'',0)
    return out

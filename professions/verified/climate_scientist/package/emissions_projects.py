"""Bounded, selected-source GHG arithmetic and climate-project draft reviews.

No built-in statutory thresholds, GWP tables, fuel factors, registry access or
verification grants. All finite arithmetic/predicates use exact Fractions.
"""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal, Context, localcontext, DecimalException
from fractions import Fraction as F
import re

FUNCTIONS=('ghg_inventory','climate_project')
NUMBER=re.compile(r'[+-]?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?\Z')
MASS={'g':F(1,1000000),'kg':F(1,1000),'t':F(1)}
CO2E_MASS={'gCO2e':F(1,1000000),'kgCO2e':F(1,1000),'tCO2e':F(1)}
ACTIVITY_UNITS=('g','kg','t','m3','L','kWh','MWh','GJ','TJ','km','unit')
AGGREGATE_MODELS=('activity_CO2e_factor','provided_CO2e')

def fail(path,why):raise ValueError(path+':'+why)
def obj(v,p,required=(),optional=()):
    if type(v)is not dict or set(v)-set(required)-set(optional) or set(required)-set(v):fail(p,'object_keys')
    return v
def text(v,p,maximum=4000):
    if type(v)is not str or not v.strip() or len(v)>maximum or any(ord(c)<32 and c not in '\n\r\t' for c in v):fail(p,'text')
    return v
def choice(v,p,values):
    if type(v)is not str or v not in values:fail(p,'choice')
    return v
def rows(v,p,maximum,minimum=0):
    if type(v)is not list or not minimum<=len(v)<=maximum:fail(p,'array_size')
    return v
def unique(items,p,key='id'):
    ids=[x[key] for x in items]
    if len(set(ids))!=len(ids):fail(p,'duplicate_identity')
def iso(v,p,cutoff=None):
    if type(v)is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',v):fail(p,'ISO_date')
    try:d=date.fromisoformat(v)
    except ValueError:fail(p,'ISO_date')
    if cutoff and v>cutoff:fail(p,'date_after_cutoff')
    return d
def serial(v):
    if isinstance(v,F):
        with localcontext(Context(prec=180,Emin=-9999,Emax=9999)):return '0' if not v else str(Decimal(v.numerator)/Decimal(v.denominator))
    if type(v)is dict:return {k:serial(x) for k,x in v.items()}
    if type(v)is list:return [serial(x) for x in v]
    return v
def bounded(v):
    count=0
    def walk(x,depth):
        nonlocal count
        if depth>20:fail('data','nesting_limit')
        if type(x)is dict:
            if any(type(k)is not str for k in x):fail('data','string_keys')
            for y in x.values():walk(y,depth+1)
        elif type(x)is list:
            if len(x)>64:fail('data','array_limit')
            for y in x:walk(y,depth+1)
        else:
            if x is not None and type(x)not in (str,bool):fail('data','untyped_leaf')
            count+=1
            if count>900:fail('data','leaf_budget')
    walk(v,0)

class Read:
    def __init__(self,data):
        self.data=data;self.cutoff=data.get('as_of');iso(self.cutoff,'/as_of');choice(data.get('jurisdiction'),'/jurisdiction',('RU',))
        self.units={};self.texts={};self.gaps=[]
    def literal(self,row,p,key='excerpt'):
        self.texts[p+'/'+key]=text(row[key],p+'/'+key,6000)
    def ref(self,row,p):return text(row.get('source_reference'),p+'/source_reference',200)
    def q(self,v,p,units,low=None,high=None,integer=False,effective_not_after=None):
        obj(v,p,('value','unit','source_reference'),('observed_date',))
        raw=v['value']
        if type(raw)is not str or len(raw)>150 or not NUMBER.fullmatch(raw):fail(p,'exact_decimal_string')
        d=Decimal(raw)
        if not d.is_finite() or len(d.as_tuple().digits)>40 or abs(d.as_tuple().exponent)>140 or d and not -100<=d.adjusted()<=100:fail(p,'decimal_bounds')
        n=F(d)
        if n and not F('1e-100')<=abs(n)<=F('1e100'):fail(p,'decimal_bounds')
        unit=text(v['unit'],p+'/unit',80)
        if units is not None and unit not in units:fail(p,'unit')
        if low is not None and n<low or high is not None and n>high or integer and n.denominator!=1:fail(p,'range_or_integer')
        self.ref(v,p);bound=effective_not_after or self.cutoff
        meta={'unit':unit,'effective_not_after':bound,'published_not_after':self.cutoff,'source_references':[v['source_reference']]}
        if 'observed_date'in v:iso(v['observed_date'],p+'/observed_date',bound);meta['effective_date']=v['observed_date']
        self.units[p+'/value']=meta
        return n
    def basis(self,v,p,roles):
        obj(v,p,('document_identity','edition','publication_date','effective_from','effective_to','selection_date','role','scope','clause','source_reference','excerpt'))
        for k in ('document_identity','edition','scope','clause'):text(v[k],p+'/'+k)
        choice(v['role'],p+'/role',roles);self.ref(v,p);self.literal(v,p)
        iso(v['publication_date'],p+'/publication_date',self.cutoff);iso(v['selection_date'],p+'/selection_date',self.cutoff)
        start=iso(v['effective_from'],p+'/effective_from') if v['effective_from'] is not None else None
        end=iso(v['effective_to'],p+'/effective_to') if v['effective_to'] is not None else None
        if start and end and end<start:fail(p,'reversed_effective_window')
        within=None if start is None else v['selection_date']>=v['effective_from'] and (end is None or v['selection_date']<=v['effective_to'])
        if within is not True:self.gaps.append({'kind':'selected_basis_window_unresolved','path':p})
        if v['publication_date']>v['selection_date']:self.gaps.append({'kind':'basis_published_after_selected_date','path':p})
        return dict(deepcopy(v),selected_date_within_supplied_window=within,publication_after_selected_date=v['publication_date']>v['selection_date'],applicability_established=False)
    def record(self,v,p,roles=None):
        obj(v,p,('id','state','note'),('role','date','source_reference','excerpt'))
        text(v['id'],p+'/id',200);text(v['note'],p+'/note')
        choice(v['state'],p+'/state',('provided','missing','unknown','not_applicable'))
        if roles is not None:choice(v.get('role'),p+'/role',roles)
        elif 'role'in v:text(v['role'],p+'/role',200)
        if 'date'in v:iso(v['date'],p+'/date',self.cutoff)
        if v['state']=='provided' or 'source_reference'in v or 'excerpt'in v:
            self.ref(v,p);self.literal(v,p)
        if v['state']in ('missing','unknown'):self.gaps.append({'kind':'selected_record_unresolved','path':p,'state':v['state']})
        return dict(deepcopy(v),record_semantics_established=False)

def deadline(v,p,r):
    if v is None:return None
    obj(v,p,('mode','basis','boundary','roll'),('date','year_offset','month','day','calendar'))
    basis=r.basis(v['basis'],p+'/basis',('reporting_deadline',));choice(v['boundary'],p+'/boundary',('on_or_before','before_exclusive'));roll=choice(v['roll'],p+'/roll',('none','next_working_day'))
    if v['mode']=='provided_date':
        if set(v)&{'year_offset','month','day'}:fail(p,'provided_deadline_fields')
        nominal=iso(v.get('date'),p+'/date')
    elif v['mode']=='annual_month_day':
        if 'date'in v:fail(p,'annual_deadline_fields')
        y=int(r.q(r.data['reporting_year'],'/reporting_year',('year',),1800,2300,True))
        offset=int(r.q(v.get('year_offset'),p+'/year_offset',('year',),0,2,True,effective_not_after=basis['selection_date']))
        month=int(r.q(v.get('month'),p+'/month',('month',),1,12,True,effective_not_after=basis['selection_date']))
        day=int(r.q(v.get('day'),p+'/day',('day',),1,31,True,effective_not_after=basis['selection_date']))
        try:nominal=date(y+offset,month,day)
        except ValueError:fail(p,'invalid_annual_date')
    else:fail(p,'deadline_mode')
    last=nominal if v['boundary']=='on_or_before' else nominal-timedelta(days=1);candidate=last
    if roll=='none':
        if 'calendar'in v:fail(p,'unused_calendar')
    else:
        cal=obj(v.get('calendar'),p+'/calendar',('source_reference','excerpt','days'));r.ref(cal,p+'/calendar');r.literal(cal,p+'/calendar')
        daymap={}
        for i,row in enumerate(rows(cal['days'],p+'/calendar/days',32,1)):
            q=p+'/calendar/days/'+str(i);obj(row,q,('date','kind'));iso(row['date'],q+'/date');choice(row['kind'],q+'/kind',('working','nonworking'))
            if row['date']in daymap:fail(q,'duplicate_calendar_day')
            daymap[row['date']]=row['kind']
        for _ in range(32):
            if candidate.isoformat()not in daymap:fail(p,'calendar_classification_missing')
            if daymap[candidate.isoformat()]=='working':break
            candidate+=timedelta(days=1)
        else:fail(p,'calendar_window_exhausted')
    return dict(provided=deepcopy(v),basis=basis,nominal_date=nominal.isoformat(),last_included_before_roll=last.isoformat(),candidate_deadline=candidate.isoformat(),days_until_candidate=(candidate-date.fromisoformat(r.cutoff)).days,legal_deadline_established=False,filing_performed=False)

def eligibility(v,p,r):
    if v is None:return None
    obj(v,p,('basis','perimeter_id','gwp_set_id','covered_categories','threshold','annual_records','conditions'),('selected_status_record',))
    basis=r.basis(v['basis'],p+'/basis',('regulated_organization_criteria',))
    for k in ('perimeter_id','gwp_set_id'):text(v[k],p+'/'+k,200)
    categories=[text(x,p+'/covered_categories',200) for x in rows(v['covered_categories'],p+'/covered_categories',12,1)]
    if len(set(categories))!=len(categories):fail(p,'duplicate_category')
    threshold=r.q(v['threshold'],p+'/threshold',('tCO2e',),0,effective_not_after=basis['selection_date']);review=[]
    for i,row in enumerate(rows(v['annual_records'],p+'/annual_records',6)):
        q=p+'/annual_records/'+str(i);obj(row,q,('id','year','perimeter_id','gwp_set_id','covered_categories','state','source_reference','excerpt'),('amount',))
        text(row['id'],q+'/id',200);year=int(r.q(row['year'],q+'/year',('year',),1800,date.fromisoformat(r.cutoff).year,True));r.ref(row,q);r.literal(row,q)
        for k in ('perimeter_id','gwp_set_id'):text(row[k],q+'/'+k,200)
        selected_categories=[text(x,q+'/covered_categories',200) for x in rows(row['covered_categories'],q+'/covered_categories',12,1)]
        if len(set(selected_categories))!=len(selected_categories):fail(q,'duplicate_category')
        state=choice(row['state'],q+'/state',('provided','missing','unknown'))
        if state=='provided':amount=r.q(row.get('amount'),q+'/amount',('tCO2e',),0,effective_not_after=min(r.cutoff,f'{year:04d}-12-31'))
        else:
            if 'amount'in row:fail(q,'unresolved_annual_amount_must_be_absent')
            amount=None;r.gaps.append({'kind':'annual_emissions_amount_unresolved','id':row['id'],'state':state})
        mismatch=[k for k in ('perimeter_id','gwp_set_id') if row[k]!=v[k]]
        if set(selected_categories)!=set(categories):mismatch.append('covered_categories')
        if mismatch:r.gaps.append({'kind':'annual_record_not_comparable','id':row['id'],'fields':mismatch})
        review.append(dict(provided=deepcopy(row),comparable_on_supplied_identifiers=not mismatch,comparability_gaps=mismatch,amount_status=state,at_or_above_selected_threshold=None if mismatch or amount is None else amount>=threshold,threshold=threshold,unit='tCO2e'))
    unique([x['provided'] for x in review],p+'/annual_records')
    if not review:r.gaps.append({'kind':'annual_emissions_history_not_supplied'})
    conditions=[r.record(x,p+'/conditions/'+str(i)) for i,x in enumerate(rows(v['conditions'],p+'/conditions',8))];unique(conditions,p+'/conditions')
    status=r.record(v['selected_status_record'],p+'/selected_status_record') if 'selected_status_record'in v else None
    return dict(basis=basis,perimeter_id=v['perimeter_id'],gwp_set_id=v['gwp_set_id'],covered_categories=categories,annual_reviews=review,condition_reviews=conditions,selected_status_record=status,regulated_status='not_established',scope='numeric_threshold_comparisons_do_not_determine_legal_status')

def gas_gwp(v,r):
    if v is None:return {},None,None
    gwp=obj(v,'/gwp',('set_id','horizon','basis','values'));text(gwp['set_id'],'/gwp/set_id',200);basis=r.basis(gwp['basis'],'/gwp/basis',('GWP_table',))
    if r.q(gwp['horizon'],'/gwp/horizon',('year',),1,500,True,effective_not_after=basis['selection_date'])!=100:fail('/gwp/horizon','only_selected_GWP100_supported')
    values={}
    for i,g in enumerate(rows(gwp['values'],'/gwp/values',12,1)):
        p='/gwp/values/'+str(i);obj(g,p,('gas','value'));gas=text(g['gas'],p+'/gas',100)
        if gas in values or not re.fullmatch(r'[A-Z][A-Za-z0-9_-]{0,39}',gas) or gas.upper()in ('CO2E','CO2EQ','CO2-EQ','HFC','HFCS','PFC','PFCS') or gas.upper()=='CO2' and gas!='CO2':fail(p,'duplicate_or_non_species_gas')
        value=r.q(g['value'],p+'/value',('tCO2e/t_gas',),F('1e-100'),effective_not_after=basis['selection_date'])
        if gas=='CO2' and value!=1:fail(p,'CO2_reference_GWP_must_be_one')
        values[gas]=value
    return values,basis,dict(deepcopy(gwp),basis=basis)

def aggregate_basis(v,p,r):
    obj(v,p,('set_id','horizon','basis'))
    basis=r.basis(v['basis'],p+'/basis',('aggregate_CO2e_basis',))
    identity=None if v['set_id'] is None else text(v['set_id'],p+'/set_id',200)
    horizon=None if v['horizon'] is None else r.q(v['horizon'],p+'/horizon',('year',),1,500,True,effective_not_after=basis['selection_date'])
    if identity is None or horizon is None:r.gaps.append({'kind':'aggregate_CO2e_basis_metadata_unresolved','path':p})
    if horizon is not None and horizon!=100:r.gaps.append({'kind':'aggregate_CO2e_horizon_not_100','path':p})
    return dict(set_id=identity,horizon_years=horizon,basis=basis,metadata_status='provided' if identity is not None and horizon is not None else 'unknown',GWP_applied_again=False)

def inventory(data,r):
    if data.get('mode')=='questions':
        obj(data,'data',('as_of','jurisdiction','mode'),('organization','purpose'))
        for key in ('organization','purpose'):
            if key in data:text(data[key],'/'+key)
        return dict(status='inventory_inputs_required',organization=data.get('organization'),purpose=data.get('purpose'),source_reviews=[],questions=['organization_activities_and_reporting_period','selected_boundary_sites_and_categories','prior_year_emissions_perimeter_GWP_and_coverage','activity_records_and_exact_units','selected_method_factor_and_oxidation_treatment','gas_species_and_selected_GWP100_set','dated_reporting_criteria_and_deadline_basis','quality_controls_exclusions_and_uncertainty'],inventory_calculation_performed=False)
    obj(data,'data',('as_of','jurisdiction','mode','organization','reporting_year','period_start','period_end','framework','boundary','methods','records'),('gwp','eligibility_review','deadline','exclusions','quality_controls'))
    choice(data['mode'],'/mode',('calculate_selected',))
    text(data['organization'],'/organization');year=int(r.q(data['reporting_year'],'/reporting_year',('year',),1800,date.fromisoformat(r.cutoff).year,True))
    start=iso(data['period_start'],'/period_start',r.cutoff);end=iso(data['period_end'],'/period_end',r.cutoff)
    if start>end or start.year!=year or end.year!=year:fail('/period_start','report_period')
    framework=choice(data['framework'],'/framework',('RU_direct_draft','GHGP_corporate_selected_gross'))
    boundary=obj(data['boundary'],'/boundary',('id','description','consolidation','site_ids','covered_categories','source_reference','excerpt'))
    for k in ('id','description'):text(boundary[k],'/boundary/'+k)
    choice(boundary['consolidation'],'/boundary/consolidation',('operational_control','financial_control','equity_share','selected_RU_direct_perimeter'))
    sites=[text(x,'/boundary/site_ids',200) for x in rows(boundary['site_ids'],'/boundary/site_ids',6,1)]
    if len(set(sites))!=len(sites):fail('/boundary/site_ids','duplicate_site')
    for x in rows(boundary['covered_categories'],'/boundary/covered_categories',12,1):text(x,'/boundary/covered_categories',200)
    r.ref(boundary,'/boundary');r.literal(boundary,'/boundary')
    methodmap={};methodreviews=[]
    for i,m in enumerate(rows(data['methods'],'/methods',6,1)):
        p='/methods/'+str(i);obj(m,p,('id','model','basis'));text(m['id'],p+'/id',200);choice(m['model'],p+'/model',('activity_factor','combustion_energy','measured_mass')+AGGREGATE_MODELS);basis=r.basis(m['basis'],p+'/basis',('quantification_method',))
        if m['id']in methodmap:fail(p,'duplicate_method')
        methodmap[m['id']]=(m,basis);methodreviews.append(dict(id=m['id'],model=m['model'],basis=basis))
    gwpmap,gwpbasis,gwp_display=gas_gwp(data.get('gwp'),r)
    reviews=[];gas_totals={};separate={};seen_activity={};basis_groups={};aggregate_count=0;seen_scopes=set()
    for i,row in enumerate(rows(data['records'],'/records',10,1)):
        p='/records/'+str(i);obj(row,p,('id','activity_id','site_id','category','flow','scope','method_id','period_start','period_end','parameters','source_reference','excerpt'),('gas','carbon_origin','oxidation_mode','oxidation','attribution','co2e_basis'))
        for k in ('id','activity_id','category','method_id'):text(row[k],p+'/'+k,200)
        if row['site_id']not in sites or row['category']not in boundary['covered_categories']:fail(p,'record_outside_selected_boundary')
        if row['method_id']not in methodmap:fail(p,'missing_method')
        m,basis=methodmap[row['method_id']];q=row['parameters'];model=m['model'];aggregate=model in AGGREGATE_MODELS;r.ref(row,p);r.literal(row,p)
        rs=iso(row['period_start'],p+'/period_start',r.cutoff);re_=iso(row['period_end'],p+'/period_end',r.cutoff)
        if not start<=rs<=re_<=end:fail(p,'record_period_outside_inventory')
        flow=choice(row['flow'],p+'/flow',('emission',) if aggregate else ('emission','removal'))
        scopes=('RU_direct',) if framework=='RU_direct_draft' else ('scope1','scope2_location','scope2_market','scope3')
        scope=choice(row['scope'],p+'/scope',scopes)
        if row['category']in ('purchased_energy','value_chain') and scope in ('RU_direct','scope1'):fail(p,'declared_indirect_category_in_direct_scope')
        if scope in ('scope2_location','scope2_market') and row['category']!='purchased_energy':fail(p,'scope2_requires_declared_purchased_energy')
        seen_scopes.add(scope);mass=None;origin=None;selected_gwp=None
        if aggregate:
            if any(k in row for k in ('gas','carbon_origin','oxidation_mode','oxidation')):fail(p,'aggregate_CO2e_has_no_gas_or_oxidation')
            record_basis=aggregate_basis(row.get('co2e_basis'),p+'/co2e_basis',r);aggregate_count+=1
            if model=='provided_CO2e':
                obj(q,p+'/parameters',('amount',));aggregate_amount=r.q(q['amount'],p+'/parameters/amount',tuple(CO2E_MASS),0,effective_not_after=row['period_end'])*CO2E_MASS[q['amount']['unit']]
            else:
                obj(q,p+'/parameters',('activity','factor'));activity=r.q(q['activity'],p+'/parameters/activity',ACTIVITY_UNITS,0,effective_not_after=row['period_end']);unit=q['activity']['unit']
                factor_unit=q['factor'].get('unit') if type(q.get('factor'))is dict else None
                if type(factor_unit)is not str or factor_unit.count('/')!=1:fail(p,'CO2e_factor_per_exact_activity_unit')
                numerator,denominator=factor_unit.split('/')
                if numerator not in CO2E_MASS or denominator!=unit:fail(p,'CO2e_factor_unit_dimensions')
                aggregate_amount=activity*r.q(q['factor'],p+'/parameters/factor',(factor_unit,),0,effective_not_after=record_basis['basis']['selection_date'])*CO2E_MASS[numerator]
        else:
            if 'co2e_basis'in row:fail(p,'gas_model_uses_selected_GWP_table_not_aggregate_basis')
            text(row.get('gas'),p+'/gas',100)
            if row['gas']not in gwpmap:fail(p,'missing_selected_gas_GWP')
            origin=choice(row.get('carbon_origin'),p+'/carbon_origin',('fossil','biogenic','other','not_applicable'))
            if flow=='removal' and row['gas']!='CO2':fail(p,'only_selected_CO2_removal_mass_supported')
            selected_gwp=gwpmap[row['gas']];record_basis=dict(set_id=data['gwp']['set_id'],horizon_years=F(100),basis=gwpbasis,metadata_status='provided',GWP_applied_again=False)
            if model=='measured_mass':
                obj(q,p+'/parameters',('mass',));mass=r.q(q['mass'],p+'/parameters/mass',tuple(MASS),0,effective_not_after=row['period_end'])*MASS[q['mass']['unit']]
            else:
                obj(q,p+'/parameters',('activity','factor') if model=='activity_factor' else ('activity','net_calorific_value','factor'))
                activity=r.q(q['activity'],p+'/parameters/activity',ACTIVITY_UNITS,0,effective_not_after=row['period_end']);activityunit=q['activity']['unit']
                f_unit=q['factor'].get('unit') if type(q.get('factor'))is dict else None
                if type(f_unit)is not str or f_unit.count('/')!=1:fail(p,'factor_mass_per_activity_unit')
                numerator,denominator=f_unit.split('/')
                if numerator not in MASS or denominator!=('TJ' if model=='combustion_energy' else activityunit):fail(p,'factor_unit_dimensions')
                factor=r.q(q['factor'],p+'/parameters/factor',(f_unit,),0,effective_not_after=basis['selection_date']);energy=activity
                if model=='combustion_energy':
                    if activityunit not in ('kg','t','m3','L'):fail(p,'fuel_quantity_unit')
                    energy*=r.q(q['net_calorific_value'],p+'/parameters/net_calorific_value',('TJ/'+activityunit,),F('1e-100'),effective_not_after=basis['selection_date'])
                mass=energy*factor*MASS[numerator]
            oxidation=choice(row.get('oxidation_mode'),p+'/oxidation_mode',('included_in_factor','separate_multiplier','not_applicable'))
            if oxidation=='separate_multiplier':
                if row['gas']!='CO2' or flow!='emission' or model=='measured_mass':fail(p,'oxidation_not_applicable_to_selected_gas_model')
                mass*=r.q(row.get('oxidation'),p+'/oxidation',('ratio',),0,1,effective_not_after=basis['selection_date'])
            elif 'oxidation'in row:fail(p,'oxidation_double_application')
            if model=='measured_mass' and oxidation!='not_applicable':fail(p,'measured_mass_no_oxidation')
        if boundary['consolidation']=='equity_share':attribution=r.q(row.get('attribution'),p+'/attribution',('ratio',),0,1,effective_not_after=row['period_end'])
        elif 'attribution'in row:fail(p,'attribution_only_for_selected_equity_share')
        else:attribution=F(1)
        attributed=None if aggregate else mass*attribution;co2e=aggregate_amount*attribution if aggregate else attributed*selected_gwp
        key=(row['activity_id'],row['site_id'],scope,flow)
        for a,b,old_aggregate,gas in seen_activity.get(key,[]):
            if rs<=b and a<=re_ and (aggregate or old_aggregate or gas==row.get('gas')):fail(p,'overlapping_aggregate_or_same_gas_activity_scope_period')
        seen_activity.setdefault(key,[]).append((rs,re_,aggregate,row.get('gas')))
        separate_kind='removal' if flow=='removal' else 'biogenic_CO2' if not aggregate and framework=='GHGP_corporate_selected_gross' and row['gas']=='CO2' and origin=='biogenic' else None
        known=record_basis['metadata_status']=='provided'
        groupkey=('known',record_basis['set_id'],record_basis['horizon_years']) if known else ('unknown',row['id'],m['id'],record_basis['basis']['source_reference'])
        group=basis_groups.setdefault(groupkey,dict(basis_group_id='basis_'+str(len(basis_groups)),set_id=record_basis['set_id'],horizon_years=record_basis['horizon_years'],metadata_status=record_basis['metadata_status'],source_anchors=[],source_record_ids=[],scope_totals_tCO2e={},separate_fluxes_tCO2e={}))
        group['source_record_ids'].append(row['id']);anchor=dict(method_id=m['id'],source_reference=record_basis['basis']['source_reference'],document_identity=record_basis['basis']['document_identity'],edition=record_basis['basis']['edition'])
        if anchor not in group['source_anchors']:group['source_anchors'].append(anchor)
        if separate_kind:separate[separate_kind]=separate.get(separate_kind,F(0))+co2e
        else:
            if not aggregate:
                bygas=gas_totals.setdefault(scope,{});totals=bygas.setdefault(row['gas'],{'mass_t_gas':F(0),'co2e_tonnes':F(0)})
                totals['mass_t_gas']+=attributed;totals['co2e_tonnes']+=co2e
        bucket=group['separate_fluxes_tCO2e'] if separate_kind else group['scope_totals_tCO2e'];bucketkey=separate_kind or scope;bucket[bucketkey]=bucket.get(bucketkey,F(0))+co2e
        reviews.append(dict(provided=deepcopy(row),model=model,gross_mass_t_gas=mass,attributed_mass_t_gas=attributed,selected_GWP100=selected_gwp,co2e_tonnes=co2e,unit='tCO2e',reporting_bucket=separate_kind or scope,co2e_basis_metadata=record_basis,gas_disaggregation_status='gas_disaggregation_not_supplied' if aggregate else 'gas_mass_supplied',classifications_semantically_established=False))
    unique([x['provided'] for x in reviews],'/records')
    exclusions=[r.record(x,'/exclusions/'+str(i)) for i,x in enumerate(rows(data.get('exclusions',[]),'/exclusions',8))];unique(exclusions,'/exclusions')
    quality=[r.record(x,'/quality_controls/'+str(i)) for i,x in enumerate(rows(data.get('quality_controls',[]),'/quality_controls',8))];unique(quality,'/quality_controls')
    if not exclusions:r.gaps.append({'kind':'exclusion_completeness_not_established'})
    if not quality:r.gaps.append({'kind':'data_quality_controls_not_supplied'})
    r.gaps.append({'kind':'inventory_completeness_and_uncertainty_not_established'})
    if any(s in seen_scopes for s in ('scope2_location','scope2_market')):r.gaps.append({'kind':'scope2_instrument_quality_and_factor_applicability_not_established'})
    if aggregate_count:r.gaps.append({'kind':'aggregate_CO2e_gas_disaggregation_not_supplied'})
    single_known_basis=len(basis_groups)==1 and next(iter(basis_groups.values()))['metadata_status']=='provided'
    horizon_not_100=single_known_basis and next(iter(basis_groups.values()))['horizon_years']!=100
    compatible=single_known_basis and not horizon_not_100
    scope_totals=deepcopy(next(iter(basis_groups.values()))['scope_totals_tCO2e']) if compatible else None
    summary_status='combined_on_supplied_basis_identifiers' if compatible else 'not_combined_horizon_not_100_for_selected_summary' if horizon_not_100 else 'not_combined_incompatible_or_unknown_basis'
    if not compatible:r.gaps.append({'kind':'scope_totals_horizon_not_100_for_selected_summary' if horizon_not_100 else 'scope_totals_not_combined_incompatible_or_unknown_CO2e_basis'})
    # No zero is inserted for an absent scope. Location/market representations
    # remain distinct alternatives; no total adds them together.
    return dict(organization=data['organization'],reporting_year=data['reporting_year'],period_start=data['period_start'],period_end=data['period_end'],framework=framework,boundary=deepcopy(boundary),methods=methodreviews,gwp=gwp_display,source_reviews=reviews,gas_totals_by_scope=gas_totals,scope_totals_tCO2e=scope_totals,scope_totals_status=summary_status,scope_totals_by_basis=list(basis_groups.values()),gas_disaggregation_status='provided_for_all_selected_records' if not aggregate_count else 'partial_gas_disaggregation' if aggregate_count<len(reviews) else 'gas_disaggregation_not_supplied',separate_fluxes_tCO2e=separate,RU_direct_gross_candidate_tCO2e=scope_totals.get('RU_direct') if framework=='RU_direct_draft' and scope_totals is not None else None,corporate_aggregate_tCO2e=None,corporate_aggregate_status='scopes_reported_separately_no_dual_scope2_sum',eligibility_review=eligibility(data.get('eligibility_review'),'/eligibility_review',r),deadline=deadline(data.get('deadline'),'/deadline',r),exclusion_reviews=exclusions,quality_reviews=quality,scope='selected_source_arithmetic_not_official_inventory_or_full_method371')

def economics(v,p,r):
    if v is None:return None
    obj(v,p,('currency','discount_rate','cashflows','irr_mode','basis'))
    currency=choice(v['currency'],p+'/currency',('RUB','USD','EUR','CNY'));basis=r.basis(v['basis'],p+'/basis',('project_economics',))
    rate=r.q(v['discount_rate'],p+'/discount_rate',('ratio',),F('-0.99'),10,effective_not_after=basis['selection_date'])
    mode=choice(v['irr_mode'],p+'/irr_mode',('not_requested','conventional_unique_investment'))
    flows={}
    for i,row in enumerate(rows(v['cashflows'],p+'/cashflows',24,1)):
        q=p+'/cashflows/'+str(i);obj(row,q,('id','period','amount','kind','source_reference','excerpt'))
        text(row['id'],q+'/id',200);choice(row['kind'],q+'/kind',('observed_record','provided_projection'));r.ref(row,q);r.literal(row,q)
        period=int(r.q(row['period'],q+'/period',('year_index',),0,50,True));amount=r.q(row['amount'],q+'/amount',(currency,))
        flows[period]=flows.get(period,F(0))+amount
    unique(v['cashflows'],p+'/cashflows')
    npv=sum((amount/(1+rate)**period for period,amount in flows.items()),F(0))
    irr=None;status='not_requested';interval=None
    nonzero=[(t,x) for t,x in sorted(flows.items()) if x]
    if mode!='not_requested':
        if len({1 if x>0 else -1 for _,x in nonzero})<2:status='undefined_no_sign_change'
        elif flows.get(0,F(0))>=0 or any(x<0 for t,x in flows.items() if t>0):status='unsupported_nonconventional_cashflows'
        else:
            def value(rate):return sum((amount/(1+rate)**period for period,amount in flows.items()),F(0))
            low,high=F('-0.9999'),F(1024);a,b=value(low),value(high)
            if a<0 or b>0:status='unique_root_outside_fixed_search_interval'
            elif not a:irr=low;status='computed_unique_conventional';interval=[low,low]
            elif not b:irr=high;status='computed_unique_conventional';interval=[high,high]
            else:
                for _ in range(160):
                    mid=(low+high)/2;y=value(mid)
                    if not y:low=high=mid;break
                    if y>0:low=mid
                    else:high=mid
                irr=(low+high)/2;status='computed_unique_conventional';interval=[low,high]
    return dict(provided=deepcopy(v),basis=basis,currency=currency,npv=npv,discount_rate=rate,aggregated_period_cashflows=[dict(period=t,amount=x) for t,x in sorted(flows.items())],irr=irr,irr_status=status,irr_interval=interval,irr_period_unit='year',economics_does_not_establish_additionality=True,carbon_unit_revenues_or_prices_not_generated=True)

def project(data,r):
    obj(data,'data',('as_of','jurisdiction','project'),('quantification','additionality','double_counting','monitoring','assurance_records','risks','economics'))
    info=obj(data['project'],'/project',('id','description','project_type','site','start_date','end_date','baseline_description','project_scenario','boundary_description'))
    for k in ('id','description','project_type','site','baseline_description','project_scenario','boundary_description'):text(info[k],'/project/'+k,6000)
    begin=iso(info['start_date'],'/project/start_date');end=iso(info['end_date'],'/project/end_date')
    if begin>end:fail('/project','reversed_period')
    quant=data.get('quantification');periods=[];quantreview=None;total=None
    if quant is not None:
        obj(quant,'/quantification',('basis','perimeter_id','gwp_set_id','baseline_procedure','periods'))
        basis=r.basis(quant['basis'],'/quantification/basis',('project_quantification',))
        for k in ('perimeter_id','gwp_set_id','baseline_procedure'):text(quant[k],'/quantification/'+k,500)
        prior=[];total=F(0)
        for i,row in enumerate(rows(quant['periods'],'/quantification/periods',12,1)):
            p='/quantification/periods/'+str(i);obj(row,p,('id','start_date','end_date','components','leakage','reversal_mode','source_reference','excerpt'),('baseline_emissions','project_emissions','baseline_removals','project_removals','reversal'))
            text(row['id'],p+'/id',200);s=iso(row['start_date'],p+'/start_date');e=iso(row['end_date'],p+'/end_date')
            if not begin<=s<=e<=end or any(s<=b and a<=e for a,b in prior):fail(p,'overlapping_or_outside_project_period')
            prior.append((s,e));r.ref(row,p);r.literal(row,p)
            components=rows(row['components'],p+'/components',2,1)
            if len(set(components))!=len(components) or any(x not in ('emissions','removals') for x in components):fail(p,'quantified_components')
            values={};benefit=F(0)
            for kind in ('emissions','removals'):
                if kind not in components:
                    if 'baseline_'+kind in row or 'project_'+kind in row:fail(p,'unselected_component_value')
                    continue
                for side in ('baseline','project'):values[side+'_'+kind]=r.q(row.get(side+'_'+kind),p+'/'+side+'_'+kind,('tCO2e',),0)
                benefit+=(values['baseline_'+kind]-values['project_'+kind])*(1 if kind=='emissions' else -1)
            leakage=r.q(row['leakage'],p+'/leakage',('tCO2e',),0)
            mode=choice(row['reversal_mode'],p+'/reversal_mode',('not_applicable','included_in_project_emissions','separate_adjustment'))
            reversal=None
            if mode=='separate_adjustment':
                if 'removals'not in components:fail(p,'reversal_adjustment_requires_removal_component')
                reversal=r.q(row.get('reversal'),p+'/reversal',('tCO2e',),0);benefit-=reversal
            elif 'reversal'in row:fail(p,'reversal_double_application')
            if mode=='included_in_project_emissions' and 'emissions'not in components:fail(p,'included_reversal_requires_emissions_component')
            net=benefit-leakage;total+=net
            periods.append(dict(provided=deepcopy(row),component_values=values,leakage=leakage,separate_reversal_adjustment=reversal,net_benefit_tCO2e=net,unit='tCO2e',creditable_units=None,creditable_status='not_determined_by_arithmetic'))
        unique([x['provided'] for x in periods],'/quantification/periods')
        quantreview=dict(basis=basis,perimeter_id=quant['perimeter_id'],gwp_set_id=quant['gwp_set_id'],baseline_procedure=quant['baseline_procedure'],period_reviews=periods,total_net_benefit_tCO2e=total,scope='selected_net_flux_components_only_no_automatic_baseline_or_credit_eligibility')
    else:r.gaps.append({'kind':'project_quantification_not_supplied'})
    additional=[]
    for i,v in enumerate(rows(data.get('additionality',[]),'/additionality',8)):
        p='/additionality/'+str(i);obj(v,p,('id','criterion','basis','evidence'))
        text(v['id'],p+'/id',200);text(v['criterion'],p+'/criterion')
        additional.append(dict(id=v['id'],criterion=v['criterion'],basis=r.basis(v['basis'],p+'/basis',('additionality_criterion',)),evidence=r.record(v['evidence'],p+'/evidence'),additionality_established=False))
    unique(additional,'/additionality')
    if not additional:r.gaps.append({'kind':'additionality_evidence_not_supplied'})
    claims=[];matches=[]
    for i,v in enumerate(rows(data.get('double_counting',[]),'/double_counting',10)):
        p='/double_counting/'+str(i);obj(v,p,('id','registry','claim_id','perimeter_id','start_date','end_date','state','source_reference','excerpt'))
        for k in ('id','registry','claim_id','perimeter_id'):text(v[k],p+'/'+k,200)
        choice(v['state'],p+'/state',('provided','unknown'));s=iso(v['start_date'],p+'/start_date');e=iso(v['end_date'],p+'/end_date')
        if s>e:fail(p,'reversed_claim_period')
        r.ref(v,p);r.literal(v,p)
        for previous in claims:
            if (previous['registry'],previous['claim_id'])==(v['registry'],v['claim_id']):matches.append(dict(first_id=previous['id'],second_id=v['id'],kind='duplicate_supplied_registry_claim_identity'))
            elif previous['perimeter_id']==v['perimeter_id'] and previous['start_date']<=v['end_date'] and v['start_date']<=previous['end_date']:matches.append(dict(first_id=previous['id'],second_id=v['id'],kind='overlapping_supplied_claim_perimeter_and_period'))
        claims.append(deepcopy(v))
    unique(claims,'/double_counting')
    if not claims:r.gaps.append({'kind':'double_counting_records_not_supplied'})
    monitoring=[]
    for i,v in enumerate(rows(data.get('monitoring',[]),'/monitoring',10)):
        p='/monitoring/'+str(i);obj(v,p,('id','parameter','unit','method','frequency','owner','records'),('quality_record',))
        for k in ('id','parameter','unit','method','frequency','owner'):text(v[k],p+'/'+k)
        measurements=[]
        for j,a in enumerate(rows(v['records'],p+'/records',8)):
            q=p+'/records/'+str(j);obj(a,q,('id','date','quantity','source_reference','excerpt'));text(a['id'],q+'/id',200);iso(a['date'],q+'/date',r.cutoff);r.q(a['quantity'],q+'/quantity',(v['unit'],),effective_not_after=a['date']);r.ref(a,q);r.literal(a,q);measurements.append(deepcopy(a))
        unique(measurements,p+'/records')
        if not measurements:r.gaps.append({'kind':'monitoring_measurements_not_supplied','id':v['id']})
        monitoring.append(dict(deepcopy(v),records=measurements,quality_record=r.record(v['quality_record'],p+'/quality_record') if 'quality_record'in v else None,measurement_or_calibration_performed=False))
    unique(monitoring,'/monitoring')
    if not monitoring:r.gaps.append({'kind':'monitoring_plan_not_supplied'})
    assurance=[r.record(v,'/assurance_records/'+str(i),('validation','verification','registry_entry','methodology_status')) for i,v in enumerate(rows(data.get('assurance_records',[]),'/assurance_records',8))];unique(assurance,'/assurance_records')
    risks=[]
    for i,v in enumerate(rows(data.get('risks',[]),'/risks',8)):
        p='/risks/'+str(i);obj(v,p,('id','description','proposed_mitigation','owner','review_date'))
        for k in ('id','description','proposed_mitigation','owner'):text(v[k],p+'/'+k)
        iso(v['review_date'],p+'/review_date');risks.append(dict(deepcopy(v),mitigation_performed=False))
    unique(risks,'/risks')
    r.gaps.append({'kind':'project_baseline_methodology_additionality_and_credit_eligibility_not_established'})
    return dict(project=deepcopy(info),quantification=quantreview,additionality_reviews=additional,double_counting_review=dict(provided_claims=claims,supplied_record_matches=matches,global_registry_search_performed=False,double_counting_absence_established=False),monitoring=monitoring,assurance_record_reviews=assurance,risk_reviews=risks,economics=economics(data.get('economics'),'/economics',r),carbon_units_quantity=None,carbon_units_status='not_determined_no_issuance_promise',validation_or_verification_performed=False,registry_submission_performed=False)

def _run(function,data):
    if type(function)is not str or function not in FUNCTIONS:fail('function','unsupported')
    if type(data)is not dict:fail('data','object')
    bounded(data);r=Read(data)
    output=(inventory if function=='ghg_inventory' else project)(data,r)
    output.update(as_of=r.cutoff,jurisdiction='RU',analysis_only=True,source_semantics_established=False,current_normative_chain_established=False,signature_applied=False,submission_performed=False,registry_accessed=False,official_inventory_or_project_conclusion_made=False,evidence_gaps=r.gaps)
    if len(r.units)+len(r.texts)>700:fail('data','numeric_literal_budget')
    return serial(output),r

def execute(function,data):
    try:return _run(function,deepcopy(data))[0]
    except (KeyError,TypeError,AttributeError,IndexError,DecimalException,OverflowError,ZeroDivisionError) as e:raise ValueError('emissions_project_invalid_nested_input') from e
def input_units(function,data):
    try:return _run(function,deepcopy(data))[1].units
    except (KeyError,TypeError,AttributeError,IndexError,DecimalException,OverflowError,ZeroDivisionError) as e:raise ValueError('emissions_project_invalid_nested_input') from e
def selected_texts(function,data):
    try:return _run(function,deepcopy(data))[1].texts
    except (KeyError,TypeError,AttributeError,IndexError,DecimalException,OverflowError,ZeroDivisionError) as e:raise ValueError('emissions_project_invalid_nested_input') from e

"""Pure local physicist planning and review, with explicit evidence boundaries.

No apparatus control, background task, network, account, signing or submission.
Decimal results are unrounded strings; quoted occurrence never establishes truth.
"""
import copy
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, DecimalException, Context, localcontext
from functools import wraps
from urllib.parse import urlsplit

FUNCTIONS = ('experiment_setup','radiation_safety','lab_hazards','facility_time','publication','rd_reports')
RULE_KEYS = {'source_reference','edition','publication_date','effective_date','scope','text'}
OBS_STATES = {'provided','missing','unknown','not_applicable'}
HAZARD_FIELDS = {
 'laser': ('laser_class','wavelength','power','pulse_regime','beam_path','eye_protection_basis'),
 'cryo': ('cryogen','volume','room_volume','ventilation','oxygen_monitor','relief_path'),
 'high_voltage': ('voltage','stored_energy','isolation','discharge_procedure','personnel_role'),
 'pressure': ('pressure','volume','medium','temperature','inspection_record','relief_device')}


def obj(v, required=(), optional=(), label='object'):
    if type(v) is not dict or not set(required)<=set(v) or set(v)-set(required)-set(optional):
        raise ValueError(label+'_fields')
    return v


def rows(v, label='rows', minimum=0, maximum=100):
    if type(v) is not list or not minimum<=len(v)<=maximum: raise ValueError(label+'_bounded_list_required')
    return v


def text(v, label='text', maximum=10000):
    if type(v) is not str or not v.strip() or len(v)>maximum: raise ValueError(label+'_required')
    if any(ord(c)<32 and c not in '\n\r\t' for c in v): raise ValueError(label+'_control_character')
    return v


def ref(v): return text(v,'source_reference',200)


def day(v, label='date'):
    if type(v) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',v): raise ValueError(label+'_iso_date_required')
    try: return date.fromisoformat(v)
    except ValueError: raise ValueError(label+'_invalid') from None


def past(v,asof,label='date'):
    d=day(v,label)
    if d>asof: raise ValueError(label+'_after_as_of')
    return d


def number(v,label='number'):
    if type(v) is not str or len(v)>160 or not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',v):
        raise ValueError(label+'_exact_decimal_string_required')
    n=Decimal(v)
    if not n.is_finite() or abs(n.as_tuple().exponent)>140 or len(n.as_tuple().digits)>40 or abs(n.adjusted())>100:
        raise ValueError(label+'_bounded_decimal_required')
    return n


def count(v,label='count',low=0,high=10000):
    n=number(v,label)
    if n!=n.to_integral_value() or not low<=n<=high: raise ValueError(label+'_integer_range')
    return int(n)


def quantity(v,unit=None,label='quantity'):
    obj(v,('value','unit'),('source_reference',),label)
    text(v['unit'],'unit',80)
    if unit is not None and v['unit']!=unit: raise ValueError(label+'_unit_mismatch')
    if v.get('source_reference') is not None: ref(v['source_reference'])
    return number(v['value'],label)


def interval(v,label='range'):
    obj(v,('lower','upper','unit'),('source_reference',),label)
    text(v['unit'],'unit',80)
    lo,hi=number(v['lower']),number(v['upper'])
    if lo>hi: raise ValueError(label+'_lower_above_upper')
    if v.get('source_reference') is not None: ref(v['source_reference'])
    return lo,hi,v['unit']


def bounded(v,depth=0,budget=None):
    if budget is None: budget=[0]
    budget[0]+=1
    if depth>24 or budget[0]>18000: raise ValueError('input_structure_limit')
    if type(v) is dict:
        if len(v)>100: raise ValueError('object_size_limit')
        for k,item in v.items():
            if type(k) is not str: raise ValueError('string_keys_required')
            if k.endswith(('_verified','_approved','_confirmed','_signed')) or k in {
                'verified','approved','confirmed','signed','authorized','clearance','dual_use',
                'actual_success_at','last_verified_at','host_context','startup_allowed','safe','compliant',
                'classification_decision','publication_cleared','instrument_approved'}:
                raise ValueError('reserved_authority_field:'+k)
            bounded(item,depth+1,budget)
    elif type(v) is list:
        if len(v)>500: raise ValueError('list_size_limit')
        for item in v: bounded(item,depth+1,budget)
    elif type(v) is str:
        if len(v)>160000: raise ValueError('text_size_limit')
    elif v is not None and type(v) is not bool: raise ValueError('decimal_strings_required')


def base(data,required,optional=()):
    bounded(data);obj(data,('as_of','jurisdiction',*required),optional,'scenario')
    if data['jurisdiction']!='RU': raise ValueError('jurisdiction_RU_required')
    return day(data['as_of'],'as_of')


def quote(row,source_text=None):
    ref(row['source_reference']);text(row['excerpt'],'excerpt',20000)
    if source_text is not None and row['excerpt'] not in source_text: raise ValueError('excerpt_not_in_selected_text')


def observation(v,asof):
    obj(v,('state',),('source_reference','excerpt','observation_date','valid_to','scope'),'observation')
    if v['state'] not in OBS_STATES: raise ValueError('unsupported_observation_state')
    if v['state']=='provided' or 'excerpt' in v or 'source_reference' in v: quote(v)
    if v.get('observation_date') is not None: past(v['observation_date'],asof,'observation_date')
    if v.get('valid_to') is not None: day(v['valid_to'],'valid_to')
    if v.get('scope') is not None: text(v['scope'],'observation_scope')
    ended=v.get('valid_to') is not None and day(v['valid_to'])<asof
    conflict=v.get('valid_to') is not None and v.get('observation_date') is not None and day(v['observation_date'])>day(v['valid_to'])
    return dict(copy.deepcopy(v),semantic_status='not_assessed',provided_period_ended=ended,observation_after_valid_to=conflict)


def rule(v,asof,event,scope):
    obj(v,RULE_KEYS,('not_after','role'),'selected_rule')
    ref(v['source_reference']);text(v['edition'],'edition');text(v['scope'],'rule_scope');text(v['text'],'rule_text',160000)
    if v.get('role') is not None:text(v['role'],'rule_role')
    past(v['publication_date'],asof,'publication_date')
    begin=day(v['effective_date'],'effective_date')
    if begin>event or v['scope']!=scope: raise ValueError('rule_event_date_or_scope_mismatch')
    if v.get('not_after') is not None:
        end=day(v['not_after'],'not_after')
        if end<begin or event>end: raise ValueError('rule_event_outside_provided_period')
    return {k:copy.deepcopy(val) for k,val in v.items() if k!='text'}


def selected_rules(values,asof,event,scope):
    result=[];ids=set()
    for value in rows(values,'selected_rules',maximum=20):
        meta=rule(value,asof,event,scope)
        if meta['source_reference'] in ids: raise ValueError('duplicate_selected_rule_reference')
        ids.add(meta['source_reference']);result.append(meta)
    return result


def result(function,data,**values):
    return dict(function=function,as_of=data['as_of'],jurisdiction='RU',analysis_only=True,
                assisted_draft=True,private=True,external_network_used=False,equipment_control_performed=False,
                startup_authorized=False,signature_applied=False,submission_performed=False,
                export_classification_performed=False,source_semantics_verified=False,
                current_legal_applicability_verified=False,**values)


def unique(rows_,key='id'):
    seen=set()
    for row in rows_:
        identity=text(row[key],key,200)
        if identity in seen: raise ValueError('duplicate_'+key)
        seen.add(identity)


def experiment_setup(data):
    asof=base(data,('objective','measurand','scope','proposed_method','instruments'),
              ('measurement_plan','journal','method_compare','heat_balance','processing','accuracy_basis'))
    for k in ('objective','measurand','scope','proposed_method'): text(data[k],k)
    instruments=[];gaps=[]
    for item in rows(data['instruments'],'instruments',maximum=50):
        obj(item,('id','name'),('serial_number','range','accuracy_description','verification','calibration'),'instrument')
        text(item['name'],'instrument_name');ref(item['id'])
        copied=copy.deepcopy(item);local=[]
        for k in ('serial_number','accuracy_description'):
            if item.get(k) is not None: text(item[k],k)
            else: local.append(k)
        if item.get('range') is not None: interval(item['range'],'instrument_range')
        else: local.append('range')
        for kind in ('verification','calibration'):
            if item.get(kind) is not None:
                copied[kind]=observation(item[kind],asof)
                if item[kind]['state']!='provided': local.append(kind)
                elif item[kind].get('valid_to') is not None and day(item[kind]['valid_to'])<asof: local.append(kind+'_provided_period_ended')
            else: local.append(kind)
        copied['evidence_gaps']=local;copied['metrological_status']='not_assessed';instruments.append(copied)
    unique(instruments)
    if not instruments: gaps.append('instruments')
    plan=data.get('measurement_plan')
    if plan is not None:
        obj(plan,(),('range','repeats','control_points','background','conditions'),'measurement_plan')
        if plan.get('range') is not None: interval(plan['range'])
        if plan.get('repeats') is not None: count(plan['repeats'],'repeats',1)
        for value in rows(plan.get('control_points',[]),'control_points',maximum=50): quantity(value)
        for k in ('background','conditions'):
            if plan.get(k) is not None: text(plan[k],k)
        gaps.extend('measurement_plan.'+k for k in ('range','repeats','control_points','background','conditions') if not plan.get(k))
    else: gaps.append('measurement_plan')
    journal=[]
    for row in rows(data.get('journal',[]),'journal',maximum=100):
        obj(row,('date','sample','operator','measurement','source_reference'),('settings','notes','time','utc_offset'),'journal_row')
        past(row['date'],asof,'journal_date');ref(row['source_reference'])
        has_time='time' in row;has_offset='utc_offset' in row
        if has_time!=has_offset:raise ValueError('journal_time_and_offset_required_together')
        if has_time:
            if type(row['time']) is not str or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d',row['time']):
                raise ValueError('journal_time_HH_MM_SS_required')
            offset=row['utc_offset']
            if type(offset) is not str or not re.fullmatch(r'[+-](?:0\d|1[0-4]):[0-5]\d',offset) or offset[1:3]=='14' and offset[4:]!='00':
                raise ValueError('journal_explicit_utc_offset_within_14_hours_required')
        else:gaps.append('journal.'+str(len(journal))+'.time_and_offset')
        for k in ('sample','operator'): text(row[k],k)
        quantity(row['measurement'])
        for k in ('settings','notes'):
            if row.get(k) is not None: text(row[k],k)
        journal.append(copy.deepcopy(row))
    comparison=None
    if data.get('method_compare') is not None:
        c=data['method_compare'];obj(c,('pairs','unit','normal_assumption','limit_multiplier','source_reference'),label='method_compare')
        if c['normal_assumption']!='normal_differences_assumed_not_tested': raise ValueError('explicit_normal_difference_assumption_required')
        if number(c['limit_multiplier'])!=Decimal('1.96'): raise ValueError('supported_limit_multiplier_1_96_required')
        text(c['unit'],'comparison_unit',80);ref(c['source_reference']);diffs=[];means=[]
        for pair in rows(c['pairs'],'paired_measurements',2,200):
            obj(pair,('a','b'),label='measurement_pair');a,b=number(pair['a']),number(pair['b']);diffs.append(a-b);means.append((a+b)/2)
        bias=sum(diffs,Decimal(0))/len(diffs)
        sd=(sum(((d-bias)**2 for d in diffs),Decimal(0))/(len(diffs)-1)).sqrt()
        comparison=dict(n=len(diffs),unit=c['unit'],bias=str(bias),sample_sd=str(sd),loa_low=str(bias-Decimal('1.96')*sd),
                        loa_high=str(bias+Decimal('1.96')*sd),differences=[str(d) for d in diffs],pair_means=[str(m) for m in means],
                        normal_assumption=c['normal_assumption'],source_reference=c['source_reference'],agreement_decision='not_assessed',
                        sampling_assumption='independent_homoscedastic_pairs_assumed_not_tested',limits_are_not_confidence_intervals=True)
    heat=None
    if data.get('heat_balance') is not None:
        h=data['heat_balance'];obj(h,('model','mass','specific_heat','delta_temperature','energy_input','energy_loss'),label='heat_balance')
        if h['model']!='constant_cp_no_phase_change': raise ValueError('supported_heat_model_required')
        m=quantity(h['mass'],'kg');cp=quantity(h['specific_heat'],'J/(kg*K)');dt=quantity(h['delta_temperature'],'K')
        incoming=quantity(h['energy_input'],'J');loss=quantity(h['energy_loss'],'J')
        if m<=0 or cp<=0 or loss<0: raise ValueError('heat_mass_cp_loss_range')
        expected=m*cp*dt;net=incoming-loss
        heat=dict(unit='J',expected_energy=str(expected),net_input_energy=str(net),signed_residual=str(net-expected),
                  model=h['model'],formula='m*c*delta_T; residual=(energy_input-energy_loss)-m*c*delta_T')
    for k in ('processing','accuracy_basis'):
        if data.get(k) is not None: text(data[k],k)
        else: gaps.append(k)
    return result('experiment_setup',data,draft_method={k:data[k] for k in ('objective','measurand','scope','proposed_method')},
                  instruments=instruments,measurement_plan=copy.deepcopy(plan),journal_rows=journal,method_comparison=comparison,
                  heat_balance=heat,processing=data.get('processing'),accuracy_basis=data.get('accuracy_basis'),evidence_gaps=gaps,
                  journal_template=['date','time','utc_offset','settings','sample','measurement','unit','operator','notes'],
                  notices=['draft_for_responsible_review','metrology_not_checked_online','optional_calculations_not_required_for_plan'])


def radiation_safety(data):
    asof=base(data,('scope','event_date','source','selected_rules','documents'),('proposed_work','dose'))
    text(data['scope'],'scope');event=past(data['event_date'],asof,'event_date')
    source=data['source'];obj(source,('type','room','personnel_role'),('parameters',),'radiation_source')
    if source['type'] not in ('sealed_point','sealed_extended','open_radionuclide','xray','accelerator','other'): raise ValueError('unsupported_radiation_source_type')
    for k in ('room','personnel_role'):text(source[k],k)
    if source.get('parameters') is not None:text(source['parameters'],'source_parameters')
    metas=selected_rules(data['selected_rules'],asof,event,data['scope']);documents=[];gaps=[];names=set()
    for row in rows(data['documents'],'documents',maximum=50):
        obj(row,('id','role','record'),label='safety_document');ref(row['id']);text(row['role'],'document_role')
        observed=observation(row['record'],asof)
        documents.append(dict(id=row['id'],role=row['role'],record=observed));names.add(row['id'])
        if row['record']['state']!='provided':gaps.append(row['id'])
        if observed['provided_period_ended']:gaps.append(row['id']+'.provided_period_ended')
        if observed['observation_after_valid_to']:gaps.append(row['id']+'.observation_after_valid_to')
        if row['record'].get('scope') is not None and row['record']['scope']!=data['scope']:gaps.append(row['id']+'.scope')
    unique(documents)
    gaps.extend(k for k in ('organization_permissions','personnel_training','dosimetry','source_inventory','storage','emergency_plan','radiation_control') if k not in names)
    if not metas:gaps.append('selected_rules')
    dose=None
    if data.get('dose') is not None:
        d=data['dose'];obj(d,('mode','rate','duration','quantity_kind','source_reference'),('reference_distance','target_distance','point_source_basis'),'dose')
        if d['quantity_kind'] not in ('ambient_dose_equivalent','personal_dose_equivalent','effective_dose_model'):
            raise ValueError('explicit_dose_quantity_kind_required')
        rate=quantity(d['rate']);duration=quantity(d['duration']);ref(d['source_reference'])
        factors={'Sv/h':(Decimal(1),Decimal(3600)),'mSv/h':(Decimal('0.001'),Decimal(3600)),
                 'uSv/h':(Decimal('0.000001'),Decimal(3600)),'Sv/s':(Decimal(1),Decimal(1))}
        times={'h':Decimal(3600),'min':Decimal(60),'s':Decimal(1)}
        if d['rate']['unit'] not in factors or d['duration']['unit'] not in times:raise ValueError('dose_rate_or_duration_unit_unsupported')
        if rate<0 or duration<0:raise ValueError('dose_rate_duration_nonnegative_required')
        factor=Decimal(1)
        if d['mode']=='point_source_reference':
            if source['type']!='sealed_point':raise ValueError('inverse_square_requires_sealed_point_source')
            basis=d['point_source_basis'];obj(basis,('source_reference','excerpt'),label='point_source_basis');quote(basis)
            origin=quantity(d['reference_distance'],'m');target=quantity(d['target_distance'],'m')
            if origin<=0 or target<=0:raise ValueError('point_source_distance_positive_required')
            factor=(origin/target)**2
        elif d['mode']=='measured_at_location':
            if any(k in d for k in ('reference_distance','target_distance','point_source_basis')):raise ValueError('measured_rate_no_second_distance_correction')
        else:raise ValueError('explicit_dose_mode_required')
        rate_scale,rate_seconds=factors[d['rate']['unit']]
        value=rate*rate_scale*duration*times[d['duration']['unit']]*factor/rate_seconds
        dose=dict(value=str(value),unit='Sv',quantity_kind=d['quantity_kind'],geometry_factor=str(factor),mode=d['mode'],
                  source_reference=d['source_reference'],formula='rate*duration' if d['mode']=='measured_at_location' else 'reference_rate*duration*(reference_distance/target_distance)^2',
                  safety_decision='not_assessed',shielding_not_modelled=True)
    if data.get('proposed_work') is not None:text(data['proposed_work'],'proposed_work')
    return result('radiation_safety',data,scope=data['scope'],event_date=data['event_date'],source=copy.deepcopy(source),
                  selected_rule_metadata=metas,document_inventory=documents,evidence_gaps=gaps,proposed_work=data.get('proposed_work'),
                  dose_estimate=dose,notices=['preliminary_dose_not_safety_decision','no_startup_or_interlock_authorization'])


def lab_hazards(data):
    asof=base(data,('scope','hazards'),('risk_matrix',));text(data['scope'],'scope')
    matrix=data.get('risk_matrix');levels=None;threshold=None
    if matrix is not None:
        obj(matrix,('selected_rule','severity_levels','likelihood_levels','review_threshold','formula'),label='risk_matrix')
        if matrix['formula']!='severity_times_likelihood':raise ValueError('explicit_multiplicative_risk_formula_required')
        rule(matrix['selected_rule'],asof,asof,data['scope'])
        levels=[]
        for key in ('severity_levels','likelihood_levels'):
            values=[number(v,key) for v in rows(matrix[key],key,1,20)]
            if len(set(values))!=len(values) or any(v<=0 for v in values):raise ValueError('risk_scale_distinct_positive_required')
            levels.append(set(values))
        threshold=number(matrix['review_threshold'],'review_threshold')
        if threshold<=0:raise ValueError('review_threshold_positive_required')
    reviews=[]
    for h in rows(data['hazards'],'hazards',1,50):
        obj(h,('id','type','parameters','observed_controls','proposed_controls'),('responsible','risk'),'hazard')
        ref(h['id'])
        if h['type'] not in HAZARD_FIELDS:raise ValueError('unsupported_hazard_type')
        obj(h['parameters'],(),HAZARD_FIELDS[h['type']],'hazard_parameters')
        gaps=[]
        quantitative={'wavelength':'nm','power':'W','volume':'m3','room_volume':'m3','voltage':'V','stored_energy':'J','pressure':'Pa','temperature':'K'}
        for k in HAZARD_FIELDS[h['type']]:
            if h['parameters'].get(k) is None:gaps.append(k);continue
            value=h['parameters'][k]
            if k in quantitative:
                numeric=quantity(value,quantitative[k],k)
                if numeric<0:raise ValueError('hazard_parameter_nonnegative_required')
            else:text(value,k)
        observed=[]
        for i,row in enumerate(rows(h['observed_controls'],'observed_controls',maximum=30)):
            obj(row,('control','record'),label='observed_control');text(row['control'],'control')
            rec=observation(row['record'],asof)
            observed.append(dict(control=row['control'],record=rec))
            if rec['state']!='provided':gaps.append('observed_controls.'+str(i)+'.'+rec['state'])
            if rec['provided_period_ended']:gaps.append('observed_controls.'+str(i)+'.provided_period_ended')
            if rec['observation_after_valid_to']:gaps.append('observed_controls.'+str(i)+'.observation_after_valid_to')
        proposed=[]
        for row in rows(h['proposed_controls'],'proposed_controls',maximum=30):
            obj(row,('action',),('basis_reference','owner','due_date'),'proposed_control');text(row['action'],'proposed_control')
            for k in ('basis_reference','owner'):
                if row.get(k) is not None:text(row[k],k)
            if row.get('due_date') is not None:day(row['due_date'],'due_date')
            proposed.append(dict(copy.deepcopy(row),status='proposed_not_observed'))
        if not observed:gaps.append('observed_controls')
        if not h.get('responsible'):gaps.append('responsible')
        else:text(h['responsible'],'responsible')
        score=None
        if h.get('risk') is not None:
            if matrix is None:raise ValueError('selected_risk_matrix_required')
            obj(h['risk'],('severity','likelihood'),label='risk');a,b=number(h['risk']['severity']),number(h['risk']['likelihood'])
            if a not in levels[0] or b not in levels[1]:raise ValueError('risk_value_outside_selected_scale')
            score=dict(value=str(a*b),unit='score',at_or_above_selected_review_threshold=a*b>=threshold,
                       threshold=str(threshold),source_reference=matrix['selected_rule']['source_reference'],acceptability='not_assessed')
        reviews.append(dict(id=h['id'],type=h['type'],parameters=copy.deepcopy(h['parameters']),observed_controls=observed,
                            proposed_controls=proposed,responsible=h.get('responsible'),evidence_gaps=gaps,risk_score=score))
    unique(reviews)
    return result('lab_hazards',data,scope=data['scope'],hazard_reviews=reviews,
                  selected_risk_matrix=copy.deepcopy(matrix),notices=['proposed_controls_are_not_observed_controls','no_startup_or_interlock_authorization','ppe_selection_requires_specialist'])


def url(v):
    text(v,'url',2000);p=urlsplit(v)
    if p.scheme!='https' or not p.hostname or p.username or p.password:raise ValueError('public_https_url_required')
    return p


def facility_time(data):
    asof=base(data,('task','scope','requirements','facilities'),('proposal','shift_budget'));text(data['task'],'task');text(data['scope'],'scope')
    requirements=rows(data['requirements'],'requirements',1,30)
    for r in requirements:obj(r,('id','range'),label='facility_requirement');ref(r['id']);interval(r['range'])
    unique(requirements);candidates=[]
    for f in rows(data['facilities'],'facilities',maximum=30):
        obj(f,('id','name','url','scope','snapshot_date','source_reference','capabilities'),('call',),'facility')
        for k in ('id','name','scope'):text(f[k],k)
        url(f['url']);ref(f['source_reference']);snapshot=past(f['snapshot_date'],asof,'snapshot_date');caps={}
        for c in rows(f['capabilities'],'capabilities',maximum=50):
            obj(c,('id','range','source_reference','excerpt'),label='capability');ref(c['id']);interval(c['range']);quote(c)
            if c['id'] in caps:raise ValueError('duplicate_capability_id')
            caps[c['id']]=c
        reviews=[];gaps=[]
        for r in requirements:
            c=caps.get(r['id']);state='missing_capability'
            if c is not None:
                lo,hi,u=interval(r['range']);clo,chi,cu=interval(c['range'])
                state='unit_mismatch' if u!=cu else ('range_covered' if clo<=lo<=hi<=chi else 'range_not_covered')
            if f['scope']!=data['scope']:state='scope_mismatch'
            if state!='range_covered':gaps.append(r['id'])
            reviews.append(dict(id=r['id'],status=state,requirement=copy.deepcopy(r['range']),capability=copy.deepcopy(c)))
        call=f.get('call');callreview=None
        if call is None:gaps.append('call')
        else:
            obj(call,('id','opens','deadline','scope','source_reference','excerpt'),label='facility_call');quote(call)
            text(call['id'],'call_id');text(call['scope'],'call_scope')
            opens,end=day(call['opens']),day(call['deadline'])
            if opens>end:raise ValueError('call_open_after_deadline')
            callreview=dict(copy.deepcopy(call),window_status='not_open' if asof<opens else ('past_deadline' if asof>end else 'within_supplied_dates'))
            if call['scope']!=data['scope']:gaps.append('call.scope')
        candidates.append(dict(id=f['id'],name=f['name'],url=f['url'],scope=f['scope'],snapshot_date=f['snapshot_date'],
                               snapshot_age_days=(asof-snapshot).days,capability_review=reviews,call=callreview,evidence_gaps=gaps,
                               availability='not_assessed',source_reference=f['source_reference']))
    unique(candidates);proposal=data.get('proposal');gaps=[]
    if not candidates:gaps.append('facilities')
    if proposal is None:gaps.append('proposal')
    else:
        obj(proposal,('scientific_case',),('preliminary_results','sample_safety','expected_outcomes','facility_id','call_id'),'proposal')
        text(proposal['scientific_case'],'scientific_case')
        for k in ('preliminary_results','expected_outcomes'):
            if proposal.get(k) is not None:text(proposal[k],k)
            else:gaps.append('proposal.'+k)
        if proposal.get('sample_safety') is not None:
            observation(proposal['sample_safety'],asof)
            if proposal['sample_safety']['state']!='provided':gaps.append('sample_safety')
        else:gaps.append('sample_safety')
        if proposal.get('facility_id') is not None:
            chosen=[c for c in candidates if c['id']==proposal['facility_id']]
            if not chosen:raise ValueError('proposal_facility_not_selected')
            if proposal.get('call_id') is not None and (chosen[0]['call'] is None or proposal['call_id']!=chosen[0]['call']['id']):raise ValueError('proposal_call_not_selected')
        else:
            gaps.append('proposal.facility_id')
            if proposal.get('call_id') is not None:raise ValueError('proposal_call_requires_facility')
    budget=data.get('shift_budget');budgetreview=None
    if budget is None:gaps.append('shift_budget')
    else:
        obj(budget,('requested','available','shifts'),label='shift_budget');requested=quantity(budget['requested']);available=quantity(budget['available'])
        if budget['requested']['unit']!=budget['available']['unit'] or requested<0 or available<0:raise ValueError('shift_budget_unit_or_sign')
        total=Decimal(0)
        for shift in rows(budget['shifts'],'shifts',1,100):
            obj(shift,('date','activity','duration'),label='shift');day(shift['date']);text(shift['activity'],'shift_activity');value=quantity(shift['duration'],budget['requested']['unit'])
            if value<0:raise ValueError('shift_duration_negative')
            total+=value
        budgetreview=dict(copy.deepcopy(budget),planned_total=str(total),request_minus_plan=str(requested-total),available_minus_request=str(available-requested))
    return result('facility_time',data,task=data['task'],scope=data['scope'],requirements=copy.deepcopy(requirements),candidate_reviews=candidates,
                  proposal=copy.deepcopy(proposal),shift_budget=budgetreview,evidence_gaps=gaps,notices=['capability_range_is_not_actual_availability','draft_not_submitted'])


def sourced_results(values,asof):
    output=[]
    for r in rows(values,'results',maximum=100):
        obj(r,('id','quantity','uncertainty','source_reference','excerpt'),('observation_date',),'scientific_result')
        ref(r['id']);quote(r);value=quantity(r['quantity']);unc=quantity(r['uncertainty'],r['quantity']['unit'])
        if unc<0:raise ValueError('uncertainty_nonnegative_required')
        if r.get('observation_date') is not None:past(r['observation_date'],asof,'result_observation_date')
        output.append(dict(copy.deepcopy(r),value=str(value),uncertainty_value=str(unc),semantic_status='not_assessed'))
    unique(output);return output


def draft_sections(v,allowed):
    obj(v,(),allowed,'draft_sections')
    for k,val in v.items():text(val,k,20000)
    return copy.deepcopy(v)


def publication(data):
    asof=base(data,('title','version','references','results'),('journal','draft_sections','contributors','license_record','data_code','review_records','systematics'))
    text(data['title'],'title');text(data['version'],'manuscript_version',200)
    if data.get('journal') is not None:text(data['journal'],'journal')
    references=[]
    for r in rows(data['references'],'references',maximum=100):
        obj(r,('id','url','identifier','source_reference','excerpt','source_text','publication_date'),label='reference')
        ref(r['id']);p=url(r['url']);quote(r,r['source_text']);text(r['source_text'],'source_text',160000);past(r['publication_date'],asof,'citation_publication_date')
        identity=text(r['identifier'],'citation_identifier',300)
        if identity.startswith('doi:'):
            token=identity[4:]
            if not re.fullmatch(r'10\.\d{4,9}/\S+',token) or p.hostname.lower()!='doi.org' or p.path[1:]!=token:raise ValueError('doi_identifier_url_mismatch')
        elif identity.startswith('arxiv:'):
            token=identity[6:]
            if not re.fullmatch(r'(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?',token) or p.hostname.lower() not in ('arxiv.org','www.arxiv.org') or p.path!='/abs/'+token:raise ValueError('arxiv_identifier_url_mismatch')
        else:raise ValueError('doi_or_arxiv_identifier_required')
        if token not in r['source_text']:raise ValueError('citation_identifier_not_in_selected_metadata')
        references.append(dict(copy.deepcopy(r),identity_status='selected_metadata_occurrence_only',claim_support='not_assessed'))
    unique(references);contributors=[];gaps=[]
    for c in rows(data.get('contributors',[]),'contributors',maximum=100):
        obj(c,('id','contributions','consent_record'),label='contributor');ref(c['id'])
        for role in rows(c['contributions'],'contributions',1,20):text(role,'contribution')
        record=observation(c['consent_record'],asof);contributors.append(dict(id=c['id'],contributions=copy.deepcopy(c['contributions']),consent_record=record))
        if record['state']!='provided':gaps.append('contributor.'+c['id'])
    unique(contributors)
    if not contributors:gaps.append('contributors')
    license_record=data.get('license_record')
    if license_record is not None:
        license_record=observation(license_record,asof)
        if license_record['state']!='provided':gaps.append('license_record')
        if license_record['provided_period_ended']:gaps.append('license_record.provided_period_ended')
    else:gaps.append('license_record')
    datacode=[]
    for item in rows(data.get('data_code',[]),'data_code',maximum=50):
        obj(item,('id','kind','version','access_record'),('url','license_record'),'data_code')
        for k in ('id','kind','version'):text(item[k],k,300)
        if item.get('url') is not None:url(item['url'])
        copied=copy.deepcopy(item);copied['access_record']=observation(item['access_record'],asof)
        if item.get('license_record') is not None:
            copied['license_record']=observation(item['license_record'],asof)
            if item['license_record']['state']!='provided':gaps.append('data_code.'+item['id']+'.license_record')
            if copied['license_record']['provided_period_ended']:gaps.append('data_code.'+item['id']+'.license_record.provided_period_ended')
        else:gaps.append('data_code.'+item['id']+'.license_record')
        datacode.append(copied)
        if item['access_record']['state']!='provided':gaps.append('data_code.'+item['id']+'.access')
        if copied['access_record']['provided_period_ended']:gaps.append('data_code.'+item['id']+'.access.provided_period_ended')
    unique(datacode)
    if not datacode:gaps.append('data_code')
    reviews=[]
    for row in rows(data.get('review_records',[]),'review_records',maximum=30):reviews.append(observation(row,asof))
    for i,record in enumerate(reviews):
        if record['state']!='provided':gaps.append('review_records.'+str(i))
        if record['provided_period_ended']:gaps.append('review_records.'+str(i)+'.provided_period_ended')
    systematics=[]
    for value in rows(data.get('systematics',[]),'systematics',maximum=50):systematics.append(text(value,'systematics'))
    for name,values in (('references',references),('results',data['results']),('systematics',systematics),('review_records',reviews)):
        if not values:gaps.append(name)
    sections=draft_sections(data.get('draft_sections',{}),('abstract','introduction','method','conclusions','reviewer_response'))
    return result('publication',data,title=data['title'],version=data['version'],journal=data.get('journal'),draft_sections=sections,
                  results=sourced_results(data['results'],asof),reference_review=references,contributor_review=contributors,
                  license_record=license_record,data_code=datacode,review_records=reviews,systematics=systematics,
                  evidence_gaps=gaps,notices=['citation_occurrence_is_not_claim_support','author_license_export_review_required','draft_not_submitted'])


def conditional_deadline(config,event):
    obj(config,('duration','count_start','roll'),('calendar',),'conditional_deadline')
    n=quantity(config['duration']);unit=config['duration']['unit']
    if n!=n.to_integral_value() or not 1<=n<=365:raise ValueError('deadline_positive_integer_up_to_365_required')
    if unit not in ('calendar_days','business_days'):raise ValueError('supported_deadline_day_unit_required')
    if config['count_start'] not in ('include_event','next_day'):raise ValueError('explicit_deadline_count_start_required')
    if config['roll'] not in ('none','next_working_day'):raise ValueError('supported_deadline_roll_required')
    include=config['count_start']=='include_event';calendar=config.get('calendar');classified={}
    if unit=='business_days' or config['roll']=='next_working_day':
        obj(calendar,('coverage_from','coverage_to','days','source_reference'),label='deadline_calendar')
        ref(calendar['source_reference']);begin,end=day(calendar['coverage_from']),day(calendar['coverage_to'])
        if not begin<=event<=end or (end-begin).days>365:raise ValueError('deadline_calendar_coverage_invalid')
        supplied=rows(calendar['days'],'calendar_days',1,366)
        if len(supplied)!=(end-begin).days+1:raise ValueError('complete_daily_calendar_required')
        for i,row in enumerate(supplied):
            obj(row,('date','working'),label='deadline_calendar_day');current=day(row['date'])
            if current!=begin+timedelta(days=i) or type(row['working']) is not bool:raise ValueError('complete_ordered_classified_calendar_required')
            classified[current]=row['working']
    elif calendar is not None:raise ValueError('unused_deadline_calendar')
    count_=int(n);counted=[]
    if unit=='business_days':
        eligible=[d for d,working in classified.items() if working and (d>event or include and d==event)]
        if len(eligible)<count_:raise ValueError('calendar_does_not_cover_deadline')
        counted=eligible[:count_];candidate=counted[-1]
    else:
        delta=count_-1 if include else count_
        if (date.max-event).days<delta:raise ValueError('deadline_date_overflow')
        candidate=event+timedelta(days=delta)
    nominal=candidate
    if config['roll']=='next_working_day':
        while True:
            if candidate not in classified:raise ValueError('calendar_does_not_cover_roll')
            if classified[candidate]:break
            if candidate==date.max:raise ValueError('deadline_date_overflow')
            candidate+=timedelta(days=1)
    return dict(candidate_deadline=candidate.isoformat(),nominal_deadline=nominal.isoformat(),
                counted_dates=[d.isoformat() for d in counted],duration=copy.deepcopy(config['duration']),
                count_start=config['count_start'],roll=config['roll'],calendar_reference=calendar['source_reference'] if calendar else None)


def rd_reports(data):
    asof=base(data,('project_id','scope','milestones','agreements','results'),('draft_sections','budget','reporting_obligations','export_review'))
    text(data['project_id'],'project_id');text(data['scope'],'scope');agreements=[];agreementids=set()
    for a in rows(data['agreements'],'agreements',maximum=30):
        obj(a,('id','scope','start_date','end_date','source_reference','excerpt'),label='agreement');quote(a);ref(a['id'])
        if day(a['start_date'])>day(a['end_date']):raise ValueError('agreement_period_invalid')
        text(a['scope'],'agreement_scope');agreements.append(copy.deepcopy(a));agreementids.add(a['source_reference'])
    unique(agreements);milestones=[]
    for m in rows(data['milestones'],'milestones',maximum=100):
        obj(m,('id','title','due_date','deliverable','agreement_reference'),('completion_record',),'milestone')
        for k in ('id','title','deliverable'):text(m[k],k)
        due=day(m['due_date'],'milestone_due_date');ref(m['agreement_reference'])
        if m['agreement_reference'] not in agreementids:raise ValueError('milestone_agreement_not_selected')
        if m.get('completion_record') is not None:observation(m['completion_record'],asof)
        milestones.append(dict(copy.deepcopy(m),past_due_date=due<asof,completion_status='not_assessed'))
    unique(milestones);gaps=[]
    obligations=[]
    for o in rows(data.get('reporting_obligations',[]),'reporting_obligations',maximum=50):
        obj(o,('id','event_date','selected_rule','recipient'),('due_date','deadline_calculation','reporter_role','record'),'reporting_obligation')
        if ('due_date' in o)==('deadline_calculation' in o):raise ValueError('one_deadline_mode_required')
        event=past(o['event_date'],asof,'reporting_event_date')
        calculation=None
        if 'deadline_calculation' in o:
            text(o['reporter_role'],'reporter_role')
            if o['selected_rule'].get('role')!=o['reporter_role']:raise ValueError('reporting_rule_role_mismatch')
            calculation=conditional_deadline(o['deadline_calculation'],event);due=day(calculation['candidate_deadline'])
        else:
            due=day(o['due_date'],'reporting_due_date')
            if o.get('reporter_role') is not None:text(o['reporter_role'],'reporter_role')
        if due<event:raise ValueError('report_due_before_event')
        meta=rule(o['selected_rule'],asof,event,data['scope']);text(o['recipient'],'recipient');ref(o['id'])
        if o.get('record') is not None:observation(o['record'],asof)
        copied=copy.deepcopy(o);copied['due_date']=due.isoformat()
        obligations.append(dict(copied,selected_rule=meta,past_due_date=due<asof,
                                candidate_deadline=due.isoformat(),conditional_calculation=calculation,
                                deadline_basis='conditional_selected_rule' if calculation else 'provided_date',
                                deadline_interpretation='provided_date_not_legally_validated'))
    unique(obligations)
    budget=data.get('budget');budgetreview=None
    if budget is None:gaps.append('budget')
    else:
        obj(budget,('limit','items'),label='rd_budget');limit=quantity(budget['limit'],'RUB');total=Decimal(0)
        if limit<0:raise ValueError('budget_limit_nonnegative_required')
        for item in rows(budget['items'],'budget_items',maximum=100):
            obj(item,('id','amount','purpose','agreement_reference'),label='budget_item');ref(item['id']);text(item['purpose'],'budget_purpose')
            value=quantity(item['amount'],'RUB')
            if value<0 or item['agreement_reference'] not in agreementids:raise ValueError('budget_amount_or_agreement_invalid')
            total+=value
        unique(budget['items']);budgetreview=dict(copy.deepcopy(budget),total=str(total),remaining=str(limit-total),budget_eligibility='not_assessed')
    export=data.get('export_review');exportout=None
    if export is None:gaps.append('export_scope_and_lists')
    else:
        obj(export,('transfer_scope','event_date','selected_lists','checks'),('items',),'export_review')
        text(export['transfer_scope'],'transfer_scope');event=past(export['event_date'],asof,'export_review_date')
        metas=selected_rules(export['selected_lists'],asof,event,data['scope']);checks={}
        obj(export['checks'],(),('destination','end_user','end_use','item_identification','list_coverage'),'export_checks')
        for k in ('destination','end_user','end_use','item_identification','list_coverage'):
            if k not in export['checks']:gaps.append('export.'+k)
            else:
                checks[k]=observation(export['checks'][k],asof)
                if checks[k]['state']!='provided':gaps.append('export.'+k)
                if checks[k]['provided_period_ended']:gaps.append('export.'+k+'.provided_period_ended')
        items=[]
        for item in rows(export.get('items',[]),'export_items',maximum=50):items.append(text(item,'export_item'))
        if not metas:gaps.append('export.selected_lists')
        exportout=dict(transfer_scope=export['transfer_scope'],selected_lists=metas,checks=checks,items=items,
                       classification='not_performed',responsible_review='required_before_transfer')
    for key,value in (('milestones',milestones),('agreements',agreements),('reporting_obligations',obligations)):
        if not value:gaps.append(key)
    sections=draft_sections(data.get('draft_sections',{}),('abstract','introduction','methods','conclusion'))
    return result('rd_reports',data,project_id=data['project_id'],scope=data['scope'],draft_sections=sections,milestone_review=milestones,
                  agreement_review=agreements,budget_review=budgetreview,results=sourced_results(data['results'],asof),
                  reporting_obligations=obligations,export_review=exportout,evidence_gaps=gaps,
                  notices=['selected_reporting_dates_not_universal_deadlines','export_scope_cannot_be_cleared_by_model_flag','draft_not_submitted'])


def input_units(function,data):
    if function not in FUNCTIONS:raise ValueError('unknown_scenario_function')
    bounded(data);units={};asof=data['as_of']
    def put(path,unit,effective=None):
        units[path]={'unit':unit,'not_after':asof}
        if effective is not None:units[path]['effective_date']=effective
    def walk(v,path='',effective=None):
        if type(v) is dict:
            effective=v.get('snapshot_date',v.get('observation_date',effective))
            if 'unit' in v:
                if 'value' in v:put(path+'/value',v['unit'],effective)
                for k in ('lower','upper'):
                    if k in v:put(path+'/'+k,v['unit'],effective)
            for k,item in v.items():
                child=path+'/'+k.replace('~','~0').replace('/','~1')
                if k=='repeats':put(child,'count',effective)
                elif k=='limit_multiplier':put(child,'ratio',effective)
                elif k in ('severity','likelihood','review_threshold'):put(child,'score',effective)
                elif k in ('severity_levels','likelihood_levels'):
                    for i in range(len(item)):put(child+'/'+str(i),'score',effective)
                elif function=='experiment_setup' and '/method_compare/pairs/' in child and k in ('a','b'):
                    put(child,data['method_compare']['unit'],effective)
                else:walk(item,child,effective)
        elif type(v) is list:
            for i,item in enumerate(v):walk(item,path+'/'+str(i),effective)
    walk(data);return units


def selected_texts(function,data):
    if function not in FUNCTIONS:raise ValueError('unknown_scenario_function')
    bounded(data);selected={}
    def walk(v,path=''):
        if type(v) is dict:
            for k,item in v.items():
                p=path+'/'+k.replace('~','~0').replace('/','~1')
                if k in ('excerpt','source_text') or k=='text' and 'source_reference' in v:
                    selected[p]=text(item,'selected_literal',160000)
                else:walk(item,p)
        elif type(v) is list:
            for i,item in enumerate(v):walk(item,path+'/'+str(i))
    walk(data);return selected


def public(fn):
    @wraps(fn)
    def checked(*args,**kwargs):
        try:
            with localcontext(Context(prec=100,Emax=999,Emin=-999)):
                return fn(*args,**kwargs)
        except (KeyError,TypeError,AttributeError,IndexError,OverflowError,RecursionError,DecimalException):
            raise ValueError('invalid_nested_or_numeric_scenario_input') from None
    return checked


for _name in (*FUNCTIONS,'input_units','selected_texts'):
    globals()[_name]=public(globals()[_name])

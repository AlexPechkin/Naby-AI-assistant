"""Bounded source-selected embedded architecture/code assistance, no execution.

All finite arithmetic and predicates use Fractions; Decimal180 is rendering,
not measurement precision. No target, compiler, RTOS or analyzer is invoked.
"""
from collections import Counter
from copy import deepcopy
from datetime import date
from decimal import Decimal,Context,InvalidOperation,DecimalException,localcontext
from fractions import Fraction as F
import hashlib,json,re
import xml.etree.ElementTree as ET
from .privacy import reject_known_secret_material

FUNCTIONS=('fw_architecture','fw_code')
CTX=Context(prec=180,Emin=-999999,Emax=999999)
NUMBER=re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z')
TIME_US={'s':F(1000000),'ms':F(1000),'us':F(1),'ns':F(1,1000)}
BYTE={'byte':1,'KiB':1024,'MiB':1048576}

def fail(code):raise ValueError(code)
def obj(x,required=(),optional=()):
    if type(x) is not dict or set(required)-set(x) or set(x)-set(required)-set(optional):fail('bounded_object_fields_required')
    return x
def rows(x,maximum=60,minimum=0):
    if type(x) is not list or not minimum<=len(x)<=maximum:fail('bounded_array_required')
    return x
def text(x,maximum=6000):
    if type(x) is not str or not x.strip() or len(x)>maximum or any(ord(c)<32 and c not in '\n\r\t' for c in x):fail('bounded_nonempty_text_required')
    return x
def ref(x):return text(x,80)
def enum(x,values):
    if type(x) is not str or x not in values:fail('unsupported_selected_model_or_option')
    return x
def iso(x):
    if type(x) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',x):fail('ISO_date_required')
    try:date.fromisoformat(x)
    except ValueError:fail('ISO_date_required')
    return x
def sha(x):return hashlib.sha256(x.encode('utf8')).hexdigest()
def hashtext(x):
    if type(x) is not str or not re.fullmatch('[0-9a-f]{64}',x):fail('SHA256_required')
    return x
def unique(items):
    if len({text(x['id'],160) for x in items})!=len(items):fail('duplicate_identity')
def ceil(x):return -(-x.numerator//x.denominator)
def serial(x):
    if isinstance(x,F):
        with localcontext(CTX):return '0' if not x else str((Decimal(x.numerator)/Decimal(x.denominator)).normalize())
    if type(x) is dict:return {k:serial(v) for k,v in x.items()}
    if type(x) is list:return [serial(v) for v in x]
    return x

class Read:
    def __init__(self,data):
        if type(data) is not dict:fail('data_object_required')
        self.asof=iso(data['as_of'])
        if data['jurisdiction']!='RU':fail('RU_jurisdiction_required')
        self.units={};self.literals={};self.gaps=[]
    def gap(self,kind,path=''):
        row=dict(kind=kind,path=path)
        if row not in self.gaps:self.gaps.append(row)
    def literal(self,value,path,references):
        text(value,100000);references=list(dict.fromkeys(ref(v) for v in references))
        if not references:fail('literal_source_reference_required')
        self.literals[path]=dict(text=value,source_references=references)
    def q(self,x,path,units=None,lo=None,hi=None,integer=False,cutoff=None):
        obj(x,('value','unit','source_reference'),('observed_date',));raw=x['value']
        if type(raw) is not str or len(raw)>170 or not NUMBER.fullmatch(raw):fail('exact_decimal_string_required')
        if 'e' in raw.lower() and abs(int(raw.lower().split('e')[1]))>100:fail('numeric_exponent_bound')
        try:d=Decimal(raw)
        except InvalidOperation:fail('numeric_exponent_bound')
        if not d.is_finite() or len(d.as_tuple().digits)>40 or abs(d.as_tuple().exponent)>140 or d and not -100<=d.adjusted()<=100:fail('numeric_precision_bound')
        n=F(d);unit=text(x['unit'],100)
        if units is not None and unit not in units:fail('explicit_supported_unit_required')
        if lo is not None and n<lo or hi is not None and n>hi or integer and n.denominator!=1:fail('numeric_domain_bound')
        bound=min(self.asof,iso(cutoff)) if cutoff else self.asof
        spec=dict(unit=unit,effective_not_after=bound,published_not_after=self.asof,source_references=[ref(x['source_reference'])])
        if 'observed_date' in x:
            observed=iso(x['observed_date'])
            if observed>bound:fail('actual_observation_after_selected_cutoff')
            spec['effective_date']=observed
            self.literal(observed,path+'/observed_date',[x['source_reference']])
        self.units[path+'/value']=spec
        if len(self.units)>850:fail('numeric_budget_850')
        return n
    def time(self,x,p,lo=F(0)):
        n=self.q(x,p,TIME_US,lo=lo)
        return n*TIME_US[x['unit']]
    def size(self,x,p):
        n=self.q(x,p,BYTE,lo=0,hi=2**64)
        n*=BYTE[x['unit']]
        if n.denominator!=1:fail('integer_byte_count_required')
        if n>2**64:fail('byte_count_bound_after_unit_conversion')
        return n
    def address(self,x,p):return self.q(x,p,('byte_address',),0,2**64-1,True)

def note(r,x,p):
    obj(x,('text','source_reference'));r.literal(x['text'],p+'/text',[x['source_reference']]);return deepcopy(x)
def context(x):
    obj(x,(),('device','mcu','compiler','expected_behavior','coding_standard','notes'))
    for v in x.values():text(v)
    return deepcopy(x)

def proposal(r,x,p='/proposal'):
    obj(x,(),('device_functions','interfaces','modules','states','transitions','forbidden_transitions','reset_state','runtime_choice','error_handling','watchdog','security','power_strategy','RU_ECB_OS_constraints','requirements','notes'))
    out=deepcopy(x)
    for field in ('device_functions','interfaces','requirements'):
        for value in rows(x.get(field,[]),50):text(value)
    for field in ('runtime_choice','error_handling','watchdog','security','power_strategy','RU_ECB_OS_constraints','notes'):
        if field in x:text(x[field])
    modules=rows(x.get('modules',[]),40)
    for m in modules:
        obj(m,('id','responsibility','dependencies'))
        text(m['id']);text(m['responsibility'])
        for identity in rows(m['dependencies'],40):text(identity)
    unique(modules);mids={v['id'] for v in modules}
    if any(set(v['dependencies'])-mids or len(v['dependencies'])!=len(set(v['dependencies'])) for v in modules):fail('unknown_or_duplicate_module_dependency')
    states=rows(x.get('states',[]),40)
    for st in states:obj(st,('id','description'));text(st['id']);text(st['description'])
    unique(states);sids={v['id'] for v in states}
    if 'reset_state' in x and x['reset_state'] not in sids:fail('reset_state_not_declared')
    transitions=rows(x.get('transitions',[]),80);forbidden=rows(x.get('forbidden_transitions',[]),80)
    for row in transitions:
        obj(row,('from','to','guard','action'))
        for v in row.values():text(v)
        if row['from'] not in sids or row['to'] not in sids:fail('transition_unknown_state')
    for row in forbidden:
        obj(row,('from','to','rationale'))
        for v in row.values():text(v)
        if row['from'] not in sids or row['to'] not in sids:fail('forbidden_transition_unknown_state')
    conflicts=[dict(from_state=a['from'],to_state=a['to']) for a in transitions if any(a['from']==b['from'] and a['to']==b['to'] for b in forbidden)]
    if conflicts:r.gap('proposed_transition_conflicts',p)
    for field in ('device_functions','interfaces','modules','states','reset_state','error_handling','watchdog','security','RU_ECB_OS_constraints'):
        if not x.get(field):r.gap('proposal_context_missing',p+'/'+field)
    return dict(provided=out,transition_conflicts=conflicts,interpretation='authored_architecture_proposal_not_hardware_behavior',safety_established=False)

def timing(r,x,p='/timing'):
    obj(x,('model','tasks','interrupts','utilization_limit'),('model_note',))
    model=enum(x['model'],('fp_preemptive_constrained_single_core','utilization_only'))
    if x.get('model_note') is not None:note(r,x['model_note'],p+'/model_note')
    limit=r.q(x['utilization_limit'],p+'/utilization_limit',('ratio',),0,1)
    tasks=[];irqs=[];unsupported=[]
    for i,t in enumerate(rows(x['tasks'],40,1)):
        q=p+'/tasks/'+str(i);obj(t,('id','period','execution_budget'),('deadline','priority_rank','blocking_budget','description'))
        text(t['id']);period=r.time(t['period'],q+'/period',F(1,10**100));C=r.time(t['execution_budget'],q+'/execution_budget')
        D=r.time(t['deadline'],q+'/deadline',F(1,10**100)) if 'deadline' in t else None
        B=r.time(t['blocking_budget'],q+'/blocking_budget') if 'blocking_budget' in t else None
        priority=r.q(t['priority_rank'],q+'/priority_rank',('priority_rank',),1,1000000,True) if 'priority_rank' in t else None
        if t.get('description') is not None:text(t['description'])
        if model.startswith('fp_'):
            if D is None or B is None or priority is None:unsupported.append(('missing_explicit_RTA_parameters',q))
            elif D>period:unsupported.append(('arbitrary_deadline_not_supported',q))
        tasks.append(dict(id=t['id'],period_us=period,execution_budget_us=C,deadline_us=D,blocking_budget_us=B,priority_rank=priority,utilization=C/period))
    unique(tasks)
    for i,t in enumerate(rows(x['interrupts'],30)):
        q=p+'/interrupts/'+str(i);obj(t,('id','minimum_interarrival','execution_budget'));text(t['id'])
        T=r.time(t['minimum_interarrival'],q+'/minimum_interarrival',F(1,10**100));C=r.time(t['execution_budget'],q+'/execution_budget')
        irqs.append(dict(id=t['id'],minimum_interarrival_us=T,execution_budget_us=C,utilization=C/T))
    unique(irqs)
    pri=[v['priority_rank'] for v in tasks if v['priority_rank'] is not None]
    if model.startswith('fp_') and len(set(pri))!=len(pri):unsupported.append(('equal_priority_scheduling_not_supported',p))
    enabled=model.startswith('fp_') and not unsupported
    for why,where in unsupported:r.gap(why,where)
    results=[]
    for t in tasks:
        row=dict(t,response_time_us=None,last_iterate_us=None,next_iterate_us=None,next_iterate_deadline_margin_us=None,iteration_count=0,status='utilization_only' if model=='utilization_only' else 'RTA_model_or_parameters_unsupported',model_deadline_met=None)
        if enabled:
            base=t['execution_budget_us']+t['blocking_budget_us'];current=base;status='iteration_limit_reached';next_value=base
            hp=[z for z in tasks if z['priority_rank']<t['priority_rank']]
            for n in range(4096):
                next_value=base+sum((ceil(current/z['period_us'])*z['execution_budget_us'] for z in hp),F())+sum((ceil(current/z['minimum_interarrival_us'])*z['execution_budget_us'] for z in irqs),F())
                row['iteration_count']=n+1
                if next_value>t['deadline_us']:status='selected_deadline_exceeded';break
                if next_value==current:status='fixed_point_found';break
                current=next_value
            row.update(last_iterate_us=current,next_iterate_us=next_value,next_iterate_deadline_margin_us=t['deadline_us']-next_value,status=status)
            if status=='fixed_point_found':row.update(response_time_us=next_value,model_deadline_met=True)
            elif status=='selected_deadline_exceeded':row['model_deadline_met']=False
            else:r.gap('RTA_iteration_resource_limit',p)
        results.append(row)
    total=sum((v['utilization'] for v in tasks+irqs),F())
    if total>limit and serial(total)==serial(limit):r.gap('utilization_comparison_uses_unrounded_operands',p)
    r.gap('execution_blocking_and_interrupt_bounds_not_established',p)
    return dict(model=model,priority_convention='lower_rank_higher_priority_not_vendor_numeric_priority',tasks=results,interrupts=irqs,total_demand_ratio=total,selected_utilization_limit=limit,selected_utilization_margin=limit-total,within_selected_utilization_limit=total<=limit,model_all_task_deadlines_met=all(v['model_deadline_met'] for v in results) if enabled and all(v['model_deadline_met'] is not None for v in results) else None,assumptions=['one_processor','independent_periodic_or_sporadic_jobs','preemptive_distinct_fixed_task_priorities','all_supplied_interrupts_preempt_tasks','supplied_blocking_budget_only','no_release_jitter_self_suspension_or_unmodeled_overheads'] if model.startswith('fp_') else ['declared_execution_over_selected_interarrival_only'],iteration_resource_limit=4096,measured_WCET_established=False,interrupt_response_times_assessed=False)

def memory(r,x,p='/memory'):
    obj(x,('regions','allocations'),('map_provenance',))
    provenance=None
    if x.get('map_provenance') is not None:provenance=note(r,x['map_provenance'],p+'/map_provenance')
    regionmap={};regions=[]
    for i,z in enumerate(rows(x['regions'],12,1)):
        q=p+'/regions/'+str(i);obj(z,('id','kind','address_space','capacity'),('origin',));text(z['id']);text(z['address_space']);enum(z['kind'],('flash','ram','other'))
        capacity=r.size(z['capacity'],q+'/capacity');origin=r.address(z['origin'],q+'/origin') if 'origin' in z else None
        if origin is not None and origin+capacity>2**64:fail('memory_region_address_overflow')
        item=dict(id=z['id'],kind=z['kind'],address_space=z['address_space'],capacity_bytes=capacity,origin=origin)
        if z['id'] in regionmap:fail('duplicate_memory_region')
        regionmap[z['id']]=item;regions.append(item)
    allocations=[]
    for i,z in enumerate(rows(x['allocations'],70)):
        q=p+'/allocations/'+str(i);obj(z,('id','region_id','purpose','size'),('address','initialization','load_image_id'))
        text(z['id']);reg=regionmap.get(z['region_id'])
        if reg is None:fail('unknown_allocation_region')
        purpose=enum(z['purpose'],('section','stack','heap','reserve','load_image'))
        size=r.size(z['size'],q+'/size');address=r.address(z['address'],q+'/address') if 'address' in z else None
        if address is not None and address+size>2**64:fail('allocation_address_overflow')
        init=enum(z['initialization'],('zeroed','copied_plain','execute_in_place','not_applicable','unknown')) if 'initialization' in z else None
        if 'load_image_id' in z:text(z['load_image_id'])
        inside=None if reg['origin'] is None or address is None else reg['origin']<=address and address+size<=reg['origin']+reg['capacity_bytes']
        if inside is None:r.gap('allocation_layout_not_assessed_missing_address',q)
        elif not inside:r.gap('allocation_outside_selected_region',q)
        allocations.append(dict(id=z['id'],region_id=z['region_id'],purpose=purpose,size_bytes=size,address=address,initialization=init,load_image_id=z.get('load_image_id'),inside_selected_region=inside))
    unique(allocations);byid={z['id']:z for z in allocations};image_checks=[]
    for a in allocations:
        if a['initialization']=='copied_plain':
            image=byid.get(a['load_image_id']);match=None if image is None else image['purpose']=='load_image' and image['size_bytes']==a['size_bytes']
            if match is not True:r.gap('initialized_RAM_image_unresolved_or_size_mismatch',p+'/'+a['id'])
            image_checks.append(dict(runtime_id=a['id'],load_image_id=a['load_image_id'],same_size_plain_copy=match))
    overlaps=[]
    for i,a in enumerate(allocations):
        if a['address'] is None or not a['size_bytes']:continue
        for b in allocations[i+1:]:
            if b['address'] is not None and b['size_bytes'] and a['region_id']==b['region_id']:
                overlap=min(a['address']+a['size_bytes'],b['address']+b['size_bytes'])-max(a['address'],b['address'])
                if overlap>0:overlaps.append(dict(first_id=a['id'],second_id=b['id'],overlap_bytes=overlap))
    region_overlaps=[]
    for i,a in enumerate(regions):
        for b in regions[i+1:]:
            if a['address_space']==b['address_space'] and a['origin'] is not None and b['origin'] is not None and a['capacity_bytes'] and b['capacity_bytes']:
                overlap=min(a['origin']+a['capacity_bytes'],b['origin']+b['capacity_bytes'])-max(a['origin'],b['origin'])
                if overlap>0:region_overlaps.append(dict(first_id=a['id'],second_id=b['id'],overlap_bytes=overlap))
    if overlaps or region_overlaps:r.gap('selected_memory_ranges_overlap',p)
    for reg in regions:
        used=sum((a['size_bytes'] for a in allocations if a['region_id']==reg['id']),F());capacity=reg['capacity_bytes']
        reg.update(declared_sum_bytes=used,free_from_declared_sum_bytes=capacity-used,utilization_ratio=None if not capacity else used/capacity,capacity_only_within_selected_limit=used<=capacity)
    return dict(regions=regions,allocations=allocations,allocation_overlaps=overlaps,region_overlaps=region_overlaps,initialization_image_checks=image_checks,map_provenance=provenance,all_declared_capacity_sums_fit=all(z['capacity_only_within_selected_limit'] for z in regions),scope='declared_allocations_only_not_full_linker_or_physical_map_validation',stack_high_water_or_aliasing_established=False)

def power(r,x,p='/power'):
    obj(x,('window','modes','transitions','transition_energy_basis'),('battery',))
    enum(x['transition_energy_basis'],('additional_to_mode_energy',))
    window=r.time(x['window'],p+'/window',F(1,10**100))/1000000;mode_rows=[];seconds=F();energy=F();charge=F()
    for i,z in enumerate(rows(x['modes'],20,1)):
        q=p+'/modes/'+str(i);obj(z,('id','duration','current','voltage'));text(z['id'])
        duration=r.time(z['duration'],q+'/duration')/1000000;current=r.q(z['current'],q+'/current',('mA',),0);voltage=r.q(z['voltage'],q+'/voltage',('V',),0)
        e=duration*current*voltage/1000;energy+=e;charge+=duration*current/1000;seconds+=duration
        mode_rows.append(dict(id=z['id'],duration_s=duration,current_mA=current,voltage_V=voltage,energy_J=e))
    unique(mode_rows);transition_rows=[]
    for i,z in enumerate(rows(x['transitions'],30)):
        q=p+'/transitions/'+str(i);obj(z,('id','count','energy'));text(z['id']);n=r.q(z['count'],q+'/count',('count',),0,10**12,True);e=r.q(z['energy'],q+'/energy',('uJ','J'),0)*(F(1,1000000) if z['energy']['unit']=='uJ' else 1)
        energy+=n*e;transition_rows.append(dict(id=z['id'],count=n,per_transition_energy_J=e,total_energy_J=n*e))
    unique(transition_rows);complete=seconds==window
    if not complete:r.gap('power_window_not_fully_and_uniquely_accounted',p)
    avg=energy/window if complete else None;battery=None
    if 'battery' in x:
        b=obj(x['battery'],('capacity','voltage','usable_fraction','conversion_efficiency'));cap=r.q(b['capacity'],p+'/battery/capacity',('mAh',),0);v=r.q(b['voltage'],p+'/battery/voltage',('V',),0);usable=r.q(b['usable_fraction'],p+'/battery/usable_fraction',('ratio',),0,1);eff=r.q(b['conversion_efficiency'],p+'/battery/conversion_efficiency',('ratio',),F(1,10**100),1)
        available=cap*v*F(3600,1000)*usable*eff;life=None if avg is None or avg==0 else available/avg
        if avg==0:r.gap('ideal_battery_life_undefined_zero_power',p)
        battery=dict(selected_available_energy_J=available,ideal_energy_limited_life_s=life,physical_lifetime_established=False)
    return dict(window_s=window,accounted_mode_time_s=seconds,unaccounted_time_s=window-seconds,declared_mode_durations_sum_to_window=complete,duration_partition_model='supplied_durations_assumed_disjoint_when_sum_matches',physical_mode_partition_established=False,modes=mode_rows,transitions=transition_rows,transition_energy_basis=x['transition_energy_basis'],declared_energy_J=energy,average_power_W=avg,mode_average_current_mA_excluding_transitions=charge/window*1000 if complete else None,battery=battery,scope='selected_duty_cycle_energy_model_not_measured_power_or_battery_guarantee')

def platforms(r,values,p='/platforms'):
    out=[]
    for i,z in enumerate(rows(values,6)):
        q=p+'/'+str(i);obj(z,('id','kind','datasheet','resources','features'),('tradeoffs',));text(z['id']);kind=enum(z['kind'],('mcu','fpga','mixed'))
        ds=note(r,z['datasheet'],q+'/datasheet');resources=[]
        for j,a in enumerate(rows(z['resources'],20)):
            pp=q+'/resources/'+str(j);obj(a,('id','required','available'));text(a['id'])
            if a['required']['unit']!=a['available']['unit']:fail('platform_resource_unit_mismatch')
            unit=a['required']['unit'];integer=unit in ('byte','count','pin','channel','bit')
            need=r.q(a['required'],pp+'/required',None,0,integer=integer);available=r.q(a['available'],pp+'/available',None,0,integer=integer)
            if unit in BYTE and any((v*BYTE[unit]).denominator!=1 for v in (need,available)):fail('integer_byte_count_required')
            resources.append(dict(id=a['id'],required=need,available=available,unit=a['required']['unit'],within_selected_capacity=need<=available,margin=available-need))
        unique(resources);features=[]
        for j,a in enumerate(rows(z['features'],30)):
            obj(a,('id','state','note'),('evidence',));text(a['id']);enum(a['state'],('provided_support','provided_no_support','unknown'));text(a['note'])
            if a.get('evidence') is not None:note(r,a['evidence'],q+'/features/'+str(j)+'/evidence')
            elif a['state']!='unknown':r.gap('candidate_feature_evidence_not_supplied',q+'/features/'+str(j))
            features.append(deepcopy(a))
        unique(features)
        if z.get('tradeoffs') is not None:text(z['tradeoffs'])
        out.append(dict(id=z['id'],kind=kind,datasheet=ds,resource_comparisons=resources,features=features,tradeoffs=z.get('tradeoffs'),selection_status='candidate_comparison_not_platform_selection_or_RU_ECB_clearance'))
    unique(out);return out

def fpga(r,x,p='/fpga'):
    obj(x,('provenance','resources','paths'))
    prov=note(r,x['provenance'],p+'/provenance');res=[];paths=[]
    for i,z in enumerate(rows(x['resources'],20)):
        q=p+'/resources/'+str(i);obj(z,('id','used','capacity'));text(z['id'])
        if z['used']['unit']!=z['capacity']['unit']:fail('FPGA_resource_unit_mismatch')
        used=r.q(z['used'],q+'/used',None,0,integer=True);cap=r.q(z['capacity'],q+'/capacity',None,0,integer=True)
        res.append(dict(id=z['id'],used=used,capacity=cap,unit=z['used']['unit'],utilization=None if not cap else used/cap,within_supplied_capacity=used<=cap))
    unique(res)
    for i,z in enumerate(rows(x['paths'],30)):
        q=p+'/paths/'+str(i);obj(z,('id','analysis','corner','arrival','required'));text(z['id']);text(z['corner']);analysis=enum(z['analysis'],('setup','hold'))
        arrival=r.time(z['arrival'],q+'/arrival',None);required=r.time(z['required'],q+'/required',None)
        slack=required-arrival if analysis=='setup' else arrival-required
        paths.append(dict(id=z['id'],analysis=analysis,corner=z['corner'],arrival_us=arrival,required_us=required,slack_us=slack,nonnegative_supplied_path_slack=slack>=0))
    unique(paths)
    return dict(provenance=prov,resources=res,paths=paths,scope='supplied_STA_arrival_required_and_utilization_only',timing_constraints_completeness_established=False,synthesis_or_simulation_executed=False)

def risks(r,x,p='/risks'):
    obj(x,('items',),('matrix',));matrix=x.get('matrix');cells={}
    if matrix is not None:
        obj(matrix,('origin','likelihood_ids','impact_ids','cells'),('evidence',));enum(matrix['origin'],('selected_basis','authored_proposal'))
        ls=rows(matrix['likelihood_ids'],12,1);im=rows(matrix['impact_ids'],12,1)
        for v in ls+im:text(v)
        if len(set(ls))!=len(ls) or len(set(im))!=len(im):fail('duplicate_risk_category')
        for z in rows(matrix['cells'],144):
            obj(z,('likelihood_id','impact_id','priority','label'))
            for v in z.values():text(v)
            key=(z['likelihood_id'],z['impact_id'])
            if key in cells or key[0] not in ls or key[1] not in im:fail('duplicate_or_unknown_risk_cell')
            cells[key]=z
        if matrix['origin']=='selected_basis':note(r,matrix.get('evidence'),p+'/matrix/evidence')
    out=[]
    for z in rows(x['items'],40):
        obj(z,('id','hazard','likelihood_id','impact_id','mitigation','owner'))
        for v in z.values():text(v)
        cell=cells.get((z['likelihood_id'],z['impact_id']))
        if cell is None:r.gap('selected_risk_cell_missing',p+'/'+z['id'])
        out.append(dict(provided=deepcopy(z),priority=None if cell is None else cell['priority'],priority_label=None if cell is None else cell['label']))
    unique([z['provided'] for z in out]);return dict(matrix=deepcopy(matrix),items=out,interpretation='selected_ordinal_lookup_not_probability_or_physical_loss')

def architecture(r,data):
    obj(data,('as_of','jurisdiction','mode'),('context','proposal','timing','memory','power','platforms','fpga','risks'))
    mode=enum(data['mode'],('questions','draft','review'))
    if mode=='questions' and any(k in data for k in ('timing','memory','power','platforms','fpga','risks')):fail('questions_mode_has_calculations')
    return dict(mode=mode,context=context(data['context']) if 'context' in data else None,proposal=proposal(r,data['proposal']) if 'proposal' in data else None,timing=timing(r,data['timing']) if 'timing' in data else None,memory=memory(r,data['memory']) if 'memory' in data else None,power=power(r,data['power']) if 'power' in data else None,platform_candidates=platforms(r,data['platforms']) if 'platforms' in data else [],fpga=fpga(r,data['fpga']) if 'fpga' in data else None,risks=risks(r,data['risks']) if 'risks' in data else None,questions=['device_functions_interfaces_latency_power_data_safety_RU_ECB_OS','select_actual_datasheets_and_runtime_model','supply_only_selected_timing_memory_power_or_FPGA_evidence'] if mode=='questions' else [],architecture_is_draft=True)

def counter(r,x,p='/counter'):
    obj(x,('model','bits'),('value','increment','mode','now','before','maximum_elapsed','tick_frequency','emit_c_draft'))
    model=enum(x['model'],('unsigned_add','elapsed_modulo'))
    bits=r.q(x['bits'],p+'/bits',('bit',),1,64,True)
    if bits not in (8,16,32,64):fail('supported_exact_unsigned_width_required')
    width=int(bits);modulus=1<<width;maximum=modulus-1
    if x.get('emit_c_draft') is not None and type(x['emit_c_draft']) is not bool:fail('emit_c_draft_boolean_required')
    code=None
    if model=='unsigned_add':
        if any(k in x for k in ('now','before','maximum_elapsed','tick_frequency')):fail('unselected_elapsed_parameters')
        value=r.q(x['value'],p+'/value',('count',),0,maximum,True);increment=r.q(x['increment'],p+'/increment',('count',),0,2**64-1,True);mode=enum(x['mode'],('wrap','saturate'))
        raw=value+increment;result=raw%modulus if mode=='wrap' else min(raw,F(maximum))
        if x.get('emit_c_draft'):
            head='#include <stdint.h>\n/* Inert C99 draft; exact-width types and target behavior require review. */\n'
            body=f'uint{width}_t naby_add_u{width}(uint{width}_t value, uint64_t step) {{\n'
            if mode=='saturate':body+=f'    if (step > (uint64_t)(UINT{width}_MAX - value)) return UINT{width}_MAX;\n'
            body+=f'    return (uint{width}_t)(value + (uint{width}_t)step);\n}}\n';code=head+body
        return dict(model=model,bits=width,value=value,increment=increment,raw_sum=raw,mode=mode,result=result,overflow=raw>maximum,mathematical_wrap_count=raw//modulus,saturated=mode=='saturate' and raw>maximum,c_draft=code,draft_interpretation='authored_inert_C99_template_not_compiled_or_existing_source',integer_promotion_and_target_types_established=False)
    if any(k in x for k in ('value','increment','mode')):fail('unselected_add_parameters')
    now=r.q(x['now'],p+'/now',('count',),0,maximum,True);before=r.q(x['before'],p+'/before',('count',),0,maximum,True)
    delta=(now-before)%modulus;bound=r.q(x['maximum_elapsed'],p+'/maximum_elapsed',('count',),0,2**64-1,True) if 'maximum_elapsed' in x else None
    unambiguous=None if bound is None else bound<modulus and delta<=bound
    if unambiguous is not True:r.gap('counter_elapsed_wrap_ambiguity_or_bound_conflict',p)
    frequency=r.q(x['tick_frequency'],p+'/tick_frequency',('Hz',),F(1,10**100)) if 'tick_frequency' in x else None
    if x.get('emit_c_draft'):code=f'#include <stdint.h>\n/* Inert draft: true elapsed must be less than one modulus. */\nuint{width}_t naby_delta_u{width}(uint{width}_t now, uint{width}_t before) {{\n    return (uint{width}_t)(now - before);\n}}\n'
    return dict(model=model,bits=width,now=now,before=before,modular_delta=delta,selected_maximum_elapsed=bound,unambiguous_under_selected_bound=unambiguous,elapsed_s_under_single_modulus_model=delta/frequency if frequency is not None and unambiguous else None,c_draft=code,real_elapsed_or_wrap_count_established=False)

def uart(r,x,p='/uart'):
    obj(x,('clock_hz','oversampling','divider','requested_baud','tolerance','model_source_reference','model_excerpt'),('clock_bounds',))
    r.literal(x['model_excerpt'],p+'/model_excerpt',[x['model_source_reference']])
    clock=r.q(x['clock_hz'],p+'/clock_hz',('Hz',),F(1,10**100));over=r.q(x['oversampling'],p+'/oversampling',('ratio',),F(1,10**100));divider=r.q(x['divider'],p+'/divider',('ratio',),F(1,10**100));requested=r.q(x['requested_baud'],p+'/requested_baud',('bit/s',),F(1,10**100));tol=r.q(x['tolerance'],p+'/tolerance',('ratio',),0,1)
    actual=clock/(over*divider);error=(actual-requested)/requested;bounds=None
    if 'clock_bounds' in x:
        b=obj(x['clock_bounds'],('minimum','maximum'));lo=r.q(b['minimum'],p+'/clock_bounds/minimum',('Hz',),F(1,10**100));hi=r.q(b['maximum'],p+'/clock_bounds/maximum',('Hz',),lo)
        worst=max(abs(lo/(over*divider)/requested-1),abs(hi/(over*divider)/requested-1))
        if not lo<=clock<=hi:r.gap('point_clock_outside_selected_bounds',p)
        bounds=dict(minimum_clock_hz=lo,maximum_clock_hz=hi,worst_absolute_error_ratio=worst,within_selected_tolerance=worst<=tol)
    return dict(model='clock_divided_by_explicit_oversampling_and_effective_divider',clock_hz=clock,oversampling=over,divider=divider,requested_baud=requested,actual_baud=actual,signed_error_ratio=error,signed_error_percent=error*100,absolute_error_ratio=abs(error),selected_tolerance_ratio=tol,within_selected_tolerance=abs(error)<=tol,clock_bounds=bounds,model_source_reference=x['model_source_reference'],model_excerpt=x['model_excerpt'],register_encoding_or_link_reliability_established=False)

def mask_c(source):
    """Whitespace-mask comments and literals, preserving positions/newlines.

    This is a small lexical aid, not preprocessing, parsing or C/C++ analysis.
    Raw strings, macros and compiler extensions remain an explicit limitation.
    """
    out=list(source);i=0;n=len(source)
    while i<n:
        end=None
        if source.startswith('//',i):
            e=source.find('\n',i+2);end=n if e<0 else e
        elif source.startswith('/*',i):
            e=source.find('*/',i+2);end=n if e<0 else e+2
        elif source[i] in ('"',"'"):
            quote=source[i];j=i+1
            while j<n:
                if source[j]=='\\':j+=2;continue
                if source[j]==quote:j+=1;break
                j+=1
            end=min(j,n)
        if end is not None:
            for j in range(i,end):
                if out[j] not in '\r\n':out[j]=' '
            i=end
        else:i+=1
    return ''.join(out)

def lexical_review(r,files,isr_names):
    parsed=[];findings=[];total_bytes=0
    for name in rows(isr_names,40):
        if not re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,99}',name):fail('ASCII_ISR_identifier_required')
    if len(set(isr_names))!=len(isr_names):fail('duplicate_ISR_name')
    for i,f in enumerate(rows(files,6)):
        p='/source_files/'+str(i);obj(f,('id','path','language','content','logical_utf8_sha256','source_reference'))
        text(f['id']);text(f['path'],1000);language=enum(f['language'],('c','cpp','other'));content=text(f['content'],64000)
        total_bytes+=len(content.encode('utf8'))
        if total_bytes>180000:fail('selected_source_text_budget')
        actual=sha(content)
        if hashtext(f['logical_utf8_sha256'])!=actual:fail('logical_UTF8_content_hash_mismatch')
        r.literal(content,p+'/content',[f['source_reference']]);masked=mask_c(content);spans=[];matched_names=[]
        if language in ('c','cpp'):
            for name in isr_names:
                for match in re.finditer(r'\b'+re.escape(name)+r'\s*\([^;{}]*\)\s*\{',masked):
                    start=match.end()-1;depth=1;j=start+1
                    while j<len(masked) and depth:
                        depth+=(masked[j]=='{')-(masked[j]=='}');j+=1
                    if not depth:spans.append((start,j,name));matched_names.append(name)
            rules=[('unbounded_string_API',r'\b(?:strcpy|strcat|sprintf|gets)\s*\(',False),('selected_ISR_blocking_or_nonreentrant_call',r'\b(?:delay|sleep|printf|malloc|free)\s*\(',True),('narrow_cast_before_addition',r'\(\s*(?:uint8_t|int8_t|uint16_t|int16_t)\s*\)\s*[A-Za-z_]\w*\s*\+',False)]
            for rule,pattern,isr_only in rules:
                for match in re.finditer(pattern,masked):
                    handlers=[name for a,b,name in spans if a<=match.start()<b]
                    if isr_only and not handlers:continue
                    line=content.count('\n',0,match.start())+1;original=content.splitlines()[line-1]
                    findings.append(dict(rule=rule,file_id=f['id'],path=f['path'],line=line,source_line_excerpt=original[:4000],excerpt_truncated=len(original)>4000,ISR_contexts=handlers,interpretation='lexical_candidate_not_proven_defect'))
                    if len(findings)>100:fail('bounded_lexical_finding_count')
        else:r.gap('lexical_language_not_supported',p)
        parsed.append(dict(id=f['id'],path=f['path'],language=language,content=content,logical_utf8_sha256=actual,logical_UTF8_bytes=len(content.encode('utf8')),source_reference=f['source_reference'],selected_ISR_bodies_found=sorted(set(matched_names))))
    unique(parsed)
    if len({f['path'] for f in parsed})!=len(parsed):fail('duplicate_logical_source_path')
    found={name for f in parsed for name in f['selected_ISR_bodies_found']}
    for name in set(isr_names)-found:r.gap('selected_ISR_body_not_resolved','/isr_functions/'+name)
    return dict(files=parsed,selected_ISR_functions=deepcopy(isr_names),findings=findings,limitations=['no_preprocessor_or_macro_expansion','no_full_control_flow_or_alias_analysis','volatile_does_not_establish_atomicity_or_memory_order','empty_pattern_result_is_not_clean_code_or_MISRA_conformance'],static_analyzer_executed=False)

def tool_reports(r,values,source_files,p='/tool_reports'):
    out=[];filemap={v['path']:v for v in source_files}
    for i,z in enumerate(rows(values,3)):
        q=p+'/'+str(i);obj(z,('id','format','state','tool','version','source_reference','source_identities'),('run_date','run_source_reference','configuration_sha256','report_text','diagnostics','execution_note'))
        for k in ('id','tool','version'):text(z[k])
        fmt=enum(z['format'],('cppcheck_xml_v2','prepared_compiler_diagnostics'))
        state=enum(z['state'],('provided_complete','provided_partial','provided_failed','not_run'))
        if state!='not_run' and ('run_date' not in z or 'configuration_sha256' not in z):fail('provided_result_run_and_configuration_required')
        if 'run_date' in z and iso(z['run_date'])>r.asof:fail('provided_tool_run_after_information_cutoff')
        if 'configuration_sha256' in z:hashtext(z['configuration_sha256'])
        if 'run_source_reference' in z:ref(z['run_source_reference'])
        ref(z['source_reference']);identities=rows(z['source_identities'],20)
        identity_rows=[]
        for item in identities:
            obj(item,('path','logical_utf8_sha256'));text(item['path'],1000);hashtext(item['logical_utf8_sha256'])
            supplied=filemap.get(item['path']);match=None if supplied is None else supplied['logical_utf8_sha256']==item['logical_utf8_sha256']
            if match is not True:r.gap('tool_report_source_identity_unresolved_or_mismatch',q+'/'+item['path'])
            identity_rows.append(dict(provided=deepcopy(item),matches_selected_logical_text=match))
        if len({x['path'] for x in identities})!=len(identities):fail('duplicate_tool_source_identity')
        diagnostics=[];expected=[]
        if state=='not_run':
            if z.get('report_text') is not None or z.get('diagnostics'):fail('not_run_has_tool_results')
            r.gap('provided_tool_not_run',q)
        else:
            raw=text(z.get('report_text'),64000);r.literal(raw,q+'/report_text',[z['source_reference']]);r.literal(z['run_date'],q+'/run_date',[z.get('run_source_reference',z['source_reference'])])
            if fmt=='cppcheck_xml_v2':
                if re.search(r'<!\s*(?:DOCTYPE|ENTITY)',raw,re.I):fail('XML_DTD_or_ENTITY_forbidden')
                try:root=ET.fromstring(raw)
                except ET.ParseError:fail('invalid_cppcheck_XML')
                nodes=list(root.iter())
                if len(nodes)>1000 or root.tag!='results' or root.attrib.get('version')!='2':fail('unsupported_cppcheck_XML_subset')
                def depth(node,n):
                    if n>10:fail('XML_nesting_limit')
                    for child in node:depth(child,n+1)
                depth(root,0)
                if any(n.tag not in ('results','cppcheck','errors','error','location','symbol') for n in nodes):fail('unsupported_cppcheck_XML_element')
                if root.attrib!={'version':'2'} or [n.tag for n in root]!=['cppcheck','errors']:fail('unsupported_cppcheck_XML_subset')
                cp=root.find('cppcheck')
                if cp is None or cp.attrib.get('version')!=z['version']:fail('tool_version_report_mismatch')
                if set(cp.attrib)!={'version'} or len(cp):fail('unsupported_cppcheck_XML_subset')
                errors=root.find('errors')
                if errors is None:fail('cppcheck_errors_element_required')
                if errors.attrib:fail('unsupported_cppcheck_XML_subset')
                for er in list(errors):
                    if er.tag!='error':fail('unsupported_cppcheck_XML_subset')
                    if set(er.attrib)-{'id','severity','msg','verbose','cwe','inconclusive','remark','file0'}:fail('unsupported_cppcheck_XML_attributes')
                    if any(ch.tag not in ('location','symbol') for ch in er):fail('unsupported_cppcheck_XML_subset')
                    for ch in er:
                        if len(ch) or ch.tag=='symbol' and ch.attrib:fail('unsupported_cppcheck_XML_subset')
                    item=dict(rule=text(er.attrib.get('id')),severity=text(er.attrib.get('severity')),message=text(er.attrib.get('msg')),locations=[])
                    for loc in er.findall('location'):
                        if not {'file','line'}<=set(loc.attrib) or set(loc.attrib)-{'file','line','column','info'}:fail('cppcheck_location_required')
                        item['locations'].append(dict(path=text(loc.attrib['file'],1000),line=loc.attrib['line'],column=loc.attrib.get('column')))
                    expected.append(item)
                if len(expected)>40:fail('tool_diagnostic_budget')
            for j,d in enumerate(rows(z.get('diagnostics',[]),40)):
                pp=q+'/diagnostics/'+str(j);obj(d,('rule','severity','message','locations'))
                for key in ('rule','severity','message'):text(d[key])
                locations=[];rawlocations=[]
                for k,l in enumerate(rows(d['locations'],6)):
                    lp=pp+'/locations/'+str(k);obj(l,('path','line'),('column',));text(l['path'],1000)
                    if l['line']['source_reference']!=z['source_reference'] or 'column' in l and l['column']['source_reference']!=z['source_reference']:fail('tool_location_numeric_source_mismatch')
                    line=r.q(l['line'],lp+'/line',('line',),0,10000000,True,cutoff=z['run_date']);column=r.q(l['column'],lp+'/column',('column',),0,10000000,True,cutoff=z['run_date']) if 'column' in l else None
                    rawlocations.append(dict(path=l['path'],line=str(int(line)),column=None if column is None else str(int(column))))
                    source=filemap.get(l['path']);source_line=None
                    identity_match=next((a['matches_selected_logical_text'] for a in identity_rows if a['provided']['path']==l['path']),None)
                    if source is not None and identity_match is True and 1<=line<=len(source['content'].splitlines()):source_line=source['content'].splitlines()[int(line)-1]
                    else:r.gap('tool_diagnostic_source_line_not_selected_or_resolved',lp)
                    locations.append(dict(path=l['path'],line=line,column=column,source_identity_matches_selected=identity_match,selected_source_line=source_line))
                candidate=dict(rule=d['rule'],severity=d['severity'],message=d['message'],locations=rawlocations)
                if fmt=='cppcheck_xml_v2':
                    if j>=len(expected) or candidate!=expected[j]:fail('normalised_diagnostic_does_not_match_actual_XML')
                else:
                    # Prepared diagnostics are explicitly source text fragments;
                    # no claim that an arbitrary compiler log was parsed.
                    r.literal(d['message'],pp+'/message',[z['source_reference']])
                    for k,l in enumerate(d['locations']):r.literal(l['path'],f'{pp}/locations/{k}/path',[z['source_reference']])
                diagnostics.append(dict(rule=d['rule'],severity=d['severity'],message=d['message'],locations=locations))
            if fmt=='cppcheck_xml_v2' and len(diagnostics)!=len(expected):fail('all_XML_diagnostics_required_no_silent_filtering')
            if state!='provided_complete':r.gap('provided_tool_result_partial_or_failed',q)
        if z.get('execution_note') is not None:text(z['execution_note'])
        out.append(dict(id=z['id'],format=fmt,state=state,tool=z['tool'],version=z['version'],run_date=z.get('run_date'),run_source_reference=z.get('run_source_reference',z['source_reference']) if 'run_date' in z else None,configuration_sha256=z.get('configuration_sha256'),source_reference=z['source_reference'],source_identity_reviews=identity_rows,diagnostics=diagnostics,execution_note=z.get('execution_note'),tool_invoked_here=False,coverage_or_MISRA_conformance_established=False))
    unique(out);return out

def code(r,data):
    obj(data,('as_of','jurisdiction','mode'),('context','source_files','isr_functions','review_records','counter','uart','tool_reports','state_machine','watchdog_note'))
    mode=enum(data['mode'],('questions','draft','review'))
    if mode=='questions' and any(data.get(k) for k in ('source_files','counter','uart','tool_reports')):fail('questions_mode_has_code_calculations')
    review=lexical_review(r,data.get('source_files',[]),data.get('isr_functions',[]))
    records=[]
    topics=('shared_variables_volatile_atomicity','timer_overflow','buffer_bounds','ISR_blocking','peripheral_error_handling','watchdog','state_machine','selected_coding_rules')
    for i,z in enumerate(rows(data.get('review_records',[]),40)):
        obj(z,('id','topic','state','analysis'),('evidence',));text(z['id']);enum(z['topic'],topics);enum(z['state'],('provided_finding','provided_no_finding','unknown','not_applicable'));text(z['analysis'])
        if z['state'] in ('provided_finding','provided_no_finding'):note(r,z.get('evidence'),'/review_records/'+str(i)+'/evidence')
        elif z.get('evidence') is not None:note(r,z['evidence'],'/review_records/'+str(i)+'/evidence')
        records.append(dict(provided=deepcopy(z),independent_confirmation_established=False))
    unique([x['provided'] for x in records])
    if review['files']:
        for topic in topics:
            if not any(z['provided']['topic']==topic for z in records):r.gap('code_review_topic_unresolved','/'+topic)
        if not data.get('context'):r.gap('target_and_compiler_context_not_supplied','/context')
    if data.get('watchdog_note') is not None:text(data['watchdog_note'])
    return dict(mode=mode,context=context(data['context']) if 'context' in data else None,review=review,review_records=records,counter=counter(r,data['counter']) if 'counter' in data else None,uart=uart(r,data['uart']) if 'uart' in data else None,tool_reports=tool_reports(r,data.get('tool_reports',[]),review['files']),state_machine=proposal(r,data['state_machine'],'/state_machine') if 'state_machine' in data else None,watchdog_note=data.get('watchdog_note'),questions=['select_source_fragment_target_compiler_and_expected_behavior','select_only_needed_counter_UART_or_provided_analyzer_branch','supply_ISR_shared_variable_buffer_error_watchdog_context'] if mode=='questions' else [],review_is_not_compilation_or_MISRA_certification=True)

def _run(function,data):
    if type(function) is not str or function not in FUNCTIONS:fail('unknown_architecture_code_function')
    try:
        reject_known_secret_material(data)
        with localcontext(CTX):
            r=Read(data);out=(architecture if function=='fw_architecture' else code)(r,data)
            if len(r.units)+len(r.literals)>900:fail('numeric_literal_budget_900')
            out.update(as_of=r.asof,jurisdiction='RU',evidence_gaps=r.gaps,analysis_only=True,arithmetic_precision='exact_finite_rational_predicates_Decimal180_display_not_measurement_precision',hardware_or_WCET_validation_performed=False,toolchain_executed=False,source_compiled=False,device_programmed=False,device_commands_sent=False)
            return serial(out),r
    except (KeyError,TypeError,AttributeError,IndexError,DecimalException,OverflowError,ZeroDivisionError,RecursionError):raise ValueError('malformed_or_unbounded_architecture_code_input') from None
def execute(function,data):return _run(function,deepcopy(data))[0]
def input_units(function,data):return _run(function,deepcopy(data))[1].units
def selected_texts(function,data):return _run(function,deepcopy(data))[1].literals

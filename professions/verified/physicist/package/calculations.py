"""Bounded local physics arithmetic on supplied records; no solver/code execution.

Exact decimal inputs and 180-digit Decimal arithmetic, with explicit units.
Irrational results are numerical approximations at the stated precision. Source
occurrence, dimensional consistency and numerical agreement establish no mechanism.
"""
import ast
from copy import deepcopy
from datetime import date
from decimal import Decimal,Context,localcontext,DecimalException,ROUND_HALF_UP
from fractions import Fraction
from functools import wraps
import re

D=Decimal
CTX=Context(prec=180,rounding=ROUND_HALF_UP,Emin=-9999,Emax=9999)
ZERO=D(0);ONE=D(1)
FUNCTIONS=('physical_model','numerical_sim','uncertainty')
BASE_DIMENSIONS=('kg','m','s','A','K','mol','cd')
DIM_ZERO=(Fraction(0),)*7

def fail(code):raise ValueError(code)
def obj(value,name,required=(),optional=()):
    if type(value) is not dict:fail(name+'_object_required')
    if required and (not set(required)<=set(value) or set(value)-set(required)-set(optional)):
        fail(name+'_fields')
    return value
def rows(value,name,lo=0,hi=40):
    if type(value) is not list or not lo<=len(value)<=hi:fail(name+'_bounded_list_required')
    return value
def text(value,name,limit=12000):
    if type(value) is not str or not value.strip() or len(value)>limit:fail(name+'_text_required')
    if any(ord(ch)<32 and ch not in '\n\r\t' for ch in value):fail(name+'_control_character')
    return value.strip()
def number(value,name,lo=None,hi=None):
    if type(value) not in (str,int,D) or len(str(value))>160 or not re.fullmatch(r'[+-]?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d{1,3})?',str(value)):
        fail(name+'_exact_scientific_decimal_required')
    n=D(value)
    if not n.is_finite() or len(n.as_tuple().digits)>40 or abs(n)>D('1e100') or n and abs(n)<D('1e-100'):
        fail(name+'_bounded_scientific_decimal_required')
    if lo is not None and n<D(lo) or hi is not None and n>D(hi):fail(name+'_range')
    return n
def integer(value,name,lo=0,hi=1000000000000):
    n=number(value,name,str(lo),str(hi))
    if n!=int(n):fail(name+'_integer_required')
    return int(n)
def boolean(value,name):
    if type(value) is not bool:fail(name+'_boolean_required')
    return value
def day(value,name):
    if type(value) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):fail(name+'_iso_date_required')
    try:return date.fromisoformat(value)
    except ValueError:fail(name+'_invalid_date')
def reference(value):return text(value,'source_reference',200)
def historic(value,name,asof):
    result=day(value,name)
    if result>asof:fail(name+'_after_analysis_cutoff')
    return result
def exact(value):
    if not value.is_finite():fail('nonfinite_derived_value')
    return str(value)
def bounded_result(value):
    if not value.is_finite() or abs(value)>D('1e1000') or value and abs(value)<D('1e-1000'):
        fail('derived_numeric_range_exceeds_1e1000')
    return value
def strings(value,name,lo=0,hi=30):return [text(v,name,6000) for v in rows(value,name,lo,hi)]
def tree(value,depth=0,budget=None):
    if budget is None:budget=[0]
    budget[0]+=1
    if depth>16 or budget[0]>12000:fail('physics_structure_limit')
    if type(value) is dict:
        if len(value)>100 or any(type(k) is not str for k in value):fail('physics_object_keys')
        for item in value.values():tree(item,depth+1,budget)
    elif type(value) is list:
        if len(value)>200:fail('physics_list_limit')
        for item in value:tree(item,depth+1,budget)
    elif type(value) is str:
        if len(value)>30000:fail('physics_text_limit')
    elif value is not None and type(value) not in (bool,int,D):fail('physics_exact_json_values_required')
def guard(fn):
    @wraps(fn)
    def checked(data):
        tree(data)
        with localcontext(CTX):
            data=deepcopy(obj(data,'data'));asof=day(data.get('as_of'),'as_of')
            try:result=fn(data,asof)
            except (KeyError,TypeError,IndexError,AttributeError,OverflowError,RecursionError):
                raise ValueError('invalid_'+fn.__name__+'_structure') from None
            except DecimalException:
                raise ValueError('unsupported_'+fn.__name__+'_numeric_condition') from None
            result.update(as_of=data['as_of'],assisted_draft=True,arithmetic_precision_digits=CTX.prec,
                source_semantics_verified=False,current_legal_applicability_verified=False,
                external_network_used=False,external_code_executed=False,human_review_required=True)
            return result
    return checked

def dim(values):return tuple(Fraction(x) for x in values)
def add_dim(a,b,sign=1):
    result=tuple(x+sign*y for x,y in zip(a,b))
    if any(abs(x)>120 for x in result):fail('dimension_exponent_limit')
    return result
def dimension_record(dimension):return {key:str(value) for key,value in zip(BASE_DIMENSIONS,dimension) if value}

UNITS={'1':(ONE,DIM_ZERO),'rad':(ONE,DIM_ZERO)}
for i,name in enumerate(BASE_DIMENSIONS):UNITS[name]=(ONE,tuple(Fraction(int(j==i)) for j in range(7)))
for name,powers in {
 'Hz':(0,0,-1,0,0,0,0),'N':(1,1,-2,0,0,0,0),'J':(1,2,-2,0,0,0,0),
 'W':(1,2,-3,0,0,0,0),'Pa':(1,-1,-2,0,0,0,0),'C':(0,0,1,1,0,0,0),
 'V':(1,2,-3,-1,0,0,0),'Ohm':(1,2,-3,-2,0,0,0),'F':(-1,-2,4,2,0,0,0),
 'T':(1,0,-2,-1,0,0,0),'H':(1,2,-2,-2,0,0,0)}.items():UNITS[name]=(ONE,dim(powers))
for name,base,power in [('km','m',3),('cm','m',-2),('mm','m',-3),('um','m',-6),('nm','m',-9),
 ('ms','s',-3),('us','s',-6),('ns','s',-9),('g','kg',-3),('mg','kg',-6),('kPa','Pa',3),('MPa','Pa',6),
 ('mV','V',-3),('uV','V',-6),('mA','A',-3),('uA','A',-6)]:UNITS[name]=(D(10)**power,UNITS[base][1])
UNITS['min']=(D(60),UNITS['s'][1]);UNITS['h']=(D(3600),UNITS['s'][1])
UNITS['eV']=(D('1.602176634e-19'),UNITS['J'][1])

def parsed(expression,name='expression',limit=500):
    expression=text(expression,name,limit)
    try:root=ast.parse(expression,mode='eval')
    except (SyntaxError,ValueError,RecursionError):fail(name+'_unsupported_syntax')
    if len(list(ast.walk(root)))>120:fail(name+'_node_limit')
    return expression,root.body

def unit(value):
    expression,node=parsed(value,'unit',250)
    def visit(n):
        if type(n) is ast.Name and n.id in UNITS:return UNITS[n.id]
        if type(n) is ast.Constant and type(n.value) is int and n.value==1:return ONE,DIM_ZERO
        if type(n) is ast.BinOp and type(n.op) in (ast.Mult,ast.Div):
            a,da=visit(n.left);b,db=visit(n.right)
            return (bounded_result(a*b),add_dim(da,db)) if type(n.op) is ast.Mult else (bounded_result(a/b),add_dim(da,db,-1))
        if type(n) is ast.BinOp and type(n.op) is ast.Pow:
            a,da=visit(n.left)
            exponent=n.right
            sign=-1 if type(exponent) is ast.UnaryOp and type(exponent.op) is ast.USub else 1
            base=exponent.operand if sign==-1 else exponent
            if type(base) is not ast.Constant or type(base.value) is not int or abs(base.value)>12:fail('unit_integer_exponent_required')
            p=sign*base.value
            return bounded_result(a**p),tuple(x*p for x in da)
        fail('unsupported_unit_atom_or_syntax')
    return visit(node)

class DimensionError(ValueError):pass

def _literal_fraction(node,source,depth=0):
    if depth>12:fail('literal_exponent_depth_limit')
    if type(node) is ast.Constant and type(node.value) in (int,float):
        result=Fraction(number(ast.get_source_segment(source,node),'exponent_literal'))
    elif type(node) is ast.UnaryOp and type(node.op) in (ast.UAdd,ast.USub):
        result=_literal_fraction(node.operand,source,depth+1)
        if type(node.op) is ast.USub:result=-result
    elif type(node) is ast.BinOp and type(node.op) in (ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow):
        left=_literal_fraction(node.left,source,depth+1);right=_literal_fraction(node.right,source,depth+1)
        if type(node.op) is ast.Add:result=left+right
        elif type(node.op) is ast.Sub:result=left-right
        elif type(node.op) is ast.Mult:result=left*right
        elif type(node.op) is ast.Div:
            if right==0:fail('literal_exponent_division_by_zero')
            result=left/right
        else:
            if right.denominator!=1 or abs(right)>12:fail('literal_exponent_power_limit')
            if left==0 and right<=0:fail('literal_exponent_zero_power')
            result=left**right.numerator
    else:fail('dimensioned_power_requires_literal_rational_exponent')
    if result.numerator.bit_length()>4096 or result.denominator.bit_length()>4096:fail('literal_exponent_size_limit')
    return result

def evaluate(expression,symbols):
    source,root=parsed(expression);trace=[]
    def emit(node,value,dimension):
        bounded_result(value)
        if any(abs(x)>120 for x in dimension):fail('dimension_exponent_limit')
        trace.append(dict(expression=ast.get_source_segment(source,node),value_si=exact(value),dimension=dimension_record(dimension)))
        return value,dimension
    def visit(node):
        if type(node) is ast.Constant and type(node.value) in (int,float):
            literal=ast.get_source_segment(source,node)
            return emit(node,number(literal,'formula_literal'),DIM_ZERO)
        if type(node) is ast.Name:
            if node.id not in symbols:fail('undefined_formula_symbol:'+node.id)
            if symbols[node.id][0] is None:fail('uncomputed_declared_output_in_numeric_expression:'+node.id)
            return emit(node,*symbols[node.id])
        if type(node) is ast.UnaryOp and type(node.op) in (ast.UAdd,ast.USub):
            value,dimension=visit(node.operand)
            return emit(node,-value if type(node.op) is ast.USub else value,dimension)
        if type(node) is ast.BinOp and type(node.op) in (ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow):
            a,da=visit(node.left);b,db=visit(node.right)
            if type(node.op) in (ast.Add,ast.Sub):
                if da!=db:raise DimensionError('addition_or_subtraction_dimension_mismatch')
                return emit(node,a+b if type(node.op) is ast.Add else a-b,da)
            if type(node.op) is ast.Mult:return emit(node,a*b,add_dim(da,db))
            if type(node.op) is ast.Div:
                if b==0:fail('formula_division_by_zero')
                return emit(node,a/b,add_dim(da,db,-1))
            if db!=DIM_ZERO:raise DimensionError('dimensioned_exponent')
            if abs(b)>12:fail('formula_exponent_limit')
            p=_literal_fraction(node.right,source) if da!=DIM_ZERO else Fraction(b)
            if da!=DIM_ZERO and (p.denominator>12 or abs(p)>12):fail('dimensioned_power_requires_small_literal_rational_exponent')
            exponent=D(p.numerator)/D(p.denominator)
            if a==0 and p<=0:fail('zero_nonpositive_power_not_supported')
            if a<0:
                if p.denominator%2==0:fail('negative_even_root_not_real')
                value=(-a)**exponent
                if p.numerator%2:value=-value
            else:value=a**exponent
            return emit(node,value,tuple(x*p for x in da))
        if type(node) is ast.Call and type(node.func) is ast.Name and node.func.id in ('sqrt','abs','exp','ln') and len(node.args)==1 and not node.keywords:
            value,dimension=visit(node.args[0]);fn=node.func.id
            if fn=='abs':return emit(node,abs(value),dimension)
            if fn=='sqrt':
                if value<0:fail('sqrt_domain')
                return emit(node,value.sqrt(),tuple(x/2 for x in dimension))
            if dimension!=DIM_ZERO:raise DimensionError('transcendental_argument_must_be_dimensionless')
            if fn=='ln':
                if value<=0:fail('ln_positive_argument_required')
                return emit(node,value.ln(),DIM_ZERO)
            if abs(value)>2000:fail('exp_argument_limit')
            return emit(node,value.exp(),DIM_ZERO)
        fail('unsupported_formula_ast_node')
    value,dimension=visit(root)
    return value,dimension,trace

def _symbols(data,asof):
    symbols={};inventory=[]
    for kind,key,maximum in (('variable','variables',20),('constant','constants',10)):
        for row in rows(data.get(key),key,1 if key=='variables' else 0,maximum):
            required=('symbol','value','unit','source_reference','observation_date') if kind=='variable' else ('symbol','name','value','unit','kind','edition','publication_date','source_reference')
            row=obj(row,kind,required)
            symbol=text(row['symbol'],'symbol',50)
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,49}',symbol) or symbol in ('sqrt','abs','exp','ln') or symbol in symbols:fail('unique_supported_symbol_required')
            reference(row['source_reference']);n=number(row['value'],symbol);factor,dimension=unit(row['unit'])
            if kind=='variable':historic(row['observation_date'],'observation_date',asof)
            else:
                text(row['name'],'constant_name',500);text(row['edition'],'constant_edition',500)
                historic(row['publication_date'],'constant_publication_date',asof)
                if row['kind'] not in ('codata_adjusted','si_defining','conventional','local_measured','mathematical','supplied_model_parameter'):fail('constant_kind_required')
                if symbol in ('g','g_n') and row['kind'] in ('codata_adjusted','si_defining'):fail('gravity_is_not_a_codata_adjusted_or_si_defining_constant')
            symbols[symbol]=(bounded_result(n*factor),dimension)
            inventory.append(dict(row,value_si=exact(n*factor),dimension=dimension_record(dimension),record_kind=kind))
    for row in rows(data.get('declared_outputs',[]),'declared_outputs',0,6):
        obj(row,'declared_output',('symbol','unit','source_reference'));reference(row['source_reference'])
        symbol=text(row['symbol'],'declared_output_symbol',50)
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,49}',symbol) or symbol in symbols or symbol in ('sqrt','abs','exp','ln'):
            fail('unique_supported_symbol_required')
        _,dimension=unit(row['unit']);symbols[symbol]=(None,dimension)
        inventory.append(dict(row,value_si=None,dimension=dimension_record(dimension),record_kind='declared_output',
                              observation_status='not_supplied_no_value_invented'))
    return symbols,inventory

def _equation(row,symbols):
    obj(row,'equation',('id','lhs','rhs','target_unit','source_reference'));reference(row['source_reference'])
    text(row['id'],'equation_id',100);target_factor,target_dim=unit(row['target_unit'])
    values={};errors={};traces={};unobserved_lhs=False
    for side in ('lhs','rhs'):
        try:
            source,node=parsed(row[side])
            if side=='lhs' and type(node) is ast.Name and node.id in symbols and symbols[node.id][0] is None:
                value,dimension=symbols[node.id];unobserved_lhs=True
                trace=[dict(expression=source,value_si=None,dimension=dimension_record(dimension),observation_status='not_supplied_declared_output')]
            else:value,dimension,trace=evaluate(row[side],symbols)
            values[side]=(value,dimension);traces[side]=trace
        except DimensionError as exc:errors[side]=str(exc);traces[side]=[]
    consistent=not errors and values['lhs'][1]==values['rhs'][1]
    target_ok=not errors and values['rhs'][1]==target_dim
    result=dict(id=row['id'],lhs=row['lhs'],rhs=row['rhs'],target_unit=row['target_unit'],
        lhs_value_si=exact(values['lhs'][0]) if 'lhs' in values and values['lhs'][0] is not None else None,rhs_value_si=exact(values['rhs'][0]) if 'rhs' in values else None,
        lhs_dimension=dimension_record(values['lhs'][1]) if 'lhs' in values else None,
        rhs_dimension=dimension_record(values['rhs'][1]) if 'rhs' in values else None,
        dimension_consistent=bool(consistent),dimension_errors=errors,target_unit_compatible=bool(target_ok),
        residual_si=exact(values['lhs'][0]-values['rhs'][0]) if consistent and values['lhs'][0] is not None else None,
        value_in_target_unit=exact(values['rhs'][0]/target_factor) if target_ok else None,
        expression_trace=traces,source_reference=row['source_reference'])
    if unobserved_lhs:
        result.update(lhs_observation_status='not_supplied_declared_output',numeric_comparison_performed=False,
            residual_status='not_computed_without_lhs_observation',
            rhs_decimal_order_of_magnitude=values['rhs'][0].copy_abs().adjusted() if 'rhs' in values and values['rhs'][0] else None)
    return result

@guard
def physical_model(c,asof):
    obj(c,'physical_model',('as_of','system','target','assumptions','applicability_limits','variables','constants','equations','limiting_cases','dimensionless_parameters','scale_checks'),('declared_outputs',))
    text(c['system'],'system');text(c['target'],'target');assumptions=strings(c['assumptions'],'assumptions',1)
    applicability=strings(c['applicability_limits'],'applicability_limits',1)
    symbols,inventory=_symbols(c,asof);equations=[];byid={}
    for row in rows(c['equations'],'equations',1,6):
        result=_equation(row,symbols)
        if result['id'] in byid:fail('duplicate_equation_id')
        byid[result['id']]=row;equations.append(result)
    limits=[]
    for row in rows(c['limiting_cases'],'limiting_cases',1,8):
        obj(row,'limit_probe',('id','equation_id','description','overrides','expected_rhs','absolute_tolerance','source_reference'))
        text(row['id'],'limit_id',100);text(row['description'],'limit_description');reference(row['source_reference'])
        if row['equation_id'] not in byid:fail('unknown_limit_equation')
        overridden=deepcopy(symbols);seen=set()
        for change in rows(row['overrides'],'limit_overrides',1,5):
            obj(change,'override',('symbol','value','unit','source_reference'));reference(change['source_reference'])
            name=change['symbol']
            if name not in symbols or name in seen:fail('unique_known_override_symbol_required')
            seen.add(name);factor,dimension=unit(change['unit'])
            if dimension!=symbols[name][1]:fail('override_dimension_mismatch')
            if symbols[name][0] is None:fail('limit_override_cannot_invent_declared_output_observation')
            overridden[name]=(number(change['value'],'override_value')*factor,dimension)
        expected=obj(row['expected_rhs'],'expected_rhs',('value','unit'));factor,dimension=unit(expected['unit'])
        target=number(expected['value'],'limit_expected')*factor;tolerance=number(row['absolute_tolerance'],'limit_absolute_tolerance','0')*factor
        evaluated=_equation(byid[row['equation_id']],overridden)
        match=evaluated['rhs_dimension']==dimension_record(dimension) and evaluated['rhs_value_si'] is not None
        difference=D(evaluated['rhs_value_si'])-target if match else None
        limits.append(dict(id=row['id'],description=row['description'],equation_id=row['equation_id'],overrides=deepcopy(row['overrides']),
            computed_rhs_si=evaluated['rhs_value_si'],expected_rhs_si=exact(target),absolute_tolerance_si=exact(tolerance),
            signed_difference_si=exact(difference) if difference is not None else None,
            within_selected_tolerance=abs(difference)<=tolerance if difference is not None else None,
            interpretation='finite_selected_probe_not_a_symbolic_or_asymptotic_limit_proof',source_reference=row['source_reference']))
    groups=[]
    for row in rows(c['dimensionless_parameters'],'dimensionless_parameters',0,6):
        obj(row,'dimensionless_parameter',('id','expression','source_reference'));reference(row['source_reference'])
        value,dimension,trace=evaluate(row['expression'],symbols)
        groups.append(dict(id=text(row['id'],'dimensionless_id',100),expression=row['expression'],value=exact(value),
            dimension=dimension_record(dimension),is_dimensionless=dimension==DIM_ZERO,expression_trace=trace,source_reference=row['source_reference']))
    scales=[]
    for row in rows(c['scale_checks'],'scale_checks',1,10):
        obj(row,'scale_check',('symbol','minimum','maximum','unit','rationale','source_reference'));reference(row['source_reference']);text(row['rationale'],'scale_rationale')
        if row['symbol'] not in symbols:fail('unknown_scale_symbol')
        factor,dimension=unit(row['unit']);lower=number(row['minimum'],'scale_minimum')*factor;upper=number(row['maximum'],'scale_maximum')*factor
        if lower>upper or dimension!=symbols[row['symbol']][1]:fail('scale_range_or_dimension_mismatch')
        value=symbols[row['symbol']][0]
        if value is None:fail('scale_check_requires_supplied_input_value')
        scales.append(dict(row,value_si=exact(value),minimum_si=exact(lower),maximum_si=exact(upper),within_selected_range=lower<=value<=upper,
            decimal_order_of_magnitude=value.copy_abs().adjusted() if value else None))
    result=dict(system=c['system'],target=c['target'],assumptions=assumptions,applicability_limits=applicability,
        quantity_inventory=inventory,constant_inventory=[r for r in inventory if r['record_kind']=='constant'],equations=equations,
        dimensions_consistent=all(r['dimension_consistent'] and r['target_unit_compatible'] for r in equations),
        limiting_cases=limits,dimensionless_parameters=groups,scale_checks=scales,
        mechanism_not_proven_by_single_fit=True,no_symbolic_limit_proof=True,
        supported_expression_language='bounded_arithmetic_sqrt_abs_exp_ln_no_eval_no_attributes_no_indexing')
    if c.get('declared_outputs'):
        result['declared_outputs']=deepcopy([row for row in inventory if row['record_kind']=='declared_output'])
        result['evidence_gaps']=['lhs_observation_not_supplied:'+row['symbol'] for row in result['declared_outputs']]
    return result

def _problem(value):
    fields=('equations','geometry','boundary_conditions','initial_conditions','materials','code','version','method','stop_criterion','source_reference')
    value=obj(value,'problem',fields);reference(value['source_reference'])
    strings(value['equations'],'problem_equations',1,8)
    for key in fields[1:-1]:text(value[key],'problem_'+key,6000)
    return deepcopy(value)

def _benchmark(value,actual,quantity_unit,asof):
    value=obj(value,'benchmark',('reference_value','absolute_tolerance','relative_tolerance','source_reference','observation_date'))
    reference(value['source_reference']);historic(value['observation_date'],'benchmark_observation_date',asof)
    expected=number(value['reference_value'],'benchmark_reference');atol=number(value['absolute_tolerance'],'absolute_tolerance','0')
    rtol=number(value['relative_tolerance'],'relative_tolerance','0','10')
    difference=actual-expected;allowance=atol+rtol*abs(expected)
    return dict(reference_value=exact(expected),actual=exact(actual),unit=quantity_unit,
        signed_difference=exact(difference),absolute_difference=exact(abs(difference)),
        relative_difference=exact(difference/abs(expected)) if expected else None,
        reference_is_zero=expected==0,selected_allowance=exact(allowance),absolute_tolerance=exact(atol),relative_tolerance=exact(rtol),
        within_selected_tolerance=abs(difference)<=allowance,source_reference=value['source_reference'],observation_date=value['observation_date'],
        agreement_is_not_model_validation=True)

@guard
def numerical_sim(c,asof):
    mode=c.get('mode')
    if mode not in ('refinement_review','monte_carlo_review'):fail('supported_numerical_sim_mode_required')
    required=('as_of','mode','problem','quantity_unit','benchmark','refinement' if mode=='refinement_review' else 'monte_carlo')
    obj(c,'numerical_sim',required);problem=_problem(c['problem']);unit(c['quantity_unit'])
    grid=[];pairs=[];triplets=[];mc=None;gaps=[]
    if mode=='refinement_review':
        r=obj(c['refinement'],'refinement',('axis','h_unit','levels','ratio_relative_tolerance','expected_order','assumptions','source_reference'))
        reference(r['source_reference']);_,hd=unit(r['h_unit'])
        if r['axis'] not in ('space','time','parameter'):fail('refinement_axis_required')
        if r['axis']=='space' and hd!=UNITS['m'][1] or r['axis']=='time' and hd!=UNITS['s'][1]:fail('refinement_axis_unit_mismatch')
        tolerance=number(r['ratio_relative_tolerance'],'ratio_relative_tolerance','0','0.01')
        expected_order=number(r['expected_order'],'expected_order','1e-100','20')
        assumptions=obj(r['assumptions'],'refinement_assumptions',('same_model','same_scheme','iterative_error_negligible','asymptotic_range_claimed'))
        for key in assumptions:
            if not boolean(assumptions[key],key):gaps.append('selected_assumption_not_established:'+key)
        previous=None;ids=set();raw=[]
        for row in rows(r['levels'],'grid_levels',3,8):
            obj(row,'grid_level',('id','h','value','source_reference'));reference(row['source_reference']);identity=text(row['id'],'grid_id',100)
            if identity in ids:fail('duplicate_grid_id')
            ids.add(identity);h=number(row['h'],'grid_h','1e-100');value=number(row['value'],'grid_value')
            if previous is not None and h>=previous:fail('ordered_strictly_decreasing_real_h_required')
            raw.append((h,value));grid.append(dict(id=identity,h=exact(h),h_unit=r['h_unit'],value=exact(value),source_reference=row['source_reference']));previous=h
        for i in range(len(raw)-1):
            h0,v0=raw[i];h1,v1=raw[i+1]
            pairs.append(dict(coarse_id=grid[i]['id'],fine_id=grid[i+1]['id'],refinement_ratio=exact(h0/h1),signed_change=exact(v1-v0)))
        for i in range(len(raw)-2):
            h0,v0=raw[i];h1,v1=raw[i+1];h2,v2=raw[i+2]
            r1=h0/h1;r2=h1/h2;dc=v0-v1;df=v1-v2
            ratio_compatible=abs(r1-r2)<=max(r1,r2)*tolerance
            order=None;candidate=None;expected_candidate=None;error=None
            if not ratio_compatible:status='unequal_refinement_ratios_no_richardson'
            elif dc==0 and df==0:status='identical_values_no_order_evidence'
            elif dc==0 or df==0:status='zero_change_no_order_estimate'
            elif dc*df<0:status='oscillatory_changes_no_monotone_richardson'
            elif abs(df)>=abs(dc):status='noncontracting_changes_no_convergence_evidence'
            else:
                order=(abs(dc)/abs(df)).ln()/r2.ln()
                if order<=0:status='nonpositive_observed_order'
                elif not all(assumptions.values()):status='contracting_changes_assumptions_not_established'
                else:
                    status='conditional_richardson_estimate'
                    candidate=bounded_result(v2+(v2-v1)/(r2**order-ONE))
                    expected_candidate=bounded_result(v2+(v2-v1)/(r2**expected_order-ONE))
                    error=abs(candidate-v2)
            triplets.append(dict(level_ids=[row['id'] for row in grid[i:i+3]],status=status,
                coarse_ratio=exact(r1),fine_ratio=exact(r2),ratios_compatible=ratio_compatible,
                selected_ratio_tolerance=exact(tolerance),unequal_ratios_accepted_as_approximation=ratio_compatible and r1!=r2,
                change_ratio=exact(df/dc) if dc else None,observed_order=exact(order) if order is not None else None,
                expected_order=exact(expected_order),order_minus_expected=exact(order-expected_order) if order is not None else None,
                extrapolated_value=exact(candidate) if candidate is not None else None,
                expected_order_extrapolated_value=exact(expected_candidate) if expected_candidate is not None else None,
                estimated_fine_discretization_error=exact(error) if error is not None else None,
                conditional_on_selected_assumptions=True))
        actual=raw[-1][1]
        refinement=dict(axis=r['axis'],h_unit=r['h_unit'],assumptions=deepcopy(assumptions),source_reference=r['source_reference'])
    else:
        m=obj(c['monte_carlo'],'monte_carlo',('events','seed','engine','engine_version','physics_model_version','mean','sample_standard_deviation','iid_assumption','source_reference','observation_date'))
        reference(m['source_reference']);historic(m['observation_date'],'mc_observation_date',asof)
        for key in ('engine','engine_version','physics_model_version'):text(m[key],key,1000)
        n=integer(m['events'],'events',2,1000000000000);seed=integer(m['seed'],'seed',0,18446744073709551615)
        mean=number(m['mean'],'mc_mean');sd=number(m['sample_standard_deviation'],'mc_sample_sd','0')
        iid=boolean(m['iid_assumption'],'iid_assumption');error=sd/D(n).sqrt()
        if not iid:gaps.append('iid_standard_error_model_not_established')
        mc=dict(events=n,seed=seed,engine=m['engine'],engine_version=m['engine_version'],physics_model_version=m['physics_model_version'],
            mean=exact(mean),sample_standard_deviation=exact(sd),standard_error=exact(error),unit=c['quantity_unit'],
            standard_error_model='supplied_unweighted_iid_sample_mean_s_over_sqrt_N',iid_assumption=iid,
            standard_error_applicability_established=False,source_reference=m['source_reference'],observation_date=m['observation_date'],
            random_stream_recreated=False,event_generation_performed=False)
        actual=mean;refinement=None
    return dict(mode=mode,problem=problem,quantity_unit=c['quantity_unit'],grid_levels=grid,
        refinement=refinement,refinement_pairs=pairs,richardson_triplets=triplets,
        benchmark=_benchmark(c['benchmark'],actual,c['quantity_unit'],asof),monte_carlo=mc,evidence_gaps=gaps,
        convergence_proven=False,no_solver_execution=True,no_cluster_execution=True,
        reproducibility_scope='review_of_supplied_results_versions_and_seed_not_reexecution')

def _fraction_decimal(value):
    return D(value.numerator)/D(value.denominator)

def _psd(matrix):
    # Exact rational LDL^T on the supplied finite decimal correlations. It accepts
    # singular PSD matrices but never clips a negative eigenvalue or correlation.
    n=len(matrix);lower=[[Fraction(0) for _ in range(n)] for _ in range(n)];diagonal=[]
    for j in range(n):
        pivot=Fraction(matrix[j][j])-sum((lower[j][k]**2*diagonal[k] for k in range(j)),Fraction(0))
        if pivot<0:fail('correlation_matrix_not_positive_semidefinite')
        diagonal.append(pivot);lower[j][j]=Fraction(1)
        for i in range(j+1,n):
            residual=Fraction(matrix[i][j])-sum((lower[i][k]*lower[j][k]*diagonal[k] for k in range(j)),Fraction(0))
            if pivot==0:
                if residual!=0:fail('correlation_matrix_not_positive_semidefinite')
            else:lower[i][j]=residual/pivot

def _sample(values):
    n=len(values);mean=sum(values,ZERO)/n
    variance=sum(((v-mean)**2 for v in values),ZERO)/(n-1)
    return mean,variance,variance.sqrt()

def _budget(value,output_unit,asof):
    value=obj(value,'budget',('estimate','components','correlation','coverage_factor','coverage_statement','reporting_digits','source_reference'))
    reference(value['source_reference']);text(value['coverage_statement'],'coverage_statement',5000)
    nominal=number(value['estimate'],'measurand_estimate');k=number(value['coverage_factor'],'coverage_factor','1e-100','100')
    digits=integer(value['reporting_digits'],'reporting_digits',1,3)
    out_factor,out_dimension=unit(output_unit);prepared=[];signed=[];standard=[];sensitivities=[];ids=set()
    for row in rows(value['components'],'uncertainty_components',1,8):
        row=obj(row,'uncertainty_component');identity=text(row.get('id'),'component_id',100)
        if identity in ids:fail('duplicate_uncertainty_component_id')
        ids.add(identity);reference(row.get('source_reference'));reference(row.get('sensitivity_reference'))
        input_factor,input_dimension=unit(row.get('unit'));sensitivity_factor,sensitivity_dimension=unit(row.get('sensitivity_unit'))
        if add_dim(input_dimension,sensitivity_dimension)!=out_dimension:fail('sensitivity_unit_incompatible_with_measurand')
        sensitivity=number(row.get('sensitivity'),'signed_sensitivity');kind=row.get('type');distribution=row.get('distribution')
        common=('id','type','distribution','unit','sensitivity','sensitivity_unit','source_reference','sensitivity_reference')
        sd=None;variance=None;n=None
        if kind=='A':
            obj(row,'type_A_component',(*common,'observations'))
            if distribution!='sample_mean':fail('type_A_requires_sample_mean_distribution')
            samples=[number(v,'type_A_observation') for v in rows(row['observations'],'type_A_observations',2,30)]
            estimate,variance,sd=_sample(samples);n=len(samples);u=sd/D(n).sqrt()
        elif kind=='B':
            estimate=number(row.get('estimate'),'type_B_estimate')
            if distribution=='standard':
                obj(row,'type_B_standard',(*common,'estimate','standard_uncertainty'));u=number(row['standard_uncertainty'],'standard_uncertainty','0')
            elif distribution in ('rectangular','triangular'):
                obj(row,'type_B_width',(*common,'estimate','half_width'));width=number(row['half_width'],'half_width','0')
                u=width/(D(3) if distribution=='rectangular' else D(6)).sqrt()
            elif distribution=='normal_expanded':
                obj(row,'type_B_expanded',(*common,'estimate','expanded_uncertainty','coverage_factor'))
                u=number(row['expanded_uncertainty'],'type_B_expanded','0')/number(row['coverage_factor'],'type_B_coverage','1e-100','100')
            else:fail('supported_type_B_distribution_required')
        else:fail('uncertainty_component_type_A_or_B_required')
        contribution=bounded_result(u*input_factor*sensitivity*sensitivity_factor/out_factor)
        standard.append(u);signed.append(contribution);sensitivities.append(sensitivity)
        prepared.append(dict(id=identity,type=kind,distribution=distribution,estimate=exact(estimate),unit=row['unit'],
            standard_uncertainty=exact(u),sensitivity=exact(sensitivity),sensitivity_unit=row['sensitivity_unit'],
            signed_contribution=exact(contribution),variance_contribution=exact(contribution**2),output_unit=output_unit,
            repeat_count=n,sample_standard_deviation=exact(sd) if sd is not None else None,
            source_reference=row['source_reference'],sensitivity_reference=row['sensitivity_reference']))
    corr=obj(value['correlation'],'correlation',('matrix','source_reference'));reference(corr['source_reference']);n=len(prepared)
    matrix=[]
    for line in rows(corr['matrix'],'correlation_matrix',n,n):
        matrix.append([number(v,'correlation','-1','1') for v in rows(line,'correlation_row',n,n)])
    for i in range(n):
        if matrix[i][i]!=1:fail('unit_diagonal_correlation_required')
        for j in range(n):
            if matrix[i][j]!=matrix[j][i]:fail('symmetric_correlation_matrix_required')
    _psd(matrix)
    # Compute the quadratic form exactly on the finite Decimal contribution
    # approximations, avoiding a spurious negative residual from cancellation.
    variance=sum((Fraction(signed[i])*Fraction(signed[j])*Fraction(matrix[i][j]) for i in range(n) for j in range(n)),Fraction(0))
    if variance<0:fail('negative_combined_variance')
    combined_variance=_fraction_decimal(variance);combined=combined_variance.sqrt();expanded=combined*k
    rounded=None
    if expanded:
        exponent=expanded.adjusted()-digits+1;quantum=ONE.scaleb(exponent)
        with localcontext(Context(prec=1500,rounding=ROUND_HALF_UP,Emin=-9999,Emax=9999)):
            rounded=dict(estimate=exact(nominal.quantize(quantum)),expanded_uncertainty=exact(expanded.quantize(quantum)),
                quantum=exact(quantum),uncertainty_significant_digits=digits,method='selected_half_up_reporting_both_at_same_decimal_place')
    covariance=[[exact(standard[i]*standard[j]*matrix[i][j]) for j in range(n)] for i in range(n)]
    output_covariance=[[exact(signed[i]*signed[j]*matrix[i][j]) for j in range(n)] for i in range(n)]
    return dict(estimate=exact(nominal),output_unit=output_unit,components=prepared,correlation_matrix=[[exact(v) for v in line] for line in matrix],
        correlation_source_reference=corr['source_reference'],input_covariance_matrix=covariance,
        input_covariance_units=[[prepared[i]['unit']+'*'+prepared[j]['unit'] for j in range(n)] for i in range(n)],
        signed_output_covariance_matrix=output_covariance,combined_variance=exact(combined_variance),
        combined_standard_uncertainty=exact(combined),coverage_factor=exact(k),expanded_uncertainty=exact(expanded),
        coverage_statement=value['coverage_statement'],reported_result=rounded,
        reporting_gaps=[] if rounded else ['zero_expanded_uncertainty_no_rounding_basis'],
        propagation='first_order_linearized_GUM_with_supplied_signed_sensitivities',
        sensitivities_symbolically_verified=False,coverage_probability_not_inferred=True,type_A_counted_only_once_per_component=True,
        psd_method='exact_rational_LDL_on_selected_decimal_correlations',source_reference=value['source_reference'])

def _fit(value,asof):
    value=obj(value,'weighted_linear_fit',('x_unit','y_unit','sigma_mode','points','normalized_residual_threshold','assumptions','source_reference'))
    reference(value['source_reference']);unit(value['x_unit']);unit(value['y_unit'])
    if value['sigma_mode'] not in ('absolute_standard','relative_weights'):fail('explicit_sigma_mode_required')
    assumptions=obj(value['assumptions'],'fit_assumptions',('independent_errors','gaussian_errors','x_uncertainty_negligible'))
    gaps=['fit_assumption_not_established:'+k for k,v in assumptions.items() if not boolean(v,k)]
    threshold=number(value['normalized_residual_threshold'],'normalized_residual_threshold','1e-100','1000000')
    points=[];ids=set()
    for row in rows(value['points'],'fit_points',2,80):
        obj(row,'fit_point',('id','x','y','sigma','source_reference'));reference(row['source_reference']);identity=text(row['id'],'point_id',100)
        if identity in ids:fail('duplicate_fit_point_id')
        ids.add(identity);points.append((identity,number(row['x'],'fit_x'),number(row['y'],'fit_y'),number(row['sigma'],'fit_sigma','1e-100'),row['source_reference']))
    weights=[ONE/p[3]**2 for p in points];sw=sum(weights,ZERO)
    xbar=sum((w*p[1] for w,p in zip(weights,points)),ZERO)/sw;ybar=sum((w*p[2] for w,p in zip(weights,points)),ZERO)/sw
    sxx=sum((w*(p[1]-xbar)**2 for w,p in zip(weights,points)),ZERO)
    sxy=sum((w*(p[1]-xbar)*(p[2]-ybar) for w,p in zip(weights,points)),ZERO)
    if sxx<=0:fail('fit_requires_distinct_x_and_nonsingular_design')
    slope=sxy/sxx;intercept=ybar-slope*xbar;chi2=ZERO;residuals=[]
    for identity,x,y,sigma,ref_ in points:
        fitted=ybar+slope*(x-xbar);residual=y-fitted;normalized=residual/sigma;chi2+=normalized**2
        residuals.append(dict(id=identity,x=exact(x),y=exact(y),sigma=exact(sigma),fitted=exact(fitted),residual=exact(residual),
            normalized_residual=exact(normalized),flagged=abs(normalized)>threshold,source_reference=ref_))
    ndf=len(points)-2;reduced=chi2/ndf if ndf else None
    multiplier=ONE if value['sigma_mode']=='absolute_standard' else reduced
    covariance=None
    if multiplier is not None:
        covariance=[[exact(multiplier*(ONE/sw+xbar*xbar/sxx)),exact(-multiplier*xbar/sxx)],
                    [exact(-multiplier*xbar/sxx),exact(multiplier/sxx)]]
    else:gaps.append('relative_covariance_undefined_at_zero_degrees_of_freedom')
    return dict(model='y=intercept+slope*x',x_unit=value['x_unit'],y_unit=value['y_unit'],sigma_mode=value['sigma_mode'],
        slope=exact(slope),slope_unit=value['y_unit']+'/('+value['x_unit']+')',intercept=exact(intercept),
        parameter_covariance_order=['intercept','slope'],parameter_covariance=covariance,
        chi2=exact(chi2),ndf=ndf,chi2_ndf=exact(reduced) if reduced is not None else None,residuals=residuals,
        normalized_residual_threshold=exact(threshold),flagged_ids=[r['id'] for r in residuals if r['flagged']],
        assumptions=deepcopy(assumptions),evidence_gaps=gaps,automatically_excluded_points=[],
        x_uncertainty_and_correlated_y_errors_not_fitted=True,p_value_not_computed=True,source_reference=value['source_reference'])

def _qc(value,asof):
    value=obj(value,'qc',('unit','observations','reference_value','control_standard_deviation','threshold_sigma','control_basis','source_reference'))
    reference(value['source_reference']);unit(value['unit'])
    if value['control_basis']!='selected_reference_not_estimated_from_this_series':fail('independent_selected_qc_reference_required')
    target=number(value['reference_value'],'qc_reference');control=number(value['control_standard_deviation'],'control_sd','1e-100')
    threshold=number(value['threshold_sigma'],'qc_threshold','1e-100','1000000');samples=[];ids=set()
    for row in rows(value['observations'],'qc_observations',2,80):
        obj(row,'qc_observation',('id','value','source_reference'));reference(row['source_reference']);identity=text(row['id'],'qc_id',100)
        if identity in ids:fail('duplicate_qc_id')
        ids.add(identity);samples.append((identity,number(row['value'],'qc_value'),row['source_reference']))
    values=[r[1] for r in samples];mean,variance,sd=_sample(values);n=len(values)
    center=D(n-1)/2;denominator=sum(((D(i)-center)**2 for i in range(n)),ZERO)
    trend=sum(((D(i)-center)*(v-mean) for i,v in enumerate(values)),ZERO)/denominator
    autocov=sum(((values[i]-mean)*(values[i-1]-mean) for i in range(1,n)),ZERO)
    total_sq=sum(((v-mean)**2 for v in values),ZERO)
    points=[dict(id=identity,value=exact(v),standardized_difference=exact((v-target)/control),
        flagged=abs((v-target)/control)>threshold,source_reference=ref_) for identity,v,ref_ in samples]
    return dict(unit=value['unit'],n=n,mean=exact(mean),sample_standard_deviation=exact(sd),standard_error_of_mean=exact(sd/D(n).sqrt()),
        standard_error_model='iid_sample_mean_s_over_sqrt_N_assumption_not_established',standard_error_applicability_established=False,
        reference_value=exact(target),control_standard_deviation=exact(control),threshold_sigma=exact(threshold),
        trend_per_observation_index=exact(trend),lag_one_sample_coefficient=exact(autocov/total_sq) if total_sq else None,
        observations=points,flagged_ids=[r['id'] for r in points if r['flagged']],automatically_excluded_points=[],
        stability_proven=False,control_basis=value['control_basis'],source_reference=value['source_reference'])

@guard
def uncertainty(c,asof):
    mode=c.get('mode');mapping={'budget':('budget',),'weighted_linear_fit':('fit',),'qc':('qc',),'comprehensive':('budget','fit','qc')}
    if mode not in mapping:fail('supported_uncertainty_mode_required')
    required=('as_of','mode','measurement_model','output_unit',*mapping[mode]);obj(c,'uncertainty',required)
    text(c['measurement_model'],'measurement_model');unit(c['output_unit'])
    return dict(mode=mode,measurement_model=c['measurement_model'],output_unit=c['output_unit'],
        budget=_budget(c['budget'],c['output_unit'],asof) if 'budget' in mapping[mode] else None,
        fit=_fit(c['fit'],asof) if 'fit' in mapping[mode] else None,qc=_qc(c['qc'],asof) if 'qc' in mapping[mode] else None,
        no_unjustified_outlier_removal=True,no_automatic_systematic_correction=True)

def input_units(function,data):
    """Variable numeric paths only; literal formula coefficients are source text."""
    if function not in FUNCTIONS:fail('unknown_physics_calculation')
    with localcontext(CTX):
        globals()[function](data)
        c=data;units={}
        def put(path,unit_,when=None):
            units[path]={'unit':unit_,'not_after':when} if when else unit_
        if function=='physical_model':
            for key in ('variables','constants'):
                for i,row in enumerate(c[key]):put(f'/{key}/{i}/value',row['unit'],row.get('observation_date',c['as_of']))
            for i,row in enumerate(c['limiting_cases']):
                for j,change in enumerate(row['overrides']):put(f'/limiting_cases/{i}/overrides/{j}/value',change['unit'])
                put(f'/limiting_cases/{i}/expected_rhs/value',row['expected_rhs']['unit'])
                put(f'/limiting_cases/{i}/absolute_tolerance',row['expected_rhs']['unit'])
            for i,row in enumerate(c['scale_checks']):
                for key in ('minimum','maximum'):put(f'/scale_checks/{i}/'+key,row['unit'])
        elif function=='numerical_sim':
            q=c['quantity_unit'];benchmark=c['benchmark']
            put('/benchmark/reference_value',q,benchmark['observation_date']);put('/benchmark/absolute_tolerance',q)
            put('/benchmark/relative_tolerance','1')
            if c['mode']=='refinement_review':
                r=c['refinement']
                put('/refinement/ratio_relative_tolerance','1');put('/refinement/expected_order','1')
                for i,row in enumerate(r['levels']):
                    put(f'/refinement/levels/{i}/h',r['h_unit'],c['as_of']);put(f'/refinement/levels/{i}/value',q,c['as_of'])
            else:
                m=c['monte_carlo']
                for key in ('events','seed'):put('/monte_carlo/'+key,'count',m['observation_date'])
                for key in ('mean','sample_standard_deviation'):put('/monte_carlo/'+key,q,m['observation_date'])
        else:
            if 'budget' in c:
                b=c['budget'];put('/budget/estimate',c['output_unit'],c['as_of']);put('/budget/coverage_factor','1');put('/budget/reporting_digits','count')
                for i,row in enumerate(b['components']):
                    p=f'/budget/components/{i}';put(p+'/sensitivity',row['sensitivity_unit'])
                    if row['type']=='A':
                        for j,value in enumerate(row['observations']):put(p+f'/observations/{j}',row['unit'],c['as_of'])
                    else:
                        put(p+'/estimate',row['unit'],c['as_of'])
                        keys={'standard':('standard_uncertainty',),'rectangular':('half_width',),'triangular':('half_width',),'normal_expanded':('expanded_uncertainty',)}[row['distribution']]
                        for key in keys:put(p+'/'+key,row['unit'],c['as_of'])
                        if row['distribution']=='normal_expanded':put(p+'/coverage_factor','1')
                for i,line in enumerate(b['correlation']['matrix']):
                    for j,value in enumerate(line):put(f'/budget/correlation/matrix/{i}/{j}','1')
            if 'fit' in c:
                f=c['fit'];put('/fit/normalized_residual_threshold','1')
                for i,row in enumerate(f['points']):
                    for key,u in (('x',f['x_unit']),('y',f['y_unit']),('sigma',f['y_unit'])):put(f'/fit/points/{i}/'+key,u,c['as_of'])
            if 'qc' in c:
                q=c['qc']
                for key in ('reference_value','control_standard_deviation'):put('/qc/'+key,q['unit'],c['as_of'])
                put('/qc/threshold_sigma','1')
                for i,row in enumerate(q['observations']):put(f'/qc/observations/{i}/value',q['unit'],c['as_of'])
        if len(units)>900:fail('numeric_binding_contract_limit')
        return units

def selected_texts(function,data):
    """Selected input formulas are literal records, not proof of scientific truth."""
    if function not in FUNCTIONS:fail('unknown_physics_calculation')
    globals()[function](data)
    selected={}
    if function=='physical_model':
        for i,row in enumerate(data['equations']):
            for side in ('lhs','rhs'):selected[f'/equations/{i}/{side}']=row[side]
        for i,row in enumerate(data['dimensionless_parameters']):selected[f'/dimensionless_parameters/{i}/expression']=row['expression']
    return selected

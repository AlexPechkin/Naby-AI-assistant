"""Bounded local member/geotechnical arithmetic; no structural approval or solver.

Selected material strengths, coefficients, combinations and survey parameters
are supplied records. Their occurrence in a source is not semantic validation.
"""
import copy
import re
from datetime import date
from decimal import Decimal as D,Context,localcontext,DecimalException
from functools import wraps
from fractions import Fraction as F

FUNCTIONS=('member_design','foundations')
CTX=Context(prec=180,Emin=-9999,Emax=9999)
ZERO=D(0)
ONE=D(1)
MEMBER_MODELS={
 'rc_rect_singly_reinforced_flexure':'reinforced_concrete',
 'steel_elastic_beam':'steel','steel_central_axial':'steel',
 'timber_rect_beam':'timber','timber_rect_central_axial':'timber',
 'masonry_rect_eccentric_compression':'masonry'}
FORCE_BASIS='N_compression_positive_Mx_compresses_positive_y_My_compresses_positive_x_Vy_signed'
FOUNDATION_BASIS='downward_N_includes_selfweight_separate_upward_water_Mx_increases_positive_y_pressure_My_increases_positive_x_pressure'


def obj(v,required=(),optional=(),name='object'):
    if type(v) is not dict or not set(required)<=set(v) or set(v)-set(required)-set(optional):raise ValueError(name+'_fields')
    return v


def seq(v,minimum=0,maximum=10,name='list'):
    if type(v) is not list or not minimum<=len(v)<=maximum:raise ValueError(name+'_bounded_list')
    return v


def txt(v,name='text',maximum=5000):
    if type(v) is not str or not v.strip() or len(v)>maximum or any(ord(c)<32 and c not in '\r\n\t' for c in v):raise ValueError(name+'_required')
    return v


def day(v):
    if type(v) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',v):raise ValueError('ISO_date_required')
    try:return date.fromisoformat(v)
    except ValueError:raise ValueError('invalid_date') from None


def decimal(v):
    if type(v) is not str or len(v)>160 or not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d{1,3})?',v):raise ValueError('exact_decimal_string_required')
    x=D(v)
    if not x.is_finite() or len(x.as_tuple().digits)>40 or abs(x.as_tuple().exponent)>140 or x and abs(x.adjusted())>100:raise ValueError('bounded_decimal_required')
    return x


def q(v,unit,low=None,high=None):
    obj(v,('value','unit'),('source_reference','effective_date'),'quantity')
    if v['unit']!=unit:raise ValueError('quantity_unit_mismatch:'+unit)
    if 'source_reference' in v:txt(v['source_reference'],'source_reference',200)
    if v.get('effective_date') is not None:day(v['effective_date'])
    n=decimal(v['value'])
    if low is not None and n<D(low) or high is not None and n>D(high):raise ValueError('quantity_bound')
    return n


def positive(v,unit):
    n=q(v,unit)
    if n<=0:raise ValueError('positive_quantity_required')
    return n


def tree(v,depth=0,budget=None):
    if budget is None:budget=[0]
    budget[0]+=1
    if depth>28 or budget[0]>18000:raise ValueError('bounded_input_structure')
    if type(v) is dict:
        if len(v)>80:raise ValueError('object_limit')
        for k,x in v.items():
            if type(k) is not str:raise ValueError('string_keys_required')
            if k.endswith(('_verified','_approved','_confirmed','_signed')) or k in {'safe','compliant','authorized','verified','approved','signed','permit','category_assigned','actual_success_at','current_rule_chain_complete'}:raise ValueError('reserved_authority_field:'+k)
            tree(x,depth+1,budget)
    elif type(v) is list:
        if len(v)>100:raise ValueError('list_limit')
        for x in v:tree(x,depth+1,budget)
    elif type(v) is str:
        if len(v)>50000:raise ValueError('text_limit')
    elif v is not None and type(v) is not bool:raise ValueError('numeric_values_must_be_exact_strings')


def common(data,required,optional=()):
    tree(data);obj(data,('as_of','jurisdiction',*required),optional,'data')
    asof=day(data['as_of'])
    if data['jurisdiction']!='RU':raise ValueError('jurisdiction_RU_required')
    def dates(v):
        if type(v) is dict:
            if 'value' in v and 'unit' in v and v.get('effective_date') is not None and day(v['effective_date'])>asof:raise ValueError('quantity_effective_date_after_as_of')
            for x in v.values():dates(x)
        elif type(v) is list:
            for x in v:dates(x)
    dates(data);return asof


def source(v,asof):
    obj(v,('document_identity','edition','publication_date','effective_from','effective_to','clause','source_reference','excerpt'),name='model_basis')
    for k in ('document_identity','edition','clause','source_reference','excerpt'):txt(v[k],k,20000 if k=='excerpt' else 2000)
    if day(v['publication_date'])>asof or day(v['effective_from'])>asof:raise ValueError('source_after_as_of')
    if v['effective_to'] is not None and day(v['effective_to'])<day(v['effective_from']):raise ValueError('source_window_invalid')
    return dict(copy.deepcopy(v),provided_period_ended=v['effective_to'] is not None and day(v['effective_to'])<asof,legal_applicability='not_established')


def reference(v):
    txt(v['source_reference'],'source_reference',200)
    if v.get('excerpt') is not None:txt(v['excerpt'],'excerpt',20000)


def unique(values):
    keys=[txt(v['id'],'id',200) for v in values]
    if len(keys)!=len(set(keys)):raise ValueError('duplicate_id')


def checked(demand,capacity,unit,**extra):
    if capacity<=0:raise ValueError('nonpositive_derived_capacity')
    # Rational derived operands remain exact through comparison and division;
    # conversion to the declared Decimal precision is only for final reporting.
    a,b=F(demand),F(capacity)
    return dict(status='computed_conditional',demand=str(rational_decimal(a)),capacity=str(rational_decimal(b)),unit=unit,utilization=str(rational_decimal(a/b)),within_selected_limit=a<=b,**extra)


def unperformed(reason,status='not_supported'):
    return dict(status=status,reason=reason,utilization=None,within_selected_limit=None)


def output(function,data,**values):
    return dict(function=function,as_of=data['as_of'],jurisdiction='RU',**values,
       analysis_only=True,private=True,source_semantics_established=False,current_normative_chain_established=False,
       design_approval_granted=False,safety_conclusion_made=False,technical_category_assigned=False,
       signature_applied=False,records_changed=False,external_network_used=False,external_solver_executed=False)


def section(v,allowed):
    kind=v.get('type') if type(v) is dict else None
    if kind not in allowed:raise ValueError('supported_section_geometry_required')
    if kind=='rectangle':
        obj(v,('type','b','h'),('source_reference','excerpt'),'rectangle')
        b,h=positive(v['b'],'mm'),positive(v['h'],'mm')
        return dict(A=b*h,Ix=b*h**3/12,Iy=h*b**3/12,Wx=b*h**2/6,Wy=h*b**2/6,b=b,h=h,Sx=b*h**2/8,shear_width=b)
    obj(v,('type','b','h','tf','tw'),('source_reference','excerpt'),'doubly_symmetric_I')
    b,h,tf,tw=(positive(v[k],'mm') for k in ('b','h','tf','tw'))
    if 2*tf>=h or tw>=b:raise ValueError('I_section_geometry_invalid')
    hw=h-2*tf
    # Exact finite input geometry prevents subtracting two large nearly equal
    # rectangles from erasing a thin positive web/flange before rounding output.
    exact=exact_section(v);fb,fh,ftf,ftw=(F(v[k]['value']) for k in ('b','h','tf','tw'));fhw=fh-2*ftf
    return dict(A=rational_decimal(exact['A']),Ix=rational_decimal(exact['Ix']),Iy=rational_decimal(exact['Iy']),
                Wx=rational_decimal(2*exact['Ix']/fh),Wy=rational_decimal(2*exact['Iy']/fb),
                b=b,h=h,Sx=rational_decimal(fb*ftf*(fh-ftf)/2+ftw*fhw**2/8),shear_width=tw)


def properties(v,required,optional=()):
    obj(v,required,optional,'material_properties')
    return {k:positive(val,'MPa') for k,val in v.items()}


def forces(v):
    obj(v,('id','N','Mx','My','Vy','source_reference'),('excerpt',),'combination');reference(v)
    return {k:q(v[k],'kN' if k in ('N','Vy') else 'kN*m') for k in ('N','Mx','My','Vy')}


def rc_geometry(data,geom,moment):
    rebar=data['reinforcement'];obj(rebar,(),('bottom','top'),'reinforcement')
    for row in rebar.values():
        obj(row,('area','effective_depth','xi_limit'),('source_reference','excerpt'),'reinforcement_face')
        positive(row['area'],'mm2');depth=positive(row['effective_depth'],'mm')
        q(row['xi_limit'],'ratio','0','1')
        if depth>=geom['h']:raise ValueError('reinforcement_depth_outside_section')
    face='bottom' if moment>=0 else 'top'
    if face not in rebar:raise ValueError('reinforcement_required_for_bending_sign:'+face)
    return face,positive(rebar[face]['area'],'mm2'),positive(rebar[face]['effective_depth'],'mm')


def cracked_rc(data,geom,prop,moment,concrete_modulus='Eb'):
    if not {concrete_modulus,'Es'}<=set(prop):raise ValueError('selected_concrete_and_steel_moduli_required_for_SLS:'+concrete_modulus)
    face,As,d=rc_geometry(data,geom,moment);n=prop['Es']/prop[concrete_modulus];b=geom['b']
    # Stable equivalent of sqrt((nAs)^2+2bnAsd)/b-nAs/b.
    c=2*n*As*d/(((n*As)**2+2*b*n*As*d).sqrt()+n*As)
    # Force equilibrium supplies d-c without subtracting nearly equal values.
    arm=b*c*c/(2*n*As)
    inertia=b*c**3/3+n*As*arm**2
    stress=abs(moment)*D('1e6')*n*arm/inertia
    return dict(face=face,neutral_axis=str(c),transformed_cracked_inertia=str(inertia),steel_stress=str(stress),concrete_modulus_key=concrete_modulus,selected_concrete_modulus=str(prop[concrete_modulus]),modulus_unit='MPa'),inertia,stress


def exact_section(v):
    """Rational geometry for predicates, before any I/12 Decimal rounding."""
    values={k:F(v[k]['value']) for k in ('b','h')}
    b,h=values['b'],values['h']
    if v['type']=='rectangle':return dict(A=b*h,Ix=b*h**3/12,Iy=h*b**3/12)
    tf,tw=F(v['tf']['value']),F(v['tw']['value']);hw=h-2*tf
    return dict(A=2*b*tf+hw*tw,Ix=(b*h**3-(b-tw)*hw**3)/12,Iy=(2*tf*b**3+hw*tw**3)/12)


def rational_decimal(v):return D(v.numerator)/D(v.denominator)


def fmt(v):return str(rational_decimal(v)) if isinstance(v,F) else str(v)


def steel_phi(normalized_square,curve):
    if curve not in ('a','b','c'):raise ValueError('selected_steel_curve_required')
    alpha,beta,threshold={'a':('0.03','0.06','3.8'),'b':('0.04','0.09','4.4'),'c':('0.04','0.14','5.8')}[curve]
    z=rational_decimal(normalized_square);normalized=z.sqrt()
    if normalized_square<F('0.6')**2:phi=ONE;regime='normalized_slenderness_below_0_6'
    else:
        delta=D('9.87')*(1-D(alpha)+D(beta)*normalized)+z
        discriminant=delta**2-D('39.48')*z
        if discriminant<0:raise ValueError('steel_curve_discriminant')
        phi=D('19.74')/(delta+discriminant.sqrt())
        above_tail=normalized_square>F(threshold)**2
        if above_tail:phi=min(phi,D('7.6')/z)
        regime='selected_curve_above_tail_threshold' if above_tail else 'selected_curve_not_above_tail_threshold'
        phi=min(phi,ONE)
    return phi,normalized,regime


def interpolate(points,value):
    seq(points,2,20,'selected_table_points');pairs=[]
    for p in points:
        obj(p,('slenderness','phi'),name='table_point')
        pairs.append((F(q(p['slenderness'],'ratio','0')),F(q(p['phi'],'ratio','0','1'))))
    if any(pairs[i][0]>=pairs[i+1][0] or pairs[i][1]<pairs[i+1][1] for i in range(len(pairs)-1)):raise ValueError('ordered_monotonic_selected_phi_table_required')
    if not pairs[0][0]<=value<=pairs[-1][0]:raise ValueError('slenderness_outside_selected_table_no_extrapolation')
    for x,y in pairs:
        if value==x:return y
    for (x0,y0),(x1,y1) in zip(pairs,pairs[1:]):
        if x0<value<x1:return y0+(y1-y0)*(value-x0)/(x1-x0)
    raise ValueError('selected_table_interpolation')


def context(v,asof,topics):
    obj(v,(),topics,'context');result={};gaps=[]
    for topic in topics:
        row=v.get(topic)
        if row is None:result[topic]=dict(state='unknown',meaning='not_supplied');gaps.append('context.'+topic);continue
        obj(row,('state','note'),('source_reference','excerpt','record_date'),topic)
        if row['state'] not in ('provided','unknown','not_applicable'):raise ValueError('context_state')
        txt(row['note'],'context_note')
        if row['state']=='provided':reference(row);txt(row.get('excerpt'),'provided_context_excerpt',20000)
        if row.get('record_date') is not None and day(row['record_date'])>asof:raise ValueError('context_record_after_as_of')
        if row['state']=='unknown':gaps.append('context.'+topic)
        result[topic]=copy.deepcopy(row)
    return result,gaps


def member_design(data):
    asof=common(data,('member_id','model','material_class','section','properties','force_basis','combinations','model_basis','context'),('reinforcement','stability','masonry','serviceability'))
    txt(data['member_id'],'member_id',200);txt(data['material_class'],'material_class',300)
    model=data['model']
    if model not in MEMBER_MODELS:raise ValueError('supported_member_model_required')
    material=MEMBER_MODELS[model]
    if data['force_basis']!=FORCE_BASIS:raise ValueError('explicit_member_force_basis_required')
    basis=source(data['model_basis'],asof);geom=section(data['section'],('rectangle','doubly_symmetric_I') if material=='steel' else ('rectangle',))
    member_context,gaps=context(data['context'],asof,('exposure','fire','seismic','dynamic','aggressive_environment','supports'))
    if basis['provided_period_ended']:gaps.append('selected_model_source_period_ended')
    if material=='reinforced_concrete':
        if 'reinforcement' not in data:raise ValueError('reinforcement_required')
        prop=properties(data['properties'],('Rb','Rs'),('Eb','Eb_red','Es','Rs_ser'))
        if 'masonry' in data or 'stability' in data:raise ValueError('irrelevant_material_branch')
    elif material=='steel':
        obj(data['properties'],('Ry','E','gamma_c'),('R_shear',),'steel_properties')
        prop={k:positive(v,'ratio' if k=='gamma_c' else 'MPa') for k,v in data['properties'].items()}
    elif model=='timber_rect_beam':prop=properties(data['properties'],('R_bending','R_shear'),('E_effective',))
    elif material=='timber':prop=properties(data['properties'],('R_compression',),('R_tension','E_effective'))
    else:prop=properties(data['properties'],('R_compression',))
    if material!='reinforced_concrete' and 'reinforcement' in data:raise ValueError('irrelevant_reinforcement')
    if material!='masonry' and 'masonry' in data:raise ValueError('irrelevant_masonry_branch')
    if not model.endswith('central_axial') and 'stability' in data:raise ValueError('central_axial_stability_branch_only')
    stability=data.get('stability');stability_basis=None
    if model.endswith('central_axial'):
        if stability is None:raise ValueError('selected_effective_lengths_required')
        obj(stability,('length_x','length_y','model_basis'),('curve_x','curve_y'),'stability')
        lx,ly=positive(stability['length_x'],'mm'),positive(stability['length_y'],'mm');stability_basis=source(stability['model_basis'],asof)
        if material=='steel' and not {'curve_x','curve_y'}<=set(stability):raise ValueError('selected_steel_curves_required')
        if material=='timber' and ('curve_x' in stability or 'curve_y' in stability):raise ValueError('steel_curve_not_timber')
    masonry=data.get('masonry');masonry_basis=None
    if material=='masonry':
        obj(masonry,('actual_height','effective_height','phi_table','omega_family','model_basis'),('long_term',),'masonry')
        H=positive(masonry['actual_height'],'mm');l0=positive(masonry['effective_height'],'mm')
        table=masonry['phi_table'];obj(table,('elastic_characteristic','points','source_reference','excerpt'),name='masonry_phi_table');reference(table);positive(table['elastic_characteristic'],'ratio')
        masonry_basis=source(masonry['model_basis'],asof)
        if masonry['omega_family'] not in ('table7_2_general','table7_2_omega_one'):raise ValueError('selected_masonry_family_required')
    reviews=[]
    for row in seq(data['combinations'],1,6,'combinations'):
        f=forces(row);N,Mx,My,V=(f[k] for k in ('N','Mx','My','Vy'));checks={}
        if material=='reinforced_concrete':
            if N or My:raise ValueError('RC_model_is_pure_single_axis_flexure')
            face,As,depth=rc_geometry(data,geom,Mx);x=F(prop['Rs'])*F(As)/(F(prop['Rb'])*F(geom['b']))
            rebar=data['reinforcement'][face]
            # xi_R is a selected material/strain limit rather than a fabricated
            # universal reinforcement limit; placed in the combination branch.
            obj(rebar,('area','effective_depth','xi_limit'),('source_reference','excerpt'),'reinforcement_face')
            xi_limit=q(rebar['xi_limit'],'ratio','0','1')
            if not 0<x<=F(xi_limit)*F(depth):raise ValueError('RC_compression_block_outside_selected_singly_reinforced_model')
            capacity=F(prop['Rb'])*F(geom['b'])*x*(F(depth)-x/2)/1000000
            checks['flexure']=checked(abs(Mx),capacity,'kN*m',tension_face=face,rebar_area=str(As),effective_depth=str(depth),compression_depth=fmt(x),xi=fmt(x/F(depth)),selected_xi_limit=str(xi_limit))
            checks['shear']=unperformed('RC_inclined_sections_and_stirrups_not_calculated')
            checks['stability']=unperformed('RC_axial_second_order_and_global_stability_not_calculated')
        elif model in ('steel_elastic_beam','timber_rect_beam'):
            if N or material=='timber' and My:raise ValueError('beam_model_excludes_axial_or_timber_biaxial_force')
            eg=exact_section(data['section']);fb,fh=(F(data['section'][k]['value']) for k in ('b','h'))
            wx,wy=2*eg['Ix']/fh,2*eg['Iy']/fb
            sigma=abs(F(Mx))*1000000/wx+abs(F(My))*1000000/wy
            bending=prop['Ry']*prop['gamma_c'] if material=='steel' else prop['R_bending']
            checks['flexure']=checked(sigma,bending,'MPa',section_moduli=dict(Wx=str(geom['Wx']),Wy=str(geom['Wy'])))
            if data['section']['type']=='rectangle':Sx=fb*fh**2/8;width=fb
            else:
                tf,tw=(F(data['section'][k]['value']) for k in ('tf','tw'));Sx=fb*tf*(fh-tf)/2+tw*(fh-2*tf)**2/8;width=tw
            shear=abs(F(V))*1000*Sx/(eg['Ix']*width)
            if material=='steel' and 'R_shear' not in prop:checks['shear']=unperformed('selected_shear_strength_not_supplied','missing_input');gaps.append('properties.R_shear')
            else:checks['shear']=checked(shear,prop['R_shear']*(prop['gamma_c'] if material=='steel' else ONE),'MPa')
            checks['stability']=unperformed('lateral_torsional_buckling_local_plate_or_beam_stability_not_calculated')
        elif model.endswith('central_axial'):
            if Mx or My or V:raise ValueError('central_axial_model_excludes_bending_shear')
            exact_geom=exact_section(data['section']);area=exact_geom['A'];sig=abs(F(N))*1000/area
            if material=='timber' and N<0 and 'R_tension' not in prop:raise ValueError('selected_timber_tension_strength_required')
            resistance=prop['Ry']*prop['gamma_c'] if material=='steel' else prop['R_compression'] if N>=0 else prop['R_tension']
            checks['axial_strength']=checked(sig,resistance,'MPa')
            if N>0:
                directions=[]
                for axis,length,I in (('x',lx,geom['Ix']),('y',ly,geom['Iy'])):
                    slender_square=F(stability['length_'+axis]['value'])**2*exact_geom['A']/exact_geom['I'+axis]
                    slender=rational_decimal(slender_square).sqrt()
                    if material=='steel':
                        normalized_square=slender_square*F(data['properties']['Ry']['value'])/F(data['properties']['E']['value'])
                        phi,normalized,regime=steel_phi(normalized_square,stability['curve_'+axis])
                    else:
                        at_most_70=slender_square<=F(70)**2
                        phi=rational_decimal(F(1)-F('0.8')*slender_square/10000 if at_most_70 else F(3000)/slender_square);normalized=None
                        regime='geometric_slenderness_at_most_70' if at_most_70 else 'geometric_slenderness_above_70'
                    exact_phi=F(phi) if material=='steel' else F(1)-F('0.8')*slender_square/10000 if at_most_70 else F(3000)/slender_square
                    capacity=exact_phi*area*F(resistance)/1000
                    directions.append(dict(axis=axis,effective_length=str(length),slenderness=str(slender),normalized_slenderness=str(normalized) if normalized is not None else None,phi=str(phi),phi_regime=regime,**checked(N,capacity,'kN')))
                checks['stability']=dict(status='computed_conditional',directions=directions,scope='central_flexural_buckling_only')
            else:checks['stability']=unperformed('compressive_buckling_not_applied_to_noncompressive_force','not_applicable_to_selected_force')
        else:
            if N<=0 or My or V:raise ValueError('masonry_model_requires_positive_compression_single_axis_no_shear')
            eccentricity=abs(F(Mx))*1000/F(N);hc=F(geom['h'])-2*eccentricity
            if hc<=0:raise ValueError('masonry_resultant_outside_section')
            phi=interpolate(table['points'],F(l0)/F(geom['h']));phic=interpolate(table['points'],F(H)/hc);phi1=(phi+phic)/2
            mg=F(1);longterm=masonry.get('long_term')
            if min(geom['b'],geom['h'])<300:
                if longterm is None:raise ValueError('masonry_long_term_inputs_required_for_thin_section')
                obj(longterm,('eta','N_long','M_long','source_reference'),('excerpt',),'masonry_long_term');reference(longterm)
                eta=q(longterm['eta'],'ratio','0','1');Ng=q(longterm['N_long'],'kN','0');Mg=q(longterm['M_long'],'kN*m')
                if Ng>N or not Ng and Mg:raise ValueError('masonry_long_term_force_basis_conflict')
                eg=abs(F(Mg))*1000/F(Ng) if Ng else F(0)
                mg=F(1)-F(eta)*(F(Ng)/F(N))*(F(1)+F('1.2')*eg/F(geom['h']))
                if mg<=0:raise ValueError('masonry_mg_outside_supported_model')
            elif longterm is not None:raise ValueError('irrelevant_long_term_branch_for_thick_masonry_model')
            omega=min(F(1)+eccentricity/F(geom['h']),F('1.45')) if masonry['omega_family']=='table7_2_general' else F(1)
            capacity=mg*phi1*F(prop['R_compression'])*F(geom['b'])*hc*omega/1000
            checks['eccentric_compression']=checked(N,capacity,'kN',eccentricity=fmt(eccentricity),compressed_depth=fmt(hc),compressed_area=fmt(F(geom['b'])*hc),phi=fmt(phi),phi_compressed=fmt(phic),phi_mean=fmt(phi1),mg=fmt(mg),omega=fmt(omega))
            checks['crack']=unperformed('masonry_tensile_crack_and_multilayer_wall_checks_not_calculated')
        reviews.append(dict(id=row['id'],provided_forces=copy.deepcopy(row),checks=checks))
    unique(reviews)
    sls=serviceability(data,geom,prop,material,asof)
    return output('member_design',data,member_id=data['member_id'],model=model,material=material,material_class=data['material_class'],force_basis=data['force_basis'],
                  model_basis=basis,section_properties={k:str(x) for k,x in geom.items()},selected_section=copy.deepcopy(data['section']),selected_material_properties=copy.deepcopy(data['properties']),
                  reinforcement=copy.deepcopy(data.get('reinforcement')),stability_basis=stability_basis,masonry_basis=masonry_basis,
                  context=member_context,combination_reviews=reviews,serviceability=sls,evidence_gaps=sorted(set(gaps)),
                  exclusions=['fire_seismic_fatigue_connections_and_detailing_not_calculated','combined_web_stress_and_member_bending_compression_interaction_not_calculated','no_full_member_or_structure_code_design','no_automatic_section_selection'])


def serviceability(data,geom,prop,material,asof):
    value=data.get('serviceability')
    if value is None:return dict(status='not_requested',deflection=unperformed('serviceability_not_requested','not_requested'),crack=unperformed('serviceability_not_requested','not_requested'))
    obj(value,(),('deflection','crack'),'serviceability');result=dict(status='selected_bounded_serviceability',deflection=unperformed('deflection_not_requested','not_requested'),crack=unperformed('crack_not_requested','not_requested'))
    if value.get('deflection') is not None:
        if data['model'].endswith('central_axial'):raise ValueError('beam_deflection_not_a_central_axial_member_model')
        v=value['deflection'];obj(v,('id','model','span','udl','limit','model_basis'),name='deflection')
        if v['model']!='simply_supported_uniform_load_immediate':raise ValueError('supported_deflection_scheme_required')
        source(v['model_basis'],asof);L=positive(v['span'],'mm');load=q(v['udl'],'kN/m');limit=positive(v['limit'],'mm')
        if material=='reinforced_concrete':
            detail,I,stress=cracked_rc(data,geom,prop,load*(L/1000)**2/8);E=prop['Eb'];scope='fully_cracked_transformed_elastic_immediate_no_creep_or_tension_stiffening'
        elif material=='steel':I=geom['Ix'];E=prop['E'];detail=None;scope='elastic_Euler_Bernoulli_no_shear_deformation'
        elif material=='timber':
            if 'E_effective' not in prop:raise ValueError('selected_effective_timber_modulus_required')
            I=geom['Ix'];E=prop['E_effective'];detail=None;scope='selected_effective_modulus_no_independent_creep_or_shear_deformation'
        else:raise ValueError('masonry_deflection_model_not_supported')
        deflection=D(5)*load*L**4/(384*E*I)
        result['deflection']=dict(checked(abs(deflection),limit,'mm'),signed_deflection=str(deflection),EI=str(E*I),model=v['model'],scope=scope,cracked_section=detail,model_basis=copy.deepcopy(v['model_basis']),id=v['id'])
    if value.get('crack') is not None:
        if material!='reinforced_concrete':raise ValueError('reinforced_concrete_crack_model_only')
        v=value['crack'];obj(v,('id','moment','phi_duration','phi_profile','phi_loading','psi_s','spacing','limit','model_basis'),name='RC_crack')
        source(v['model_basis'],asof);moment=q(v['moment'],'kN*m');detail,I,stress=cracked_rc(data,geom,prop,moment,'Eb_red')
        coefficients=[positive(v[k],'ratio') for k in ('phi_duration','phi_profile','phi_loading')];psi=q(v['psi_s'],'ratio','0','1');spacing=positive(v['spacing'],'mm');limit=positive(v['limit'],'mm')
        width=coefficients[0]*coefficients[1]*coefficients[2]*psi*stress/prop['Es']*spacing
        if 'Rs_ser' not in prop:raise ValueError('selected_service_rebar_stress_limit_required')
        result['crack']=dict(checked(width,limit,'mm'),steel_stress_check=checked(stress,prop['Rs_ser'],'MPa'),cracked_section=detail,selected_spacing=str(spacing),
             coefficient_product=str(coefficients[0]*coefficients[1]*coefficients[2]*psi),scope='one_selected_load_duration_component_using_reduced_concrete_modulus_not_aggregate_or_crack_formation_prediction',provided=copy.deepcopy(v))
    return result


SOIL_UNITS={'cohesion':'kPa','friction_angle':'degree','gamma_effective':'kN/m3','E_primary':'MPa','E_reload':'MPa'}
FOUNDATION_QUESTIONS=('survey_report_identity_date_and_site','borehole_logs_and_depths','soil_units_and_test_parameters',
 'groundwater_levels_variation_and_buoyancy','specific_soils_and_frost','site_seismicity_and_dynamic_actions',
 'signed_foundation_level_combinations_including_selfweight_and_water','neighbouring_buildings_excavation_and_monitoring',
 'selected_foundation_scheme_and_applicable_model_sources')


def geology(v,asof):
    obj(v,('report_id','report_date','site_id','source_reference','excerpt','boreholes','soil_units'),name='igi')
    reference(v);txt(v['report_id'],'report_id',200);txt(v['site_id'],'site_id',200)
    if day(v['report_date'])>asof:raise ValueError('survey_report_after_as_of')
    boreholes=seq(v['boreholes'],1,8,'boreholes')
    for b in boreholes:
        obj(b,('id','depth','source_reference','excerpt'),name='borehole');reference(b);positive(b['depth'],'m')
    unique(boreholes);units={}
    for u in seq(v['soil_units'],1,10,'soil_units'):
        obj(u,('id','description','parameters','source_reference','excerpt'),name='soil_unit');reference(u);txt(u['description'],'soil_description')
        obj(u['parameters'],(),SOIL_UNITS,'soil_parameters')
        parsed={}
        for key,val in u['parameters'].items():
            parsed[key]=q(val,SOIL_UNITS[key],'0','45' if key=='friction_angle' else None)
            if key in ('gamma_effective','E_primary','E_reload') and parsed[key]<=0:raise ValueError('positive_soil_unit_weight_or_modulus_required')
        if u['id'] in units:raise ValueError('duplicate_soil_unit')
        txt(u['id'],'soil_unit_id',200);units[u['id']]=parsed
    return units


def contact(B,L,N,Mx,My,with_exact_pressure=False):
    def finish(record,maximum=None):return (record,maximum) if with_exact_pressure else record
    area=B*L;result=dict(net_downward_force=fmt(N),base_area=str(area),pressure_unit='kPa',length_unit='m',
                       moment_about_x=str(Mx),moment_about_y=str(My),Wx=str(B*L**2/6),Wy=str(L*B**2/6))
    if N<=0:
        return finish(dict(result,status='no_compressive_contact_resultant',eccentricity_x=None,eccentricity_y=None,minimum_pressure=None,maximum_pressure=None,
                    average_contact_pressure=None,contact_fraction=None,reason='net_uplift_or_zero_vertical_resultant_moment_not_resolved_by_contact_model'))
    fb,fl,fn,fmx,fmy=(F(x) for x in (B,L,N,Mx,My));ex,ey=fmy/fn,fmx/fn
    corners=[];pressures=[]
    for x,y in ((-fb/2,-fl/2),(-fb/2,fl/2),(fb/2,-fl/2),(fb/2,fl/2)):
        p=fn/(fb*fl)+fmx*y/(fb*fl**3/12)+fmy*x/(fl*fb**3/12)
        pressures.append(p)
        corners.append(dict(x=str(rational_decimal(x)),y=str(rational_decimal(y)),linear_full_base_pressure=str(rational_decimal(p))))
    pmin=min(pressures);pmax=max(pressures)
    result.update(eccentricity_x=str(rational_decimal(ex)),eccentricity_y=str(rational_decimal(ey)),linear_full_base_corners=corners,linear_full_base_average=fmt(fn/(fb*fl)))
    if pmin>=0:return finish(dict(result,status='full_compressive_contact',minimum_pressure=str(rational_decimal(pmin)),maximum_pressure=str(rational_decimal(pmax)),average_contact_pressure=fmt(fn/(fb*fl)),contact_fraction='1'),pmax)
    if Mx and My:return finish(dict(result,status='biaxial_partial_contact_not_supported',minimum_pressure=None,maximum_pressure=None,average_contact_pressure=None,contact_fraction=None,reason='linear_tension_is_not_soil_contact_pressure'))
    axis='y' if Mx else 'x';dimension=fl if Mx else fb;width=fb if Mx else fl;e=abs(ey) if Mx else abs(ex)
    if e>=dimension/2:return finish(dict(result,status='resultant_outside_base',minimum_pressure=None,maximum_pressure=None,average_contact_pressure=None,contact_fraction=None,reason='compression_only_equilibrium_not_available'))
    compressed=3*(dimension/2-e);maxpressure=2*fn/(width*compressed)
    return finish(dict(result,status='uniaxial_partial_compressive_contact',minimum_pressure='0',maximum_pressure=str(rational_decimal(maxpressure)),average_contact_pressure=str(rational_decimal(fn/(width*compressed))),
                contact_fraction=str(rational_decimal(compressed/dimension)),compressed_axis=axis,compressed_length=str(rational_decimal(compressed)),compressed_width=str(rational_decimal(width)),
                compression_side='positive' if (ey if Mx else ex)>0 else 'negative',scope='rigid_base_linear_triangle_no_soil_tension'),maxpressure)


def bearing(v,soil,B,L,asof):
    obj(v,('model','soil_below','soil_above','burial_depth','gamma_c1','gamma_c2','k','M_gamma','M_q','M_c','coefficient_friction_angle','maximum_pressure_factor','model_basis'),name='bearing')
    if v['model']!='SP22_5_6_7_no_basement_no_preparation_extension':raise ValueError('supported_bearing_model_required')
    if v['soil_below'] not in soil or v['soil_above'] not in soil:raise ValueError('bearing_soil_unit_not_in_IGI')
    below,above=soil[v['soil_below']],soil[v['soil_above']]
    if not {'cohesion','friction_angle','gamma_effective'}<=set(below) or 'gamma_effective' not in above:raise ValueError('IGI_bearing_parameters_missing')
    phi=q(v['coefficient_friction_angle'],'degree','0','45')
    if phi!=below['friction_angle']:raise ValueError('bearing_coefficients_friction_angle_mismatch')
    gamma1=positive(v['gamma_c1'],'ratio');gamma2=positive(v['gamma_c2'],'ratio');k=positive(v['k'],'ratio')
    Mgamma=q(v['M_gamma'],'ratio','0');Mq=q(v['M_q'],'ratio','0');Mc=q(v['M_c'],'ratio','0');depth=q(v['burial_depth'],'m','0')
    width=F(min(B,L));kz=F(1) if width<10 else F(8)/width+F('0.2')
    R=F(gamma1)*F(gamma2)/F(k)*(F(Mgamma)*kz*width*F(below['gamma_effective'])+F(Mq)*F(depth)*F(above['gamma_effective'])+F(Mc)*F(below['cohesion']))
    if R<=0:raise ValueError('nonpositive_derived_soil_resistance')
    factor=q(v['maximum_pressure_factor'],'ratio','1','5')
    return dict(status='computed_conditional',resistance=fmt(R),unit='kPa',kz=fmt(kz),selected_width=fmt(width),
                maximum_pressure_factor=str(factor),model_basis=source(v['model_basis'],asof),provided=copy.deepcopy(v),
                applicability='selected_coefficients_and_IGI_scope_not_legally_established'),R,factor


def settlement(v,soil,B,L,loads,asof):
    obj(v,('model','id','load_case_id','profile_location','layers','beta','limit','model_basis'),name='settlement')
    if v['model']!='SP22_layer_sum_primary_reload_selected_stresses':raise ValueError('supported_settlement_model_required')
    if v['load_case_id'] not in loads:raise ValueError('settlement_load_case_not_selected')
    txt(v['id'],'settlement_profile_id',200);txt(v['profile_location'],'profile_location')
    beta=positive(v['beta'],'ratio');limit=positive(v['limit'],'mm');values=[];total=F(0);depth=ZERO
    for row in seq(v['layers'],1,10,'settlement_layers'):
        obj(row,('id','soil_unit_id','thickness','stress_external','stress_excavation','source_reference','excerpt'),name='settlement_layer');reference(row)
        if row['soil_unit_id'] not in soil:raise ValueError('settlement_soil_unit_not_in_IGI')
        p=soil[row['soil_unit_id']]
        h=positive(row['thickness'],'m');external=q(row['stress_external'],'kPa','0');excavation=q(row['stress_excavation'],'kPa','0')
        if h>D('0.4')*min(B,L):raise ValueError('settlement_layer_exceeds_selected_0_4_base_width')
        # Supported normal loading/reloading branch. A heave/unloading history
        # requires a different geotechnical model, not a negative primary strain.
        if external<excavation:raise ValueError('unloading_heave_history_outside_supported_settlement_branch')
        if external>excavation and 'E_primary' not in p or excavation and 'E_reload' not in p:raise ValueError('selected_active_branch_modulus_required_no_default')
        primary=F(beta)*(F(external)-F(excavation))*F(h)/(F(p['E_primary'])*1000)*1000 if external>excavation else F(0)
        reload=F(beta)*F(excavation)*F(h)/(F(p['E_reload'])*1000)*1000 if excavation else F(0)
        total+=primary+reload
        values.append(dict(id=row['id'],soil_unit_id=row['soil_unit_id'],top_depth=str(depth),bottom_depth=str(depth+h),
             primary_settlement_mm=str(rational_decimal(primary)),reload_settlement_mm=str(rational_decimal(reload)),settlement_mm=str(rational_decimal(primary+reload)),provided=copy.deepcopy(row)))
        depth+=h
    unique(values)
    return dict(checked(total,limit,'mm'),id=v['id'],load_case_id=v['load_case_id'],profile_location=v['profile_location'],layers=values,
                covered_depth=str(depth),beta=str(beta),model_basis=source(v['model_basis'],asof),
                scope='provided_average_stresses_and_compressible_depth_no_stress_distribution_or_consolidation_solution',
                evidence_gaps=['compressible_depth_layer_stresses_and_history_applicability_require_geotechnical_review']),total


def shallow(v,soil,asof):
    obj(v,('id','type','role','B','L','force_basis','load_combinations','model_basis'),('bearing','settlement'),'shallow_option')
    if v['force_basis']!=FOUNDATION_BASIS:raise ValueError('explicit_foundation_force_basis_required')
    if v['role'] not in ('actual_foundation','alternative'):raise ValueError('foundation_role_required')
    B,L=positive(v['B'],'m'),positive(v['L'],'m');basis=source(v['model_basis'],asof)
    b_review,R,factor=bearing(v['bearing'],soil,B,L,asof) if v.get('bearing') is not None else (unperformed('bearing_not_requested','not_requested'),None,None)
    reviews=[];ids=set();exact_net_forces={}
    for row in seq(v['load_combinations'],1,4,'foundation_load_combinations'):
        obj(row,('id','downward_N_including_selfweight','upward_water','Mx','My','source_reference'),('excerpt',),'foundation_load_combination');reference(row)
        Ndown=q(row['downward_N_including_selfweight'],'kN');water=q(row['upward_water'],'kN','0');Mx=q(row['Mx'],'kN*m');My=q(row['My'],'kN*m');N=F(Ndown)-F(water)
        pressure,exact_maximum=contact(B,L,N,Mx,My,True)
        if R is None:pressure_check=unperformed('bearing_not_requested','not_requested')
        elif pressure['maximum_pressure'] is None:pressure_check=unperformed('contact_model_not_available_for_bearing_comparison')
        else:
            # Average over the full nominal base is explicitly separate from
            # the average over a triangular compressed contact patch.
            pressure_check=dict(status='computed_conditional',full_base_average_check=checked(F(N)/(F(B)*F(L)),R,'kPa'),maximum_contact_check=checked(exact_maximum,F(factor)*R,'kPa'))
        reviews.append(dict(id=row['id'],provided=copy.deepcopy(row),net_downward_force=fmt(N),contact=pressure,bearing_comparison=pressure_check))
        if row['id'] in ids:raise ValueError('duplicate_foundation_combination')
        ids.add(row['id'])
        exact_net_forces[row['id']]=N
    s_review,exact_profile=settlement(v['settlement'],soil,B,L,ids,asof) if v.get('settlement') is not None else (unperformed('settlement_not_requested','not_requested'),None)
    if s_review['status']=='computed_conditional':
        chosen=next(x for x in reviews if x['id']==s_review['load_case_id'])
        if chosen['contact']['status']!='full_compressive_contact':raise ValueError('provided_centerline_settlement_branch_requires_full_compressive_contact')
        if R is None:s_review['evidence_gaps'].append('linear_settlement_resistance_applicability_not_checked')
        elif exact_net_forces[s_review['load_case_id']]/(F(B)*F(L))>R:s_review['evidence_gaps'].append('linear_settlement_mean_pressure_exceeds_selected_R')
    return dict(id=v['id'],type=v['type'],role=v['role'],B=str(B),L=str(L),force_basis=v['force_basis'],model_basis=basis,
                bearing=b_review,load_reviews=reviews,settlement=s_review,
                exclusions=['sliding_overall_ground_stability_punching_and_footing_reinforcement_not_calculated','biaxial_partial_contact_requires_separate_solution','groundwater_frost_and_neighbour_effects_not_resolved_by_contact_arithmetic']),exact_profile


def pile(v,soil,asof):
    obj(v,('id','type','pile_id','soil_unit_id','loading_mode','selected_characteristic_resistance','gamma_c','gamma_test','gamma_ground','gamma_n','characteristic_basis','model_basis','load_combinations'),('test_records',),'pile_option')
    txt(v['pile_id'],'pile_id',200)
    if v['soil_unit_id'] not in soil:raise ValueError('pile_soil_unit_not_in_IGI')
    if v['loading_mode'] not in ('compression','uplift'):raise ValueError('supported_static_axial_pile_test_mode_required')
    basis=source(v['model_basis'],asof);characteristic=source(v['characteristic_basis'],asof)
    Fu=positive(v['selected_characteristic_resistance'],'kN');gc=positive(v['gamma_c'],'ratio');gt=q(v['gamma_test'],'ratio','1');gg=q(v['gamma_ground'],'ratio','1');gn=q(v['gamma_n'],'ratio','1')
    Fd=F(gc)*F(Fu)/F(gt);allowable=Fd/(F(gg)*F(gn));tests=[]
    for t in seq(v.get('test_records',[]),0,6,'pile_test_records'):
        obj(t,('id','test_date','pile_id','soil_unit_id','partial_ultimate_resistance','source_reference','excerpt'),name='pile_test_record');reference(t)
        if day(t['test_date'])>asof:raise ValueError('pile_test_after_as_of')
        if t['soil_unit_id'] not in soil:raise ValueError('test_soil_unit_not_in_IGI')
        positive(t['partial_ultimate_resistance'],'kN');tests.append(copy.deepcopy(t))
    unique(tests);reviews=[]
    for c in seq(v['load_combinations'],1,4,'pile_load_combinations'):
        obj(c,('id','N','source_reference'),('excerpt',),'pile_load_combination');reference(c);N=q(c['N'],'kN')
        if v['loading_mode']=='compression' and N<0 or v['loading_mode']=='uplift' and N>0:raise ValueError('pile_force_sign_conflicts_with_test_loading_mode')
        reviews.append(dict(id=c['id'],provided=copy.deepcopy(c),**checked(abs(N),allowable,'kN')))
    unique(reviews)
    return dict(id=v['id'],type=v['type'],pile_id=v['pile_id'],loading_mode=v['loading_mode'],selected_Fu_n=str(Fu),derived_Fd=fmt(Fd),allowable_axial_load=fmt(allowable),
                resistance_unit='kN',model_basis=basis,characteristic_basis=characteristic,characteristic_resistance_status='provided_not_established',
                test_records=tests,test_record_count=len(tests),load_reviews=reviews,
                evidence_gaps=['selected_characteristic_resistance_and_test_population_not_statistically_established','test_pile_geometry_and_actual_foundation_conditions_require_review'],
                exclusions=['no_automatic_minimum_or_statistics_from_raw_test_steps','pile_group_settlement_lateral_load_negative_friction_and_structural_pile_capacity_not_calculated'])


def foundations(data):
    asof=common(data,('site_id','mode'),('igi','context','options','differential_settlement'));txt(data['site_id'],'site_id',200)
    if data['mode']=='questions':
        if any(k in data for k in ('igi','options','differential_settlement')):raise ValueError('questions_only_without_IGI_no_soil_or_option_arithmetic')
        ctx,_=context(data['context'],asof,('groundwater','frost','specific_soils','seismic','dynamic','neighbours','excavation','monitoring')) if data.get('context') is not None else (None,[])
        return output('foundations',data,site_id=data['site_id'],status='survey_data_required',questions=list(FOUNDATION_QUESTIONS),option_reviews=[],context=ctx,no_soil_parameters_invented=True)
    if data['mode']!='igi_review' or not {'igi','context','options'}<=set(data):raise ValueError('dated_IGI_required_for_foundation_arithmetic')
    soil=geology(data['igi'],asof)
    if data['igi']['site_id']!=data['site_id']:raise ValueError('IGI_site_scope_mismatch')
    site_context,gaps=context(data['context'],asof,('groundwater','frost','specific_soils','seismic','dynamic','neighbours','excavation','monitoring'))
    options=[];exact_profiles={}
    for v in seq(data['options'],1,3,'foundation_options'):
        if type(v) is not dict:raise ValueError('foundation_option_object_required')
        if v.get('type')=='shallow_rect':
            review,exact_profile=shallow(v,soil,asof)
            if exact_profile is not None:exact_profiles[review['id']]=exact_profile
        elif v.get('type')=='pile_static_tests':review=pile(v,soil,asof)
        else:raise ValueError('supported_foundation_option_required')
        options.append(review)
    unique(options);comparisons=[]
    for d in seq(data.get('differential_settlement',[]),0,3,'differential_settlement'):
        obj(d,('id','foundation_a','foundation_b','distance','limit_ratio','model_basis'),name='differential_settlement')
        byid={v['id']:v for v in options}
        if d['foundation_a']==d['foundation_b'] or not {d['foundation_a'],d['foundation_b']}<=set(byid):raise ValueError('different_known_foundation_profiles_required')
        a,b=(byid[d[key]] for key in ('foundation_a','foundation_b'))
        if any(v['type']!='shallow_rect' or v['role']!='actual_foundation' or v['settlement']['status']!='computed_conditional' for v in (a,b)):raise ValueError('differential_requires_actual_comparable_computed_profiles_not_alternatives')
        if a['settlement']['load_case_id']!=b['settlement']['load_case_id']:raise ValueError('differential_load_case_scope_mismatch')
        distance=positive(d['distance'],'m');limit=positive(d['limit_ratio'],'ratio');difference=exact_profiles[d['foundation_a']]-exact_profiles[d['foundation_b']];slope=abs(difference)/(F(distance)*1000)
        comparisons.append(dict(id=d['id'],foundation_a=d['foundation_a'],foundation_b=d['foundation_b'],signed_settlement_difference_mm=str(rational_decimal(difference)),
              **checked(slope,limit,'ratio'),model_basis=source(d['model_basis'],asof),scope='two_point_relative_settlement_only_not_rigid_foundation_rotation_or_neighbour_model'))
    unique(comparisons)
    return output('foundations',data,site_id=data['site_id'],status='selected_IGI_bounded_review',igi=copy.deepcopy(data['igi']),context=site_context,
                  option_reviews=options,differential_settlement=comparisons,evidence_gaps=gaps,
                  questions=list(FOUNDATION_QUESTIONS),foundation_type_selected=False,
                  exclusions=['no_site_geotechnical_category_or_safety_assignment','no_automatic_soil_defaults_or_FEA','no_construction_permission_or_physical_remedy_authorization'])


def execute(function,data):
    if function not in FUNCTIONS:raise ValueError('unknown_member_foundation_function')
    return {'member_design':member_design,'foundations':foundations}[function](data)


def input_units(function,data):
    # Executing validates the selected bounded branch and every supplied numeric
    # shape; no network, solver or external side effect is present.
    execute(function,data);units={}
    def walk(v,path=''):
        if type(v) is dict:
            if 'value' in v and 'unit' in v:
                item={'unit':v['unit'],'effective_not_after':data['as_of'],'published_not_after':data['as_of']}
                if v.get('effective_date') is not None:item['effective_date']=v['effective_date']
                units[path+'/value']=item
            for key,x in v.items():walk(x,path+'/'+key.replace('~','~0').replace('/','~1'))
        elif type(v) is list:
            for i,x in enumerate(v):walk(x,path+'/'+str(i))
    walk(data)
    if len(units)>850:raise ValueError('member_foundation_numeric_binding_limit')
    return units


def selected_texts(function,data):
    if function not in FUNCTIONS:raise ValueError('unknown_member_foundation_function')
    # Existing excerpts are also collected by the shared binding. Authored
    # context notes and proposed questions are deliberately not source quotes.
    tree(data);result={}
    def walk(v,path=''):
        if type(v) is dict:
            for k,x in v.items():
                p=path+'/'+k.replace('~','~0').replace('/','~1')
                if k=='excerpt':result[p]=txt(x,'excerpt',20000)
                else:walk(x,p)
        elif type(v) is list:
            for i,x in enumerate(v):walk(x,path+'/'+str(i))
    walk(data);return result


def public(fn):
    @wraps(fn)
    def wrapped(*args,**kwargs):
        try:
            with localcontext(CTX):return fn(*args,**kwargs)
        except (KeyError,TypeError,AttributeError,IndexError,OverflowError,RecursionError,DecimalException,ZeroDivisionError):raise ValueError('invalid_nested_member_or_foundation_input') from None
    return wrapped


for _name in ('execute','input_units','selected_texts'):globals()[_name]=public(globals()[_name])

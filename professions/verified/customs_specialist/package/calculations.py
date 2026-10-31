"""Pure subject arithmetic. One ordinary third-country import item into RU.
Inputs remain declared assumptions, never authenticated approvals/live legal data.
No I/O; source binding belongs to the host. Staged rounding is explicit.
"""
from datetime import date
from decimal import Decimal, Context, localcontext, InvalidOperation, ROUND_HALF_UP
import re

D = Decimal
ZERO = D('0')
# A specific duty may multiply three bounded 1e18 inputs and divide by
# a permitted 1e-18 unit denominator. Keep those 73 integer digits plus
# cents and guard digits without inheriting the caller's Decimal traps.
CTX = Context(prec=128, rounding=ROUND_HALF_UP)
ADDITIONS = frozenset(('transport_before_arrival','loading_before_arrival',
    'insurance_before_arrival','agent_except_buying','containers','packing',
    'assists','royalties','seller_proceeds'))
DEDUCTIONS = frozenset(('post_import_construction','transport_after_arrival','import_duties_taxes'))
CONDITIONS = ('sale_for_export','permitted_restrictions_only','quantifiable_conditions',
    'seller_proceeds_accounted','related_price_acceptable','additions_complete','documents_sufficient')
ROUND_FIELDS = ('customs_value','duty','excise','vat','customs_fee','special_duties')
INCOTERMS = frozenset(('EXW','FCA','FAS','FOB','CFR','CIF','CPT','CIP','DAP','DPU','DDP'))

def _fail(code):
    raise ValueError(code)

def _obj(x, name):
    if type(x) is not dict: _fail(name+'_object_required')
    return x

def _text(x, name, limit=2000):
    if type(x) is not str or not x.strip() or len(x)>limit: _fail(name+'_text_required')
    return x.strip()

def _num(x, name, *, positive=False, maximum='1e18'):
    if type(x) not in (str,int,Decimal): _fail(name+'_decimal_required')
    token=str(x)
    if len(token)>64 or not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',token): _fail(name+'_decimal_required')
    try: v=D(token)
    except InvalidOperation: _fail(name+'_decimal_required')
    if not v.is_finite() or v<0 or v>D(maximum) or (positive and v==0) or abs(v.as_tuple().exponent)>18: _fail(name+'_range')
    return v

def _day(x, name):
    if type(x) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',x): _fail(name+'_iso_date_required')
    try: return date.fromisoformat(x)
    except ValueError: _fail(name+'_invalid_date')

def _bool(x, name):
    if type(x) is not bool: _fail(name+'_boolean_required')
    return x

def _list(x, name, maximum=100):
    if type(x) is not list or len(x)>maximum: _fail(name+'_list_required')
    return x

def _currency(x, name):
    if type(x) is not str or not re.fullmatch('[A-Z]{3}',x): _fail(name+'_currency_code_required')
    if x in ('XXX','XTS'): _fail(name+'_unsupported_currency')
    return x

def _scope(c):
    _obj(c,'data');s=_obj(c.get('scope'),'scope')
    for key,value in (('jurisdiction','RU'),('flow','third_country_import'),('procedure','release_for_domestic_consumption')):
        if s.get(key)!=value: _fail('unsupported_'+key)
    if type(s.get('item_count')) is not int or s['item_count']!=1: _fail('single_item_declaration_required')
    return _day(c.get('declaration_date'),'declaration_date')

def _source(x, name, when):
    x=_obj(x,name);ref=_text(x.get('reference'),name+'_reference')
    start=_day(x.get('effective_from'),name+'_effective_from')
    end=_day(x.get('effective_to'),name+'_effective_to') if x.get('effective_to') is not None else None
    checked=_day(x.get('checked_at'),name+'_checked_at')
    if end is not None and end<start: _fail(name+'_inverted_effective_period')
    if not start<=when or (end is not None and when>end): _fail(name+'_outside_effective_period')
    if checked>when: _fail(name+'_check_after_declaration')
    return {'reference':ref,'effective_from':start.isoformat(),'effective_to':end.isoformat() if end else None,
        'checked_at':checked.isoformat(),'refresh_due':(when-checked).days>=7,
        'metadata_status':'caller_declared_not_authenticated','current_edition_verified':False}

def _fx(x, currency, when, name):
    rate=_num(x.get('fx_rate'),name+'_rate',positive=True)
    nominal=_num(x.get('fx_nominal'),name+'_nominal',positive=True,maximum='1e9')
    if nominal!=nominal.to_integral_value(): _fail(name+'_nominal_integer_required')
    if _day(x.get('fx_date'),name+'_date')!=when: _fail(name+'_must_apply_on_declaration_date')
    reference=_text(x.get('fx_source_reference'),name+'_source_reference')
    if currency=='RUB' and (rate!=1 or nominal!=1): _fail(name+'_rub_identity_required')
    return rate/nominal, {'currency':currency,'fx_rate':str(rate),'fx_nominal':str(nominal),
        'rub_per_unit':str(rate/nominal),'fx_date':when.isoformat(),'fx_source_reference':reference,
        'source_authenticity_verified':False}

def _money(v, quantum=D('0.01')):
    return format(v.quantize(quantum,rounding=ROUND_HALF_UP),'f')

def customs_value(data):
    with localcontext(CTX): return _customs_value(data)

def _customs_value(c):
    when=_scope(c)
    if c.get('method')!=1 or type(c.get('method')) is not int: _fail('only_method_1_supported')
    price=_num(c.get('price'),'price',positive=True)
    currency=_currency(c.get('currency'),'currency');fx,fx_detail=_fx(c,currency,when,'invoice_fx')
    invoice_ref=_text(c.get('price_source_reference'),'price_source_reference')
    related=_bool(c.get('related_parties'),'related_parties');parties=_text(c.get('parties'),'parties')
    incoterms=_text(c.get('incoterms'),'incoterms',3)
    if incoterms not in INCOTERMS: _fail('incoterms_unsupported')
    place=_text(c.get('incoterms_place'),'incoterms_place')
    method_source=_source(c.get('method_source'),'method_source',when)
    conditions=_obj(c.get('method1_conditions'),'method1_conditions')
    if set(conditions)!=set(CONDITIONS): _fail('method1_conditions_exact_keys_required')
    issues=[]
    for key in CONDITIONS:
        value=conditions[key]
        if value is not None and type(value) is not bool: _fail('condition_'+key+'_boolean_or_null_required')
        if key=='related_price_acceptable' and not related: continue
        if value is not True: issues.append(key+('_unknown' if value is None else '_failed'))
    documents=[_text(v,'document') for v in _list(c.get('documents'),'documents',100)]
    if not documents: issues.append('no_documents')
    adjustments={};ids=set()
    for category,allowed in (('additions',ADDITIONS),('deductions',DEDUCTIONS)):
        output=[]
        for item in _list(c.get(category),category):
            _obj(item,category+'_item');ident=_text(item.get('id'),'adjustment_id',100)
            if ident in ids: _fail('duplicate_adjustment_id')
            ids.add(ident);kind=_text(item.get('kind'),'adjustment_kind',80)
            if kind not in allowed: _fail('unsupported_'+category+'_kind')
            amount=_num(item.get('amount'),'adjustment_amount');curr=_currency(item.get('currency'),'adjustment_currency')
            rate,detail=_fx(item,curr,when,'adjustment_fx')
            included=_bool(item.get('included_in_price'),'included_in_price')
            documented=_bool(item.get('documented_separately'),'documented_separately')
            quantifiable=_bool(item.get('quantifiable'),'quantifiable');ref=_text(item.get('source_reference'),'adjustment_source_reference')
            if category=='deductions' and not included: _fail('deduction_not_in_invoice_price')
            if not documented or not quantifiable: issues.append('adjustment_'+ident+'_not_documented_quantifiable')
            if kind=='royalties':
                if not _bool(item.get('related_to_goods'),'royalty_related_to_goods') or not _bool(item.get('condition_of_sale'),'royalty_condition_of_sale'):
                    _fail('royalty_addition_conditions_not_met')
            apply=category=='deductions' or not included;rub=amount*rate if apply else ZERO
            output.append({'id':ident,'kind':kind,'original':str(amount),'currency':curr,**detail,
                'rub':str(rub),'included_in_price':included,'applied':apply,
                'documented_separately':documented,'quantifiable':quantifiable,
                'source_reference':ref,'tracks_base_fx':curr==currency and currency!='RUB'})
        adjustments[category]=output
    total=price*fx+sum((D(x['rub']) for x in adjustments['additions']),ZERO)-sum((D(x['rub']) for x in adjustments['deductions']),ZERO)
    if total<=0: _fail('customs_value_not_positive')
    if sum((D(x['rub']) for x in adjustments['deductions']),ZERO)>price*fx: _fail('deductions_exceed_invoice_price')
    currency_rates={currency:fx}
    for item in adjustments['additions']+adjustments['deductions']:
        item_rate=D(item['rub_per_unit'])
        if item['currency'] in currency_rates and currency_rates[item['currency']]!=item_rate: _fail('conflicting_fx_for_same_currency_date')
        currency_rates[item['currency']]=item_rate
    shipping=_obj(c.get('shipping_documents',{}),'shipping_documents')
    if not set(shipping)<=set(('invoice','packing_list','transport','specification','insurance')): _fail('shipping_document_type_unsupported')
    shipping={k:None if v is None else _text(v,'shipping_document') for k,v in shipping.items()}
    supported=not issues;scenarios=[]
    for shock in (D('.9'),D('1'),D('1.1')):
        factor=shock if currency!='RUB' else D(1);value=price*fx*factor
        for sign,category in ((D(1),'additions'),(D(-1),'deductions')):
            value+=sign*sum((D(x['rub'])*(factor if x['tracks_base_fx'] else D(1)) for x in adjustments[category]),ZERO)
        scenarios.append({'fx_rate':str(D(fx_detail['fx_rate'])*factor),'fx_nominal':fx_detail['fx_nominal'],
            'value_rub':_money(value) if value>0 else None,'scenario_valid':value>0,
            'assumption':'invoice_currency_only_sensitivity_not_forecast_or_official_fx'})
    return {'method':1,'declaration_date':when.isoformat(),'price_original':str(price),
        'price_source_reference':invoice_ref,'currency':currency,'fx_rate':fx_detail['fx_rate'],
        'fx_nominal':fx_detail['fx_nominal'],'fx_details':fx_detail,**adjustments,
        'value_rub_unrounded':str(total) if supported else None,'value_rub':_money(total) if supported else None,
        'candidate_value_rub':_money(total),'candidate_value_rub_unrounded':str(total),
        'fx_scenarios':scenarios,'parties':parties,'related_parties':related,'incoterms':incoterms,
        'incoterms_place':place,'documents':documents,'shipping_documents':shipping,
        'method1_supported':supported,'method1_conditions':dict(conditions),'method1_issues':issues,
        'method_source':method_source,'final_declaration':False,'user_confirmed':False,
        'assessment_basis':'caller_declared_conditions_not_authenticated',
        'limitations':['not_official_DTS','methods_2_to_6_not_calculated','incoterms_does_not_prove_cost_inclusion',
            'source_binding_and_method_applicability_require_host_review'],
        'formula':'invoice * FX/nominal + nonincluded additions - separately identified included deductions'}

def _quantity(x,name):
    quantity=_num(x.get('quantity'),name+'_quantity',positive=True)
    unit=_text(x.get('quantity_unit'),name+'_quantity_unit',40)
    rate_unit=_text(x.get('rate_unit'),name+'_rate_unit',40)
    if unit!=rate_unit: _fail(name+'_unit_mismatch_no_implicit_conversion')
    per=_num(x.get('per_units'),name+'_per_units',positive=True,maximum='1e9')
    return quantity/per, {'quantity':str(quantity),'quantity_unit':unit,'per_units':str(per),'rate_unit':rate_unit}

def _tariff(x,base,when,name):
    _obj(x,name);mode=x.get('mode')
    if mode not in ('ad_valorem','specific','combined_max','combined_min','combined_sum'): _fail(name+'_mode_unsupported')
    ad=ZERO;sp=ZERO;detail={'mode':mode}
    if mode!='specific':
        percent=_num(x.get('rate_percent'),name+'_rate_percent',maximum='1000');ad=base*percent/100
        detail.update({'rate_percent':str(percent),'ad_valorem_unrounded':str(ad)})
    if mode!='ad_valorem':
        qty,qdetail=_quantity(x,name);amount=_num(x.get('amount_per_unit'),name+'_amount_per_unit')
        currency=_currency(x.get('currency'),name+'_currency');rate,fxdetail=_fx(x,currency,when,name+'_fx')
        sp=amount*rate*qty
        detail.update({**qdetail,'amount_per_unit':str(amount),'fx':fxdetail,'specific_unrounded':str(sp)})
    if mode=='ad_valorem':result=ad;formula='customs_value * rate_percent / 100'
    elif mode=='specific':result=sp;formula='quantity / per_units * amount_per_unit * FX / nominal'
    elif mode=='combined_max':result=max(ad,sp);formula='max(ad_valorem_component, specific_component)'
    elif mode=='combined_min':result=min(ad,sp);formula='min(ad_valorem_component, specific_component)'
    else:result=ad+sp;formula='ad_valorem_component + specific_component'
    return result,formula,detail

def customs_payments(data):
    with localcontext(CTX): return _customs_payments(data)

def _customs_payments(c):
    when=_scope(c);code=_text(c.get('tnved_code'),'tnved_code',10)
    if not re.fullmatch('[0-9]{10}',code): _fail('tnved_code_10_digits_required')
    origin=_text(c.get('origin_country'),'origin_country',2)
    if not re.fullmatch('[A-Z]{2}',origin): _fail('origin_country_iso2_required')
    sources=_obj(c.get('rate_sources'),'rate_sources');keys=('duty','excise','vat','customs_fee','special_duties','rounding')
    if set(sources)!=set(keys): _fail('rate_sources_exact_keys_required')
    checks={k:_source(sources[k],'rate_'+k,when) for k in keys}
    rounding=_obj(c.get('rounding'),'rounding')
    if set(rounding)!=set(ROUND_FIELDS): _fail('rounding_exact_keys_required')
    quanta={}
    for k in ROUND_FIELDS:
        if rounding[k] not in ('0.01','1'): _fail('unsupported_rounding_quantum')
        quanta[k]=D(rounding[k])
    rawbase=_num(c.get('customs_value_rub'),'customs_value_rub',positive=True)
    base=rawbase.quantize(quanta['customs_value'],rounding=ROUND_HALF_UP)
    if base<=0: _fail('customs_value_zero_after_rounding')
    rawduty,formula,duty_detail=_tariff(c.get('duty'),base,when,'duty')
    duty=rawduty.quantize(quanta['duty'],rounding=ROUND_HALF_UP)
    excise_input=_obj(c.get('excise'),'excise');mode=excise_input.get('mode');excise_detail={'mode':mode}
    if mode=='not_applicable':
        reason=_text(excise_input.get('reason'),'excise_non_applicability_reason')
        rawexcise=ZERO;excise_formula='not_applicable_under_supplied_basis';excise_detail['reason']=reason
    elif mode=='specific':
        qty,qdetail=_quantity(excise_input,'excise')
        if excise_input.get('currency')!='RUB': _fail('excise_specific_rate_must_be_rub')
        amount=_num(excise_input.get('amount_per_unit'),'excise_amount_per_unit')
        rawexcise=qty*amount;excise_formula='excise_quantity / per_units * RUB_per_unit'
        excise_detail.update({**qdetail,'amount_per_unit':str(amount)})
    elif mode=='ad_valorem':
        percent=_num(excise_input.get('rate_percent'),'excise_rate_percent',maximum='1000')
        rawexcise=(base+duty)*percent/100;excise_formula='(customs_value + payable_import_duty) * excise_rate_percent / 100'
        excise_detail.update({'base':str(base+duty),'rate_percent':str(percent)})
    elif mode=='combined_retail':
        qty,qdetail=_quantity(excise_input,'excise')
        if excise_input.get('currency')!='RUB': _fail('excise_specific_rate_must_be_rub')
        amount=_num(excise_input.get('amount_per_unit'),'excise_amount_per_unit')
        retail_base=_num(excise_input.get('retail_value_rub'),'excise_retail_value_rub',positive=True)
        retail_ref=_text(excise_input.get('retail_value_reference'),'excise_retail_value_reference')
        percent=_num(excise_input.get('rate_percent'),'excise_rate_percent',maximum='1000')
        minimum=_num(excise_input.get('minimum_per_units_rub'),'excise_minimum_per_units_rub')
        combined=qty*amount+retail_base*percent/100;floor=qty*minimum;rawexcise=max(combined,floor)
        excise_formula='max(quantity/per_units * RUB_per_unit + retail_value * percent/100, quantity/per_units * minimum_RUB)'
        excise_detail.update({**qdetail,'amount_per_unit':str(amount),'retail_value_rub':str(retail_base),
            'retail_value_reference':retail_ref,'rate_percent':str(percent),'combined_unrounded':str(combined),
            'minimum_unrounded':str(floor),'minimum_per_units_rub':str(minimum)})
    else: _fail('excise_mode_unsupported')
    excise=rawexcise.quantize(quanta['excise'],rounding=ROUND_HALF_UP)
    vat_rate=_num(c.get('vat_rate_percent'),'vat_rate_percent',maximum='100');treatment=c.get('vat_treatment')
    if treatment not in ('taxable','exempt'): _fail('vat_treatment_required')
    if treatment=='exempt':
        if vat_rate!=0: _fail('exempt_vat_rate_must_be_zero')
        _text(c.get('vat_exemption_basis'),'vat_exemption_basis')
    elif vat_rate==0: _fail('zero_vat_requires_explicit_exemption')
    vat_base=base+duty+excise;rawvat=vat_base*vat_rate/100;vat=rawvat.quantize(quanta['vat'],rounding=ROUND_HALF_UP)
    rawfee=_num(c.get('customs_fee_rub'),'customs_fee_rub');fee=rawfee.quantize(quanta['customs_fee'],rounding=ROUND_HALF_UP)
    rawspecial=_num(c.get('special_duties_rub'),'special_duties_rub');special=rawspecial.quantize(quanta['special_duties'],rounding=ROUND_HALF_UP)
    special_basis=_text(c.get('special_duties_basis'),'special_duties_basis');total=duty+excise+vat+fee+special
    components={'duty':(rawduty,duty),'excise':(rawexcise,excise),'vat':(rawvat,vat),'customs_fee':(rawfee,fee),'special_duties':(rawspecial,special)}
    return {'declaration_date':when.isoformat(),'tnved_code':code,'origin_country':origin,
        'customs_value_rub':_money(base),'customs_value_rub_input':str(rawbase),
        'duty':_money(duty),'duty_formula':formula,'excise':_money(excise),'excise_formula':excise_formula,
        'vat_base':_money(vat_base),'vat_rate_percent':str(vat_rate),'vat_treatment':treatment,
        'vat_exemption_basis':c.get('vat_exemption_basis') if treatment=='exempt' else None,
        'vat':_money(vat),'customs_fee':_money(fee),'special_duties':_money(special),
        'special_duties_basis':special_basis,'total_advance_els':_money(total),
        'quantity':duty_detail.get('quantity'),'quantity_unit':duty_detail.get('quantity_unit'),
        'duty_breakdown':duty_detail,'excise_breakdown':excise_detail,
        'breakdown':{k:{'unrounded':str(raw),'rounded':_money(rounded),'quantum':str(quanta[k])} for k,(raw,rounded) in components.items()},
        'rounding':{**dict(rounding),'mode':'ROUND_HALF_UP','stage':'round_value_then_duty_then_excise_then_vat_sum_rounded_components'},
        'rate_checks':checks,'verification_required':'rates_applicability_and_rounding_on_declaration_date',
        'current_rates_verified':False,'user_confirmed':False,'payment_submitted':False,
        'limitations':['single_item_third_country_import_RU_only','fee_once_per_declaration_not_per_item',
            'special_duties_supplied_amount_not_tariff_resolution','special_duties_and_fee_excluded_from_vat_base',
            'recycling_fee_penalties_storage_and_broker_fees_excluded','preferences_exemptions_require_source_review',
            'not_a_payment_order_or_final_declaration']}

def input_units(function_id,data):
    """Expected units by schema, not by caller-supplied binding assertions.

    FX rate is the RUB quote for the explicit nominal foreign units, *not* a
    per-unit FX fact. Its evidence unit is RUB; nominal has the currency unit.
    Per-units and quantity have the physical unit, rate amount has currency.
    A host still needs semantic evidence that the quote applies to that nominal.
    """
    _obj(data,'data');out={}
    def fx(obj,prefix):
        currency=_currency(obj.get('currency'),'currency')
        out[prefix+'/fx_rate']='RUB';out[prefix+'/fx_nominal']=currency
    if function_id=='customs_value':
        out['/price']=_currency(data.get('currency'),'currency');fx(data,'')
        for cat in ('additions','deductions'):
            for i,x in enumerate(_list(data.get(cat),cat)):
                _obj(x,'adjustment');prefix='/'+cat+'/'+str(i)
                out[prefix+'/amount']=_currency(x.get('currency'),'currency');fx(x,prefix)
    elif function_id=='customs_payments':
        out.update({'/customs_value_rub':'RUB','/vat_rate_percent':'percent','/customs_fee_rub':'RUB','/special_duties_rub':'RUB'})
        for k in ROUND_FIELDS:out['/rounding/'+k]='RUB'
        for cat in ('duty','excise'):
            x=_obj(data.get(cat),cat);mode=x.get('mode');prefix='/'+cat
            if mode in ('ad_valorem','combined_max','combined_min','combined_sum','combined_retail'):out[prefix+'/rate_percent']='percent'
            if mode in ('specific','combined_max','combined_min','combined_sum','combined_retail'):
                unit=_text(x.get('quantity_unit'),'quantity_unit',40)
                out[prefix+'/quantity']=unit;out[prefix+'/per_units']=_text(x.get('rate_unit'),'rate_unit',40)
                out[prefix+'/amount_per_unit']=_currency(x.get('currency'),'currency')
                if cat=='duty':fx(x,prefix)
                if mode=='combined_retail':out[prefix+'/retail_value_rub']='RUB';out[prefix+'/minimum_per_units_rub']='RUB'
    else:_fail('input_units_unknown_function')
    when=_day(data.get('declaration_date'),'declaration_date').isoformat()
    return {p:{'unit':u,'effective_date':when} if p.endswith(('/fx_rate','/fx_nominal')) else u for p,u in out.items()}

def source_ids(function_id,data):
    """All documentary reference fields requiring host evidence binding.

    Values are declared reference strings (host aliases or fact IDs), not proof.
    Narrative basis fields are not promoted to source identity; their normative
    source is the corresponding mandatory rate_sources entry.
    """
    out={}
    def add(pointer,value):out[pointer]=_text(value,'evidence_reference')
    if function_id=='customs_value':
        add('/price_source_reference',data.get('price_source_reference'))
        add('/fx_source_reference',data.get('fx_source_reference'))
        add('/method_source/reference',_obj(data.get('method_source'),'method_source').get('reference'))
        for category in ('additions','deductions'):
            for i,x in enumerate(_list(data.get(category),category)):
                _obj(x,'adjustment')
                for key in ('source_reference','fx_source_reference'):add('/'+category+'/'+str(i)+'/'+key,x.get(key))
        # documents and shipping_documents are descriptive labels, not source IDs.
    elif function_id=='customs_payments':
        sources=_obj(data.get('rate_sources'),'rate_sources')
        for key in ('duty','excise','vat','customs_fee','special_duties','rounding'):
            add('/rate_sources/'+key+'/reference',_obj(sources.get(key),'rate_source').get('reference'))
        duty=_obj(data.get('duty'),'duty')
        if duty.get('mode') in ('specific','combined_max','combined_min','combined_sum'):add('/duty/fx_source_reference',duty.get('fx_source_reference'))
        excise=_obj(data.get('excise'),'excise')
        if excise.get('mode')=='combined_retail':add('/excise/retail_value_reference',excise.get('retail_value_reference'))
    else:_fail('source_ids_unknown_function')
    return out

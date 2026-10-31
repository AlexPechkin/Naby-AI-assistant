"""Pure customs profession dispatch. Application integration is done by Naby."""
import copy,hashlib,json
from decimal import localcontext,Context
from . import calculations,scenarios

FUNCTIONS=('tnved_classification','customs_value','customs_payments','declaration','non_tariff','origin','trade_contract','post_clearance')

def reject_proposed_authority(value,depth=0):
    """Declared business conditions cannot carry host-generated trust markers."""
    if depth>32:raise ValueError('proposal_nesting_limit')
    if type(value) is dict:
        for key,item in value.items():
            if type(key) is not str:raise ValueError('proposal_string_keys_required')
            if key in {'authorization_established','approval_established','clinical_approval','freshness','current_law','practice_right'}:
                raise ValueError('reserved_authority_field:'+key)
            if key.endswith(('_verified','_confirmed','_approved','_signed','_approval_established','_authorization_established')) or key in {
                'verified','confirmed','approved','trusted','is_trusted','user_approval','approved_by_user','authorized','host_context','assignment_context',
                'signed','signature_applied','official_declaration','official_fcs_schema','final_declaration','bank_submission_performed','submission_performed','external_actions','final_classification',
                'final_origin_determination','legality_conclusion','payment_submitted'}:
                raise ValueError('reserved_authority_field:'+key)
            reject_proposed_authority(item,depth+1)
    elif type(value) is list:
        for item in value:reject_proposed_authority(item,depth+1)

def strict_snapshot(value):
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise ValueError('duplicate_json_key')
            result[k]=v
        return result
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False,separators=(',',':'))
    if len(raw.encode('utf8'))>2_000_000:raise ValueError('config_size_limit')
    return json.loads(raw,object_pairs_hook=pairs),hashlib.sha256(raw.encode('utf8')).hexdigest()

def execute(function_id,config):
    if type(function_id) is not str or function_id not in FUNCTIONS:raise ValueError('unknown_customs_function')
    if type(config) is not dict or set(config)!={'function','data'} or config['function']!=function_id or type(config['data']) is not dict:
        raise ValueError('function_config_mismatch')
    reject_proposed_authority(config['data'])
    original,digest=strict_snapshot(config)
    module=calculations if function_id in ('customs_value','customs_payments') else scenarios
    with localcontext(Context(prec=60)):
        result=getattr(module,function_id)(copy.deepcopy(original['data']))
    result=copy.deepcopy(result)
    result['input_sha256']=digest
    result['source_semantics_verified']=False
    result['current_legal_applicability_verified']=False
    result['external_actions']=False
    return result

def input_units(function_id,data):
    module=calculations if function_id in ('customs_value','customs_payments') else scenarios
    return module.input_units(function_id,data)

"""Pure profession calculations and review, never an actuarial approval."""
import copy,hashlib,json
from importlib import import_module
from decimal import Context,localcontext,DecimalException
FUNCTIONS=('data_assumptions','actuarial_task','tariff','reserves','life_pension','mandatory_assessment','ifrs17','solvency_stress','actuary_status')
CALCULATIONS=frozenset(('tariff','reserves','life_pension'))
RESERVED=frozenset(('engagement_context','confirmed_by_user','data_scope_agreed','task_agreed','engagement_agreed','accounting_policy_approved_by_insurer','tariffs_applied','reserves_approved','accounting_policy_approved','signature_applied','report_submitted','professional_status_granted','approved_tariff','approved_reserve','registered','attested','qualification_granted','practice_authorized','authorization_established','approval_established','clinical_approval','freshness','current_law','practice_right','current_rule_chain_complete','actual_weekly_update_performed','last_confirmed_database','last_verified_snapshot','last_verified_at','actual_success_at','verified','confirmed','approved','signed','trusted','is_trusted','user_approval','approved_by_user','authorized','host_context','assignment_context','external_actions','official_report','calculation_allowed','host_agreement_received','assignment_user_confirmation_received'))
def reject_proposed_authority(value,depth=0):
    if depth>32:raise ValueError('proposal_nesting_limit')
    if type(value) is dict:
        for key,item in value.items():
            if type(key) is not str:raise ValueError('proposal_string_keys_required')
            if key in RESERVED or key.endswith(('_verified','_confirmed','_approved','_signed','_approval_established','_authorization_established')):
                raise ValueError('reserved_authority_field:'+key)
            reject_proposed_authority(item,depth+1)
    elif type(value) is list:
        for item in value:reject_proposed_authority(item,depth+1)
def strict_snapshot(value):
    try:raw=json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False,separators=(',',':'))
    except (TypeError,OverflowError,RecursionError):raise ValueError('bounded_json_config_required') from None
    if len(raw.encode('utf8'))>2_000_000:raise ValueError('config_size_limit')
    return json.loads(raw),hashlib.sha256(raw.encode('utf8')).hexdigest()
def module_for(function):
    if type(function) is not str or function not in FUNCTIONS:raise ValueError('unknown_actuary_function')
    return import_module('.calculations' if function in CALCULATIONS else '.scenarios',__package__)
def execute(function_id,config):
    module=module_for(function_id)
    if type(config) is not dict or set(config)!={'function','data'} or config['function']!=function_id or type(config['data']) is not dict:
        raise ValueError('function_config_mismatch')
    reject_proposed_authority(config['data']);original,digest=strict_snapshot(config)
    with localcontext(Context(prec=128)):
        try:result=getattr(module,function_id)(copy.deepcopy(original['data']))
        except (KeyError,AttributeError,TypeError,IndexError):raise ValueError('invalid_subject_input_structure') from None
        except (DecimalException,OverflowError,ZeroDivisionError):raise ValueError('bounded_actuarial_calculation_required') from None
    result=copy.deepcopy(result)
    result.update(input_sha256=digest,source_semantics_verified=False,current_legal_applicability_verified=False,external_actions=False,analysis_only=True,
        tariffs_applied=False,reserves_approved=False,accounting_policy_approved=False,signature_applied=False,report_submitted=False,professional_status_granted=False)
    strict_snapshot(result);return result
def input_units(function_id,data):
    try:return module_for(function_id).input_units(function_id,data)
    except (KeyError,AttributeError,TypeError,IndexError):raise ValueError('invalid_numeric_input_structure') from None
def selected_texts(function_id,data):
    callback=getattr(module_for(function_id),'selected_texts',None)
    try:return callback(function_id,data) if callback else {}
    except (KeyError,AttributeError,TypeError,IndexError):raise ValueError('invalid_selected_text_structure') from None

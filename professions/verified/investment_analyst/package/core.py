"""Pure profession dispatch; host integration is done by Naby."""
import copy,hashlib,json
from decimal import localcontext,Context
from . import calculations,scenarios
FUNCTIONS=('issuer_disclosure','valuation_model','peer_comparison','bond_analysis','research_report','investor_status','insider_compliance','portfolio_scenarios','investor_tax')
CALCULATIONS=frozenset(('valuation_model','peer_comparison','bond_analysis','portfolio_scenarios'))

def reject_proposed_authority(value,depth=0):
    if depth>32:raise ValueError('proposal_nesting_limit')
    if type(value) is dict:
        for key,item in value.items():
            if type(key) is not str:raise ValueError('proposal_string_keys_required')
            if key in {'authorization_established','approval_established','clinical_approval','freshness','current_law','practice_right'}:
                raise ValueError('reserved_authority_field:'+key)
            if key in {'orders_submitted','qualified_status_granted','tax_filing_performed','publication_cleared','broker_authorized','investor_status_decision','publication_clearance','qualification_decision','testing_passed','inside_information_determination','manipulation_determination','relief_eligibility'}:
                raise ValueError('reserved_authority_field:'+key)
            if key in {'current_rule_chain_complete','actual_weekly_update_performed','last_confirmed_database','complete_disclosure_established','last_verified_snapshot','last_verified_at','actual_success_at'}:
                raise ValueError('reserved_authority_field:'+key)
            if key.endswith(('_verified','_confirmed','_approved','_signed','_approval_established','_authorization_established')) or key in {'verified','confirmed','approved','signed','trusted','is_trusted','user_approval','approved_by_user','authorized','host_context','assignment_context','submission_performed','external_actions','final_classification','final_origin_determination','legality_conclusion','payment_submitted','official_report','official_expertise','signature_applied','credit_decision_made','calculation_allowed','host_agreement_received','assignment_user_confirmation_received'}:
                raise ValueError('reserved_authority_field:'+key)
            reject_proposed_authority(item,depth+1)
    elif type(value) is list:
        for item in value:reject_proposed_authority(item,depth+1)

def strict_snapshot(value):
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False,separators=(',',':'))
    if len(raw.encode('utf8'))>2_000_000:raise ValueError('config_size_limit')
    return json.loads(raw),hashlib.sha256(raw.encode('utf8')).hexdigest()

def execute(function_id,config):
    if type(function_id) is not str or function_id not in FUNCTIONS:raise ValueError('unknown_investment_function')
    if type(config) is not dict or set(config)!={'function','data'} or config['function']!=function_id or type(config['data']) is not dict:raise ValueError('function_config_mismatch')
    reject_proposed_authority(config['data'])
    try:original,digest=strict_snapshot(config)
    except (TypeError,OverflowError,RecursionError):raise ValueError('bounded_json_config_required') from None
    module=calculations if function_id in CALCULATIONS else scenarios
    with localcontext(Context(prec=128)):
        try:result=getattr(module,function_id)(copy.deepcopy(original['data']))
        except (KeyError,AttributeError,TypeError,IndexError):raise ValueError('invalid_subject_input_structure') from None
    result=copy.deepcopy(result)
    result.update(input_sha256=digest,source_semantics_verified=False,current_legal_applicability_verified=False,external_actions=False,
      analysis_only=True,publication_authorization_established=False,orders_submitted=False,qualified_status_granted=False,tax_filing_performed=False)
    return result

def input_units(function_id,data):
    if function_id not in FUNCTIONS:raise ValueError('unknown_investment_function')
    try:return (calculations if function_id in CALCULATIONS else scenarios).input_units(function_id,data)
    except (KeyError,AttributeError,TypeError,IndexError):raise ValueError('invalid_numeric_input_structure') from None

def selected_texts(function_id,data):
    module=calculations if function_id in CALCULATIONS else scenarios
    callback=getattr(module,'selected_texts',None)
    try:return callback(function_id,data) if callback else {}
    except (KeyError,AttributeError,TypeError,IndexError):raise ValueError('invalid_selected_text_structure') from None

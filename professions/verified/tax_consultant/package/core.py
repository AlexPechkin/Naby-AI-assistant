"""Pure selected-source RU tax assistance; no filing, payment or legal approval."""
import copy,hashlib,json
from importlib import import_module
from decimal import Context,localcontext,DecimalException
from datetime import date
from .privacy import reject_known_secret_material

FUNCTIONS=('law_monitoring','regime_choice','transaction_structuring','tax_audit_support','objections_appeal','penalties_mitigation','individual_3ndfl','tax_accounting_method','ens_dispute','client_engagement')
MODULES={**dict.fromkeys(('regime_choice','transaction_structuring','individual_3ndfl'),'.tax_models'),**dict.fromkeys(('tax_audit_support','objections_appeal','penalties_mitigation','ens_dispute'),'.tax_procedure'),**dict.fromkeys(('law_monitoring','tax_accounting_method','client_engagement'),'.tax_practice')}
RESERVED=frozenset(('methodology_approved','report_certified','carbon_units_issued','project_registered','edition_verified_by_human','host_context','assignment_context','engagement_context','confirmed_by_user','registered','authorization_established','approval_established','clinical_approval','freshness','current_law','practice_right','current_rule_chain_complete','actual_weekly_update_performed','last_confirmed_database','last_verified_snapshot','last_verified_at','actual_success_at','verified','confirmed','approved','signed','trusted','is_trusted','user_approval','approved_by_user','authorized','external_actions','official_report','calculation_allowed','design_approved','model_certified','fitness_for_use_certified','technical_category_assigned','drawings_issued','signature_applied','submission_performed','physical_work_authorized','normative_applicability_established','design_compliance_established','design_approval','solver_executed','graphical_content_generated','verification_calculation_performed','responsible_signature_status'))

RESERVED=RESERVED|frozenset(('verified_against_law','human_confirmed','human_reviewed','source_checked','source_validated','rule_checked','court_verified','current_law_verified','case_verified','rights_confirmed'))

def reject_proposed_authority(value,depth=0):
    if depth>32:raise ValueError('proposal_nesting_limit')
    if type(value) is dict:
        for key,item in value.items():
            if type(key) is not str:raise ValueError('proposal_string_keys_required')
            if key in RESERVED or key.endswith(('_verified','_confirmed','_approved','_signed','_approval_established','_authorization_established','_verified_by_human','_checked_by_human','_confirmed_by_human')):raise ValueError('reserved_authority_field:'+key)
            reject_proposed_authority(item,depth+1)
    elif type(value) is list:
        for item in value:reject_proposed_authority(item,depth+1)

def strict_snapshot(value):
    try:raw=json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False,separators=(',',':'))
    except (TypeError,OverflowError,RecursionError):raise ValueError('bounded_json_config_required') from None
    if len(raw.encode('utf8'))>2_000_000:raise ValueError('config_size_limit')
    return json.loads(raw),hashlib.sha256(raw.encode('utf8')).hexdigest()

def module_for(function):
    if type(function) is not str or function not in FUNCTIONS:raise ValueError('unknown_tax_consultant_function')
    return import_module(MODULES[function],__package__)

def common(data):
    if type(data) is not dict or data.get('jurisdiction')!='RU':raise ValueError('explicit_RU_jurisdiction_required')
    value=data.get('as_of')
    if type(value) is not str:raise ValueError('as_of_date_required')
    try:parsed=date.fromisoformat(value)
    except ValueError:raise ValueError('as_of_date_required') from None
    if parsed.isoformat()!=value:raise ValueError('as_of_date_required')

def execute(function_id,config):
    if type(function_id) is not str or function_id not in FUNCTIONS:raise ValueError('unknown_tax_consultant_function')
    if type(config) is not dict or set(config)!={'function','data'} or config['function']!=function_id or type(config['data']) is not dict:raise ValueError('function_config_mismatch')
    reject_proposed_authority(config['data']);reject_known_secret_material(config['data']);original,digest=strict_snapshot(config);common(original['data']);module=module_for(function_id)
    with localcontext(Context(prec=180)):
        try:result=module.execute(function_id,copy.deepcopy(original['data']))
        except (KeyError,AttributeError,TypeError,IndexError):raise ValueError('invalid_subject_input_structure') from None
        except (DecimalException,OverflowError,ZeroDivisionError):raise ValueError('bounded_tax_calculation_required') from None
    if type(result) is not dict:raise ValueError('subject_result_object_required')
    # Prepared provider formats can decode escaped credential markers. Apply the
    # same narrow guard to actual decoded output before it can be echoed/exported.
    reject_known_secret_material(result)
    result=copy.deepcopy(result)
    result.update(input_sha256=digest,source_semantics_verified=False,current_legal_applicability_verified=False,external_actions=False,analysis_only=True,
        methodology_approved=False,model_certified=False,report_certified=False,signature_applied=False,submission_performed=False,physical_work_authorized=False)
    for name in ('declaration_submitted','taxes_paid','documents_signed','case_submitted','representation_performed','legal_applicability_certified','tax_authority_decision_verified','counterparty_registry_checked','client_right_or_eligibility_confirmed','calendar_legally_verified','data_sent_external','signature_verified','registry_submitted','published'):
        result[name]=False
    strict_snapshot(result);return result

def input_units(function_id,data):
    common(data)
    reject_known_secret_material(data)
    with localcontext(Context(prec=180)):
        try:return module_for(function_id).input_units(function_id,data)
        except (KeyError,AttributeError,TypeError,IndexError):raise ValueError('invalid_numeric_input_structure') from None
        except (DecimalException,OverflowError,ZeroDivisionError):raise ValueError('bounded_tax_calculation_required') from None

def selected_texts(function_id,data):
    reject_known_secret_material(data)
    callback=getattr(module_for(function_id),'selected_texts',None)
    with localcontext(Context(prec=180)):
        try:return callback(function_id,data) if callback else {}
        except (KeyError,AttributeError,TypeError,IndexError):raise ValueError('invalid_selected_text_structure') from None
        except (DecimalException,OverflowError,ZeroDivisionError):raise ValueError('bounded_tax_calculation_required') from None

"""Appraisal subject facade; existing NABY handles selection, policy and saving."""
import hashlib,json,re
from .core import execute,FUNCTIONS
from .binding import verify
from .assignment_gate import verify_confirmation

def _pairs(items):
    result={}
    for key,value in items:
        if key in result:raise ValueError('duplicate_json_key')
        result[key]=value
    return result

def _constant(_):raise ValueError('nonfinite_json')

def run(function,proposal_json,documents,language='ru',review='preview',*,assignment_context=None):
    if function not in FUNCTIONS or language not in ('ru','en','zh') or review not in ('preview','calculate'):
        raise ValueError('function_language_review_required')
    if type(proposal_json) is not str or len(proposal_json.encode('utf8'))>2_000_000:raise ValueError('bounded_json_required')
    try:config=json.loads(proposal_json,object_pairs_hook=_pairs,parse_constant=_constant)
    except RecursionError:raise ValueError('proposal_nesting_limit') from None
    json.dumps(config,allow_nan=False)
    facts,evidence=verify(function,config,documents)
    confirmation=verify_confirmation(function,config['data'],assignment_context,facts,documents,config['as_of'])
    evidence['assignment_confirmation']=confirmation
    if confirmation['required'] and not confirmation['received']:
        if review=='calculate':raise ValueError('assignment_confirmation_required')
        return {'function':function,'result':None,'files':{},'evidence':evidence,
          'status':'assignment_confirmation_required','proposed_scope':confirmation['scope'],
          'user_message':{
            'ru':'Согласуйте задание: объект, права, дату, валюту, цель и вид стоимости. После этого можно выполнить расчёт.',
            'en':'Confirm the assignment: property, rights, valuation date, currency, purpose and value type. The calculation can then proceed.',
            'zh':'请确认估价任务：对象、权利、估价日期、币种、目的及价值类型。确认后即可计算。'}[language],
          'proposal_sha256':hashlib.sha256(proposal_json.encode('utf8')).hexdigest(),
          'review':review,'private':True,'external_network_used':False,'records_changed':False,
          'host_integration_required':True,'source_semantics_verified':False}
    domain_config={'function':function,'data':config['data']}
    result=execute(function,domain_config)
    files={}
    if review=='calculate':
        from .artifacts import render
        files=render(function,result,language,config=domain_config,review_evidence=evidence)
        if not files or len(files)>30:raise ValueError('bounded_artifacts_required')
        for name,raw in files.items():
            if type(name) is not str or not re.fullmatch(r'[A-Za-z0-9_-]+\.(?:json|docx|xlsx|pdf|xml|html|txt|csv)',name):raise ValueError('artifact_name')
            if type(raw) is not bytes or not raw or len(raw)>24_000_000:raise ValueError('artifact_bytes')
        files['selected_evidence.json']=(json.dumps({'facts':facts,'review':evidence},ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8')
    return {'function':function,'result':result,'files':files,'evidence':evidence,
      'proposal_sha256':hashlib.sha256(proposal_json.encode('utf8')).hexdigest(),
      'review':review,'private':True,'external_network_used':False,'records_changed':False,
      'host_integration_required':True,'source_semantics_verified':False}

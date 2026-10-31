"""Tax profession facade; the host owns real selection, policy and file saving."""
import hashlib,json,re
from .core import execute,FUNCTIONS
from .binding import verify

def _pairs(items):
    result={}
    for key,value in items:
        if key in result:raise ValueError('duplicate_json_key')
        result[key]=value
    return result

def _constant(_):raise ValueError('nonfinite_json')

def validate_artifacts(files,function,data):
    """Validate bounded draft output basenames, never user-controlled paths."""
    if type(files) is not dict or not 1<=len(files)<=30:raise ValueError('bounded_artifacts_required')
    for name,raw in files.items():
        if type(name) is not str or len(name)>200 or not re.fullmatch(r'[A-Za-z0-9_-]+\.(?:json|docx|xlsx|pdf|xml|html|txt|csv|md)',name):raise ValueError('artifact_name')
        if type(raw) is not bytes or not 1<=len(raw)<=24_000_000:raise ValueError('artifact_bytes')
    return files

def run(function,proposal_json,documents,language='ru',review='preview'):
    if function not in FUNCTIONS or language not in ('ru','en','zh') or review not in ('preview','calculate'):
        raise ValueError('function_language_review_required')
    if type(proposal_json) is not str or len(proposal_json.encode('utf8'))>2_000_000:raise ValueError('bounded_json_required')
    try:config=json.loads(proposal_json,object_pairs_hook=_pairs,parse_constant=_constant)
    except RecursionError:raise ValueError('proposal_nesting_limit') from None
    json.dumps(config,allow_nan=False)
    facts,evidence=verify(function,config,documents)
    domain_config={'function':function,'data':config['data']}
    result=execute(function,domain_config)
    files={}
    if review=='calculate':
        from .artifacts import render
        files=render(function,result,language,config=domain_config,review_evidence=evidence)
        validate_artifacts(files,function,config['data'])
        files['selected_evidence.json']=(json.dumps({'facts':facts,'review':evidence},ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8')
    return {'function':function,'result':result,'files':files,'evidence':evidence,
      'proposal_sha256':hashlib.sha256(proposal_json.encode('utf8')).hexdigest(),
      'review':review,'private':True,'external_network_used':False,'records_changed':False,
      'host_integration_required':True,'source_semantics_verified':False}

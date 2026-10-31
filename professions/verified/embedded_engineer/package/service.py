"""Climate profession subject facade; existing NABY handles selection, policy and saving."""
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
    """Validate ordinary files and exact inert logical-source text companions."""
    if type(files) is not dict or not files:raise ValueError('bounded_artifacts_required')
    sources=data.get('source_files',[])
    if type(sources) is not list or len(sources)>200:raise ValueError('source_file_list_required')
    ordinary=0;source_texts=0
    for name,raw in files.items():
        if type(name) is not str or len(name)>200 or not re.fullmatch(r'[A-Za-z0-9_-]+\.(?:json|docx|xlsx|pdf|xml|html|txt|csv|md)',name):raise ValueError('artifact_name')
        if type(raw) is not bytes or len(raw)>24_000_000:raise ValueError('artifact_bytes')
        match=re.fullmatch(r'program_source_([1-9]\d{0,2})\.txt',name)
        if name.startswith('program_source_') and not match:raise ValueError('source_text_artifact_name')
        if match:
            source_texts+=1;index=int(match.group(1))-1
            if function not in ('fw_code','sw_docs_rights') or source_texts>200 or index>=len(sources):raise ValueError('source_text_artifact_index')
            content=sources[index].get('content') if type(sources[index]) is dict else None
            if type(content) is not str or raw!=content.encode('utf8'):raise ValueError('source_text_artifact_content_mismatch')
        else:
            ordinary+=1
            if ordinary>30 or not raw:raise ValueError('bounded_artifacts_required')
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

"""Match a HOST-ONLY task confirmation to selected assignment and proposed scope.

This module does not authenticate the application or legal validity of a contract.
The adapter must derive this argument from the current user's existing host state,
never from an LLM proposal, a source document's instructions or a model bool.
"""
from datetime import datetime,date
import re
GATED=frozenset(('market_analysis','sales_comparison','income_approach','cost_approach','valuation_report'))
SCOPE_KEYS={'object_id','rights','valuation_date','currency','purpose','value_type'}

def task_scope(value):
    if type(value) is not dict or set(value)!=SCOPE_KEYS:raise ValueError('assignment_scope_required')
    if any(type(v) is not str or not v.strip() or len(v)>2000 for v in value.values()):raise ValueError('assignment_scope_text_required')
    if not re.fullmatch('[A-Z]{3}',value['currency']):raise ValueError('assignment_scope_currency')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value['valuation_date']):raise ValueError('assignment_scope_date')
    try:date.fromisoformat(value['valuation_date'])
    except ValueError:raise ValueError('assignment_scope_date') from None
    return dict(value)

def verify_confirmation(function,data,context,facts,documents,as_of):
    if function not in GATED:return {'required':False,'received':False,'legal_contract_validity_verified':False}
    proposed=task_scope(data.get('task_scope'))
    if context is None:return {'required':True,'received':False,'scope':proposed,'legal_contract_validity_verified':False}
    if type(context) is not dict or set(context)!={'kind','event_id','confirmed_at','source_sha256','scope'}:raise ValueError('host_assignment_context_required')
    if context['kind']!='assignment_confirmation':raise ValueError('host_assignment_context_kind')
    if type(context['event_id']) is not str or not re.fullmatch('[A-Za-z0-9_.:-]{1,160}',context['event_id']):raise ValueError('host_assignment_event_required')
    digest=context['source_sha256']
    if type(digest) is not str or not re.fullmatch('[0-9a-f]{64}',digest) or digest not in documents:raise ValueError('assignment_source_not_selected')
    if task_scope(context['scope'])!=proposed:raise ValueError('confirmed_assignment_scope_mismatch')
    ref=data.get('assignment_reference')
    if type(ref) is not str or ref not in facts or facts[ref]['source_sha256']!=digest:raise ValueError('assignment_reference_mismatch')
    stamp=context['confirmed_at']
    if type(stamp) is not str or len(stamp)>50:raise ValueError('assignment_confirmation_timestamp')
    try:when=datetime.fromisoformat(stamp)
    except ValueError:raise ValueError('assignment_confirmation_timestamp') from None
    if when.tzinfo is None or when.utcoffset() is None or when.date()>date.fromisoformat(as_of):raise ValueError('assignment_confirmation_date')
    return {'required':True,'received':True,'scope':proposed,'source_sha256':digest,'host_event_id':context['event_id'],
      'confirmed_at':stamp,'legal_contract_validity_verified':False,'professional_independence_verified':False}

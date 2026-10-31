"""Host-only scope confirmation, checked before any valuation arithmetic."""
import re
from .evidence import day
GUARDED=frozenset(('tariff','reserves','life_pension','mandatory_assessment','ifrs17','solvency_stress'))
FIELDS={'confirmed_by_user','valuation_date','data_scope','source_sha256s'}
def verify_confirmation(function,data,context,documents):
    if type(data) is not dict:raise ValueError('data_object_required')
    if data.get('jurisdiction')!='RU':raise ValueError('actuary_RU_jurisdiction_required')
    asof=day(data.get('as_of'));valuation=day(data.get('valuation_date'))
    if valuation>asof:raise ValueError('valuation_date_after_analysis_cutoff')
    scope=data.get('data_scope')
    if type(scope) is not str or not scope.strip() or len(scope)>4000:raise ValueError('explicit_data_scope_required')
    if type(documents) is not dict or not 1<=len(documents)<=12:raise ValueError('selected_documents_required')
    if any(type(digest) is not str or not re.fullmatch('[0-9a-f]{64}',digest) for digest in documents):raise ValueError('selected_document_hash_required')
    expected=dict(valuation_date=data['valuation_date'],data_scope=scope,source_sha256s=sorted(documents))
    required=function in GUARDED
    if context is None:
        return dict(required=required,received=False,scope=expected,source='host_context_absent',contract_signature_established=False)
    if type(context) is not dict or set(context)!=FIELDS:raise ValueError('host_engagement_context_fields_required')
    if context['confirmed_by_user'] is not True:raise ValueError('host_engagement_confirmation_required')
    if type(context['source_sha256s']) is not list or context['source_sha256s']!=expected['source_sha256s'] or context['valuation_date']!=expected['valuation_date'] or context['data_scope']!=expected['data_scope']:
        raise ValueError('host_engagement_scope_mismatch')
    return dict(required=required,received=True,scope=expected,source='host_only_argument',contract_signature_established=False,
        source_authenticity_established=False,legal_authority_established=False)

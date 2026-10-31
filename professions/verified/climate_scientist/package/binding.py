"""Bind climate_scientist inputs to selected evidence without granting legal trust."""
import copy,hashlib,json,re
from decimal import Decimal,InvalidOperation,localcontext,Context
from .evidence import prepare,day,exact_number
from .core import input_units,reject_proposed_authority,selected_texts

# Fixed physical/unit conversions only; no expression, regulatory formula or
# conversion guessed from an ambiguous '%' label. Original evidence stays intact.
CONVERSIONS={
    'percent_to_ratio':('percent','ratio',Decimal('0.01')),
}

def unit_spec(expected):
    if type(expected) is str:
        unit=expected
    elif type(expected) is dict and 'unit' in expected and not set(expected)-{'unit','effective_date','not_after','effective_not_after','published_not_after','source_references'}:
        unit=expected['unit']
        for key,value in expected.items():
            if key not in ('unit','source_references') and value is not None:day(value)
        if 'source_references' in expected:
            references=expected['source_references']
            if type(references) is not list or not 1<=len(references)<=100 or any(type(identity) is not str or not 1<=len(identity)<=80 or not identity.strip() for identity in references):
                raise ValueError('numeric_source_reference_ids_required')
            if len(set(references))!=len(references):raise ValueError('duplicate_numeric_source_reference')
    else:raise ValueError('invalid_subject_unit_contract')
    if type(unit) is not str or not unit.strip() or len(unit)>100:raise ValueError('invalid_subject_unit_contract')
    return unit

def bound_number(fact,expected_unit,operation=None):
    if fact is None or 'value' not in fact:raise ValueError('bound_fact_or_unit_mismatch')
    original=exact_number(fact['value'])
    if operation is None:
        if fact['unit']!=expected_unit:raise ValueError('bound_fact_or_unit_mismatch')
        return original,None
    if type(operation) is not str or operation not in CONVERSIONS:raise ValueError('unsupported_unit_conversion')
    source_unit,target_unit,multiplier=CONVERSIONS[operation]
    if fact['unit']!=source_unit or expected_unit!=target_unit:raise ValueError('unit_conversion_dimension_mismatch')
    with localcontext(Context(prec=80)):converted=original*multiplier
    return converted,dict(operation=operation,source_value=fact['value'],source_unit=source_unit,
        derived_value=format(converted,'f'),derived_unit=target_unit)

def pointer(data,path):
    if type(path) is not str or not path.startswith('/') or len(path)>2000:
        raise ValueError('json_pointer_required')
    value=data
    for part in path[1:].split('/'):
        if re.search(r'~(?![01])',part):raise ValueError('invalid_pointer_escape')
        key=part.replace('~1','/').replace('~0','~')
        if type(value) is dict:
            if key not in value:raise ValueError('binding_pointer_missing')
            value=value[key]
        elif type(value) is list:
            if not re.fullmatch(r'0|[1-9]\d*',key) or int(key)>=len(value):raise ValueError('binding_index')
            value=value[int(key)]
        else:raise ValueError('binding_noncontainer')
    return value

def cited_ids(value):
    """Fields explicitly designated as evidence IDs by the subject contract."""
    if type(value) is dict:
        for key,item in value.items():
            if (key=='reference' or key.endswith('_reference')) and item is not None:
                if type(item) is not str:raise ValueError('source_reference_id_required')
                yield item
            elif key=='source_references' or key.endswith('_refs'):
                lists=item.values() if type(item) is dict else [item]
                for values in lists:
                    if type(values) is not list or any(type(v) is not str for v in values):raise ValueError('source_reference_ids_required')
                    yield from values
            else:yield from cited_ids(item)
    elif type(value) is list:
        for item in value:yield from cited_ids(item)

def quoted_fields(value,path=''):
    """Literal quotations require a real file, not just any selected citation."""
    if type(value) is dict:
        for key,item in value.items():
            child=path+'/'+key.replace('~','~0').replace('/','~1')
            if key in ('quote','excerpt') and item is not None:
                if type(item) is not str:raise ValueError('quoted_text_required')
                yield child,item
            else:yield from quoted_fields(item,child)
    elif type(value) is list:
        for i,item in enumerate(value):yield from quoted_fields(item,path+'/'+str(i))

def verify_selected_texts(data,texts,facts,documents):
    texts=dict(texts)
    for path,value in quoted_fields(data):
        if type(texts.get(path)) is dict:
            if texts[path].get('text')!=value:raise ValueError('literal_contract_differs_from_quote')
        else:texts[path]=value
    if len(texts)>2000:raise ValueError('selected_text_limit')
    proof=[]
    joined={digest:'\n'.join(s['source'] for s in doc['segments']) for digest,doc in documents.items()}
    for path,proposed in texts.items():
        scoped_references=None
        if type(proposed) is dict:
            if set(proposed)!={'text','source_references'}:raise ValueError('scoped_literal_contract_required')
            scoped_references=proposed['source_references']
            if type(scoped_references) is not list or not 1<=len(scoped_references)<=100 or any(type(identity) is not str or not 1<=len(identity)<=80 or not identity.strip() for identity in scoped_references):
                raise ValueError('literal_source_reference_ids_required')
            if len(set(scoped_references))!=len(scoped_references):raise ValueError('duplicate_literal_source_reference')
            proposed=proposed['text']
        if type(proposed) is not str or not proposed.strip():raise ValueError('selected_text_required:'+path)
        parent_path,_,field=path.rpartition('/')
        record=pointer(data,parent_path) if parent_path else data
        ids=[];explicit=False
        if type(record) is dict:
            stem=field[:-5] if field.endswith('_text') else ''
            scalar_keys=('source_reference',)+((stem+'_source_reference',) if stem else ())
            for key in scalar_keys:
                if key in record:
                    explicit=True
                    if type(record[key]) is not str:raise ValueError('quoted_text_reference_required')
                    ids.append(record[key])
            for key in ('evidence_refs','source_references'):
                if key in record:
                    explicit=True
                    if type(record[key]) is not list or any(type(v) is not str for v in record[key]):raise ValueError('quoted_text_references_required')
                    ids.extend(record[key])
        if explicit and not ids:raise ValueError('quoted_text_reference_required')
        # Structured callbacks select their source context from the validated
        # domain schema. Unused extra JSON keys cannot redirect that context.
        if scoped_references is not None:ids=list(scoped_references);explicit=True
        allowed=[]
        for identity in dict.fromkeys(ids):
            if identity not in facts:raise ValueError('unselected_text_source_reference')
            allowed.append(facts[identity]['source_sha256'])
        hashes=set(allowed) if explicit else set(documents)
        matches=[digest for digest in hashes if proposed in joined[digest]]
        if not matches:raise ValueError('text_not_in_selected_reference_document:'+path)
        if scoped_references is not None and set(matches)!=hashes:raise ValueError('literal_not_in_every_selected_reference_document:'+path)
        item=dict(pointer=path,source_sha256=sorted(matches),references=list(dict.fromkeys(ids)),text_occurrence_verified=True,semantic_mapping_verified=False)
        if scoped_references is not None:item['all_declared_source_documents_matched']=True
        proof.append(item)
    return proof

def verify(function,envelope,documents):
    required={'function','data','as_of','facts','text_facts','bindings','assumptions'}
    if type(envelope) is not dict or set(envelope)!=required or envelope['function']!=function:
        raise ValueError('evidence_envelope_required')
    if type(envelope['data']) is not dict:raise ValueError('data_object_required')
    reject_proposed_authority(envelope['data'])
    if any(type(envelope[key]) is not list for key in ('facts','text_facts')):
        raise ValueError('source_facts_list_required')
    if type(envelope['assumptions']) is not list:raise ValueError('bindings_and_assumptions_required')
    if sum(len(envelope[key]) for key in ('facts','text_facts','assumptions'))>1000:
        raise ValueError('combined_facts_and_assumptions_limit')
    for category in ('facts','text_facts'):
        rows=envelope[category]
        if type(rows) is not list:raise ValueError('source_facts_list_required')
        for row in rows:
            if type(row) is not dict or type(row.get('source_sha256')) is not str or not re.fullmatch('[0-9a-f]{64}',row['source_sha256']):
                raise ValueError('source_fact_hash_required')
    analysis_date=envelope['data'].get('as_of')
    if analysis_date!=envelope['as_of']:raise ValueError('analysis_date_mismatch')
    if type(documents) is not dict or not 1<=len(documents)<=12:raise ValueError('selected_documents_required')
    source_characters=0
    for document in documents.values():
        metadata=[document]
        if type(document) is dict and type(document.get('segments')) is list:
            if not 1<=len(document['segments'])<=20000:raise ValueError('document_segments_required')
            metadata+=document['segments']
        for record in metadata:
            if type(record) is not dict:continue
            for flag in ('truncated','complete','extraction_complete'):
                if flag in record and type(record[flag]) is not bool:raise ValueError('source_extraction_flag_boolean_required')
            if 'notices' in record and type(record['notices']) is not list:raise ValueError('source_extraction_notices_list_required')
            if record.get('truncated') is True or record.get('complete') is False or record.get('extraction_complete') is False or record.get('notices'):
                raise ValueError('complete_source_extraction_required')
        if type(document) is dict and (document.get('truncated') is True or document.get('complete') is False or document.get('extraction_complete') is False):
            raise ValueError('complete_source_extraction_required')
        if type(document) is dict and type(document.get('segments')) is list:
            for segment in document['segments']:
                if type(segment) is dict and type(segment.get('source')) is str:source_characters+=len(segment['source'])
    if source_characters>32_000_000:raise ValueError('selected_source_size_limit')
    facts=prepare({'scope':{'as_of':envelope['as_of']},'facts':envelope['facts'],'text_facts':envelope['text_facts']},documents)
    # Prevent a proposed contract/request being invented while citing a real but
    # unrelated selected document. Semantic interpretation remains unverified.
    texts=selected_texts(function,envelope['data'])
    if type(texts) is not dict or len(texts)>1000:raise ValueError('selected_text_contract')
    text_bindings=verify_selected_texts(envelope['data'],texts,facts,documents)
    units=input_units(function,envelope['data'])
    if type(units) is not dict or len(units)>1000:raise ValueError('subject_unit_contract')
    assigned={};observed=[];hypothetical=[]
    if type(envelope['bindings']) is not list or type(envelope['assumptions']) is not list:
        raise ValueError('bindings_and_assumptions_required')
    for row in envelope['bindings']:
        if type(row) is not dict or set(row) not in ({'pointer','fact_id'},{'pointer','fact_id','conversion'}):raise ValueError('numeric_binding_fields')
        if 'conversion' in row and row['conversion'] is None:raise ValueError('explicit_unit_conversion_required')
        path=row['pointer'];identity=row['fact_id']
        if type(identity) is not str:raise ValueError('fact_id_required')
        if type(path) is not str or path in assigned or path not in units:raise ValueError('duplicate_or_unknown_binding')
        fact=facts.get(identity)
        expected=units[path];unit=unit_spec(expected)
        converted,conversion=bound_number(fact,unit,row.get('conversion'))
        selected_numeric_references=expected.get('source_references') if type(expected) is dict else None
        if selected_numeric_references is not None:
            if any(identity not in facts for identity in selected_numeric_references):
                raise ValueError('unselected_numeric_source_reference')
            allowed_hashes={facts[identity]['source_sha256'] for identity in selected_numeric_references}
            if fact['source_sha256'] not in allowed_hashes:
                raise ValueError('numeric_fact_not_in_selected_reference_document')
        if exact_number(pointer(envelope['data'],path))!=converted:raise ValueError('bound_value_mismatch')
        if type(expected) is dict and expected.get('effective_date') and fact['effective_date']!=expected['effective_date']:
            raise ValueError('bound_effective_date_mismatch')
        if type(expected) is dict and expected.get('not_after') and day(fact['effective_date'])>day(expected['not_after']):
            raise ValueError('bound_observation_after_valuation_date')
        if type(expected) is dict and expected.get('not_after') and day(fact['published_at'])>day(expected['not_after']):
            raise ValueError('bound_publication_after_information_cutoff')
        if type(expected) is dict and expected.get('effective_not_after') and day(fact['effective_date'])>day(expected['effective_not_after']):
            raise ValueError('bound_effective_date_after_selected_cutoff')
        if type(expected) is dict and expected.get('published_not_after') and day(fact['published_at'])>day(expected['published_not_after']):
            raise ValueError('bound_publication_after_selected_cutoff')
        assigned[path]=identity;observed.append(dict(row,unit=unit,quote_verified=True,semantic_mapping_verified=False,
          source_sha256=fact['source_sha256'],segment_id=fact['segment_id'],quote=fact['quote']))
        if selected_numeric_references is not None:
            observed[-1].update(expected_source_references=list(selected_numeric_references),source_document_alignment_verified=True)
        if conversion is not None:observed[-1]['conversion']=conversion
    for row in envelope['assumptions']:
        if type(row) is not dict or set(row)!={'pointer','value','unit','rationale'}:raise ValueError('explicit_assumption_fields')
        path=row['pointer']
        if type(path) is not str or path in assigned or path not in units:raise ValueError('duplicate_or_unknown_assumption')
        expected=units[path];unit=unit_spec(expected)
        if row['unit']!=unit or exact_number(row['value'])!=exact_number(pointer(envelope['data'],path)):
            raise ValueError('assumption_unit_or_value_mismatch')
        if type(row['rationale']) is not str or not 1<=len(row['rationale'].strip())<=1000:raise ValueError('assumption_rationale_required')
        assigned[path]='assumption';hypothetical.append(dict(row,verified=False))
    if set(assigned)!=set(units):raise ValueError('every_numeric_input_requires_evidence_or_explicit_assumption')
    for identity in cited_ids(envelope['data']):
        if identity not in facts:raise ValueError('unselected_source_reference:'+identity[:100])
    if not facts:raise ValueError('selected_evidence_required')
    return facts,{'as_of':envelope['as_of'],'bindings':observed,'assumptions':hypothetical,'text_bindings':text_bindings,
      'page_reference_mapping_verified':False,
      'hypothetical_inputs_present':bool(hypothetical),'normative_revision_verified':False,
      'source_authenticity_verified':False,'source_semantics_verified':False,
      'user_approval_established':False,'private':True,'external_network_used':False}

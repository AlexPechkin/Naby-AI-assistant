"""Local exact scientific source tokens; presence never certifies semantics."""
import re,csv,io
import hashlib
from datetime import date
from decimal import Decimal,InvalidOperation,Context,localcontext

EMPTY_SHA256=hashlib.sha256(b'').hexdigest()

def selected_blank_file(digest,document):
    """Only exact UTF8 byte identity and one complete whitespace-only segment.

    Documents are host-owned snapshots, never model arguments. This is a narrow
    empty-file identity check, not a source publication/authenticity certificate.
    """
    if type(document) is not dict:return False
    segments=document.get('segments')
    if type(segments) is not list or len(segments)!=1 or type(segments[0]) is not dict:return False
    body=segments[0].get('source')
    if type(body) is not str or body.strip():return False
    raw=body.encode('utf8')
    if hashlib.sha256(raw).hexdigest()!=digest:return False
    for key in ('bytes','raw_byte_count'):
        if key in document and (type(document[key]) is not int or document[key]!=len(raw)):return False
    for record in (document,segments[0]):
        notices=record.get('notices',[])
        if type(notices) is not list or notices:return False
        for flag,valid in (('complete',True),('extraction_complete',True),('truncated',False)):
            if flag in record and (type(record[flag]) is not bool or record[flag] is not valid):return False
    return True

def selected_empty_file(digest,document):
    return digest==EMPTY_SHA256 and selected_blank_file(digest,document) and document['segments'][0]['source']==''

def day(value):
    if type(value) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise ValueError('iso_date_required')
    try:return date.fromisoformat(value)
    except ValueError:raise ValueError('invalid_date') from None

def text(value,maximum):
    if type(value) is not str or not value.strip() or len(value)>maximum:raise ValueError('bounded_source_text_required')
    return value

def exact_number(value):
    """Canonical input value: decimal or e notation; no binary floats/grouping."""
    if type(value) not in (str,int) or len(str(value))>160:raise ValueError('exact_numeric_value_required')
    value=str(value)
    if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d{1,3})?',value):raise ValueError('exact_numeric_value_required')
    try:number=Decimal(value)
    except InvalidOperation:raise ValueError('invalid_numeric_value') from None
    if not number.is_finite() or len(number.as_tuple().digits)>40 or abs(number.as_tuple().exponent)>140 or (number and abs(number.adjusted())>100):
        raise ValueError('bounded_numeric_value_required')
    return number

def source_number(token,separator):
    """Explicit separator, e or ×10^ notation, SI digit grouping; no ellipses.

    Uncertainty suffixes, broken superscript extraction, ambiguous thousands commas,
    and shortened rounded fragments require a clearer source extraction.
    """
    if separator not in ('.',','):raise ValueError('decimal_separator_required')
    token=text(token,160)
    if any(c in token for c in ('…','(',')')) or '...' in token:raise ValueError('ambiguous_scientific_token')
    # Normalization concerns representation only. Original token/quote is retained.
    raw=token.replace('\u2212','-').replace('\u00a0',' ').replace('\u202f',' ')
    superscript=re.fullmatch(r'(.+?[x×]\s*10)([⁺⁻⁰¹²³⁴⁵⁶⁷⁸⁹]+)',raw)
    if superscript:
        raw=superscript.group(1)+'^'+superscript.group(2).translate(str.maketrans('⁺⁻⁰¹²³⁴⁵⁶⁷⁸⁹','+-0123456789'))
    sci=re.fullmatch(r'(.+?)(?:\s*[x×]\s*10\s*\^\s*([+-]?\d{1,3}))',raw)
    if sci:mantissa,exponent=sci.group(1),sci.group(2)
    else:
        parts=re.fullmatch(r'(.+?)(?: *[eE]([+-]?\d{1,3}))?',raw)
        if not parts:raise ValueError('scientific_source_token_required')
        mantissa,exponent=parts.group(1),parts.group(2)
    # Spaces are digit grouping only: integer 1-3 + groups3; fraction groups3
    # with a final group of 1..4, as used by the NIST constants table.
    sep=re.escape(separator)
    integer=r'(?:\d+|\d{1,3}(?: \d{3})+)'
    fraction=r'(?:\d+|\d{3}(?: \d{3})*(?: \d{1,4})?)'
    if not re.fullmatch(r'[+-]?(?:'+integer+r'(?:'+sep+fraction+r')?|'+sep+fraction+r')',mantissa):raise ValueError('scientific_source_token_required')
    canonical=mantissa.replace(' ','').replace(separator,'.')+('e'+exponent if exponent is not None else '')
    return exact_number(canonical)

def whole_token_present(quote,token):
    """Reject fragments of a grouped mantissa or separated ×10 exponent."""
    pattern=r'(?<![\w.,^+\-−])'+re.escape(token)+r'(?![\w.,^])'
    for match in re.finditer(pattern,quote):
        before,after=quote[:match.start()],quote[match.end():]
        # Single spaces are the supported digit grouping. Multiple spaces are
        # explicit column separators (e.g. NIST value / uncertainty columns).
        if re.search(r'\d[ \u00a0\u202f]$',before):continue
        if re.match(r'^[ \u00a0\u202f]\d',after) or re.match(r'^[ \u00a0\u202f]*[x×]\s*10',after):continue
        if re.match(r'^[ \u00a0\u202f]*[eE][+\-−]?\d',after):continue
        if re.match(r'^\(\d+\)\s*[x×]\s*10',after):continue
        if after and after[0] in '⁺⁻⁰¹²³⁴⁵⁶⁷⁸⁹':continue
        return True
    return False

def hex_integer(token):
    """Explicit bounded unsigned hex integer; preserve original spelling elsewhere."""
    if type(token) is not str or not re.fullmatch(r'0[xX][0-9a-fA-F]{1,32}',token):
        raise ValueError('bounded_hex_integer_token_required')
    return Decimal(int(token,16))

def whole_hex_token_present(quote,token):
    # Hex literals have an unambiguous prefix; adjacent map columns may contain
    # digits separated by one space. Reject signs, suffixes, floats and fragments.
    return re.search(r'(?<![\w.,^+\-−])'+re.escape(token)+r'(?![\w.,^])',quote) is not None

def csv_record_fields(body,delimiter,wanted):
    """Match whole actual CSV records, never arbitrary quoted-field substrings.

    Uses the standard reader with explicit delimiter, double quotes/doubled quote
    escaping and no float conversion. Does not change global CSV field limits.
    Encoding identity and row/header semantics are separate host/domain concerns.
    """
    if type(body) is not str or len(body)>2_000_000:raise ValueError('bounded_csv_source_required')
    if delimiter not in (',',';','\t','|'):raise ValueError('explicit_csv_delimiter_required')
    leading_bom=body.startswith('\ufeff');stream=io.StringIO(body[1:] if leading_bom else body,newline='')
    consumed=[]
    class Lines:
        def __iter__(self):return self
        def __next__(self):
            line=next(stream);consumed.append(line);return line
    found={};records=0;cells=0
    try:
        for values in csv.reader(Lines(),delimiter=delimiter,quotechar='"',doublequote=True,escapechar=None,strict=True):
            records+=1;cells+=len(values)
            if records>10000 or len(values)>256 or cells>200000:raise ValueError('bounded_csv_structure_required')
            raw=''.join(consumed);consumed.clear()
            unended=raw[:-2] if raw.endswith('\r\n') else raw[:-1] if raw.endswith(('\r','\n')) else raw
            candidates=(raw,unended)
            if records==1 and leading_bom:candidates+=('\ufeff'+raw,'\ufeff'+unended)
            for record in candidates:
                if record in wanted:found[record]=tuple(values)
    except csv.Error:raise ValueError('strict_csv_record_required') from None
    return found

def complete_csv_segment(document,segment,delimiter):
    if len(document['segments'])!=1:raise ValueError('single_complete_csv_source_segment_required')
    if document.get('source_format')!='csv' or document.get('csv_delimiter')!=delimiter:raise ValueError('host_selected_csv_dialect_required')
    for record in (document,segment):
        if type(record.get('notices')) is not list or record['notices']:raise ValueError('complete_csv_extraction_required')
        for flag,valid in (('complete',True),('extraction_complete',True),('truncated',False)):
            if type(record.get(flag)) is not bool or record[flag] is not valid:raise ValueError('complete_csv_extraction_required')

def prepare(config,documents):
    if type(documents) is not dict or not 1<=len(documents)<=12:raise ValueError('selected_documents_required')
    for digest,document in documents.items():
        if type(digest) is not str or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('selected_document_hash_required')
        if type(document) is not dict or document.get('notices'):raise ValueError('complete_extraction_required')
        segments=document.get('segments')
        if type(segments) is not list or not 1<=len(segments)<=20000:raise ValueError('document_segments_required')
        ids=set()
        for segment in segments:
            if type(segment) is not dict or type(segment.get('source')) is not str:raise ValueError('invalid_source_segment')
            identity=text(segment.get('id'),200)
            if identity in ids:raise ValueError('duplicate_source_segment')
            ids.add(identity)
    cutoff=day(config['scope']['as_of']);facts={};csv_cache={}
    numeric=config.get('facts',[]);texts=config.get('text_facts',[])
    if type(numeric) is not list or type(texts) is not list or len(numeric)+len(texts)>1000:raise ValueError('facts_limit')
    base={'id','source_sha256','segment_id','quote','published_at','effective_date'}
    for rows,is_numeric in ((numeric,True),(texts,False)):
        fields=base|({'token','decimal_separator','value','unit'} if is_numeric else set())
        for row in rows:
            if type(row) is not dict or (set(row)!=fields and not (is_numeric and set(row) in (fields|{'numeric_format'},fields|{'numeric_format','csv_delimiter','csv_field_index'}))):
                raise ValueError('source_fact_required' if is_numeric else 'text_fact_fields_required')
            hex_format=is_numeric and row.get('numeric_format')=='hex_integer'
            csv_format=is_numeric and row.get('numeric_format')=='csv_field'
            if is_numeric and 'numeric_format' in row and not (hex_format or csv_format):raise ValueError('explicit_numeric_format_required')
            if hex_format and (set(row)!=fields|{'numeric_format'} or row['decimal_separator']!='.'):
                raise ValueError('explicit_hex_integer_format_required')
            if csv_format and (set(row)!=fields|{'numeric_format','csv_delimiter','csv_field_index'} or row['csv_delimiter'] not in (',',';','\t','|') or type(row['csv_field_index']) is not int or not 0<=row['csv_field_index']<256):raise ValueError('explicit_csv_field_format_required')
            identity=text(row['id'],80)
            if identity in facts:raise ValueError('duplicate_fact')
            document=documents.get(row['source_sha256'])
            if document is None:raise ValueError('fact_document_not_selected')
            matches=[s for s in document['segments'] if s['id']==row['segment_id']]
            blank_source=(not is_numeric and type(row['quote']) is str and len(row['quote'])<=2000 and not row['quote'].strip() and selected_blank_file(row['source_sha256'],document) and len(matches)==1 and row['quote'] in ('',matches[0]['source']))
            empty_source=blank_source and matches[0]['source']==''
            quote=row['quote'] if blank_source else text(row['quote'],2000)
            if len(matches)!=1 or quote not in matches[0]['source']:raise ValueError('quote_not_in_selected_segment')
            if day(row['published_at'])>cutoff or day(row['effective_date'])>cutoff:raise ValueError('future_source_or_effective_date')
            result=dict(row,quote_verified=not blank_source,semantic_mapping_verified=False,source_authenticity_verified=False)
            if empty_source:result['empty_selected_file']=True
            elif blank_source:result['blank_selected_file']=True
            if is_numeric:
                token=text(row['token'],160)
                if csv_format:
                    complete_csv_segment(document,matches[0],row['csv_delimiter'])
                    key=(row['source_sha256'],row['segment_id'],row['csv_delimiter'])
                    if key not in csv_cache:
                        wanted={r['quote'] for r in numeric if type(r) is dict and r.get('numeric_format')=='csv_field' and r.get('source_sha256')==key[0] and r.get('segment_id')==key[1] and r.get('csv_delimiter')==key[2] and type(r.get('quote')) is str and len(r['quote'])<=2000}
                        csv_cache[key]=csv_record_fields(matches[0]['source'],row['csv_delimiter'],wanted)
                    values=csv_cache[key].get(quote)
                    if values is None or row['csv_field_index']>=len(values) or values[row['csv_field_index']]!=token:raise ValueError('numeric_token_not_in_complete_csv_field')
                elif not (whole_hex_token_present(quote,token) if hex_format else whole_token_present(quote,token)):
                    raise ValueError('numeric_token_not_in_selected_quote')
                observed=hex_integer(token) if hex_format else source_number(token,row['decimal_separator'])
                proposed=exact_number(row['value'])
                if proposed!=observed:raise ValueError('fact_value_differs_from_source_token')
                text(row['unit'],100);result['value']=str(proposed)
            facts[identity]=result
    return facts

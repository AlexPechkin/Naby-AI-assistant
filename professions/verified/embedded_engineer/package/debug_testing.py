"""Bounded offline debug/test evidence review. Never opens a device or runs tools."""
from copy import deepcopy
from datetime import date,datetime
from decimal import Decimal,Context,localcontext,InvalidOperation
from fractions import Fraction as F
import json,re
from .privacy import reject_known_secret_material

FUNCTIONS=('hw_debug','fw_testing')
NUMBER=re.compile(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$')
TIME={'s':F(1),'ms':F(1,1000),'us':F(1,1000000),'ns':F(1,1000000000)}
CONTEXT=('firmware_version','board_revision','build_id','source_sha256','configuration_sha256','platform','toolchain','toolchain_version')
LAYERS=('power_reset_clock','wiring_levels','interface','firmware')
STATUSES=('not_run','passed','failed','blocked','skipped','error','build_only','unknown')
TWISTER={'passed':'passed','failed':'failed','blocked':'blocked','skipped':'skipped','error':'error','not run':'not_run','filtered':'skipped','started':'unknown',None:'unknown'}
def fail(p,c):raise ValueError(p+':'+c)
def obj(v,p,required=(),optional=()):
    if type(v)is not dict or set(required)-set(v)or set(v)-set(required)-set(optional):fail(p,'object_fields')
    return v
def text(v,p,maximum=6000,empty=False):
    if type(v)is not str or len(v)>maximum or not empty and not v.strip()or any(0xD800<=ord(c)<=0xDFFF or ord(c)<32 and c not in '\t\r\n'for c in v):fail(p,'text')
    return v
def rows(v,p,maximum,minimum=0):
    if type(v)is not list or not minimum<=len(v)<=maximum:fail(p,'bounded_array')
    return v
def choice(v,p,values):
    if type(v)is not str or v not in values:fail(p,'choice')
    return v
def iso(v,p,cutoff=None):
    text(v,p,10)
    try:d=date.fromisoformat(v)
    except ValueError:fail(p,'ISO_date')
    if d.isoformat()!=v or cutoff and v>cutoff:fail(p,'date_after_cutoff_or_not_ISO')
    return v
def number(v,p):
    if type(v)is not str or len(v)>160 or not NUMBER.fullmatch(v):fail(p,'bounded_decimal_string')
    try:d=Decimal(v)
    except InvalidOperation:fail(p,'bounded_decimal_string')
    if not d.is_finite()or len(d.as_tuple().digits)>40 or abs(d.as_tuple().exponent)>140 or d and abs(d.adjusted())>100:fail(p,'bounded_decimal_string')
    return F(d)
def display(v):
    if isinstance(v,F):
        with localcontext(Context(prec=180)):return str(Decimal(v.numerator)/Decimal(v.denominator))
    if type(v)is dict:return {k:display(x)for k,x in v.items()}
    if type(v)is list:return [display(x)for x in v]
    return v
def unique(items,p):
    ids=[x['id']for x in items]
    if len(set(ids))!=len(ids):fail(p,'duplicate_id')
def bounded(v,p='data',depth=0,counter=None):
    if counter is None:counter=[0]
    if depth>24:fail(p,'depth')
    if type(v)is dict:
        for k,x in v.items():
            if type(k)is not str:fail(p,'string_keys')
            if k.endswith(('_verified','_approved','_confirmed','_signed'))or k in ('confirmed_by_user','trusted','registered','authorized','clearance'):fail(p,'authority_not_input')
            bounded(x,p+'/'+k,depth+1,counter)
    elif type(v)is list:
        if len(v)>144:fail(p,'array_bound')
        for i,x in enumerate(v):bounded(x,p+'/'+str(i),depth+1,counter)
    else:
        counter[0]+=1
        if counter[0]>900:fail(p,'scalar_budget')
        if type(v)is str:text(v,p,120000,True)
        elif v is not None and type(v)is not bool:fail(p,'numeric_inputs_must_be_Q_decimal_strings')
def pointer(p,k):return p+'/'+str(k).replace('~','~0').replace('/','~1')

class Read:
    def __init__(self,data):
        self.cutoff=iso(data.get('as_of'),'/as_of');self.units={};self.literals={};self.gaps=[]
        if data.get('jurisdiction')!='RU':fail('/jurisdiction','explicit_RU')
    def gap(self,kind,**kw):self.gaps.append(dict(kind=kind,**kw))
    def literal(self,v,p,ref,empty=False):
        text(v,p,120000,empty);text(ref,p+'/source_reference',300)
        if v.strip():self.literals[p]=dict(text=v,source_references=[ref])
        return v
    def evidence(self,v,p):
        obj(v,p,('source_reference','excerpt'));text(v['source_reference'],p+'/source_reference',300);self.literal(v['excerpt'],p+'/excerpt',v['source_reference']);return deepcopy(v)
    def q(self,v,p,units,lo=None,hi=None,integer=False,ceiling=None):
        obj(v,p,('value','unit','source_reference'),('observed_date',));text(v['source_reference'],p+'/source_reference',300)
        if v['unit']not in units or type(v['unit'])is not str:fail(p,'unit')
        n=number(v['value'],p+'/value')
        if lo is not None and n<lo or hi is not None and n>hi or integer and n.denominator!=1:fail(p,'numeric_range_or_integer')
        spec=dict(unit=v['unit'],effective_not_after=ceiling or self.cutoff,published_not_after=self.cutoff,source_references=[v['source_reference']])
        if 'observed_date'in v:
            spec['effective_date']=iso(v['observed_date'],p+'/observed_date',ceiling or self.cutoff)
            self.literal(v['observed_date'],p+'/observed_date',v['source_reference'])
        self.units[p+'/value']=spec;return n
    def time(self,v,p,ceiling=None):return self.q(v,p,TIME,0,ceiling=ceiling)*TIME[v['unit']]
    def context(self,v,p):
        if v is None:return None
        obj(v,p,CONTEXT+('source_reference','excerpt'))
        self.evidence({k:v[k]for k in ('source_reference','excerpt')},p)
        for k in CONTEXT:
            self.literal(v[k],p+'/'+k,v['source_reference'])
            if k.endswith('sha256')and not re.fullmatch('[0-9a-fA-F]{64}',v[k]):fail(p+'/'+k,'sha256')
        return deepcopy(v)
    def basis(self,v,p):
        obj(v,p,('document_identity','edition','publication_date','selection_date','effective_from','effective_to','source_reference','excerpt'))
        for k in ('document_identity','edition'):self.literal(v[k],p+'/'+k,v['source_reference'])
        self.evidence({k:v[k]for k in ('source_reference','excerpt')},p)
        pub=iso(v['publication_date'],p+'/publication_date',self.cutoff);sel=iso(v['selection_date'],p+'/selection_date',self.cutoff)
        start=iso(v['effective_from'],p+'/effective_from')if v['effective_from']is not None else None;end=iso(v['effective_to'],p+'/effective_to')if v['effective_to']is not None else None
        if start and end and start>end:fail(p,'effective_date_order')
        state='unknown_selected_window'if start is None else 'within_supplied_window'if start<=sel and(end is None or sel<=end)else 'outside_supplied_window'
        if state!='within_supplied_window'or end is None:self.gap('selected_method_window_unresolved',path=p)
        if pub>sel:self.gap('method_published_after_selection_date',path=p)
        return dict(deepcopy(v),selected_window_status=state,applicability_established=False)

def clock_basis(v,p,r):
    if v is None:return None
    obj(v,p,('origin','clock_id','source_reference','excerpt'));choice(v['origin'],p+'/origin',('relative_capture','unix_epoch'));r.literal(v['clock_id'],p+'/clock_id',v['source_reference']);r.evidence({k:v[k]for k in ('source_reference','excerpt')},p)
    return dict(deepcopy(v),clock_alignment_established=False)
def telemetry(v,p,r,clock=None):
    if v is None:return None
    obj(v,p,('sequence_model','records','source_reference'),('serial_bits','capture_date','max_gap'))
    model=choice(v['sequence_model'],p+'/sequence_model',('monotonic','modulo_serial'));ceiling=iso(v['capture_date'],p+'/capture_date',r.cutoff)if 'capture_date'in v else r.cutoff
    if 'capture_date'in v:r.literal(v['capture_date'],p+'/capture_date',v['source_reference'])
    if 'capture_date'not in v:r.gap('capture_date_not_supplied',path=p)
    if model=='modulo_serial':bits=int(r.q(v.get('serial_bits'),p+'/serial_bits',('bit',),1,64,True));modulus=2**bits
    else:
        if 'serial_bits'in v:fail(p,'unused_serial_bits')
        modulus=None
    threshold=r.time(v['max_gap'],p+'/max_gap')if 'max_gap'in v else None
    parsed=[];seen={};high=None;lasttime=None;timing=[];unknown=False
    for i,a in enumerate(rows(v['records'],p+'/records',64,1)):
        q=pointer(p+'/records',i);obj(a,q,('id','sequence','source_reference'),('timestamp','payload'))
        text(a['id'],q+'/id',200);s=int(r.q(a['sequence'],q+'/sequence',('count',),0,modulus-1 if modulus else 2**64-1,True,ceiling))
        if 'payload'in a:r.literal(a['payload'],q+'/payload',a['source_reference'],True)
        else:text(a['source_reference'],q+'/source_reference',300)
        status='first';position=s
        if high is not None:
            if modulus:
                delta=(s-high%modulus)%modulus
                if 2*delta==modulus:position=None;status='half_range_ambiguous';unknown=True
                elif 2*delta<modulus:position=high+delta;status='forward'if delta else 'duplicate'
                else:position=high-(modulus-delta);status='late_or_large_forward_ambiguous'
            else:status='forward'if s>high else 'duplicate'if s==high else 'late_or_duplicate'
        duplicate=[]
        if position is not None:
            duplicate=seen.get(position,[])[:]
            if duplicate:status='duplicate_position'
            seen.setdefault(position,[]).append(a['id']);high=max(high,position)if high is not None else position
        if status in ('half_range_ambiguous','late_or_large_forward_ambiguous'):r.gap('serial_order_model_conditional',record_id=a['id'],status=status)
        timestamp=r.time(a['timestamp'],q+'/timestamp',ceiling)if 'timestamp'in a else None;elapsed=None
        if clock is not None and timestamp is not None and lasttime is not None:
            elapsed=timestamp-lasttime;timing.append(elapsed)
            if elapsed<0:r.gap('timestamp_regression',record_id=a['id'])
        if timestamp is not None:lasttime=timestamp
        else:lasttime=None;r.gap('record_timestamp_not_supplied',record_id=a['id'])
        parsed.append(dict(provided=deepcopy(a),unwrapped_position=position,sequence_status=status,duplicate_of_ids=duplicate,timestamp_s=timestamp,interarrival_s=elapsed,above_selected_gap=None if elapsed is None or threshold is None or elapsed<0 else elapsed>threshold))
    if clock is None and any(x['timestamp_s']is not None for x in parsed):r.gap('common_timestamp_basis_not_selected',path=p)
    unique([x['provided']for x in parsed],p+'/records');ordered=sorted(seen);gaps=[]
    for a,b in zip(ordered,ordered[1:]):
        if b-a>1:gaps.append(dict(after_position=a,before_position=b,missing_candidate_count=b-a-1))
    return dict(sequence_model=model,serial_modulus=modulus,time_basis=deepcopy(clock),records=parsed,missing_candidates=gaps,missing_candidate_count=sum(g['missing_candidate_count']for g in gaps),selected_gap_s=threshold,max_nonnegative_interarrival_s=max((x for x in timing if x>=0),default=None),mapping_complete_under_selected_model=not unknown,loss_established=False,serial_scope='conditional_half_range_unwrapping_not_unseen_wrap_or_loss_proof')

def uart(v,p,r):
    if v is None:return None
    obj(v,p,('clock_hz','oversampling','divider','requested_baud','tolerance','model_source_reference','model_excerpt'))
    r.literal(v['model_excerpt'],p+'/model_excerpt',v['model_source_reference'])
    clock=r.q(v['clock_hz'],p+'/clock_hz',('Hz',),F('1e-100'));over=r.q(v['oversampling'],p+'/oversampling',('ratio',),F('1e-100'));div=r.q(v['divider'],p+'/divider',('ratio',),F('1e-100'));wanted=r.q(v['requested_baud'],p+'/requested_baud',('bit/s',),F('1e-100'));tol=r.q(v['tolerance'],p+'/tolerance',('ratio',),0)
    actual=clock/(over*div);error=(actual-wanted)/wanted
    return dict(provided=deepcopy(v),actual_baud=actual,unit='bit/s',signed_relative_error=error,absolute_relative_error=abs(error),within_selected_tolerance=abs(error)<=tol,formula='clock_hz/(oversampling*divider)',hardware_clock_measured_here=False,register_semantics_established=False)

def crc16(data):
    crc=0xFFFF
    for byte in data:
        crc^=byte
        for _ in range(8):crc=(crc>>1)^(0xA001 if crc&1 else 0)
    return crc
def hexbytes(value,p,maximum):
    text(value,p,maximum*3,True)
    compact=re.sub(r'[ \t\r\n]','',value)
    return bytes.fromhex(compact)if len(compact)%2==0 and re.fullmatch('[0-9a-fA-F]*',compact)and len(compact)<=2*maximum else None
def frame(a,p,r):
    obj(a,p,('id','direction','hex','source_reference'),('timestamp',));text(a['id'],p+'/id',200);direction=choice(a['direction'],p+'/direction',('request','response','unknown'));r.literal(a['hex'],p+'/hex',a['source_reference'],True)
    raw=hexbytes(a['hex'],p+'/hex',256);ts=r.time(a['timestamp'],p+'/timestamp')if 'timestamp'in a else None
    result=dict(provided=deepcopy(a),timestamp_s=ts,byte_count=None if raw is None else len(raw),address=None,function=None,crc_matches=None,computed_crc_hex=None,supported_shape=None,shape_status='invalid_hex',shape_issues=[],decoded=None,protocol_conformance_established=False)
    if raw is None:return result
    if len(raw)<4:result['shape_status']='too_short';return result
    address,fc=raw[:2];result.update(address=address,function=fc,crc_matches=crc16(raw[:-2])==int.from_bytes(raw[-2:],'little'),computed_crc_hex=crc16(raw[:-2]).to_bytes(2,'little').hex().upper())
    issues=result['shape_issues'];decoded={};base=fc&0x7F
    if address>247 or address==0 and direction=='response':issues.append('invalid_serial_address')
    if base==0:issues.append('invalid_function_zero');result.update(shape_status='invalid_supported_shape',supported_shape=False);return result
    if direction=='unknown':result.update(shape_status='direction_not_selected',supported_shape=None);return result
    if base not in (3,4,6,16):result.update(shape_status='unsupported_function',supported_shape=None);return result
    u16=lambda i:int.from_bytes(raw[i:i+2],'big')
    if fc&0x80:
        if direction!='response'or len(raw)!=5:issues.append('exception_shape')
        elif raw[2]not in (1,2,3,4):issues.append('exception_outside_selected_subset')
        else:decoded=dict(kind='exception',exception_code=raw[2],base_function=base)
    elif base in (3,4)and direction=='response':
        if len(raw)<5 or not 2<=raw[2]<=250 or raw[2]%2 or len(raw)!=5+raw[2]:issues.append('read_response_byte_count')
        else:decoded=dict(kind='read_response',registers=[u16(i)for i in range(3,len(raw)-2,2)],register_count=raw[2]//2)
    elif base==16 and direction=='request':
        if len(raw)<9:issues.append('write_multiple_request_length')
        else:
            start,qty=u16(2),u16(4)
            if not 1<=qty<=123 or start+qty>65536 or raw[6]!=2*qty or len(raw)!=9+2*qty:issues.append('write_multiple_quantity_or_byte_count')
            else:decoded=dict(kind='write_multiple_request',start_address=start,quantity=qty,registers=[u16(i)for i in range(7,len(raw)-2,2)])
    else:
        if len(raw)!=8:issues.append('fixed_length_PDU')
        elif base==6:decoded=dict(kind='write_single',register_address=u16(2),register_value=u16(4))
        else:
            start,qty=u16(2),u16(4);limit=125 if base in (3,4)else 123
            if not 1<=qty<=limit or start+qty>65536:issues.append('register_address_quantity')
            else:decoded=dict(kind='read_request'if base in (3,4)else 'write_multiple_response',start_address=start,quantity=qty)
    if address==0 and (direction!='request'or fc not in (6,16)):issues.append('broadcast_not_supported_for_this_role')
    result.update(supported_shape=not issues,shape_status='supported_shape'if not issues else 'invalid_supported_shape',decoded=decoded or None)
    return result
def modbus(v,p,r,clock=None):
    if v is None:return None
    obj(v,p,('frames',),('transactions',));frames=[frame(a,pointer(p+'/frames',i),r)for i,a in enumerate(rows(v['frames'],p+'/frames',12,1))];unique([f['provided']for f in frames],p+'/frames');byid={f['provided']['id']:f for f in frames};transactions=[];used=set()
    for i,a in enumerate(rows(v.get('transactions',[]),p+'/transactions',6)):
        q=pointer(p+'/transactions',i);obj(a,q,('id','request_id','response_id'),('max_latency',));text(a['id'],q+'/id',200)
        for k in ('request_id','response_id'):
            if a[k]is not None and(a[k]not in byid or a[k]in used):fail(q,'unknown_or_reused_frame')
            if a[k]is not None:used.add(a[k])
        if a['request_id']is None:fail(q,'request_required')
        req=byid[a['request_id']];resp=byid[a['response_id']]if a['response_id']is not None else None;issues=[];matched=None;latency=None;within=None
        maximum=r.time(a['max_latency'],q+'/max_latency')if 'max_latency'in a else None
        if req['provided']['direction']!='request'or resp and resp['provided']['direction']!='response':issues.append('transaction_direction_mismatch')
        elif not req['crc_matches']or not req['supported_shape']or resp and(not resp['crc_matches']or not resp['supported_shape']):issues.append('unusable_crc_or_supported_shape')
        elif req['address']==0:
            matched=resp is None
            if resp is not None:issues.append('broadcast_response_unexpected')
        elif resp is None:issues.append('response_not_supplied')
        else:
            matched=req['address']==resp['address']and req['function']==(resp['function']&0x7F)
            if not matched:issues.append('response_address_or_function_mismatch')
            elif resp['function']&0x80:issues.append('exception_response_not_normal_success')
            elif req['function']in (3,4):matched=req['decoded']['quantity']==resp['decoded']['register_count']
            elif req['function']==6:matched=req['decoded']==resp['decoded']
            else:matched=all(req['decoded'][k]==resp['decoded'][k]for k in ('start_address','quantity'))
            if not matched:issues.append('response_data_does_not_match_request')
        if resp is not None and req['timestamp_s']is not None and resp['timestamp_s']is not None and clock is None:r.gap('common_timestamp_basis_not_selected',path=q)
        if clock is not None and resp is not None and req['timestamp_s']is not None and resp['timestamp_s']is not None:
            latency=resp['timestamp_s']-req['timestamp_s']
            if latency<0:issues.append('response_timestamp_regression')
            elif maximum is not None:within=latency<=maximum
        transactions.append(dict(provided=deepcopy(a),request_response_fields_match=matched,response_latency_s=latency,within_selected_latency=within,issues=issues,device_success_established=False))
    unique([t['provided']for t in transactions],p+'/transactions')
    return dict(frames=frames,transactions=transactions,time_basis=deepcopy(clock),crc_scope='checksum_only_not_protocol_or_physical_conformance',PDU_scope='03_04_06_16_selected_exception_subset',wire_timing_checked=False)

def can_review(v,p,r):
    if v is None:return None
    obj(v,p,('frames',),('decoded_exports',));frames=[];raws={}
    for i,a in enumerate(rows(v['frames'],p+'/frames',12,1)):
        q=pointer(p+'/frames',i);obj(a,q,('id','frame_type','hex','source_reference'),('identifier_format','arbitration_id','length_kind','length','timestamp'));text(a['id'],q+'/id',200);kind=choice(a['frame_type'],q+'/frame_type',('classic_data','classic_remote','fd_data','error_record'));r.literal(a['hex'],q+'/hex',a['source_reference'],True);raw=hexbytes(a['hex'],q+'/hex',64);issues=[];arb=None;length=None
        if kind!='error_record':
            fmt=choice(a.get('identifier_format'),q+'/identifier_format',('standard','extended'));arb=r.q(a.get('arbitration_id'),q+'/arbitration_id',('can_id',),0,2**(11 if fmt=='standard'else 29)-1,True)
            interpretation=choice(a.get('length_kind'),q+'/length_kind',('dlc_code','payload_bytes'));n=int(r.q(a.get('length'),q+'/length',('count',),0,15 if interpretation=='dlc_code'else 64,True))
            length=([0,1,2,3,4,5,6,7,8,12,16,20,24,32,48,64][n]if kind=='fd_data'else n)if interpretation=='dlc_code'else n
            if kind!='fd_data'and length>8:issues.append('classic_length_above_eight')
            if kind=='fd_data'and length not in (0,1,2,3,4,5,6,7,8,12,16,20,24,32,48,64):issues.append('FD_payload_length_not_encodable')
            if raw is None or len(raw)!=(0 if kind=='classic_remote'else length):issues.append('payload_length_or_hex_mismatch')
        elif any(k in a for k in ('identifier_format','arbitration_id','length_kind','length')):fail(q,'error_record_not_data_frame')
        ts=r.time(a['timestamp'],q+'/timestamp')if 'timestamp'in a else None
        frames.append(dict(provided=deepcopy(a),arbitration_id=arb,expected_payload_bytes=length,actual_payload_bytes=None if raw is None else len(raw),timestamp_s=ts,structural_fields_match=None if kind=='error_record'else not issues,issues=issues,wire_CRC_available=False,wire_CRC_matches=None));raws[a['id']]=raw
    unique([x['provided']for x in frames],p+'/frames');decoded=[]
    for i,a in enumerate(rows(v.get('decoded_exports',[]),p+'/decoded_exports',6)):
        q=pointer(p+'/decoded_exports',i);obj(a,q,('id','frame_id','tool','tool_version','database_sha256','payload_hex','signals','source_reference','excerpt'))
        for k in ('id','frame_id','tool','tool_version','database_sha256'):r.literal(a[k],q+'/'+k,a['source_reference'])
        if a['frame_id']not in raws:fail(q,'unknown_decoded_frame')
        if not re.fullmatch('[0-9a-fA-F]{64}',a['database_sha256']):fail(q,'database_sha256')
        r.literal(a['payload_hex'],q+'/payload_hex',a['source_reference']);r.evidence({k:a[k]for k in ('source_reference','excerpt')},q)
        for j,s in enumerate(rows(a['signals'],q+'/signals',4)):
            z=pointer(q+'/signals',j);obj(s,z,('name','quantity'));r.literal(s['name'],z+'/name',a['source_reference']);r.q(s['quantity'],z+'/quantity',(s['quantity'].get('unit'),))
        supplied=hexbytes(a['payload_hex'],q+'/payload_hex',64);match=supplied is not None and raws[a['frame_id']]is not None and supplied==raws[a['frame_id']]
        if not match:r.gap('external_decode_payload_mismatch',id=a['id'])
        decoded.append(dict(provided=deepcopy(a),payload_matches_selected_frame=match,decode_recomputed=False,database_semantics_established=False))
    unique([x['provided']for x in decoded],p+'/decoded_exports')
    return dict(frames=frames,decoded_exports=decoded,scope='prepared_CAN_metadata_not_wire_or_DBC_conformance')

def timing_windows(values,p,r,clock=None):
    output=[]
    for i,a in enumerate(rows(values,p,8)):
        q=pointer(p,i);obj(a,q,('id','kind','start','end','source_reference'),('minimum','maximum','limit_source_reference','limit_excerpt'));text(a['id'],q+'/id',200);choice(a['kind'],q+'/kind',('logic_pulse','setup','hold','rtu_intercharacter_silence','rtu_interframe_silence'))
        start=r.time(a['start'],q+'/start');end=r.time(a['end'],q+'/end');limits={}
        if 'minimum'in a or 'maximum'in a:
            r.literal(a.get('limit_excerpt'),q+'/limit_excerpt',a.get('limit_source_reference'))
            for k in ('minimum','maximum'):
                if k in a:limits[k]=r.time(a[k],q+'/'+k)
            if 'minimum'in limits and 'maximum'in limits and limits['minimum']>limits['maximum']:fail(q,'reversed_limits')
        elif 'limit_excerpt'in a or 'limit_source_reference'in a:fail(q,'unused_limit_basis')
        rawdifference=end-start;duration=rawdifference if clock is not None else None;valid=None if duration is None or duration<0 or not limits else all(duration>=n if k=='minimum'else duration<=n for k,n in limits.items())
        if clock is None:r.gap('common_timestamp_basis_not_selected',id=a['id'])
        if duration is not None and duration<0:r.gap('timing_window_regression',id=a['id'])
        if not limits:r.gap('timing_limits_not_selected',id=a['id'])
        output.append(dict(provided=deepcopy(a),raw_difference_s=rawdifference,duration_s=duration,time_basis=deepcopy(clock),selected_limits_s=limits,within_selected_limits=valid,hardware_timing_measured_here=False))
    unique([x['provided']for x in output],p);return output

def debug(data,r):
    obj(data,'data',('as_of','jurisdiction','mode'),('context','time_basis','symptoms','connection','telemetry','uart','modbus','can','timing_windows','observations','hypotheses','next_checks'))
    mode=choice(data['mode'],'/mode',('questions','draft','review'));context=r.context(data.get('context'),'/context');clock=clock_basis(data.get('time_basis'),'/time_basis',r)
    for k in ('symptoms','connection'):
        if k in data:text(data[k],'/'+k)
    if mode=='questions'and any(data.get(k)for k in ('telemetry','uart','modbus','can','timing_windows','observations')):fail('/mode','questions_contains_measurement_branches')
    observations=[]
    for i,a in enumerate(rows(data.get('observations',[]),'/observations',12)):
        p=pointer('/observations',i);obj(a,p,('id','layer','state','description'),('evidence',));text(a['id'],p+'/id',200);choice(a['layer'],p+'/layer',LAYERS);choice(a['state'],p+'/state',('provided','missing','unknown'));text(a['description'],p+'/description')
        evidence=r.evidence(a['evidence'],p+'/evidence')if 'evidence'in a else None
        if a['state']!='provided'or evidence is None:r.gap('debug_observation_evidence_unresolved',id=a['id'])
        observations.append(dict(deepcopy(a),evidence=evidence,description_semantics_established=False))
    unique(observations,'/observations');hypotheses=[];steps=[]
    for i,a in enumerate(rows(data.get('hypotheses',[]),'/hypotheses',8)):
        p=pointer('/hypotheses',i);obj(a,p,('id','explanation','evidence_refs'));text(a['id'],p+'/id',200);text(a['explanation'],p+'/explanation')
        for ref in rows(a['evidence_refs'],p+'/evidence_refs',12):text(ref,p+'/evidence_refs',300)
        hypotheses.append(dict(deepcopy(a),status='hypothesis_not_established_cause'))
    unique(hypotheses,'/hypotheses')
    for i,a in enumerate(rows(data.get('next_checks',[]),'/next_checks',12)):
        p=pointer('/next_checks',i);obj(a,p,('id','layer','action','expected_observation'));text(a['id'],p+'/id',200);choice(a['layer'],p+'/layer',LAYERS)
        for k in ('action','expected_observation'):text(a[k],p+'/'+k)
        steps.append(dict(deepcopy(a),status='proposed_not_executed'))
    unique(steps,'/next_checks');steps.sort(key=lambda x:LAYERS.index(x['layer']))
    if context is None:r.gap('board_firmware_context_not_supplied')
    return dict(mode=mode,context=context,time_basis=clock,symptoms=data.get('symptoms'),connection=data.get('connection'),telemetry=telemetry(data.get('telemetry'),'/telemetry',r,clock),uart=uart(data.get('uart'),'/uart',r),modbus=modbus(data.get('modbus'),'/modbus',r,clock),can=can_review(data.get('can'),'/can',r),timing_windows=timing_windows(data.get('timing_windows',[]),'/timing_windows',r,clock),observations=observations,hypotheses=hypotheses,next_checks=steps,questions=['supply_symptoms_board_firmware_connection','select_actual_logs_protocol_direction_units','supply_clock_divider_model_if_UART_requested','separate_physical_observations_from_hypotheses']if mode=='questions'else [],root_cause_established=False)

def context_differences(actual,expected):
    if actual is None or expected is None:return ['context_not_supplied']
    return [k for k in CONTEXT if actual[k]!=expected[k]]
def revisions(v,ids,p):
    if type(v)is not dict or set(v)!=set(ids):fail(p,'versioned_requirement_links')
    for k,x in v.items():text(x,p+'/'+k,300)
    return v
def report_json(raw):
    def pairs(values):
        d={}
        for k,v in values:
            if k in d:raise ValueError('duplicate_JSON_key')
            d[k]=v
        return d
    def numeric(s):return number(s,'/report_numeric')
    def constant(s):raise ValueError('nonfinite_JSON_number')
    try:v=json.loads(raw,object_pairs_hook=pairs,parse_int=numeric,parse_float=numeric,parse_constant=constant)
    except (ValueError,RecursionError):return None,'invalid_or_outside_bounded_JSON_profile'
    def limit(a,depth=0,counter=None):
        if counter is None:counter=[0]
        if depth>16:raise ValueError('report_depth')
        if type(a)is dict:
            if len(a)>64:raise ValueError('report_fields')
            for x in a.values():limit(x,depth+1,counter)
        elif type(a)is list:
            if len(a)>144:raise ValueError('report_array')
            for x in a:limit(x,depth+1,counter)
        else:
            counter[0]+=1
            if counter[0]>1600:raise ValueError('report_scalar_budget')
    try:limit(v)
    except ValueError:return None,'outside_bounded_JSON_profile'
    return v,None
def prepared_reports(values,p,r):
    review=[];candidates=[]
    for i,a in enumerate(rows(values,p,4)):
        q=pointer(p,i);obj(a,q,('id','format','tool_version','execution_date','publication_date','environment_id','context','source_reference','report_text'))
        for k in ('id','tool_version','environment_id'):text(a[k],q+'/'+k,300)
        choice(a['format'],q+'/format',('twister_json',));day=iso(a['execution_date'],q+'/execution_date',r.cutoff);iso(a['publication_date'],q+'/publication_date',r.cutoff)
        if a['publication_date']<day:fail(q,'report_publication_before_execution')
        context=r.context(a['context'],q+'/context');r.literal(a['report_text'],q+'/report_text',a['source_reference']);v,error=report_json(a['report_text']);issues=[];made=[]
        if error or type(v)is not dict or type(v.get('testsuites'))is not list or type(v.get('environment'))is not dict:
            error=error or 'unsupported_Twister_report_structure'
        else:
            env=v['environment'];version=env.get('zephyr_version');run_date=env.get('run_date');dated_run=None
            if type(run_date)is str:
                try:dated_run=datetime.fromisoformat(run_date.replace('Z','+00:00')).date().isoformat()
                except ValueError:pass
            if version!=a['tool_version']:issues.append('report_tool_version_mismatch')
            if dated_run!=day:issues.append('report_run_date_missing_or_mismatch')
            suites=v['testsuites']
            if len(suites)>12:error='report_suite_limit'
            else:
                for si,s in enumerate(suites):
                    if type(s)is not dict or type(s.get('testcases'))is not list or len(s['testcases'])>30:error='unsupported_Twister_suite_structure';break
                    if s.get('status')is not None and type(s['status'])is not str:error='unsupported_Twister_status_type';break
                    for ci,t in enumerate(s['testcases']):
                        if type(t)is not dict:error='unsupported_Twister_case_structure';break
                        if t.get('status')is not None and type(t['status'])is not str:error='unsupported_Twister_status_type';break
                        for field in ('reason','log'):
                            if t.get(field)is not None:
                                try:text(t[field],'/report_case/'+field,6000,True)
                                except ValueError:error='unsupported_Twister_case_text'
                        if error:break
                        fields={k:s.get(k)for k in ('name','platform','toolchain','run_id','dut')};fields['identifier']=t.get('identifier')
                        if any(type(fields[k])is not str or not fields[k]for k in ('name','platform','toolchain','identifier')):error='report_identity_missing';break
                        if any(fields[k]is not None and type(fields[k])is not str for k in ('run_id','dut')):error='report_identity_type';break
                        status=TWISTER.get(t.get('status'),'unsupported_status');problems=issues[:]
                        if s.get('runnable')is False:
                            problems.append('suite_not_runnable')
                            if status=='passed':status='build_only';problems.append('case_pass_in_nonrunnable_suite')
                        elif s.get('runnable')is not True:problems.append('report_runnable_unknown')
                        if s.get('status')not in ('passed','failed'):problems.append('suite_not_completed_execution')
                        if fields['run_id']is None:problems.append('report_run_identity_not_supplied')
                        selector=dict(suite=fields['name'],identifier=fields['identifier'],platform=fields['platform'],toolchain=fields['toolchain'],run_id=fields['run_id'],dut=fields['dut'])
                        if context is not None:
                            for k in ('platform','toolchain'):
                                if fields[k]!=context[k]:problems.append('report_context_'+k+'_mismatch')
                        made.append(dict(id=a['id']+'#'+str(si)+'#'+str(ci),case_id=None,case_revision=None,requirement_ids=None,requirement_revisions=None,environment_id=a['environment_id'],status=status,raw_status=t.get('status'),raw_suite_status=s.get('status'),execution_date=day,context=deepcopy(context),evidence=dict(source_reference=a['source_reference'],report_id=a['id'],report_pointer='/testsuites/'+str(si)+'/testcases/'+str(ci)),actual_result=t.get('reason')or t.get('log'),problems=problems,report_id=a['id'],external_identity=selector,identity_origin='intrinsic_report_identity_before_selected_mapping'))
                    if error:break
        if len(candidates)+len(made)>60:fail(p,'parsed_report_case_limit')
        if error:r.gap('prepared_report_unusable',id=a['id'],reason=error);made=[]
        review.append(dict(id=a['id'],format=a['format'],tool_version=a['tool_version'],execution_date=a['execution_date'],publication_date=a['publication_date'],source_reference=a['source_reference'],context=context,parse_status=error or 'parsed_selected_Twister_profile',issues=issues,case_records=deepcopy(made),engine_executed_here=False));candidates+=made
    unique(review,p);return review,candidates

def testing(data,r):
    obj(data,'data',('as_of','jurisdiction','mode'),('object','goal','target','requirements','test_cases','environments','execution_records','prepared_reports','coverage_reports','methodology','defects'))
    mode=choice(data['mode'],'/mode',('questions','draft','review'))
    for k in ('object','goal'):
        if k in data:text(data[k],'/'+k)
    target=r.context(data.get('target'),'/target');requirements=[];cases=[];environments=[]
    for i,a in enumerate(rows(data.get('requirements',[]),'/requirements',20)):
        p=pointer('/requirements',i);obj(a,p,('id','revision','text','source_reference','excerpt'))
        for k in ('id','revision','text','excerpt'):r.literal(a[k],p+'/'+k,a['source_reference'])
        requirements.append(deepcopy(a))
    unique(requirements,'/requirements');reqby={a['id']:a for a in requirements}
    for i,a in enumerate(rows(data.get('environments',[]),'/environments',6)):
        p=pointer('/environments',i);obj(a,p,('id','kind','description'),('tool','tool_version','context'));text(a['id'],p+'/id',200);choice(a['kind'],p+'/kind',('host','simulation','hardware_hil'));text(a['description'],p+'/description')
        context=r.context(a.get('context'),p+'/context')
        for k in ('tool','tool_version'):
            if k in a:
                if context:r.literal(a[k],p+'/'+k,context['source_reference'])
                else:text(a[k],p+'/'+k,300)
        environments.append(dict(deepcopy(a),context=context))
    unique(environments,'/environments');envby={a['id']:a for a in environments}
    selectors=set()
    for i,a in enumerate(rows(data.get('test_cases',[]),'/test_cases',30)):
        p=pointer('/test_cases',i);obj(a,p,('id','revision','requirement_ids','requirement_revisions','level','kind','purpose','preconditions','inputs','steps','expected','method'),('environment_id','selected_execution_id','external_identity','mapping_evidence'))
        for k in ('id','revision','purpose','preconditions','inputs','expected','method'):text(a[k],p+'/'+k)
        for step in rows(a['steps'],p+'/steps',12,1):text(step,p+'/steps')
        links=rows(a['requirement_ids'],p+'/requirement_ids',20,1)
        if len(set(links))!=len(links):fail(p,'duplicate_requirement_link')
        revisions(a['requirement_revisions'],links,p+'/requirement_revisions')
        for identity in links:
            text(identity,p+'/requirement_ids',200)
            if identity not in reqby:r.gap('test_case_unknown_requirement',case_id=a['id'],requirement_id=identity)
            elif a['requirement_revisions'][identity]!=reqby[identity]['revision']:r.gap('test_case_requirement_revision_mismatch',case_id=a['id'],requirement_id=identity)
        choice(a['level'],p+'/level',('host_unit','host_integration','simulation','HIL_plan'));choice(a['kind'],p+'/kind',('normal','boundary','peripheral_error','power_loss','recovery'))
        for k in ('environment_id','selected_execution_id'):
            if k in a:text(a[k],p+'/'+k,500)
        if 'external_identity'in a:
            e=obj(a['external_identity'],p+'/external_identity',('report_id','suite','identifier','platform','toolchain','run_id','dut'))
            for k in e:
                if e[k]is not None:text(e[k],p+'/external_identity/'+k,500)
                elif k not in ('run_id','dut'):fail(p,'external_identity_field')
            key=tuple(e[k]for k in ('report_id','suite','identifier','platform','toolchain','run_id','dut'))
            if key in selectors:fail(p,'same_external_case_mapped_twice')
            selectors.add(key)
        if 'mapping_evidence'in a:
            ev=r.evidence(a['mapping_evidence'],p+'/mapping_evidence')
            for k in ('id','revision'):r.literal(a[k],p+'/'+k,ev['source_reference'])
            for rid,rev in a['requirement_revisions'].items():r.literal(rev,pointer(p+'/requirement_revisions',rid),ev['source_reference'])
            for k,x in a.get('external_identity',{}).items():
                if x is not None:r.literal(x,p+'/external_identity/'+k,ev['source_reference'])
        cases.append(deepcopy(a))
    unique(cases,'/test_cases');caseby={a['id']:a for a in cases};candidates=[]
    for i,a in enumerate(rows(data.get('execution_records',[]),'/execution_records',40)):
        p=pointer('/execution_records',i);obj(a,p,('id','case_id','case_revision','requirement_ids','requirement_revisions','environment_id','status'),('execution_date','context','evidence','actual_result','duration'))
        for k in ('id','case_id','case_revision','environment_id','status'):text(a[k],p+'/'+k,300)
        for identity in rows(a['requirement_ids'],p+'/requirement_ids',20):text(identity,p+'/requirement_ids',200)
        if len(set(a['requirement_ids']))!=len(a['requirement_ids']):fail(p,'duplicate_record_requirement')
        revisions(a['requirement_revisions'],a['requirement_ids'],p+'/requirement_revisions')
        day=iso(a['execution_date'],p+'/execution_date',r.cutoff)if 'execution_date'in a else None;context=r.context(a.get('context'),p+'/context');evidence=r.evidence(a['evidence'],p+'/evidence')if 'evidence'in a else None
        if evidence:
            for k in ('case_id','case_revision','status'):r.literal(a[k],p+'/'+k,evidence['source_reference'])
            if day is not None:r.literal(day,p+'/execution_date',evidence['source_reference'])
            for rid,rev in a['requirement_revisions'].items():r.literal(rev,pointer(p+'/requirement_revisions',rid),evidence['source_reference'])
            if 'actual_result'in a:r.literal(a['actual_result'],p+'/actual_result',evidence['source_reference'])
        elif 'actual_result'in a:text(a['actual_result'],p+'/actual_result')
        duration=r.time(a['duration'],p+'/duration',day or r.cutoff)if 'duration'in a else None
        candidates.append(dict(deepcopy(a),execution_date=day,context=context,evidence=evidence,duration_s=duration,problems=[],report_id=None))
    unique(candidates,'/execution_records');reportreview,external=prepared_reports(data.get('prepared_reports',[]),'/prepared_reports',r)
    for entry in external:
        matches=[a for a in cases if a.get('external_identity')==dict(report_id=entry['report_id'],**entry['external_identity'])]
        if len(matches)==1:
            selected=matches[0];entry.update(case_id=selected['id'],case_revision=selected['revision'],requirement_ids=selected['requirement_ids'],requirement_revisions=selected['requirement_revisions'],identity_origin='selected_mapping_not_intrinsic_Twister_requirement_revision',mapping_evidence=selected.get('mapping_evidence'))
            if not selected.get('mapping_evidence'):entry['problems'].append('external_identity_mapping_evidence_not_supplied')
        else:entry['problems'].append('external_case_not_mapped')
    candidates+=external;unique(candidates,'/all_execution_records');review=[];reportby={a['id']:a for a in reportreview}
    for a in candidates:
        problems=a['problems'][:];case=caseby.get(a.get('case_id'));env=envby.get(a['environment_id'])
        if case is None:problems.append('execution_unknown_case')
        else:
            if a['case_revision']!=case['revision']:problems.append('case_revision_mismatch')
            if set(a['requirement_ids'])!=set(case['requirement_ids']):problems.append('execution_requirement_links_mismatch')
            if a['requirement_revisions']!=case['requirement_revisions']:problems.append('execution_requirement_revision_mismatch')
            if any(identity not in reqby for identity in case['requirement_ids']):problems.append('unknown_selected_requirement')
            elif any(a['requirement_revisions'].get(identity)!=reqby[identity]['revision']for identity in case['requirement_ids']):problems.append('selected_requirement_revision_mismatch')
            if a['environment_id']!=case.get('environment_id'):problems.append('case_environment_mismatch')
        if env is None:problems.append('execution_environment_not_supplied')
        else:
            if case and env['kind']!=('hardware_hil'if case['level']=='HIL_plan'else 'simulation'if case['level']=='simulation'else 'host'):problems.append('test_level_environment_mismatch')
            if context_differences(a.get('context'),env['context']):problems.append('execution_environment_context_mismatch')
            if not env.get('tool')or not env.get('tool_version'):problems.append('environment_tool_version_not_supplied')
            if a['report_id']is not None and env.get('tool_version')!=reportby[a['report_id']]['tool_version']:problems.append('report_environment_tool_version_mismatch')
            if env['kind']=='hardware_hil'and a.get('external_identity')and not a['external_identity']['dut']:problems.append('HIL_device_identity_not_supplied')
        differences=context_differences(a.get('context'),target)
        if differences:problems.append('execution_target_context_mismatch')
        if a['status']not in STATUSES:problems.append('unsupported_execution_status')
        if a['status']in ('passed','failed','error'):
            if not a.get('execution_date'):problems.append('execution_date_not_supplied')
            if not a.get('evidence'):problems.append('execution_evidence_not_supplied')
            if a['report_id']is None and not a.get('actual_result'):problems.append('actual_result_not_supplied')
        supported=not problems and a['status']in STATUSES
        if problems:r.gap('execution_record_unresolved',id=a['id'],issues=problems)
        review.append(dict(deepcopy(a),problems=problems,context_differences=differences,identity_and_evidence_consistent=supported,counts_as_reported_pass=supported and a['status']=='passed',execution_performed_here=False))
    case_review=[]
    for a in cases:
        related=[x for x in review if x['case_id']==a['id']];chosen=None;issue=None
        if a.get('selected_execution_id'):
            chosen=next((x for x in related if x['id']==a['selected_execution_id']),None)
            if chosen is None:issue='selected_execution_not_found_for_case'
        elif len(related)==1:chosen=related[0]
        elif len(related)>1:issue='multiple_executions_need_explicit_selection'
        else:issue='execution_not_supplied'
        if issue:r.gap(issue,case_id=a['id'])
        status='unresolved'if issue or chosen and not chosen['identity_and_evidence_consistent']else chosen['status']
        case_review.append(dict(proposed_case=deepcopy(a),execution_record_ids=[x['id']for x in related],selected_record_id=chosen['id']if chosen else None,selection_issue=issue,reported_status=status,reported_pass=bool(chosen and chosen['counts_as_reported_pass']and issue is None)))
    covered={rid for a in cases for rid in a['requirement_ids']if rid in reqby};passing={rid for rid in covered if all(a['reported_pass']for a in case_review if rid in a['proposed_case']['requirement_ids'])};count=len(requirements)
    req_review=[dict(requirement=deepcopy(a),case_ids=[c['id']for c in cases if a['id']in c['requirement_ids']],all_linked_planned_cases_have_consistent_reported_pass=a['id']in passing)for a in requirements]
    for a in req_review:
        if not a['case_ids']:r.gap('requirement_without_planned_case',requirement_id=a['requirement']['id'])
    coverage=[]
    for i,a in enumerate(rows(data.get('coverage_reports',[]),'/coverage_reports',6)):
        p=pointer('/coverage_reports',i);obj(a,p,('id','metric','covered','total','context','execution_date','source_reference','excerpt'));text(a['id'],p+'/id',200);choice(a['metric'],p+'/metric',('line','branch'));day=iso(a['execution_date'],p+'/execution_date',r.cutoff);ctx=r.context(a['context'],p+'/context');r.evidence({k:a[k]for k in ('source_reference','excerpt')},p);n=r.q(a['covered'],p+'/covered',('count',),0,10**12,True,day);total=r.q(a['total'],p+'/total',('count',),0,10**12,True,day)
        r.literal(day,p+'/execution_date',a['source_reference'])
        if n>total:fail(p,'coverage_count_exceeds_total')
        differences=context_differences(ctx,target)
        if differences:r.gap('coverage_target_context_mismatch',id=a['id'],fields=differences)
        coverage.append(dict(provided=deepcopy(a),selected_count_ratio=n/total if total else None,ratio_status='undefined_zero_denominator'if not total else 'provided_count_arithmetic_only',target_context_matches=not differences,instrumentation_executed_here=False))
    unique([x['provided']for x in coverage],'/coverage_reports');methodology=None
    if 'methodology'in data:
        a=obj(data['methodology'],'/methodology',('resources','order','entry_criteria','exit_criteria'),('selected_basis',));methodology=deepcopy(a)
        for k in ('resources','order'):
            for item in rows(a[k],'/methodology/'+k,12):text(item,'/methodology/'+k)
        for k in ('entry_criteria','exit_criteria'):text(a[k],'/methodology/'+k)
        if 'selected_basis'in a:methodology['selected_basis']=r.basis(a['selected_basis'],'/methodology/selected_basis')
        methodology['status']='proposed_methodology_not_accepted'
    defects=[]
    for i,a in enumerate(rows(data.get('defects',[]),'/defects',16)):
        p=pointer('/defects',i);obj(a,p,('id','description','case_ids','state'),('owner','next_action','evidence'));text(a['id'],p+'/id',200);text(a['description'],p+'/description');choice(a['state'],p+'/state',('reported_open','reported_closed','unknown'))
        for identity in rows(a['case_ids'],p+'/case_ids',30):
            if identity not in caseby:r.gap('defect_unknown_case',id=a['id'],case_id=identity)
        for k in ('owner','next_action'):
            if k in a:text(a[k],p+'/'+k)
        if 'evidence'in a:r.evidence(a['evidence'],p+'/evidence')
        elif a['state']=='reported_closed':r.gap('closed_defect_without_selected_evidence',id=a['id'])
        defects.append(deepcopy(a))
    unique(defects,'/defects')
    if mode=='questions'and any(data.get(k)for k in ('execution_records','prepared_reports','coverage_reports')):fail('/mode','questions_contains_execution_records')
    return dict(mode=mode,object=data.get('object'),goal=data.get('goal'),target=target,requirements=req_review,test_cases=case_review,environments=environments,execution_reviews=review,prepared_reports=reportreview,coverage=dict(requirement_count=count,requirements_with_planned_cases=len(covered),requirements_with_consistent_reported_pass=len(passing),planned_requirement_ratio=F(len(covered),count)if count else None,reported_pass_requirement_ratio=F(len(passing),count)if count else None,case_count=len(cases),selected_reported_pass_case_count=sum(a['reported_pass']for a in case_review),all_planned_cases_have_consistent_reported_pass=bool(cases)and all(a['reported_pass']for a in case_review),scope='selected_supplied_records_not_actual_testing_or_code_coverage'),provided_code_coverage=coverage,methodology=methodology,defects=defects,questions=['supply_versioned_requirements_and_test_scope','separate_host_logic_doubles_simulation_and_HIL','select_build_board_toolchain_and_actual_result_records','plan_boundary_peripheral_fault_power_loss_and_recovery_cases']if mode=='questions'else [],tests_executed_here=False,hil_executed_here=False)

def _run(function,data):
    reject_known_secret_material(data)
    if type(function)is not str or function not in FUNCTIONS:fail('function','unsupported')
    if type(data)is not dict:fail('data','object')
    bounded(data);r=Read(data)
    try:result=(debug if function=='hw_debug'else testing)(data,r)
    except (KeyError,TypeError,AttributeError,IndexError):fail('data','invalid_nested_structure')
    if len(r.units)+len(r.literals)>800:fail('data','numeric_plus_literal_budget')
    result.update(as_of=r.cutoff,jurisdiction='RU',analysis_only=True,source_semantics_established=False,current_normative_chain_established=False,device_connected=False,device_commands_sent=False,hardware_test_performed=False,hil_executed=False,tool_executed=False,firmware_flashed=False,evidence_gaps=r.gaps)
    return display(result),r
def execute(function,data):return _run(function,data)[0]
def input_units(function,data):return _run(function,data)[1].units
def selected_texts(function,data):return _run(function,data)[1].literals

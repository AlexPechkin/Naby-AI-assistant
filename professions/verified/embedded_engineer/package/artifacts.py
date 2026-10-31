"""Local documents from exactly recomputed embedded results; no execution or URLs."""
import hashlib,json,re
from .artifact_labels import UI,TOKENS,TEMPLATES,FIELDS,tr,field_label,token,LANGUAGES
from .artifact_formatting import snapshot,display_text,scalar,LITERAL_FIELDS,flat,extra_sections,docx_bytes,pdf_bytes

ROUTES={
'fw_architecture':{
'sw_requirements':[
('mode','questions','context','proposal.provided.device_functions','proposal.provided.requirements','proposal.provided.notes'),
('proposal.provided.interfaces','platform_candidates'),
('timing',),
('proposal.provided.error_handling','proposal.provided.watchdog','proposal.provided.states','proposal.provided.transitions','proposal.provided.forbidden_transitions','proposal.provided.reset_state','proposal.transition_conflicts'),
('proposal.provided.security','proposal.provided.RU_ECB_OS_constraints','risks','evidence_gaps'),
('memory','power','fpga')],
'arch_doc':[
('mode','questions','context','proposal','platform_candidates','risks','evidence_gaps'),
('timing.model','timing.tasks','timing.total_demand_ratio','timing.selected_utilization_limit','timing.selected_utilization_margin','timing'),
('timing.interrupts','timing.interrupt_response_times_assessed'),
('memory',),
('power','fpga')]},
'fw_code':{'program_text':[
('mode','questions','context','review.selected_ISR_functions','review.files.id','review.files.path','review.files.language','review.files.source_reference'),
('review.files.logical_utf8_sha256','review.files.logical_UTF8_bytes','tool_reports'),
('review.files.content','review','review_records','counter','uart','state_machine','watchdog_note','evidence_gaps')]},
'hw_debug':{'test_report':[
('mode','questions','context','time_basis','symptoms','connection'),
('telemetry','uart','modbus','can','timing_windows','observations'),
('telemetry.missing_candidates','telemetry.missing_candidate_count','telemetry.records.sequence_status','uart.within_selected_tolerance','modbus.transactions','can.frames.structural_fields_match','timing_windows.within_selected_limits'),
('hypotheses','next_checks','evidence_gaps')]},
'fw_testing':{
'test_program':[
('mode','questions','object','target'),
('goal',),
('requirements','test_cases.proposed_case.requirement_ids','test_cases.proposed_case.requirement_revisions'),
('environments','methodology','test_cases.proposed_case.preconditions','test_cases.proposed_case.inputs','test_cases.proposed_case.steps','test_cases.proposed_case.environment_id'),
('test_cases','evidence_gaps')],
'test_report':[
('mode','questions','object','goal','target','environments'),
('requirements','test_cases'),
('execution_reviews','prepared_reports','coverage','provided_code_coverage'),
('defects','evidence_gaps','methodology')]},
'secure_dev':{'sdl_pack':[
('mode','questions','threat_model','requirements','risk_matrix'),
('components',),
('tool_reports',),
('vulnerability_queries','security_controls','evidence_gaps'),
('update_plan',)]},
'sw_docs_rights':{
'program_text':[
('mode','source_files','source_files.id','source_files.path_label','source_files.source_reference'),
('source_files.version','source_files.provided_utf8_content_sha256','source_files.original_bytes_sha256','source_files.utf8_content_bytes','source_files.hash_scope','source_files.encoding_note','source_files.source_compiled'),
('source_files.content',)],
'program_description':[
('mode','questions','recipient','document_basis','program_sections','program_sections.general'),
('program_sections.purpose',),
('program_sections.structure',),
('program_sections.technical_means',),
('program_sections.inputs_outputs',)],
'programmer_manual':[
('mode','questions','recipient','program_sections.purpose'),
('program_sections.characteristics',),
('program_sections.invocation',),
('program_sections.inputs_outputs',),
('program_sections.messages',)],
'pr_registration':[
('mode','questions','rights.right_holder','rights.employment_basis','rights.assignment_basis','rights.contract_notes','rights.unresolved_questions','rights.interpretation','rights','license_records','evidence_gaps'),
('rights.authors',),
('registration.program_name','registration.abstract','registration.status','registration.application_notes','registration.basis'),
('registration.deposited_material_ids','registration',)]},
'release':{'release_notes':[
('mode','questions','notes','notes.version','notes.date','notes.branch','notes.tag','images','builds'),
('notes.changes',),
('notes.fixes',),
('notes.compatibility','test_reviews.expected_context_constraints','test_reviews.constraint_checks'),
('notes.limitations','expected_tests','executions','test_reviews','test_ledger_status','unmatched_execution_ids','evidence_gaps'),
('notes.update','notes.rollback','schedule',)]}}

BOUND_NAMES={'as_of','jurisdiction','input_sha256','analysis_only','assisted_draft','external_actions','arithmetic_precision','architecture_is_draft','review_is_not_compilation_or_MISRA_certification','root_cause_established','tests_executed_here','hil_executed_here','decision_scope','device_connected','firmware_flashed'}
BOUND_SUFFIXES=('_approved','_certified','_established','_performed','_applied','_authorized','_verified','_executed','_processed','_submitted','_started','_programmed','_sent','_compiled')
def _is_bound(key):return key in BOUND_NAMES or key in ('published','hardware_or_WCET_validation_performed') or key.endswith(BOUND_SUFFIXES)

def _leaves(v,path=(),parents=()):
    if type(v)is dict and v:
        for k,x in v.items():yield from _leaves(x,path+(k,),parents+((path,v),))
    elif type(v)is list and v:
        for i,x in enumerate(v):yield from _leaves(x,path+(str(i),),parents+((path,v),))
    else:yield path,v,parents

def _score(pattern,path):
    plain=tuple(x for x in path if not x.isdigit());parts=tuple(pattern.split('.'))
    return len(parts) if plain[:len(parts)]==parts else -1

def _key(path):return next((x for x in reversed(path)if not x.isdigit()),'value')
def _has(parents,key,value):return any(type(p)is dict and p.get(key)==value for _,p in parents)
def _label_part(path,i,language):
    if i and path[i-1]=='requirement_revisions':return display_text(path[i])
    if path[0]=='source_files' and path[i]=='version':return tr(('Версия из предоставленных метаданных файла','Version from supplied file metadata','所提供文件元数据版本'),language)
    return field_label(path[i],language) if not path[i].isdigit() else str(int(path[i])+1)

def _shown(function,path,value,parents,result,language):
    key=_key(path)
    if value is None:
        if len(path)==1 and key in ('timing','memory','power','fpga','proposal','counter','uart','state_machine','update_plan','risk_matrix','risks','registration','schedule','notes','can','modbus','telemetry'):
            return token('not_requested',language)
        parent=next((p for _,p in reversed(parents)if type(p)is dict),{})
        transaction=next((p for _,p in reversed(parents)if type(p)is dict and 'request_response_fields_match'in p and type(p.get('provided'))is dict),None)
        broadcast=False
        if transaction is not None:
            request_id=transaction['provided'].get('request_id')
            broadcast=any(f.get('provided',{}).get('id')==request_id and f.get('address')==0 for f in result.get('modbus',{}).get('frames',[]))
        if broadcast and key in ('response_id','response_latency_s','within_selected_latency'):
            return tr(('Ответ и его задержка не требуются для выбранного широковещательного запроса','Response and latency are not required for the selected broadcast request','所选广播请求不需要响应及其延迟'),language)
        if key=='within_selected_latency' and transaction is not None and 'max_latency'not in transaction['provided']:
            return tr(('Предел задержки не выбран','Latency limit not selected','未选择延迟限值'),language)
        if key=='within_selected_limits' and 'selected_limits_s'in parent:
            if not parent['selected_limits_s']:return tr(('Пределы времени не выбраны','Time limits not selected','未选择时间限值'),language)
            if str(parent.get('raw_difference_s','')).startswith('-'):return tr(('Сравнение не выполнено при регрессии времени','Comparison not performed for time regression','时间回退时未执行比较'),language)
        if key=='selection_issue':return tr(('Проблем выбора записи в выбранном наборе не выявлено','No record selection issue in the selected set','所选集合中未发现记录选择问题'),language)
        if key=='time_basis':return tr(('Общая шкала времени не выбрана','Common time basis not selected','未选择共同时间基准'),language)
        if function=='hw_debug' and 'telemetry'in path:
            telemetry=result.get('telemetry')or{}
            if key=='serial_modulus' and telemetry.get('sequence_model')=='monotonic':return tr(('Модуль не используется в монотонной модели','Modulus not used in monotonic model','单调模型不使用模数'),language)
            if key=='selected_gap_s' or key=='above_selected_gap' and telemetry.get('selected_gap_s')is None:return tr(('Предел интервала не выбран','Gap limit not selected','未选择间隔限值'),language)
            if key=='unwrapped_position':return tr(('Позиция не определена при неоднозначности модели порядка','Position undefined under ordering model ambiguity','排序模型有歧义时位置未定义'),language)
            if key=='max_nonnegative_interarrival_s':return tr(('В выбранном наборе нет рассчитанного неотрицательного интервала','No calculated nonnegative interval in selected set','所选集合无已计算非负间隔'),language)
            if key in ('interarrival_s','above_selected_gap'):
                if parent.get('sequence_status')=='first':return tr(('Для первой записи нет предыдущего интервала','First record has no preceding interval','首条记录无前一间隔'),language)
                if str(parent.get('interarrival_s','')).startswith('-'):return tr(('Сравнение интервала не выполнено при регрессии времени','Interval comparison not performed for time regression','时间回退时未执行间隔比较'),language)
                return tr(('Интервал не вычислен без общей шкалы или пары отметок','Interval not calculated without common basis or timestamp pair','无共同基准或时间戳对时未计算间隔'),language)
        if function=='hw_debug' and 'modbus'in path:
            shape=next((p['shape_status']for _,p in reversed(parents)if type(p)is dict and 'shape_status'in p),None)
            if shape is not None and key in ('byte_count','address','function','crc_matches','computed_crc_hex','decoded','supported_shape'):
                return tr(('Не разобрано или не оценено для предоставленной структуры','Not decoded or assessed for supplied structure','未解码或评估所提供结构'),language)+' / '+token(shape,language)
            if key=='request_response_fields_match':return tr(('Не сопоставлено см несогласованности выбранной транзакции','Not compared see selected transaction issues','未比对 请参阅所选事务问题'),language)
        if key in ('deadline_us','blocking_budget_us','priority_rank')and result.get('timing',{}).get('model')=='utilization_only':
            return tr(('Не требуется для выбранной модели только загрузки','Not required for selected utilization only model','所选仅利用率模型不需要此项'),language)
        if key in ('run_date','configuration_sha256','run_source_reference') and _has(parents,'state','not_run'):
            return tr(('Не требуется для предоставленного статуса запуска не было','Not required for supplied not run state','所提供未运行状态不需要此项'),language)
        if key in ('response_time_us','model_all_task_deadlines_met','model_deadline_met','next_iterate_deadline_margin_us','last_iterate_us','next_iterate_us'):
            state=next((p['status']for _,p in reversed(parents)if type(p)is dict and 'status'in p),None)
            return tr(('Не вычислено выбранной моделью','Not calculated by selected model','所选模型未计算'),language)+((' / '+token(state,language))if state else '')
        if key in ('utilization','utilization_ratio','selected_count_ratio','planned_requirement_ratio','reported_pass_requirement_ratio'):
            return tr(('Отношение не определено при пустом или нулевом знаменателе','Ratio undefined with empty or zero denominator','空或零分母下比值未定义'),language)
        if key in ('average_power_W','mode_average_current_mA_excluding_transitions','ideal_energy_limited_life_s'):
            return tr(('Не вычислено при неполном окне или нулевой мощности см пробелы','Not calculated for incomplete window or zero power see gaps','窗口不完整或功率为零时未计算 见缺口'),language)
        if key in ('selected_maximum_elapsed','unambiguous_under_selected_bound'):
            return tr(('Граница истинного интервала не выбрана','True elapsed bound not selected','未选择真实间隔界限'),language)
        if key=='elapsed_s_under_single_modulus_model':return tr(('Нет достаточной границы интервала или выбранной частоты','Sufficient elapsed bound or selected frequency unavailable','缺少充分间隔界限或所选频率'),language)
        if key in ('priority','priority_label','selected_category'):
            return tr(('Нет выбранной ячейки порядковой матрицы','No selected ordinal matrix cell','无所选序数矩阵单元'),language)
        if key in ('matches_selected_logical_text','selected_source_line'):
            return tr(('Соответствующий выбранный исходник или строка не установлены','Matching selected source or line not established','未确定匹配的所选源码或行'),language)
        if key in ('inside_selected_region','same_size_plain_copy'):
            return tr(('Не вычислено без нужного адреса или связанного образа','Not calculated without required address or linked image','无所需地址或关联镜像时未计算'),language)
        if key=='wire_CRC_matches':return tr(('CRC линии отсутствует в предоставленном экспорте','Wire CRC absent from supplied export','所提供导出不含线路CRC'),language)
        error_frame=_has(parents,'frame_type','error_record') or any(type(p)is dict and type(p.get('provided'))is dict and p['provided'].get('frame_type')=='error_record'for _,p in parents)
        if key in ('arbitration_id','structural_fields_match','expected_payload_bytes','actual_payload_bytes') and error_frame:
            return tr(('Не используется для выбранной записи ошибки CAN','Not used for selected CAN error record','所选CAN错误记录不使用此项'),language)
        if key in ('duration_s','response_latency_s','within_selected_limits','within_selected_latency','max_nonnegative_interarrival_s') and function=='hw_debug':
            return tr(('Не вычислено без общей шкалы времени или нужной пары записей','Not calculated without common time basis or required record pair','无共同时间基准或所需记录对时未计算'),language)
        if key=='total_duration_days' and result.get('schedule',{}).get('schedule_status')=='empty_task_graph_no_duration_estimated':
            return token('empty_task_graph_no_duration_estimated',language)
        if key=='queried_at':return token('not_supplied_no_freshness_established',language)
        if key=='actual_result' and any(type(p)is dict and p.get('report_id')is not None for _,p in parents):
            return tr(('Текст reason или log не предоставлен и не выдумывается','Reason or log text not supplied and not invented','未提供reason或log文本 不予编造'),language)
    if type(value)is str:
        if key in ('compared_fields','missing_fields','mismatched_fields','fields_without_selected_expected_constraint','control') and value in FIELDS:return field_label(value,language)
        if key in LITERAL_FIELDS or key.endswith(('_id','_ids','_reference','_references','_sha256','_version','_unit','_units')) or 'requirement_revisions'in path:return display_text(value)
        return display_text(token(value,language))
    if type(value)is list:return UI[language]['none']
    if type(value)is dict:return UI[language]['missing']
    return scalar(value,language)

def _summary(function,result,language):
    text=tr({
        'fw_architecture':('Предложение и расчёты относятся к выбранным бюджетам и модели. Планируемость аппаратуры измерения и выбор платформы не установлены.','The proposal and calculations concern selected budgets and models. Hardware schedulability measurements and platform selection are not established.','提议与计算仅涉及所选预算和模型 未确定硬件可调度性 测量或平台选择'),
        'fw_code':('Показаны выбранные исходники арифметика и кандидаты для ревью. Компиляция анализатор и проверка MISRA здесь не выполнялись.','Selected source arithmetic and review candidates are shown. Compilation analyzer execution and MISRA verification were not performed here.','显示所选源码 算术与审查候选 此处未编译 未运行分析器或核验MISRA'),
        'hw_debug':('Сопоставлены предоставленные записи и выбранные модели интерфейсов. Физическая потеря пакета и причина сбоя не установлены.','Supplied records and selected interface models were compared. Physical packet loss and root cause are not established.','已比对所提供记录与所选接口模型 未确定实际丢包或故障根因'),
        'fw_testing':('Планирование тестов отделено от согласованности предоставленных результатов. Запуск тестов и приёмка методики здесь не выполнялись.','Test planning is separate from supplied-result consistency. Tests and methodology acceptance were not performed here.','测试计划与所提供结果一致性分开 此处未运行测试或接受方法'),
        'secure_dev':('Предложения защиты и предоставленные свидетельства показаны отдельно. Сертификация проверка подписи и отсутствие уязвимостей не установлены.','Security proposals and supplied evidence are separate. Certification signature verification and vulnerability clearance are not established.','安全提议与所提供证据分开 未确定认证 签名验证或无漏洞'),
        'sw_docs_rights':('Подготовлены выбранные части программной документации и правовых материалов. Правообладание совместимость лицензий и регистрация не установлены.','Selected software documentation and rights materials are drafted. Ownership license compatibility and registration are not established.','已编制所选软件文档及权利材料草稿 未确定权属 许可兼容性或登记'),
        'release':('Предоставленные записи выпуска и график не являются разрешением выпуска. Образы не подписывались не публиковались и не отправлялись на устройство.','Supplied release records and schedule are not release authorization. Images were not signed published or sent to a device.','所提供发布记录与计划不构成发布许可 未签名 发布或向设备发送镜像')
    }[function],language)
    qualifiers={
        'ru':{'Планируемость аппаратуры измерения и выбор платформы не установлены.':'Планируемость аппаратуры измерения и выбор платформы не установлены этим инструментом.','Физическая потеря пакета и причина сбоя не установлены.':'Физическая потеря пакета и причина сбоя не установлены этим инструментом.','Сертификация проверка подписи и отсутствие уязвимостей не установлены.':'Сертификация проверка подписи и отсутствие уязвимостей не установлены этим инструментом.','Правообладание совместимость лицензий и регистрация не установлены.':'Правообладание совместимость лицензий и регистрация не установлены этим инструментом.','Образы не подписывались не публиковались и не отправлялись на устройство.':'Этот инструмент не подписывал не публиковал и не отправлял образы на устройство.'},
        'en':{'are not established.':'are not established by this tool.','Images were not signed published or sent to a device.':'This tool did not sign publish or send images to a device.'},
        'zh':{'未确定硬件可调度性 测量或平台选择':'本工具未确定硬件可调度性 测量或平台选择','未确定实际丢包或故障根因':'本工具未确定实际丢包或故障根因','未确定认证 签名验证或无漏洞':'本工具未确定认证 签名验证或无漏洞','未确定权属 许可兼容性或登记':'本工具未确定权属 许可兼容性或登记','未签名 发布或向设备发送镜像':'本工具未签名 发布或向设备发送镜像'}}
    for before,after in qualifiers[language].items():text=text.replace(before,after)
    if function=='fw_architecture' and result.get('timing')is not None:text+=' '+UI[language]['host_load_notice']
    return text

CODE_FIELDS={'content','c_draft','record_json','query_json','response_json','report_text','source_line_excerpt','selected_source_line'}
PROSE_FIELDS={'purpose','structure','technical_means','inputs_outputs','characteristics','invocation','messages','general','symptoms','connection','proposal','analysis','description','explanation','expected_observation','preconditions','inputs','steps','expected','abstract','error_handling','watchdog','security','power_strategy','runtime_choice','notes','note','update','rollback','compatibility','limitations','changes','fixes','excerpt','model_excerpt','limit_excerpt'}

def _content(function,artifact,result,language):
    specs=ROUTES[function][artifact];definitions=TEMPLATES[artifact]['sections']
    if len(specs)!=len(definitions):raise ValueError('artifact_section_count_mismatch')
    sections=[dict(title=tr(title,language),paragraphs=[],rows=[],code_blocks=[],source_paths=list(paths),selected_paths=[],rendered_leaf_values=[])for title,paths in zip(definitions,specs)]
    for path,value,parents in _leaves(result):
        if not path or _is_bound(path[0]):continue
        score,index=max(((max((_score(p,path)for p in paths),default=-1),i)for i,paths in enumerate(specs)),key=lambda x:(x[0],-x[1]))
        if score<0:continue  # Another named artifact owns this leaf; union audit is mandatory.
        section=sections[index];ids=[]
        for _,parent in parents:
            if type(parent)is dict and type(parent.get('id'))is str and parent['id']not in ids:ids.append(parent['id'])
        label=' / '.join(ids+[_label_part(path,i,language)for i in range(max(0,len(path)-3),len(path))])
        shown=_shown(function,path,value,parents,result,language);key=_key(path)
        if type(value)is str and key in CODE_FIELDS:
            text=display_text(value).replace('\ufeff','\\uFEFF') if value else UI[language]['empty_text']
            if value and not value.strip():
                visible=''.join({' ':'\\x20','\t':'\\t','\r':'\\r','\n':'\\n'}.get(ch,'\\u%04X'%ord(ch))for ch in value)
                text=UI[language]['whitespace_text']+'\n'+visible
            shown=text
            section['code_blocks'].append({'label':label,'text':text,'source_path':'.'.join(path)})
        elif type(value)is str and key in PROSE_FIELDS:
            section['paragraphs'].append(label+'\n'+shown)
        else:section['rows'].append([label,shown])
        section['selected_paths'].append('.'.join(path));section['rendered_leaf_values'].append({'path':'.'.join(path),'value':value,'display':shown})
    for section in sections:
        if section['code_blocks']:section['paragraphs'].insert(0,UI[language]['code_notice'] if any(b['source_path'].endswith(('.content','.c_draft'))for b in section['code_blocks']) else UI[language]['original_record'])
        if not section['rows']and not section['paragraphs']and not section['code_blocks']:section['paragraphs']=[UI[language]['section_empty']]
    sections[0]['paragraphs'].insert(0,_summary(function,result,language))
    bounds={k:v for k,v in result.items()if _is_bound(k)}
    sections.append(dict(title=UI[language]['tool_scope'],paragraphs=[UI[language]['verification_scope'],UI[language]['scope_note']],rows=flat(bounds,language),code_blocks=[],source_paths=list(bounds),selected_paths=list(bounds),rendered_leaf_values=[dict(path=k,value=v,display=scalar(v,language))for k,v in bounds.items()]))
    return sections

def _fence(value):
    runs=[len(x)for x in re.findall(r'`+',value)];f='`'*max(3,max(runs,default=0)+1)
    return f+'\n'+value+'\n'+f

def markdown_bytes(title,sections,language,review_evidence):
    from .artifact_formatting import intro
    lines=['# '+title,'']
    for value in intro(language,review_evidence):lines.extend([_fence(display_text(value)),''])
    for s in sections:
        lines.extend(['## '+s['title'],''])
        for paragraph in s.get('paragraphs',[]):lines.extend([_fence(display_text(paragraph)),''])
        for block in s.get('code_blocks',[]):lines.extend([_fence(block['label']+'\n'+block['text']),''])
        for row in s.get('rows',[]):lines.extend([_fence('\n'.join(display_text(x)for x in row)),''])
    return ('\n'.join(lines)+'\n').encode('utf8')

def render(function,result,language,*,config,review_evidence=None):
    if function not in ROUTES or language not in LANGUAGES:raise ValueError('artifact_function_language')
    try:json.dumps(result,allow_nan=False);json.dumps(config,allow_nan=False)
    except (TypeError,ValueError):raise ValueError('artifact_json_values_required')from None
    result=snapshot(result);config=snapshot(config);review=snapshot(review_evidence)if review_evidence is not None else None
    from .core import execute
    canonical=lambda v:json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    if canonical(execute(function,config))!=canonical(result):raise ValueError('artifact_result_input_mismatch')
    files={'result.json':(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8')}
    sources=result.get('source_files',[])if function=='sw_docs_rights'else result.get('review',{}).get('files',[])if function=='fw_code'else []
    for i,source in enumerate(sources,1):files['program_source_'+str(i)+'.txt']=source['content'].encode('utf8')
    for artifact in ROUTES[function]:
        sections=_content(function,artifact,result,language)+extra_sections(review,language);title=tr(TEMPLATES[artifact]['title'],language)
        files[artifact+'.'+TEMPLATES[artifact]['format']]=(markdown_bytes if TEMPLATES[artifact]['format']=='md'else docx_bytes)(title,sections,language,review)
        files[artifact+'.pdf']=pdf_bytes(title,sections,language,review)
    return files

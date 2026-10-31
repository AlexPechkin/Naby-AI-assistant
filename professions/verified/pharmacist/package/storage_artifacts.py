"""Narrow storage views without fictitious measurements or procedure drafts."""
from .artifact_labels import UI,tr,field_label,token
from .artifact_formatting import xlsx_bytes,pdf_bytes,extra_sections,display_text,LITERAL_FIELDS

FIELDS={
'observed_at':('Момент оценки','Observation timestamp','评估时刻'),
'expiry_alert_days':('Выбранный горизонт предупреждения в днях','Selected warning horizon in days','所选预警天数'),
'humidity_applicability':('Применимость контроля влажности по выбранным данным','Humidity monitoring applicability from selected data','所选资料湿度监测适用性'),
'temperature_check_performed':('Выполнено сопоставление температуры','Temperature comparison performed','已进行温度比较'),
'humidity_check_performed':('Выполнено сопоставление влажности','Humidity comparison performed','已进行湿度比较'),
'expiry_check_performed':('Выполнено сопоставление сроков годности','Expiry comparison performed','已进行有效期比较'),
'expiry_semantics_gaps':('Нерешённые вопросы толкования сроков','Unresolved expiry semantics','未决有效期语义'),
'expiry_semantics_review_required':('Требуется уточнить смысл маркированного срока','Expiry label semantics need review','需审核有效期标签语义'),
}
TOKENS={
'expiry_only':('Только сроки годности','Expiry records only','仅有效期记录'),
'temperature_only':('Только температурный журнал','Temperature log only','仅温度日志'),
'expiry_semantics_unresolved':('Смысл маркированного срока не установлен','Expiry label semantics unresolved','有效期标签语义未决'),
'humidity_applicability_unknown':('Применимость контроля влажности не установлена','Humidity monitoring applicability unknown','湿度监测适用性未知'),
'expiry_records_only_no_batch_fitness_decision':('Только записи сроков годности без решения о пригодности серии','Expiry records only without batch fitness decision','仅有效期记录不决定批次适用性'),
'temperature_observations_only_no_batch_fitness_decision':('Только температурные наблюдения без решения о пригодности серии','Temperature observations only without batch fitness decision','仅温度观察不决定批次适用性'),
'unresolved':('Не установлено','Unresolved','未确定'),
}
TITLES={
'expiry_list':('Список маркированных сроков годности','Labelled expiry inventory','标签有效期清单'),
'temp_log':('Журнал наблюдений температуры','Temperature observation log','温度观察日志'),
}
BOUNDS=('as_of','input_sha256','assisted_draft','analysis_only','external_network_used','human_review_required','source_semantics_verified','current_legal_applicability_verified','external_actions','dispensing_performed','formulation_changed','batch_released','report_submitted','qualification_granted')

def label(key,language):return tr(FIELDS[key],language) if key in FIELDS else field_label(key,language)
def value(item,language,key=''):
    if item is None:
        if key in ('exclusive_expiry','expired_at_observation','within_alert_horizon','excursion_observed','actual_excursion_duration_minutes'):return token('not_established',language)
        return UI[language]['missing']
    if type(item) is bool:return UI[language]['yes'] if item else UI[language]['no']
    if isinstance(item,str) and key in LITERAL_FIELDS:return display_text(item)
    return display_text(tr(TOKENS[item],language) if isinstance(item,str) and item in TOKENS else token(str(item),language))

def flat(item,language,prefix='',key=''):
    rows=[]
    if isinstance(item,dict):
        for k,v in item.items():rows.extend(flat(v,language,(prefix+' / ' if prefix else '')+label(k,language),k))
        if not item:return [[prefix,UI[language]['missing']]]
    elif isinstance(item,list):
        for index,v in enumerate(item,1):rows.extend(flat(v,language,prefix+' / '+str(index),key))
        if not item:return [[prefix,UI[language]['none']]]
    else:rows.append([prefix,value(item,language,key)])
    return rows

def section(title,data,language):return dict(title=tr(title,language),rows=flat(data,language),paragraphs=[])

def grid(title,records,keys,language):
    return dict(title=tr(title,language),columns=[label(k,language) for k in keys],rows=[[value(r.get(k),language,k) for k in keys] for r in records],paragraphs=[] if records else [UI[language]['none']])

def content(result,language):
    expiry=result['mode']=='expiry_only'
    mode_notice=tr((
      'Проверка сроков использует маркировку и выбранный момент оценки. Температурный журнал и инструкция хранения для этой задачи не требуются; фактическое качество серии не устанавливается.',
      'Expiry review uses the label and selected observation timestamp. This task does not require a temperature log or storage instruction; actual batch quality is not established.',
      '有效期审核使用标签和所选评估时刻。此任务不需要温度日志或储存说明书，也不确定批次实际质量。'),language) if expiry else tr((
      'В журнале приведены только предоставленные температурные измерения. Измерения влажности не выдумываются. Применимость контроля влажности показана отдельно; неизвестная применимость остаётся открытым вопросом.',
      'This log contains only supplied temperature readings. Humidity measurements are not fabricated. Humidity monitoring applicability is shown separately; unknown applicability remains an open question.',
      '本日志仅列所提供温度读数，不编造湿度测量。湿度监测适用性单独显示；未知适用性保留为未决问题。'),language)
    out=[dict(title=UI[language]['summary'],paragraphs=[mode_notice,UI[language]['advice']],rows=flat({k:result[k] for k in ('mode','decision_scope','observed_at','timezone_offset','location','responsible','zones') if k in result},language))]
    if not expiry:
        out.append(section(('Основание температурного контроля','Temperature monitoring basis','温度监测依据'),result['instruction'],language))
        out.append(grid(('Предоставленные измерения','Supplied readings','提供的读数'),result['readings'],('timestamp','temperature','temperature_outside','source_reference'),language))
        humidity=tr(('Контроль влажности не применяется по выбранным данным. Числовых измерений влажности в этом журнале нет.','Humidity monitoring is not applicable according to the selected data. This log contains no numeric humidity readings.','根据所选资料不适用湿度监测，本日志无湿度数值读数。'),language) if result['humidity_applicability']=='not_applicable' else tr(('Применимость контроля влажности неизвестна. Требуется уточнение источника; отсутствие измерений не означает нулевую влажность или выполнение контроля.','Humidity monitoring applicability is unknown. Clarify the source; missing readings mean neither zero humidity nor completed monitoring.','湿度监测适用性未知，须澄清来源；缺少读数不表示湿度为零或已完成监测。'),language)
        out.append(dict(title=label('humidity_applicability',language),paragraphs=[],rows=[[UI[language]['details'],humidity]]))
        out.append(section(('Интервалы наблюдений','Observation intervals','观察间隔'),{'segments':result['segments'],'actual_excursion_duration_minutes':result['actual_excursion_duration_minutes'],'interpolation_used':result['interpolation_used']},language))
    if result.get('expiry_check_performed'):
        out.append(section(('Горизонт предупреждения','Warning horizon','预警期间'),{'expiry_alert_days':result['expiry_alert_days']},language))
        out.append(grid(('Маркированные сроки и источники','Labelled expiry and sources','标签有效期及来源'),result['expiry_rows'],('id','label_value','semantics','source_reference'),language))
        out.append(grid(('Сопоставление на выбранный момент','Comparison at selected timestamp','所选时刻比较'),result['expiry_rows'],('id','exclusive_expiry','expired_at_observation','within_alert_horizon','quarantine_review_required'),language))
        out.append(section(('Вопросы толкования маркировки','Expiry label interpretation questions','有效期标签解释问题'),{'expiry_semantics_gaps':result['expiry_semantics_gaps'],'expiry_semantics_review_required':[{'id':r['id'],'expiry_semantics_review_required':r['expiry_semantics_review_required']} for r in result['expiry_rows']]},language))
    out.append(section(('Пробелы и границы выполненных проверок','Gaps and completed check scope','缺口及已完成核查范围'),{k:result[k] for k in ('gaps','rule_review_gaps','temperature_check_performed','humidity_check_performed','expiry_check_performed','excursion_observed','quarantine_review_required') if k in result},language))
    out.append(dict(title=UI[language]['bounds'],paragraphs=[UI[language]['disclaimer_note']],rows=flat({k:result[k] for k in BOUNDS if k in result},language)))
    return out

def render_branch(result,language,review_evidence):
    from .artifacts import _presentation
    artifact='expiry_list' if result['mode']=='expiry_only' else 'temp_log'
    title=tr(TITLES[artifact],language);sections=content(result,language)+extra_sections(review_evidence,language)
    return {artifact+'.xlsx':xlsx_bytes(title,sections,language,review_evidence),artifact+'.pdf':pdf_bytes(title,_presentation(sections,language),language,review_evidence)}

"""Pure locally rebound pharmacist draft artifacts; no network or subprocesses."""
import json
from .artifact_labels import UI,TITLES,LANGUAGES,tr,field_label
from .artifact_formatting import snapshot,flat,extra_sections,docx_bytes,pdf_bytes,xlsx_bytes,display_text,intro
from copy import deepcopy
from decimal import Decimal,localcontext,Context
import re

# Every original document identity and section is kept. Paths follow actual nested
# subject outputs instead of placing the useful data in a generic appendix.
SECTIONS={
'rx_dispensing':{
'rx_check':[
 (('Форма бланка','Prescription form','处方表格'),('prescription.form','prescription.channel','prescription.category','selected_rule.forms','selected_rule.channels')),
 (('Реквизиты','Required fields','必填项'),('prescription','selected_rule.required_fields','missing_fields')),
 (('Срок действия','Validity period','有效期间'),('prescription.issue_date','conditional_valid_through','validity_mode','selected_rule.valid_days','selected_rule.validity_count_issue_day')),
 (('Количество','Quantity','数量'),('prescription.quantity','prescription.quantity_unit','requested_quantity','selected_rule.max_quantity')),
 (('Условия отпуска по инструкции','Selected dispensing conditions','所选发药条件'),('prescription.inpatient_only','prescription.pku','prescription.benefit','selected_rule')),
 (('Решение провизора','Pharmacist decision pending','待药师决定'),('findings','decision_scope'))],
'deferred_log':[
 (('Дата обращения','Request date','申请日期'),('contact_date','deferred.start_date')),
 (('Рецепт','Prescription','处方'),('prescription_id','prescription')),
 (('Препарат','Medicine','药品'),('prescription.product','prescription.drug','prescription.name')),
 (('Условный срок по выбранному правилу','Conditional deadline under selected rule','所选规则下条件期限'),('deferred',)),
 (('Дата отпуска','Actual dispensing date','实际发药日期'),('dispensing_date',))]},
'mdlp_marking':{'mdlp_discrepancy':[
 (('УПД и операция','Transfer document and operation','交接文件及操作'),('operation','source_reference','snapshot_date','snapshot_age_days')),
 (('Код маркировки','Marking code','标识代码'),('expected','actual')),
 (('Серия','Batch','批号'),('expected.series','actual.series')),
 (('Факт','Observed discrepancies','观察差异'),('discrepancies',)),
 (('Статус в МДЛП','Supplied MDLP status','所供MDLP状态'),('expected.supplied_status','expected.status_reference','actual.supplied_status','actual.status_reference')),
 (('Действие','Action for authorised reviewer','授权人员后续操作'),('next_steps',))]},
'acceptance_control':{'acceptance_act':[
 (('Поставка','Delivery','供货'),('items.id','items.name','items.registration_number','items.form','items.strength','items.series','items.transport','items.expiry','items.expired_on_analysis_date')),
 (('Описание','Description','描述'),('items.checks.description',)),
 (('Упаковка','Packaging','包装'),('items.checks.packaging',)),
 (('Маркировка','Labelling','标签'),('items.checks.marking',)),
 (('Документы','Documents','文件'),('items.checks.documents','items.evidence_gaps')),
 (('Серии на изъятие','Selected withdrawal snapshot review','所选撤回快照核查'),('items.withdrawal_status','items.withdrawal_matches','snapshot_date','snapshot_age_days','snapshot_coverage','source_reference')),
 (('Решение','Decision pending','待决定'),('items.release_decision','items.temperature_result','responsible','context_gaps','next_steps'))]},
'storage_quality':{
'storage_sop':[
 (('Ответственные','Responsible persons','责任人'),('responsible',)),
 (('Зоны хранения и карантин','Storage and quarantine zones','储存与隔离区'),('zones','quarantine_review_required')),
 (('Мониторинг температуры и влажности','Temperature and humidity monitoring','温湿度监测'),('instruction','timezone_offset','readings','segments')),
 (('Действия при отклонении','Excursion review actions','超限审核措施'),('excursion_observed','gaps','rule_review_gaps','actual_excursion_duration_minutes','interpolation_used','decision_scope')),
 (('Сроки годности','Expiry dates','有效期'),('expiry_rows',))],
'temp_log':[
 (('Дата и время','Date and time','日期与时间'),('readings.timestamp','timezone_offset')),
 (('Помещение или холодильник','Room or refrigerator','房间或冷藏设备'),('location',)),
 (('Температура','Temperature','温度'),('readings.temperature','readings.temperature_outside','instruction.temperature_min','instruction.temperature_max')),
 (('Влажность','Humidity','湿度'),('readings.humidity','readings.humidity_outside','instruction.humidity_min','instruction.humidity_max')),
 (('Отклонение','Excursion and observation gaps','超限及观察间隔'),('segments','gaps','actual_excursion_duration_minutes','interpolation_used')),
 (('Подпись','Actual signature pending','待实际签名'),('signature',))]},
'drug_info':{'drug_info_note':[
 (('МНН и торговое название','Active ingredient and trade name','活性成分及商品名'),('medicines.id','medicines.trade_name','medicines.inn','medicines.form','medicines.strength','ingredient_duplicates')),
 (('РУ и дата инструкции','Registration and instruction date','注册及说明书日期'),('medicines.registration_number','medicines.instruction')),
 (('Противопоказания','Contraindications','禁忌'),('medicines.selected_claims@contraindications','medicines.missing_topics')),
 (('Взаимодействия','Interactions','相互作用'),('medicines.selected_claims@interactions','documented_interactions','pairs_without_selected_interaction')),
 (('Условия отпуска','Dispensing conditions','发药条件'),('medicines.selected_claims@dispensing',)),
 (('Источник','Source','来源'),('medicines.instruction','medicines.selected_claims','next_steps'))]},
'pharmacovigilance':{'adr_report':[
 (('Препарат и серия','Medicine and batch','药品及批号'),('draft_case.suspected_drug',)),
 (('Реакция','Reaction','反应'),('draft_case.patient','draft_case.reaction','draft_case.seriousness','causal_link','minimum_case_gaps','completeness_gaps')),
 (('Хронология','Chronology','时间线'),('chronology','chronology_conflicts','draft_case.awareness_date','draft_case.ongoing','candidate_deadline','deadline_overdue_at_as_of','deadline_basis','selected_reporting_rule')),
 (('Исход','Outcome','结局'),('draft_case.outcome',)),
 (('Сопутствующие ЛП','Concomitant medicines','合并用药'),('draft_case.concomitants',)),
 (('Сообщивший','Reporter','报告人'),('draft_case.reporter','reporter_scope','selected_form','next_steps'))]},
'compounding':{'ppk':[
 (('Номер','Record number','记录号'),('number',)),
 (('Пропись','Original prescription formulation','原处方配方'),('prescription_text','ppk_text')),
 (('Ингредиенты и количества','Ingredients and quantities','成分与数量'),('ingredient_checks','control_rule')),
 (('Общая масса или объём','Total mass or volume','总质量或体积'),('prescribed_total','recorded_total','final_unit','final_absolute_difference','final_relative_difference','final_exceeds_selected_tolerance','ingredient_sum_checks')),
 (('Подписи изготовившего и проверившего','Actual preparer and reviewer signatures pending','待配制及审核人员实际签名'),('signatures','decision_scope'))]},
'zhnvlp_pricing':{'price_check':[
 (('Препарат','Medicine','药品'),('item_id','prices.item_id','prices.price_date')),
 (('Цена в реестре','Registered price','登记价格'),('prices.registered_cap_net','prices.manufacturer_actual_net')),
 (('Закупочная цена','Purchase price','采购价格'),('prices.purchase_net','prices.purchase_vat','prices.purchase_gross')),
 (('Надбавка региона','Selected regional markup','所选地区加价'),('regional_rule','tax_rule','price_components')),
 (('Условная предельная розничная цена','Conditional retail price ceiling','条件零售价格上限'),('conditional_ceiling_unrounded','conditional_ceiling_display','rounding')),
 (('Ценник','Proposed price label','拟议标价'),('prices.proposed_gross','proposed_minus_ceiling','findings','decision_scope'))]},
'gpp_sop':{
'gpp_sop_doc':[
 (('Цель','Purpose','目的'),('draft_plan.purpose','draft_plan.authorship','organization_scope')),
 (('Область','Scope','范围'),('draft_plan.scope','required_controls.scope')),
 (('Ответственные','Responsible persons','责任人'),('draft_plan.owner','document_inventory.owner','corrective_actions.owner')),
 (('Порядок','Procedure draft and selected requirements','程序草稿及所选要求'),('draft_plan.procedure','required_controls','document_inventory.selected_controls','corrective_actions.action','missing_control_documents')),
 (('Записи','Records','记录'),('draft_plan.records','document_inventory.records','corrective_actions.records')),
 (('Пересмотр','Revision','修订'),('draft_plan.version','draft_plan.review_date','document_inventory.review_date','document_inventory.review_due','corrective_actions.review_date','selected_rule','additional_rules','inventory_topics_without_selected_requirement','next_steps'))],
'self_inspection':[
 (('Требование','Requirement','要求'),('required_controls',)),
 (('Документ','Document','文件'),('document_inventory',)),
 (('Факт','Observed fact','观察事实'),('document_inventory.selected_controls',)),
 (('Несоответствие','Gap','缺口'),('missing_control_documents','corrective_actions.discrepancy','inventory_topics_without_selected_requirement')),
 (('Корректирующее действие','Corrective action','纠正措施'),('corrective_actions','missing_corrective_actions')),
 (('Срок','Due date','截止日期'),('corrective_actions.due_date','corrective_actions.overdue_at_as_of','draft_plan.review_date'))]},
'nmo_pharma':{'pharma_activity_report':[
 (('Сведения о специалисте','Specialist information','专业人员信息'),('person','accreditation','qualification_rule')),
 (('Место работы','Workplace','工作单位'),('workplace','person.workplace')),
 (('Описание деятельности','Activity description','活动描述'),('activities','report','missing_training_specialties','delivery_modes_checked_against_selected_rule')),
 (('ЗЕТ и часы по документам','Documented credits and hours','有证明的学分与学时'),('documented_zet','documented_total_hours','documented_pk_hours','documented_other_nmo_hours','total_hours_gap','pk_hours_gap','zet_not_equated_to_hours','distance_mode_not_automatically_disqualified')),
 (('Согласование','Approval pending','待审批'),('findings','conditional_submission_target','submission_target_kind','decision_scope'))]},
}
XLSX={'deferred_log','mdlp_discrepancy','temp_log','price_check','self_inspection'}
MD={'rx_check','drug_info_note','ppk'}
BOUNDS=('as_of','jurisdiction','status','status_codes','input_sha256','assisted_draft','analysis_only','private','external_network_used','human_review_required','source_semantics_verified','current_legal_applicability_verified','external_actions','dispensing_performed','formulation_changed','batch_released','report_submitted','qualification_granted','signature_applied')

def _path(value,path):
    if not path:return value,True
    key,*rest=path.split('.')
    if isinstance(value,list):
        rows=[]
        for index,item in enumerate(value,1):
            selected,present=_path(item,path)
            if present:rows.append({'record_index':index,path.split('.')[-1].split('@')[0]:selected})
        return rows,bool(rows)
    if not isinstance(value,dict):return None,False
    if '@' in key:
        key,topic=key.split('@',1)
        if key not in value:return None,False
        selected=[item for item in value[key] if item.get('topic')==topic]
        return selected,True
    if key not in value:return None,False
    return _path(value[key],'.'.join(rest))

def _content(function,artifact,result,language):
    sections=[];used=set()
    sections.append(dict(title=UI[language]['summary'],paragraphs=[UI[language]['advice']],rows=flat({k:result[k] for k in ('findings','status_codes','decision_scope','next_steps') if k in result},language)))
    for title,paths in SECTIONS[function][artifact]:
        selected={}
        for path in paths:
            value,present=_path(result,path)
            if present:selected[path]=value;used.add(path.split('.')[0])
        sections.append(dict(title=tr(title,language),paragraphs=[] if selected else [UI[language]['missing']],rows=flat(selected,language) if selected else [],source_paths=list(paths),selected_paths=list(selected)))
    # Any genuinely new subject field remains visible, while audits detect drift.
    used.update(path.split('.')[0] for specs in SECTIONS[function].values() for title,paths in specs for path in paths)
    remaining={k:v for k,v in result.items() if k not in used and k not in BOUNDS and k not in ('function','findings','next_steps','decision_scope')}
    if remaining:sections.append(dict(title=tr(('Дополнительные сведения','Additional information','补充资料'),language),paragraphs=[],rows=flat(remaining,language),additional_subject_fields=sorted(remaining)))
    sections.append(dict(title=UI[language]['bounds'],paragraphs=[UI[language]['disclaimer_note']],rows=flat({k:result[k] for k in BOUNDS if k in result},language)))
    return sections

def _validate_result(function,result):
    if function not in SECTIONS or type(result) is not dict:raise ValueError('pharmacist_function_result_required')
    authority={'external_actions','signature_applied','submission_performed','qualification_granted','dispensing_performed','formulation_changed','batch_released','report_submitted','dispensing_allowed'}
    def visit(value,depth=0):
        if depth>24:raise ValueError('artifact_nesting_limit')
        if isinstance(value,dict):
            for key,item in value.items():
                if (key in authority or key.endswith(('_verified','_approved','_confirmed','_signed'))) and item is True:raise ValueError('unsupported_final_or_verified_claim:'+key)
                visit(item,depth+1)
        elif isinstance(value,list):
            for item in value:visit(item,depth+1)
    visit(result)

def md_bytes(title,sections,language,review_evidence):
    def safe(v):
        # HTML escaping and backslash punctuation make source text inert Markdown.
        value=display_text(v).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
        import re
        return re.sub(r'([\\`*_{}\[\]()#+.!|>-])',r'\\\1',value)
    lines=['# '+title,'']+[safe(p)+'\n' for p in intro(language,review_evidence)]
    for section in sections:
        lines+=['## '+section['title'],'']+[safe(p)+'\n' for p in section.get('paragraphs',[])]
        for row in section.get('rows',[]):lines+=[' — '.join(safe(v) for v in row),'']
    return ('\n'.join(lines)+'\n').encode('utf8')

def _presentation(sections,language):
    """Readable decimal display; exact results remain in JSON and XLSX."""
    selected=deepcopy(sections);changed=False
    for section in selected:
        for row in section.get('rows',[]):
            for i,value in enumerate(row):
                if isinstance(value,str) and len(value)>18 and re.fullmatch(r'-?\d+\.\d+',value):
                    with localcontext(Context(prec=128)):row[i]=format(Decimal(value).quantize(Decimal('.000001')),'f').rstrip('0').rstrip('.') or '0'
                    changed=True
    if changed:selected[0]['paragraphs'].append(tr(('Длинные десятичные значения в этом представлении округлены до шести знаков. Точные значения сохранены в JSON результата и в книге XLSX когда она предусмотрена.','Long decimal values in this view are rounded to six decimal places. Exact values remain in result JSON and the XLSX workbook where provided.','本视图长小数舍入至六位。精确值保留在结果JSON及适用的XLSX工作簿中。'),language))
    return selected

def render(function,result,language,*,config=None,review_evidence=None):
    if language not in LANGUAGES:raise ValueError('language_invalid')
    result=snapshot(result);review_evidence=snapshot(review_evidence) if review_evidence is not None else None
    _validate_result(function,result)
    if config is None:raise ValueError('artifact_source_config_required')
    from .core import execute
    if snapshot(execute(function,snapshot(config)))!=result:raise ValueError('artifact_result_input_mismatch')
    if review_evidence is not None:
        if type(review_evidence) is not dict:raise ValueError('review_evidence_object_required')
        for key in ('bindings','assumptions'):
            if type(review_evidence.get(key,[])) is not list or any(type(row) is not dict for row in review_evidence.get(key,[])):raise ValueError('review_evidence_rows_required')
    files={'result.json':(json.dumps(dict(function=function,result=result,review_evidence=review_evidence,result_rebound_to_config=True),ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8')}
    if function=='storage_quality' and result.get('mode') in ('expiry_only','temperature_only'):
        from .storage_artifacts import render_branch
        files.update(render_branch(result,language,review_evidence))
        return files
    for artifact in SECTIONS[function]:
        title=tr(TITLES[artifact],language);content=_content(function,artifact,result,language)+extra_sections(review_evidence,language)
        writer=xlsx_bytes if artifact in XLSX else md_bytes if artifact in MD else docx_bytes
        extension='.xlsx' if artifact in XLSX else '.md' if artifact in MD else '.docx'
        files[artifact+extension]=writer(title,content if artifact in XLSX else _presentation(content,language),language,review_evidence)
        files[artifact+'.pdf']=pdf_bytes(title,_presentation(content,language),language,review_evidence)
    return files

"""Readable customs profession artifacts. No filing, signing or official FCS XML claims."""
from decimal import Decimal,localcontext,Context,InvalidOperation
import json
from .artifact_labels import TITLES,SECTIONS,SECTION_TRANSLATIONS,UI,localized_section,field_label,token
from .artifact_formatting import snapshot,flat,extra_sections,docx_bytes,pdf_bytes,xml_bytes,xlsx_bytes


def _take(result,*keys):return {key:result.get(key) for key in keys}

def _summary(function,result,language):
    keys={
      'tnved_classification':('missing_product_documents','preliminary_decision_recommended'),
      'customs_value':('value_rub','candidate_value_rub','method1_supported','method1_issues'),
      'customs_payments':('total_advance_els','duty','excise','vat','customs_fee','special_duties'),
      'declaration':('mismatches','unverified_fields','release_deadline'),
      'non_tariff':('unresolved',),
      'origin':('preference_eligible_preliminary','sufficient_processing'),
      'trade_contract':('amount_rub','bank_registration_required_preliminary','bank_registration_threshold_rub'),
      'post_clearance':('response_deadline',)
    }[function]
    selected=_take(result,*keys)
    if function=='customs_value' and result.get('value_rub') is not None:selected.pop('candidate_value_rub')
    if function=='post_clearance' and result.get('appeal'):
        selected['appeal_deadline']=result['appeal']['deadline']['calculated_deadline']
        if result.get('mode')=='appeal':selected.pop('response_deadline',None)
    for key,value in selected.items():
        if value==[]:
            if key=='method1_issues':selected[key]={'ru':'По заявленным условиям препятствия не отмечены; это не проверка применимости нормы.','en':'No obstacle is recorded under the declared conditions; this does not verify legal applicability.','zh':'按所声明条件未记录障碍；这不证明法规适用性。'}[language]
            else:selected[key]={'ru':'В переданном перечне нет строк; это не подтверждает полноту проверки.','en':'The supplied list has no entries; this does not establish complete coverage.','zh':'所提供列表没有条目；这不证明核查已全面完成。'}[language]
    notes=[]
    if function=='customs_payments':notes.append({'ru':'Утильсбор не рассчитан и не включён в итог. Уточните, применим ли он к товару; для транспорта нужны его параметры и отдельное датированное правило.','en':'Recycling fee is not calculated or included in the total. Determine whether it applies; vehicles need their parameters and a separate dated rule.','zh':'回收费尚未计算，也未计入合计。请确认商品是否适用；车辆需要具体参数及单独的日期明确规则。'}[language])
    return {'title':{'ru':'Результат и следующие действия','en':'Result and next steps','zh':'结果及后续事项'}[language],'paragraphs':notes,'rows':flat(selected,language)}


def _validate_result(function_id,result):
    if function_id not in SECTIONS or type(result) is not dict:raise ValueError('artifact_function_or_result_invalid')
    for key in ('final_classification','final_declaration','payment_submitted','submission_performed','bank_submission_performed','contract_legality_confirmed','legality_conclusion','final_origin_determination','external_actions','user_confirmed','current_rates_verified','current_legal_applicability_verified','source_semantics_verified'):
        if result.get(key) is True:raise ValueError('artifact_unsupported_verified_or_final_claim:'+key)
    if function_id=='customs_payments':
        with localcontext(Context(prec=128)):
            keys=('duty','excise','vat','customs_fee','special_duties','total_advance_els','customs_value_rub','vat_base')
            try:values={key:Decimal(result[key]) for key in keys}
            except (KeyError,ValueError,TypeError,InvalidOperation):raise ValueError('artifact_payment_values_required') from None
            if any(not x.is_finite() or x<0 for x in values.values()):raise ValueError('artifact_payment_values_invalid')
            if sum((values[k] for k in keys[:5]),Decimal(0))!=values['total_advance_els']:raise ValueError('artifact_payment_total_mismatch')
            if values['customs_value_rub']+values['duty']+values['excise']!=values['vat_base']:raise ValueError('artifact_vat_base_mismatch')
    if function_id=='customs_value' and result.get('method1_supported') is False and result.get('value_rub') is not None:raise ValueError('artifact_unsupported_customs_value_claim')


def _content(function_id,artifact_id,result,language):
    u=UI[language]
    if artifact_id=='shipping_docs':
        data=result.get('shipping_documents') or {};keys=('invoice','packing_list','transport','specification','insurance')
        sections=[{'title':localized_section(name,language),'paragraphs':[],'rows':flat(data.get(key),language)} for key,name in zip(keys,SECTIONS[function_id][artifact_id])]
        untyped=result.get('documents') or result.get('g44_documents')
        if untyped:sections.append({'title':u['shipping_untyped'],'paragraphs':[],'rows':flat(untyped,language)})
        return sections
    if function_id=='tnved_classification':
        candidates=result.get('candidates',[])
        values={'Описание товара':result.get('product'),'Кандидаты кодов':[{k:row.get(k) for k in ('code','arguments','impact','status','evidence_refs')} for row in candidates],'Применение ОПИ':[{'code':row.get('code'),'rule_checks':row.get('rule_checks',row.get('opi'))} for row in candidates],'Решения и пояснения':{'official_checks':result.get('official_checks'),'nomenclature':result.get('nomenclature')},'Вывод и риски':_take(result,'final_classification','preliminary_decision_recommended','missing_product_documents','rule_applicability_verified')}
    elif function_id=='customs_value':
        values={'Сделка и стороны':_take(result,'parties','incoterms','incoterms_place','declaration_date'),'Связанность':_take(result,'related_parties','method1_conditions'),'Цена по инвойсу':_take(result,'price_original','currency','fx_rate','fx_nominal','price_source_reference'),'Дополнительные начисления':result.get('additions'),'Вычеты':result.get('deductions'),'Подтверждающие документы':result.get('documents')}
    elif function_id=='customs_payments':
        values={'База':_take(result,'customs_value_rub','customs_value_rub_input','declaration_date','tnved_code','origin_country','quantity','quantity_unit'),'Пошлина':_take(result,'duty','duty_formula','duty_breakdown'),'Акциз':_take(result,'excise','excise_formula','excise_breakdown'),'НДС при ввозе':_take(result,'vat_base','vat_rate_percent','vat','vat_treatment','vat_exemption_basis'),'Таможенный сбор':_take(result,'customs_fee'),'Итог и аванс на ЕЛС':_take(result,'special_duties','special_duties_basis','total_advance_els')}
    elif function_id=='declaration':
        values={'Процедура и стороны':_take(result,'procedure','parties','adjustment_stage'),'Товар: код, описание, вес':_take(result,'tnved_code','description','net_weight_kg'),'Происхождение':result.get('origin_country'),'Стоимость и платежи':_take(result,'customs_value_rub','payments','mismatches','compared_fields','unverified_fields'),'Графа 44: документы':result.get('g44_documents')}
    elif function_id=='non_tariff':values=result.get('blocks',{})
    elif function_id=='origin':
        values={'Сертификат/декларация происхождения':result.get('certificate'),'Критерий происхождения':_take(result,'manufacture_country','currency','criterion','method','criteria_results','heading_changed','sufficient_processing','value_content','non_origin_value','total_material_value','materials'),'Прямая отправка':_take(result,'direct_shipment','preference_conditions'),'Право на преференцию':_take(result,'preference_eligible_preliminary','official_lists_verification_required','rule_applicability_verified','final_origin_determination')}
    elif function_id=='trade_contract':
        if artifact_id=='currency_docs':
            docs=result.get('currency_documents') or {}
            values={'Постановка контракта на учёт (УНК)':dict(_take(result,'bank_registration_required_preliminary','bank_registration_threshold_rub','amount_rub','bank_rule'),document=docs.get('bank_registration')),'Сведения о валютных операциях':dict(_take(result,'direction','amount_original','currency','fx_rate','fx_date'),document=docs.get('currency_operations')),'Справка о подтверждающих документах':docs.get('supporting_documents'),'Сроки репатриации':{'repatriation_dates':result.get('repatriation_dates'),'document':docs.get('repatriation')}}
        else:
            keymap={'Стороны и право':'parties_law','Предмет и спецификации':'subject_specifications','Incoterms 2020':'incoterms','Цена, валюта, оплата':'price_currency_payment','Документы и сроки':'documents_deadlines','Форс-мажор и санкционные оговорки':'force_majeure_sanctions'}
            checks={row.get('topic'):row for row in result.get('clause_checks',[])}
            values={heading:checks.get(key) for heading,key in keymap.items()}
            values['Цена, валюта, оплата']={'clause_checks':values['Цена, валюта, оплата'],**_take(result,'amount_original','currency','fx_rate','amount_rub','fx_scenarios')}
    elif function_id=='post_clearance':
        documents=result.get('documents',[])
        values={'Реквизиты запроса или решения':_take(result,'request','received_date','response_deadline','deadline_rule','deadline_method'),'Перечень документов':[{k:r.get(k) for k in ('requested','status','available_reference','replacement_plan')} for r in documents],'Пояснения по пунктам':[{k:r.get(k) for k in ('requested','explanation','replacement_plan')} for r in documents],'Правовое обоснование':result.get('legal_arguments'),'Приложения':[r.get('available_reference') for r in documents if r.get('available_reference')]}
        if result.get('mode')=='appeal':
            appeal=result['appeal']
            values={'Реквизиты запроса или решения':{'request':result['request'],'challenged_decision':appeal['challenged_decision'],'route':appeal['route']},'Перечень документов':appeal['document_refs'],'Пояснения по пунктам':appeal['demands'],'Правовое обоснование':appeal['grounds'],'Приложения':appeal['document_refs']}
    else:raise ValueError('unknown_artifact')
    sections=[_summary(function_id,result,language)]+[{'title':localized_section(name,language),'paragraphs':[],'rows':flat(values.get(name),language)} for name in SECTIONS[function_id][artifact_id]]
    if function_id=='customs_value':
        for section,name in zip(sections[1:],SECTIONS[function_id][artifact_id]):
            if name not in ('Дополнительные начисления','Вычеты'):continue
            entries=result.get('additions' if name=='Дополнительные начисления' else 'deductions',[])
            section['rows']=[]
            for entry in entries:
                heading=token(entry['kind'],language)+' ['+entry['id']+']'
                shown='; '.join([str(entry['original'])+' '+entry['currency'],field_label('fx_rate',language)+': '+entry['fx_rate']+' RUB / '+entry['fx_nominal']+' '+entry['currency'],field_label('rub',language)+': '+entry['rub']+' RUB',field_label('applied',language)+': '+UI[language]['yes' if entry['applied'] else 'no'],field_label('source_reference',language)+': '+entry['source_reference']])
                section['rows'].append([heading,shown])
            if not entries:section['rows']=flat([],language)
    if function_id=='declaration' and result.get('correction'):
        sections.append({'title':{'ru':'Проект корректировки декларации','en':'Declaration amendment draft','zh':'报关单更正草案'}[language],'paragraphs':[],'rows':flat(result['correction'],language)})
    if function_id=='post_clearance' and result.get('appeal'):
        sections.append({'title':{'ru':'Проект жалобы','en':'Appeal draft','zh':'申诉草案'}[language],'paragraphs':[],'rows':flat(result['appeal'],language)})
    extra={}
    if function_id=='customs_value':extra={u['total_value']:result.get('value_rub'),u['conditional_value']:result.get('candidate_value_rub'),**_take(result,'method1_supported','method1_issues','method_source','fx_scenarios')}
    elif function_id=='customs_payments':extra=_take(result,'breakdown','rate_checks','rounding','limitations')
    elif function_id=='declaration':extra=_take(result,'release_deadline','registration_timestamp_required','release_rule')
    elif function_id=='non_tariff':extra=_take(result,'declared_features','unresolved','end_recipient','legality_conclusion')
    elif function_id=='post_clearance' and result.get('penalty') is not None:extra=_take(result,'penalty')
    if extra:sections.append({'title':u['calculation'],'paragraphs':[u['deadline_notice']] if function_id in ('declaration','post_clearance') else [],'rows':flat(extra,language)})
    return sections


def render(function_id,result,language,*,config=None,review_evidence=None):
    """Legacy 3-arg call retained. Host supplies config for exact result rebinding."""
    if language not in ('ru','en','zh'):raise ValueError('language_invalid')
    result=snapshot(result);review_evidence=snapshot(review_evidence) if review_evidence is not None else None
    _validate_result(function_id,result)
    if config is not None:
        from .core import execute
        if snapshot(execute(function_id,snapshot(config)))!=result:raise ValueError('artifact_result_input_mismatch')
    if review_evidence is not None:
        if type(review_evidence) is not dict or type(review_evidence.get('bindings',[])) is not list or type(review_evidence.get('assumptions',[])) is not list:raise ValueError('artifact_review_evidence_invalid')
        if any(type(row) is not dict for row in review_evidence.get('bindings',[])+review_evidence.get('assumptions',[])):raise ValueError('artifact_review_evidence_row_invalid')
    files={'result.json':(json.dumps({'function':function_id,'result':result,'review_evidence':review_evidence,'result_rebound_to_config':config is not None},ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')}
    for artifact_id in SECTIONS[function_id]:
        title_key=artifact_id if artifact_id in ('shipping_docs','currency_docs') else function_id
        title=TITLES[title_key][language];sections=_content(function_id,artifact_id,result,language)+extra_sections(review_evidence,language)
        if function_id=='post_clearance' and result.get('mode')=='appeal':
            title={'ru':'Проект жалобы по таможенному решению','en':'Draft appeal against a customs decision','zh':'海关决定申诉草案'}[language]
        if artifact_id in ('dts','dt'):
            files[artifact_id+'.xml']=xml_bytes(title,sections,language,function_id,artifact_id,review_evidence)
            files[artifact_id+'.pdf']=pdf_bytes(title,sections,language,review_evidence)
        elif artifact_id=='payments_calc':files[artifact_id+'.xlsx']=xlsx_bytes(title,sections,language,review_evidence)
        elif artifact_id in ('shipping_docs','origin_pack','currency_docs'):files[artifact_id+'.pdf']=pdf_bytes(title,sections,language,review_evidence)
        else:files[artifact_id+'.docx']=docx_bytes(title,sections,language,review_evidence)
    return files

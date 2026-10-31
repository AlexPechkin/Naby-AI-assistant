"""Tax-specific readable draft routing. Writers are inert and source-scoped.

Each actual result leaf is routed to a named logical section, including explicit
None/False/zero states. Repeated identical selected rule objects are indexed once
per document with all occurrence paths retained for audit, rather than dumped as
JSON or repeated on every line.
"""
from pathlib import Path
from decimal import Decimal,InvalidOperation
import json
from .artifact_labels import UI,FIELDS,TOKENS,field_label,token,tr
from .artifact_formatting import snapshot,display_text,docx_bytes,pdf_bytes,xlsx_bytes,extra_sections

ROOT=Path(__file__).resolve().parent
TEMPLATES=json.loads((ROOT/'artifact_templates.json').read_text(encoding='utf-8'))
ROUTES={
'law_monitoring':['change_memo'],'regime_choice':['regime_comparison'],'transaction_structuring':['tax_opinion'],
'tax_audit_support':['audit_roadmap','request_reply'],'objections_appeal':['objections','appeal'],
'penalties_mitigation':['mitigation_letter'],'individual_3ndfl':['ndfl_3_draft'],
'tax_accounting_method':['tax_policy'],'ens_dispute':['ens_claim'],'client_engagement':['engagement_letter']}
COMMON=set('as_of jurisdiction mode function analysis_only assisted_draft draft_status arithmetic_precision input_sha256 source_semantics_verified current_legal_applicability_verified external_actions methodology_approved model_certified report_certified signature_applied submission_performed physical_work_authorized declaration_submitted taxes_paid documents_signed case_submitted representation_performed legal_applicability_certified tax_authority_decision_verified counterparty_registry_checked client_right_or_eligibility_confirmed calendar_legally_verified data_sent_external signature_verified registry_submitted published source_semantics_established current_legal_chain_established legal_eligibility_granted filing_performed payment_performed legal_applicability_established network_used official_declaration_XML_generated refund_authorized complete_rule_chain_established'.split())
ROOTS={
'law_monitoring':set('client applicability_date documents changes source_conflicts topic_comparison weekly_update_status questions evidence_gaps'.split()),
'regime_choice':set('client_context entity_type scenarios comparison_span_equal comparison_period_coverage_equal automatic_regime_selected comparison_limitations question required_inputs calculation gaps'.split()),
'transaction_structuring':set('question facts business_purpose authored_conclusion counterparties VAT direct_tax withholding risk_reviews required_inputs calculation gaps'.split()),
'tax_audit_support':set('context events audit_kind audit_record request_reply questions evidence_gaps'.split()),
'objections_appeal':set('context events act_record decision_record episodes appeal_draft questions evidence_gaps'.split()),
'penalties_mitigation':set('context events violation fine penalty_ledger circumstances request_draft questions evidence_gaps'.split()),
'individual_3ndfl':set('tax_year residency groups deduction_pools foreign_tax_credits tax_total foreign_tax_credit_applied withheld domestic_advance_paid signed_settlement potential_amount_due potential_refund filing_review documents question required_inputs calculation gaps'.split()),
'tax_accounting_method':set('client policy_period general_provisions documents choices selected_required_topics missing_selected_topics vat_cost_share registers branch_method change_timing_scope questions evidence_gaps'.split()),
'ens_dispute':set('context events ledger claim penalty_ledger refund_interest request_draft questions evidence_gaps'.split()),
'client_engagement':set('brief parties documents clauses selected_required_topics missing_selected_topics clause_topic_conflicts fee representation_date power_review quality_checks contract_confidentiality_scope professional_care_scope contract_validity_established questions evidence_gaps'.split())}
SOURCE_SECTION={'change_memo':4,'regime_comparison':5,'tax_opinion':2,'audit_roadmap':1,'request_reply':3,'objections':2,'appeal':2,'mitigation_letter':2,'ndfl_3_draft':5,'tax_policy':0,'ens_claim':1,'engagement_letter':0}
OPTIONAL_BRANCHES=set('calculation VAT direct_tax withholding property cadastral_floor fine penalty_ledger refund_interest request_reply act_record decision_record audit_record appeal_draft repeat mitigation selected_exemption exemption_review extension rounding cap filing_review criteria_basis temporal_basis selected_start_constraint ledger claim vat_cost_share'.split())
CONTROLLED=set('mode function draft_status kind document_kind authorship trigger role form status selected_status state selected_status calculation_status start_review rule_temporal_status temporal_status weekly_update_status change_timing_scope scope_comparison contract_confidentiality_scope professional_care_scope review_status condition_results questions required_inputs comparison_limitations arithmetic_precision period_kind entity_type record_kind treatment exemption_treatment other_exemption_conditions anniversary_policy cost_method recognition_method classification evidence_status expenses_contribution_basis allocation_model attribution_model prorating_model balance_interpretation model mental_state provided_mental_state temporal_state count_start roll duration_unit operator comparison field price_basis tax_treatment amount_basis buyer_type method scope basis balance_basis unit category'.split())
LITERALS=set('id name source_reference source_references date_source_reference reference fact_id source_sha256 segment_id pointer quote excerpt text citation url edition document_identity clause value description rationale title purpose responsibility procedure publication_date effective_from effective_to observed_date observed_at as_of selection_date date input_sha256 sha256 owner tax_year received acquired sold event_date recognition_date record_identity case_number court identifier principal representative valid_from valid_to issued_at recorded_at bank_details draft_text draft_action draft_analysis authored_conclusion conditions_review proposed_procedure proposed_follow_up cost_scope_note analysis summary draft_conclusion business_purpose scope_analysis reason consequences check question proposed_action history_group provided_status recognition_rationale draft_notes ground grounds requests recipient violated_rights pretrial_review extension_or_refusal'.split())


def leaves(value,path=''):
    if type(value)is dict and value:
        for key,item in value.items():yield from leaves(item,path+'/'+key.replace('~','~0').replace('/','~1'))
    elif type(value)is list and value:
        for i,item in enumerate(value):yield from leaves(item,path+'/'+str(i))
    else:yield path,value


def pointer(value,path):
    if not path:return value
    for part in path.lstrip('/').split('/'):
        part=part.replace('~1','/').replace('~0','~')
        value=value[int(part)] if type(value)is list else value[part]
    return value


def is_basis(value):
    return type(value)is dict and {'document_identity','clause','excerpt','source_reference','publication_date','effective_from','effective_to'}<=set(value)


def _ancestor(result,path,key):
    parts=path.strip('/').split('/')
    for i in range(len(parts)-1,-1,-1):
        if parts[i]==key:
            target=pointer(result,'/'+'/'.join(parts[:i+1]))
            if type(target)is list and i+1<len(parts):target=target[int(parts[i+1])]
            return target
    return None


def path_label(path,result,language):
    parts=path.lstrip('/').split('/');labels=[];anchors=[];value=result;previous=''
    for part in parts:
        part=part.replace('~1','/').replace('~0','~')
        if type(value)is list:
            item=value[int(part)]
            anchors.append(str(item.get('id',int(part)+1)) if type(item)is dict else str(int(part)+1));value=item
        elif type(value)is dict:
            labels.append(part if previous=='missing_days_by_obligation' else field_label(part,language))
            value=value.get(part);previous=part
        else:labels.append(field_label(part,language))
    # Section headings already provide the major workflow context. Keep useful
    # record IDs and at most the last two descriptive labels, rather than a long
    # repeated technical JSON pointer on every human row.
    return ' / '.join(anchors+labels[-2:])


def shown(value,path,result,language):
    u=UI[language];parts=path.split('/');key=parts[-1];parent=pointer(result,'/'.join(parts[:-1])) if len(parts)>2 else result
    if value is None:
        if key in ('effective_from','effective_to','publication_date','edition','issued_at','valid_from','valid_to'):return u['unknown']
        if key=='selected_client_conditions_match' or 'condition_results'in parts:return u['unknown']
        if key in ('base_candidate_date','candidate_before_roll','candidate_deadline'):return u['not_computed']
        if key=='maximum_divisor':return tr(('Верхняя граница делителя не задана в выбранной модели','No upper divisor bound is supplied in the selected model','所选模型未给出除数上限'),language)
        if key=='selected_positive_balance':return u['not_computed'] if type(parent)is dict and 'requested_amount'in parent else u['not_requested']
        if key=='audit_kind':return u['missing'] if any(x.get('role')in ('desk_vat_end','desk_other_end','field_audit_end') for x in result.get('events',[])) else u['not_used']
        if key=='signed_VAT_after_selected_rounding':return u['rounding_not_selected']
        if key=='exemption_basis' and type(parent)is dict:return u['property_exemption_basis_separate'] if parent.get('treatment')=='property_sale' else u['not_requested']
        if key=='received' and type(parent)is dict and parent.get('treatment')=='property_sale':return u['income_date_in_property']
        if key in ('selected_filing_deadline','selected_payment_deadline') and type(parent)is dict:
            if parent.get('case')=='deduction_only':return u['deduction_only_deadline_not_selected']
            if parent.get('case')=='unknown':return u['unknown']
        if key=='automatic_regime_selected':return u['automatic_choice_not_made']
        if key=='upper' and 'scale_steps' in parts:return u['open_upper']
        if key=='conditional_signed_accrual_total':return u['periods_not_summed']
        if key=='recognized_expenses':return u['expenses_not_used']
        if key=='rounded_amount':return u['rounding_not_selected']
        if key in ('conditional_after_selected_exemption','final_conditional_amount'):return u['exemption_temporal_unknown']
        if key=='conditional_total':return u['incomplete_accrual']
        if key in ('share','within_selected_threshold') and 'vat_cost_share'in parts:return u['undefined']
        if key in ('rate','net_amount','gross_amount') and type(parent)is dict and parent.get('amount_basis')=='vat_only':return u['VAT_only_not_derived']
        if key=='advance_id' and type(parent)is dict and parent.get('kind')!='advance_offset':return u['not_used']
        if key=='VAT_period_matches_tax_span':return u['comparison_unselected']
        if key in ('within_selected_positive_balance','within_declared_inclusive_window'):return u['not_computed']
        if key=='selected_mitigation_divisor':return u['not_requested']
        if key=='service' and type(parent)is dict and parent.get('trigger') not in ('requirement_received','act_received','decision_served'):return u['service_not_needed']
        if key=='power_review':return u['missing'] if 'power_of_attorney'in result.get('selected_required_topics',[]) else u['not_requested']
        if key=='fee':return u['not_requested']
        if key in OPTIONAL_BRANCHES:return u['not_requested']
        return u['missing']
    if type(value)is bool:return u['yes'] if value else u['no']
    if type(value)is dict:
        if key=='missing_days_by_obligation':
            ledger=_ancestor(result,path,'penalty_ledger') or _ancestor(result,path,'refund_interest')
            return u['no_missing_selected_days'] if ledger and ledger.get('periods') else u['no_obligations_selected']
        return u['missing']
    if type(value)is list:
        if key in ('gaps','evidence_gaps'):return u['not_assessed_questions'] if result.get('mode')=='questions' else u['no_additional_issues']
        if key=='missing_selected_topics':return u['no_missing_review_topics'] if result.get('selected_required_topics') else u['review_topics_not_selected']
        if key=='source_conflicts':return u['not_assessed_questions'] if result.get('mode')=='questions' else u['no_source_conflict_records']
        if key=='clause_topic_conflicts':return u['no_duplicate_clause_topics'] if result.get('clauses') else u['clauses_not_selected']
        if key=='topic_comparison':return u['no_multiple_selected_positions'] if result.get('changes') else u['not_assessed_questions'] if result.get('mode')=='questions' else u['change_comparison_not_performed']
        if key=='unprovided_period_intervals':return u['no_unprovided_between_periods']
        if key=='repeated_external_record_identities':return u['no_repeated_external_ids'] if type(parent)is dict and parent.get('entries') else u['ledger_entries_not_selected']
        if key=='selected_ids_missing':return u['selected_power_ids_present'] if type(parent)is dict and parent.get('requested_power_ids') else u['power_comparison_not_selected']
        return u['none']
    if type(value)is not str:return str(value)
    if key=='unit':return display_text(token(value,language,required=True)) if value in ('calendar_month','calendar_day','working_day') else display_text(value)
    if any(x in parts for x in ('gaps','evidence_gaps')) and type(parent)is list:return display_text(token(value,language,required=True))
    if key in ('eligibility_status','audit_kind','coverage_status','approval_status'):return display_text(token(value,language,required=True))
    if key=='case' and 'filing_review'in parts or key=='action' and 'claim'in parts or key=='stage' and 'appeal_draft'in parts:return display_text(token(value,language,required=True))
    if key=='field' and 'conditions'in parts:return field_label(value,language)
    if key=='foreign_trade':return display_text(token(value,language,required=True))
    if key=='method' and 'rounding' not in parts:return display_text(value)
    if key=='category':return display_text(value)
    if any(x in parts for x in ('selected_required_topics','missing_selected_topics')):return display_text(token(value,language,required=True))
    if 'conditions'in parts:
        condition=_ancestor(result,path,'conditions')
        if type(condition)is dict and condition.get('field')=='foreign_trade' and 'expected'in parts:return display_text(token(value,language))
    if key in LITERALS:return display_text(value)
    if key=='regime':
        return display_text(token(value,language,required=True)) if 'scenarios'in parts else display_text(value)
    if key=='topic':
        return display_text(token(value,language,required=True)) if any(p in parts for p in ('choices','risk_reviews','clauses','clause_topic_conflicts')) else display_text(value)
    if key=='scope' and is_basis(parent):return display_text(value)
    if key=='tax_treatment':return display_text(value)
    if key in CONTROLLED or any(x in parts for x in ('questions','required_inputs','comparison_limitations')):
        return display_text(token(value,language,required=True))
    return display_text(value)


def _doc_for(function,path,result):
    root=path.strip('/').split('/')[0]
    if function=='tax_audit_support':return ['request_reply'] if root=='request_reply' else ['audit_roadmap']
    if function=='objections_appeal':
        if root in ('act_record','episodes'):return ['objections']
        if root=='decision_record':return ['appeal']
        if root=='events' and len(path.split('/'))>2:
            event=_ancestor(result,path,'events')
            return ['objections'] if type(event)is dict and event.get('role')=='objections' else ['appeal']
        if root=='appeal_draft':return ['objections'] if (result.get('appeal_draft') or {}).get('stage')=='objections' else ['appeal']
        return ['objections','appeal']
    return ROUTES[function]


def _regime_section(result,path):
    scenario=_ancestor(result,path,'scenarios')
    if type(scenario)is not dict:return 0
    parts=path.split('/')
    if any(x in parts for x in ('assumptions',)):return 5
    if any(x in parts for x in ('transition_reviews','eligibility_conditions')):return 6
    model=scenario['regime']
    if model.startswith('OSNO'):return 1
    if model.startswith(('PSN','AUSN')):return 4
    if model=='NPD':return 7
    vat=scenario.get('VAT');rates=[]
    if vat:
        for row in vat.get('entries',[]):
            if row.get('rate') is not None:
                try:rates.append(Decimal(row['rate']))
                except InvalidOperation:raise ValueError('artifact_rate_invalid') from None
    if rates and all(rate in (Decimal('.05'),Decimal('.07')) for rate in rates):return 2
    if rates and all(rate==Decimal('.22') for rate in rates):return 3
    return 8


def _section(function,doc,path,result):
    parts=path.strip('/').split('/');root=parts[0];last=parts[-1]
    if function not in ('law_monitoring','regime_choice','transaction_structuring') and root in ('evidence_gaps','gaps','questions','required_inputs','missing_selected_topics','selected_required_topics','clause_topic_conflicts'):
        return -2
    if function=='law_monitoring':
        if root=='client':return 2
        if root=='applicability_date':return 1
        if root=='documents':return 4
        if root in ('source_conflicts','topic_comparison','weekly_update_status','questions','evidence_gaps'):return 5
        if root=='changes':
            if any(x in parts for x in ('conditions','condition_results','selected_client_conditions_match')):return 2
            if any(x in parts for x in ('proposed_action','owner','target_date')):return 3
            if any(x in parts for x in ('document_metadata','temporal_status','document_kind','document_id')):return 1
            if 'related_document_ids'in parts:return 4
        return 0
    if function=='regime_choice':
        if root=='scenarios':return _regime_section(result,path)
        if root in ('automatic_regime_selected','comparison_span_equal','comparison_period_coverage_equal','comparison_limitations','gaps'):return 6
        return 0
    if function=='transaction_structuring':
        if root in ('question','required_inputs','calculation'):return 0
        if root in ('facts','business_purpose','counterparties'):return 1
        if root=='risk_reviews':return 4
        if root=='authored_conclusion':return 5
        if root=='gaps':return 6
        return 3
    if function=='tax_audit_support':
        if doc=='request_reply':
            if 'request_record'in parts:return 0
            if 'requested_items'in parts:return 1
            if 'provided_items'in parts:return 2
            if 'inventory'in parts:return 4
            return 3
        if root=='events':
            if 'selected_rule'in parts:return 1
            if last=='owner':return 4
            if any(x in parts for x in ('event_date','service')):return 2
            if last in ('provided_status','calculation_status','legal_deadline_established'):return 5
            if last in ('id','role','trigger','source_reference','excerpt'):return 0
            return 3
        return 5 if root in ('questions','evidence_gaps') else 0
    if function=='objections_appeal':
        if doc=='appeal':
            if root=='decision_record' or root=='events':return 0
            if 'violated_rights'in parts:return 1
            if 'requests'in parts:return 3
            if 'appendices'in parts:return 4
            return 2
        if root=='act_record' or root=='events':return 0
        if root=='episodes':
            if 'norms'in parts or 'objection'in parts:return 2
            if 'evidence'in parts:return 3
            if 'court_records'in parts:return 4
            if 'mitigation_notes'in parts:return 5
            return 1
        return 6
    if function=='penalties_mitigation':
        if root=='penalty_ledger':return 4
        if root=='circumstances':return 1
        if root in ('evidence_gaps','questions'):return 2
        if root=='request_draft':return 3
        if root=='fine':
            if any(x in parts for x in ('repeat','mitigation','selected_mitigation_divisor','conditional_after_mitigation','after_selected_repeat_multiplier','selected_exemption','exemption_review','conditional_after_selected_exemption','final_conditional_amount')):return 3
        return 0
    if function=='individual_3ndfl':
        if root=='residency':return 6
        if root=='groups':
            if any(x in parts for x in ('exemption_basis','exemption_treatment','other_exemption_conditions','calendar_holding_condition_met','minimum_holding_anniversary','minimum_holding_months','anniversary_policy','selected_exempt_and_property_reduction')):return 1
            if any(x in parts for x in ('deductions_applied','cost_method','cost_or_deduction')):return 2
            if any(x in parts for x in ('tax_base','scale_steps','tax_before_rounding','tax','rounding','taxable_after_selected_treatment')):return 3
            return 0
        if root=='deduction_pools':return 2
        if root in ('tax_total','foreign_tax_credits','foreign_tax_credit_applied','withheld','domestic_advance_paid','signed_settlement','potential_amount_due','potential_refund'):return 4
        if root in ('documents','filing_review','question','required_inputs','gaps'):return 5
        if root=='calculation':return 3
        return 0
    if function=='tax_accounting_method':
        if root=='choices':
            item=_ancestor(result,path,'choices');topic=item.get('topic') if type(item)is dict else None
            return {'income_expenses':1,'depreciation':2,'reserves':3,'vat':4,'registers':5,'branches':6,'usn_expenses':1}.get(topic,0)
        if root=='vat_cost_share':return 4
        if root=='registers':return 5
        if root=='branch_method':return 6
        return 0
    if function=='ens_dispute':
        if root in ('penalty_ledger','refund_interest'):return 4
        if root=='claim' and 'bank_record'in parts:return 2
        if root=='claim' and any(x in parts for x in ('requested_amount','selected_positive_balance','within_selected_positive_balance')):return 0
        if root=='ledger' and last in ('opening_balance','statement_balance','reconstructed_balance','statement_minus_reconstructed','proposed_adjustment_delta','candidate_after_proposed_adjustments'):return 0
        return 1
    if function=='client_engagement':
        if root=='clauses':
            item=_ancestor(result,path,'clauses');topic=item.get('topic') if type(item)is dict else None
            return {'inputs':1,'document_exchange':1,'deadlines':2,'price':3,'confidentiality':4,'liability':5,'power_of_attorney':6}.get(topic,0)
        if root=='fee':return 3
        if root in ('power_review','representation_date'):return 6
        if root=='contract_confidentiality_scope':return 4
        if root=='professional_care_scope':return 5
        if root=='brief':return 1
        return 0
    raise ValueError('artifact_function_route_missing')


def _content(function,result,language):
    if function not in ROUTES or language not in UI:raise ValueError('artifact_function_language_required')
    unknown=set(result)-COMMON-ROOTS[function]
    if unknown:raise ValueError('unmapped_result_roots:'+','.join(sorted(unknown)))
    def check_keys(value,parent_key=''):
        if type(value)is dict:
            for key,item in value.items():
                if parent_key!='missing_days_by_obligation' and key not in FIELDS:raise ValueError('artifact_field_label_missing:'+key)
                check_keys(item,key)
        elif type(value)is list:
            for item in value:check_keys(item,parent_key)
    check_keys(result)
    content={};catalogs={};source_lookups={}
    for doc in ROUTES[function]:
        sections=[{'title':tr(t,language),'paragraphs':[],'rows':[],'selected_paths':[],'rendered_leaf_values':[],'original_section':i,'original_title':t[0]} for i,t in enumerate(TEMPLATES[doc]['sections'])]
        if function=='regime_choice':
            sections.extend({'title':UI[language][key],'paragraphs':[],'rows':[],'selected_paths':[],'rendered_leaf_values':[],'additional_semantic_section':True} for key in ('NPD','other_USN'))
            sections[0]['paragraphs'].append(UI[language]['original_section_notice'])
        if function in ('penalties_mitigation','ens_dispute'):
            sections.append({'title':tr(('Пени и проценты по выбранным периодам','Interest on selected periods','所选期间的滞纳金及利息'),language),'paragraphs':[],'rows':[],'selected_paths':[],'rendered_leaf_values':[],'additional_semantic_section':True})
        if function=='individual_3ndfl':
            sections.append({'title':field_label('residency',language),'paragraphs':[],'rows':[],'selected_paths':[],'rendered_leaf_values':[],'additional_semantic_section':True})
        if function not in ('law_monitoring','regime_choice','transaction_structuring'):
            sections.append({'title':tr(('Недостающие сведения и следующие проверки','Missing information and follow-up checks','缺失资料及后续核查'),language),'paragraphs':[],'rows':[],'selected_paths':[],'rendered_leaf_values':[],'review_notes_section':True})
        sections.append({'title':UI[language]['tool_scope'],'paragraphs':[],'rows':[],'selected_paths':[],'rendered_leaf_values':[],'tool_scope_section':True})
        content[doc]=sections;catalogs[doc]={};source_lookups[doc]={}

    def add(doc,section,path,value,label=None,human=True):
        target=content[doc][section];display=shown(value,path,result,language)
        if human:
            key=path.split('/')[-1]
            narrative=key in {'authored_conclusion','question','business_purpose','proposed_action','proposed_follow_up','consequences','proposed_procedure','cost_scope_note','grounds','requests','pretrial_review','scope_analysis','draft_text','draft_notes','request_draft','objection','context','branch_method','general_provisions'} or key=='text' and any(x in path.split('/') for x in ('clauses','choices'))
            if type(value)is str and narrative:target['paragraphs'].append((label or path_label(path,result,language))+': '+display)
            else:target['rows'].append([label or path_label(path,result,language),display])
        target['selected_paths'].append(path)
        target['rendered_leaf_values'].append({'path':path,'type':type(value).__name__,'value':value,'display':display})

    def visit(value,path=''):
        if path and is_basis(value):
            identity=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
            for doc in _doc_for(function,path,result):
                section=_section(function,doc,path,result);source_section=SOURCE_SECTION[doc]
                new=identity not in catalogs[doc]
                if new:catalogs[doc][identity]='R'+str(len(catalogs[doc])+1)
                ref=catalogs[doc][identity]
                content[doc][section]['rows'].append([path_label(path,result,language),ref])
                source_lookups[doc].setdefault(ref,[]).append(path)
                for suffix,item in leaves(value):
                    actual=path+suffix
                    add(doc,source_section,actual,item,label=ref+' / '+path_label(suffix,value,language),human=new)
            return
        if type(value)is dict and value:
            for key,item in value.items():visit(item,path+'/'+key.replace('~','~0').replace('/','~1'))
        elif type(value)is list and value:
            for i,item in enumerate(value):visit(item,path+'/'+str(i))
        else:
            root=path.strip('/').split('/')[0]
            if root in COMMON:
                for doc in ROUTES[function]:add(doc,-1,path,value)
            else:
                for doc in _doc_for(function,path,result):add(doc,_section(function,doc,path,result),path,value)
    visit(result)
    for doc,sections in content.items():
        for section in sections:
            if not section['rows'] and not section['paragraphs']:
                if doc=='ens_claim' and section.get('original_section')==2 and (result.get('claim') or {}).get('action')=='refund':section['paragraphs'].append(tr(('Банковские реквизиты для выбранного возврата не предоставлены.','Bank details for the selected refund were not supplied.','未提供所选退款的银行信息。'),language))
                elif section['title']==tr(TEMPLATES[doc]['sections'][-1],language) and doc=='ens_claim':section['paragraphs'].append(UI[language]['signature_draft'])
                else:section['paragraphs'].append(UI[language]['unselected_original_section'])
        sections[SOURCE_SECTION[doc]]['source_catalog_occurrences']=source_lookups[doc]
    # Compact reader views reuse already computed values; they add no arithmetic
    # or Excel formulas and do not replace the routed original sections.
    if function=='regime_choice' and result.get('scenarios'):
        rows=[]
        for item in result['scenarios']:
            vat=item.get('VAT');balance=UI[language]['not_requested'] if vat is None else vat['signed_VAT_balance']
            combined=UI[language]['periods_not_summed'] if item['conditional_signed_accrual_total'] is None else item['conditional_signed_accrual_total']
            rows.append([item['id']+'\n'+token(item['regime'],language),item['covered_span']['start']+'\n'+item['covered_span']['end'],item['tax_total'],item['contributions_cash_total'],balance,item['unconfirmed_VAT_credit'],combined])
        content['regime_comparison'].insert(0,{'title':UI[language]['comparison_summary'],'paragraphs':[tr(('Только выбранные компоненты и периоды. Невыбранный НДС не доказывает освобождение; потенциальный кредит не является возвратом.','Only selected components and periods. Unselected VAT does not prove exemption; potential credit is not a refund.','仅包含所选组成项和期间；未选择增值税不证明免税，潜在抵免不是已获退款。'),language)],'columns':[field_label(k,language)+(' (RUB)' if i>=2 else '') for i,k in enumerate(('scenarios','covered_span','tax_total','contributions_cash_total','signed_VAT_balance','unconfirmed_VAT_credit','conditional_signed_accrual_total'))],'rows':rows,'selected_paths':[],'rendered_leaf_values':[],'additional_summary_section':True})
    if function=='tax_audit_support' and result.get('events'):
        rows=[]
        for item in result['events']:
            rule=item['selected_rule'];rows.append([item['id']+'\n'+token(item['role'],language),rule['document_identity']+'\n'+rule['clause'],item['event_date'],item['candidate_deadline'] or UI[language]['not_computed'],item['owner'],token(item['calculation_status'],language)+'\n'+item['provided_status']])
        content['audit_roadmap'].insert(0,{'title':UI[language]['records_summary'],'paragraphs':[],'columns':[tr(x,language) for x in TEMPLATES['audit_roadmap']['sections']],'rows':rows,'selected_paths':[],'rendered_leaf_values':[],'additional_summary_section':True})
    if function=='individual_3ndfl' and result.get('groups'):
        rows=[[item['id'],item['taxable_before_group_deductions'],item['deductions_applied'],item['tax_base'],item['tax']] for item in result['groups']]
        content['ndfl_3_draft'].insert(0,{'title':UI[language]['comparison_summary'],'paragraphs':[],'columns':[field_label(k,language)+(' (RUB)' if i else '') for i,k in enumerate(('group_id','taxable_before_group_deductions','deductions_applied','tax_base','tax'))],'rows':rows,'selected_paths':[],'rendered_leaf_values':[],'additional_summary_section':True})
    return content


def render(function,result,language,*,config,review_evidence=None):
    from .core import execute
    cfg=snapshot(config);actual=snapshot(result);evidence=snapshot(review_evidence or {})
    expected=execute(function,cfg)
    canonical=lambda v:json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    if canonical(actual)!=canonical(expected):raise ValueError('artifact_result_config_mismatch')
    content=_content(function,actual,language)
    files={'result.json':(json.dumps(actual,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')}
    for identifier,sections in content.items():
        title=tr(TEMPLATES[identifier]['title'],language);combined=sections+extra_sections(evidence,language)
        fmt=TEMPLATES[identifier]['format']
        if fmt=='docx':files[identifier+'.docx']=docx_bytes(title,combined,language,evidence)
        elif fmt=='xlsx':files[identifier+'.xlsx']=xlsx_bytes(title,combined,language,evidence)
        else:raise ValueError('unsupported_original_artifact_format')
        files[identifier+'.pdf']=pdf_bytes(title,combined,language,evidence)
    return files

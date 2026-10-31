"""Bounded local appraisal document writers; never opens source URLs."""
from decimal import Decimal
from pathlib import Path
import io,json,html,re,hashlib
from .artifact_labels import UI,field_label,token

FONT_SHA256='d4b79f59e2b6b3d791b3ed265edc5294ce9973a13c1c6f86a5ccd9e40d07fd9d'


def snapshot(value):
    raw=json.dumps(value,ensure_ascii=False,allow_nan=False,default=lambda x:str(x) if isinstance(x,Decimal) else (_ for _ in ()).throw(ValueError('non_json_artifact_input')))
    if len(raw.encode('utf-8'))>8_000_000:raise ValueError('artifact_input_limit')
    parsed=json.loads(raw)
    def visit(x,depth=0):
        if depth>24:raise ValueError('artifact_nesting_limit')
        if isinstance(x,str):
            if len(x)>200000 or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',x):raise ValueError('artifact_text_invalid')
            if any(0xD800<=ord(c)<=0xDFFF or ord(c) in (0xFFFE,0xFFFF) for c in x):raise ValueError('artifact_unicode_invalid')
        elif isinstance(x,dict):
            if len(x)>10000:raise ValueError('artifact_mapping_limit')
            for k,v in x.items():visit(k,depth+1);visit(v,depth+1)
        elif isinstance(x,list):
            if len(x)>2000:raise ValueError('artifact_array_limit')
            for v in x:visit(v,depth+1)
    visit(parsed);return parsed


def scalar(value,language):
    u=UI[language]
    if value is None:return u['missing']
    if type(value) is bool:return u['yes'] if value else u['no']
    return token(str(value),language)


def flat(value,language,prefix=''):
    """Expand data into labelled rows; never a JSON dump in a document section."""
    u=UI[language];rows=[]
    if isinstance(value,dict):
        if not value:return [[prefix or u['details'],u['missing']]]
        for key,item in value.items():
            label=field_label(key,language)
            if key=='days' and isinstance(item,dict) and item and all(re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(k)) and type(v) is bool for k,v in item.items()):
                item={'calendar_days_count':len(item),'working_days_count':sum(item.values()),'nonworking_days_count':len(item)-sum(item.values())}
            rows.extend(flat(item,language,(prefix+' / ' if prefix else '')+label))
    elif isinstance(value,list):
        if not value:return [[prefix or u['items'],u['none']]]
        for index,item in enumerate(value,1):rows.extend(flat(item,language,(prefix+' / ' if prefix else '')+str(index)))
    else:rows.append([prefix or u['value'],scalar(value,language)])
    if len(rows)>15000:raise ValueError('artifact_rows_limit')
    return rows


def extra_sections(review_evidence,language):
    u=UI[language];review=review_evidence or {};out=[]
    assumptions=review.get('assumptions',[])
    if assumptions:
        rows=[]
        for assumption in assumptions:
            rows.extend(flat({k:assumption.get(k) for k in ('pointer','value','unit','rationale')},language))
        out.append({'title':u['assumptions'],'paragraphs':[u['assumption_banner']],'rows':rows})
    bindings=review.get('bindings',[])
    if bindings:
        rows=[]
        for binding in bindings:rows.extend(flat(binding,language))
        out.append({'title':u['evidence'],'paragraphs':[u['unverified']],'rows':rows})
    else:out.append({'title':u['evidence'],'paragraphs':[u['sources_unconfirmed'],u['unverified']],'rows':[]})
    return out


def intro(language,review_evidence):
    u=UI[language];review=review_evidence or {}
    paragraphs=[u['draft'],u['source_note'],u['unverified']]
    if review.get('assumptions') or review.get('hypothetical_inputs_present'):
        paragraphs.insert(0,u['assumption_banner'])
    if review.get('as_of'):paragraphs.append(u['as_of']+': '+str(review['as_of']))
    return paragraphs


def docx_bytes(title,sections,language,review_evidence):
    from docx import Document
    from docx.shared import Inches,Pt,RGBColor
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    doc=Document();section=doc.sections[0]
    section.page_width=Inches(8.27);section.page_height=Inches(11.69)
    section.top_margin=section.bottom_margin=Inches(.65);section.left_margin=section.right_margin=Inches(.7)
    normal=doc.styles['Normal'];normal.font.name='Arial';normal.font.size=Pt(10)
    normal.paragraph_format.space_after=Pt(6)
    normal.element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),'Microsoft YaHei')
    for style in ('Title','Heading 1','Heading 2'):
        doc.styles[style].font.color.rgb=RGBColor(0,0,0)
        doc.styles[style].font.name='Arial'
        properties=doc.styles[style].element.find(qn('w:pPr'))
        if properties is not None:
            for border in list(properties.findall(qn('w:pBdr'))):properties.remove(border)
    doc.core_properties.author='NABY';doc.core_properties.title=title
    doc.add_paragraph(title,'Title')
    for paragraph in intro(language,review_evidence):doc.add_paragraph(paragraph)
    for content in sections:
        doc.add_heading(content['title'],1)
        for paragraph in content.get('paragraphs',[]):doc.add_paragraph(paragraph)
        if content.get('rows'):
            columns=content.get('columns',[UI[language]['field'],UI[language]['value']])
            table=doc.add_table(rows=0,cols=len(columns));table.style='Light Shading Accent 1';table.autofit=False
            widths=content.get('widths',[2.3,4.57] if len(columns)==2 else [6.87/len(columns)]*len(columns))
            for column,width in zip(table.columns,widths):column.width=Inches(width)
            header=table.add_row().cells
            for cell,label in zip(header,columns):cell.text=str(label)
            repeat=OxmlElement('w:tblHeader');table.rows[0]._tr.get_or_add_trPr().append(repeat)
            for row in content['rows']:
                cells=table.add_row().cells
                for cell,value in zip(cells,row):cell.text=str(value)
            for row in table.rows:
                for cell in row.cells:
                    margins=OxmlElement('w:tcMar')
                    for edge in ('top','left','bottom','right'):
                        item=OxmlElement('w:'+edge);item.set(qn('w:w'),'100');item.set(qn('w:type'),'dxa');margins.append(item)
                    cell._tc.get_or_add_tcPr().append(margins)
                    for paragraph in cell.paragraphs:
                        paragraph.paragraph_format.space_after=Pt(3)
                        for run in paragraph.runs:run.font.size=Pt(9)
            doc.add_paragraph('')
    stream=io.BytesIO();doc.save(stream);return stream.getvalue()


def _font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    name='NabyDocumentSans'
    path=Path(__file__).resolve().parent/'fonts'/'NabyDocumentSans.ttf'
    if not path.exists():path=Path(__file__).resolve().parent.parent/'_shared'/'fonts'/'NabyDocumentSans.ttf'  # NABY build 39: one shared copy
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=FONT_SHA256:raise ValueError('document_font_hash_mismatch')
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(name,io.BytesIO(raw)))
    return name


def pdf_bytes(title,sections,language,review_evidence):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph,SimpleDocTemplate,Spacer,LongTable,TableStyle,CondPageBreak
    from reportlab.pdfbase import pdfmetrics
    font=_font();face=pdfmetrics.getFont(font).face
    def safe(value):
        value=str(value)
        if any(ord(c)>32 and ord(c) not in face.charToGlyph for c in value):raise ValueError('document_font_missing_glyph')
        return html.escape(value,quote=False).replace('\n','<br/>')
    stream=io.BytesIO();document=SimpleDocTemplate(stream,pagesize=A4,leftMargin=18*mm,rightMargin=18*mm,topMargin=16*mm,bottomMargin=16*mm,title=title,author='NABY',invariant=1)
    normal=ParagraphStyle('body',fontName=font,fontSize=9.3,leading=13.5,spaceAfter=5,wordWrap='CJK' if language=='zh' else None,splitLongWords=1)
    title_style=ParagraphStyle('title',parent=normal,fontSize=17,leading=22,spaceAfter=12)
    heading=ParagraphStyle('heading',parent=normal,fontSize=12,leading=17,spaceBefore=11,spaceAfter=7,keepWithNext=False)
    label=ParagraphStyle('label',parent=normal,fontSize=8.5,leading=12,textColor='#404040',spaceBefore=3,spaceAfter=1,keepWithNext=True)
    story=[Paragraph(safe(title),title_style)]
    for paragraph in intro(language,review_evidence):story.append(Paragraph(safe(paragraph),normal))
    for section in sections:
        story.append(CondPageBreak(60))
        story.append(Paragraph(safe(section['title']),heading))
        for paragraph in section.get('paragraphs',[]):story.append(Paragraph(safe(paragraph),normal))
        rows=section.get('rows',[])
        if rows:
            columns=section.get('columns')
            values=([columns]+rows) if columns else rows
            widths=([64*mm,110*mm] if len(values[0])==2 else [174*mm/len(values[0])]*len(values[0]))
            table=LongTable([[Paragraph(safe(value) or ' ',normal) for value in row] for row in values],colWidths=widths,hAlign='LEFT',splitByRow=1,splitInRow=1,repeatRows=1 if columns else 0)
            table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),('ROWBACKGROUNDS',(0,0),(-1,-1),['#f2f5f7','#ffffff'])]))
            story.append(table)
        story.append(Spacer(1,3))
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont(font,8);canvas.drawRightString(A4[0]-18*mm,9*mm,UI[language]['page']+' '+str(doc.page));canvas.restoreState()
    document.build(story,onFirstPage=footer,onLaterPages=footer)
    return stream.getvalue()


def xlsx_bytes(title,sections,language,review_evidence):
    from openpyxl import Workbook
    from openpyxl.styles import Font,Alignment,PatternFill
    from openpyxl.utils import get_column_letter
    book=Workbook();book.remove(book.active)
    evidence_titles={UI[language]['evidence'],UI[language]['assumptions']}
    main=[s for s in sections if not s.get('columns') and s['title'] not in evidence_titles]
    proofs=[s for s in sections if s['title'] in evidence_titles]
    groups=[(UI[language]['calculation'],main)]+[(s['title'],[s]) for s in sections if s.get('columns')]
    if proofs:groups.append((UI[language]['evidence'],proofs))
    for index,(group_title,group) in enumerate(groups):
        base=re.sub(r'[\\/*?:\[\]]',' ',group_title).strip() or UI[language]['calculation']
        sheet=book.create_sheet((str(index+1)+' '+base)[:31])
        rows=[[title]];header_rows=[];max_columns=2
        if index==0:
            rows.extend([[paragraph] for paragraph in intro(language,review_evidence)])
            rows.append([{'ru':'Книга содержит сохранённые результаты локального расчёта. После изменения исходных данных запустите инструмент NABY повторно; автоматического пересчёта формул в Excel здесь нет.','en':'This workbook stores local calculation results. After changing inputs, rerun the NABY tool; this file does not automatically recalculate Excel formulas.','zh':'本工作簿保存本地计算结果。输入改变后请重新运行NABY工具；此文件不自动重新计算Excel公式。'}[language]])
        for section in group:
            rows.append([section['title']]);rows.extend([[paragraph] for paragraph in section.get('paragraphs',[])])
            columns=section.get('columns',[UI[language]['field'],UI[language]['value']]);max_columns=max(max_columns,len(columns))
            header_rows.append(len(rows)+1);rows.append(columns);rows.extend(section.get('rows',[]));rows.append([])
        for row in rows:
            values=[str(value) if value is not None else UI[language]['missing'] for value in row]
            if any(len(value)>32767 for value in values):raise ValueError('xlsx_cell_text_limit')
            sheet.append(values)
            for cell in sheet[sheet.max_row]:
                cell.data_type='s';cell.alignment=Alignment(vertical='top',wrap_text=True);cell.font=Font(name='Arial',size=10)
        sheet['A1'].font=Font(name='Arial',size=15,bold=True)
        for header_row in header_rows:
            for cell in sheet[header_row]:cell.fill=PatternFill('solid',fgColor='E8EEF3');cell.font=Font(name='Arial',size=10,bold=True)
        for number in range(1,max_columns+1):sheet.column_dimensions[get_column_letter(number)].width=52 if max_columns==2 else 24
        if max_columns==2:sheet.column_dimensions['B'].width=82
        sheet.freeze_panes='A'+str(header_rows[0]+1)
        if len(group)==1 and group[0].get('columns') and group[0].get('rows'):sheet.auto_filter.ref=f'A{header_rows[0]}:{get_column_letter(max_columns)}{sheet.max_row-1}'
        sheet.sheet_properties.pageSetUpPr.fitToPage=True
        sheet.page_setup.orientation='landscape';sheet.page_setup.paperSize=sheet.PAPERSIZE_A4;sheet.page_setup.fitToWidth=1;sheet.page_setup.fitToHeight=0
    stream=io.BytesIO();book.save(stream);return stream.getvalue()

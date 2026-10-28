import os
import re
import zipfile
import html

def escape_xml(text):
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;"))

def parse_inline(text):
    """Parses inline bold, italic, inline code, and links into OpenXML runs."""
    # Pattern to find **bold**, `code`, *italic*
    tokens = []
    # Tokenize by regex: (`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)
    parts = re.split(r'(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)', text)
    
    runs_xml = []
    for part in parts:
        if not part:
            continue
        if part.startswith('`') and part.endswith('`') and len(part) >= 2:
            code_text = part[1:-1]
            runs_xml.append(f'''<w:r>
              <w:rPr>
                <w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>
                <w:sz w:val="20"/>
                <w:color w:val="C7254E"/>
                <w:shd w:fill="F9F2F4"/>
              </w:rPr>
              <w:t xml:space="preserve">{escape_xml(code_text)}</w:t>
            </w:r>''')
        elif part.startswith('**') and part.endswith('**') and len(part) >= 4:
            bold_text = part[2:-2]
            runs_xml.append(f'''<w:r>
              <w:rPr><w:b/></w:rPr>
              <w:t xml:space="preserve">{escape_xml(bold_text)}</w:t>
            </w:r>''')
        elif part.startswith('*') and part.endswith('*') and len(part) >= 2:
            italic_text = part[1:-1]
            runs_xml.append(f'''<w:r>
              <w:rPr><w:i/></w:rPr>
              <w:t xml:space="preserve">{escape_xml(italic_text)}</w:t>
            </w:r>''')
        else:
            # Clean markdown links [text](url) -> text
            cleaned_plain = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', part)
            runs_xml.append(f'''<w:r>
              <w:t xml:space="preserve">{escape_xml(cleaned_plain)}</w:t>
            </w:r>''')
    return "".join(runs_xml)

def make_paragraph(content_xml, style=None, align=None):
    pPr = []
    if style:
        pPr.append(f'<w:pStyle w:val="{style}"/>')
    if align:
        pPr.append(f'<w:jc w:val="{align}"/>')
    pPr_xml = f'<w:pPr>{"".join(pPr)}</w:pPr>' if pPr else ''
    return f'<w:p>{pPr_xml}{content_xml}</w:p>'

def make_table(rows):
    """Generates an OpenXML table with stylish borders and header shading."""
    tbl_xml = ['''<w:tbl>
      <w:tblPr>
        <w:tblW w:w="5000" w:type="pct"/>
        <w:tblBorders>
          <w:top w:val="single" w:sz="6" w:space="0" w:color="CCCCCC"/>
          <w:left w:val="none"/>
          <w:bottom w:val="single" w:sz="6" w:space="0" w:color="CCCCCC"/>
          <w:right w:val="none"/>
          <w:insideH w:val="single" w:sz="4" w:space="0" w:color="E5E5E5"/>
          <w:insideV w:val="none"/>
        </w:tblBorders>
        <w:tblCellMar>
          <w:top w:w="120" w:type="dxa"/>
          <w:left w:w="160" w:type="dxa"/>
          <w:bottom w:w="120" w:type="dxa"/>
          <w:right w:w="160" w:type="dxa"/>
        </w:tblCellMar>
      </w:tblPr>''']

    for r_idx, row in enumerate(rows):
        tbl_xml.append('<w:tr>')
        is_header = (r_idx == 0)
        for cell in row:
            tcPr = []
            if is_header:
                tcPr.append('<w:shd w:fill="0F172A"/>')
            else:
                if r_idx % 2 == 1:
                    tcPr.append('<w:shd w:fill="F8FAFC"/>')
                else:
                    tcPr.append('<w:shd w:fill="FFFFFF"/>')
            
            tcPr_str = f'<w:tcPr>{"".join(tcPr)}</w:tcPr>'
            
            if is_header:
                cell_p = f'''<w:p>
                  <w:pPr><w:spacing w:after="0"/></w:pPr>
                  <w:r><w:rPr><w:b/><w:color w:val="FFFFFF"/><w:sz w:val="20"/></w:rPr>
                  <w:t>{escape_xml(cell.strip())}</w:t></w:r>
                </w:p>'''
            else:
                cell_runs = parse_inline(cell.strip())
                cell_p = f'''<w:p>
                  <w:pPr><w:spacing w:after="0"/></w:pPr>
                  {cell_runs}
                </w:p>'''
            
            tbl_xml.append(f'<w:tc>{tcPr_str}{cell_p}</w:tc>')
        tbl_xml.append('</w:tr>')

    tbl_xml.append('</w:tbl>')
    return "".join(tbl_xml)

def markdown_to_docx(md_path, docx_path):
    with open(md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()

    lines = md_text.splitlines()
    doc_elements = []
    
    in_code_block = False
    code_block_lines = []
    in_table = False
    table_rows = []

    for line in lines:
        stripped = line.strip()

        # Handle Code blocks
        if stripped.startswith("```"):
            if in_code_block:
                # Close code block
                in_code_block = False
                code_text = "\n".join(code_block_lines)
                for cb_line in code_block_lines:
                    runs = f'''<w:r>
                      <w:rPr>
                        <w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>
                        <w:sz w:val="18"/>
                        <w:color w:val="333333"/>
                      </w:rPr>
                      <w:t xml:space="preserve">{escape_xml(cb_line)}</w:t>
                    </w:r>'''
                    doc_elements.append(f'''<w:p>
                      <w:pPr>
                        <w:pStyle w:val="CodeBlock"/>
                        <w:shd w:fill="F1F5F9"/>
                        <w:spacing w:after="40" w:line="200" w:lineRule="auto"/>
                        <w:ind w:left="240" w:right="240"/>
                      </w:pPr>
                      {runs}
                    </w:p>''')
                code_block_lines = []
            else:
                in_code_block = True
                code_block_lines = []
            continue

        if in_code_block:
            code_block_lines.append(line)
            continue

        # Handle Tables
        if stripped.startswith("|") and stripped.endswith("|"):
            # Check if divider line like |---|---|
            if re.match(r'^\|[\s\-:|]+\|$', stripped):
                continue
            cells = [c for c in stripped.split("|")[1:-1]]
            table_rows.append(cells)
            in_table = True
            continue
        else:
            if in_table:
                doc_elements.append(make_table(table_rows))
                table_rows = []
                in_table = False

        if not stripped:
            continue

        # Headings
        if stripped.startswith("# "):
            heading_text = stripped[2:].strip()
            runs = parse_inline(heading_text)
            doc_elements.append(make_paragraph(runs, style="Title"))
        elif stripped.startswith("## "):
            heading_text = stripped[3:].strip()
            runs = parse_inline(heading_text)
            doc_elements.append(make_paragraph(runs, style="Heading1"))
        elif stripped.startswith("### "):
            heading_text = stripped[4:].strip()
            runs = parse_inline(heading_text)
            doc_elements.append(make_paragraph(runs, style="Heading2"))
        elif stripped.startswith("#### "):
            heading_text = stripped[5:].strip()
            runs = parse_inline(heading_text)
            doc_elements.append(make_paragraph(runs, style="Heading3"))
        elif stripped.startswith("---") or stripped.startswith("***"):
            # Divider line
            doc_elements.append('''<w:p>
              <w:pPr>
                <w:pBdr><w:bottom w:val="single" w:sz="12" w:space="4" w:color="0F172A"/></w:pBdr>
                <w:spacing w:before="180" w:after="180"/>
              </w:pPr>
            </w:p>''')
        elif stripped.startswith("- ") or stripped.startswith("* "):
            # Bullet point
            item_text = stripped[2:].strip()
            bullet_run = '<w:r><w:rPr><w:b/><w:color w:val="0F172A"/></w:rPr><w:t>  •  </w:t></w:r>'
            item_runs = parse_inline(item_text)
            doc_elements.append(f'''<w:p>
              <w:pPr>
                <w:ind w:left="360" w:hanging="240"/>
                <w:spacing w:after="80"/>
              </w:pPr>
              {bullet_run}{item_runs}
            </w:p>''')
        elif re.match(r'^\d+\.\s+', stripped):
            # Numbered list
            num_match = re.match(r'^(\d+\.)\s+(.+)$', stripped)
            num_tag = num_match.group(1)
            num_text = num_match.group(2)
            num_run = f'<w:r><w:rPr><w:b/><w:color w:val="0F172A"/></w:rPr><w:t>{escape_xml(num_tag)}  </w:t></w:r>'
            item_runs = parse_inline(num_text)
            doc_elements.append(f'''<w:p>
              <w:pPr>
                <w:ind w:left="360" w:hanging="240"/>
                <w:spacing w:after="80"/>
              </w:pPr>
              {num_run}{item_runs}
            </w:p>''')
        else:
            # Normal paragraph
            runs = parse_inline(stripped)
            doc_elements.append(make_paragraph(runs))

    if in_table and table_rows:
        doc_elements.append(make_table(table_rows))

    document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    {"".join(doc_elements)}
    <w:sectPr>
      <w:pgSz w:w="12240" w:h="15840"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720"/>
    </w:sectPr>
  </w:body>
</w:document>'''

    content_types_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>'''

    rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

    doc_rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''

    styles_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Segoe UI" w:hAnsi="Segoe UI" w:cs="Segoe UI"/>
        <w:sz w:val="22"/>
        <w:color w:val="1E293B"/>
      </w:rPr>
    </w:rPrDefault>
    <w:pPrDefault>
      <w:pPr>
        <w:spacing w:after="160" w:line="260" w:lineRule="auto"/>
      </w:pPr>
    </w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:rPr>
      <w:rFonts w:ascii="Segoe UI Semibold" w:hAnsi="Segoe UI Semibold"/>
      <w:b/>
      <w:sz w:val="48"/>
      <w:color w:val="0F172A"/>
    </w:rPr>
    <w:pPr>
      <w:spacing w:before="240" w:after="160"/>
      <w:jc w:val="center"/>
    </w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:rPr>
      <w:rFonts w:ascii="Segoe UI Semibold" w:hAnsi="Segoe UI Semibold"/>
      <w:b/>
      <w:sz w:val="34"/>
      <w:color w:val="1E40AF"/>
    </w:rPr>
    <w:pPr>
      <w:spacing w:before="360" w:after="140"/>
    </w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:rPr>
      <w:rFonts w:ascii="Segoe UI Semibold" w:hAnsi="Segoe UI Semibold"/>
      <w:b/>
      <w:sz w:val="26"/>
      <w:color w:val="2563EB"/>
    </w:rPr>
    <w:pPr>
      <w:spacing w:before="240" w:after="100"/>
    </w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading3">
    <w:name w:val="heading 3"/>
    <w:rPr>
      <w:rFonts w:ascii="Segoe UI Semibold" w:hAnsi="Segoe UI Semibold"/>
      <w:b/>
      <w:sz w:val="22"/>
      <w:color w:val="0D9488"/>
    </w:rPr>
    <w:pPr>
      <w:spacing w:before="180" w:after="80"/>
    </w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="CodeBlock">
    <w:name w:val="CodeBlock"/>
    <w:rPr>
      <w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>
      <w:sz w:val="18"/>
      <w:color w:val="0F172A"/>
    </w:rPr>
  </w:style>
</w:styles>'''

    # Package as ZIP (.docx)
    with zipfile.ZipFile(docx_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', content_types_xml)
        zf.writestr('_rels/.rels', rels_xml)
        zf.writestr('word/_rels/document.xml.rels', doc_rels_xml)
        zf.writestr('word/styles.xml', styles_xml)
        zf.writestr('word/document.xml', document_xml)

    print(f"Successfully generated DOCX document at: {docx_path}")

if __name__ == "__main__":
    md_file = "PROJECT_DOCUMENTATION.md"
    docx_file = "CROWDGUARD_AI_DOCUMENTATION.docx"
    markdown_to_docx(md_file, docx_file)

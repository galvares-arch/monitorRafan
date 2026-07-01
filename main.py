import os, re, json, datetime, requests
from flask import Flask, request, jsonify, send_file

# ==========================================================================
#  Monitor de Inteligencia RAFAN  -  renderizador de PDF (ReportLab)
#  Mesmo modelo do Monitor Cenergy: header/rule/footer, tabelas coloridas,
#  KeepTogether no resumo. Aqui: PDF unico, informacoes quebradas em paginas.
# ==========================================================================

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
    LongTable, TableStyle, KeepTogether, Table, PageBreak
)

# ---- paleta (PLACEHOLDER: troco pela identidade do RAFAN/moteis) ----
PRIMARY = colors.HexColor("#22303A")   # slate escuro (cabecalho/titulos)
ACCENT  = colors.HexColor("#C6A15B")   # dourado (regua/detalhes)
ACCENT_D = colors.HexColor("#9A7A38")
GREY    = colors.HexColor("#666666")
LGREY   = colors.HexColor("#999999")

# ---- cores de classificacao das avaliacoes ----
SENT_COLORS = {
    "POSITIVO": colors.HexColor("#2E8B57"),
    "NEUTRO":   colors.HexColor("#E0A21E"),
    "NEGATIVO": colors.HexColor("#C0392B"),
    "—":        colors.HexColor("#999999"),
}
# ---- relevancia da imprensa (reaproveita a logica de "risco" do Cenergy) ----
REL_COLORS = {
    "ALTA":  colors.HexColor("#C0392B"),
    "MÉDIA": colors.HexColor("#E0A21E"),
    "BAIXA": colors.HexColor("#2E8B57"),
    "—":     colors.HexColor("#999999"),
}

PAGE_W, PAGE_H = A4
MARGIN = 14 * mm

LOGO = "logo_rafan.png"          # opcional: se existir, desenha; senao, wordmark textual
LOGO_ASPECT = 5.0
LOGO_W = 150
LOGO_H = LOGO_W / LOGO_ASPECT


def _styles():
    s = {}
    s["title"] = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=15,
                                textColor=PRIMARY, spaceAfter=4, leading=18)
    s["intro"] = ParagraphStyle("intro", fontName="Helvetica", fontSize=7.8,
                                textColor=GREY, leading=10.5, spaceAfter=2)
    s["block"] = ParagraphStyle("block", fontName="Helvetica-Bold", fontSize=12,
                                textColor=PRIMARY, spaceBefore=6, spaceAfter=3, leading=14)
    s["sub"]   = ParagraphStyle("sub", fontName="Helvetica", fontSize=7.8,
                                textColor=GREY, leading=10.5, spaceAfter=4)
    s["th"]    = ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=7.6,
                                textColor=colors.white, leading=9)
    s["cell"]  = ParagraphStyle("cell", fontName="Helvetica", fontSize=7.4,
                                textColor=colors.HexColor("#222222"), leading=9.3)
    s["sent"]  = ParagraphStyle("sent", fontName="Helvetica-Bold", fontSize=7.2,
                                textColor=colors.white, alignment=TA_CENTER, leading=9)
    s["leitura"] = ParagraphStyle("leitura", fontName="Helvetica", fontSize=7.5,
                                textColor=colors.HexColor("#333333"), leading=10,
                                spaceBefore=4, spaceAfter=2)
    s["kpi_big"] = ParagraphStyle("kpi_big", fontName="Helvetica-Bold", fontSize=20,
                                textColor=PRIMARY, alignment=TA_CENTER, leading=22)
    s["kpi_lbl"] = ParagraphStyle("kpi_lbl", fontName="Helvetica", fontSize=7,
                                textColor=GREY, alignment=TA_CENTER, leading=9)
    s["subhead"] = ParagraphStyle("subhead", fontName="Helvetica-Bold", fontSize=9.5,
                                textColor=ACCENT_D, spaceBefore=6, spaceAfter=3, leading=12)
    return s

S = _styles()


def _link(texto, url):
    if url:
        return f'<a href="{url}" color="#9A7A38"><u>{texto}</u></a>'
    return texto


def _make_header_footer(header_right_top, header_right_sub, footer_left):
    def header_footer(canvas, doc):
        canvas.saveState()
        if os.path.exists(LOGO):
            canvas.drawImage(LOGO, MARGIN, PAGE_H - MARGIN - LOGO_H,
                             width=LOGO_W, height=LOGO_H, mask="auto",
                             preserveAspectRatio=True)
        else:
            # wordmark textual como placeholder ate ter o logo real
            canvas.setFillColor(PRIMARY)
            canvas.setFont("Helvetica-Bold", 17)
            canvas.drawString(MARGIN, PAGE_H - MARGIN - 15, "RAFAN")
            canvas.setFillColor(ACCENT_D)
            canvas.setFont("Helvetica", 7.5)
            canvas.drawString(MARGIN, PAGE_H - MARGIN - 25, "Empreendimentos")
        canvas.setFillColor(PRIMARY)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN - 4, header_right_top)
        canvas.setFillColor(GREY)
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN - 14, header_right_sub)
        canvas.setStrokeColor(ACCENT)
        canvas.setLineWidth(1.4)
        y = PAGE_H - MARGIN - LOGO_H - 5
        canvas.line(MARGIN, y, PAGE_W - MARGIN, y)
        canvas.setStrokeColor(colors.HexColor("#DDDDDD"))
        canvas.setLineWidth(0.6)
        canvas.line(MARGIN, MARGIN + 14, PAGE_W - MARGIN, MARGIN + 14)
        canvas.setFillColor(LGREY)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(MARGIN, MARGIN + 5, footer_left)
        canvas.drawRightString(PAGE_W - MARGIN, MARGIN + 5, f"Página {doc.page}")
        canvas.restoreState()
    return header_footer


def _doc(path, header_right_top, header_right_sub, footer_left):
    top_used = LOGO_H + 16
    frame = Frame(MARGIN, MARGIN + 18, PAGE_W - 2*MARGIN,
                  PAGE_H - 2*MARGIN - top_used - 18, id="main",
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc = BaseDocTemplate(path, pagesize=A4,
                          leftMargin=MARGIN, rightMargin=MARGIN,
                          topMargin=MARGIN + top_used, bottomMargin=MARGIN + 18)
    hf = _make_header_footer(header_right_top, header_right_sub, footer_left)
    doc.addPageTemplates([PageTemplate(id="t", frames=[frame], onPage=hf)])
    return doc


# ---------- componentes ----------
def _faixa_kpis(kpis):
    """Faixa horizontal de KPIs: valor em cima, rotulo embaixo, centralizado."""
    n = len(kpis)
    col_w = (PAGE_W - 2*MARGIN) / n
    row_val = [Paragraph(val, S["kpi_big"]) for val, _ in kpis]
    row_lbl = [Paragraph(lbl, S["kpi_lbl"]) for _, lbl in kpis]
    t = Table([row_val, row_lbl], colWidths=[col_w]*n)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4F1EA")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#E3DAC4")),
        ("LINEAFTER", (0, 0), (-2, -1), 0.8, colors.HexColor("#E3DAC4")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
        ("TOPPADDING", (0, 1), (-1, 1), 0),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 9),
    ]))
    return t


def _tabela_avaliacoes(rows):
    col_w = [58, 30, 40, 300, 89]
    head = [Paragraph(h, S["th"]) for h in
            ["Autor", "Nota", "Data", "Comentário (linguagem simples)", "Classificação"]]
    data = [head]
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E2E2")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("VALIGN", (-1, 1), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F7F7")]),
    ]
    for i, r in enumerate(rows, start=1):
        autor = r.get("autor", "—")
        nota = r.get("nota", "—")
        if str(nota).isdigit():
            n = int(nota)
            estrelas = (f'<font color="#C6A15B">{"★" * n}</font>'
                        f'<font color="#D8D2C4">{"★" * (5 - n)}</font>')
        else:
            estrelas = str(nota)
        cls = r.get("classificacao", "—").upper()
        data.append([
            Paragraph(autor, S["cell"]),
            Paragraph(estrelas, S["cell"]),
            Paragraph(r.get("data", "—"), S["cell"]),
            Paragraph(r.get("comentario", ""), S["cell"]),
            Paragraph(cls, S["sent"]),
        ])
        style.append(("BACKGROUND", (4, i), (4, i), SENT_COLORS.get(cls, GREY)))
    t = LongTable(data, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle(style))
    return t


def _tabela_instagram(rows):
    col_w = [72, 32, 285, 40, 88]
    head = [Paragraph(h, S["th"]) for h in
            ["Autor", "Data", "Comentário (linguagem simples)", "Post", "Classificação"]]
    data = [head]
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E2E2")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("VALIGN", (-1, 1), (-1, -1), "MIDDLE"),
        ("VALIGN", (3, 1), (3, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F7F7")]),
    ]
    for i, r in enumerate(rows, start=1):
        cls = r.get("classificacao", "—").upper()
        post = _link("abrir", r.get("post_url")) if r.get("post_url") else "—"
        data.append([
            Paragraph(r.get("autor", "—"), S["cell"]),
            Paragraph(r.get("data", "—"), S["cell"]),
            Paragraph(r.get("comentario", ""), S["cell"]),
            Paragraph(post, S["cell"]),
            Paragraph(cls, S["sent"]),
        ])
        style.append(("BACKGROUND", (4, i), (4, i), SENT_COLORS.get(cls, GREY)))
    t = LongTable(data, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle(style))
    return t


def _tabela_imprensa(rows):
    col_w = [140, 78, 245, 54]
    head = [Paragraph(h, S["th"]) for h in
            ["Título / Veículo", "Fonte / Data", "Resumo (linguagem simples)", "Relevância"]]
    data = [head]
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E2E2")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("VALIGN", (-1, 1), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F7F7")]),
    ]
    for i, it in enumerate(rows, start=1):
        rel = it.get("relevancia", "—").upper()
        data.append([
            Paragraph(_link(it.get("titulo", ""), it.get("url")), S["cell"]),
            Paragraph(it.get("fonte", "—"), S["cell"]),
            Paragraph(it.get("resumo", ""), S["cell"]),
            Paragraph(rel, S["sent"]),
        ])
        style.append(("BACKGROUND", (3, i), (3, i), REL_COLORS.get(rel, GREY)))
    t = LongTable(data, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle(style))
    return t


def _pagina_motel(story, m):
    """Uma pagina por motel: KPIs + avaliacoes Google + comentarios Instagram."""
    story.append(Paragraph(m["nome"], S["block"]))
    story.append(Paragraph(m["subtitle"], S["sub"]))
    story.append(_faixa_kpis(m["kpis"]))
    story.append(Spacer(1, 6))

    # --- bloco Google ---
    story.append(Paragraph("Avaliações no Google — novas no dia anterior", S["subhead"]))
    if m.get("avaliacoes"):
        story.append(_tabela_avaliacoes(m["avaliacoes"]))
    else:
        story.append(Paragraph(
            "<b>Nenhuma nova avaliação encontrada no período.</b> "
            "Ausência de registro é reportada como tal — nada é inventado.", S["leitura"]))
    story.append(Paragraph("<b>Leitura (Google):</b> " + m.get("leitura", ""), S["leitura"]))
    story.append(Spacer(1, 6))

    # --- bloco Instagram ---
    handle = m.get("handle", "")
    story.append(Paragraph(f"Comentários no Instagram {handle} — novos no dia anterior",
                           S["subhead"]))
    if m.get("instagram"):
        story.append(_tabela_instagram(m["instagram"]))
    else:
        story.append(Paragraph(
            "<b>Nenhum comentário novo encontrado no período.</b> "
            "Ausência de registro é reportada como tal — nada é inventado.", S["leitura"]))
    story.append(Paragraph("<b>Leitura (Instagram):</b> " + m.get("leitura_instagram", ""),
                           S["leitura"]))


def gerar_monitor_rafan(d, out_path):
    doc = _doc(out_path, "Monitor de Inteligência", "Reputação e Imprensa",
               "RAFAN Empreendimentos  •  Documento interno / confidencial")
    story = []

    # ---- Pagina 1: capa / resumo executivo ----
    story.append(Paragraph("Monitor de Inteligência — Reputação e Imprensa", S["title"]))
    story.append(Paragraph(d["intro"], S["intro"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Resumo executivo", S["block"]))
    story.append(_faixa_kpis(d["resumo"]["kpis"]))
    story.append(Spacer(1, 8))
    pts = []
    for lead, txt in d["resumo"]["destaques"]:
        pts.append(Paragraph(f"<b>{lead}</b> {txt}",
                   ParagraphStyle("pt", fontName="Helvetica", fontSize=8.2,
                                  leading=11.5, spaceAfter=4,
                                  textColor=colors.HexColor("#222222"))))
    box = Table([[pts]], colWidths=[PAGE_W - 2*MARGIN])
    box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#E3DAC4")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FBFAF6")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(box)

    # ---- Uma pagina por motel ----
    for m in d["moteis"]:
        story.append(PageBreak())
        _pagina_motel(story, m)

    # ---- Ultima pagina: imprensa ----
    story.append(PageBreak())
    story.append(Paragraph("Imprensa e portais de notícias", S["block"]))
    story.append(Paragraph(d["imprensa"]["subtitle"], S["sub"]))
    if d["imprensa"].get("rows"):
        story.append(_tabela_imprensa(d["imprensa"]["rows"]))
    else:
        story.append(Paragraph(
            "<b>Nenhuma menção encontrada</b> nos portais monitorados no período.", S["leitura"]))
    story.append(Paragraph("<b>Leitura do bloco:</b> " + d["imprensa"].get("leitura", ""),
                           S["leitura"]))

    doc.build(story)


# ==========================================================================
#  Endpoint Flask
# ==========================================================================
app = Flask(__name__)

# Entrega (WhatsApp) - a definir; hoje deixa plugavel via variaveis de ambiente.
WA_PROVIDER = os.environ.get("WA_PROVIDER", "")   # "zapi" | "cloud" | ""(off)


def _entregar(pdf_path):
    """Envio do PDF ao WhatsApp. Implementado apos escolha do provedor."""
    if not WA_PROVIDER:
        return {"delivery": "skipped (WA_PROVIDER nao configurado)"}
    # placeholders — preenchidos quando definirmos Z-API/Cloud API
    return {"delivery": f"provider={WA_PROVIDER} (nao implementado ainda)"}


@app.route("/", methods=["GET"])
def health():
    return "Monitor RAFAN render endpoint OK"


@app.route("/render", methods=["POST"])
def render():
    try:
        raw = request.get_data(as_text=True)
        payload = request.get_json(force=True, silent=True)
        if isinstance(payload, dict) and "moteis" in payload:
            data = payload
        else:
            txt = raw if isinstance(raw, str) else json.dumps(raw)
            data = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
        hoje = datetime.date.today().isoformat()
        out = "/tmp/Monitor RAFAN - " + hoje + ".pdf"
        gerar_monitor_rafan(data, out)
        if WA_PROVIDER:
            deliv = _entregar(out)
            return jsonify({"ok": True, **deliv, "arquivo": os.path.basename(out)})
        # sem canal de entrega: devolve o proprio PDF (testavel ja)
        return send_file(out, mimetype="application/pdf",
                         as_attachment=True, download_name=os.path.basename(out))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/test", methods=["GET"])
def test():
    try:
        data = json.loads(EXEMPLO_JSON)
        hoje = datetime.date.today().isoformat()
        out = "/tmp/Monitor RAFAN - " + hoje + ".pdf"
        gerar_monitor_rafan(data, out)
        return send_file(out, mimetype="application/pdf",
                         as_attachment=True, download_name=os.path.basename(out))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ---- dados de exemplo p/ validar sem gastar credito ----
EXEMPLO_JSON = r'''{
  "intro": "Data de elaboração: <b>1 de julho de 2026</b> | Período monitorado: <b>avaliações, comentários e notícias do dia anterior (30/06/2026)</b>. Este relatório reúne (1) as novas avaliações no Google e (2) os novos comentários no Instagram dos motéis do grupo, classificados em positivos, neutros e negativos, e (3) menções nos portais de imprensa de Brasília. <b>Os títulos e links sublinhados são clicáveis e abrem a fonte.</b>",
  "resumo": {
    "kpis": [["7", "avaliações Google"], ["9", "comentários Instagram"], ["10 / 3 / 3", "pos / neu / neg"], ["4,3★", "nota média Google"]],
    "destaques": [
      ["Saldo do dia:", "as duas unidades tiveram saldo positivo em Google e Instagram. As 3 avaliações/comentários negativos se concentraram no Motel Colorado (demora no check-in e limpeza)."],
      ["Ponto de atenção:", "reclamação recorrente sobre demora no check-in no Motel Colorado aparece tanto no Google quanto no Instagram — 2º registro no mês. Sugere revisar o fluxo da recepção em horário de pico."],
      ["Instagram:", "engajamento saudável no Park Way (elogios à suíte com piscina). No Colorado, um comentário negativo público sobre atendimento ainda sem resposta da página — recomendável responder."],
      ["Imprensa:", "1 menção neutra no Metrópoles citando motéis da região em matéria sobre turismo no DF. Sem repercussão negativa."]
    ]
  },
  "moteis": [
    {
      "nome": "Motel Colorado",
      "subtitle": "Sobradinho/DF — reputação online referente a 30/06/2026.",
      "handle": "@motelcolorado",
      "kpis": [["4", "avaliações Google"], ["4,2★", "nota média"], ["5", "comentários Instagram"]],
      "avaliacoes": [
        {"autor": "Marcelo A.", "nota": 5, "data": "30/06", "comentario": "Suíte impecável, hidro funcionando e atendimento pelo interfone muito rápido. Voltarei com certeza.", "classificacao": "positivo"},
        {"autor": "Anônimo", "nota": 5, "data": "30/06", "comentario": "Melhor custo-benefício da região, limpeza nota 10 e entrada discreta.", "classificacao": "positivo"},
        {"autor": "Patrícia L.", "nota": 3, "data": "30/06", "comentario": "Quarto bom, mas o cardápio demorou quase 40 minutos para chegar. Estrutura ok.", "classificacao": "neutro"},
        {"autor": "João P.", "nota": 2, "data": "30/06", "comentario": "Demora enorme no check-in, fila na entrada e a suíte tinha cheiro de mofo. Recepção despreparada.", "classificacao": "negativo"}
      ],
      "leitura": "reputação estável, mas a demora no check-in aparece pela 2ª vez no mês. Recomenda-se responder publicamente à avaliação negativa e revisar a escala da recepção nos fins de semana.",
      "instagram": [
        {"autor": "@lucas.brasilia", "data": "30/06", "comentario": "Fui no fim de semana, suíte luxo top demais! Recomendo.", "post_url": "https://www.instagram.com/motelcolorado/", "classificacao": "positivo"},
        {"autor": "@ana_paula_ferr", "data": "30/06", "comentario": "Vocês têm suíte com piscina? Qual o valor da diária?", "post_url": "https://www.instagram.com/motelcolorado/", "classificacao": "neutro"},
        {"autor": "@rc_oliveira", "data": "30/06", "comentario": "Demorei quase 30 min pra ser atendido na portaria, poderiam melhorar isso.", "post_url": "https://www.instagram.com/motelcolorado/", "classificacao": "negativo"},
        {"autor": "@marina.df", "data": "30/06", "comentario": "Ambiente lindo e discreto, adoramos!", "post_url": "https://www.instagram.com/motelcolorado/", "classificacao": "positivo"},
        {"autor": "@thiago.santos", "data": "30/06", "comentario": "Promoção de terça ainda está valendo?", "post_url": "https://www.instagram.com/motelcolorado/", "classificacao": "neutro"}
      ],
      "leitura_instagram": "engajamento positivo, mas há 1 comentário público sobre demora no atendimento (mesmo tema do Google) e 2 dúvidas comerciais sem resposta. Sugere-se responder às dúvidas (piscina, promoção) e ao comentário negativo o quanto antes."
    },
    {
      "nome": "Motel Park Way",
      "subtitle": "Núcleo Bandeirante/DF — reputação online referente a 30/06/2026.",
      "handle": "@motelparkwaybsb",
      "kpis": [["3", "avaliações Google"], ["4,5★", "nota média"], ["4", "comentários Instagram"]],
      "avaliacoes": [
        {"autor": "Rafael S.", "nota": 5, "data": "30/06", "comentario": "Suíte premium com piscina privativa excelente, som e iluminação ótimos. Ambiente muito limpo.", "classificacao": "positivo"},
        {"autor": "Anônimo", "nota": 5, "data": "30/06", "comentario": "Atendimento cordial, entrega rápida e discrição total. Recomendo a suíte luxo.", "classificacao": "positivo"},
        {"autor": "Camila R.", "nota": 2, "data": "30/06", "comentario": "Cobraram um valor diferente do combinado no site e a TV da suíte não funcionava.", "classificacao": "negativo"}
      ],
      "leitura": "unidade com reputação forte. A avaliação negativa aponta divergência de preço site x recepção — vale conferir se a tabela online está atualizada para evitar atrito.",
      "instagram": [
        {"autor": "@pedro.hln", "data": "30/06", "comentario": "Essa suíte com piscina é surreal! Já quero reservar.", "post_url": "https://www.instagram.com/motelparkwaybsb/", "classificacao": "positivo"},
        {"autor": "@bia_costa22", "data": "30/06", "comentario": "Que horas fecha a cozinha? Queria pedir algo mais tarde.", "post_url": "https://www.instagram.com/motelparkwaybsb/", "classificacao": "neutro"},
        {"autor": "@jr_almeida", "data": "30/06", "comentario": "Melhor do DF, sempre volto. Estrutura impecável.", "post_url": "https://www.instagram.com/motelparkwaybsb/", "classificacao": "positivo"},
        {"autor": "@lorena.m", "data": "30/06", "comentario": "Fui semana passada e o ar da suíte não gelava direito, fora isso ótimo.", "post_url": "https://www.instagram.com/motelparkwaybsb/", "classificacao": "neutro"}
      ],
      "leitura_instagram": "forte prova social nos comentários (elogios à suíte com piscina). Uma dúvida operacional (horário da cozinha) sem resposta e uma observação leve sobre climatização. Nada crítico — vale só responder à dúvida para não perder a conversão."
    }
  ],
  "imprensa": {
    "subtitle": "Monitoramento de Metrópoles, Correio Braziliense, Jornal de Brasília e demais portais do DF, buscando menções aos motéis e ao grupo RAFAN.",
    "rows": [
      {"titulo": "Turismo no DF: setor de hospedagem aquece no inverno", "url": "https://www.metropoles.com/", "fonte": "Metrópoles<br/>30/06/2026", "resumo": "Matéria sobre a alta ocupação de hotéis e motéis no DF durante o feriado. Cita motéis da região da EPIA de forma genérica, sem apontar o grupo nominalmente. Tom neutro/positivo.", "relevancia": "BAIXA"}
    ],
    "leitura": "sem menções negativas nos portais no período. A citação do Metrópoles é institucional e favorável ao setor. Nenhuma ação necessária."
  }
}'''

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

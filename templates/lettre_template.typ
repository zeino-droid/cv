// Template Lettre de Motivation — Style Français Normé
// Optimisé pour Zein ELAJAMY — Compilation via Typst

// ─── Paramètres dynamiques (Inputs) ───
#let data-path = sys.inputs.at("data-path", default: "_lettre_data.json")
#let theme-name = sys.inputs.at("theme", default: "premium")

// ─── Données JSON ───
#let letter = json(data-path)

// ─── Thèmes ───
#let themes = (
  premium: (
    primary:      rgb("#1a1a2e"),
    secondary:    rgb("#475569"),
    accent:       rgb("#334155"),
    light-line:   rgb("#cbd5e1"),
  ),
  subtle: (
    primary:      rgb("#2d3748"),
    secondary:    rgb("#718096"),
    accent:       rgb("#4a5568"),
    light-line:   rgb("#e2e8f0"),
  ),
  ats: (
    primary:      rgb("#000000"),
    secondary:    rgb("#333333"),
    accent:       rgb("#111111"),
    light-line:   rgb("#cccccc"),
  ),
)

#let resolved-theme = if themes.keys().contains(theme-name) { theme-name } else { "premium" }
#let theme = themes.at(resolved-theme)
#let primary   = theme.at("primary")
#let secondary = theme.at("secondary")
#let accent    = theme.at("accent")
#let light-line = theme.at("light-line")

#set document(
  title: "Lettre de Motivation - " + letter.sender.name,
  author: letter.sender.name,
)

// ─── Page ───
#set page(
  paper: "a4",
  margin: (
    top: 2.5cm,
    bottom: 2.0cm,
    left: 2.5cm,
    right: 2.5cm,
  ),
)

#set text(
  font: ("Noto Serif", "Georgia", "Times New Roman", "serif"),
  size: 11pt,
  lang: "fr",
  fill: primary,
)

#set par(
  justify: true,
  leading: 0.75em,
  first-line-indent: 1em,
)

// ═══════════════════════════════════════════════
// BLOC EXPÉDITEUR — en haut à gauche
// ═══════════════════════════════════════════════
#block(spacing: 0pt)[
  #set par(first-line-indent: 0pt)
  #text(size: 12pt, weight: "bold", fill: primary)[#letter.sender.name]
  #linebreak()
  #set text(size: 10pt, fill: secondary)
  #if letter.sender.at("address", default: "") != "" [
    #letter.sender.address
    #linebreak()
  ]
  #letter.sender.at("location", default: "")
  #linebreak()
  #letter.sender.phone
  #linebreak()
  #letter.sender.email
]

#v(1.2em)

// ═══════════════════════════════════════════════
// BLOC DESTINATAIRE — aligné à droite
// ═══════════════════════════════════════════════
#align(right)[
  #set par(first-line-indent: 0pt)
  #set text(size: 10.5pt)
  #text(weight: "bold", fill: primary)[#letter.recipient.company]
  #linebreak()
  #set text(fill: secondary)
  #if letter.recipient.at("contact_name", default: "") != "" [
    À l'attention de #letter.recipient.contact_name
    #linebreak()
  ]
  #letter.recipient.at("department", default: "Service des Ressources Humaines")
  #if letter.recipient.at("address", default: "") != "" [
    #linebreak()
    #letter.recipient.address
  ]
]

#v(1.0em)

// ═══════════════════════════════════════════════
// LIEU ET DATE — aligné à droite
// ═══════════════════════════════════════════════
#align(right)[
  #set par(first-line-indent: 0pt)
  #text(size: 10.5pt, style: "italic", fill: secondary)[
    #letter.city, le #letter.date
  ]
]

#v(1.5em)

// ═══════════════════════════════════════════════
// OBJET
// ═══════════════════════════════════════════════
#block(spacing: 0pt)[
  #set par(first-line-indent: 0pt)
  #text(size: 10.5pt, weight: "bold", fill: accent)[
    Objet : #letter.subject
  ]
  #if letter.at("reference", default: "") != "" [
    #text(size: 10pt, fill: secondary)[ — Réf. #letter.reference]
  ]
]

#v(1.8em)

// ═══════════════════════════════════════════════
// FORMULE D'APPEL
// ═══════════════════════════════════════════════
#block(spacing: 0pt)[
  #set par(first-line-indent: 0pt)
  #text(weight: "semibold")[#letter.at("salutation", default: "Madame, Monsieur,")]
]

#v(0.8em)

// ═══════════════════════════════════════════════
// CORPS — Paragraphes
// ═══════════════════════════════════════════════
#{
  for (i, para) in letter.paragraphs.enumerate() {
    block(spacing: 0pt)[
      #text(size: 11pt, fill: primary)[#para]
    ]
    if i < letter.paragraphs.len() - 1 {
      v(0.6em)
    }
  }
}

#v(1.2em)

// ═══════════════════════════════════════════════
// FORMULE DE POLITESSE
// ═══════════════════════════════════════════════
#block(spacing: 0pt)[
  #text(size: 11pt, fill: primary)[
    #letter.closing_formula
  ]
]

#v(2.0em)

// ═══════════════════════════════════════════════
// SIGNATURE
// ═══════════════════════════════════════════════
#align(right)[
  #set par(first-line-indent: 0pt)
  #text(size: 12pt, weight: "bold", fill: primary)[#letter.signature_name]
]

// Template CV Premium V5 — Phase 4 (Projets + One-Page)
// Optimisé pour Zein ELAJAMY

// ─── Paramètres dynamiques (Inputs) ───
#let data-path = sys.inputs.at("data-path", default: "_cv_data.json")
#let font-size-delta-raw = sys.inputs.at("font-size-delta", default: "0.0")
#let font-size-delta = float(font-size-delta-raw) * 1pt

// ─── Données JSON ───
#let cv_data = json(data-path)

#set page(
  paper: "a4",
  margin: (top: 1.0cm, bottom: 0.9cm, left: 0cm, right: 1.0cm),
)

#set text(
  font: ("Inter", "Helvetica Neue", "Helvetica", "Arial", "sans-serif"),
  size: 9.0pt + font-size-delta,
  lang: "fr",
  fill: rgb("#334155")
)

#set par(
  justify: false,
  leading: 0.50em,
)

// ─── Couleurs Premium ───
#let primary = rgb("#0f172a")
#let secondary = rgb("#475569")
#let light-bg = rgb("#f1f5f9")
#let divider-color = rgb("#e2e8f0")

// ─── Composants ───
#let pill(text-content) = {
  box(
    inset: (x: 6pt, y: 2.5pt),
    radius: 3pt,
    fill: light-bg,
    text(size: 7.2pt + font-size-delta, weight: "medium", fill: primary, text-content)
  )
}

#let section-title(title) = {
  v(0.6em)
  text(size: 9.5pt + font-size-delta, weight: "bold", fill: primary, tracking: 1.0pt, upper(title))
  v(-0.7em)
  line(length: 100%, stroke: 0.4pt + divider-color)
  v(0.2em)
}

#let sidebar-title(title) = {
  v(0.6em)
  text(size: 8.5pt + font-size-delta, weight: "bold", fill: primary, tracking: 0.5pt, upper(title))
  v(0.2em)
}

#let render-project(proj) = {
  block(spacing: 3.5pt, breakable: false)[
    #grid(
      columns: (1fr, auto),
      gutter: 4pt,
      text(size: 9pt + font-size-delta, weight: "semibold", fill: primary)[#proj.name],
      box(
        fill: divider-color,
        inset: (x: 4pt, y: 1.5pt),
        radius: 2pt,
        text(size: 6.5pt + font-size-delta, fill: secondary, weight: "bold")[PROJET]
      )
    )
    #v(-0.2em)
    #text(size: 8.5pt + font-size-delta, style: "italic", fill: secondary)[#proj.description]
    #v(-0.3em)
    #text(size: 7.8pt + font-size-delta, fill: secondary.lighten(20%))[#proj.keywords]
  ]
}

// ─── Structure ───
#grid(
  columns: (155pt, 1fr),
  // ── COLONNE GAUCHE (SIDEBAR) ──
  rect(
    fill: light-bg,
    width: 100%,
    height: 100%,
    inset: (left: 1.0cm, right: 12pt, top: 1.0cm, bottom: 1.0cm),
    [
      #set align(center)
      #box(
        clip: true,
        radius: 50%,
        stroke: 1.2pt + white,
        image("photo.jpg", width: 2.8cm)
      )
      
      #set align(left)
      #v(1.0em)
      
      #sidebar-title("CONTACT")
      #set text(size: 7.8pt + font-size-delta, fill: secondary)
      #text(weight: "bold", fill: primary, "Email") \
      #cv_data.identity.email \
      #v(0.2em)
      #text(weight: "bold", fill: primary, "Téléphone") \
      #cv_data.identity.phone \
      #v(0.2em)
      #text(weight: "bold", fill: primary, "LinkedIn") \
      #if cv_data.identity.linkedin != none { cv_data.identity.linkedin } else { "zein-elajamy" }
      
      #sidebar-title("COMPÉTENCES")
      #{
        let all_skills = ()
        if cv_data.keys().contains("grouped_skills") {
          for (group, skills) in cv_data.grouped_skills {
              for s in skills { all_skills.push(s.name) }
          }
        }
        set par(spacing: 4pt)
        for s in all_skills.slice(0, calc.min(all_skills.len(), 12)) {
          pill(s) 
          h(2pt)
        }
      }
      
      #sidebar-title("LANGUES")
      #{
        if cv_data.keys().contains("languages") {
            for l in cv_data.languages {
              text(size: 8.2pt + font-size-delta, weight: "bold", fill: primary, l.name)
              v(-0.7em)
              text(size: 7.8pt + font-size-delta, fill: secondary, l.level)
              v(0.2em)
            }
        }
      }
    ]
  ),
  
  // ── COLONNE DROITE (CONTENU PRINCIPAL) ──
  pad(
    left: 15pt,
    top: 1.0cm,
    [
      #text(size: 22pt + font-size-delta, weight: "black", fill: primary, tracking: -0.5pt, upper(cv_data.identity.name))
      #v(-0.5em)
      #text(size: 10.5pt + font-size-delta, weight: "bold", fill: secondary, cv_data.headline)
      
      #section-title("RÉSUMÉ")
      #text(size: 9.2pt + font-size-delta, fill: secondary, weight: "medium", cv_data.summary)
      
      #v(0.4em)
      
      #section-title("EXPÉRIENCES")
      #{
        if cv_data.keys().contains("experiences") {
            for exp in cv_data.experiences {
              grid(
                columns: (1fr, auto),
                text(size: 9.5pt + font-size-delta, weight: "bold", fill: primary, exp.position),
                text(size: 8.2pt + font-size-delta, weight: "medium", fill: secondary, exp.start_date + " — " + exp.end_date)
              )
              v(-0.45em)
              text(size: 9.2pt + font-size-delta, weight: "bold", fill: primary, exp.company)
              v(0.1em)
              
              if exp.keys().contains("achievements") {
                  for ach in exp.achievements {
                    grid(
                      columns: (7pt, 1fr),
                      text(size: 8.5pt + font-size-delta, fill: primary, "•"),
                      text(size: 8.8pt + font-size-delta, fill: secondary, ach)
                    )
                    v(0.02em)
                  }
              }
              v(0.3em)
            }
        }
      }

      #if cv_data.keys().contains("projects") and cv_data.projects.len() > 0 {
        section-title("PROJETS TECHNIQUES")
        for proj in cv_data.projects {
          render-project(proj)
          v(0.3em)
        }
      }
      
      #section-title("FORMATION")
      #{
        if cv_data.keys().contains("education") {
            for edu in cv_data.education {
              grid(
                columns: (1fr, auto),
                text(size: 9.2pt + font-size-delta, weight: "bold", fill: primary, edu.degree),
                text(size: 8.2pt + font-size-delta, weight: "medium", fill: secondary, edu.year)
              )
              v(-0.45em)
              text(size: 8.8pt + font-size-delta, weight: "medium", fill: primary, edu.school)
              if edu.keys().contains("details") and edu.details != "" {
                  v(-0.3em)
                  text(size: 8.2pt + font-size-delta, fill: secondary, edu.details)
              }
              v(0.2em)
            }
        }
      }
    ]
  )
)

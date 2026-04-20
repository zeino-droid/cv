// Template CV Premium — Style Moderne (Apple / Nike / Minimal)
// Optimisé pour la garantie One-Page

// ─── Paramètres dynamiques (Inputs) ───
#let data-path = sys.inputs.at("data-path", default: "_cv_data.json")
#let font-size-delta-raw = sys.inputs.at("font-size-delta", default: "0.0")
#let font-size-delta = float(font-size-delta-raw) * 1pt // Conversion float -> length

// ─── Données JSON ───
#let cv = json(data-path)

#set page(
  paper: "a4",
  margin: (top: 1.1cm, bottom: 1.0cm, left: 0cm, right: 1.1cm),
)

#set text(
  font: ("Inter", "Helvetica Neue", "Helvetica", "Arial", "sans-serif"),
  size: 9.2pt + font-size-delta,
  lang: "fr",
  fill: rgb("#334155")
)

#set par(
  justify: false,
  leading: 0.52em,
)

// ─── Couleurs Premium ───
#let primary = rgb("#0f172a") // Deep slate
#let secondary = rgb("#475569") // slate-600
#let light-bg = rgb("#f1f5f9") // slate-100 for pills
#let divider-color = rgb("#e2e8f0")

// ─── Composants ───
#let pill(text-content) = {
  box(
    inset: (x: 7pt, y: 3pt),
    radius: 3pt,
    fill: light-bg,
    text(size: 7.5pt + font-size-delta, weight: "medium", fill: primary, text-content)
  )
}

#let section-title(title) = {
  v(0.8em)
  text(size: 10pt + font-size-delta, weight: "bold", fill: primary, tracking: 1.2pt, upper(title))
  v(-0.6em)
  line(length: 100%, stroke: 0.5pt + divider-color)
  v(0.3em)
}

#let sidebar-title(title) = {
  v(0.7em)
  text(size: 9pt + font-size-delta, weight: "bold", fill: primary, tracking: 0.5pt, upper(title))
  v(0.25em)
}

// ─── Structure ───
#grid(
  columns: (160pt, 1fr),
  // ── COLONNE GAUCHE (SIDEBAR AVEC FOND) ──
  rect(
    fill: light-bg,
    width: 100%,
    height: 100%,
    inset: (left: 1.1cm, right: 15pt, top: 1.1cm, bottom: 1.1cm),
    [
      #set align(center)
      #box(
        clip: true,
        radius: 50%,
        stroke: 1.5pt + white,
        image("photo.jpg", width: 3.0cm)
      )
      
      #set align(left)
      #v(1.2em)
      
      #sidebar-title("CONTACT")
      #set text(size: 8pt + font-size-delta, fill: secondary)
      #text(weight: "bold", fill: primary, "Email") \
      #cv.identity.email \
      #v(0.3em)
      #text(weight: "bold", fill: primary, "Téléphone") \
      #cv.identity.phone \
      #v(0.3em)
      #text(weight: "bold", fill: primary, "Localisation") \
      #cv.identity.location \
      #v(0.3em)
      #text(weight: "bold", fill: primary, "LinkedIn") \
      #if cv.identity.linkedin != none { cv.identity.linkedin } else { "zein-elajamy" }
      
      #sidebar-title("COMPÉTENCES")
      #{
        let all_skills = ()
        if cv.keys().contains("grouped_skills") {
          for (group, skills) in cv.grouped_skills {
              for s in skills {
                all_skills.push(s.name)
              }
          }
        }
        
        set par(spacing: 5pt)
        for s in all_skills {
          pill(s) 
          h(2pt)
        }
      }
      
      #sidebar-title("LANGUES")
      #{
        if cv.keys().contains("languages") {
            for l in cv.languages {
              text(size: 8.5pt + font-size-delta, weight: "bold", fill: primary, l.name)
              v(-0.65em)
              text(size: 8pt + font-size-delta, fill: secondary, l.level)
              v(0.3em)
            }
        }
      }
    ]
  ),
  
  // ── COLONNE DROITE (CONTENU PRINCIPAL) ──
  pad(
    left: 18pt,
    top: 1.1cm,
    [
      #text(size: 24pt + font-size-delta, weight: "black", fill: primary, tracking: -0.8pt, upper(cv.identity.name))
      #v(-0.45em)
      #text(size: 11pt + font-size-delta, weight: "bold", fill: secondary, cv.headline)
      
      #section-title("RÉSUMÉ")
      #text(size: 9.5pt + font-size-delta, fill: secondary, weight: "medium", cv.summary)
      
      #v(0.5em)
      
      #section-title("EXPÉRIENCES")
      #{
        if cv.keys().contains("experiences") {
            for exp in cv.experiences {
              grid(
                columns: (1fr, auto),
                text(size: 10pt + font-size-delta, weight: "bold", fill: primary, exp.position),
                text(size: 8.5pt + font-size-delta, weight: "medium", fill: secondary, exp.start_date + " — " + exp.end_date)
              )
              v(-0.4em)
              text(size: 9.5pt + font-size-delta, weight: "bold", fill: primary, exp.company)
              if exp.keys().contains("location") and exp.location != "" {
                h(4pt) 
                text(size: 8.5pt + font-size-delta, fill: secondary, "• " + exp.location)
              }
              v(0.15em)
              
              if exp.keys().contains("achievements") {
                  for ach in exp.achievements.slice(0, calc.min(exp.achievements.len(), 3)) {
                    let clean = ach
                    if type(ach) == str and ach.starts-with("•") { clean = ach.slice(3).trim() }
                    grid(
                      columns: (8pt, 1fr),
                      text(fill: primary, "•"),
                      text(size: 9pt + font-size-delta, fill: secondary, clean)
                    )
                    v(0.05em)
                  }
              }
              v(0.4em)
            }
        }
      }
      
      #section-title("FORMATION")
      #{
        if cv.keys().contains("education") {
            for edu in cv.education {
              grid(
                columns: (1fr, auto),
                text(size: 9.5pt + font-size-delta, weight: "bold", fill: primary, edu.degree),
                text(size: 8.5pt + font-size-delta, weight: "medium", fill: secondary, edu.year)
              )
              v(-0.4em)
              text(size: 9pt + font-size-delta, weight: "medium", fill: primary, edu.school)
              v(0.05em)
              if edu.keys().contains("details") {
                  text(size: 8.5pt + font-size-delta, fill: secondary, edu.details)
              }
              v(0.3em)
            }
        }
      }
      
      #section-title("PROJETS")
      #{
        if cv.keys().contains("projects") {
            for proj in cv.projects.slice(0, calc.min(cv.projects.len(), 2)) {
              text(size: 9.5pt + font-size-delta, weight: "bold", fill: primary, proj.name)
              v(0.1em)
              if proj.keys().contains("description") {
                  text(size: 8.5pt + font-size-delta, fill: secondary, proj.description)
              }
              v(0.3em)
            }
        }
      }
    ]
  )
)

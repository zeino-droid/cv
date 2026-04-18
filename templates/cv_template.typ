// Template CV Premium — Style Moderne (Apple / Nike / Minimal)
#set page(
  paper: "a4",
  margin: (top: 1.2cm, bottom: 1.2cm, left: 0cm, right: 1.2cm), // Sidebar will touch the edge
)

#set text(
  font: ("Inter", "Helvetica Neue", "Helvetica", "Arial", "sans-serif"),
  size: 9.6pt,
  lang: "fr",
  fill: rgb("#334155")
)

#set par(
  justify: false,
  leading: 0.55em,
)

// ─── Données JSON ───
#let data-path = sys.inputs.at("data-path", default: "_cv_data.json")
#let cv = json(data-path)

// ─── Couleurs Premium ───
#let primary = rgb("#0f172a") // Deep slate (almost black)
#let secondary = rgb("#475569") // slate-600
#let light-bg = rgb("#f1f5f9") // slate-100 for pills
#let divider-color = rgb("#e2e8f0")

// ─── Composants ───
#let pill(text-content) = {
  box(
    inset: (x: 8pt, y: 4pt),
    radius: 4pt,
    fill: light-bg,
    text(size: 8pt, weight: "medium", fill: primary, text-content)
  )
}

#let section-title(title) = {
  v(1em)
  text(size: 10.5pt, weight: "bold", fill: primary, tracking: 1.5pt, upper(title))
  v(-0.55em)
  line(length: 100%, stroke: 0.6pt + divider-color)
  v(0.4em)
}

#let sidebar-title(title) = {
  v(0.8em)
  text(size: 9.5pt, weight: "bold", fill: primary, tracking: 0.5pt, upper(title))
  v(0.3em)
}

// ─── Structure ───
#grid(
  columns: (170pt, 1fr),
  // ── COLONNE GAUCHE (SIDEBAR AVEC FOND) ──
  rect(
    fill: light-bg,
    width: 100%,
    height: 100%,
    inset: (left: 1.2cm, right: 18pt, top: 1.2cm, bottom: 1.2cm),
    [
      #set align(center)
      #box(
        clip: true,
        radius: 50%, // Photo ronde pour le style premium
        stroke: 2pt + white,
        image("photo.jpg", width: 3.2cm)
      )
      
      #set align(left)
      #v(1.5em)
      
      #sidebar-title("CONTACT")
      #set text(size: 8.5pt, fill: secondary)
      #text(weight: "bold", fill: primary, "Email") \
      #cv.identity.email \
      #v(0.4em)
      #text(weight: "bold", fill: primary, "Téléphone") \
      #cv.identity.phone \
      #v(0.4em)
      #text(weight: "bold", fill: primary, "Localisation") \
      #cv.identity.location \
      #v(0.4em)
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
        
        set par(spacing: 6pt)
        for s in all_skills {
          pill(s) 
          h(2pt)
        }
      }
      
      #sidebar-title("LANGUES")
      #{
        if cv.keys().contains("languages") {
            for l in cv.languages {
              text(size: 9pt, weight: "bold", fill: primary, l.name)
              v(-0.6em)
              text(size: 8.5pt, fill: secondary, l.level)
              v(0.4em)
            }
        }
      }
    ]
  ),
  
  // ── COLONNE DROITE (CONTENU PRINCIPAL) ──
  pad(
    left: 20pt,
    top: 1.2cm,
    [
      #text(size: 28pt, weight: "black", fill: primary, tracking: -1pt, upper(cv.identity.name))
      #v(-0.4em)
      #text(size: 12pt, weight: "bold", fill: secondary, cv.headline)
      
      #section-title("RÉSUMÉ")
      #text(size: 10pt, fill: secondary, weight: "medium", cv.summary)
      
      #v(0.6em)
      
      #v(0.2fr) // Dynamic space
      #section-title("EXPÉRIENCES")
      #{
        if cv.keys().contains("experiences") {
            for exp in cv.experiences {
              grid(
                columns: (1fr, auto),
                text(size: 11pt, weight: "bold", fill: primary, exp.position),
                text(size: 9pt, weight: "medium", fill: secondary, exp.start_date + " — " + exp.end_date)
              )
              v(-0.35em)
              text(size: 10pt, weight: "bold", fill: primary, exp.company)
              if exp.keys().contains("location") and exp.location != "" {
                h(4pt) 
                text(size: 9pt, fill: secondary, "• " + exp.location)
              }
              v(0.2em)
              
              if exp.keys().contains("achievements") {
                  for ach in exp.achievements.slice(0, calc.min(exp.achievements.len(), 4)) {
                    let clean = ach
                    if type(ach) == str and ach.starts-with("•") { clean = ach.slice(3).trim() }
                    grid(
                      columns: (10pt, 1fr),
                      text(fill: primary, "•"),
                      text(size: 9.2pt, fill: secondary, clean)
                    )
                    v(0.1em)
                  }
              }
              v(0.6em)
            }
        }
      }
      
      #v(0.2fr) // Dynamic space
      #section-title("FORMATION")
      #{
        if cv.keys().contains("education") {
            for edu in cv.education {
              grid(
                columns: (1fr, auto),
                text(size: 10pt, weight: "bold", fill: primary, edu.degree),
                text(size: 9pt, weight: "medium", fill: secondary, edu.year)
              )
              v(-0.35em)
              text(size: 9.5pt, weight: "medium", fill: primary, edu.school)
              v(0.1em)
              if edu.keys().contains("details") {
                  text(size: 9pt, fill: secondary, edu.details)
              }
              v(0.5em)
            }
        }
      }
      
      #v(0.2fr) // Dynamic space
      #section-title("PROJETS")
      #{
        if cv.keys().contains("projects") {
            for proj in cv.projects.slice(0, calc.min(cv.projects.len(), 2)) {
              text(size: 10pt, weight: "bold", fill: primary, proj.name)
              v(0.15em)
              if proj.keys().contains("description") {
                  text(size: 9pt, fill: secondary, proj.description)
              }
              v(0.4em)
            }
        }
      }
    ]
  )
)

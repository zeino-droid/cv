// Template CV Premium — Style Moderne (Apple / Nike / Minimal)
#set page(
  paper: "a4",
  margin: (top: 0.8cm, bottom: 0.8cm, left: 1cm, right: 1cm),
)

#set text(
  font: ("Inter", "Helvetica Neue", "Helvetica", "Arial", "sans-serif"),
  size: 8.4pt,
  lang: "fr",
  fill: rgb("#334155")
)

#set par(
  justify: false,
  leading: 0.4em,
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
  v(0.3em)
  text(size: 9pt, weight: "bold", fill: primary, tracking: 1pt, upper(title))
  v(-0.7em)
  line(length: 100%, stroke: 0.4pt + divider-color)
  v(0.1em)
}

#let sidebar-title(title) = {
  v(0.4em)
  text(size: 8.5pt, weight: "bold", fill: primary, tracking: 0.5pt, upper(title))
  v(0.1em)
}

// ─── Structure ───
#grid(
  columns: (180pt, 1fr),
  gutter: 35pt,
  // ── COLONNE GAUCHE (SIDEBAR) ──
  [
    #set align(center)
    #v(0.5em)
    #box(
      clip: true,
      radius: 8pt,
      image("photo.jpg", width: 3.5cm)
    )
    
    #set align(left)
    #v(1em)
    
    #sidebar-title("CONTACT")
    #set text(size: 9pt, fill: secondary)
    #text(weight: "medium", fill: primary, "Email") \
    #cv.identity.email \
    #v(0.3em)
    #text(weight: "medium", fill: primary, "Téléphone") \
    #cv.identity.phone \
    #v(0.3em)
    #text(weight: "medium", fill: primary, "Localisation") \
    #cv.identity.location \
    #v(0.3em)
    #text(weight: "medium", fill: primary, "LinkedIn") \
    #if cv.identity.linkedin != none { cv.identity.linkedin } else { "linkedin.com/in/zein-elajamy" }
    
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
        h(3pt)
      }
    }
    
    #sidebar-title("LANGUES")
    #{
      if cv.keys().contains("languages") {
          for l in cv.languages {
            text(size: 9pt, weight: "bold", fill: primary, l.name)
            v(-0.6em)
            text(size: 8.5pt, fill: secondary, l.level)
            v(0.3em)
          }
      }
    }
  ],
  
  // ── COLONNE DROITE (CONTENU PRINCIPAL) ──
  [
    #v(0.5em)
    #text(size: 24pt, weight: "black", fill: primary, tracking: -1pt, upper(cv.identity.name))
    #v(-0.6em)
    #grid(
      columns: (1fr),
      text(size: 10.5pt, weight: "medium", fill: secondary, cv.headline),
      v(-0.3em),
      text(size: 8.2pt, fill: secondary, style: "italic", cv.summary)
    )
    
    #section-title("EXPÉRIENCES")
    #{
      if cv.keys().contains("experiences") {
          for exp in cv.experiences {
            grid(
              columns: (1fr, auto),
              text(size: 11.5pt, weight: "bold", fill: primary, exp.position),
              text(size: 9.5pt, weight: "medium", fill: secondary, exp.start_date + " — " + exp.end_date)
            )
            v(-0.35em)
            text(size: 10pt, weight: "bold", fill: primary, exp.company)
            if exp.keys().contains("location") and exp.location != "" {
              h(4pt) 
              text(size: 9.5pt, fill: secondary, "• " + exp.location)
            }
            v(0.4em)
            
            if exp.keys().contains("achievements") {
                for ach in exp.achievements.slice(0, calc.min(exp.achievements.len(), 4)) {
                  let clean = ach
                  if type(ach) == str and ach.starts-with("•") { clean = ach.slice(3).trim() }
                  grid(
                    columns: (12pt, 1fr),
                    text(fill: primary, "•"),
                    text(size: 9.5pt, fill: secondary, clean)
                  )
                  v(0.1em)
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
              text(size: 10pt, weight: "bold", fill: primary, edu.degree),
              text(size: 9.5pt, weight: "medium", fill: secondary, edu.year)
            )
            v(-0.35em)
            text(size: 10pt, weight: "medium", fill: primary, edu.school)
            v(0.1em)
            if edu.keys().contains("details") {
                text(size: 9.5pt, fill: secondary, edu.details)
            }
            v(0.3em)
          }
      }
    }
    
    #section-title("PROJETS")
    #{
      if cv.keys().contains("projects") {
          for proj in cv.projects.slice(0, calc.min(cv.projects.len(), 2)) {
            text(size: 10.5pt, weight: "bold", fill: primary, proj.name)
            v(0.2em)
            set par(spacing: 5pt)
            if proj.keys().contains("technologies") {
                for tech in proj.technologies {
                  pill(tech)
                  h(3pt)
                }
            }
            v(0.3em)
            if proj.keys().contains("description") {
                text(size: 9.5pt, fill: secondary, proj.description)
            }
            v(0.3em)
          }
      }
    }
  ]
)

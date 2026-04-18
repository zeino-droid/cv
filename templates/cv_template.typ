// ──────────────────────────────────────────────────────────────
// Template CV Premium — Deux Colonnes — Typst (v3)
// Optimisé pour : Remplissage visuel, Lisibilité, Professionnalisme
// ──────────────────────────────────────────────────────────────

#set page(
  paper: "a4",
  margin: (top: 1cm, bottom: 0.8cm, left: 1cm, right: 1cm),
)

#set text(
  font: "New Computer Modern",
  size: 9pt,
  lang: "fr",
)

#set par(
  justify: true,
  leading: 0.45em,
)

// ─── Données JSON ───
#let data-path = sys.inputs.at("data-path", default: "_cv_data.json")
#let cv = json(data-path)

// ─── Couleurs ───
#let primary-color = rgb("#1a365d")
#let secondary-color = rgb("#2b6cb0")
#let sidebar-gray = rgb("#f8fafc")
#let text-dark = rgb("#1e293b")
#let text-light = rgb("#64748b")
#let accent-light = rgb("#e2e8f0")

// ─── Composants Visuels ───

// Barre de niveau (Skill Progress Bar)
#let skill-bar(name, level) = {
  v(0.1em)
  grid(
    columns: (1fr, 40pt),
    gutter: 5pt,
    text(size: 8pt, weight: "medium", name),
    box(width: 40pt, height: 4pt, fill: accent-light, radius: 2pt, {
      box(width: (level / 5 * 40pt), height: 4pt, fill: secondary-color, radius: 2pt)
    })
  )
}

// Badge compact
#let compact-badge(name) = {
  box(
    inset: (x: 4pt, y: 1.5pt),
    radius: 2pt,
    fill: white,
    stroke: 0.5pt + accent-light,
    text(size: 7.5pt, fill: primary-color, name)
  )
}

// Titre de section (Sidebar)
#let sidebar-title(title) = {
  v(0.6em)
  text(size: 9pt, weight: "bold", fill: primary-color, upper(title))
  v(-0.35em)
  line(length: 100%, stroke: 1.5pt + secondary-color)
  v(0.3em)
}

// Titre de section (Main)
#let main-title(title) = {
  v(0.4em)
  text(size: 11pt, weight: "bold", fill: primary-color, upper(title))
  v(-0.4em)
  line(length: 100%, stroke: 0.8pt + secondary-color)
  v(0.2em)
}

// ─────────────────────────────────────────────────────────────
// ── STRUCTURE PRINCIPALE ──
// ─────────────────────────────────────────────────────────────

#grid(
  columns: (190pt, 1fr),
  gutter: 20pt,
  
  // ── COLONNE GAUCHE (SIDEBAR) ──
  [
    #set align(center)
    #v(0.5em)
    #box(
      clip: true,
      radius: 50%,
      stroke: 2pt + secondary-color,
      image("photo.jpg", width: 4.5cm)
    )
    
    #set align(left)
    #v(1em)
    
    #sidebar-title("Contact")
    #set text(size: 8pt, fill: text-dark)
    📞 #cv.identity.phone \
    📧 #text(size: 7.5pt, cv.identity.email) \
    📍 #cv.identity.location \
    🔗 #if cv.identity.linkedin != none { cv.identity.linkedin } else { "linkedin.com/in/zein-elajamy" }
    
    #sidebar-title("Expertise Technique")
    #{
      for skill in cv.grouped_skills.at("Expertise Technique") {
        skill-bar(skill.name, skill.level)
      }
    }
    
    #sidebar-title("Outils & Digital")
    #{
      for skill in cv.grouped_skills.at("Outils & Digital") {
        skill-bar(skill.name, skill.level)
      }
    }
    
    #sidebar-title("Langues")
    #{
      for l in cv.languages {
        let level_int = if l.level.contains("C1") or l.level.contains("maternelle") { 5 } else { 4 }
        skill-bar(l.name, level_int)
      }
    }
    
    #sidebar-title("Certifications")
    #set text(size: 7.5pt)
    #{
      for cert in cv.certifications {
        [• *#cert.name* (#cert.date) \ ]
      }
    }
    
    #sidebar-title("Centres d'intérêt")
    #set text(size: 8pt)
    🏀 Basketball (Compétition) \
    🎸 Guitare & Musique \
    🚗 Sport Automobile & Tech \
    🌍 Voyages & Diversité Cult.
  ],
  
  // ── COLONNE DROITE (CONTENU) ──
  [
    #v(0.2em)
    #text(size: 24pt, weight: "bold", fill: primary-color, upper(cv.identity.name))
    #v(-0.4em)
    #text(size: 11pt, weight: "bold", fill: secondary-color, hyphenate: false, cv.headline)
    
    #main-title("Résumé Professionnel")
    #text(size: 8.8pt, cv.summary)
    
    #main-title("Expériences Professionnelles")
    #{
      for exp in cv.experiences {
        // Ligne 1 : Titre du poste (Pleine largeur)
        text(size: 10pt, weight: "bold", fill: primary-color, hyphenate: false, exp.position)
        v(-0.35em)
        
        // Ligne 2 : Entreprise (Gauche) et Dates (Droite)
        grid(
          columns: (1fr, auto),
          text(size: 9pt, weight: "bold", style: "italic", fill: secondary-color, exp.company),
          text(size: 8.5pt, fill: text-light, weight: "bold", exp.start_date + " — " + exp.end_date)
        )
        
        v(0.1em)
        for ach in exp.achievements {
          let clean = if ach.starts-with("•") { ach } else { "• " + ach }
          text(size: 8.5pt, clean)
          v(0.15em)
        }
        v(0.4em)
      }
    }
    
    #main-title("Formation Académique")
    #{
      for edu in cv.education {
        grid(
          columns: (1fr, auto),
          [*#text(size: 9pt, fill: primary-color, edu.degree + " — " + edu.field)*],
          [*#text(size: 8.5pt, fill: text-light, edu.year)*]
        )
        v(-0.2em)
        text(size: 8.5pt, style: "italic", edu.school)
        linebreak()
        text(size: 8pt, fill: text-dark, edu.details)
        v(0.4em)
      }
    }
    
    #main-title("Projets Significatifs")
    #{
      for proj in cv.projects {
        text(size: 8.5pt, weight: "bold", fill: primary-color, proj.name)
        h(0.5em)
        for tech in proj.technologies {
          compact-badge(tech)
        }
        list(tight: true, marker: [$-$], text(size: 8pt, proj.description))
        v(0.2em)
      }
    }
  ]
)

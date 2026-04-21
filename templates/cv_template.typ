// Template CV Premium V5 — Phase 4 (Projets + One-Page)
// Optimisé pour Zein ELAJAMY

// ─── Paramètres dynamiques (Inputs) ───
#let data-path          = sys.inputs.at("data-path",       default: "_cv_data.json")
#let font-size-delta    = float(sys.inputs.at("font-size-delta", default: "0.0"))  * 1pt
#let leading-val        = float(sys.inputs.at("leading",        default: "0.58"))  * 1em
#let section-gap-val    = float(sys.inputs.at("section-gap",    default: "18.0"))  * 1pt
#let margin-sides-val   = float(sys.inputs.at("margin-sides",   default: "14.0"))  * 1pt

// ─── Données JSON ───
#let cv_data = json(data-path)

#set page(
  paper: "a4",
  margin: (
    top: 1.0cm,
    bottom: 0.9cm,
    left: 0cm,
    right: margin-sides-val,
  ),
)

#set text(
  font: ("Inter", "Helvetica Neue", "Helvetica", "Arial", "sans-serif"),
  size: 9.0pt + font-size-delta,
  lang: "fr",
  fill: rgb("#334155")
)

#set par(
  justify: false,
  leading: leading-val,
)

// ─── Couleurs Premium ───
#let primary = rgb("#0f172a")
#let secondary = rgb("#475569")
#let light-bg = rgb("#f1f5f9")
#let divider-color = rgb("#e2e8f0")

// ─── Composants ───
#let pill(text-content) = {
  box(
    inset: (x: 5pt, y: 1.8pt),
    radius: 3pt,
    fill: light-bg,
    text(size: 7.5pt + font-size-delta, weight: "medium", fill: primary, text-content)
  )
}

#let section-title(title) = {
  v(section-gap-val)
  text(size: 10.0pt + font-size-delta, weight: "bold", fill: primary, tracking: 1.0pt, upper(title))
  v(-0.7em)
  line(length: 100%, stroke: 0.4pt + divider-color)
  v(0.2em)
}

#let sidebar-title(title) = {
  v(0.8em)
  text(size: 9.0pt + font-size-delta, weight: "bold", fill: primary, tracking: 0.5pt, upper(title))
  v(0.3em)
}

#let render-project(proj, index) = {
  block(spacing: 2.0pt, breakable: false)[
    // En-tête compacte avec numéro
    #grid(
      columns: (auto, 1fr, auto),
      gutter: 4pt,
      text(size: 8.0pt, fill: secondary, "[" + str(index + 1) + "]"),
      text(size: 9.5pt, weight: "semibold", fill: primary)[#proj.name],
      box(
        fill: divider-color,
        inset: (x: 4pt, y: 1.5pt),
        radius: 2pt,
        text(size: 7.0pt, fill: secondary, weight: "bold")[PROJET]
      )
    )
    // Description conditionnelle (si présente)
    #if proj.description != "" and proj.description != none {
      v(0.25em)
      text(size: 8.5pt, style: "italic", fill: secondary)[#proj.description]
    }
    // Keywords toujours affichés, proches du titre
    #v(0.2em)
    #text(size: 9.0pt, fill: secondary)[#proj.keywords]
  ]
  // Ligne de séparation fine après chaque projet
  line(length: 100%, stroke: 0.3pt + divider-color.lighten(40%))
  v(0.85em)
}

// ─── Structure ───
#grid(
  columns: (155pt, 1fr),
   // ── COLONNE GAUCHE (SIDEBAR) ──
   rect(
     fill: light-bg,
     width: 100%,
     height: 100%,
     inset: (left: 1.0cm, right: 10pt, top: 0.4cm, bottom: 0.5cm),
     [
       #set align(center)
       #box(
         clip: true,
         radius: 50%,
         stroke: 1.2pt + white,
         image("photo.jpg", width: 2.9cm)
       )

       #set align(left)
       #v(0.6em)

       #sidebar-title("CONTACT")
       #set text(size: 8.0pt + font-size-delta, fill: secondary)
       #text(weight: "bold", fill: primary, "Email") \
       #cv_data.identity.email \
       #v(0.15em)
       #text(weight: "bold", fill: primary, "Téléphone") \
       #cv_data.identity.phone \
       #v(0.15em)
       #text(weight: "bold", fill: primary, "LinkedIn") \
       #if cv_data.identity.linkedin != none { cv_data.identity.linkedin } else { "zein-elajamy" }

       #sidebar-title("MOBILITÉ")
       #set text(size: 8.0pt + font-size-delta, fill: secondary)
       #text("Mobilité nationale") \
       #v(0.15em)

        #{
          if cv_data.keys().contains("grouped_skills") {
            for (group_name, skills) in cv_data.grouped_skills {
              sidebar-title(upper(group_name))
              for s in skills {
                pill(s.name)
                h(1.5pt)
              }
              v(0.1em)
            }
          }
        }

        #{
          if cv_data.keys().contains("soft_skills") and cv_data.soft_skills.len() > 0 {
            sidebar-title("SOFT SKILLS")
            for ss in cv_data.soft_skills {
              pill(ss)
              h(1.5pt)
            }
            v(0.1em)
          }
        }

        #{
          sidebar-title("LANGUES")
          if cv_data.keys().contains("languages") {
            for l in cv_data.languages {
              text(size: 8.0pt + font-size-delta, weight: "bold", fill: primary, l.name)
              v(-0.6em)
              text(size: 8.0pt + font-size-delta, fill: secondary, l.level)
              v(0.15em)
            }
          }
        }

        #{
          if cv_data.keys().contains("hobbies") and cv_data.hobbies.len() > 0 {
            sidebar-title("LOISIRS")
            set text(size: 8.0pt + font-size-delta, fill: secondary)
            for hobby in cv_data.hobbies {
              text(hobby)
              v(0.1em)
            }
          }
        }
        
        v(1fr)
        align(center, text(size: 6pt, fill: secondary.lighten(30%), "VER 5.1.b (SPACING_FIXED)"))
     ]
   ),

  // ── COLONNE DROITE (CONTENU PRINCIPAL) ──
  pad(
    left: 15pt,
    top: 1.8cm,
    [
      #text(size: 22pt + font-size-delta, weight: "black", fill: primary, tracking: -0.5pt, upper(cv_data.identity.name))
      #v(-0.5em)
      #text(size: 10.5pt + font-size-delta, weight: "bold", fill: secondary, cv_data.headline)

      #v(0.5em)
      #section-title("RÉSUMÉ")
      #text(size: 9.8pt + font-size-delta, fill: secondary, weight: "medium", cv_data.summary)

      #v(1.4em)

      #section-title("EXPÉRIENCES")
      #{
        if cv_data.keys().contains("experiences") {
            for (i, exp) in cv_data.experiences.enumerate() {
              let same_company = i > 0 and exp.company == cv_data.experiences.at(i - 1).company
              grid(
                columns: (1fr, auto),
                text(size: 10.2pt + font-size-delta, weight: "bold", fill: primary, exp.position),
                text(size: 9.5pt + font-size-delta, weight: "medium", fill: secondary, exp.start_date + " — " + exp.end_date)
              )
              v(-0.45em)
              if not same_company {
                text(size: 9.8pt + font-size-delta, weight: "bold", fill: primary, exp.company)
                v(0.1em)
              } else {
                v(-0.3em)
              }

              if exp.keys().contains("achievements") {
                  for ach in exp.achievements {
                    grid(
                      columns: (7pt, 1fr),
                      text(size: 9.5pt + font-size-delta, fill: primary, "•"),
                      text(size: 9.8pt + font-size-delta, fill: secondary, ach)
                    )
                    v(0.12em)
                  }
              }
              v(0.65em)
            }
        }
      }

      #if cv_data.keys().contains("projects") and cv_data.projects.len() > 0 {
        v(0.8em)
        section-title("PROJETS TECHNIQUES")
        for (i, proj) in cv_data.projects.enumerate() {
          render-project(proj, i)
        }
      }

      #v(0.8em)
      #section-title("FORMATION")
      #{
        if cv_data.keys().contains("education") {
            for edu in cv_data.education {
              grid(
                columns: (1fr, auto),
                text(size: 10.2pt + font-size-delta, weight: "bold", fill: primary, edu.degree),
                text(size: 9.5pt + font-size-delta, weight: "medium", fill: secondary, edu.year)
              )
              v(-0.45em)
              text(size: 9.8pt + font-size-delta, weight: "medium", fill: primary, edu.school)
              if edu.keys().contains("specialization") and edu.specialization != none and edu.specialization != "" {
                  v(-0.3em)
                  text(size: 9.5pt + font-size-delta, weight: "semibold", fill: secondary.lighten(10%), edu.specialization)
              }
              if edu.keys().contains("details") and edu.details != "" {
                  v(-0.3em)
                  text(size: 9.2pt + font-size-delta, fill: secondary, edu.details)
              }
              if edu.keys().contains("modules") and edu.modules != () and edu.modules != [] {
                  let mods = edu.modules
                  let all_mods = if type(mods) == "dictionary" {
                    // Flatten S5_S6, S7_S8, S9 arrays
                    let arr = ()
                    for v in mods.values() { arr += v }
                    arr
                  } else if type(mods) == "array" {
                    mods
                  } else {
                    ()
                  }
                  if all_mods.len() > 0 {
                    v(-0.2em)
                    set text(size: 9.5pt + font-size-delta, fill: secondary.lighten(10%))
                    for mod in all_mods.slice(0, 6) {
                      text("· " + mod)
                      v(0.05em)
                    }
                  }
              }
              v(0.2em)
            }
        }
      }
    ]
  )
)

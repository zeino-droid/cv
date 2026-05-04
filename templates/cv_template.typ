// Template CV Premium V5 — Phase 4 (Projets + One-Page)
// Optimisé pour Zein ELAJAMY

// ─── Paramètres dynamiques (Inputs) ───
#let data-path          = sys.inputs.at("data-path",       default: "_cv_data.json")
#let font-size-delta    = float(sys.inputs.at("font-size-delta", default: "0.0"))  * 1pt
#let leading-val        = float(sys.inputs.at("leading",        default: "0.65"))  * 1em
#let section-gap-val    = float(sys.inputs.at("section-gap",    default: "20.0"))  * 1pt
#let margin-sides-val   = float(sys.inputs.at("margin-sides",   default: "14.0"))  * 1pt
#let theme-name         = sys.inputs.at("theme",           default: "premium")

// ─── Couleurs THEME injectées depuis config/theme.py ───
#let sb-bg      = rgb(sys.inputs.at("sidebar-bg",      default: "#1B3A6B"))
#let accent-col = rgb(sys.inputs.at("accent-primary",  default: "#2E5FAC"))
#let sb-text    = rgb(sys.inputs.at("sidebar-text",    default: "#CCDDFF"))
#let sb-link    = rgb(sys.inputs.at("sidebar-link",    default: "#88BBFF"))
#let sb-head    = rgb(sys.inputs.at("sidebar-heading", default: "#FFFFFF"))
#let sb-divider = rgb(sys.inputs.at("sidebar-divider", default: "#3A5FA0"))
#let body-col   = rgb(sys.inputs.at("body-text",       default: "#333333"))
#let meta-col   = rgb(sys.inputs.at("meta-text",       default: "#666666"))

// ─── Données JSON ───
#let cv_data = json(data-path)

#set document(
  title: "CV " + cv_data.identity.name + " - " + cv_data.headline,
  author: cv_data.identity.name,
)

#set page(
  paper: "a4",
  margin: 0pt,
)

#set text(
  font: ("Inter", "Helvetica Neue", "Helvetica", "Arial", "sans-serif"),
  size: 9.0pt + font-size-delta,
  lang: "fr",
  fill: body-col
)

#set par(
  justify: false,
  leading: leading-val,
)

// ─── Thèmes (conservés pour compatibilité ascendante) ───
#let themes = (
  premium: (
    primary:       rgb("#1a1a2e"),
    secondary:     rgb("#475569"),
    light-bg:      rgb("#f0f4f8"),
    accent-light:  rgb("#e8f4fd"),
    divider-color: rgb("#e2e8f0"),
  ),
  subtle: (
    primary:       rgb("#2d3748"),
    secondary:     rgb("#718096"),
    light-bg:      rgb("#f7fafc"),
    accent-light:  rgb("#edf2f7"),
    divider-color: rgb("#e2e8f0"),
  ),
  ats: (
    primary:       rgb("#000000"),
    secondary:     rgb("#333333"),
    light-bg:      rgb("#ffffff"),
    accent-light:  rgb("#f5f5f5"),
    divider-color: rgb("#cccccc"),
  ),
)

#let resolved-theme = if themes.keys().contains(theme-name) { theme-name } else { "premium" }
#let theme = themes.at(resolved-theme)

// Aliases locaux — identiques aux anciens noms pour garder le reste du template intact
#let primary       = theme.at("primary")
#let secondary     = theme.at("secondary")
#let light-bg      = theme.at("light-bg")
#let accent-light  = theme.at("accent-light")
#let divider-color = theme.at("divider-color")

// ─── Composants ───
#let pill(text-content) = {
  box(
    inset: (x: 5pt, y: 1.8pt),
    radius: 3pt,
    fill: sb-divider,
    text(size: 7.5pt + font-size-delta, weight: "medium", fill: sb-head, text-content)
  )
}

#let section-title(title) = {
  v(section-gap-val)
  text(size: 10.0pt + font-size-delta, weight: "bold", fill: accent-col, tracking: 1.0pt, upper(title))
  v(-0.6em)
  line(length: 100%, stroke: 1.2pt + accent-col)
  v(0.3em)
}

#let sidebar-title(title) = {
  v(0.8em)
  text(size: 9.0pt + font-size-delta, weight: "bold", fill: sb-head, tracking: 0.5pt, upper(title))
  v(-0.5em)
  line(length: 100%, stroke: 0.3pt + sb-divider)
  v(0.3em)
}

#let render-project(proj, index) = {
  block(spacing: 2.0pt, breakable: false)[
    // En-tête compacte avec numéro
    #grid(
      columns: (auto, 1fr, auto),
      gutter: 4pt,
      text(size: 8.0pt, fill: meta-col, "[" + str(index + 1) + "]"),
      text(size: 9.5pt, weight: "semibold", fill: body-col)[#proj.name],
      box(
        fill: divider-color,
        inset: (x: 4pt, y: 1.5pt),
        radius: 2pt,
        text(size: 7.0pt, fill: meta-col, weight: "bold")[PROJET]
      )
    )
    // Description conditionnelle (si présente)
    #if proj.description != "" and proj.description != none {
      v(0.25em)
      text(size: 8.5pt, style: "italic", fill: meta-col)[#proj.description]
    }
    // Keywords toujours affichés, proches du titre
    #v(0.2em)
    #text(size: 9.0pt, style: "italic", fill: meta-col)[#proj.keywords]
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
     fill: sb-bg,
     width: 100%,
     height: 100%,
     inset: (left: 1.0cm, right: 10pt, top: 1.0cm, bottom: 0.5cm),
     [
       #set align(center)
       // Photo optionnelle : on l'affiche seulement si has-photo == "true".
       // Le chemin du fichier photo est transmis via l'input "photo-path".
       // Sans cette garde, le compileur Typst plante et le PDF n'est pas généré.
       #context {
         let photo_file = sys.inputs.at("photo-path", default: "photo.jpg")
         if sys.inputs.at("has-photo", default: "false") == "true" {
           box(
             clip: true,
             radius: 20%,
             stroke: 1.2pt + white,
             image(photo_file, width: 3.5cm)
           )
         } else {
           // Placeholder discret (cercle avec initiales) si pas de photo
           let initials = (
             cv_data.identity.at("name", default: "Z E")
               .split(" ").map(s => s.at(0, default: "")).join("")
           )
           box(
             width: 2.9cm,
             height: 2.9cm,
             radius: 50%,
             fill: sb-divider,
             stroke: 1.2pt + white,
             align(center + horizon, text(
               size: 22pt,
               weight: "bold",
               fill: sb-head,
               initials,
             )),
           )
         }
       }

       #set align(left)
       #v(0.6em)

       #sidebar-title("CONTACT")
       #set text(size: 8.0pt + font-size-delta, fill: sb-text)
       #text(weight: "bold", fill: sb-head, "Email") \
       #cv_data.identity.email \
       #v(0.15em)
       #text(weight: "bold", fill: sb-head, "Téléphone") \
       #cv_data.identity.phone \
       #v(0.15em)
       #text(weight: "bold", fill: sb-head, "LinkedIn") \
       #let linkedin = cv_data.identity.at("linkedin", default: none)
       #if linkedin != none { linkedin } else { "zein-elajamy" }

       #sidebar-title("MOBILITÉ")
       #set text(size: 8.0pt + font-size-delta, fill: sb-text)
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

        // Bloc soft_skills supprimé car fusionné dans grouped_skills

        #{
          sidebar-title("LANGUES")
          if cv_data.keys().contains("languages") {
            for l in cv_data.languages {
              text(size: 8.0pt + font-size-delta, weight: "bold", fill: sb-head, l.name)
              v(-0.6em)
              text(size: 8.0pt + font-size-delta, fill: sb-text, l.level)
              v(0.15em)
            }
          }
        }

        #{
          if cv_data.keys().contains("hobbies") and cv_data.hobbies.len() > 0 {
            sidebar-title("LOISIRS")
            set text(size: 8.0pt + font-size-delta, fill: sb-text)
            for hobby in cv_data.hobbies {
              text(hobby)
              v(0.1em)
            }
          }
        }
        
        #v(1fr)
     ]
   ),

  // ── COLONNE DROITE (CONTENU PRINCIPAL) ──
  pad(
    left: 15pt,
    top: 1.8cm,
    right: margin-sides-val,
    bottom: 0.9cm,
    [
      #text(size: 22pt + font-size-delta, weight: "black", fill: body-col, tracking: -0.5pt, upper(cv_data.identity.name))
      #v(-0.5em)
      #text(size: 10.5pt + font-size-delta, weight: "bold", fill: meta-col, cv_data.headline)

      #v(0.5em)
      #section-title("RÉSUMÉ")
      #text(size: 9.8pt + font-size-delta, fill: meta-col, weight: "medium", cv_data.summary)

      #v(2.2em)

      #section-title("EXPÉRIENCES")
      #{
        if cv_data.keys().contains("experiences") {
            for (i, exp) in cv_data.experiences.enumerate() {
              let same_company = i > 0 and exp.company == cv_data.experiences.at(i - 1).company
              grid(
                columns: (1fr, auto),
                text(size: 10.2pt + font-size-delta, weight: "bold", fill: body-col, exp.position),
                text(size: 9.5pt + font-size-delta, style: "italic", fill: meta-col, exp.start_date + " — " + exp.end_date)
              )
              v(-0.4em)
              if not same_company {
                text(size: 9.8pt + font-size-delta, weight: "bold", fill: body-col, exp.company)
                v(0.1em)
              } else {
                v(0.5em)
              }

              if exp.keys().contains("achievements") {
                  for ach in exp.achievements {
                    grid(
                      columns: (7pt, 1fr),
                      text(size: 9.5pt + font-size-delta, fill: accent-col, "•"),
                      text(size: 9.8pt + font-size-delta, fill: meta-col, ach)
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
                text(size: 10.2pt + font-size-delta, weight: "bold", fill: body-col, edu.degree),
                text(size: 9.5pt + font-size-delta, style: "italic", fill: meta-col, edu.year)
              )
              v(-0.45em)
              text(size: 9.8pt + font-size-delta, weight: "medium", fill: body-col, edu.school)
              if edu.keys().contains("specialization") and edu.specialization != none and edu.specialization != "" {
                  v(-0.3em)
                  text(size: 9.5pt + font-size-delta, weight: "semibold", fill: meta-col, edu.specialization)
              }
              if edu.keys().contains("details") and edu.details != "" {
                  v(-0.3em)
                  text(size: 9.2pt + font-size-delta, fill: meta-col, edu.details)
              }
              if edu.keys().contains("modules") and edu.modules != () and edu.modules != [] {
                  let mods = edu.modules
                  let all_mods = if type(mods) == dictionary {
                    // Flatten S5_S6, S7_S8, S9 arrays
                    let arr = ()
                    for v in mods.values() { arr += v }
                    arr
                  } else if type(mods) == array {
                    mods
                  } else {
                    ()
                  }
                  if all_mods.len() > 0 {
                    v(-0.2em)
                    set text(size: 9.5pt + font-size-delta, fill: meta-col)
                    for mod in all_mods.slice(0, calc.min(all_mods.len(), 6)) {
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

import json
from pathlib import Path
from engine.rendering import TypstRenderer

renderer = TypstRenderer(template_path=Path("templates/cv_template.typ"))

with open("vault/resumes/CV_CIMEM_TARGETED.json", "r", encoding="utf-8") as f:
    cv_data = json.load(f)

output_path = Path("CV_CIMEM_TARGETED.pdf")
pdf_path = renderer.render(cv_data, output_path, photo_path="photo.jpg")
print(f"PDF generated at: {pdf_path}")

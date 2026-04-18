import unittest

from engine.cv_generator import PersonalCVGenerator


class PersonalCVGeneratorUnitTests(unittest.TestCase):
    def setUp(self):
        self.generator = PersonalCVGenerator()

    def test_parse_json_accepts_plain_json(self):
        payload = '{"improved_headline":"Ingénieur R&D","improved_summary":"Résumé court."}'
        parsed = self.generator._parse_json(payload)
        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed["improved_headline"], "Ingénieur R&D")

    def test_parse_json_accepts_embedded_json(self):
        payload = 'Analyse: {"improved_headline":"X","improved_summary":"Y"} merci'
        parsed = self.generator._parse_json(payload)
        self.assertEqual(parsed, {"improved_headline": "X", "improved_summary": "Y"})

    def test_parse_json_returns_none_on_invalid_input(self):
        self.assertIsNone(self.generator._parse_json("pas de json"))
        self.assertIsNone(self.generator._parse_json(""))
        self.assertIsNone(self.generator._parse_json(None))

    def test_normalize_job_handles_missing_and_string_skills(self):
        normalized = self.generator._normalize_job(
            {
                "title": "  ",
                "company": "",
                "description": "  test ",
                "required_skills": "Python",
            }
        )
        self.assertEqual(normalized["title"], "Poste non spécifié")
        self.assertEqual(normalized["company"], "Entreprise non spécifiée")
        self.assertEqual(normalized["description"], "test")
        self.assertEqual(normalized["required_skills"], ["Python"])

    def test_assemble_data_does_not_mutate_master_profile(self):
        original = self.generator.master_profile["experiences"][0]["achievements"][:]
        _ = self.generator._assemble_data(
            job={"title": "Ingénieur", "company": "Test"},
            headline="Headline",
            summary="Summary",
            skills=["Python", "Abaqus"],
            achievements=["Résultat 1", "Résultat 2"],
        )
        self.assertEqual(self.generator.master_profile["experiences"][0]["achievements"], original)


if __name__ == "__main__":
    unittest.main()

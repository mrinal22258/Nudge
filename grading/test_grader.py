import unittest
from grading.grader import grade

class TestGrader(unittest.TestCase):
    def setUp(self):
        # A simple schema to use for tests
        self.schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "contact": {
                    "type": "object",
                    "properties": {
                        "email": {"type": "string"},
                        "phone": {"type": "string"}
                    }
                },
                "education": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "institution": {"type": "string"},
                            "degree": {"type": "string"},
                            "gpa": {"type": "number"}
                        }
                    }
                }
            }
        }

    def test_perfect_match(self):
        gt = {
            "name": "Alice Smith",
            "contact": {"email": "alice@example.com"},
            "education": [
                {"institution": "Uni A", "degree": "BS", "gpa": 3.8}
            ]
        }
        pred = {
            "name": "Alice Smith",
            "contact": {"email": "alice@example.com"},
            "education": [
                {"institution": "Uni A", "degree": "BS", "gpa": 3.8}
            ]
        }
        res = grade(self.schema, pred, gt)
        
        self.assertTrue(res["completed"])
        self.assertEqual(res["leaf_accuracy"], 100.0)
        self.assertEqual(res["precision"], 1.0)
        self.assertEqual(res["recall"], 1.0)
        
        # Check diffs
        correct_paths = {d["path"] for d in res["field_diffs"] if d["status"] == "correct"}
        self.assertIn("name", correct_paths)
        self.assertIn("contact.email", correct_paths)
        self.assertIn("education[0].institution", correct_paths)
        self.assertIn("education[0].degree", correct_paths)
        self.assertIn("education[0].gpa", correct_paths)

    def test_missing_field(self):
        gt = {
            "name": "Alice Smith",
            "contact": {"email": "alice@example.com", "phone": "123-456"}
        }
        pred = {
            "name": "Alice Smith",
            "contact": {"email": "alice@example.com"}
        }
        res = grade(self.schema, pred, gt)
        
        self.assertTrue(res["completed"])
        # name matches (1), email matches (1), phone is missing (0/1) -> 2/3 = 66.67%
        self.assertLess(res["leaf_accuracy"], 100.0)
        
        # Check diffs
        missed = [d for d in res["field_diffs"] if d["status"] == "missed"]
        self.assertEqual(len(missed), 1)
        self.assertEqual(missed[0]["path"], "contact.phone")

    def test_hallucinated_field(self):
        gt = {
            "name": "Alice Smith",
            "contact": {"email": "alice@example.com"}
        }
        pred = {
            "name": "Alice Smith",
            "contact": {"email": "alice@example.com", "phone": "999-999"}
        }
        res = grade(self.schema, pred, gt)
        
        self.assertTrue(res["completed"])
        # name matches (1), email matches (1), phone is hallucinated (0/1) -> 2/3 = 66.67%
        self.assertLess(res["leaf_accuracy"], 100.0)
        
        # Check diffs
        hallucinated = [d for d in res["field_diffs"] if d["status"] == "hallucinated"]
        self.assertEqual(len(hallucinated), 1)
        self.assertEqual(hallucinated[0]["path"], "contact.phone")

    def test_wrong_type_value_mismatch(self):
        gt = {
            "name": "Alice Smith"
        }
        pred = {
            "name": "Bob Jones"
        }
        res = grade(self.schema, pred, gt)
        
        self.assertTrue(res["completed"])
        self.assertEqual(res["leaf_accuracy"], 0.0)
        
        # Check diffs
        incorrect = [d for d in res["field_diffs"] if d["status"] == "incorrect"]
        self.assertEqual(len(incorrect), 1)
        self.assertEqual(incorrect[0]["path"], "name")

    def test_partial_nested_match(self):
        gt = {
            "education": [
                {"institution": "Uni A", "degree": "BS", "gpa": 3.8},
                {"institution": "Uni B", "degree": "MS", "gpa": 4.0}
            ]
        }
        pred = {
            "education": [
                {"institution": "Uni A", "degree": "BS", "gpa": 3.5}, # GPA mismatched
                {"institution": "Uni B", "degree": "PhD"} # Degree mismatched, GPA missing
            ]
        }
        res = grade(self.schema, pred, gt)
        
        self.assertTrue(res["completed"])
        # Row precision and recall should be 1.0 because both rows pair up
        self.assertEqual(res["precision"], 1.0)
        self.assertEqual(res["recall"], 1.0)
        
        # Leaf accuracy should be partial
        self.assertLess(res["leaf_accuracy"], 100.0)
        self.assertGreater(res["leaf_accuracy"], 0.0)
        
        # Check incorrect and missed diffs
        incorrect = {d["path"] for d in res["field_diffs"] if d["status"] == "incorrect"}
        missed = {d["path"] for d in res["field_diffs"] if d["status"] == "missed"}
        
        self.assertIn("education[0].gpa", incorrect)
        self.assertIn("education[1].degree", incorrect)
        self.assertIn("education[1].gpa", missed)

if __name__ == "__main__":
    unittest.main()

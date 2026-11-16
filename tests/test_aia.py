import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import aia  # noqa: E402

H = "name,purpose,domain,risk_class,human_oversight,logging,data_governance,transparency_notice,conformity_assessment_date,owner\n"


def row(name="S", purpose="p", domain="it", rc="minimal", ho="", lg="", dg="", tn="", ca="", owner="O"):
    return f"{name},{purpose},{domain},{rc},{ho},{lg},{dg},{tn},{ca},{owner}\n"


def rules(text):
    return sorted(f["rule"] for f in aia.audit(text, "t.csv"))


HIGH_OK = row(rc="high", domain="employment", ho="yes", lg="yes", dg="yes", ca="2026-01-01")


class Rules(unittest.TestCase):
    def test_clean_minimal(self):
        self.assertEqual(rules(H + row()), [])

    def test_clean_high(self):
        self.assertEqual(rules(H + HIGH_OK), [])

    def test_prohibited_keywords(self):
        for p in ["social scoring of citizens", "Emotion Recognition at work", "facial image scraping from the web",
                  "subliminal nudges", "real-time remote biometric identification in public", "untargeted scraping"]:
            self.assertIn("AIA001", rules(H + row(purpose=p)), p)

    def test_emotion_recognition_is_banned_only_at_work_and_school(self):
        self.assertIn("AIA001", rules(H + row(purpose="emotion recognition of employees")))
        self.assertIn("AIA001", rules(H + row(purpose="emotion recognition", domain="education")))
        self.assertNotIn("AIA001", rules(H + row(purpose="emotion recognition for call-centre customers", rc="high")))
        self.assertIn("AIA002", rules(H + row(purpose="emotion recognition for call-centre customers", rc="limited")))

    def test_2026_article_5_additions(self):
        for p in ["nudification app", "undress photos", "generates child sexual abuse material"]:
            f = aia.audit(H + row(purpose=p), "t.csv")
            self.assertTrue(any(x["rule"] == "AIA001" and "2026/1744" in x["msg"] for x in f), p)

    def test_prohibited_is_critical(self):
        f = aia.audit(H + row(purpose="social scoring"), "t.csv")
        self.assertEqual([x["sev"] for x in f if x["rule"] == "AIA001"], ["critical"])

    def test_benign_purpose(self):
        self.assertNotIn("AIA001", rules(H + row(purpose="route optimisation")))

    def test_annex3_misclassified(self):
        for d in aia.ANNEX3:
            self.assertIn("AIA002", rules(H + row(domain=d, rc="minimal")), d)

    def test_annex3_correct(self):
        self.assertNotIn("AIA002", rules(H + HIGH_OK))

    def test_annex3_empty_class(self):
        self.assertIn("AIA002", rules(H + row(domain="education", rc="")))

    def test_oversight(self):
        self.assertIn("AIA003", rules(H + row(rc="high", ho="no", lg="yes", dg="yes", ca="d")))
        self.assertNotIn("AIA003", rules(H + row(rc="high", ho="YES", lg="yes", dg="yes", ca="d")))

    def test_logging_governance_conformity(self):
        r = rules(H + row(rc="high", ho="yes"))
        self.assertEqual(r, ["AIA004", "AIA005", "AIA006"])

    def test_limited_needs_transparency(self):
        self.assertIn("AIA007", rules(H + row(rc="limited")))
        self.assertNotIn("AIA007", rules(H + row(rc="limited", tn="yes")))

    def test_keyword_limited(self):
        for p in ["customer support chatbot", "deepfake generator", "generative text", "voice cloning"]:
            self.assertIn("AIA007", rules(H + row(purpose=p)), p)

    def test_owner(self):
        self.assertEqual(rules(H + row(owner="")), ["AIA008"])

    def test_bad_class(self):
        self.assertEqual(rules(H + row(rc="")), ["AIA009"])
        self.assertEqual(rules(H + row(rc="medium")), ["AIA009"])

    def test_class_case_insensitive(self):
        self.assertEqual(rules(H + row(rc="MINIMAL")), [])

    def test_high_requires_nothing_for_minimal(self):
        self.assertEqual(rules(H + row(ho="no", lg="no", dg="no")), [])


class Shapes(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(rules(""), ["AIA000"])
        self.assertEqual(rules("\n\n"), ["AIA000"])

    def test_wrong_header(self):
        self.assertEqual(rules("a,b\n1,2\n"), ["AIA000"])

    def test_info_severity(self):
        self.assertEqual(aia.audit("", "e")[0]["sev"], "info")

    def test_header_only(self):
        self.assertEqual(rules(H), [])

    def test_crlf(self):
        self.assertEqual(rules((H + HIGH_OK).replace("\n", "\r\n")), [])

    def test_quoted_commas(self):
        self.assertEqual(rules(H + row(purpose='"filter, sort, rank"')), [])

    def test_missing_columns_tolerated(self):
        self.assertEqual(rules("name,risk_class\nx,minimal\n"), ["AIA008"])

    def test_short_rows(self):
        self.assertIn("AIA008", rules(H + "x,y\n"))

    def test_nul_bytes(self):
        self.assertIsInstance(aia.audit(H + "a\x00b,p\n", "t"), list)

    def test_line_numbers(self):
        f = aia.audit(H + row(name="A") + row(name="B", owner=""), "t.csv")
        self.assertEqual(f[0]["where"], "t.csv:3")

    def test_line_numbers_after_quoted_newline(self):
        f = aia.audit(H + 'A,"two\nlines",it,minimal,,,,,,O\n' + row(name="B", owner=""), "t.csv")
        self.assertEqual(f[0]["line"], 4)

    def test_blank_lines_skipped(self):
        f = aia.audit(H + "\n" + row(name="B", owner=""), "t.csv")
        self.assertEqual(f[0]["line"], 3)

    def test_sorting(self):
        fs = [{"sev": "low", "file": "a", "line": 1, "rule": "B"}, {"sev": "high", "file": "z", "line": 9, "rule": "A"},
              {"sev": "high", "file": "a", "line": 10, "rule": "A"}, {"sev": "high", "file": "a", "line": 2, "rule": "A"}]
        self.assertEqual([(f["file"], f["line"]) for f in aia.sort_findings(fs)], [("a", 2), ("a", 10), ("z", 9), ("a", 1)])

    def test_yes_variants(self):
        for v in ("yes", "YES", " true ", "1", "y"):
            self.assertTrue(aia.yes(v))
        for v in ("", "no", "n/a", "0"):
            self.assertFalse(aia.yes(v))


class Fuzz(unittest.TestCase):
    def test_random_inputs(self):
        rnd = random.Random(7)
        bits = ["", ",", '"', "\n", "\r", "name", "risk_class", "high", "employment", "yes", " ", "social scoring", "\x00", "é", "a,b"]
        for _ in range(3000):
            s = "".join(rnd.choice(bits) for _ in range(rnd.randint(1, 30)))
            aia.audit(s, "f.csv")

    def test_truncated_valid(self):
        text = H + HIGH_OK * 3
        for i in range(len(text)):
            aia.audit(text[:i], "f.csv")


if __name__ == "__main__":
    unittest.main()

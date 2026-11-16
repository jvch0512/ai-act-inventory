import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BIN = os.path.join(ROOT, "bin", "ai-act-inventory")


def run(*args):
    p = subprocess.run([sys.executable, BIN, *args], cwd=ROOT, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


class Cli(unittest.TestCase):
    def test_default_exit_zero(self):
        self.assertEqual(run("examples")[0], 0)

    def test_human_header(self):
        self.assertTrue(run("examples")[1].startswith("2 files, 9 findings\n"))

    def test_tsv(self):
        lines = run("examples", "--tsv")[1].splitlines()
        self.assertEqual(lines[0], "# 2 files, 9 findings")
        self.assertTrue(all(len(l.split("\t")) == 4 for l in lines[1:]))

    def test_fail_on(self):
        self.assertEqual(run("examples", "--fail-on", "critical")[0], 1)
        self.assertEqual(run("examples", "--fail-on", "high")[0], 1)
        self.assertEqual(run("examples/clean.csv", "--fail-on", "medium")[0], 0)

    def test_bad_input(self):
        for args in (["nope.csv"], ["--bogus"], [], ["examples", "--fail-on", "low"], ["examples", "--fail-on"], ["examples", "x"]):
            self.assertEqual(run(*args)[0], 2, args)

    def test_single_file_label(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "one.csv")
            with open(p, "w") as f:
                f.write("name,risk_class\nx,\n")
            out = run(p, "--tsv")[1]
            self.assertIn("\tAIA009\tone.csv:2\t", out)

    def test_binary_survives(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "b.csv")
            with open(p, "wb") as f:
                f.write(os.urandom(3000))
            self.assertLessEqual(run(p)[0], 1)


if __name__ == "__main__":
    unittest.main()

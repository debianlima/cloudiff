import pathlib
import shutil
import subprocess
import tempfile
import textwrap
import unittest


class DeriveDiagramsTests(unittest.TestCase):
    def run_with_manifest(self, manifest: str) -> str:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "tools").mkdir()
            shutil.copy2(pathlib.Path(__file__).parents[1] / "tools" / "derive_diagrams.py", root / "tools" / "derive_diagrams.py")
            (root / "manifesto.yaml").write_text(textwrap.dedent(manifest), encoding="utf-8")
            proc = subprocess.run(
                ["python3", str(root / "tools" / "derive_diagrams.py")],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return proc.stdout

    def test_output_is_derived_only_from_manifest(self):
        out = self.run_with_manifest(
            """
            entradas:
              - id: 1
                caminho: alpha.cpp
                proposito: alpha producer
                tipo: agente
                consome: []
                produz: token/alpha
                aceite: test-alpha
                status: aceito
              - id: 2
                caminho: beta.cpp
                proposito: beta consumer
                tipo: fila
                consome: [token/alpha]
                produz: token/beta
                aceite: test-beta
                status: pendente
            trabalho_compartilhado: null
            """
        )
        self.assertIn('E1["alpha.cpp"]', out)
        self.assertIn('E2["beta.cpp"]', out)
        self.assertIn('E1 --> E2', out)
        self.assertIn('E1["1 ACEITO alpha.cpp"]', out)
        self.assertIn('E2["2 PENDENTE beta.cpp"]', out)
        self.assertIn('E1["agente :: alpha.cpp"]', out)
        self.assertIn('E2["fila :: beta.cpp"]', out)
        for forbidden in (
            "Portal legado",
            "cloudiff-control",
            "PostgreSQL",
            "NATS",
            "Faro",
            "Maurício",
            "Forja",
            "10.62.",
        ):
            self.assertNotIn(forbidden, out)

    def test_mermaid_fences_are_balanced(self):
        out = self.run_with_manifest(
            """
            entradas:
              - id: 7
                caminho: only.cpp
                proposito: only node
                tipo: agente
                consome: []
                produz: token/only
                aceite: test-only
                status: aceito
            """
        )
        lines = [line.strip() for line in out.splitlines()]
        self.assertGreater(lines.count("```mermaid"), 0)
        self.assertEqual(lines.count("```mermaid"), lines.count("```"))
        inside = False
        for line in lines:
            if line == "```mermaid":
                self.assertFalse(inside, "nested Mermaid fence")
                inside = True
            elif line == "```":
                self.assertTrue(inside, "stray closing fence")
                inside = False
        self.assertFalse(inside, "unclosed Mermaid fence")


if __name__ == "__main__":
    unittest.main()

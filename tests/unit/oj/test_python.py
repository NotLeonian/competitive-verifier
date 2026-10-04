import pathlib

from competitive_verifier.oj.languages.python import PythonLanguage


def test_list_dependencies(testtemp: pathlib.Path):
    source = testtemp / "main.py"
    dependency = testtemp / "helper.py"
    source.write_text("from helper import value\nprint(value)\n", encoding="utf-8")
    dependency.write_text("value = 42\n", encoding="utf-8")

    assert set(PythonLanguage().list_dependencies(source, basedir=testtemp)) == {
        source,
        dependency,
    }

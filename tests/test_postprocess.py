from __future__ import annotations

from quillvault.postprocess.lexicon import Lexicon
from quillvault.postprocess.review import ReviewPolicy, apply_review, normalize
from quillvault.postprocess.validators import find_cie10_codes, validate_text
from quillvault.types import TextLine


def test_valid_text_has_no_issues():
    assert validate_text("Fecha de nacimiento: 12/03/1985") == []
    assert validate_text("CC 1.023.456.789") == []


def test_impossible_and_future_dates_are_flagged():
    assert any("inválida" in i for i in validate_text("Fecha: 31/02/2020"))
    assert any("futuro" in i for i in validate_text("Fecha: 01/01/2999"))


def test_document_length_is_checked():
    assert any("longitud" in i for i in validate_text("TI 12345"))


def test_letter_digit_confusion_is_flagged():
    issues = validate_text("CC 1O23456")
    assert any("confusión" in i for i in issues)


def test_cie10_codes_are_extracted():
    assert find_cie10_codes("Dx: I10 y E11.9, control") == ["I10", "E119"]


def test_builtin_lexicon_loads_and_ignores_accents():
    lexicon = Lexicon.builtin()
    assert len(lexicon) > 100
    assert "diagnostico" in lexicon
    assert "Diagnóstico" in lexicon


def test_lexicon_suggests_but_never_rewrites():
    lexicon = Lexicon({"acetaminofén", "losartán"})
    line = "Acetaminofen 500 mg y losartam"
    suggestions = lexicon.suggest(line)
    assert suggestions == {"losartam": ["losartán"]}


def test_custom_lexicon_from_file(tmp_path):
    vocab = tmp_path / "cum.txt"
    vocab.write_text("# comentario\nmetformina\n\nlevotiroxina\n", encoding="utf-8")
    lexicon = Lexicon.from_files(vocab)
    assert len(lexicon) == 2
    assert lexicon.suggest("metfornina") == {"metfornina": ["metformina"]}


def test_review_flags_low_confidence_and_missing_confidence():
    lines = [
        TextLine("Control en ocho días", 0.97),
        TextLine("Contro1 en ocho", 0.40),
        TextLine("texto de un VLM", None),
    ]
    apply_review(lines, ReviewPolicy(min_confidence=0.85))
    assert [ln.needs_review for ln in lines] == [False, True, True]
    assert any("confianza baja" in i for i in lines[1].issues)


def test_review_normalizes_whitespace_and_unicode():
    assert normalize("  José   Peña \n") == "José Peña"

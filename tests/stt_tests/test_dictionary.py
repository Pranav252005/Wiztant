"""Tests for the user dictionary fuzzy pass and surgical refiner replacements."""

import pytest

import core.dictation_correction as dc
import core.vocab as vocab
from core.stt_refiner import STTRefiner


@pytest.fixture
def dictionary(tmp_path, monkeypatch):
    """Point vocab + learned-correction storage at temp files and preload words."""
    monkeypatch.setattr(vocab, "_VOCAB_PATH", tmp_path / "vocab.json")
    monkeypatch.setattr(vocab, "_APPDATA", tmp_path)
    monkeypatch.setattr(vocab, "_vocab_cache", None)
    monkeypatch.setattr(dc, "_CORRECTIONS_PATH", tmp_path / "dictation_corrections.json")
    monkeypatch.setattr(dc, "_phonetic_index", {})
    monkeypatch.setattr(dc, "_index_built", False)
    vocab.add_word("Wiztant")
    vocab.add_word("Groq")
    vocab.add_word("Tune Hub")
    return vocab


class TestDictionaryWords:
    def test_add_and_list(self, dictionary):
        words = [e["word"] for e in dictionary.list_words()]
        assert words == ["Wiztant", "Groq", "Tune Hub"]

    def test_add_duplicate_rejected(self, dictionary):
        assert dictionary.add_word("wiztant") is False
        assert len(dictionary.list_words()) == 3

    def test_delete_word(self, dictionary):
        assert dictionary.delete_word("groq") is True
        assert all(e["word"] != "Groq" for e in dictionary.list_words())


class TestDictionaryCorrections:
    def test_single_word_fuzzy(self, dictionary):
        text, changes = dictionary.apply_dictionary_corrections("use grok for this")
        assert text == "use Groq for this"
        assert changes == ["grok->Groq"]

    def test_multiword_mishearing(self, dictionary):
        text, changes = dictionary.apply_dictionary_corrections("open the whiz tant settings")
        assert text == "open the Wiztant settings"
        assert changes == ["whiz tant->Wiztant"]

    def test_only_target_word_changes(self, dictionary):
        original = "please tell grok about the meeting tomorrow, thanks."
        text, _ = dictionary.apply_dictionary_corrections(original)
        assert text == "please tell Groq about the meeting tomorrow, thanks."

    def test_stopwords_never_replaced(self, dictionary):
        text, changes = dictionary.apply_dictionary_corrections("that thing was great")
        assert text == "that thing was great"
        assert changes == []

    def test_correct_word_left_alone(self, dictionary):
        text, changes = dictionary.apply_dictionary_corrections("I told Wiztant to do it")
        assert text == "I told Wiztant to do it"
        assert changes == []

    def test_casing_normalized(self, dictionary):
        text, changes = dictionary.apply_dictionary_corrections("check tune hub now")
        assert text == "check Tune Hub now"
        assert changes == ["tune hub->Tune Hub"]

    def test_empty_dictionary_noop(self, dictionary):
        for e in list(dictionary.list_words()):
            dictionary.delete_word(e["word"])
        text, changes = dictionary.apply_dictionary_corrections("use grok for this")
        assert text == "use grok for this"
        assert changes == []


class TestRefinerReplacements:
    @pytest.fixture
    def refiner(self):
        r = STTRefiner()
        r.set_dictionary(["Wiztant", "Groq"])
        r.set_vocab({"grock": "Groq"})
        return r

    def test_valid_replacement_applied(self, refiner):
        text, changes = refiner._apply_replacements(
            "open the wizz tant settings", [{"from": "wizz tant", "to": "Wiztant"}]
        )
        assert text == "open the Wiztant settings"
        assert changes == ["wizz tant->Wiztant"]

    def test_homophone_replacement_applied(self, refiner):
        text, changes = refiner._apply_replacements(
            "put it over their", [{"from": "their", "to": "there"}]
        )
        assert text == "put it over there"

    def test_hallucinated_rewrite_rejected(self, refiner):
        # "to" is not in dictionary/vocab and not similar to "from" -> dropped
        text, changes = refiner._apply_replacements(
            "schedule the meeting", [{"from": "meeting", "to": "appointment"}]
        )
        assert text == "schedule the meeting"
        assert changes == []

    def test_from_not_in_text_rejected(self, refiner):
        text, changes = refiner._apply_replacements(
            "hello world", [{"from": "goodbye", "to": "good buy"}]
        )
        assert text == "hello world"
        assert changes == []

    def test_malformed_entries_ignored(self, refiner):
        text, changes = refiner._apply_replacements(
            "hello world", ["junk", {"from": "", "to": "x"}, {"from": "hello", "to": "hello"}]
        )
        assert text == "hello world"
        assert changes == []

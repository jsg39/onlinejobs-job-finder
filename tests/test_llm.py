from ojagent.config import _fallbacks
from ojagent.llm import FallbackLLM, Turn


class Model:
    def __init__(self, name, log, ok):
        self.name, self.log, self.ok = name, log, ok

    def complete(self, messages):
        self.log.append(self.name)
        if not self.ok:
            raise RuntimeError("Service temporarily overloaded")
        return Turn(content=f"hi from {self.name}")


def fallback(ok, models, discovered=None):
    log = []
    llm = FallbackLLM(models, lambda m: Model(m, log, m in ok),
                      discover=(lambda: discovered) if discovered is not None else None)
    return llm, log


def test_falls_back_until_a_model_answers_then_sticks_with_it():
    llm, log = fallback({"c"}, ["a", "b", "c"])
    assert llm.complete([]).content == "hi from c"
    assert log == ["a", "b", "c"]
    llm.complete([])
    assert log[-1] == "c" and len(log) == 4 and llm.model == "c"


def test_finds_more_free_models_when_the_listed_ones_fail():
    llm, log = fallback({"free-2"}, ["mine"], discovered=["mine", "free-1", "free-2"])
    assert llm.complete([]).content == "hi from free-2"
    assert log == ["mine", "free-1", "free-2"]


def test_gives_up_with_the_errors_when_nothing_works():
    llm, _ = fallback(set(), ["a"], discovered=["b"])
    try:
        llm.complete([])
    except RuntimeError as e:
        assert "Every model failed" in str(e) and "overloaded" in str(e)
    else:
        raise AssertionError("expected a failure")


def test_fallback_setting():
    assert _fallbacks("auto") is None and _fallbacks("") is None
    assert _fallbacks("none") == []
    assert _fallbacks(" a:free, b:free ") == ["a:free", "b:free"]

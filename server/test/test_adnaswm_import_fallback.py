import importlib.util
import sys
from pathlib import Path


def test_adnaswm_import_fallback_blocked_watermarking_method(monkeypatch, tmp_path):
    src_path = Path("src/AdnasWM.py").resolve()
    assert src_path.exists(), "src/AdnasWM.py hittas inte"

    # Ta bort ev. redan laddad watermarking_method så import-maskinen inte använder cache
    sys.modules.pop("watermarking_method", None)

    # Meta-finder som blockerar just watermarking_method
    class Blocker:
        def find_spec(self, fullname, path, target=None):
            if fullname == "watermarking_method":
                raise ModuleNotFoundError("blocked for test")
            return None

    blocker = Blocker()
    sys.meta_path.insert(0, blocker)
    try:
        # Ladda AdnasWM.py under nytt namn för att köra top-level-koden igen
        mod_name = "AdnasWM_nomw"
        spec = importlib.util.spec_from_file_location(mod_name, str(src_path))
        mod = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(mod)

        # Nu ska fallbacken vara aktiv
        assert hasattr(mod, "WatermarkingError")
        assert hasattr(mod, "SecretNotFoundError")
        assert hasattr(mod, "InvalidKeyError")
        # Och bas-typen ska vara 'object' när watermarking_method saknas
        assert mod.WatermarkingMethodBase is object
    finally:
        sys.meta_path.remove(blocker)

def test_adnaswm_hmac_compare_all_paths():
    import AdnasWM as mod
    # olika längd -> False (täcker early return)
    assert mod.hmac_compare("a", "bb") is False
    # samma längd & samma bytes -> True
    assert mod.hmac_compare("abc", "abc") is True
    # samma längd men olika -> False
    assert mod.hmac_compare("abc", "abX") is False

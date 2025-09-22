from pathlib import Path
from advanced_steganographic_watermark import AdvancedSteganographicWatermark as Adv

# Läs in en riktig PDF (ta vilken som helst, helst några sidor)
pdf_data = Path("testpdf.pdf").read_bytes()

adv = Adv()

# --- Skriv watermark ---
wm = adv.add_watermark(pdf_data, secret="mamma", key="hej")
Path("adv_watermarked.pdf").write_bytes(wm)

# --- Läs watermark ---
try:
    secret = adv.read_secret(wm, key="hej")
    print("✅ Advanced OK, secret =", secret)
except Exception as e:
    print("❌ Fel:", type(e).__name__, e)

# --- Testa med fel nyckel (ska kasta fel) ---
try:
    adv.read_secret(wm, key="fel")
except Exception as e:
    print("🔒 Fel nyckel testad ->", type(e).__name__, e)


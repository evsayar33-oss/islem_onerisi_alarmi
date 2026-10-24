# islem_onerisi_alarmi — ICT çoklu zaman dilimi konfluens araştırma motoru

Bu sistem ICT kavramlarının (FVG, Order Block, MSB, likidite) her kombinasyonunu
6 varlıkta test eder. Sistem en güçlü birleşimleri bulur. Sistem her çalışmada kendi
ileri (forward) sonuçlarından öğrenir.

## 1. Zaman dilimi rolleri

| TF | Koşullar |
|---|---|
| 1 Aylık (M) | `M_LIQ` (önceki ay yüksek/düşük süpürme + geri alma), `M_FVG`, `M_OB` |
| 1 Haftalık (W) | `W_FVG`, `W_OB` |
| 1 Günlük (D) | `D_FVG`, `D_OB` |
| 4 Saatlik (H4) | `H4_MSB`, `H4_FVG`, `H4_OB` |
| 1 Saatlik (H1) | Giriş: `H1_FVG`, `H1_OB` veya `H1_ANY` |

Varlıklar: NQ, SPX, XAU, XAG, BTC, ETH.

## 2. Ne test edilir

- **Kombinasyonlar:** 10 HTF koşulunun tüm alt kümeleri (2^10 = 1024) × 3 giriş tipi.
  Sistem en az 30 tetikleyicisi olan her kombinasyonu değerlendirir.
  - "HTF FVG içinde LTF block/FVG": 1h giriş bölgesi, aynı yöndeki HTF bölgesiyle
    kesişmelidir (`--overlap overlap`). Bölgenin tamamen içinde olması da istenebilir
    (`--overlap inside`).
  - "Tüm TF block alanı içinde FVG": `M_OB+W_OB+D_OB+H4_OB+H1_FVG` ve bunun tüm alt
    kümeleri ızgarada yer alır.
- **Giriş modları (3):** market (tetikleyici kapanışı), limit bölge kenarı, limit %50 (CE).
- **Stoplar (10):** bölge dış kenarı (+0 / 0,1 / 0,25 / 0,5 ATR), ATR 1 / 1,5 / 2 / 3,
  son swing + 0,1 ATR, formasyon ucu + 0,1 ATR.
- **RR (9):** 1, 1,5, 2, 2,5, 3, 3,5, 4, 5, 6.
- **Yönetim (2):** yok, +1R'de başa baş (break-even).
- Toplam: varlık başına 540 yürütme konfigürasyonu × ~300–500 kombinasyon ≈ 250.000 deneme.

## 3. Doğruluk güvenceleri

- **Lookahead yok:** HTF mumu, son 1h mumu kapandıktan sonra görünür. Oluşan son HTF mumu
  atılır. Test: veri kesildiğinde geçmiş koşul bitleri değişmez.
- **Muhafazakâr dolum:** aynı mumda stop ve hedef → stop. Limit dolum mumunda hedef
  sayılmaz. Gap → açılış fiyatı. Varlık başına gidiş-dönüş maliyet uygulanır.
- **Tek pozisyon kuralı dolum sırasıyla uygulanır.** Tetikleyici sırası kullanılmaz. Bu
  kural ileriye bakma sızıntısını önler. Sızıntı rastgele yürüyüşte +0,7R sahte avantaj
  üretmişti. Test: rastgele yürüyüşte ızgara ortalaması ≈ 0R.
- **Çoklu test kontrolü:** empirical-Bayes küçültme, Deflated Sharpe, IS/OOS ayrımı,
  anchored walk-forward (seçim sürecinin kendisi test edilir), plasebo (yapısı bozulmuş
  permütasyon serileri), komşu-RR kararlılığı, çapraz-varlık sağlamlığı.

## 4. Kendini geliştiren döngü (`ictlab/learner.py`)

1. **ingest:** önceki öneriler, sonradan gelen ve görülmemiş mumlarda puanlanır.
2. **calibrate:** κ = backtest avantajının ileri dönemde kalan oranı (0 … 1,5).
3. **rank:** backtest posterior × κ ile ileri kanıt birleştirilir. İleri kanıt çift ağırlık
   alır. Yarı ömür 1 yıldır. Eski avantajlar söner.
4. **record:** yeni en iyi öneriler tahminleriyle saklanır.

`replay` komutu bu döngüyü geçmişte adım adım çalıştırır ve öğrenme eğrisini gösterir.

## 5. Kullanım

```bash
pip install -r requirements.txt

# Veri: Dukascopy (NQ, SPX, XAU, XAG) ve Binance Vision (BTC, ETH), 1h
python -m ictlab fetch --assets all
# Alternatif: yfinance (son 730 gün) veya kendi CSV dosyanız
python -m ictlab fetch --assets NQ --source csv --csv NQ_1h.csv

# Tam araştırma: ızgara + walk-forward + 3 plasebo -> reports/RESEARCH_REPORT.md
python -m ictlab research --assets all --placebo 3 --folds 5

# Öğrenme döngüsünü geçmişte çalıştır
python -m ictlab replay --assets all --step 6MS

# Canlı alarm: aktif kurulumlar (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID varsa Telegram)
python -m ictlab scan --assets all

python -m pytest -q
```

## 6. Çıktılar

- `reports/RESEARCH_REPORT.md` — yöntem, en iyi 15 kombinasyon, koşulların marjinal değeri,
  walk-forward, plasebo, yıllık ve rejim dökümü, çapraz-varlık, öğrenme eğrisi.
- `results/<ASSET>_grid.parquet` — tüm (kombinasyon × konfigürasyon) istatistikleri.
- `results/knowledge/` — kalıcı bilgi tabanı (her çalışmada güncellenir).
- `results/signals.json` — `scan` çıktısı.

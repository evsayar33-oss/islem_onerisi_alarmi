> **İki labın birleşik sonucu (2026-10-24):** quant_lab [`SENTEZ_RAPORU.md`](https://github.com/evsayar33-oss/quant_lab/blob/main/SENTEZ_RAPORU.md) — bu depodaki ICT sonuçları ve quant_lab'ın bütün testleri birlikte; ölçüt S&P 500 endeksinin kendisi (H072).

# islem_onerisi_alarmi — ICT çoklu zaman dilimi konfluens araştırma motoru

> **Tek dosyada tüm sonuçlar:** [`STRATEGY_BOOK.md`](STRATEGY_BOOK.md) — her varlığın seçilen kuralı, kuralların tam tanımları, kilitli 2 yıllık test sonuçları ve 1 birimin büyümesi. Başka bir kişiye veya yapay zekaya gösterilecek dosya budur.
>
> **Denenen tüm yöntemler ve sonuçları:** [`RESEARCH_LOG.md`](RESEARCH_LOG.md) — volatilite boyutlandırma, 15 dakikalık giriş, haber/makro takvimi ve yeni ICT modelleri (Judas, PO3, Turtle Soup, Silver Bullet).

Bu sistem ICT kavramlarının (FVG, Order Block, MSB, likidite) her kombinasyonunu
6 varlıkta test eder. Sistem en güçlü birleşimleri bulur. Sistem her çalışmada kendi
ileri (forward) sonuçlarından öğrenir.

## 1. Zaman dilimi rolleri ve bölge türleri

| TF | Koşullar |
|---|---|
| 1 Aylık (M) | `M:LIQ` (önceki ay yüksek/düşük süpürme + geri alma), FVG, tüm blok türleri |
| 1 Haftalık (W) | FVG, tüm blok türleri |
| 1 Günlük (D) | FVG, tüm blok türleri |
| 4 Saatlik (H4) | `H4:MSB`, FVG, tüm blok türleri |
| 1 Saatlik (H1) | Giriş: FVG veya herhangi bir blok türü |

Bölge türleri (her TF'de ve 1h girişte):

| Kod | Tür | Tanım |
|---|---|---|
| FVG | Fair value gap | 3 mum boşluğu: low[i] > high[i-2] (boğa) |
| OB | Order block | Yapı kırılımını (MSB) üreten bacaktaki son ters renkli mum |
| BB | Breaker block | Tepeyi yapan son yükseliş mumu; düşüş bacağı önceki dibi süpürdü, sonra tepe kırıldı |
| MB | Mitigation block | BB ile aynı yapı, ama düşüş bacağı önceki dibin üstünde kaldı (failure swing) |
| RB | Rejection block | Onaylı swing noktasında uzun fitil (fitil ≥ mum aralığının %50'si); bölge = fitil |
| PB | Propulsion block | Daha önceki geçerli bir OB'ye dokunan yeni OB |
| VB | Vacuum block | Önceki kapanış ile yeni açılış arasındaki boşluk (≥ 0,25 ATR) |

Varlıklar: NQ, SPX, XAU, XAG, BTC, ETH.

## 2. Ne test edilir

- **Slot yapısı:** M, W, D, H4 slotlarının her biri tek bir seçim alır (16 seçenek):
  - yok,
  - tek bir bölge türü (7),
  - `ANYB` (herhangi bir blok),
  - `FVG+<blok>` (o TF'deki FVG ve blok, 1h giriş bölgesiyle birlikte kesişir = "blok alanı
    içinde FVG"), 6 blok + `FVG+ANYB`.
  - Bayraklar: `M:LIQ`, `H4:MSB`. Giriş filtresi: 9 seçenek (7 tür, `ANYB`, `ANY`).
- **Tam arama, budamalı:** bir dal minimum işlem sayısının altına düştüğünde durur. Koşul
  eklemek tetikleyici sayısını yalnızca azaltabilir. Aynı tetikleyici kümesini seçen
  kombinasyonlar bir kez değerlendirilir. Varlık başına ≈ 18.000–30.000 farklı kombinasyon.
- **Yürütme ızgarası:** 3 giriş modu (market, limit kenar, limit %50 CE) × 10 stop
  (bölge kenarı + 0 / 0,1 / 0,25 / 0,5 ATR, ATR 1 / 1,5 / 2 / 3, swing, formasyon ucu)
  × 9 RR (1 … 6) × 2 yönetim (yok, +1R'de başa baş) = 540 konfigürasyon.
- Toplam: varlık başına ≈ 10–16 milyon (kombinasyon × konfigürasyon) denemesi.

## 2.1 Veri kaynakları (`python -m ictlab fetch --source github`)

| Varlık | Kaynak | Dönem |
|---|---|---|
| NQ | Oanda NAS100_USD 1m → 1h (FutureSharks/financial-data) | 2005 – 2020-05 |
| SPX | Oanda SPX500_USD 1m → 1h (FutureSharks/financial-data) | 2005 – 2020-05 |
| XAU | Oanda XAU_USD 1m → 1h (FutureSharks/financial-data) | 2006 – 2020-05 |
| XAG | Dukascopy XAGUSD 1h dışa aktarımı (EPSOFT/Database-Currency-Pair) | 2007 – 2023-03 |
| BTC, ETH | Binance spot 1h (Speirsy11/crypto-dataset, Git LFS) | 2017-08 – 2026-10 |

Yerel çalışmada `--source auto` güncel Dukascopy ve Binance Vision verisini kullanır.

## 3. Doğruluk güvenceleri

- **Lookahead yok:** HTF mumu, son 1h mumu kapandıktan sonra görünür. Oluşan son HTF mumu
  atılır. Test: veri kesildiğinde geçmiş koşul bitleri değişmez.
- **Muhafazakâr dolum:** aynı mumda stop ve hedef → stop. Limit dolum mumunda hedef
  sayılmaz. Gap → açılış fiyatı. Varlık başına gidiş-dönüş maliyet uygulanır.
- **Tek pozisyon kuralı dolum sırasıyla uygulanır.** Tetikleyici sırası kullanılmaz. Bu
  kural ileriye bakma sızıntısını önler. Sızıntı rastgele yürüyüşte +0,7R sahte avantaj
  üretmişti. Test: rastgele yürüyüşte ızgara ortalaması ≈ 0R.
- **Çoklu test kontrolü:**
  - DerSimonian-Laird random-effects öncülü, tüm denemeler üzerinden hesaplanır
    (yalnızca saklanan en iyi konfigürasyonlar üzerinden değil).
  - **Küçültme gücü örneklem dışından öğrenilir:** walk-forward katlarında IS → OOS tahmin
    hatasını en aza indiren τ² seçilir. IS sıralaması OOS'u tahmin etmiyorsa τ² → 0 olur ve
    sistem tavsiye vermez.
  - t-istatistiği engeli: farklı kombinasyon sayısı kadar şans denemesinin beklenen
    maksimumu (≈ 4,0).
  - Anchored walk-forward: seçim sürecinin kendisi test edilir.
  - Plasebo: gün blokları karıştırılmış seriler.
  - Varyans tabanı (sd ≥ 0,5R): tamamı −1R olan konfigürasyonlar ağırlıkları bozamaz.

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

## 7. Son araştırma sonuçları (6 varlık)

Tam rapor: `reports/RESEARCH_REPORT.md`. Kısa özet:

- Hiçbir kombinasyon çoklu test engelini (t > 4,0–4,3) geçmiyor.
- Walk-forward kararı: NQ ve XAU "zayıf sinyal", SPX, XAG, BTC ve ETH "avantaj yok".
- Tekrarlayan yapı: en güçlü kayıtlar geniş stop (ATR 3) ve yüksek RR (4–6) kullanıyor.
  Bölge kenarı stopları maliyetten sonra zayıf kalıyor.
- En iyi çapraz-varlık adayı (yalnızca IS ile seçildi): `H4:MSB | H1:ANY`, limit %50 (CE),
  ATR 3 stop, RR 6, +1R'de başa baş. BTC, ETH ve XAU'da IS pozitif. OOS: 3/3 varlık
  pozitif, 1.202 işlemde +0,134R. Bu bir izleme adayıdır, doğrulanmış bir avantaj değildir.

# ICT yeni deney için gerçek piyasa gözlemi (V1)

Mevcut `STRATEGY_BOOK.md` kural seçimlerini ve iki-yıllık holdout
sonuçlarını yeniden seçmiyoruz veya değiştirmiyoruz. Çünkü tarihsel
başarıya bakarak yeni parametre seçmek geçmiş holdout'u kirletir.

Bu bağımsız araştırma kaydı her gün **gerçek, tamamlanmış 1h OHLCV**
verisini kriptoda önceki iki UTC günü, endeks/metal kaynaklarında önceki
üç hafta içi gününü (takvim adayları; borsa seansı teyidi değildir) tarayarak
altı özgün varlıkta toplamayı dener:
NQ ve SPX Dukascopy CFD/BID fiyatı, XAU ve XAG Dukascopy BID, BTC ve
ETH Binance SPOT (data.binance.vision) kamu arşivi. Bunlar birbirine
eşit komisyon, borsa ya da gerçek fill kaynağı değildir; her kaynağın
kimliği ve ham SHA-256 parmak izi ayrı kalır.

* İlk gözlem zamanı GitHub çalışmasının gerçek UTC veri edinim
  zamanıdır. Dün oluşan fiyat, dün önceden bilinen strateji sinyali
  olarak geriye doğru kaydedilemez.
* 2025+ Binance dosyalarında **mikrosaniye timestamp** ayırt edilir.
  Duka kaynak dönüştürme `ictlab.data` ile tam orijinal ölçek üzerinden.
* Açık-yüksek-düşük-kapanış tutarsızsa candle düzeltilmez;
  invalid olarak dışlanır ve kaynak boşluğu görünür kalır.
* Veriler `research/ict-firstseen-ohlcv` dalında ayrık
  SHA zincirinde ve 90 günlük Actions artifact'ında saklanır.
* Bu işlem FVG, OB, breaker, HTF zone gibi ICT sinyal kurallarını
  geçmişten uydurmaz. Yeterli yeni veri ve orijinal çok zaman
  dilimli yapı oluştuktan sonra kaynak repo, eaverse ve
  quant_superlab ile araştırma/yeni dondurulmuş forward sınıflandırma
  başlayabilir. Bu aşama **ham gözlem biriktirmedir, strateji testi
  başarı kanıtı değil**.

`Actions > ICT six-asset prospective real 1h evidence (NO TRADING)`
ile bir kez manuel de çalıştırılabilir. Genel cron saat garantisi
yoktur. Veri sağlayıcı erişilemezse sonuç eksik olarak görünür;
sahte bar veya PAPER/LIVE emir oluşturulmaz.

**23 Kasım gerçek provider sınaması:** İlk çalışma BTC/ETH için her biri
48 geçerli saatlik bar topladı. NQ/SPX/XAU/XAG pazartesi sabahı yalnız
hafta sonuna baktığından erişilebilir veri sunamadı. Bu düzeltme son
çarşamba-perşembe-cuma günlerini de sorgular. Tatil, rate limit, HTTP
403/404 ve eksik seanslar yine NO_DATA olarak kalır. Yalnız çalışan
kaynaktan tamamlanmış mum alınıp sayılır. Hiçbir sektör/CFD serisi
otomatik futures verisiyle değiştirilmez.

## Ayrı kaynak / erişim yedeği (23 Kasım)

Dukascopy BID CFD kaynakları hafta içi aday günlerinde de GitHub Actions
üzerinden erişilemedi. Yeni yöntem, Dukascopy 403/429 erişim reddini
kapalı piyasa seansı gibi sınıflandırmaz ve engel varken her günü tekrar
tekrar sorgulamaz. **Kaynak erişimi hâlâ çözülmüş sayılmaz.**

Yalnız tamamlayıcı araştırma bağlamı için ücretsiz Yahoo 60m continuous
futures serileri ayrı bir `proxy_datasets` nesnesine eklenir:
`NQ=F`, `ES=F`, `GC=F`, `SI=F`. Bunlar sırasıyla NQ/SPX/XAU/XAG
orijinal **Dukascopy CFD BID** fiyatlarının eşdeğeri değildir; farklı
sözleşme, rollover, seans, fiyat yapısı ve veri lisansı olabilir.
Orijinal `datasets` içinde asla yerlerine yazılmaz; proxy ile gerçek
ICT backtest, fill, zarar-durdur veya PAPER terfisi yapılamaz.

Barların en geç veri edinim anından önce tamamlanması, en fazla yedi
takvim günlük olması, instrument metaverisinin eşleşmesi ve OHLCV
fiziksel bütünlük kontrolünden geçmesi zorunludur. Yahoo da veri
vermezse bu açıkça ayrı kaynak eksikliği olarak kaydedilir; sahte veya
retrospektif ilk-gözlem zamanı türetilmez.

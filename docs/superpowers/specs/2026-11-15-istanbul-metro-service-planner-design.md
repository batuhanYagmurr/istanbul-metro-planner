# Istanbul Metro Service Planner — Tasarım

## Bağlam (neden)

Batuhan, veri analisti / iş analitiği pozisyonlarına başvururken gösterebileceği bir portföy
projesi istiyor. İzlenen kalıp: bir iş sorusu → benzerleri
grupla → tahmin et → somut karar öner → yöneticinin saniyeler içinde okuyacağı tek sayfalık panel.
Bu kalıbı İstanbul'un açık toplu taşıma verisine uyguluyoruz.

**Panelin cevapladığı soru:** "İstanbul'un raylı hatlarında hangi hatta, hangi saat diliminde
sefer eklenmeli ya da azaltılmalı?"

Okuyucu: repoya 2 dakika bakan bir işe alımcı. Başarı: README'nin ilk ekranında soru, 3–5 sayısal
bulgu ve canlı panel linki; panelde tek bakışta okunan bir öneri kartı; her sayının nasıl
üretildiği notebook'tan izlenebiliyor.

## Hedefler

- Kullanıcının kararı: İstanbul raylı sistemler, sefer planı sorusu.
- Kullanıcının kararı: sade ve açıklanabilir yöntem, veri hazırlığı SQL ile, panel Streamlit.
- Kullanıcının kararı: tüm proje çıktıları (README, panel, notebook) İngilizce.
- Tahminin geçmişe karşı sınanması ve hatanın açıkça raporlanması.
- Verinin ölçemediği şeylerin açıkça yazılması (aşağıda "Sınırlar").

## Hedef olmayanlar

- Otobüs ve deniz hatları; gerçek zamanlı veri; otomatik güncellenen veri hattı.
- Makine öğrenmesi modelleri (LightGBM, Prophet vb.), derin öğrenme.
- Slayt / PDF rapor (README rapor görevini görür).
- Power BI / Tableau.

## Karşı-hedefler (teknik olarak çalışsa bile başarısızlık)

- Verinin desteklemediği kesinlikte öneri vermek ("M2'ye 08:00'de 3 sefer ekleyin" gibi).
- Açıklanamayan gruplar veya "kara kutu" tahmin.
- Çalıştırmak için 10+ GB ham veri isteyen bir repo: panel küçük, hazır bir özet dosyayla çalışmalı.

## Veri (doğrulandı, 2026-11-15)

Kaynak: İBB Açık Veri Portalı (`data.ibb.gov.tr`, CKAN API, İBB Açık Veri Lisansı).

| Veri seti (CKAN id) | İçerik | Not |
|---|---|---|
| `hourly-public-transport-data-set` | Ocak 2020 – Ekim 2024, aylık CSV. Sütunlar: `transition_date, transition_hour, transport_type_id, road_type, line, transfer_type, number_of_passage, number_of_passenger, product_kind, transaction_type_desc, town, line_name, station_poi_desc_cd` | Dosya başına 1,3–1,8 GB (Ağustos–Ekim 2024: 0,27–0,39 GB); Ocak 2023 – Ekim 2024 toplamı 31,5 GB. "Aralık 2024" dosyasının adı `202512`. Raylı satırlar `road_type = 'RAYLI'`; `line_name` hat kodu (M2, T4…), `station_poi_desc_cd` istasyon. Kasım/Aralık 2024 dosyaları boş. |
| `rayli-sistemler-hat-bazli-sefer-sayilari` | Hat başına **aylık** sefer sayısı, 2017'den itibaren (XLSX, tarih Excel seri numarası). Hatlar: M1–M9, T1, T3, T4, T5, F1, F4, TF1, TF2 | Saatlik sefer verisi yok. |
| `rayli-sistemler-istasyon-bazli-yolcu-ve-yolculuk-sayilari` | 2021–2025, istasyon × gün, koordinatlı (`;` ayraçlı, koordinat biçimi bozuk) | İsteğe bağlı, aşağıya bakın. |

**Kullanılacak dönem:** aşağıdaki "Dönem kararı" bölümü bunun yerine geçer. İlk hali (benim kararım): saatlik verinin raylı kısmı, Ocak 2023 – Ekim 2024
(22 ay; pandemi dönemi dışarıda, bir tam yıl mevsimsellik + sınama dönemi). İndirme boyutu sorun
olursa builder dönemi Ocak 2024 – Ekim 2024'e kısaltabilir ve bunu README'de belirtir.

## Yaklaşımlar

1. **Sade + SQL + Streamlit — seçildi.** DuckDB SQL ile özet, kural tabanlı gruplar, sınanmış basit
   tahmin, Streamlit paneli. Veri analisti rolüne en uygun; SQL becerisini gösterir. Bedeli: model
   gösterişli değil.
2. **Model ağırlıklı.** İstasyon-saat bazında ML tahmini. Hata biraz düşebilir, ama açıklaması zor
   ve veri bilimci rolüne kayar. Seçilmedi.
3. **Power BI / Tableau.** İlanlarda aranan araç, ama canlı link zor ve repo daha az kod gösterir.
   Seçilmedi.

## Tasarım

### 1. Veri hazırlığı (SQL)

- Aylık CSV'ler tek tek okunur, yalnızca raylı satırlar tutulur, ham dosya saklanmaz.
- Çıktı: `istasyon × tarih × saat` düzeyinde yolcu sayısı, bilet tipi (tam / indirimli / ücretsiz)
  ve aktarma payıyla birlikte, tek bir Parquet dosyası (repo dışında, `.gitignore`).
- Sorgular `sql/` klasöründe okunabilir `.sql` dosyaları olarak durur; README'den linklenir.
- Takvim tablosu: hafta içi / cumartesi / pazar, resmî tatiller, dini bayramlar, okul tatilleri
  (2023–2024 için elle yazılmış küçük bir CSV, kaynağı belirtilerek).

### 2. İstasyon grupları

- İstasyon başına özellikler: hafta içi/hafta sonu oranı, sabah zirvesi payı, akşam zirvesi payı,
  gün ortası payı, gece payı, indirimli (öğrenci) bilet payı, aktarma payı.
- Önce k-means ile keşif (4–6 grup), sonra grupları **birkaç cümlelik basit kurala** indirgeme
  (sığ bir karar ağacı yardımıyla); amaç, istasyonun grubunu tek bakışta söyleyen kısa bir kural. Beklenen türden
  gruplar: sabah çıkışlı konut, akşam çıkışlı iş merkezi, öğrenci, turist/eğlence, aktarma merkezi.
  Gerçek gruplar veriden çıkar; isimleri builder verir.
- Kuralın k-means atamalarıyla ne kadar örtüştüğü raporlanır.

### 3. Tahmin ve sınama

- Tahmin: `yolcu(istasyon, gün tipi, saat) = istasyonun son N haftadaki tipik profili × özel gün katsayısı`.
- Grupların işi burada: özel günler az olduğu için katsayılar **istasyon yerine grup düzeyinde**
  tahmin edilir (az verisi olan bir istasyon, kendi birkaç özel gününden değil grubunun ortak davranışından öğrenir).
- Sınama (dönem kararıyla güncellendi, aşağıya bakın): ana sınama Nisan–Mayıs 2024, ek sınama Haziran–Temmuz 2024; her biri 8 hafta gizlenir. Üç yöntem karşılaştırılır: (a) özel gün
  katsayısı yok, (b) istasyon bazlı katsayı, (c) grup bazlı katsayı. Ölçüt: istasyon-gün ve
  hat-saat dilimi düzeyinde ortalama mutlak yüzde hata. Hangisi kazanırsa o kullanılır ve sonuç
  dürüstçe yazılır (gruplar yardımcı olmazsa bu da bir bulgudur).
- Tahmin ufku (dönem kararıyla güncellendi): Ağustos 2024, "yaz senaryosu". İlk hali: verinin bittiği yerden sonraki 4 hafta (Kasım 2024). README'de verinin Ekim 2024'te
  bittiği açıkça yazılır.

### 4. Öneri kartı

- Birim: hat × gün tipi (hafta içi / cmt / pazar) × saat dilimi (erken, sabah zirvesi, gün ortası,
  akşam zirvesi, akşam, gece).
- Yük göstergesi: `sefer başına biniş = tahmini biniş / o dilimdeki sefer`.
  Aylık sefer sayısı gerçek veriden gelir; saat dilimlerine dağıtımı **varsayımdır**.
  Temel varsayım: seferler işletme saatlerine eşit dağılır. Duyarlılık: zirve saatlerde 1.0x–2.0x
  daha sık sefer. Panelde bu bir kaydırıcıdır; bir okumanın varsayıma ne kadar bağlı olduğunu gösteren duyarlılık testi.
- Öneri, **hattın kendi içinde** göreli yüke dayanır: en yüklü dilimler "sefer ekle", en boş
  dilimler "azaltılabilir", gerisi "koru". Bir öneri ancak duyarlılık aralığının tamamında aynı
  kalıyorsa "sağlam" diye işaretlenir.
- Yalnızca hem yolcu hem sefer verisi olan hatlar öneri alır; diğerleri (ör. Marmaray) yalnızca
  talep görünümünde yer alır.

### 5. Panel (Streamlit, tek sayfa, İngilizce)

```
┌──────────────────────────────────────────────────────────────────────┐
│ Istanbul Metro Service Planner            [Line: M2 ▾] [Day: Weekday ▾]│
├──────────────────────────────────────────────────────────────────────┤
│  Riders/day   Trips/day   Boardings/trip   Forecast error (backtest)  │
│   412k          540          763               11%                    │
├───────────────────────────────┬──────────────────────────────────────┤
│ Recommendation card           │ Hourly demand vs assumed service     │
│ Early    ░ keep               │  (line chart, 24h, peaks shaded)     │
│ AM peak  █ ADD   (robust)     │                                      │
│ Midday   ░ keep               │                                      │
│ PM peak  █ ADD                │                                      │
│ Evening  ░ keep               │                                      │
│ Night    ▒ can reduce         │                                      │
├───────────────────────────────┼──────────────────────────────────────┤
│ Station groups on this line   │ Next 4 weeks: forecast & special days│
│ (bar per station, coloured    │  (daily bars, holidays marked)       │
│  by group)                    │                                      │
├───────────────────────────────┴──────────────────────────────────────┤
│ Peak-service assumption  1.0x ───●──── 2.0x     "What we can't measure"│
└──────────────────────────────────────────────────────────────────────┘
```

(Sayılar yer tutucudur.) Panel yalnızca repodaki küçük bir `data.json` dosyasını okur; ham veriye
ihtiyaç duymaz. Görünüm inşa öncesinde tarayıcıda bir taslakla ayrıca gösterilebilir.

### 6. Repo yapısı

```
~/istanbul-metro-planner/
  README.md                      soru, bulgular, öneri tablosu, yöntem, sınırlar, çalıştırma
  analysis.ipynb                 gruplar, sınama, tahmin, öneri kartı (uçtan uca)
  sql/                           veri hazırlığı sorguları
  scripts/build_data.py          CSV'leri indir → Parquet özet
  scripts/make_app_data.py       Parquet → app/data.json
  data/calendar.csv              özel günler
  data/station_groups.csv        istasyon → grup
  data/recommendations.csv       hat × gün tipi × dilim → öneri
  app/streamlit_app.py           panel
  app/model.py                   formüller (tahmin, yük göstergesi, öneri kuralı)
  app/data.json                  panelin okuduğu sayılar
  app/requirements.txt
  tests/test_model.py            model.py formüllerinin testleri
```

Araçlar (benim kararım): Python, DuckDB, pandas, scikit-learn, Streamlit, Altair, pytest.

## Gözden geçirme sonrası netleşenler (hepsi benim kararım)

- **Talep ölçüsü:** `number_of_passage` (biniş/geçiş). `number_of_passenger` tekil yolcu sayısıdır
  ve yalnızca yardımcı bilgi olarak tutulur. Belgede "yolcu" geçen her yerde kastedilen biniştir.
- **Analiz birimi:** istasyon-hat çifti (`station_poi_desc_cd` + `line_name`). Yenikapı gibi ortak
  istasyonlar her hat için ayrı birimdir. Builder, ortak istasyonlarda `line_name` atamasının
  tutarlı olduğunu ilk iş olarak kontrol eder; tutarsızsa o istasyonlar tek birim sayılır ve bu
  README'de yazılır.
- **Gün tipine sefer dağılımı:** bu da varsayımdır. Temel durum: her gün eşit sefer. İkinci
  duyarlılık parametresi: hafta sonu sefer oranı 0.6x–1.0x. Bir hattın 18 hücresi (3 gün tipi ×
  6 dilim) **birlikte** sıralanır; "sağlam" etiketi için öneri hem zirve (1.0x–2.0x) hem hafta sonu
  (0.6x–1.0x) aralığının tamamında aynı kalmalıdır.
- **Ölçülen (varsayımsız) bulgu:** hat başına aylık `biniş / sefer` eğilimi, Ocak 2023 – Temmuz 2024.
  Bu, README'nin ve panelin gerçek veriye dayanan ana göstergesidir; saat dilimi kartı onun üstüne
  kurulan senaryodur.
- **Sınama iki parçalı:** (1) genel hata için Nisan–Mayıs 2024 (ana) ve Haziran–Temmuz 2024 (ek); (2) özel gün
  katsayılarını ayırt etmek için 2024'ün özel günleri (Ramazan ve Kurban bayramları, resmî
  tatiller, yarıyıl ve yaz tatili başlangıcı) tek tek gizlenip öncesindeki veriden tahmin edilir.
  Üç yöntemin karşılaştırması (2) üzerinden yapılır. Sonuç belirsiz çıkarsa öyle raporlanır.
- **Yeni açılan / uzatılan hatlar ve istasyonlar:** dönem içinde 12 aydan az verisi olanlar
  gruplamaya, katsayı tahminine ve öneri kartına girmez; yalnızca talep görünümünde yer alır.
- **Sefer ayı:** sefer dosyası Ocak 2017'den başlayan 108 aylık satır içeriyor (Aralık 2025'e
  kadar görünüyor; builder doğrular). Ağustos 2024 önerisi için Ağustos 2024'ün gerçek sefer sayısı
  kullanılır; bir hat için yoksa son mevcut ay kullanılır ve işaretlenir.
- **Repo kalıbı:** README'de bulgular + tablo, tek notebook, `model.py` + `data.json` ile çalışan
  panel, duyarlılık testi.

## Dönem kararı (Batuhan, 2026-11-15; önceki dönem tanımlarının yerine geçer)

Görev 2'de kaynak verinin Ağustos 2024'ten itibaren eksik olduğu görüldü (ayrıntı `docs/data-notes.md`).
Batuhan'ın kararı:

- **Analiz dönemi:** Ocak 2023 – Temmuz 2024 (19 tam ay). Gruplar, katsayılar ve profiller yalnızca bu dönemden.
- **Ana sınama:** Nisan–Mayıs 2024 (okul dönemi), 8 hafta.
- **Ek sınama:** Haziran–Temmuz 2024, 8 hafta.
- **Tahmin:** Ağustos 2024. README ve panelde "yaz senaryosu" (summer scenario) olarak adlandırılır.
- **Gerçekle karşılaştırma:** Ağustos–Ekim 2024'teki 19 tam gün, Temmuz 2024 sonuna kadarki veriyle yapılan tahminle karşılaştırılır ve hata raporlanır.
- **Sınırlar:** kırılma kaynak verinin kendisinde olduğu için README'deki "What we can't measure" bölümünde yazılır.

## Sınırlar (README'de "What we can't measure" başlığıyla yazılacak)

- Sefer verisi aylık; saatlik dağılım varsayımdır.
- Veri **binişleri** sayar, trendeki doluluğu değil; inişler ve yolculuk uzunluğu bilinmiyor.
- Tren kapasitesi (vagon sayısı) hatlar arasında farklı ve veride yok; bu yüzden hatlar birbiriyle
  değil, her hat kendi saat dilimleriyle karşılaştırılır.
- Kaynak veri Ağustos 2024'ten itibaren eksik: Ağustos–Ekim 2024'ün 79 gününden yalnızca 19'u tam, Ekim dosyası 18'inde bitiyor, Kasım–Aralık dosyaları boş. Eksiklik İBB dosyalarının kendisinde (otobüs ve vapur için de aynı), bizim işlememizden değil. Bu yüzden analiz Temmuz 2024'te bitiyor ve Ağustos–Ekim aylık toplamları kullanılmıyor.

## Builder'a bırakılanlar

- Grup sayısı, grup isimleri ve kuralın tam hali (veriden).
- Tipik profil için N hafta, "ekle / azalt" eşikleri.
- `product_kind` değerlerinin (INDIRIMLI1, INDIRIMLI2, UCRETSIZ…) hangisinin öğrenci olduğunun
  doğrulanması; doğrulanamazsa özellik "indirimli pay" olarak kalır.
- İsteğe bağlı ek: istasyon-gün veri seti (2025'e kadar) ile Ağustos 2024 sonrası tahminin gerçek
  veriye karşı sınanması. İstasyon adları iki veri setinde kolayca eşleşirse yapılır, yoksa atlanır.

## Yayın

Yerel git reposu builder tarafından kurulur. GitHub'a public repo olarak göndermek ve Streamlit
Community Cloud'da yayınlamak dışa dönük adımlardır; Batuhan'ın onayıyla, en sonda yapılır.

## Doğrulama

1. `python scripts/build_data.py` Parquet özetini üretir; satır sayıları ve ay başına toplam yolcu
   ham CSV'den alınan bağımsız bir toplamla tutar (en az bir ay için).
2. `pytest` geçer (tahmin formülü, yük göstergesi, öneri kuralı, duyarlılık altında "sağlam" etiketi).
3. Notebook baştan sona hatasız çalışır; README'deki her sayı notebook çıktısıyla aynıdır.
4. `streamlit run app/streamlit_app.py` açılır; her hat ve gün tipi seçiminde kart ve grafikler
   dolar, kaydırıcı önerileri değiştirir, ham veri olmadan çalışır (yalnızca `data.json`).
5. Sınama hatası README'de ve panelde aynı sayıdır.

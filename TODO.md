# FinPortal.si TODO

## Naslednje (prioriteta / največji ROI)
- [ ] **[22]** Modernizirati lead page `povprasevanje.html` (trust blok, boljši form UI)
- [ ] **[20]** Modernizirati UI kalkulatorjev (inputs, rezultat kartice, CTA)
- [x] **[44]** social proof: Podatki 11 slovenskih bank, Neodvisen finančni portal, Brezplačna uporaba, Narejeno v Sloveniji (dodati eno kratko sekcijo na začetku strani)
- [ ] **[24]** Preveri ali so na vseh straneh slike optimizirane (alt, size, format)
- [ ] **[21]** Modernizirati izgled člankov (tipografija, max širina, TOC, spacing)
- [ ] **[48]** Google Discover - dodaj vsebino za Google Discover (+ velike slike za članke)
- [x] **[26]** Dodaj "back to top" gumb na dolgih straneh
- [ ] **[28]** Poenostavi navigacijo (kjer lahko)
- [ ] **[29]** Izboljšaj vizualno hierarhijo
- [x] **[61]** Pri vrsti kredita naj se ob izbiri avtomatično izpiše neka pričakovana vrednost za OM (najdi podatek o povprečni OM pri BS) in dopiši nekam da je to pravilo in se lahko pe vedno spremeni vrednost ročno.
- [ ] **[62]** Naredi tabelo pričakovanih OM za različne vreste kreditov in naredi članek iz tega in povezavo do kalkulatorja. Dodaj simulacijo ali neko dodatno analizo kaj se zgodi če se bo OM spremenila navzgor, kot je pričakovano zaradi EURIBORA.

## Predlogi (novi hitri win-i)
- [ ] **[51]** GSC: pregled in odprava 404 URL-jev
  - [x] Cloudflare Bulk Redirects: dodana lista `finportal_legacy_urls` + rule (301) za stare URL-je (/kalkulatorji/* → root, /clanki/primerjava-depozitov.html → /primerjava-depozitov.html)
  - [ ] GSC: v poročilu “Ni bilo mogoče najti (404)” klikni “Preveri popravek”
  - [ ] GSC: čez 3–7 dni preveri, da se status premika v validating/passed in da se število 404 zmanjšuje
- [ ] **[63]** GitHub Issues: uvedi sledenje bugov/feature requestov (labels + bug report template), da bo odpravljanje bolj sistematično.
- [ ] **[60]** URL kanonikalizacija: poenoti internal linke + canonicale + sitemap na isto končno verzijo (https, brez www, brez /index.html, konsistentno .html) + preveri Cloudflare Bulk Redirects, da ni redirect verig
  - [x] `script.js`: “Povezani članki” linki na članke so konsistentno z `.html`
  - [x] Cloudflare Redirect Rules: izjema za `https://www.finportal.si/index.html` → `https://finportal.si/` (redirect chain 2 → 1) + GSC “Preveri popravek” kliknjen
- [ ] **[58]** Breadcrumbs + kategorijske strani za članke: ponovno preveri, ko bo 50+ člankov (odločitev A vs B2: samo UI breadcrumbs vs indexable kategorije `/clanki/varcevanje/` ipd.)
- [ ] **[52]** Internal linking: dodaj povezave iz home/"kalkulatorji" na ključne podstrani + povezovanje člankov → kalkulatorji (dvigne SEO)
- [ ] **[59]** Internal linking: dodaj povezave iz kalkulatorjev → relevantni članki (modul "Povezani članki" na kalkulatorjih; po potrebi tudi članki → kalkulatorji) + Dodaj “lead form” v članke Npr. pod člankom o EURIBOR.
- [ ] **[53]** FAQ + FAQPage schema na ključnih straneh (kreditni kalkulator, kreditna sposobnost, primerjava depozitov)
  - [x] `kreditni-kalkulator.html`: dodan `FAQPage` JSON-LD
  - [x] `kreditna-sposobnost.html`: dodan `FAQPage` JSON-LD
  - [x] `clanki/eom-zakaj-ti-banka-o-tem-ne-govori.html`: dodan `FAQPage` JSON-LD
  - [ ] `primerjava-depozitov.html`: dodaj FAQ sekcijo + `FAQPage` (če/ko ima smisel)
-   - [ ] `primerjava-depozitov.html`: dodaj FAQ sekcijo + `FAQPage` (če/ko ima smisel)
- [ ] **[54]** Core Web Vitals: audit LCP/CLS/INP na mobilnih (PageSpeed) + popravki (hero image, font loading, lazy/eager)
- [x] **[55]** Članki (`clanki/index.html`): dodaj iskalnik + client-side filtriranje po kategorijah prek `data-category` (zaenkrat: `krediti`, `varcevanje`, `investicije`) + stanje "ni zadetkov" + fallback, da je brez JS seznam še vedno viden

## Tehnično (perf + struktura)
- [ ] **[9]** Poenotiti structured data (JSON-LD) še na vseh ostalih “legal/info” straneh inline (brez odvisnosti od JS)
- [x] **[37]** v google je še vedno viden modri planet, in ne favicon (urejeno: preveri čez par dni)

## Večji projekti / kasneje
- [ ] **[25]** Izboljšaj mobilno izkušnjo (največ uporabnikov bo tam)
   - [x] Sticky mobilni lead CTA na kalkulatorjih ("Pošlji povpraševanje banki")
   - [x] Po kliku na "Izračunaj": auto-scroll na rezultate + pulse highlight na modrem CTA
   - [x] Cache-busting: `style.css?v=2026-04-08-1` + `script.js?v=2026-04-08-1` (da se spremembe vidijo tudi na telefonu)
   - [ ] B: tap targeti + odstrani horizontal overflow (če/ko opazimo na mobilnem)
   - [x] Kreditni kalkulator (mobilno): odstrani horizontalni “slajder” (overflow-x) in naredi layout v eni koloni (v delu)
   - [x] Primerjava depozitov (mobilno): tekst pod tabelo se trenutno skrola skupaj s tabelo pri slajdanju levo/desno — popraviti (prioritetno).
- [ ] **[25C]** Mobilni pilot: izberi 1 kalkulator in tam najprej uredi mobile quick wins (sticky CTA + tap targeti + overflow), nato razširi na ostale.
- [ ] **[30]** Označi najboljše ponudbe v tabeli z depoziti - oblika kot v članku, kjer primerjam EOM med bankami?
- [ ] **[31]** Dodaj KDO SMO, v sekciji O NAS
- [ ] **[34]** lead_form naj se avtomatično zapolne s podatki, ki so bili zadnji vnešeni s strani uporabnika
- [ ] **[35]** Dodaj Google Tag Manager (GTM) - je to smiselno? koliko dela?
- [x] **[36]** Dodaj varovalke, da se v tabele lahko vnašajo samo smiselne vsebine (znesek, ročnost, telefon- samo številke, ime in priimek samo črke, mail mora vsegovati @ in .), itd.
- [ ] **[38]** povpraševanja (leadi) in z njimi povezani kontaktni podatki: do 90 dni od oddaje povpraševanja - kako zagotoviti?! avtomatizirati? Odloženo do sestanka z banko: implementacija audit log + 90-dnevna hramba.
- [x] **[39]** v script.js je treba narediti link, kjer pod tabelo za depozite piše info@finportal.si mail - povezava do kontaktnega obrazca
- [ ] **[42]** dodaj "pošlji izračun na mail" in "shrani izračun"
- [ ] **[45]** DODAJ PRIMORSKO HRANILNICO - naredi nov scraper in razširi bazo bank. https://phv.si/obrestne-mere/#obrestne-pasivni-posli 
- [ ] **[46]** Lahko bi dodal se tarife za potrosniske & stanovanjske kredite vseh bank.
- [x] **[49]** Prihranek obresti: primerjava obresti po rednem amortizacijskem načrtu vs z predčasnimi vplačili (razlika 2 amortizacij). Dodan prikaz baseline obresti in pravilno osveževanje rezultatov.
- [ ] **[57]** Cache rate dvigniti na 60-80 %

## Completed
- [x] **[19]** Modernizirati Home page (index.html): hero + sekcije + tipografija + spacing + CTA (minimalen redesign)
- [x] **[17]** Popraviti JS napako (ReferenceError `formatThousandsSI` v lead form flow), da `povprasevanje` stran ne meče rdečih napak in da GA4 test lahko deluje
- [x] **[11]** GA4: uvesti enoten dogodek za uspešno oddajo leada `lead_form_submit` in ga označiti kot Conversion
- [x] **[12]** GA4: dodati parameter `lead_type` (credit/deposit) k lead dogodkom za ločeno poročanje/cenik
- [x] **[10]** Odpraviti `www` origin pri nalaganju `all_banks.csv`/`latest.csv` v `script.js` (force non-www origin)
- [x] **[8]** Nastaviti priporočeni format v `clanki/template-clanek.html` za `datePublished`/`dateModified` na ISO datetime z 00:00:00 in timezone
- [x] **[7]** Popraviti Rich Results 'nekritične težave' za članke: datePublished/dateModified naj bosta ISO datetime z timezone
- [x] **[2]** Implementirati generiranje `BreadcrumbList` v `script.js` za ključne strani (root kalkulatorji/primerjave/leksikon) z mappingi
- [x] **[3]** Dodati `BreadcrumbList` v `clanki/template-clanek.html` (Domov → Članki → Naslov)
- [x] **[6]** Batch posodobitev obstoječih člankov v `/clanki/*.html` (inline BreadcrumbList)
- [x] **[18]** Lead forma: omejiti vnose na smiselne vrednosti (znesek kredita/depozita samo številke, ročnost samo številke v dovoljenem razponu, validacija email/telefon)
- [x] **[16]** GA4: zagotoviti, da se `lead_form_submit` dejansko sproži (trenutno je submit gumb na `povprasevanje.html` `disabled`) – omogočiti testni submit ali sprožiti event na alternativni akciji
- [x] **[43]** faviconi niso WebP - morda lahko to izboljšamo v nadaljevanju - ODLOČITEV: “ne delamo WebP za favicon”
- [x] **[47]** Dodati v kalkulator za kredit, da bi lahko dolocil še mesecna/letna vplačila za predhodno poplačilo kredita. Predlog? na tej strani je ena ideja https://jsfiddle.net/bjs475gw/
- [x] **[56]** template članka ima zdaj [[...]] placeholderje + [[KATEGORIJA]] + articleSection v JSON-LD.

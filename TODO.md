# FinPortal.si TODO

## High priority
- [ ] **[18]** Lead forma: omejiti vnose na smiselne vrednosti (znesek kredita/depozita samo številke, ročnost samo številke v dovoljenem razponu, validacija email/telefon)
- [ ] **[16]** GA4: zagotoviti, da se `lead_form_submit` dejansko sproži (trenutno je submit gumb na `povprasevanje.html` `disabled`) – omogočiti testni submit ali sprožiti event na alternativni akciji
- [ ] **[15]** GA4: označiti `lead_form_submit` kot Conversion v GA4 (po tem ko se event vsaj enkrat sproži)
- [ ] **[13]** GSC: pregled “Pages/Strani” (Indexed vs Not indexed) in odprava glavnih razlogov za neindeksiranje (Discovered/Crawled currently not indexed, duplicate/canonical ipd.) za ključne strani + članke

## Medium priority
- [ ] **[14]** Cloudflare: potrditi, da je `www` → non-`www` preusmeritev vedno `301` (ne `302`) za home in tipične podstrani
- [ ] **[20]** Modernizirati UI kalkulatorjev (inputs, rezultat kartice, CTA)
- [ ] **[21]** Modernizirati izgled člankov (tipografija, max širina, TOC, spacing)
- [ ] **[22]** Modernizirati lead page `povprasevanje.html` (trust blok, boljši form UI)

## Low priority
- [ ] **[9]** Poenotiti structured data (JSON-LD) še na vseh ostalih “legal/info” straneh inline (brez odvisnosti od JS)

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
## My additional suggestions
- [ ] **[23]** Preveri ali so na vseh straneh meta opisi, naslovi in slike
- [ ] **[24]** Preveri ali so na vseh straneh slike optimizirane (alt, size, format)
- [ ] **[25]** Izboljšaj mobilno izkušnjo (največ uporabnikov bo tam)
- [ ] **[26]** Dodaj "back to top" gumb na dolgih straneh
- [ ] **[27]** Dodaj "share" gumb na člankih
- [ ] **[28]** Poenostavi navigacijo (kjer lahko)
- [ ] **[29]** Izboljšaj vizualno hierarhijo
- [ ] **[30]** Označi najboljše ponudbe v tabeli z depoziti - oblika kot v članku, kjer primerjam EOM med bankami?
- [ ] **[31]** Dodaj KDO SMO, v sekciji O NAS
- [ ] **[32]** Dodaj Članke, FAQ vsebino
- [ ] **[33]** Dodaj slike in grafe k člankom
- [ ] **[34]** lead_form naj se avtomatično zapolne s podatki, ki so bili zadnji vnešeni s strani uporabnika
- [ ] **[35]** Dodaj Google Tag Manager (GTM) - je to smiselno? koliko dela?
- [ ] **[36]** Dodaj varovalke, da se v tabele lahko vnašajo samo smiseln6e vsebine (znesek, ročnost, telefon- samo številke, ime in priimek samo črke, mail mora vsegovati @ in .), itd.
- [ ] **[37]** v google je še vedno viden modri planet, in ne favicon
- [ ] **[38]** povpraševanja (leadi) in z njimi povezani kontaktni podatki: do 90 dni od oddaje povpraševanja - kako zagotoviti?! avtomatizirati? je to že?
- [ ] **[39]** v script.js je treba narediti link, kjer pod tabelo za depozite piše info@finportal.si mail - povezava do kontaktnega obrazca
- [ ] **[40]** kako iz ga4 analitike izločim sebe?
- [ ] **[41]** Dropdown “Kalkulatorji” je predolg - morda narediva raje ločnico med krediti/varčevanje/investicije?
- [ ] **[42]** dodaj "pošlji izračun na mail" in "shrani izračun"
- [ ] **[43]** Logotipi (scit8 in scitmali) in faviconi niso WebP - morda lahko to izboljšamo v nadaljevanju



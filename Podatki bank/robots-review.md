# Robots.txt pregled virov (FinPortal.si)

Datum: 2026-03-20

Ta dokument služi kot kratek dokaz, da je bil opravljen pregled `robots.txt` za uradne vire, iz katerih se črpajo podatki o depozitih (URL-ji/PDF-ji so navedeni v `offers.json`).

## Povzetek

- Večina bank v `robots.txt` ne blokira splošnega dostopa do javnih vsebin.
- Kjer so omejitve, so večinoma vezane na administrativne/tehnične poti, iskalnike ali URL-je s parametri.
- Pri avtomatizaciji je priporočljivo spoštovati `Crawl-delay` (kjer je naveden) in se izogibati URL-jem z `?` parametri, če so ti blokirani.

## Rezultati po domenah

### www.addiko.si
- `Disallow`: /wp-admin/, /profiles/, /misc/, /icons/, /.web, /sites/, /slides/, /quick-menu/, /old/ …
- `Allow`: /wp-admin/admin-ajax.php
- `Sitemap`: https://www.addiko.si/sitemap_index.xml

### www.bksbank.si
- `Disallow`: /services/site, /services/preview, /services/contact, /services/contentserver, /services/contentserverexport, /api, /gateway

### www.dbs.si
- `User-agent: *` (brez `Disallow` pravil)
- `Sitemap`: https://www.dbs.si/sitemap.xml

### www.dh.si
- `Allow: /`
- `Sitemap`: https://www.dh.si/sitemap.xml.gz

### www.gbkr.si
- `Disallow:` (prazno)
- `Sitemap`: https://www.gbkr.si/sitemap_index.xml

### www.intesasanpaolobank.si
- `User-agent: *` → `Allow: /`
- `User-agent: Googlebot` → `Disallow`: /nogooglebot/, /onboarding/
- `Sitemap`: https://www.intesasanpaolobank.si/sitemap.xml

### www.lon.si
- `Crawl-delay: 10`
- `Disallow`: večinoma sistemske/admin poti (npr. /admin/, /user/login/, /search/, /includes/, /modules/, /themes/ …)
- Opomba: priporočeno je striktno spoštovati `Crawl-delay`.

### www.nlb.si
- `User-agent: *` → `Allow: /`
- `Sitemap`: https://nlb.si/sl.sitemap.xml

### www.otpbanka.si
- `Disallow`: /close/, /nop/, /layouts/, /system/
- `Sitemap`: https://www.otpbanka.si/sitemap.xml

### www.sparkasse.si
- `Disallow`: /*.compare, /*.question, /*nodeId=

### www.unicreditbank.si
- `Sitemap`: https://www.unicreditbank.si/sitemap.xml
- `User-agent: *` → `Disallow`:
  - /*from=adwords
  - /*utm_source
  - /*gclid=
  - /search.*
  - *?modal_page
  - /application-forms/
  - /popupeditpages/
  - /*?
  - /internet-banking-login-page.html
  - /internet-banking-login-page-bn.html
  - /error404.html
- Opomba: avtomatsko pridobivanje vsebine `robots.txt` je v našem orodju vračalo `403 Forbidden`, vsebina je bila preverjena z ročnim ogledom v brskalniku.

## Opombe / omejitve

- `robots.txt` je tehnična smernica za crawlerje, ne nadomešča Pogojev uporabe (ToS) ali drugih pravnih omejitev.
- Priporočilo za avtomatizacijo:
  - spoštuj `Crawl-delay` (kjer je naveden),
  - uporabljaj “čiste” URL-je brez parametrov, če je `/*?` ali podobno disallow,
  - ne obremenjuj domen s preveč zahtevami v kratkem času.

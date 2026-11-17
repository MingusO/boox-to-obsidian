# Installationsguide

Denne guide tager dig fra nul til et kørende system, hvor dine håndskrevne Boox noter bliver læst, rettet, opsummeret og lagt i din Obsidian vault.

Tid: ca. 45 minutter første gang.

## Indhold

1. Overblik
2. Det skal du have klar
3. Trin 1: Anthropic API nøgle
4. Trin 2: Tjek at Boox lægger PDF'erne i Drive
5. Trin 3: Giv programmet læseadgang til Drive
6. Trin 4: Installér add on'et i Home Assistant
7. Trin 5: Udfyld indstillingerne
8. Trin 6: Første test
9. Trin 7: Få vaulten ind i Obsidian
10. Trin 8: Daglige noter
11. Trin 9: Sikkerhedskopi
12. Tilføj en notesbog
13. Fejlfinding
14. Opdatering og afinstallation
15. Sikkerhed og pris
16. Sådan er det bygget

## 1. Overblik

```
Boox Note Air 5C
   synkroniserer PDF pr. notesbog
        ↓
Google Drive: Mit drev / onyx / NoteAir5C / Notebooks / Kompan.pdf
        ↓ rclone henter filen hvert 15. minut (kun læseadgang)
Home Assistant Green: add on "Boox til Obsidian"
   1. deler PDF'en i sider og husker hver side via en fingeraftryk
   2. venter til en side har været uændret i 30 minutter
   3. sender kun nye eller ændrede sider til Claude
   4. Claude læser håndskriften og retter stavefejl
   5. skriver markdown til din vault
   6. efter kl. 21 laver Claude en dagsopsummering til daglig note
        ↓
Obsidian vault (Obsidian Sync)
```

Hvorfor Home Assistant Green? Den er tændt døgnet rundt, har 4 GB RAM, kører Docker og bruger næsten ingen strøm. Din Synology DS216 Play er en 32 bit ARM maskine uden officiel Docker understøttelse, så den bruges i stedet som mål for sikkerhedskopi.

## 2. Det skal du have klar

* Home Assistant Green (Home Assistant OS) med adgang til indstillinger som administrator.
* Add on'et "Terminal & SSH" i Home Assistant (du har det allerede).
* En Mac eller PC til at logge ind på Google én gang (til rclone).
* En Anthropic konto med betalingskort.
* Obsidian Sync abonnement, hvis du vil bruge Obsidian Headless (se trin 7).
* Et GitHub repo med denne kode. Din version ligger på `https://github.com/MingusO/boox-to-obsidian`.

## 3. Trin 1: Anthropic API nøgle

1. Gå til `console.anthropic.com` og log ind.
2. Under Billing: tilføj betalingskort og sæt en **månedlig udgiftsgrænse**. Sæt den lavt til at starte med, fx 100 kroner.
3. Under API keys: opret en nøgle med navnet "Boox HA". Kopiér den med det samme, du kan ikke se den igen.
4. Gem nøglen i din adgangskodemanager (du har Vaultwarden i Home Assistant). Den skal ikke i chat, mails eller GitHub.

## 4. Trin 2: Tjek at Boox lægger PDF'erne i Drive

1. Åbn Google Drive i en browser.
2. Naviger til Mit drev, onyx, NoteAir5C, Notebooks.
3. Du skal kunne se PDF filerne, fx `Kompan.pdf`. Tjek at ændringsdatoen er frisk.
4. Skriv på Boox'en, vent på synkronisering og tjek at datoen ændrer sig.

Navnene på filerne bruges i trin 5. Mappen "Mit drev" skal ikke med i stien. Stien til Kompan er altså `onyx/NoteAir5C/Notebooks/Kompan.pdf`.

Tip: Skriv datoen øverst på hver side. Claude læser den og bruger den som sidens dato. Uden dato bruges den dag, siden første gang blev set.

## 5. Trin 3: Giv programmet læseadgang til Drive

Programmet bruger rclone. Du logger ind på Google på din Mac, og får en kode (token), som du lægger i add on'ets indstillinger.

På din Mac, i Terminal:

```bash
brew install rclone
```

```bash
rclone authorize "drive"
```

1. En browser åbner. Log ind med den Google konto, hvor Boox gemmer filerne, og godkend.
2. Terminalen viser en blok, der ligner `{"access_token":"...","token_type":"Bearer","refresh_token":"...","expiry":"..."}` mellem to linjer med pile.
3. Kopiér hele JSON blokken, fra første `{` til sidste `}`.
4. Gem den i din adgangskodemanager. Den skal ind i feltet `drive_token` i trin 5.

Gode at vide:

* Programmet læser kun fra Drive og skriver aldrig. Selve koden bruger kun kommandoen `rclone copyto` fra Drive til hjemmecentralen.
* Koden du får har bredere rettigheder end programmet bruger. Du kan altid tilbagekalde den på `myaccount.google.com/permissions`.
* Hvis loggene senere skriver `invalid_grant`, er koden udløbet eller tilbagekaldt. Kør `rclone authorize "drive"` igen og indsæt den nye kode.

## 6. Trin 4: Installér add on'et i Home Assistant

Der er to måder. Vælg **A** hvis dit repo er offentligt, ellers **B**.

### A. Offentligt repo (nemmest)

1. Åbn Home Assistant. Gå til Indstillinger, Apps (hed tidligere Add ons), Butik.
2. Tryk på menuen med de tre prikker øverst til højre, vælg Repositories.
3. Indsæt `https://github.com/MingusO/boox-to-obsidian` og tryk Tilføj.
4. Genindlæs siden. Find "Boox til Obsidian" nederst i butikken og tryk Installér.

### B. Privat repo (installeres som lokalt add on)

Lav først en adgangsnøgle til GitHub, kun til læsning af dette ene repo:

1. GitHub, Settings, Developer settings, Personal access tokens, Fine grained tokens, Generate new token.
2. Resource owner: din konto. Repository access: Only select repositories, vælg `boox-to-obsidian`.
3. Permissions, Repository permissions: Contents sæt til Read only.
4. Kopiér nøglen.

Åbn "Terminal & SSH" i Home Assistant og kør (erstat nøglen):

```bash
git clone https://MingusO:DIN_NØGLE@github.com/MingusO/boox-to-obsidian.git /root/boox-to-obsidian
```

```bash
sh /root/boox-to-obsidian/scripts/install_local.sh https://MingusO:DIN_NØGLE@github.com/MingusO/boox-to-obsidian.git
```

Derefter: Indstillinger, Apps, Butik, menuen med tre prikker, Tjek for opdateringer. Genindlæs siden. Under "Lokale apps" vises "Boox til Obsidian". Tryk Installér.

Første installation bygger Docker billedet på selve Home Assistant Green. Det kan tage flere minutter.

## 7. Trin 5: Udfyld indstillingerne

Åbn add on'et, fanen Konfiguration. Du kan skifte til YAML visning via menuen med tre prikker. Eksempel:

```yaml
anthropic_api_key: "sk-ant-..."
drive_token: '{"access_token":"...","token_type":"Bearer","refresh_token":"...","expiry":"..."}'
model: claude-sonnet-5-5
summary_model: claude-sonnet-5-5
language: da
poll_minutes: 15
settle_minutes: 30
max_pages_per_run: 25
import_existing: false
timezone: Europe/Copenhagen
vault_path: /share/obsidian_vault
notes_folder: Boox
attachments_folder: Boox/Bilag
daily_folder: 01 PRIVATE/Dagbog/YYYY/MM
daily_format: D. MMMM YYYY dddd
daily_template: ""
summary_hour: 21
notify_service: ""
obsidian_sync: false
notebooks:
  - name: Kompan
    drive_path: onyx/NoteAir5C/Notebooks/Kompan.pdf
    category: Arbejde
    hint: "Noter fra mit arbejde."
  - name: Konceptudvikling og Innovation
    drive_path: onyx/NoteAir5C/Notebooks/Konceptudvikling og Innovation.pdf
    category: Studie
    hint: "Universitetskursus. Skriv kursets emne og vigtige fagudtryk her."
  - name: Kommunikation og Samarbejde i Organisationer
    drive_path: onyx/NoteAir5C/Notebooks/Kommunikation og Sammarbejde i Organisationer.pdf
    category: Studie
    hint: "Universitetskursus. Skriv kursets emne og vigtige fagudtryk her."
```

Vigtigste valg:

* **import_existing**: `false` betyder, at siderne der allerede findes i notesbogen ved første start springes over, og kun nye sider læses. Sæt til `true`, hvis du også vil have de eksisterende sider læst. Siderne får så den dato, de har skrevet på siden, eller første gang de blev set, så skriv datoer på siderne, hvis du vil have dem placeret rigtigt. Du kan skifte fra `false` til `true` senere.
* **hint**: En sætning om kurset hjælper Claude med at læse fagudtryk rigtigt. Fx "Kursus i kompetenceudvikling, begreber: organisationslæring, tavs viden."
* **model og summary_model**: Skift summary_model til en billigere model, hvis du vil spare. Kvaliteten på selve håndskriftslæsningen er vigtigst.
* **daily_format**: Skal matche dit format i Obsidian under Indstillinger, Daglige noter, Datoformat. Din vault bruger `D. MMMM YYYY dddd`, som giver `4. september 2026 fredag`. Understøttede dele er YYYY, MMMM (måned med navn), MM, M, dddd (ugedag), DD og D. Måneder og ugedage skrives på dansk.
* **daily_folder**: Mappen til daglige noter. YYYY og MM erstattes med år og måned, så `01 PRIVATE/Dagbog/YYYY/MM` giver `01 PRIVATE/Dagbog/2026/09`.
* **notes_folder**: Hvor notesbøgerne lægges i vaulten. Standard er mappen `Boox`, og under den kommer `Arbejde` og `Studie` med en mappe pr. notesbog. Ret den, hvis du vil have dem et andet sted.
* **daily_template**: Valgfri sti til din skabelon, relativt til vaulten, fx `Templates/Daily.md`. Bruges kun, når programmet selv skal oprette en daglig note. Understøtter `{{date}}`, `{{title}}` og `{{date:YYYY-MM-DD}}`.
* **notify_service**: Fx `notify.mobile_app_din_telefon`, hvis du vil have besked på telefonen, når nye sider er læst. Find navnet i Udviklerværktøjer, Handlinger.

Tryk Gem.

## 8. Trin 6: Første test

1. Lad `max_pages_per_run` stå på 25.
2. Tryk Start på fanen Info. Slå gerne "Start ved opstart" og "Overvåg" til.
3. Åbn fanen Log. Du skal se "Boox til Obsidian 0.1.0 starter med 1 notesbog(er)".
4. Skriv en side på Boox'en. Vent til den er synkroniseret til Drive.
5. Vent op til 15 minutter for næste tjek og derefter 30 minutter, til siden regnes som færdig. Du kan sætte `settle_minutes` til 0 og `poll_minutes` til 5 under testen.
6. Loggen skriver "Side 1 i Kompan læst (dato)".

Se resultatet. Vaulten ligger i `/share/obsidian_vault`. Du kan se filerne via Terminal & SSH:

```bash
ls -R /share/obsidian_vault
```

```bash
cat "/share/obsidian_vault/Boox/Arbejde/Kompan/"*.md
```

Eller installér add on'et "Samba share" og åbn mappen `share` fra din Mac.

Hvad du skal se i noten for en dag:

* En overskrift pr. side med titel
* Den rettede tekst
* Usikre ord i en callout
* Opgaver som afkrydsningsliste
* En sammenfoldet "Rå transskription"
* En sammenfoldet "Original side" med PDF'en af siden

Er læsningen god nok? Prøv en side med dårlig håndskrift. Hvis resultatet er for svagt, skriv en bedre `hint` for notesbogen.

Dagsopsummeringen laves først efter `summary_hour` (kl. 21). For at teste den sætter du midlertidigt `summary_hour` til 0.

## 9. Trin 7: Få vaulten ind i Obsidian

Vaulten ligger nu på Home Assistant. Din vault i Obsidian ligger andre steder. Der er tre muligheder:

### A. Obsidian Headless på Home Assistant (anbefalet, men beta)

Obsidian har en officiel klient til at synkronisere en vault uden skrivebordsappen. Den er i beta og kræver Obsidian Sync abonnement. Jeg har ikke kunnet teste den mod din konto, så gør det i denne rækkefølge og tjek loggen. Fremgangsmåden:

1. Backup først: Tag en kopi af din vault på Mac'en.
2. Brug Obsidian Sync på dine egne enheder som normalt. Home Assistant bliver en ekstra enhed. Brug **ikke** både Obsidian appen og Headless på samme enhed.
3. Sæt i add on'ets indstillinger:

```yaml
obsidian_sync: true
obsidian_vault_name: "Mingus' Vault"
obsidian_email: "din Obsidian konto e mail"
obsidian_password: "din Obsidian adgangskode"
obsidian_e2ee_password: "krypteringskode, hvis du bruger end to end kryptering"
obsidian_mfa: "6 cifret kode, hvis du bruger 2 faktor"
```

4. Gem og genstart add on'et. Hvis du bruger 2 faktor, skal koden være frisk (den er kun gyldig i et halvt minut), så udfyld den lige før genstart.
5. Loggen skriver "Obsidian Sync er sat op for /share/obsidian_vault". Første gang hentes hele din vault ned til Home Assistant. Det kan tage tid.
6. Når det virker, kan du slette adgangskoderne fra indstillingerne, så de ikke ligger i klar tekst. Opsætningen gemmes i add on'ets egen datamappe.

Fra nu synkroniserer add on'et vaulten før og efter hver runde. Noterne dukker op i Obsidian på din telefon og computer.

Vigtigt: Hvis du retter i en note, som add on'et senere opdaterer, overskrives dine rettelser **ikke** i blokke, du selv har ændret. Skriv dine egne noter udenfor `%% boox ... %%` markørerne.

Virker det ikke (loggen skriver fejl for `ob`)? Brug mulighed B.

### B. Syncthing mellem Home Assistant og din Mac

1. Installér add on'et "Syncthing" i Home Assistant og dele mappen `/share/obsidian_vault`.
2. Installér Syncthing på din Mac og del den samme mappe til en mappe, du åbner som vault i Obsidian (der har Obsidian Sync slået til).
3. Din Mac skal være tændt for at noterne når Obsidian Sync.

### C. Kun test uden sync

Lad `obsidian_sync` stå på `false` og se filerne via Samba, mens du tester.

## 10. Trin 8: Daglige noter

Add on'et lægger en sektion i din daglige note:

```
### Boox: Kompan

Kort opsummering af dagen...

Nøglepunkter
* ...

Opgaver og aftaler
* ...

Se [[Kompan 2026-11-17]]
```

* Eksisterer den daglige note allerede, bliver din tekst ikke rørt. Sektionen sættes nederst.
* Eksisterer den ikke, oprettes den (med din skabelon, hvis du har sat `daily_template`).
* En ny opsummering skrives kun, hvis siderne for dagen er ændret.
* Har du selv rettet i sektionen, bliver den ikke overskrevet.

## 11. Trin 9: Sikkerhedskopi

Du har tre lag. Brug mindst to.

1. **Obsidian Sync** har versionshistorik på selve vaulten.
2. **Home Assistant backup.** Du har allerede add on'et "Google Drive Backup". En fuld backup indeholder mappen `share`, og dermed vaulten. Tjek i backup indstillingerne, at "Share" er med, hvis du bruger delvise backups.
3. **NAS.** Lad Synology hente en kopi. Gør det i to trin:
   * Slå SSH nøgle login til i Terminal & SSH add on'et (indstillingen `authorized_keys`) og tilføj NAS'ens nøgle.
   * Opret en planlagt opgave i DSM (Kontrolpanel, Opgaveplanlægning, Brugerdefineret skript) som kører natligt:

```bash
rsync -a -e "ssh -p 22" root@192.168.0.145:/share/obsidian_vault/ /volume1/backup/obsidian/
```

Til GitHub: Lav sikkerhedskopi til GitHub fra Mac'en eller NAS'en, ikke fra Home Assistant. Initialisér git i en kopi af vaulten, og kør `git add`, `git commit` og `git push` natligt. Brug et **privat** repo, da vaulten indeholder personlige noter. Brug ikke samme repo som denne kode.

## 12. Tilføj en notesbog

1. Find stien i Drive, fx `onyx/NoteAir5C/Notebooks/Andet kursus.pdf`.
2. Tilføj en blok under `notebooks` i add on'ets indstillinger:

```yaml
notebooks:
  - name: Kompan
    drive_path: onyx/NoteAir5C/Notebooks/Kompan.pdf
    category: Kursus
    hint: "..."
  - name: Andet kursus
    drive_path: onyx/NoteAir5C/Notebooks/Andet kursus.pdf
    category: Kursus
    hint: "..."
  - name: Arbejde
    drive_path: onyx/NoteAir5C/Notebooks/Arbejde.pdf
    category: Arbejde
    hint: "Noter fra mit arbejde. ..."
```

3. Gem og genstart add on'et.

Navnet (`name`) skal være unikt og bliver brugt som mappenavn. Ændrer du et navn senere, oprettes en ny mappe, og de gamle sider læses igen (hvis `import_existing` er sand).

## 13. Fejlfinding

* **Loggen siger "Indstilling: anthropic_api_key mangler"**: Feltet er tomt. Udfyld og genstart.
* **"drive_token er ikke gyldig JSON"**: Hele blokken fra rclone skal med, inkl. tuborgparenteser. Brug enkelte citationstegn rundt om i YAML.
* **"rclone fejl ... directory not found"**: Stien er forkert. Husk at udelade "Mit drev" og tjek store og små bogstaver.
* **"rclone fejl ... invalid_grant"**: Koden er udløbet. Kør `rclone authorize "drive"` igen.
* **"HTTP 401" fra Claude**: API nøglen er forkert eller deaktiveret.
* **"HTTP 429" eller "529"**: For mange kald eller overbelastet. Programmet prøver selv igen.
* **"HTTP 400 ... credit balance"**: Der er ikke penge på Anthropic kontoen.
* **Intet sker, selvom du skriver**: Siden skal have været uændret `settle_minutes`. Tjek også at Boox faktisk har synkroniseret.
* **Alle gamle sider blev ikke læst**: `import_existing` er `false`. Sæt til `true`.
* **Side står på forkert dato**: Skriv datoen øverst på siden i fremtiden. Retter du siden på Boox'en, læses den igen.
* **Noten er ikke opdateret efter din egen rettelse**: Det er med vilje. Blokke, du har rettet, overskrives ikke. Slet blokken og dens `%%` markører, så genskabes den næste gang siden ændres.
* **Daglig note får ingen opsummering**: Den laves først efter `summary_hour`.
* **"Obsidian login fejlede"**: Tjek e mail, adgangskode og 2 faktor kode. Koden skal være frisk.

Se detaljer i add on'ets Log. Sæt aldrig din API nøgle eller dit Drive token ind, hvis du beder andre om hjælp. Kopiér kun logbeskederne.

## 14. Opdatering og afinstallation

**Opdatering, mulighed A:** Home Assistant viser en opdatering ved add on'et, når versionen i `boox_obsidian/config.yaml` stiger. Tryk Opdatér.

**Opdatering, mulighed B (lokalt add on):**

```bash
sh /root/boox-to-obsidian/scripts/install_local.sh https://MingusO:DIN_NØGLE@github.com/MingusO/boox-to-obsidian.git
```

Derefter, Indstillinger, Apps, Butik, menuen med tre prikker, Tjek for opdateringer, og tryk Genopbyg eller Opdatér på add on'et.

**Afinstallation:** Stop og afinstallér add on'et. Vaulten i `/share/obsidian_vault` ligger fortsat. Slet den manuelt, hvis du ikke vil have den. Tilbagekald Drive koden på `myaccount.google.com/permissions` og slet API nøglen på `console.anthropic.com`.

## 15. Sikkerhed og pris

* Dine noter sendes til Drive (Boox) og til Anthropic API (til læsning). Anthropics regler for API data finder du hos Anthropic. Dine noter fra arbejdet er med, fordi du har sagt ok.
* API nøglen og Drive koden ligger i add on'ets indstillinger i Home Assistant. Giv ikke andre adgang til din Home Assistant konto, og tag en backup med kryptering (Google Drive Backup kan kryptere med adgangskode).
* Slå Telnet fra på din Synology. Det sender adgangskoden ukrypteret.
* Pris: Du betaler pr. side til Claude plus dagsopsummeringen. Der er et loft pr. runde (`max_pages_per_run`), og du bør sætte en månedlig grænse hos Anthropic. Følg forbruget under Usage på `console.anthropic.com` de første dage, og vælg billigere modeller, hvis det bliver for dyrt.

## 16. Sådan er det bygget

Til dig der vil udvikle videre:

```
boox_obsidian/           Home Assistant add on
  config.yaml            indstillinger og skema
  Dockerfile             Python, rclone, Node (til Obsidian Headless)
  app/
    __main__.py          hovedløkke
    pipeline.py          afstemning af sider, behandling, noter, opsummering
    pdfpages.py          deler PDF og laver fingeraftryk pr. side (pypdf)
    claude.py            kald til Anthropic API (kun standardbiblioteket)
    vault.py             skriver blokke i markdown filer uden at røre dit eget
    state.py             SQLite med sider og opsummeringer
    drive.py             rclone mod Google Drive
    obsidian_sync.py     valgfri Obsidian Headless
    notify.py            besked via Home Assistant
tests/                   automatiske tests (pytest)
```

Kør testene lokalt:

```bash
pip install pypdf pytest
python3 -m pytest tests
```

Nøgleidéer:

* Hver side får et fingeraftryk fra sit indhold. Den samme side på en ny plads sendes ikke igen. En side med nyt indhold på samme plads er en redigering og erstatter den gamle tekst.
* En side behandles først, når den har været uændret i `settle_minutes`, så halvskrevne sider ikke koster penge.
* Alt generet ligger i blokke med markører, og blokkene opdateres på stedet. Programmet rører aldrig tekst udenfor dem.
* Tilstanden ligger i SQLite i add on'ets `/data` mappe og overlever opdateringer.

Næste skridt, når det kører: flere kilder til daglig note (kalender, Strava, mails, Home Assistant hændelser) og søgning på tværs af vaulten med AI.

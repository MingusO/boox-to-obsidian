# Boox til Obsidian

Add on'et henter dine Boox notesbøger (PDF) fra Google Drive, lader Claude læse håndskriften side for side, retter stavefejl, og skriver resultatet til din Obsidian vault sammen med en daglig opsummering.

Den fulde installationsguide ligger i repoets `docs/INSTALL.md`.

## Indstillinger

* `anthropic_api_key`: din API nøgle fra Anthropic.
* `drive_token`: JSON blokken du fik fra `rclone authorize "drive"`.
* `notebooks`: en række pr. notesbog med `name`, `drive_path` (sti fra roden af Mit drev, uden "Mit drev"), `category` (mappe i vaulten, fx Kursus eller Arbejde) og `hint` (valgfri tekst der hjælper Claude, fx fagets emne og fagudtryk).
* `model`: modellen der læser siderne. `summary_model`: modellen der laver dagsopsummeringen. Vælg en billigere model for at spare penge.
* `poll_minutes`: hvor ofte der tjekkes for ændringer.
* `settle_minutes`: en side behandles først, når den har været uændret så længe. Det undgår, at halvskrevne sider sendes til AI.
* `max_pages_per_run`: loft pr. runde. Første gang kan det være mange sider, og de tages så over flere runder.
* `import_existing`: sæt til `false` for kun at behandle sider, der kommer til efter installationen. Sæt til `true` for også at læse de sider, der allerede findes i notesbogen første gang.
* `vault_path`: hvor vaulten ligger. Standard er `/share/obsidian_vault`.
* `notes_folder`, `attachments_folder`, `daily_folder`, `daily_format`, `daily_template`: placering af noter, side PDF'er og daglige noter.
* `summary_hour`: efter dette klokkeslæt (lokal tid) laves dagens opsummering.
* `notify_service`: valgfri Home Assistant notifikation, fx `notify.mobile_app_din_telefon`.
* `obsidian_*`: valgfri Obsidian Headless sync (beta).

## Hvad skrives hvor

* `Noter/<kategori>/<notesbog>/<notesbog> <dato>.md` indeholder siderne fra den dag.
* `Noter/Bilag/<notesbog>/` indeholder en PDF af hver side, som vises i noten.
* `Daily/<dato>.md` får en sektion pr. notesbog med opsummering og link.

Alt der genereres ligger mellem `%% boox ... %%` markører. Dine egne tekster udenfor markørerne bliver aldrig rørt. Retter du selv inde i en blok, overskrives den ikke.

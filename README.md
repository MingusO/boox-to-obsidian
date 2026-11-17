# Boox til Obsidian

Håndskrevne noter fra en Boox Note Air 5C bliver automatisk læst af Claude, stavefejl rettes, og resultatet lægges i en Obsidian vault sammen med en daglig log.

Kører som et Home Assistant add on på en Home Assistant Green.

## Sådan virker det

1. Boox synkroniserer en PDF pr. notesbog til Google Drive.
2. Add on'et henter PDF'en med rclone, finder nye og ændrede sider og venter til de er færdigskrevne.
3. Claude læser siden, transskriberer, retter og trækker dato, titel, usikre ord og opgaver ud.
4. Noter pr. notesbog og dag skrives til vaulten, og en opsummering kommer ind i den daglige note.
5. Valgfrit synkroniseres vaulten med Obsidian Sync via Obsidian Headless.

## Kom i gang

Læs [docs/INSTALL.md](docs/INSTALL.md). Den er en komplet guide fra API nøgle til sikkerhedskopi.

## Status

* Kernen (sidegenkendelse, noter, daglige opsummeringer, bevarelse af dine egne rettelser) er dækket af automatiske tests.
* Docker billedet og Obsidian Headless er ikke testet på rigtigt udstyr endnu. Første installation på din Home Assistant Green er den egentlige prøve.

## Struktur

```
boox_obsidian/   add on (Dockerfile, config.yaml, app/)
docs/            installationsguide
scripts/         hjælpescript til lokal installation
tests/           pytest
```

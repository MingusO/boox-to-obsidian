"""Faelles prompts og skema for alle AI udbydere."""
from typing import List

LANGUAGES = {"da": "dansk", "en": "engelsk"}

RECORD_TOOL = {
    "name": "record_page",
    "description": "Gem resultatet af laesningen af en side med haandskrevne noter.",
    "input_schema": {
        "type": "object",
        "properties": {
            "is_blank": {"type": "boolean", "description": "Sand hvis siden ingen skrift har."},
            "date": {
                "type": "string",
                "description": "Datoen der staar skrevet paa siden som YYYY-MM-DD. Tom streng hvis ingen dato er skrevet.",
            },
            "title": {"type": "string", "description": "Kort titel paa siden, hoejst otte ord. Tom streng hvis tvivl."},
            "raw_text": {"type": "string", "description": "Noejagtig transskription af skriften, ogsaa med fejl."},
            "corrected_text": {
                "type": "string",
                "description": "Samme indhold som raw_text med stavefejl og tydelige slipfejl rettet, formateret som markdown.",
            },
            "uncertain_words": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ord eller steder du er usikker paa at have laest rigtigt.",
            },
            "tasks": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Udtrykkelige opgaver, aftaler og deadlines der staar paa siden.",
            },
        },
        "required": ["is_blank", "date", "title", "raw_text", "corrected_text", "uncertain_words", "tasks"],
    },
}


def transcribe_instruction(notebook: str, hint: str, today: str, as_tool: bool = True) -> str:
    how = "kald record_page" if as_tool else "svar kun med et JSON objekt efter det givne skema"
    text = (
        f"Dette er en side fra min haandskrevne notesbog '{notebook}'. "
        f"Dagens dato er {today}. "
        f"Laes al haandskrift paa siden og {how}. "
        "Regler: Bevar sproget i hver passage, oversaet aldrig. "
        "raw_text er en tro transskription. corrected_text er det samme indhold med stavefejl rettet "
        "og pænt struktureret som markdown (overskrifter, punktlister, tabeller hvis det er skrevet som tabel, "
        "formler som LaTeX mellem dollartegn). Tilfoej aldrig indhold der ikke staar paa siden. "
        "Skriv [?] hvor et ord er ulaeseligt, og list usikre ord i uncertain_words. "
        "Hvis siden viser en dato, returner den som YYYY-MM-DD, ellers en tom streng."
    )
    if hint:
        text += f" Baggrund for notesbogen: {hint}"
    return text


def summary_prompt(notebook: str, date: str, pages: List[dict], hint: str, language: str) -> str:
    joined = "\n\n".join(
        f"[Side {p['idx'] + 1}{': ' + p['title'] if p['title'] else ''}]\n{p['text']}" for p in pages
    )
    text = (
        f"Her er mine noter fra notesbogen '{notebook}' den {date}. "
        f"Skriv en kort log paa {language} som jeg hurtigt kan skimme senere. "
        "Format: foerst to til fem saetninger om hvad der skete og blev gennemgaaet. "
        "Derefter, hvis relevant, en liste med overskriften 'Nøglepunkter' og en liste med overskriften "
        "'Opgaver og aftaler'. Brug stjerne som punkttegn. Opfind intet, og brug ikke overskrifter foroven. "
        "Svar kun med selve teksten."
    )
    if hint:
        text += f" Baggrund: {hint}"
    return f"{text}\n\nNoter:\n{joined}"

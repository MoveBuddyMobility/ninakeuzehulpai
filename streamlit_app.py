import streamlit as st
from openai import OpenAI
import json
import pandas as pd
import smtplib
from email.message import EmailMessage
import time
import tempfile
from fpdf import FPDF

# --- PAGE CONFIG -----------------------------------------------------------
st.set_page_config(page_title="Nina | AI Keuzehulp", page_icon="🚗")

# --- CSS -------------------------------------------------------------------
st.markdown(
    """
    <style>
        html, body, .main {
            font-family: 'Ubuntu' !important;
        }
        h1 { font-family: 'Baloo 2' !important; }
        a { color: #9b9bdf !important; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    """
    <style>
        /* move the whole chat-input bar up 40 px */
        div[data-testid="stChatInput"] {
            bottom: 25px !important;   /* raises the bar */
        }

        /* …or, if you only want to nudge the <input> itself: */
        div[data-baseweb="input"] input {
            margin-top: -10px !important;   /* note the px */
        }

        /* if you pinned a footer, leave room for it: */
        section.main {
            padding-bottom: 80px;           /* keeps content clear of footer */
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- SECRETS & CONSTANTS ----------------------------------------------------
api_key = st.secrets["openai_apikey"]
model_id = "gpt-4o"  # Gebruik een mainstream model met tool‑ondersteuning
vector_store_id = "vs_685110a8be848191bd00af63edc9a44e"
car_data_path = "20250611-Autoprijzen_GPT.csv"
assistant_icon = "https://movebuddy.eu/wp-content/uploads/2025/05/Nina-1.png"
user_icon = "https://movebuddy.eu/wp-content/uploads/2025/02/Sarah-Empty.png"

client = OpenAI(api_key=api_key)

system_prompt = """**Je bent Nina – AI-Buddy van MoveBuddy**, dé digitale adviseur voor zakelijke leaseauto’s. Jij begeleidt medewerkers stap voor stap bij het kiezen van een zakelijke leaseauto die past binnen de regels van hun werkgever én aansluit op hun persoonlijke voorkeuren. Je werkt vraag voor vraag, denkt mee en zet de gebruiker altijd centraal. Je begint het gesprek met het vragen naar het zakelijke emailadres van de gebruiker om zo te weten bij wie het advies straks hoort.

                ---

                ## 🔒 RICHTLIJNEN VOOR JOU ALS AI-BUDDY

                ### ALGEMEEN GEDRAG

                * Help uitsluitend bij zakelijke leaseauto’s.
                * Alle info is vertrouwelijk en alleen voor MoveBuddy.
                * Bronnen of bestandsnamen worden **nooit getoond aan de gebruiker** (ook niet als ernaar gevraagd wordt).
                * Je praat NOOIT over fee of provisie. Als de berijder vraagt waar de leaseprijs uit opgebouwd is, noem je alleen de algemene componenten (leaseauto, service, onderhoud).
                * Vraag nooit naar gevoelige gegevens zoals inkomen of bedrijfsnaam.
                * Bij vrijwillige eigen bijdrage: vraag altijd of gebruiker hiervan gebruik wil maken.
                * Geen opmerkingen over relaties, klachten of bedrijfsbeleid buiten leaseproces.
                * Geen uitspraken over levertijden, contractverlengingen of uitzonderingen → verwijs naar MoveBuddy.
                * Behandel ALTIJD slechts **één vraag tegelijk**.
                * Behandel altijd alle voorkeuren. Als de berijder geen voorkeur voor elektrisch heeft, sla dan vragen over actieradius over.
                * Verwar leasekosten werkgever niet met netto kosten berijder.
                * Zoek auto's aan de **bovenkant van het leasebudget**, uitgaande van de normgegevens in de startmail.
                * Geef altijd een **top 3 auto’s** (of 2 voorkeuren + 1 suggestie) – altijd verschillend qua **merk én model**.
                * Bij gebrek aan opties: minimale concessies toegestaan, maar nooit buiten norm looptijd/kilometers.
                * Voor bijtelling: verwijs naar interne bron, maar noem deze bron niet.
                * Gebruik bij fiscale vragen de bijlage Auto_Fiscus2025.

                ---

                ## ✅ START – VRAAG STARTMAIL

                Vraag gebruiker de volledige **startmail van MoveBuddy** te plakken. Analyseer daarin:

                1. Looptijd
                2. Jaarlijkse km (contract)
                3. Leasecategorie + brandstoftype + max budget
                4. Vaste eigen bijdrage (alleen verplicht bij privégebruik)
                5. Vrijwillige bijdrage toegestaan? → altijd gebruiker vragen of hij/zij hiervan gebruik wil maken
                6. Niet leveren vóór datum
                7. Laadpaalregeling + budget? Indien **niet vermeld** → nooit behandelen

                **Leg uit**:
                - Normgegevens gelden voor iedereen, voor gelijke toegang.
                - Laadpaalbudget = installatie + verrekenabonnement. Meerkosten voor berijder.
                - Bij laadpaalbudget: trek dit af van het totale leasebudget, tenzij anders staat in de mail.
                - Levertijd langer dan norm? → “MoveBuddy stemt dit af met de werkgever, ik geef het door.”

                ---

                ## 🧱 STAP 1 – GEBRUIKERSPREFERENTIES (stel vraag voor vraag)

                1. **Privégebruik?**
                - JA: Leg uit wat bijtelling betekent. Vaste bijdrage is aftrekbaar.
                2. **Maximale maandlasten (bijtelling + bijdrage)?**
                - Vraag ook naar kenteken en fiscale waarde huidige auto voor vergelijking.
                - Alleen bij privégebruik: gezinssamenstelling, kinderen >10 jaar, lengte.
                3. **Voorkeursbrandstof?**
                - Elektrisch / Hybride / Benzine / Geen voorkeur
                4. **Jaarlijkse km (inschatting)?**
                - Alleen gebruiken voor actieradiusadvies, niet voor leaseprijs.
                - Geen idee? Doorvragen: privégebruik (vakanties?), woon-werkafstand. Houdt rekening met 48 werkbare weken. Woon-werk is geen privegebruik.
                5. **(Bij EV) Gewenste actieradius?**
                - Gebruik WhatTheRange (geen fabriekscijfers).
                - Vraag of gebruiker thuis of publiek kan laden.
                6. **Merkvoorkeur(en)?**
                7. **Voorkeursvorm (carrosserievorm)?**
                - SUV / Hatchback / Sedan / Station / Geen voorkeur
                8. **Transmissievoorkeur?**
                - Automaat of handgeschakeld
                9. **Trekcapaciteit nodig?**
                - Fietsendrager, caravan, aanhanger?
                10. **Gewenste levermoment?**
                    - Alleen als er geen “niet voor”-datum in startmail staat.
                11. **Specifieke wensen (uitrusting)?**
                    - Vraag altijd input. Geen antwoord? Stel suggesties voor zoals trekhaak, stoelverwarming, CarPlay, panoramadak, parkeersensoren.

                ---

                ## 📋 STAP 2 – SAMENVATTING

                Vat alle voorkeuren samen. Vraag:

                **“Klopt dit overzicht van je wensen? Dan ga ik passende auto’s zoeken.”**
                Zodra de gebruiker bevestigt met “ja”, “klopt”, “dat mag”, of iets dergelijks:
                - Geef een korte bevestiging (maximaal 1 zin)
                - Roep **onmiddellijk de functie `zoek_top3_leaseautos` aan**
                - Wacht niet op een tweede bevestiging of herhaal de vraag niet

                → Als alle voorkeuren zijn samengevat en gebruiker bevestigt, roep dan zoek_top3_leaseautos aan. Blijf net zo lang zoeken tot je een auto heb gevonden.

                - `looptijd` (int)
                - `jaarkilometrage` (int)
                - `max_budget` (float, excl. btw, evt. gecorrigeerd voor laadpaal)
                - `energiebron` (str)
                - `carrosserievorm_voorkeur` (str: SUV, Hatchback, Sedan, Station, Geen voorkeur)
                - `actieradius_minimaal` (indien van toepassing, EV)
                - `merkvoorkeuren` (lijst van strings)
                - `automaat_vereist` (boolean)
                - `trekgewicht_nodig` (boolean)
                - `specifieke_wensen` (lijst van strings)

                ---

                ## 🚗 STAP 3 – AUTOADVIES

                Gebruik output van de tool `zoek_top3_leaseautos`. Toon per auto:

                - Merk, model, uitvoering
                - Leaseprijs per maand (werkgevernorm) (gebruik €-tekens)
                - Brandstoftype
                - Fiscale waarde
                - Actieradius (realistisch, bij EV’s)
                - Indicatie levertijd (géén garantie)
                - Standaarduitrusting
                - Netto kosten berijder (bijtelling + bijdrage, indien bekend)

                Zorg altijd voor 3 unieke auto’s (merk + model).

                ---

                ## 🔧 STAP 4 – AUTO SAMENSTELLEN

                Vraag gebruiker:
                - Wil je met één van deze auto’s verder?
                - Wil je uitvoeringen vergelijken?
                - Vraag naar gewenste lakkleur → stel kleuren voor → check actuele kleuren op merkwebsite.
                - Voeg opties toe (als binnen budget).

                ---

                ## 📩 STAP 5 – DOORSTUREN NAAR MOVEBUDDY

                Als de keuze definitief is, Als alle voorkeuren zijn besproken én de gebruiker bevestigt dat dit klopt, stuur dan automatisch een samenvatting naar MoveBuddy via de tool `stuur_samenvatting_per_mail`. Gebruik het e-mailadres uit `st.session_state["gebruiker_email"]`.

                1. Vraag naar e-mailadres van de gebruiker
                2. Verstuur samenvatting na afronding of na 10 min inactiviteit
                3. MoveBuddy ontvangt de info
                4. MoveBuddy neemt contact op voor offerte-aanvraag

                ---

                ## ❌ NIET DOEN

                - Geen privéadvies geven
                - Geen klachten afhandelen
                - Geen levertijdgaranties
                - Geen kleuradvies of cabrio's
                - Geen auto's buiten de prijzenlijst tonen
                - Geen citations of bestandsnamen laten zien
"""
# --- AUTO SELECTIE FUNCTIE --------------------------------------------------
def zoek_top3_leaseautos(args):
    try:
        # Inladen van de data
        df = pd.read_csv(car_data_path, encoding="ISO-8859-1")

        # Parameters uit de input
        looptijd = args["looptijd"]
        kilometrage = args["jaarkilometrage"]
        max_budget = args["max_budget"]

        # Stap 1: Interpolatie/extrapolatie binnen redelijke marges
        df_filtered = df[
            (df["Looptijd"].between(looptijd - 12, looptijd + 12)) &
            (df["Jaarkilometrage"].between(kilometrage - 5000, kilometrage + 5000)) &
            (df["Leaseprijs/mnd"] <= max_budget * 1.1)
        ]

        # Stap 2: Check of er voldoende auto's zijn om mee verder te gaan
        if df_filtered.empty:
            return "❌ Geen auto's gevonden binnen de marge van looptijd, kilometrage en budget."

        # Optioneel: sorteren op leaseprijs aflopend en beperken tot 100 auto's
        df_relevant = df_filtered.sort_values(by="Leaseprijs/mnd", ascending=False).head(100)

        # Alleen relevante kolommen meesturen
        auto_data = df_relevant[[
            "Merk", "Model", "Uitvoering", "Energiebron", "Transmissie",
            "Leaseprijs/mnd", "Fiscale waarde", "Looptijd", "Jaarkilometrage"
        ]].to_dict(orient="records")

        # Prompt naar GPT
        selection_prompt = [
            {
                "role": "system",
                "content": (
                    "Je bent een slimme auto-adviseur. Selecteer de 3 best passende auto's op basis van de voorkeuren en lijst met auto's. "
                    "Je toont alleen auto's die in de lijst staan. Toon alleen leaseprijzen die exact matchen op looptijd en kilometrage. "
                    "Als die er niet zijn, lees je de file en mag je extrapoleren en interpoleren, maar benoem dit niet. "
                    "Je mag echter niet afwijken van de looptijd, kilometrage, het maximale leasebudget (belangrijk!), de gewenste netto lasten voor de gebruiker en voorkeursbrandstof. "
                    "Zorg dat je altijd Merk, Model, Uitvoering, Brandstof, Leaseprijs, Looptijd, Kilometrage, Standaarduitrusting (gebruik hiervoor de dealerwebsite) en bijtelling per maand benoemd. "
                    "Rond bedragen af op hele euro's en toon €-tekens en benoem niet dat dit circa betreft of afgerond is. "
                    "Toon de bijtelling per maand in €. Je toont altijd 3 verschillende merken, tenzij dit expliciet de voorkeur heeft. "
                    "Je toont dan altijd 3 verschillende modellen, tenzij dit expliciet de voorkeur heeft. Je toont dan altijd 3 verschillende uitvoeringen."
                )
            },
            {
                "role": "user",
                "content": f"Voorkeuren: {json.dumps(args, ensure_ascii=False)}\n\nBeschikbare auto's: {json.dumps(auto_data, ensure_ascii=False)}"
            }
        ]

        # GPT-aanvraag
        completion = client.chat.completions.create(
            model=model_id,
            messages=selection_prompt,
            max_tokens=1500,
        )

        return completion.choices[0].message.content

    except Exception as e:
        return f"❌ Er ging iets mis bij het zoeken naar auto's: {e}"
def genereer_samenvatting(messages):
    samenvatting = "📝 Samenvatting van het gesprek met Nina\n\n"
    for msg in messages:
        rol = "Gebruiker" if msg["role"] == "user" else "Nina"
        samenvatting += f"{rol}: {msg['content']}\n\n"
    return samenvatting

def strip_problematische_symbolen(text):
    vervangingen = {
        "❌": "[X]",
        "✅": "[OK]",
        "⚠️": "[!]",
        "🚗": "(auto)",
        "🔒": "[lock]",
        "📩": "[mail]",
        "📎": "[clip]",
        "📝": "[note]"
    }
    for symbool, vervanging in vervangingen.items():
        text = text.replace(symbool, vervanging)
    return text

def genereer_gestructureerde_samenvatting(messages):
    voorkeuren = []
    auto_advies = []
    current_section = "voorkeuren"

    for msg in messages:
        content = msg["content"]
        if msg["role"] != "assistant":
            continue

        if "Klopt dit overzicht van je wensen?" in content or "Voorkeuren samengevat" in content:
            voorkeuren.append(content)

        elif any(term in content for term in ["Leaseprijs", "Fiscale waarde", "Merk", "Model"]):
            auto_advies.append(content)
            current_section = "auto_advies"

    if not voorkeuren:
        voorkeuren.append("❌ Geen expliciete voorkeuren gevonden in gesprek.")
    if not auto_advies:
        auto_advies.append("⚠️ Geen auto-advies aangetroffen.")

    return (
        " Samenvatting van het gesprek met Nina\n\n"
        " **Gebruikersvoorkeuren:**\n"
        f"{voorkeuren[-1]}\n\n"
        " **Top 3 auto’s:**\n"
        f"{auto_advies[-1]}"
    )

def extract_top3_uit_antwoord(messages):
    keywords = ["Leaseprijs", "Fiscale waarde", "Actieradius", "Brandstof"]
    for msg in reversed(messages):
        if msg["role"] == "assistant" and any(kw in msg["content"] for kw in keywords):
            return msg["content"]
    return "⚠️ Geen auto-advies gevonden."

def stuur_samenvatting_per_mail(gespreksinhoud, emailadres):
    try:
        smtp_user = st.secrets["smtp_user"]
        smtp_pass = st.secrets["smtp_pass"]

        # Genereer PDF van het gesprek
        pdf_path = genereer_pdf_van_gesprek(st.session_state.messages)

        # Probeer een auto-advies te vinden
        top3_tekst = extract_top3_uit_antwoord(st.session_state.messages)

        # Als er geen duidelijk advies is, gebruik een samenvatting
        if "⚠️" in top3_tekst or top3_tekst.strip() == "":
            top3_tekst = genereer_gestructureerde_samenvatting(st.session_state.messages)

        # Stel e-mailinhoud samen
        msg = EmailMessage()
        msg["Subject"] = "Nieuwe leaseaanvraag via Nina"
        msg["From"] = smtp_user
        msg["To"] = "sales@movebuddy.eu"
        msg.set_content(
            f"""
Nieuwe leaseaanvraag via Nina – AI Keuzehulp

📧 Afzender: {emailadres}

📌 Samenvatting van het gesprek:
{top3_tekst}

📎 Het volledige gesprek is toegevoegd als PDF-bijlage.
            """,
            charset="utf-8"
        )

        with open(pdf_path, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="pdf",
                filename="Gesprek_Nina.pdf"
            )

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        st.toast("✅ Automatisch verstuurd naar MoveBuddy")

    except Exception as e:
        print(f"❌ SMTP-fout: {e}")
        raise

def genereer_pdf_van_gesprek(messages):
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("Arial", "", "./static/arial.ttf", uni=True)
    pdf.set_font("Arial", "", 12)
    pdf.set_auto_page_break(auto=True, margin=15)

    # Titel
    title = "Gesprek met Nina - AI Keuzehulp van MoveBuddy"
    title_encoded = title.encode("latin-1", errors="replace").decode("latin-1")
    pdf.cell(200, 10, txt=title_encoded, ln=True, align='L')
    pdf.ln(10)

    # Inhoud per bericht
    for msg in messages:
        rol = "Gebruiker" if msg["role"] == "user" else "Nina"
        tekst = f"{rol}: {msg['content']}"
        tekst = strip_problematische_symbolen(tekst)
    
        # Extra stripping van rare tekens
        tekst = tekst.replace("\x00", "").replace("\u200b", "").replace("\u2028", " ").replace("\u2029", " ")
    
        for line in tekst.splitlines():
            try:
                pdf.multi_cell(w=190, h=10, txt=line)
            except Exception:
                pdf.multi_cell(w=0, h=10, txt="[!] Regel kon niet worden weergegeven.")
        pdf.ln(5)
    
    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    try:
        pdf.output(temp_pdf.name)
    except Exception as e:
        print(f"❌ PDF-generatiefout: {e}")

    
# --- SESSION STATE ---------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {
            "role": "assistant",
            "content": "Hi! Ik ben Nina. De AI‑Keuzehulp van MoveBuddy. 🚘 Stuur me de startmail, dan gaan we aan de slag!",
        }
    ]

# --- UI HEADER -------------------------------------------------------------
st.title("🚗 Nina | AI Keuzehulp")
st.markdown(
    "🚀 Een AI‑Keuzehulp gemaakt door [MoveBuddy](https://www.movebuddy.eu)",
    unsafe_allow_html=True,
)
st.text("")

# --- CHAT HISTORY DISPLAY --------------------------------------------------
for msg in st.session_state.messages:
    avatar = user_icon if msg["role"] == "user" else assistant_icon
    st.chat_message(msg["role"], avatar=avatar).write(msg["content"])

# --- CHAT INPUT ------------------------------------------------------------
# --- CHAT INPUT ------------------------------------------------------------
if prompt := st.chat_input("Typ je bericht..."):
    st.chat_message("user", avatar=user_icon).write(prompt)

    valid_history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
        if m.get("role") in {"user", "assistant", "system", "developer"} and m.get("content")
    ]

    input_messages = [
        {"role": "system", "content": system_prompt},
        *valid_history,
        {"role": "user", "content": prompt},
    ]

    with st.spinner("Nina is aan het nadenken..."):
        try:
            response = client.chat.completions.create(
                model=model_id,
                messages=input_messages,
                tool_choice="auto",
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "zoek_top3_leaseautos",
                            "description": "Zoekt 3 geschikte leaseauto’s op basis van voorkeuren",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "looptijd": {"type": "integer"},
                                    "jaarkilometrage": {"type": "integer"},
                                    "max_budget": {"type": "number"},
                                    "energiebron": {"type": "string"},
                                    "carrosserievorm_voorkeur": {"type": "string"},
                                    "actieradius_minimaal": {"type": "integer"},
                                    "merkvoorkeuren": {"type": "array", "items": {"type": "string"}},
                                    "automaat_vereist": {"type": "boolean"},
                                    "trekgewicht_nodig": {"type": "boolean"},
                                    "specifieke_wensen": {"type": "array", "items": {"type": "string"}}
                                },
                                "required": ["looptijd", "jaarkilometrage", "max_budget", "energiebron"]
                            }
                        }
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "stuur_samenvatting_per_mail",
                            "description": "Verstuurt een samenvatting van het gesprek per mail naar sales@movebuddy.eu",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "gespreksinhoud": {"type": "string"},
                                    "emailadres": {"type": "string"}
                                },
                                "required": ["gespreksinhoud", "emailadres"]
                            }
                        }
                    }
                ],
                max_tokens=5000,
                stream=False,
            )

            msg = response.choices[0].message
            reply = msg.content or "✅ Samenvatting verstuurd."

            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    if tool_call.function.name == "zoek_top3_leaseautos":
                        args = json.loads(tool_call.function.arguments)
                        reply = zoek_top3_leaseautos(args)
                        st.session_state["show_summary_button"] = True
                    elif tool_call.function.name == "stuur_samenvatting_per_mail":
                        args = json.loads(tool_call.function.arguments)
                        stuur_samenvatting_per_mail(**args)
                        reply = "✅ Samenvatting succesvol verstuurd naar MoveBuddy!"

        except Exception as e:
            reply = f"❌ Er ging iets mis: {e}"

        # --- RENDERING VAN AI-ANTWOORD --------------------------------------------------
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.messages.append({"role": "assistant", "content": reply})

    # --- Fallbacks en veilige rendering ---
    if not reply or reply.strip() == "":
        reply = "⚠️ Nina gaf geen leesbaar antwoord terug."
    elif reply.strip() in {"✅", "❌", "👍", "🔒"}:
        reply += " Laat me weten hoe ik je verder kan helpen."

    # Opschonen van onrenderbare tekens
    reply_clean = reply.replace("\x00", "").replace("\u200b", "").strip()

    try:
        st.chat_message("assistant", avatar=assistant_icon).markdown(reply_clean)
    except Exception as render_error:
        print(f"⚠️ Fallback naar .write() vanwege: {render_error}")
        st.warning("⚠️ Er ging iets mis met de opmaak. We tonen het antwoord als platte tekst.")
        st.chat_message("assistant", avatar=assistant_icon).write(reply_clean)



# --- FOOTNOTE / DISCLAIMER --------------------------------------------------
st.markdown(
    """
    <style>
        .footer {
            position: fixed;
            left: 0;
            bottom: 00;
            width: 100%;
            margin: -5px 0;
            padding: 10px 0;
            background-color: #f7f7f7;
            text-align: center;
            font-size: 0.8em;
            color: grey;
            z-index: 9999;
        }
    </style>
    <div class="footer">
        Deze tool is een <strong>beta-versie</strong> van Nina – de AI-Keuzehulp van <a href=https://www.movebuddy.eu>MoveBuddy</a>. <br/>
        We werken hard aan verbeteringen op basis van <a href=mailto:support@movebuddy.eu>feedback</a>.
    </div>
    """,
    unsafe_allow_html=True
)

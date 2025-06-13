import streamlit as st
import time
from openai import OpenAI

# --- PAGE CONFIG ---
st.set_page_config(page_title="Nina | AI Keuzehulp", page_icon="🚗")

st.markdown("""
    <style>
        h1 {
            font-family: 'Baloo 2' !important;
        }
        body {
            font-family: 'Ubuntu' !important;
        }          
        a {
            color: #9b9bdf !important;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        
    </style>
""", unsafe_allow_html=True)

# --- SECRETS & AVATARS ---
openai_api_key = st.secrets["openai_apikey"]
assistant_id = st.secrets["assistant_id"]

assistant_icon_url = "https://movebuddy.eu/wp-content/uploads/2025/05/Nina-1.png"
user_icon_path = "https://movebuddy.eu/wp-content/uploads/2025/02/Sarah-Empty.png"

# --- INIT CLIENT & THREAD ---
@st.cache_resource
def init_openai_and_thread():
    client = OpenAI(api_key=openai_api_key)
    assistant = client.beta.assistants.retrieve(assistant_id)
    thread = client.beta.threads.create()
    return client, assistant, thread

client, assistant, thread = init_openai_and_thread()

# --- SESSION STATE ---
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {
            "role": "assistant",
            "content": "Hi! Ik ben Nina. De AI-Keuzehulp van MoveBuddy. Samen gaan we op zoek naar een nieuwe leaseauto! 🚘 Kun je mij de startmail sturen die we je hebben gemaild? Dan gaan we van start!"
        }
    ]

# --- UI HEADER ---
st.title("🚗 Nina | AI Keuzehulp")
st.markdown("🚀 Een AI-Keuzehulp gemaakt door [MoveBuddy](https://www.movebuddy.eu)", unsafe_allow_html=True)
st.text("")

# --- DISPLAY CHAT HISTORY ---
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.chat_message("user", avatar=user_icon_path).write(msg["content"])
    else:
        st.chat_message("assistant", avatar=assistant_icon_url).write(msg["content"])

# --- HANDLE USER INPUT ---
if prompt := st.chat_input("Typ je bericht..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user", avatar=user_icon_path).write(prompt)

    # 1. Create user message in thread
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=prompt,
    )

    # 2. Run assistant
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant_id,
    )

    with st.spinner("Nina is aan het nadenken..."):
        while run.status in ["queued", "in_progress"]:
            time.sleep(0.5)
            run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

    # 3. Retrieve response
    messages = client.beta.threads.messages.list(thread_id=thread.id, order="desc")
    assistant_reply = None
    for msg in messages.data:
        if msg.role == "assistant":
            assistant_reply = msg.content[0].text.value
            break

    if assistant_reply:
        st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
        st.chat_message("assistant", avatar=assistant_icon_url).write(assistant_reply)
    else:
        error_msg = "Er ging iets mis met het ophalen van het antwoord."
        st.session_state.messages.append({"role": "assistant", "content": error_msg})
        st.chat_message("assistant", avatar=assistant_icon_url).write(error_msg)
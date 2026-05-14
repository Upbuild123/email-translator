#!/usr/bin/env python3
"""
Japanese Announcements Translator
- Opens camera immediately on mobile
- Reads Japanese text from photo using GPT-4o vision
- Emails English translation + hiragana/katakana + romaji
"""
from __future__ import annotations

import os
import base64
import smtplib
import textwrap
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

_rear_camera = components.declare_component("rear_camera", path="camera_component")

# ── Env ────────────────────────────────────────────────────────────────────────
def _load_env() -> None:
    env = Path(__file__).parent / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip(); v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v

_load_env()

OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")
GMAIL_ADDRESS   = os.getenv("GMAIL_ADDRESS", "michael.sloyer@gmail.com")
GMAIL_APP_PASS  = os.getenv("GMAIL_APP_PASS", "")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Japanese Translator",
    page_icon="📸",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
header[data-testid="stHeader"] { display: none; }
.block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 680px; }
.stApp { background-color: #ffffff; }
h1 { font-size: 1.5rem !important; font-weight: 700 !important; color: #111 !important; }
p, li, label { color: #333 !important; }
.stButton > button {
    background: #111 !important; color: #fff !important;
    border: none !important; border-radius: 8px !important;
    font-weight: 600 !important; padding: 0.6rem 1.4rem !important;
    font-size: 1rem !important; width: 100%;
}
.stButton > button p { color: #fff !important; }
.stButton > button:hover { opacity: 0.82; }
.stButton > button:disabled { opacity: 0.3; }
.status-box {
    background: #f0fdf4; border: 1px solid #bbf7d0;
    border-radius: 8px; padding: 1rem 1.2rem; margin-top: 1rem;
}
.error-box {
    background: #fef2f2; border: 1px solid #fecaca;
    border-radius: 8px; padding: 1rem 1.2rem; margin-top: 1rem;
}
</style>
""", unsafe_allow_html=True)

# ── GPT-4o vision call ─────────────────────────────────────────────────────────
def translate_image(image_bytes: bytes) -> dict:
    b64 = base64.b64encode(image_bytes).decode()
    prompt = textwrap.dedent("""
        You are a Japanese language expert helping an English-speaking parent understand a Japanese school announcement board.

        The image contains Japanese text. Please respond in this exact format:

        ENGLISH
        <A complete, natural English version of the entire announcement. Write it as a native English speaker would — fluid, clear, and easy to read. Do not translate word-for-word. Capture the full meaning, tone, and intent as one cohesive piece of writing.>

        JAPANESE
        <All the original Japanese text exactly as written in the image>

        READING
        <The full hiragana/katakana reading of the Japanese text>

        ROMAJI
        <The full romaji (Hepburn romanization) of the Japanese text>

        If no Japanese text is found, say: NO_JAPANESE_FOUND
    """).strip()

    resp = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }],
    )
    text = resp.choices[0].message.content.strip()
    return {"raw": text}

# ── Email sending ──────────────────────────────────────────────────────────────
def send_email(translation_text: str) -> None:
    msg = MIMEMultipart("alternative")
    from datetime import date
    today = date.today()
    msg["Subject"] = today.strftime("%a %-d %b School Announcements")
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = GMAIL_ADDRESS

    # Plain text version
    plain = f"School Announcement Translation\n\n{translation_text}"

    # HTML version — nicely formatted
    def _extract_section(text: str, heading: str) -> str:
        lines = text.splitlines()
        result, capture = [], False
        for line in lines:
            if line.strip() == heading:
                capture = True
                continue
            if capture and line.strip() in ("ENGLISH", "JAPANESE", "READING", "ROMAJI"):
                break
            if capture:
                result.append(line)
        return "\n".join(result).strip()

    english = _extract_section(translation_text, "ENGLISH")
    japanese = _extract_section(translation_text, "JAPANESE")
    reading = _extract_section(translation_text, "READING")
    romaji = _extract_section(translation_text, "ROMAJI")

    html = f"""
    <html><body style="font-family:sans-serif;max-width:600px;margin:auto;padding:1rem">
        <h2 style="color:#111">📋 School Announcement Translation</h2>
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:1.2rem 1.4rem;margin-bottom:1.5rem">
            <p style="color:#111;font-size:1.05rem;line-height:1.6;margin:0">{english}</p>
        </div>
        <hr style="border:none;border-top:1px solid #e5e7eb;margin:1.5rem 0">
        <p style="color:#555;font-size:0.9rem;margin:0 0 0.3rem 0"><b>Japanese</b></p>
        <p style="color:#333;margin:0 0 1rem 0">{japanese}</p>
        <p style="color:#555;font-size:0.9rem;margin:0 0 0.3rem 0"><b>Reading</b></p>
        <p style="color:#333;margin:0 0 1rem 0">{reading}</p>
        <p style="color:#555;font-size:0.9rem;margin:0 0 0.3rem 0"><b>Romaji</b></p>
        <p style="color:#333;margin:0">{romaji}</p>
    </body></html>
    """

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASS)
        server.sendmail(GMAIL_ADDRESS, GMAIL_ADDRESS, msg.as_string())

# ── UI ─────────────────────────────────────────────────────────────────────────
st.title("📸 Japanese Translator")
st.caption("Take a photo of the announcement board — a translation will be emailed to you instantly.")

if not OPENAI_API_KEY:
    st.error("OPENAI_API_KEY not set.")
elif not GMAIL_APP_PASS:
    st.error("GMAIL_APP_PASS not set.")
else:
    photo_data = _rear_camera()

    if photo_data is not None:
        header, encoded = photo_data.split(",", 1)
        image_bytes = base64.b64decode(encoded)
        with st.spinner("Reading Japanese and translating..."):
            try:
                result = translate_image(image_bytes)
                translation = result["raw"]

                if "NO_JAPANESE_FOUND" in translation:
                    st.markdown('<div class="error-box">⚠️ No Japanese text found in the photo. Try again with a clearer shot.</div>', unsafe_allow_html=True)
                else:
                    send_email(translation)
                    st.markdown('<div class="status-box">✅ Translation sent to <b>michael.sloyer@gmail.com</b></div>', unsafe_allow_html=True)
                    st.divider()
                    def _extract(text, heading):
                        lines = text.splitlines()
                        result, capture = [], False
                        for line in lines:
                            if line.strip() == heading:
                                capture = True
                                continue
                            if capture and line.strip() in ("ENGLISH", "JAPANESE", "READING", "ROMAJI"):
                                break
                            if capture:
                                result.append(line)
                        return "\n".join(result).strip()

                    st.markdown(_extract(translation, "ENGLISH"))
                    st.divider()
                    st.caption("**Japanese**")
                    st.markdown(_extract(translation, "JAPANESE"))
                    st.caption("**Reading**")
                    st.markdown(_extract(translation, "READING"))
                    st.caption("**Romaji**")
                    st.markdown(_extract(translation, "ROMAJI"))

            except Exception as e:
                st.markdown(f'<div class="error-box">❌ Error: {e}</div>', unsafe_allow_html=True)

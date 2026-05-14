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
from openai import OpenAI

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
        You are a Japanese language expert. The image contains Japanese text (e.g. from a school announcement board).

        Please:
        1. Extract ALL Japanese text visible in the image.
        2. For each distinct section or sentence, provide:
           - The original Japanese (kanji/kana as written)
           - Hiragana/katakana reading
           - Romaji (Hepburn romanization)
           - English translation

        Format your response EXACTLY like this for each item:

        ---
        Original: <japanese text>
        Reading: <hiragana/katakana>
        Romaji: <romaji>
        English: <english translation>
        ---

        If there are multiple sections or announcements, repeat the block for each one.
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
    msg["Subject"] = "📋 School Announcement Translation"
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = GMAIL_ADDRESS

    # Plain text version
    plain = f"School Announcement Translation\n\n{translation_text}"

    # HTML version — nicely formatted
    blocks = [b.strip() for b in translation_text.split("---") if b.strip()]
    html_blocks = ""
    for block in blocks:
        lines = {
            k.strip(): v.strip()
            for line in block.splitlines()
            if ":" in line
            for k, v in [line.split(":", 1)]
        }
        if not lines:
            continue
        html_blocks += f"""
        <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;
                    padding:1rem 1.2rem;margin-bottom:1rem;font-family:sans-serif;">
            <p style="font-size:1.2rem;margin:0 0 0.5rem 0">{lines.get('Original','')}</p>
            <p style="color:#555;margin:0.2rem 0"><b>Reading:</b> {lines.get('Reading','')}</p>
            <p style="color:#555;margin:0.2rem 0"><b>Romaji:</b> {lines.get('Romaji','')}</p>
            <p style="color:#1d4ed8;margin:0.4rem 0 0 0;font-weight:600">
                {lines.get('English','')}
            </p>
        </div>
        """

    html = f"""
    <html><body style="font-family:sans-serif;max-width:600px;margin:auto;padding:1rem">
        <h2 style="color:#111">📋 School Announcement Translation</h2>
        {html_blocks if html_blocks else f"<pre>{translation_text}</pre>"}
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
    photo = st.camera_input("")

    if photo is not None:
        with st.spinner("Reading Japanese and translating..."):
            try:
                result = translate_image(photo.getvalue())
                translation = result["raw"]

                if "NO_JAPANESE_FOUND" in translation:
                    st.markdown('<div class="error-box">⚠️ No Japanese text found in the photo. Try again with a clearer shot.</div>', unsafe_allow_html=True)
                else:
                    send_email(translation)
                    st.markdown('<div class="status-box">✅ Translation sent to <b>michael.sloyer@gmail.com</b></div>', unsafe_allow_html=True)
                    st.divider()
                    st.markdown("**Preview:**")
                    blocks = [b.strip() for b in translation.split("---") if b.strip()]
                    for block in blocks:
                        st.markdown(block)
                        st.divider()

            except Exception as e:
                st.markdown(f'<div class="error-box">❌ Error: {e}</div>', unsafe_allow_html=True)

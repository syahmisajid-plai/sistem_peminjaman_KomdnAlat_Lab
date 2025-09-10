import streamlit as st
import pandas as pd
from supabase import create_client
import os
from dotenv import load_dotenv
from datetime import date, timedelta

# Load .env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.markdown(
    """
    <style>
    .stApp { background-color: #0A0F29; color: #FFD700; margin: 0 auto;}
    section[data-testid="stSidebar"] { background-color: #FFFFFF; color: #000000; }
    section[data-testid="stSidebar"] * { color: #000000 !important; }
    .computer-card { border-radius: 10px; padding: 15px; margin: 5px; text-align: center; font-weight: bold; }
    .available { background-color: #006400; color: #FFFFFF; }
    .not-available { background-color: #8B0000; color: #FFFFFF; }
    .computer-card p { color: #FFFFFF !important; }
    
    .stButton>button {
        color: #065F46;
        background-color: #A3E635;  /* Mengatur warna latar belakang tombol */
    }
    
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("💻 Monitoring & Pengajuan Peminjaman Komputer")
st.markdown("Pantau ketersediaan komputer dan ajukan peminjaman berdasarkan hari.")

# Ambil data komputer
computers = supabase.table("computers").select("*").execute()
schedules = supabase.table("computer_schedule").select("*").execute()

df_computers = pd.DataFrame(computers.data)
df_schedules = pd.DataFrame(schedules.data)

if df_computers.empty or df_schedules.empty:
    st.warning("⚠️ Belum ada data komputer atau jadwal ketersediaan.")
else:
    # Pastikan loan_date hanya tanggal (tanpa waktu)
    df_schedules["loan_date"] = pd.to_datetime(df_schedules["loan_date"]).dt.date

    # Merge jadwal dengan komputer
    df = df_schedules.merge(df_computers, left_on="computer_id", right_on="id")
    df = df[["id_y", "name", "location", "loan_date", "available"]].rename(
        columns={
            "id_y": "computer_id",
            "name": "Komputer",
            "location": "Lokasi",
            "loan_date": "Tanggal",
            "available": "Tersedia",
        }
    )

    today = date.today()
    max_date = today + timedelta(days=7)

    tanggal = st.date_input(
        "📅 :blue[Pilih tanggal:]", value=today, min_value=today, max_value=max_date
    )

    # Filter berdasarkan tanggal yang cocok
    df_tanggal = df[df["Tanggal"] == tanggal].sort_values(by="Komputer")

    total = len(df_tanggal)
    tersedia = df_tanggal["Tersedia"].sum()
    tidak_tersedia = total - tersedia

    col1, col2, col3 = st.columns(3)

    col1.markdown(
        f"""
    <div style='text-align:center;'>
        <span style='color: white; font-size: 14px;'>Total Komputer</span><br>
        <span style='color: white; font-size: 45px; font-weight: bold;'>{total}</span>
    </div>
    """,
        unsafe_allow_html=True,
    )

    col2.markdown(
        f"""
    <div style='text-align:center;'>
        <span style='color: white; font-size: 14px;'>Tersedia</span><br>
        <span style='color: green; font-size: 45px; font-weight: bold;'>{tersedia}</span>
    </div>
    """,
        unsafe_allow_html=True,
    )

    col3.markdown(
        f"""
    <div style='text-align:center;'>
        <span style='color: white; font-size: 14px;'>Tidak Tersedia</span><br>
        <span style='color: red; font-size: 45px; font-weight: bold;'>{tidak_tersedia}</span>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.subheader(f"📋 Daftar Komputer Tanggal {tanggal}")

    # Gunakan tanggal sebagai bagian key untuk session_state
    session_key = f"status_komputer_{tanggal.isoformat()}"
    if session_key not in st.session_state:
        st.session_state[session_key] = {
            row.computer_id: row.Tersedia for row in df_tanggal.itertuples()
        }

    # Global NIM input (di atas daftar komputer, bukan sidebar)
    nim_global = st.text_input(":blue[Masukkan NIM Anda (wajib diisi):]")
    user_id_global = None

    if nim_global:
        user_resp = supabase.table("users").select("id").eq("nim", nim_global).execute()
        if user_resp.data:
            user_id_global = user_resp.data[0]["id"]
        else:
            st.warning("⚠️ NIM tidak valid. Silakan cek kembali.")

    cols = st.columns(3)

    for idx, row in enumerate(df_tanggal.itertuples(), 1):
        available = st.session_state[session_key][row.computer_id]  # ambil status

        status_class = "available" if available else "not-available"
        status_text = "✅ Available" if available else "❌ Tidak Tersedia"

        with cols[(idx - 1) % 3]:
            st.markdown(
                f"""
                <div class="computer-card {status_class}">
                    <div style="font-size:40px;">🖥️</div>
                    <div>{row.Komputer}</div>
                    <div style="font-size:14px;">{status_text}</div>
                    <div style="font-size:12px;">{row.Lokasi}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if available:
                with st.expander(f"Ajukan Peminjaman"):
                    with st.form(key=f"form_{row.Komputer}"):
                        st.text_input(
                            "Nomor Komputer:", value=row.Komputer, disabled=True
                        )
                        submitted = st.form_submit_button("Kirim Pengajuan")

                        if submitted:
                            if not user_id_global:
                                st.error(
                                    "❌ Anda belum memasukkan NIM yang valid di atas."
                                )
                            else:
                                # Cek apakah user sudah mengajukan pada tanggal yang sama dan statusnya bukan 'rejected'
                                existing_loan = (
                                    supabase.table("loans")
                                    .select("*")
                                    .eq("user_id", user_id_global)
                                    .eq("loan_date", tanggal.isoformat())
                                    .neq("status", "rejected")
                                    .execute()
                                )

                                if existing_loan.data:
                                    st.warning(
                                        "⚠️ Anda sudah mengajukan peminjaman komputer pada tanggal ini. "
                                        "Hanya pengajuan dengan status 'rejected' yang bisa diajukan ulang."
                                    )
                                else:
                                    # Insert ke tabel loans (status pending)
                                    supabase.table("loans").insert(
                                        {
                                            "user_id": user_id_global,
                                            "computer_id": row.computer_id,
                                            "loan_date": tanggal.isoformat(),
                                            "status": "pending",
                                        }
                                    ).execute()

                                    st.success(
                                        f"✅ Pengajuan peminjaman {row.Komputer} berhasil dikirim! Menunggu persetujuan admin."
                                    )

            else:
                st.button(
                    "Tidak tersedia", disabled=True, key=f"not_available_{row.Komputer}"
                )

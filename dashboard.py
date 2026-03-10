# dashboard.py

import streamlit as st
import requests
import pandas as pd
import plotly.express as px  # Recommended for professional charts

#API = "http://127.0.0.1:8000"

#API = "https://niwy6jjpcr.us-east-1.awsapprunner.com"

API = "http://localhost:8000"

st.sidebar.write("API:", API)

st.set_page_config(layout="wide", page_title="Invoice Intel", page_icon="🧾")

st.title("AI Invoice Automation")

page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Upload Invoice", "Analytics", "AI Q&A"]
)

# Helper to fetch data
@st.cache_data(ttl=60)
def fetch_data():
    try:
        response = requests.get(f"{API}/invoices/", timeout=10)
        if response.status_code == 200:
            return pd.DataFrame(response.json())
        else:
            st.error("Backend returned an error")
            return pd.DataFrame()
    except requests.exceptions.Timeout:
        st.error("Backend request timed out. Please try again.")
        return pd.DataFrame()
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to backend API.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        return pd.DataFrame()
# ---------------- Upload ----------------

if page == "Upload Invoice":

    file = st.file_uploader("Upload Invoice PDF", type=["pdf"])

    if file:
        with st.spinner("Uploading..."):
            
            response = requests.post(
                f"{API}/upload/",
                files={"file": (file.name, file.getvalue(), "application/pdf")},
                timeout=30
            )

            if response.status_code != 200:
                st.error("Backend error")
                st.text(response.text)
            else:
                try:
                    data = response.json()
                    st.success(data.get("message", "Uploaded"))
                except:
                    st.error("Server did not return valid JSON")
                    st.text(response.text)

# ---------------- Dashboard ----------------

if page == "Dashboard":
    st.header("📊 Financial Overview")
    df = fetch_data()

    if df.empty:
        st.info("No data available. Please upload invoices.")
    else:
        # Metrics Row
        total_spend = df["Total Amount"].sum()
        total_gst = df["GST"].sum()
        avg_inv = df["Total Amount"].mean()

        m1, m2, m3 = st.columns(3)
        m1.metric("💰 Total Capital Outflow", f"₹{total_spend:,.2f}")
        m2.metric("🧾 Aggregate GST", f"₹{total_gst:,.2f}")
        m3.metric("📈 Average Invoice Value", f"₹{avg_inv:,.2f}")

        st.divider()
        st.subheader("Recent Transactions")
        # Displaying the clean dataframe from API
        st.dataframe(df, width='stretch', hide_index=True)

# ---------------- Analytics ----------------

# ---------------- Analytics ----------------
elif page == "Analytics":
    st.header("📈 Business Intelligence")
    df = fetch_data()

    if not df.empty:
        # 1. Convert Date safely. 'coerce' turns "N/A" into NaT (Not a Time)
        df["Date"] = pd.to_datetime(df["Date"], errors='coerce')
        
        # 2. Drop rows where Date is NaT so charts don't break
        df = df.dropna(subset=["Date"])
        
        # 3. Spend Trend (Area Chart)
        st.subheader("Cash Flow Timeline")
        trend_df = df.groupby("Date")["Total Amount"].sum().reset_index()
        # Use a professional blue-to-purple gradient feel
        st.area_chart(trend_df.set_index("Date"), color="#29b5e8")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Vendor Allocation")
            # Donut Chart with professional 'Icefire' colors
            fig_vendor = px.pie(df, values='Total Amount', names='Vendor Name', 
                               hole=0.5, color_discrete_sequence=px.colors.qualitative.Prism)
            fig_vendor.update_layout(showlegend=True)
            st.plotly_chart(fig_vendor, width='stretch')

        with col2:
            st.subheader("Tax Liability by Vendor")
            # Horizontal Bar Chart with a clean professional scale
            gst_df = df.groupby("Vendor Name")["GST"].sum().sort_values().reset_index()
            fig_gst = px.bar(gst_df, x='GST', y='Vendor Name', orientation='h',
                             color='GST', color_continuous_scale='Turbo')
            st.plotly_chart(fig_gst, width='stretch')

        # 4. Yearly Comparison
        st.divider()
        df["Year"] = df["Date"].dt.year
        yearly_summary = df.groupby("Year")["Total Amount"].sum().reset_index()
        st.subheader("Comparative Annual Growth")
        # Multi-color bars based on the Year
        st.bar_chart(yearly_summary.set_index("Year"), color="#636EFA")
    else:
        st.info("Upload data to view analytics.")

# ---------------- AI Q&A ----------------

elif page == "AI Q&A":

    st.header("🤖 Ask about your invoices")

    question = st.text_input("Enter your question about the invoices")

    if st.button("Ask"):

        if not question.strip():
            st.warning("Please enter a question")
        else:
            with st.spinner("Getting answer..."):

                response = requests.post(
                    f"{API}/ask/",
                    json={"question": question},
                    timeout=20
                )

                if response.status_code != 200:
                    st.error("Backend error")
                    st.text(response.text)
                else:
                    try:
                        data = response.json()
                        st.success("Answer:")
                        st.write(data.get("answer", "No answer provided"))
                    except:
                        st.error("Server did not return valid JSON")
                        st.text(response.text)

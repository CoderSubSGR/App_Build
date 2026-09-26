import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

EXPENSE_CATEGORIES = [
    "Food & Groceries", "Housing Loan EMI", "Music/Dance Fees", "School/Van Fees", "Utilities GAIL/Bescom/CAMS/BWSSB", "Transportation", "Credit Card", 
    "Maid & Services", "Entertainment", "Shopping Dress and Gifts", "Subscriptions Newspaper/OTT", "Medical & Healthcare", "Mobile/Internet", "Miscellaneous"
]

INCOME_CATEGORIES = [
    "Salary", "Rental Income", "Interests", "Other Income"
]

spreadsheet_url = None
if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
    spreadsheet_url = st.secrets["connections"]["gsheets"].get("spreadsheet")

def load_database():
    df_exp = pd.DataFrame(columns=["Date", "Month-Year", "Vendor/Business", "Category", "Amount"])
    df_inc = pd.DataFrame(columns=["Date", "Month-Year", "Source/Payer", "Category", "Amount"])
    savings_pct = 0.20
    limits = {cat: 10000.0 for cat in EXPENSE_CATEGORIES}

    if not spreadsheet_url:
        return df_exp, df_inc, savings_pct, limits, False

    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        try:
            df_exp = conn.read(worksheet="Expenses", ttl="0d")
            if df_exp.empty or "Amount" not in df_exp.columns:
                df_exp = pd.DataFrame(columns=["Date", "Month-Year", "Vendor/Business", "Category", "Amount"])
        except: pass
        try:
            df_inc = conn.read(worksheet="Income", ttl="0d")
            if df_inc.empty or "Amount" not in df_inc.columns:
                df_inc = pd.DataFrame(columns=["Date", "Month-Year", "Source/Payer", "Category", "Amount"])
        except: pass
        try:
            df_tar = conn.read(worksheet="Targets", ttl="0d")
            if not df_tar.empty and "Parameter" in df_tar.columns:
                pct_rows = df_tar[df_tar["Parameter"] == "Savings_Target_Pct"]
                if not pct_rows.empty:
                    savings_pct = float(pct_rows["Value"].values[0])
                cap_rows = df_tar[df_tar["Parameter"] == "Budget_Cap"]
                if not cap_rows.empty:
                    fetched_limits = cap_rows.set_index("Category")["Value"].to_dict()
                    for cat in EXPENSE_CATEGORIES:
                        if cat in fetched_limits:
                            limits[cat] = float(fetched_limits[cat])
        except: pass
        return df_exp, df_inc, savings_pct, limits, True
    except:
        return df_exp, df_inc, savings_pct, limits, False

def save_database(df_exp, df_inc, savings_pct, limits):
    if not spreadsheet_url: return False
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        target_rows = [{"Parameter": "Savings_Target_Pct", "Category": "Global", "Value": savings_pct}]
        for cat, val in limits.items():
            target_rows.append({"Parameter": "Budget_Cap", "Category": cat, "Value": val})
        df_tar = pd.DataFrame(target_rows)
        conn.update(worksheet="Expenses", data=df_exp)
        conn.update(worksheet="Income", data=df_inc)
        conn.update(worksheet="Targets", data=df_tar)
        return True
    except: return False

st.set_page_config(page_title="Budget Core Console", page_icon="💰", layout="wide")
df_expense, df_income, fetched_savings_pct, fetched_limits, connection_status = load_database()

if not df_expense.empty:
    df_expense["Amount"] = pd.to_numeric(df_expense["Amount"], errors='coerce').fillna(0.0)
if not df_income.empty:
    df_income["Amount"] = pd.to_numeric(df_income["Amount"], errors='coerce').fillna(0.0)

if "global_savings_pct" not in st.session_state:
    st.session_state.global_savings_pct = fetched_savings_pct
if "category_limits" not in st.session_state:
    st.session_state.category_limits = fetched_limits

st.sidebar.title("🛠️ Control Console")
if not connection_status:
    st.sidebar.error("⚠️ Google Spreadsheet secret missing or invalid.")
else:
    st.sidebar.success("🔗 Connected to Live Google Sheet database.")

menu_choice = st.sidebar.selectbox("Choose Operation Mode", ["Log New Transaction", "Setup Budget Caps & Targets", "Manage / Undo Records"])

if menu_choice == "Log New Transaction":
    st.sidebar.subheader("📝 Transaction Input")
    tx_type = st.sidebar.radio("Transaction Type", ["Expense 💸", "Income 💰"])
    with st.sidebar.form("transaction_form", clear_on_submit=True):
        selected_date = st.date_input("Date", datetime.today())
        month_year_str = selected_date.strftime("%B %Y")
        entity_label = "Vendor/Business Name" if "Expense" in tx_type else "Source/Payer Name"
        entity_name = st.text_input(entity_label)
        cats_list = EXPENSE_CATEGORIES if "Expense" in tx_type else INCOME_CATEGORIES
        selected_cat = st.selectbox("Category", cats_list)
        amount = st.number_input("Amount (₹)", min_value=0.0, step=1.0, format="%.2f")
        submitted = st.form_submit_button("Save Entry")
        if submitted:
            if not connection_status: st.sidebar.error("Offline")
            elif not entity_name.strip(): st.sidebar.error("Blank Name")
            elif amount <= 0: st.sidebar.error("Invalid Amount")
            else:
                date_str = selected_date.strftime("%Y-%m-%d")
                if "Expense" in tx_type:
                    new_row = {"Date": date_str, "Month-Year": month_year_str, "Vendor/Business": entity_name, "Category": selected_cat, "Amount": amount}
                    df_expense = pd.concat([df_expense, pd.DataFrame([new_row])], ignore_index=True)
                else:
                    new_row = {"Date": date_str, "Month-Year": month_year_str, "Source/Payer": entity_name, "Category": selected_cat, "Amount": amount}
                    df_income = pd.concat([df_income, pd.DataFrame([new_row])], ignore_index=True)
                if save_database(df_expense, df_income, st.session_state.global_savings_pct, st.session_state.category_limits):
                    st.sidebar.success("Recorded entry!")
                    st.rerun()

elif menu_choice == "Setup Budget Caps & Targets":
    st.sidebar.subheader("⚙️ Goals & Parameters")
    current_savings_pct = st.session_state.global_savings_pct
    new_pct = st.sidebar.slider("Global Target Savings Percentage", min_value=0, max_value=100, value=int(current_savings_pct * 100), step=5)
    if st.sidebar.button("Save Savings Target"):
        if connection_status:
            st.session_state.global_savings_pct = new_pct / 100.0
            save_database(df_expense, df_income, st.session_state.global_savings_pct, st.session_state.category_limits)
            st.sidebar.success("Global Savings Target Adjusted!")
            st.rerun()
    st.sidebar.markdown("---")
    st.sidebar.subheader("🗂️ Category Budget Caps")
    target_cat = st.sidebar.selectbox("Select Sub-Category to modify", EXPENSE_CATEGORIES)
    current_cap = st.session_state.category_limits.get(target_cat, 10000.0)
    new_cap = st.sidebar.number_input(f"Monthly Budget Cap for {target_cat} (₹)", min_value=0.0, value=float(current_cap), step=100.0)
    if st.sidebar.button("Update Category Cap"):
        if connection_status:
            st.session_state.category_limits[target_cat] = new_cap
            save_database(df_expense, df_income, st.session_state.global_savings_pct, st.session_state.category_limits)
            st.sidebar.success("Updated category cap!")
            st.rerun()

elif menu_choice == "Manage / Undo Records":
    st.sidebar.subheader("⚠️ Ledger Maintenance")
    del_target = st.sidebar.radio("Target Ledger Sheet", ["Expenses Ledger", "Income Ledger"])
    if st.sidebar.button("🗑️ Delete Most Recent Entry"):
        if not connection_status: st.sidebar.error("Offline")
        elif del_target == "Expenses Ledger" and not df_expense.empty:
            df_expense = df_expense.drop(df_expense.index[-1])
            save_database(df_expense, df_income, st.session_state.global_savings_pct, st.session_state.category_limits)
            st.rerun()
        elif del_target == "Income Ledger" and not df_income.empty:
            df_income = df_income.drop(df_income.index[-1])
            save_database(df_expense, df_income, st.session_state.global_savings_pct, st.session_state.category_limits)
            st.rerun()

st.title("🌟 Garuda Gamana Budget Dashboard 🌟")
total_exp = df_expense["Amount"].sum() if not df_expense.empty else 0.0
total_inc = df_income["Amount"].sum() if not df_income.empty else 0.0
net_balance = total_inc - total_exp

m1, m2, m3 = st.columns(3)
m1.metric("Gross Income", f"₹{total_inc:,.2f}")
m2.metric("Gross Expenses", f"₹{total_exp:,.2f}")
m3.metric("Net Financial Balance", f"₹{net_balance:,.2f}")

st.markdown("---")
current_month_str = datetime.now().strftime("%B %Y")
all_months = list(set(df_expense["Month-Year"].dropna().astype(str).tolist() + df_income["Month-Year"].dropna().astype(str).tolist()))
if current_month_str not in all_months: all_months.append(current_month_str)
all_months.sort()
selected_month = st.selectbox("📅 Select Scope Month", all_months, index=all_months.index(current_month_str) if current_month_str in all_months else 0)

st.subheader(f"🎯 Target Scope Analysis for {selected_month.upper()}")
m_inc = df_income[df_income["Month-Year"] == selected_month]["Amount"].sum() if not df_income.empty else 0.0
m_exp = df_expense[df_expense["Month-Year"] == selected_month]["Amount"].sum() if not df_expense.empty else 0.0
m_sav = m_inc - m_exp
target_savings_threshold = m_inc * st.session_state.global_savings_pct

col_scope_a, col_scope_b = st.columns(2)
with col_scope_a:
    st.markdown("**Monthly Performance Summary:**")
    st.write(f"• **Monthly Income:** ₹{m_inc:,.2f}")
    st.write(f"• **Current Expenses:** ₹{m_exp:,.2f}")
    st.write(f"• **Target Savings Goal ({st.session_state.global_savings_pct*100:.0f}%):** ₹{target_savings_threshold:,.2f}")
    if m_inc > 0:
        if m_sav >= target_savings_threshold:
            st.success(f"✅ **Savings Health:** Saved ₹{m_sav:,.2f}")
        else:
            st.error(f"🚨 **GOAL AT RISK:** Saved ₹{m_sav:,.2f}")

with col_scope_b:
    monthly_exp_df = df_expense[df_expense["Month-Year"] == selected_month]
    if not monthly_exp_df.empty:
        cat_chart_data = monthly_exp_df.groupby("Category")["Amount"].sum().reset_index()
        st.bar_chart(cat_chart_data, x="Category", y="Amount", color="#FF4B4B", use_container_width=True)

st.markdown("### 📊 Sub-Category Budget Tracker")
tracker_rows = []
cat_spend = monthly_exp_df.groupby("Category")["Amount"].sum().to_dict() if not monthly_exp_df.empty else {}
for cat in EXPENSE_CATEGORIES:
    spent = cat_spend.get(cat, 0.0)
    limit = st.session_state.category_limits.get(cat, 10000.0)
    pct = (spent / limit) * 100 if limit > 0 else 0.0
    if spent > limit: flag = f"⚠️ OVER BUDGET (Exceeded by ₹{spent - limit:,.2f})"
    elif pct >= 80: flag = "🔶 Warning (Approaching limit)"
    else: flag = "🟢 Safe"
    tracker_rows.append({
        "Expense Category": cat,
        "Spent Amount": f"₹{spent:,.2f}",
        "Budget Ceiling Cap": f"₹{limit:,.2f}",
        "Utilization %": f"{pct:.1f}%",
        "Status Flag Alert": flag
    })
st.table(pd.DataFrame(tracker_rows))

st.markdown("---")
tab1, tab2 = st.tabs(["🗂️ Global Expenses Logs Ledger", "📥 Global Income Logs Ledger"])
with tab1: st.dataframe(df_expense, use_container_width=True)
with tab2: st.dataframe(df_income, use_container_width=True)

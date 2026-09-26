import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- Configuration Constants ---
EXPENSE_CATEGORIES = [
    "Food & Groceries", "Housing Loan EMI", "Music/Dance Fees", "School/Van Fees", "Utilities GAIL/Bescom/CAMS/BWSSB", "Transportation", "Credit Card", 
    "Maid & Services", "Entertainment", "Shopping Dress and Gifts", "Subscriptions Newspaper/OTT", "Medical & Healthcare", "Mobile/Internet", "Miscellaneous"
]

INCOME_CATEGORIES = [
    "Salary", "Rental Income", "Interests", "Other Income"
]

# --- Core Database & Sheet Pipeline Connection Engine ---
# Defensive connection mapping to completely bypass configuration script freezes
spreadsheet_url = None
if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
    spreadsheet_url = st.secrets["connections"]["gsheets"].get("spreadsheet")

def load_database():
    """Systematically fetches data matrices across tracking sheets using safe fallbacks."""
    # Build blank fallbacks first in case connection is not yet configured
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
        except:
            pass
            
        try:
            df_inc = conn.read(worksheet="Income", ttl="0d")
            if df_inc.empty or "Amount" not in df_inc.columns:
                df_inc = pd.DataFrame(columns=["Date", "Month-Year", "Source/Payer", "Category", "Amount"])
        except:
            pass
            
        try:
            df_tar = conn.read(worksheet="Targets", ttl="0d")
            if not df_tar.empty and "Parameter" in df_tar.columns:
                savings_pct = float(df_tar.loc[df_tar["Parameter"] == "Savings_Target_Pct", "Value"].values)
                limits = df_tar[df_tar["Parameter"] == "Budget_Cap"].set_index("Category")["Value"].to_dict()
        except:
            pass
            
        return df_exp, df_inc, savings_pct, limits, True
    except Exception as e:
        return df_exp, df_inc, savings_pct, limits, False

def save_database(df_exp, df_inc, savings_pct, limits):
    """Safely updates sheets across the connected cloud Google Sheet."""
    if not spreadsheet_url:
        return False
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
    except:
        return False

# --- Initialize Application Architecture Data State ---
st.set_page_config(page_title="Budget Core Console", page_icon="💰", layout="wide")
df_expense, df_income, global_savings_pct, category_limits, connection_status = load_database()

# Enforce clean data types for mathematical operations
if not df_expense.empty:
    df_expense["Amount"] = pd.to_numeric(df_expense["Amount"], errors='coerce').fillna(0.0)
if not df_income.empty:
    df_income["Amount"] = pd.to_numeric(df_income["Amount"], errors='coerce').fillna(0.0)

# --- SIDEBAR: Transaction & Configuration Controls ---
st.sidebar.title("🛠️ Control Console")

if not connection_status:
    st.sidebar.error("⚠️ Google Spreadsheet secret missing or invalid. Check your Streamlit Secrets setting.")
    st.sidebar.info("Dashboard is currently running in temporary offline preview mode.")
else:
    st.sidebar.success("🔗 Connected to Live Google Sheet database.")

menu_choice = st.sidebar.selectbox(
    "Choose Operation Mode", 
    ["Log New Transaction", "Setup Budget Caps & Targets", "Manage / Undo Records"]
)

# Initialize configuration in session state if not already done
if "global_savings_pct" not in st.session_state:
    st.session_state.global_savings_pct = 0.20  # Your default fallback

if "category_limits" not in st.session_state:
    st.session_state.category_limits = {cat: 10000.0 for cat in EXPENSE_CATEGORIES} # Your default fallback


# 1. OPERATION MODE: LOGGING ENTRIES
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
            if not connection_status:
                st.sidebar.error("Cannot save entries while spreadsheet is offline.")
            elif not entity_name.strip():
                st.sidebar.error("Name field cannot be left blank.")
            elif amount <= 0:
                st.sidebar.error("Please provide a valid transaction amount.")
            else:
                date_str = selected_date.strftime("%Y-%m-%d")
                if "Expense" in tx_type:
                    new_row = {"Date": date_str, "Month-Year": month_year_str, "Vendor/Business": entity_name, "Category": selected_cat, "Amount": amount}
                    df_expense = pd.concat([df_expense, pd.DataFrame([new_row])], ignore_index=True)
                else:
                    new_row = {"Date": date_str, "Month-Year": month_year_str, "Source/Payer": entity_name, "Category": selected_cat, "Amount": amount}
                    df_income = pd.concat([df_income, pd.DataFrame([new_row])], ignore_index=True)
                
                if save_database(df_expense, df_income, global_savings_pct, category_limits):
                    st.sidebar.success(f"Recorded entry dynamically to Google Sheets!")
                    st.rerun()
                else:
                    st.sidebar.error("Failed to write data. Check sheet write permissions.")

# 2. OPERATION MODE: SETUP GOALS
elif menu_choice == "Setup Budget Caps & Targets":
    st.sidebar.subheader("⚙️ Goals & Parameters")
    
    # Read baseline directly from session_state
    current_savings_pct = st.session_state.global_savings_pct
    
    new_pct = st.sidebar.slider(
        "Global Target Savings Percentage", 
        min_value=0, max_value=100, value=int(current_savings_pct * 100), step=5
    )
    
    # Fix loop: Use an explicit button trigger or a safer assignment check
    if st.sidebar.button("Save Savings Target"):
        if connection_status:
            st.session_state.global_savings_pct = new_pct / 100.0
            save_database(df_expense, df_income, st.session_state.global_savings_pct, st.session_state.category_limits)
            st.sidebar.success("Global Savings Target Adjusted!")
            st.rerun()
        else:
            st.sidebar.error("Cannot modify configuration parameters while offline.")
        
    st.sidebar.markdown("---")
    st.sidebar.subheader("🗂️ Category Budget Caps")
    target_cat = st.sidebar.selectbox("Select Sub-Category to modify", EXPENSE_CATEGORIES)
    
    # Read dynamic ceiling directly from session_state
    current_cap = st.session_state.category_limits.get(target_cat, 10000.0)
    
    new_cap = st.sidebar.number_input(
        f"Monthly Budget Cap for {target_cat} (₹)", 
        min_value=0.0, value=float(current_cap), step=100.0
    )
    
    if st.sidebar.button("Update Category Cap"):
        if connection_status:
            # Save directly to session state so it survives the rerun
            st.session_state.category_limits[target_cat] = new_cap
            
            save_database(df_expense, df_income, st.session_state.global_savings_pct, st.session_state.category_limits)
            st.sidebar.success(f"Updated budget ceiling configuration for {target_cat}!")
            #st.rerun()
        else:
            st.sidebar.error("Cannot modify configuration parameters while offline.")

# 3. OPERATION MODE: UNDO / DELETE LAST LOG
elif menu_choice == "Manage / Undo Records":
    st.sidebar.subheader("⚠️ Ledger Maintenance")
    del_target = st.sidebar.radio("Target Ledger Sheet", ["Expenses Ledger", "Income Ledger"])
    
    if st.sidebar.button("🗑️ Delete Most Recent Entry"):
        if not connection_status:
            st.sidebar.error("Cannot perform ledger cleanup while offline.")
        elif del_target == "Expenses Ledger" and not df_expense.empty:
            df_expense = df_expense.drop(df_expense.index[-1])
            save_database(df_expense, df_income, global_savings_pct, category_limits)
            st.sidebar.success("Last recorded expense dropped successfully.")
            st.rerun()
        elif del_target == "Income Ledger" and not df_income.empty:
            df_income = df_income.drop(df_income.index[-1])
            save_database(df_expense, df_income, global_savings_pct, category_limits)
            st.sidebar.success("Last recorded income entry dropped successfully.")
            st.rerun()
        else:
            st.sidebar.warning("Target ledger sheet contains no entries to clean.")

# --- MAIN DASHBOARD INTERFACE UI ---
st.title("🌟 Garuda Gamana Budget Dashboard 🌟")

# Core Aggregations Calculations
total_exp = df_expense["Amount"].sum() if not df_expense.empty else 0.0
total_inc = df_income["Amount"].sum() if not df_income.empty else 0.0
net_balance = total_inc - total_exp

# Global Lifetime Analytics Cards
m1, m2, m3 = st.columns(3)
m1.metric("Lifetime Gross Income", f"₹{total_inc:,.2f}")
m2.metric("Lifetime Gross Expenses", f"₹{total_exp:,.2f}")
m3.metric("Net Financial Balance", f"₹{net_balance:,.2f}", delta=f"₹{net_balance:,.2f}")

st.markdown("---")

# Monthly Tracking Filtering Layout
current_month_str = datetime.now().strftime("%B %Y")
all_months = list(set(df_expense["Month-Year"].dropna().astype(str).tolist() + df_income["Month-Year"].dropna().astype(str).tolist()))
if current_month_str not in all_months:
    all_months.append(current_month_str)
all_months.sort()

selected_month = st.selectbox("📅 Select Targeting Scope Month Analysis", all_months, index=all_months.index(current_month_str) if current_month_str in all_months else 0)

st.subheader(f"🎯 Target Scope Analysis for {selected_month.upper()}")

m_inc = df_income[df_income["Month-Year"] == selected_month]["Amount"].sum() if not df_income.empty else 0.0
m_exp = df_expense[df_expense["Month-Year"] == selected_month]["Amount"].sum() if not df_expense.empty else 0.0
m_sav = m_inc - m_exp
target_savings_threshold = m_inc * global_savings_pct

col_scope_a, col_scope_b = st.columns(2)

with col_scope_a:
    st.markdown(f"**Monthly Performance Summary:**")
    st.write(f"• **Monthly Income:** ₹{m_inc:,.2f}")
    st.write(f"• **Current Expenses:** ₹{m_exp:,.2f}")
    st.write(f"• **Target Savings Goal ({global_savings_pct*100:.0f}%):** ₹{target_savings_threshold:,.2f}")
    
    if m_inc > 0:
        if m_sav >= target_savings_threshold:
            st.success(f"✅ **Savings Health:** Keep it up! Currently saved ₹{m_sav:,.2f}")
        else:
            st.error(f"🚨 **GOAL AT RISK:** Saved ₹{m_sav:,.2f} (Short by ₹{max(0.0, target_savings_threshold - m_sav):,.2f})")
    else:
        st.info("💡 Log incoming revenue for this targeting scope month to verify metrics configuration.")

with col_scope_b:
    # Monthly Category Data Visualization Layout
    monthly_exp_df = df_expense[df_expense["Month-Year"] == selected_month]
    if not monthly_exp_df.empty:
        cat_chart_data = monthly_exp_df.groupby("Category")["Amount"].sum().reset_index()
        st.bar_chart(cat_chart_data, x="Category", y="Amount", color="#FF4B4B", use_container_width=True)
    else:
        st.caption("No distribution transactions mapped for bar chart graphing execution.")

# Sub-Category Budget Breakdown Tracker
st.markdown("### 📊 Sub-Category Budget Tracker")
tracker_rows = []
cat_spend = monthly_exp_df.groupby("Category")["Amount"].sum().to_dict() if not monthly_exp_df.empty else {}

for cat in EXPENSE_CATEGORIES:
    spent = cat_spend.get(cat, 0.0)
    limit = st.session_state.category_limits.get(cat, 10000.0)
    pct = (spent / limit) * 100 if limit > 0 else 0.0
    
    if spent > limit:
        flag = f"⚠️ OVER BUDGET (Exceeded by ₹{spent - limit:,.2f})"
    elif pct >= 80:
        flag = "🔶 Warning (Approaching limit)"
    else:
        flag = "🟢 Safe"
        
    tracker_rows.append({
        "Expense Category": cat,
        "Spent Amount": f"₹{spent:,.2f}",
        "Budget Ceiling Cap": f"₹{limit:,.2f}",
        "Utilization %": f"{pct:.1f}%",
        "Status Flag Alert": flag
    })

st.table(pd.DataFrame(tracker_rows))

# Raw Records Inspection Engine
st.markdown("---")
tab1, tab2 = st.tabs(["🗂️ Global Expenses Logs Ledger", "📥 Global Income Logs Ledger"])
with tab1:
    st.dataframe(df_expense, use_container_width=True)
with tab2:
    st.dataframe(df_income, use_container_width=True)

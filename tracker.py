pip install pandas openpyxl
pip install matplotlib seaborn
pip install ipywidgets

import os
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
from IPython.display import display, clear_output

# --- Configuration File Routing ---
EXCEL_FILE = "daily_expense_tracker.xlsx"

# Standard Base Category Matrix Structures
EXPENSE_CATEGORIES = [
    "Food & Groceries", "Rent & Housing", "Utilities", "Transport & Fuel", 
    "Entertainment", "Shopping", "Subscriptions", "Medical & Healthcare", "Miscellaneous"
]

INCOME_CATEGORIES = [
    "Salary/Wages", "Freelance & Side Hustles", "Investments", "Gifts & Reimbursements", "Other Income"
]

def initialize_database():
    """Ensures sheets for Expenses, Income, and Targets framework exist systematically."""
    if os.path.exists(EXCEL_FILE):
        try:
            df_exp = pd.read_excel(EXCEL_FILE, sheet_name="Expenses")
            df_inc = pd.read_excel(EXCEL_FILE, sheet_name="Income")
        except Exception:
            df_exp = pd.DataFrame(columns=["Date", "Month-Year", "Vendor/Business", "Category", "Amount"])
            df_inc = pd.DataFrame(columns=["Date", "Month-Year", "Source/Payer", "Category", "Amount"])
        
        # Load or generate Target configurations sheet dynamically
        try:
            df_tar = pd.read_excel(EXCEL_FILE, sheet_name="Targets")
            savings_pct = float(df_tar.loc[df_tar["Parameter"] == "Savings_Target_Pct", "Value"].values[0])
            limits = df_tar[df_tar["Parameter"] == "Budget_Cap"].set_index("Category")["Value"].to_dict()
        except Exception:
            savings_pct = 0.20
            limits = {cat: 10000.0 for cat in EXPENSE_CATEGORIES}  # Default baseline in Rupees
            save_database(df_exp, df_inc, savings_pct, limits)
            
        return df_exp, df_inc, savings_pct, limits
    else:
        df_exp = pd.DataFrame(columns=["Date", "Month-Year", "Vendor/Business", "Category", "Amount"])
        df_inc = pd.DataFrame(columns=["Date", "Month-Year", "Source/Payer", "Category", "Amount"])
        savings_pct = 0.20
        limits = {cat: 10000.0 for cat in EXPENSE_CATEGORIES}
        save_database(df_exp, df_inc, savings_pct, limits)
        return df_exp, df_inc, savings_pct, limits

def save_database(df_exp, df_inc, savings_pct, limits):
    """Safely saves data matrices along with active user target boundaries into Excel."""
    target_rows = [{"Parameter": "Savings_Target_Pct", "Category": "Global", "Value": savings_pct}]
    for cat, val in limits.items():
        target_rows.append({"Parameter": "Budget_Cap", "Category": cat, "Value": val})
    df_tar = pd.DataFrame(target_rows)
    
    with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl") as writer:
        df_exp.to_excel(writer, sheet_name="Expenses", index=False)
        df_inc.to_excel(writer, sheet_name="Income", index=False)
        df_tar.to_excel(writer, sheet_name="Targets", index=False)

def render_analytics(df_exp, df_inc, savings_pct, limits):
    """Generates precise cash flow breakdowns balancing inputs against current caps."""
    total_exp = df_exp["Amount"].sum() if not df_exp.empty else 0.0
    total_inc = df_inc["Amount"].sum() if not df_inc.empty else 0.0
    
    print("\\n" + "🌟"*25)
    print(f" 📊 LIFETIME CASH FLOW:  Income: ₹{total_inc:,.2f}  |  Expenses: ₹{total_exp:,.2f}")
    print(f" 💰 NET LIFETIME BALANCE: ₹{(total_inc - total_exp):,.2f}")
    print("🌟"*25)

    if not df_exp.empty: 
        df_exp["Date"] = pd.to_datetime(df_exp["Date"])
    if not df_inc.empty: 
        df_inc["Date"] = pd.to_datetime(df_inc["Date"])

    current_month_str = datetime.now().strftime("%B %Y")
    if not df_exp.empty: 
        current_month_str = df_exp.sort_values(by="Date", ascending=False)["Month-Year"].iloc[0]
    elif not df_inc.empty:
        current_month_str = df_inc.sort_values(by="Date", ascending=False)["Month-Year"].iloc[0]

    print(f"\\n🎯 TARGET SCOPE ANALYSIS FOR CURRENT ACTIVE MONTH: [{current_month_str.upper()}]")
    print("-" * 75)
    
    m_inc = df_inc[df_inc["Month-Year"] == current_month_str]["Amount"].sum() if not df_inc.empty else 0.0
    m_exp = df_exp[df_exp["Month-Year"] == current_month_str]["Amount"].sum() if not df_exp.empty else 0.0
    m_sav = m_inc - m_exp
    
    target_savings_threshold = m_inc * savings_pct
    
    if m_inc > 0:
        print(f" Monthly Income: ₹{m_inc:,.2f}  |  Current Expenses: ₹{m_exp:,.2f}")
        print(f" Target Savings Goal ({savings_pct*100:.0f}%): ₹{target_savings_threshold:,.2f}")
        if m_sav >= target_savings_threshold:
            print(f" ✅ Savings Health: Keep it up! Currently saved ₹{m_sav:,.2f}")
        else:
            print(f" 🚨 GOAL AT RISK: Saved ₹{m_sav:,.2f} (Short by ₹{max(0, target_savings_threshold - m_sav):,.2f})")
    else:
        print(" 💡 Tip: Log income for this month to check target tracking variables!")

    print("\\n 🗂️ SUB-CATEGORY BUDGET TRACKER:")
    cat_spend = df_exp[df_exp["Month-Year"] == current_month_str].groupby("Category")["Amount"].sum().to_dict() if not df_exp.empty else {}
    
    for cat in EXPENSE_CATEGORIES:
        spent = cat_spend.get(cat, 0.0)
        limit = limits.get(cat, 0.0)
        pct = (spent / limit) * 100 if limit > 0 else 0.0
        status_flag = "🟢 Safe"
        if spent > limit: 
            status_flag = f"⚠️ OVER BUDGET (Exceeded by ₹{spent - limit:,.2f})"
        elif pct >= 80: 
            status_flag = "   Warning (Approaching limit)"
        print(f"   • {cat:<22}: Spent ₹{spent:>9,.2f} / Cap ₹{limit:>9,.2f} ({pct:>5.1f}%) -> {status_flag}")
    print("-" * 75)

# --- Runtime Interactive System Loop ---
df_expense, df_income, global_savings_pct, category_limits = initialize_database()

while True:
    clear_output(wait=True)
    render_analytics(df_expense, df_income, global_savings_pct, category_limits)
    
    print("\\n" + "="*40)
    print(" 🛠️  BUDGET CORE MASTER CONTROLLER CONSOLE")
    print("="*40)
    print(" 1. Log Daily Expense 💸")
    print(" 2. Log Daily Income 💰")
    print(" 3. Setup / Modify Target & Budget Caps ⚙️")
    print(" 4. Undo / Delete Last Entry ⚠️")
    print(" 5. Close App Engine 👋")
    
    choice = input("\\nSelect operation code (1-5): ").strip()
    
    if choice == "5":
        print("🔒 Application closed securely. Sheet configurations updated on disk!")
        break
        
    # --- INTERACTIVE CONFIGURATION TARGET ENGINE ---
    elif choice == "3":
        print("\\n⚙️ SETUP GOALS AND BUDGET REGIME TARGETS")
        print(" 1. Update Overall Savings Target Percentage")
        print(" 2. Update Specific Sub-Category Budget Cap")
        sub_choice = input("Select update mode (1-2): ").strip()
        
        if sub_choice == "1":
            try:
                new_pct = float(input("Enter new target savings percentage (e.g., 25 for 25%): "))
                if 0 <= new_pct <= 100:
                    global_savings_pct = new_pct / 100.0
                    save_database(df_expense, df_income, global_savings_pct, category_limits)
                    input("✔️ Overall Savings Target updated successfully! Press Enter...")
                else: 
                    raise ValueError
            except ValueError:
                input("❌ Invalid percent value constraint layout. Setup aborted...")
        
        elif sub_choice == "2":
            print("\\nSelect Sub-Category to modify:")
            for idx, cat in enumerate(EXPENSE_CATEGORIES, 1):
                print(f"  {idx}. {cat} (Current Cap: ₹{category_limits.get(cat, 0.0):.2f})")
            try:
                cat_idx = int(input(f"Choice (1-{len(EXPENSE_CATEGORIES)}): "))
                target_cat = EXPENSE_CATEGORIES[cat_idx - 1]
                new_cap = float(input(f"Enter new monthly budget Rupee cap for {target_cat}: ₹"))
                if new_cap >= 0:
                    category_limits[target_cat] = new_cap
                    save_database(df_expense, df_income, global_savings_pct, category_limits)
                    input(f"✔️ {target_cat} limit set to ₹{new_cap:.2f}! Press Enter...")
                else: 
                    raise ValueError
            except:
                input("❌ Invalid entry value constraint layout. Configuration aborted...")
        continue

    elif choice == "4":
        print("\\n🔎 From which ledger sheet do you want to remove the last transaction?")
        del_target = input("Type '1' for Expenses or '2' for Income (or press Enter to cancel): ").strip()
        if del_target == "1" and not df_expense.empty:
            df_expense = df_expense.drop(df_expense.index[-1])
            save_database(df_expense, df_income, global_savings_pct, category_limits)
            input("\\n🗑️ Removed last Expense log successfully. Press Enter...")
        elif del_target == "2" and not df_income.empty:
            df_income = df_income.drop(df_income.index[-1])
            save_database(df_expense, df_income, global_savings_pct, category_limits)
            input("\\n🗑️ Removed last Income log successfully. Press Enter...")
        else:
            input("\\n❌ Request cancelled or target ledger sheet is empty. Press Enter...")
        continue

    elif choice in ["1", "2"]:
        is_expense = (choice == "1")
        type_lbl = "Expense" if is_expense else "Income"
        cats_list = EXPENSE_CATEGORIES if is_expense else INCOME_CATEGORIES
        
        print(f"\\n--- Logging New {type_lbl} ---")
        date_in = input("Date (YYYY-MM-DD) or press Enter for today: ").strip()
        if not date_in:
            selected_date = datetime.now()
        else:
            try:
                selected_date = datetime.strptime(date_in, "%Y-%m-%d")
            except ValueError:
                input("❌ Invalid date format. Entry aborted...")
                continue
        month_year_str = selected_date.strftime("%B %Y")
        
        entity_name = input(f"Enter {'Vendor/Business' if is_expense else 'Source/Payer'} name: ").strip()
        if not entity_name: 
            continue
            
        print(f"\\nSelect Custom {type_lbl} Category:")
        for idx, cat in enumerate(cats_list, 1): 
            print(f"  {idx}. {cat}")
        try:
            cat_idx = int(input(f"Choice (1-{len(cats_list)}): "))
            selected_cat = cats_list[cat_idx - 1]
        except (ValueError, IndexError):
            selected_cat = cats_list[-1]
            
        try:
            amount = float(input("Enter Amount (₹): "))
            if amount <= 0: 
                raise ValueError
        except ValueError: 
            continue
            
        if is_expense:
            new_row = {"Date": selected_date.strftime("%Y-%m-%d"), "Month-Year": month_year_str, "Vendor/Business": entity_name, "Category": selected_cat, "Amount": amount}
            df_expense = pd.concat([df_expense, pd.DataFrame([new_row])], ignore_index=True)
        else:
            new_row = {"Date": selected_date.strftime("%Y-%m-%d"), "Month-Year": month_year_str, "Source/Payer": entity_name, "Category": selected_cat, "Amount": amount}
            df_income = pd.concat([df_income, pd.DataFrame([new_row])], ignore_index=True)
            
        save_database(df_expense, df_income, global_savings_pct, category_limits)

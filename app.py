from flask import Flask, render_template, request, redirect, Response, flash, jsonify
import pyodbc
import csv
from io import StringIO
import os
from dotenv import load_dotenv

load_dotenv()


from db import (
    get_all_products,
    add_product,
    get_product,
    update_product,
    delete_product,
    get_dashboard_stats,
    get_recent_transactions,
    get_all_categories,
    get_all_suppliers,
    get_all_transactions
)
from google import genai
from google.genai import types


app = Flask(__name__)
app.secret_key = 'omnistock_super_secret_key_2026'

@app.context_processor
def inject_notifications():
    from db import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ProductName, Quantity FROM Products WHERE Quantity < 10")
    low_stock_items = cursor.fetchall()
    notifications = []
    for item in low_stock_items:
        if item[1] <= 0:
            notifications.append({'title': 'Out of Stock', 'message': f'{item[0]} is out of stock.', 'type': 'danger'})
        else:
            notifications.append({'title': 'Low Stock', 'message': f'Only {item[1]} left for {item[0]}.', 'type': 'warning'})
    return dict(notifications=notifications)

@app.route("/")
def dashboard():
    stats = get_dashboard_stats()
    transactions = get_recent_transactions()
    categories = get_all_categories()
    return render_template("dashboard.html", stats=stats, transactions=transactions, categories=categories)


@app.route("/products")
def products_list():
    query = request.args.get("q")
    products = get_all_products(query)
    return render_template("products.html", products=products)


@app.route("/add", methods=["GET", "POST"])
def add_page():
    if request.method == "POST":
        try:
            add_product(
                request.form["product_name"],
                request.form["category"],
                request.form["price"],
                request.form["quantity"],
                request.form["supplier"],
                request.form.get("product_id")
            )
            flash("Product added successfully!", "success")
            return redirect("/products")
        except pyodbc.IntegrityError:
            flash("Error: Product ID already exists or invalid data.", "error")
            return redirect("/add")
    return render_template("add.html")


@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_page(id):
    if request.method == "POST":
        try:
            update_product(
                id,
                request.form["product_name"],
                request.form["category"],
                request.form["price"],
                request.form["quantity"],
                request.form["supplier"],
                request.form.get("new_product_id")
            )
            flash("Product updated successfully!", "success")
            return redirect("/products")
        except pyodbc.IntegrityError:
            flash("Error: The new Product ID is already in use.", "error")
            return redirect(f"/edit/{id}")
    
    product = get_product(id)
    return render_template("edit.html", product=product)


@app.route("/delete/<int:id>")
def delete(id):
    delete_product(id)
    flash("Product deleted successfully!", "success")
    return redirect("/products")


@app.route("/categories")
def categories_page():
    categories = get_all_categories()
    return render_template("categories.html", categories=categories)


@app.route("/suppliers")
def suppliers_page():
    suppliers = get_all_suppliers()
    return render_template("suppliers.html", suppliers=suppliers)


@app.route("/history")
def history_page():
    query = request.args.get("q")
    transactions = get_all_transactions(query)
    return render_template("history.html", transactions=transactions)


@app.route("/settings")
def settings_page():
    return render_template("settings.html")


@app.route("/export")
def export_data():
    products = get_all_products()
    
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Product Name', 'Category', 'Price', 'Quantity', 'Supplier'])
    cw.writerows(products)
    
    output = si.getvalue()
    
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=inventory_report.csv"}
    )


@app.route("/api/chat", methods=["POST"])
def chat_api():
    try:
        data = request.get_json()
        user_message = data.get("message", "")
        
        if not user_message:
            return jsonify({"error": "Empty message"}), 400
            
        load_dotenv(override=True)
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key.strip() in ["", "your_api_key_here"]:
            return jsonify({"response": "⚠️ **GEMINI_API_KEY is not configured.**\n\nPlease update your `.env` file with a valid Google Gemini API Key:\n`GEMINI_API_KEY=your_actual_key_here`"})

        # --- RAG: Retrieve context from database ---
        # 1. Products & Alerts
        products = get_all_products()
        inventory_list = []
        low_stock_alerts = []
        for p in products:
            qty = p[4]
            product_str = f"ID: {p[0]}, Name: {p[1]}, Category: {p[2]}, Price: ${p[3]:.2f}, Quantity: {qty}, Supplier: {p[5]}"
            inventory_list.append(product_str)
            if qty < 10:
                alert_type = "OUT OF STOCK" if qty == 0 else "LOW STOCK"
                low_stock_alerts.append(f"[{alert_type}] {p[1]} (Qty: {qty})")

        # 2. History (Recent Transactions)
        transactions = get_recent_transactions()
        history_list = []
        for t in transactions:
            # t: TransactionId, ProductName, TransactionType, QuantityChanged, TransactionDate
            history_list.append(f"Date: {t[4]}, Product: {t[1]}, Type: {t[2]}, Qty Change: {t[3]}")
            
        # 3. Stats
        stats = get_dashboard_stats()
        
        context = f"""
INVENTORY DATA CONTEXT:
---
Total Products: {stats['total_products']}
Total Inventory Value: ${stats['total_value']:.2f}

ALERTS (Low Stock):
{chr(10).join(low_stock_alerts) if low_stock_alerts else "None"}

INVENTORY LIST:
{chr(10).join(inventory_list)}

RECENT TRANSACTION HISTORY:
{chr(10).join(history_list)}
---
"""
        system_instruction = (
            "You are an AI assistant for the OmniStock Inventory Management System. "
            "Your job is to answer user queries accurately based ONLY on the provided INVENTORY DATA CONTEXT. "
            "Keep your answers concise, helpful, and professional. "
            "If the user asks about products, alerts, or history, refer to the provided context. "
            "Do not make up information that is not in the context. "
            "Format your response using Markdown for readability (e.g., bullet points for lists)."
        )

        model_name = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=[context, f"User Query: {user_message}"],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2,
            )
        )
        
        return jsonify({"response": response.text})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_str = str(e)
        if "API_KEY_INVALID" in error_str or "API key not valid" in error_str:
            return jsonify({"response": "⚠️ **Invalid API Key.**\n\nPlease enter a valid Google Gemini API Key in your `.env` file (`GEMINI_API_KEY=...`)."})
        return jsonify({"response": f"⚠️ **Error:** {error_str}"})




if __name__ == "__main__":
    app.run(debug=True)
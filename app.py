from flask import Flask, render_template, request, redirect, Response, flash, jsonify
import pyodbc
import csv
from io import StringIO
import os
from dotenv import load_dotenv

load_dotenv()


import json
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
    get_all_transactions,
    get_product_velocity,
    get_supplier_details
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

def get_ai_predictions_data():
    try:
        velocity_data = get_product_velocity()
        stats = get_dashboard_stats()
        
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key and api_key.strip() and api_key.strip() != "your_api_key_here":
            try:
                client = genai.Client(api_key=api_key)
                model_name = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
                
                prompt_context = []
                for row in velocity_data:
                    prompt_context.append(f"Product: {row[1]}, Category: {row[2]}, Qty: {row[3]}, Price: ${row[4]}, Movement: {row[5]}")
                    
                sys_instruction = (
                    "You are an AI Inventory Demand Forecaster and Supply Chain Advisor. "
                    "Analyze the provided product inventory and movement data. "
                    "Output ONLY a valid JSON object with no markdown formatting or backticks. "
                    "JSON structure MUST be:\n"
                    "{\n"
                    '  "stockout_predictions": [\n'
                    '    {"product_name": "...", "category": "...", "current_qty": 0, "risk_level": "High|Medium|Low", "predicted_days_left": 0, "suggested_reorder_qty": 20, "reasoning": "..."}\n'
                    "  ],\n"
                    '  "smart_suggestions": [\n'
                    '    {"type": "Restock Warning|Optimization|Capital Insight", "icon": "fa-triangle-exclamation|fa-boxes-stacked|fa-chart-line", "badge_color": "danger|warning|info|success", "title": "...", "description": "..."}\n'
                    "  ]\n"
                    "}"
                )
                
                response = client.models.generate_content(
                    model=model_name,
                    contents=["Current Inventory State:\n" + "\n".join(prompt_context)],
                    config=types.GenerateContentConfig(
                        system_instruction=sys_instruction,
                        temperature=0.3,
                    )
                )
                
                raw_text = response.text.strip()
                if raw_text.startswith("```"):
                    raw_text = raw_text.split("```")[1]
                    if raw_text.startswith("json"):
                        raw_text = raw_text[4:]
                    raw_text = raw_text.strip()
                    
                ai_json = json.loads(raw_text)
                if "stockout_predictions" in ai_json and "smart_suggestions" in ai_json:
                    return ai_json
            except Exception as e:
                print(f"Gemini API Prediction fallback triggered: {e}")

        # Deterministic Rule-based Fallback Prediction Engine
        predictions = []
        suggestions = []
        
        for row in velocity_data:
            p_name, category, qty, price = row[1], row[2], row[3], float(row[4]) if row[4] else 0.0
            
            if qty <= 0:
                predictions.append({
                    "product_name": p_name,
                    "category": category,
                    "current_qty": qty,
                    "risk_level": "High",
                    "predicted_days_left": 0,
                    "suggested_reorder_qty": 25,
                    "reasoning": "Currently out of stock. Immediate replenishment required."
                })
                suggestions.append({
                    "type": "Restock Required",
                    "icon": "fa-circle-exclamation",
                    "badge_color": "danger",
                    "title": f"Critical Stockout: {p_name}",
                    "description": f"{p_name} is out of stock (0 units). Reorder ~25 units immediately."
                })
            elif qty <= 10:
                est_days = max(1, int(qty * 0.8))
                predictions.append({
                    "product_name": p_name,
                    "category": category,
                    "current_qty": qty,
                    "risk_level": "High" if qty < 5 else "Medium",
                    "predicted_days_left": est_days,
                    "suggested_reorder_qty": 20,
                    "reasoning": f"Low inventory stock. Expected stockout in ~{est_days} days based on current burn rate."
                })
                suggestions.append({
                    "type": "Low Stock Alert",
                    "icon": "fa-triangle-exclamation",
                    "badge_color": "warning",
                    "title": f"Low Stock Warning: {p_name}",
                    "description": f"Only {qty} units remaining in {category}. Place reorder of ~20 units before stock exhausts."
                })
            elif qty >= 50:
                suggestions.append({
                    "type": "Inventory Optimization",
                    "icon": "fa-boxes-stacked",
                    "badge_color": "info",
                    "title": f"High Holding Stock: {p_name}",
                    "description": f"{p_name} has {qty} units (Value: ₹{price * qty:,.2f}). Consider promotional discounts to free up capital."
                })

        if not suggestions:
            suggestions.append({
                "type": "Health Check",
                "icon": "fa-circle-check",
                "badge_color": "success",
                "title": "Healthy Stock Levels",
                "description": "All inventory items are currently well-balanced. No urgent stockout risks detected."
            })

        return {
            "stockout_predictions": predictions[:5],
            "smart_suggestions": suggestions[:6]
        }
    except Exception as err:
        print(f"Error generating AI predictions: {err}")
        return {
            "stockout_predictions": [],
            "smart_suggestions": [{
                "type": "Notice",
                "icon": "fa-info-circle",
                "badge_color": "info",
                "title": "AI Engine Ready",
                "description": "Add products and record transactions to view live AI predictions."
            }]
        }


@app.route("/")
def dashboard():
    stats = get_dashboard_stats()
    transactions = get_recent_transactions()
    categories = get_all_categories()
    
    category_labels = [cat[0] for cat in categories]
    category_data = [float(cat[2]) if cat[2] is not None else 0.0 for cat in categories]
    category_qty = [int(cat[1]) if cat[1] is not None else 0 for cat in categories]

    return render_template(
        "dashboard.html", 
        stats=stats, 
        transactions=transactions, 
        categories=categories,
        category_labels=category_labels,
        category_data=category_data,
        category_qty=category_qty
    )


@app.route("/api/ai-predictions")
def api_ai_predictions():
    data = get_ai_predictions_data()
    return jsonify(data)


@app.route("/ai-predictions")
def ai_predictions_page():
    ai_predictions = get_ai_predictions_data()
    return render_template("ai_predictions.html", ai_predictions=ai_predictions)





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
    supplier_names = [s[0] for s in suppliers]
    supplier_products = [int(s[1]) if s[1] is not None else 0 for s in suppliers]
    supplier_values = [float(s[2]) if s[2] is not None else 0.0 for s in suppliers]
    
    return render_template(
        "suppliers.html", 
        suppliers=suppliers,
        supplier_names=supplier_names,
        supplier_products=supplier_products,
        supplier_values=supplier_values
    )


@app.route("/suppliers/<path:name>")
def supplier_detail_page(name):
    summary, products = get_supplier_details(name)
    product_names = [p[1] for p in products]
    product_qtys = [int(p[4]) if p[4] is not None else 0 for p in products]
    product_values = [float(p[5]) if p[5] is not None else 0.0 for p in products]
    
    return render_template(
        "supplier_detail.html",
        summary=summary,
        products=products,
        product_names=product_names,
        product_qtys=product_qtys,
        product_values=product_values
    )


@app.route("/api/supplier/<path:name>")
def api_supplier_detail(name):
    summary, products = get_supplier_details(name)
    product_list = [{
        "id": p[0],
        "name": p[1],
        "category": p[2],
        "price": float(p[3]) if p[3] is not None else 0.0,
        "quantity": p[4],
        "total_value": float(p[5]) if p[5] is not None else 0.0
    } for p in products]
    
    return jsonify({
        "summary": summary,
        "products": product_list
    })



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


@app.route("/export/supplier/<path:name>")
def export_supplier_report(name):
    summary, products = get_supplier_details(name)
    
    si = StringIO()
    cw = csv.writer(si)
    
    cw.writerow(['SUPPLIER REPORT', name])
    cw.writerow(['Total Products Supplied', summary['total_products']])
    cw.writerow(['Total Stock Quantity', summary['total_quantity']])
    cw.writerow(['Total Inventory Value (INR)', f"{summary['total_value']:.2f}"])
    cw.writerow(['Average Product Unit Price (INR)', f"{summary['avg_price']:.2f}"])
    cw.writerow([])
    
    cw.writerow(['Product ID', 'Product Name', 'Category', 'Price (INR)', 'Stock Quantity', 'Total Inventory Value (INR)', 'Stock Status'])
    
    for p in products:
        qty = p[4]
        status = "Out of Stock" if qty <= 0 else ("Low Stock" if qty < 10 else "In Stock")
        cw.writerow([p[0], p[1], p[2], f"{p[3]:.2f}", p[4], f"{p[5]:.2f}", status])
        
    output = si.getvalue()
    safe_filename = name.replace(' ', '_').replace('/', '_')
    
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=Supplier_Report_{safe_filename}.csv"}
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
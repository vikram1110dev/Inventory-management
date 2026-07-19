from flask import Flask, render_template, request, redirect, Response, flash
import pyodbc
import csv
from io import StringIO

from db import (
    get_all_products,
    add_product,
    get_product,
    update_product,
    delete_product,
    get_dashboard_stats,
    get_recent_transactions,
    get_all_categories,
    get_all_suppliers
)

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


if __name__ == "__main__":
    app.run(debug=True)
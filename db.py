import pyodbc


def get_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=DESKTOP-P3VAQC9\\SQLEXPRESS;"
        "DATABASE=InventoryManagementDB;"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )


def get_all_products(search_query=None):
    conn = get_connection()
    cursor = conn.cursor()

    if search_query:
        search_term = f"%{search_query}%"
        cursor.execute("""
            SELECT * FROM Products 
            WHERE ProductName LIKE ? OR Category LIKE ? OR Supplier LIKE ?
            ORDER BY ProductId DESC
        """, (search_term, search_term, search_term))
    else:
        cursor.execute("SELECT * FROM Products ORDER BY ProductId DESC")

    rows = cursor.fetchall()
    conn.close()
    return rows


def add_product(product_name, category, price, quantity, supplier, product_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    if product_id and str(product_id).strip():
        cursor.execute("SET IDENTITY_INSERT Products ON")
        cursor.execute("""
            INSERT INTO Products
            (ProductId, ProductName, Category, Price, Quantity, Supplier)
            OUTPUT INSERTED.ProductId
            VALUES (?, ?, ?, ?, ?, ?)
        """, (product_id, product_name, category, price, quantity, supplier))
        inserted_id = cursor.fetchone()[0]
        cursor.execute("SET IDENTITY_INSERT Products OFF")
    else:
        cursor.execute("""
            INSERT INTO Products
            (ProductName, Category, Price, Quantity, Supplier)
            OUTPUT INSERTED.ProductId
            VALUES (?, ?, ?, ?, ?)
        """, (product_name, category, price, quantity, supplier))
        inserted_id = cursor.fetchone()[0]

    cursor.execute("""
        INSERT INTO Transactions (ProductId, TransactionType, QuantityChanged)
        VALUES (?, 'ADD', ?)
    """, (inserted_id, quantity))

    conn.commit()
    conn.close()


def get_product(id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM Products WHERE ProductId=?",
        (id,)
    )

    product = cursor.fetchone()

    conn.close()

    return product


def update_product(id, product_name, category, price, quantity, supplier, new_product_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT Quantity FROM Products WHERE ProductId=?", (id,))
    old_qty_row = cursor.fetchone()
    old_quantity = old_qty_row[0] if old_qty_row else 0
    diff = int(quantity) - int(old_quantity)

    target_id = id
    if new_product_id and str(new_product_id).strip() and int(new_product_id) != int(id):
        target_id = int(new_product_id)
        cursor.execute("SET IDENTITY_INSERT Products ON")
        cursor.execute("""
            INSERT INTO Products
            (ProductId, ProductName, Category, Price, Quantity, Supplier)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (target_id, product_name, category, price, quantity, supplier))
        cursor.execute("SET IDENTITY_INSERT Products OFF")

        # Update child table references
        cursor.execute("UPDATE Transactions SET ProductId=? WHERE ProductId=?", (target_id, id))

        # Delete old product
        cursor.execute("DELETE FROM Products WHERE ProductId=?", (id,))
    else:
        cursor.execute("""
            UPDATE Products
            SET ProductName=?,
                Category=?,
                Price=?,
                Quantity=?,
                Supplier=?
            WHERE ProductId=?
        """, (
            product_name,
            category,
            price,
            quantity,
            supplier,
            id
        ))
    
    if diff != 0:
        cursor.execute("""
            INSERT INTO Transactions (ProductId, TransactionType, QuantityChanged)
            VALUES (?, 'UPDATE', ?)
        """, (target_id, diff))

    conn.commit()
    conn.close()


def delete_product(id):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Delete from child table first
    cursor.execute("DELETE FROM Transactions WHERE ProductId=?", (id,))

    cursor.execute(
        "DELETE FROM Products WHERE ProductId=?",
        (id,)
    )

    conn.commit()
    conn.close()


def get_dashboard_stats():
    conn = get_connection()
    cursor = conn.cursor()
    stats = {}
    
    cursor.execute("SELECT COUNT(*) FROM Products")
    stats['total_products'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(Price * Quantity) FROM Products")
    val = cursor.fetchone()[0]
    stats['total_value'] = float(val) if val else 0.0
    
    cursor.execute("SELECT COUNT(*) FROM Products WHERE Quantity < 10")
    stats['low_stock'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM Products WHERE Quantity = 0")
    stats['out_of_stock'] = cursor.fetchone()[0]
    
    conn.close()
    return stats


def get_recent_transactions():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT TOP 10 t.TransactionId, p.ProductName, t.TransactionType, t.QuantityChanged, t.TransactionDate
        FROM Transactions t
        JOIN Products p ON t.ProductId = p.ProductId
        ORDER BY t.TransactionDate DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_all_transactions(search_query=None):
    conn = get_connection()
    cursor = conn.cursor()
    if search_query:
        search_term = f"%{search_query}%"
        cursor.execute("""
            SELECT t.TransactionId, p.ProductName, t.TransactionType, t.QuantityChanged, t.TransactionDate
            FROM Transactions t
            JOIN Products p ON t.ProductId = p.ProductId
            WHERE p.ProductName LIKE ? OR t.TransactionType LIKE ?
            ORDER BY t.TransactionDate DESC
        """, (search_term, search_term))
    else:
        cursor.execute("""
            SELECT t.TransactionId, p.ProductName, t.TransactionType, t.QuantityChanged, t.TransactionDate
            FROM Transactions t
            JOIN Products p ON t.ProductId = p.ProductId
            ORDER BY t.TransactionDate DESC
        """)
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_all_categories():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT Category, COUNT(ProductId) as ProductCount, SUM(Price * Quantity) as TotalValue
        FROM Products
        GROUP BY Category
        ORDER BY Category
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_all_suppliers():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT Supplier, COUNT(ProductId) as ProductCount, SUM(Price * Quantity) as TotalValue
        FROM Products
        GROUP BY Supplier
        ORDER BY Supplier
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_product_velocity():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.ProductId, p.ProductName, p.Category, p.Quantity, p.Price,
               COALESCE(SUM(t.QuantityChanged), 0) as TotalMovement,
               COUNT(t.TransactionId) as TxCount
        FROM Products p
        LEFT JOIN Transactions t ON p.ProductId = t.ProductId
        GROUP BY p.ProductId, p.ProductName, p.Category, p.Quantity, p.Price
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_supplier_details(supplier_name):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT ProductId, ProductName, Category, Price, Quantity, (Price * Quantity) as TotalValue
        FROM Products
        WHERE Supplier = ?
        ORDER BY Quantity DESC
    """, (supplier_name,))
    products = cursor.fetchall()
    
    cursor.execute("""
        SELECT COUNT(ProductId), SUM(Quantity), SUM(Price * Quantity), AVG(Price)
        FROM Products
        WHERE Supplier = ?
    """, (supplier_name,))
    summary_row = cursor.fetchone()
    
    conn.close()
    
    summary = {
        "supplier_name": supplier_name,
        "total_products": summary_row[0] if summary_row and summary_row[0] else 0,
        "total_quantity": summary_row[1] if summary_row and summary_row[1] else 0,
        "total_value": float(summary_row[2]) if summary_row and summary_row[2] else 0.0,
        "avg_price": float(summary_row[3]) if summary_row and summary_row[3] else 0.0
    }
    return summary, products

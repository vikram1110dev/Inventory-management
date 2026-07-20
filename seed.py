import pyodbc
from db import add_product, get_connection

def seed_database():
    print("Starting to seed database with sample data...")
    
    # 1. Add some products
    products = [
        ("Wireless Mouse M100", "Electronics", 25.99, 150, "TechSupplies Inc."),
        ("Mechanical Keyboard K2", "Electronics", 89.50, 45, "TechSupplies Inc."),
        ("Ergonomic Office Chair", "Furniture", 199.99, 5, "OfficeFurnish"),
        ("Standing Desk Pro", "Furniture", 399.00, 12, "OfficeFurnish"),
        ("USB-C Hub 7-in-1", "Accessories", 34.99, 200, "DongleMakers")
    ]
    
    # Keep track of inserted IDs
    inserted_ids = []
    
    conn = get_connection()
    cursor = conn.cursor()
    
    for p in products:
        # Check if product already exists to avoid duplicates
        cursor.execute("SELECT ProductId FROM Products WHERE ProductName=?", (p[0],))
        row = cursor.fetchone()
        
        if not row:
            print(f"Adding product: {p[0]}")
            # Insert product manually to get ID easily or use the add_product function
            cursor.execute("""
                INSERT INTO Products (ProductName, Category, Price, Quantity, Supplier)
                OUTPUT INSERTED.ProductId
                VALUES (?, ?, ?, ?, ?)
            """, (p[0], p[1], p[2], p[3], p[4]))
            pid = cursor.fetchone()[0]
            inserted_ids.append((pid, p[0]))
            
            # Initial ADD transaction
            cursor.execute("""
                INSERT INTO Transactions (ProductId, TransactionType, QuantityChanged, TransactionDate)
                VALUES (?, 'ADD', ?, DATEADD(day, -30, GETDATE()))
            """, (pid, p[3]))
        else:
            print(f"Product {p[0]} already exists, skipping.")
            inserted_ids.append((row[0], p[0]))
            
    conn.commit()

    # 2. Add some sample transaction history (Sales, Restocks)
    print("Adding sample transaction history...")
    
    transactions = [
        (inserted_ids[0][0], 'SALE', -5, -28),
        (inserted_ids[0][0], 'SALE', -2, -25),
        (inserted_ids[1][0], 'SALE', -1, -20),
        (inserted_ids[2][0], 'SALE', -1, -15),
        (inserted_ids[3][0], 'SALE', -2, -10),
        (inserted_ids[0][0], 'RESTOCK', 50, -5),
        (inserted_ids[2][0], 'SALE', -1, -2),
        (inserted_ids[4][0], 'SALE', -10, -1),
        (inserted_ids[4][0], 'SALE', -5, 0)
    ]
    
    for t in transactions:
        pid, t_type, qty, days_ago = t
        
        # Check if we already have transactions on this day to avoid infinite duplicates on re-runs
        # Actually it's fine for sample data, just insert
        print(f"Adding transaction: {t_type} for Product {pid}, Qty: {qty}")
        cursor.execute(f"""
            INSERT INTO Transactions (ProductId, TransactionType, QuantityChanged, TransactionDate)
            VALUES (?, ?, ?, DATEADD(day, ?, GETDATE()))
        """, (pid, t_type, qty, days_ago))
        
        # Update current quantity in Products table based on the transaction
        cursor.execute("""
            UPDATE Products 
            SET Quantity = Quantity + ? 
            WHERE ProductId = ?
        """, (qty, pid))
        
    conn.commit()
    conn.close()
    
    print("Database seeded successfully!")

if __name__ == "__main__":
    seed_database()

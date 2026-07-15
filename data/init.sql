-- ============================================
-- Dummy Data for AI Analytics Multi-Agent System
-- ============================================

-- Products
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    category VARCHAR(100) NOT NULL,
    price NUMERIC(12, 2) NOT NULL,
    stock_quantity INTEGER NOT NULL DEFAULT 0
);

INSERT INTO products (name, category, price, stock_quantity) VALUES
('MacBook Pro 14"', 'Electronics', 69900.00, 45),
('iPhone 15 Pro', 'Electronics', 48900.00, 120),
('AirPods Pro 2', 'Electronics', 8990.00, 300),
('Samsung Galaxy S24', 'Electronics', 39900.00, 80),
('Dell XPS 15', 'Electronics', 55900.00, 35),
('Office Chair Ergonomic', 'Furniture', 12500.00, 60),
('Standing Desk Electric', 'Furniture', 18900.00, 25),
('Monitor Arm Dual', 'Furniture', 3500.00, 100),
('Mechanical Keyboard TKL', 'Accessories', 4500.00, 200),
('Wireless Mouse Pro', 'Accessories', 2900.00, 250),
('USB-C Hub 10-in-1', 'Accessories', 2200.00, 180),
('Webcam 4K', 'Accessories', 5500.00, 90),
('Noise Cancelling Headphones', 'Audio', 12900.00, 70),
('Bluetooth Speaker', 'Audio', 3900.00, 150),
('Microphone Condenser USB', 'Audio', 6500.00, 55);

-- Customers
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    email VARCHAR(200) UNIQUE NOT NULL,
    segment VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

INSERT INTO customers (name, email, segment, created_at) VALUES
('บริษัท ไทยเทค จำกัด', 'contact@thaitech.co.th', 'Enterprise', '2024-01-15'),
('บริษัท สมาร์ทโซลูชัน จำกัด', 'info@smartsolution.th', 'Enterprise', '2024-02-20'),
('ร้านคอมพิวเตอร์ ดิจิทัล', 'shop@digitalcom.th', 'SMB', '2024-03-10'),
('สำนักงาน กรีนออฟฟิศ', 'admin@greenoffice.th', 'SMB', '2024-03-22'),
('คุณสมชาย ใจดี', 'somchai@gmail.com', 'Consumer', '2024-04-01'),
('คุณสมหญิง รักเรียน', 'somying@gmail.com', 'Consumer', '2024-04-15'),
('บริษัท เมกะคอร์ป จำกัด (มหาชน)', 'procurement@megacorp.co.th', 'Enterprise', '2024-01-05'),
('ห้างหุ้นส่วน โปรไอที', 'sales@proit.th', 'SMB', '2024-05-01'),
('คุณวิชัย นักพัฒนา', 'wichai.dev@outlook.com', 'Consumer', '2024-05-20'),
('คุณอรุณี ครีเอทีฟ', 'arunee.creative@yahoo.com', 'Consumer', '2024-06-10');

-- Sales
CREATE TABLE IF NOT EXISTS sales (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    product_name VARCHAR(200) NOT NULL,
    category VARCHAR(100) NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL,
    total_amount NUMERIC(12, 2) NOT NULL,
    sale_date DATE NOT NULL,
    region VARCHAR(50) NOT NULL
);

INSERT INTO sales (customer_id, product_name, category, quantity, unit_price, total_amount, sale_date, region) VALUES
(1, 'MacBook Pro 14"', 'Electronics', 10, 69900.00, 699000.00, '2024-07-01', 'Bangkok'),
(1, 'AirPods Pro 2', 'Electronics', 20, 8990.00, 179800.00, '2024-07-01', 'Bangkok'),
(2, 'Dell XPS 15', 'Electronics', 5, 55900.00, 279500.00, '2024-07-05', 'Bangkok'),
(7, 'MacBook Pro 14"', 'Electronics', 25, 69900.00, 1747500.00, '2024-07-10', 'Bangkok'),
(7, 'Monitor Arm Dual', 'Furniture', 25, 3500.00, 87500.00, '2024-07-10', 'Bangkok'),
(3, 'iPhone 15 Pro', 'Electronics', 15, 48900.00, 733500.00, '2024-07-12', 'Chiang Mai'),
(3, 'Samsung Galaxy S24', 'Electronics', 10, 39900.00, 399000.00, '2024-07-12', 'Chiang Mai'),
(4, 'Office Chair Ergonomic', 'Furniture', 8, 12500.00, 100000.00, '2024-07-15', 'Phuket'),
(4, 'Standing Desk Electric', 'Furniture', 4, 18900.00, 75600.00, '2024-07-15', 'Phuket'),
(5, 'Mechanical Keyboard TKL', 'Accessories', 1, 4500.00, 4500.00, '2024-07-18', 'Bangkok'),
(5, 'Wireless Mouse Pro', 'Accessories', 1, 2900.00, 2900.00, '2024-07-18', 'Bangkok'),
(6, 'Noise Cancelling Headphones', 'Audio', 1, 12900.00, 12900.00, '2024-07-20', 'Khon Kaen'),
(8, 'Webcam 4K', 'Accessories', 5, 5500.00, 27500.00, '2024-07-22', 'Chiang Mai'),
(8, 'Microphone Condenser USB', 'Audio', 5, 6500.00, 32500.00, '2024-07-22', 'Chiang Mai'),
(9, 'USB-C Hub 10-in-1', 'Accessories', 2, 2200.00, 4400.00, '2024-07-25', 'Bangkok'),
(10, 'Bluetooth Speaker', 'Audio', 1, 3900.00, 3900.00, '2024-07-28', 'Pattaya'),
(1, 'Standing Desk Electric', 'Furniture', 5, 18900.00, 94500.00, '2024-08-02', 'Bangkok'),
(2, 'Noise Cancelling Headphones', 'Audio', 10, 12900.00, 129000.00, '2024-08-05', 'Bangkok'),
(7, 'iPhone 15 Pro', 'Electronics', 50, 48900.00, 2445000.00, '2024-08-10', 'Bangkok'),
(3, 'AirPods Pro 2', 'Electronics', 30, 8990.00, 269700.00, '2024-08-15', 'Chiang Mai'),
(4, 'Mechanical Keyboard TKL', 'Accessories', 10, 4500.00, 45000.00, '2024-08-18', 'Phuket'),
(6, 'MacBook Pro 14"', 'Electronics', 1, 69900.00, 69900.00, '2024-08-20', 'Khon Kaen'),
(9, 'Samsung Galaxy S24', 'Electronics', 1, 39900.00, 39900.00, '2024-08-25', 'Bangkok'),
(10, 'Wireless Mouse Pro', 'Accessories', 2, 2900.00, 5800.00, '2024-08-28', 'Pattaya'),
(5, 'Bluetooth Speaker', 'Audio', 1, 3900.00, 3900.00, '2024-09-01', 'Bangkok');

-- Conversations table (for app)
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id VARCHAR(64) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_thread_id ON conversations(thread_id);

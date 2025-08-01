-- categories table
CREATE TABLE categories (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
);

-- products table
CREATE TABLE products (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    quantity INT NOT NULL DEFAULT 0, 
    unit_type VARCHAR(50) NOT NULL DEFAULT 'pcs'
);

-- packing table
CREATE TABLE packing (
    class_name VARCHAR(100)) NOT NULL, 
    lesson VARCHAR(100)) NOT NULL, 
    packing_list VARCHAR(100)) NOT NULL, 


);

-- category-product table (many to many)
CREATE TABLE product_categories (
    category_id INT NOT NULL,
    product_id INT NOT NULL,
    PRIMARY KEY (category_id, product_id), -- Composite primary key
);

-- category-product table (many to many)
CREATE TABLE packing_lists (
    category_id INT NOT NULL,
    product_id INT NOT NULL,
    PRIMARY KEY (category_id, product_id), -- Composite primary key
);

-- insert sample data into categories & products
INSERT INTO categories (name) VALUES
('Sports'), ('Cooking'), ('Crafts'), ('Science'), ('General');

INSERT INTO products (name, description, quantity, unit_type) VALUES
('Basketball', 'size 7 basketball', 20, 'pcs'),
('Measuring Cups Set', 'Set of 5 stainless steel measuring cups', 50, 'sets'),
('Acrylic Paint Set', 'Set of 12 assorted acrylic paints', 30, 'sets'),
('Microscope Kit', 'Basic science microscope kit', 15, 'kits')

-- sample data for relational table
INSERT INTO product_categories (product_id, category_id) VALUES
((SELECT id FROM products WHERE name = 'Basketball'), (SELECT id FROM categories WHERE name = 'Sports')),
((SELECT id FROM products WHERE name = 'Measuring Cups Set'), (SELECT id FROM categories WHERE name = 'Cooking')),
((SELECT id FROM products WHERE name = 'Acrylic Paint Set'), (SELECT id FROM categories WHERE name = 'Crafts')),
((SELECT id FROM products WHERE name = 'Microscope Kit'), (SELECT id FROM categories WHERE name = 'Science')),
((SELECT id FROM products WHERE name = 'Basketball'), (SELECT id FROM categories WHERE name = 'General'));

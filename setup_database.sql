-- Create the database
CREATE DATABASE IF NOT EXISTS face_security;
USE face_security;

-- Create intruders table
CREATE TABLE IF NOT EXISTS intruders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    date VARCHAR(20),
    time VARCHAR(20),
    image_path VARCHAR(255),
    status VARCHAR(50) DEFAULT 'UNAUTHORIZED',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create authorized_users table
CREATE TABLE IF NOT EXISTS authorized_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    embedding_path VARCHAR(255),
    face_image_path VARCHAR(255),
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

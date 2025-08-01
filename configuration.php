<?php
$servername = "localhost";
$username = "admin";
$password = "PRLug022!";
$dbname = "Your Afterschool Inventory"; 

//create connection
$conn = new mysqli($servername, $username, $password);

// Check connection
if ($conn->connect_error) {
  die("Connection failed: " . $conn->connect_error);
}
echo "Connected successfully";
?>
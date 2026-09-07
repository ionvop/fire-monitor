<?php

if (php_sapi_name() != "cli") {
    echo "Please run this script from the command line.";
    exit(1);
}

chdir(__DIR__);

if (file_exists("../database.db")) {
    $success = unlink("../database.db");

    if ($success == false) {
        echo "Failed to delete database.";
        exit(1);
    }
}

$db = new SQLite3("../database.db");
$query = file_get_contents("schema.sql");

if ($query == false) {
    echo "Failed to read schema.";
    exit(1);
}

$success = $db->exec($query);

if ($success == false) {
    echo "Failed to initialize database.";
    exit (1);
}

echo "Database initialized.";
exit(0);
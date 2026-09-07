<?php

$db = new SQLite3(__DIR__ . "/database.db");

/**
 * Prepares and executes a parameterized SQL query against an SQLite3 database.
 *
 * Uses SQLite3::prepare() with named placeholders and binds each value from
 * $values before executing. This helps prevent SQL injection by avoiding
 * direct string interpolation of user-supplied data into the query.
 *
 * @param SQLite3 $db     The SQLite3 database connection.
 * @param string  $query  SQL query string containing named placeholders
 *                        (e.g. `:email`, `:id`).
 * @param array   $values Associative array mapping each placeholder name
 *                        (including the leading colon) to its bound value,
 *                        e.g. [':email' => $email].
 *
 * @return SQLite3Result|false The result set produced by executing the statement.
 *
 * @throws Exception If the query fails to prepare (e.g. invalid SQL syntax).
 */
function executePreparedQuery(SQLite3 $db, string $query, array $values = []): SQLite3Result | false {
    $stmt = $db->prepare($query);
    
    foreach ($values as $param => $value) {
        $stmt->bindValue($param, $value);
    }
    
    return $stmt->execute();
}
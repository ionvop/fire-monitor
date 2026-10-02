<?php

/**
 * Fire-detection history endpoint.
 *
 * Logs when the controller detects a fire. The Python detection script POSTs
 * a JSON record here on each detection/retraction; the PWA frontend reads the
 * history to render the fire report list.
 *
 * Endpoints:
 *   GET    /api/fire_history/            -> list history (newest first)
 *   GET    /api/fire_history/?id=1       -> get one record
 *   POST   /api/fire_history/            -> insert a record
 *   DELETE /api/fire_history/?id=1       -> delete a record
 *
 * The `timestamp` defaults to the server's current time (UTC) when omitted.
 * `status` defaults to 'detected' and should be 'detected' or 'retracted'.
 * `temperature_c` is the AMG8833 hottest-pixel reading (Celsius) at detection.
 */

require_once "../common.php";
header("Content-Type: application/json");
$data = json_decode(file_get_contents("php://input"), true);

switch ($_SERVER["REQUEST_METHOD"]) {
    case "GET":
        if (isset($_GET["id"])) {
            $record = executePreparedQuery($db, <<<SQL
                SELECT * FROM `fire_history` WHERE `id` = :id
            SQL, [
                ":id" => $_GET["id"]
            ])->fetchArray(SQLITE3_ASSOC);

            if ($record == false) {
                http_response_code(404);
                echo json_encode(["message" => "Record not found."]);
                exit;
            }

            echo json_encode($record);
            exit;
        }

        $result = executePreparedQuery($db, <<<SQL
            SELECT * FROM `fire_history` ORDER BY `id` DESC
        SQL);

        $records = [];

        while ($record = $result->fetchArray(SQLITE3_ASSOC)) {
            $records[] = $record;
        }

        echo json_encode($records);
        exit;
    case "POST":
        // Optional fields; defaults are applied by the schema.
        $timestamp = $data["timestamp"] ?? null;
        $temperature = $data["temperature_c"] ?? null;
        $status = $data["status"] ?? null;

        executePreparedQuery($db, <<<SQL
            INSERT INTO `fire_history`
                (`timestamp`, `temperature_c`, `status`)
            VALUES
                (COALESCE(:timestamp, datetime('now')), :temperature_c,
                 COALESCE(:status, 'detected'))
        SQL, [
            ":timestamp" => $timestamp,
            ":temperature_c" => $temperature,
            ":status" => $status
        ]);

        echo json_encode(["message" => "Record created."]);
        exit;
    case "DELETE":
        if (isset($_GET["id"]) == false) {
            http_response_code(400);
            echo json_encode(["message" => "Missing id."]);
            exit;
        }

        executePreparedQuery($db, <<<SQL
            DELETE FROM `fire_history` WHERE `id` = :id
        SQL, [
            ":id" => $_GET["id"]
        ]);

        echo json_encode(["message" => "Record deleted."]);
        exit;
    default:
        http_response_code(405);
        echo json_encode(["message" => "Method not allowed."]);
        exit;
}

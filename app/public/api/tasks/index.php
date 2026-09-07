<?php

/**
 * InfinityFree hosting limitations and how we work around them:
 *
 * 1. SAME-ORIGIN REQUESTS ONLY
 *    InfinityFree does not send CORS headers, so browsers block cross-origin
 *    requests. To stay within this constraint, the frontend is served from the
 *    SAME host/domain as this API (same-origin), so no CORS preflight is needed.
 *    We therefore do NOT add any CORS headers here — the app must be deployed
 *    on the same InfinityFree domain as this API.
 *
 * 2. ONLY GET AND POST ARE ALLOWED
 *    InfinityFree's web server rejects PUT, PATCH and DELETE requests outright.
 *    To support full CRUD with only GET + POST, we use a "method tunneling"
 *    approach:
 *      - GET  -> used for reading (list all tasks, or a single task by ?id=).
 *      - POST -> used for everything else. The real HTTP verb is carried in a
 *                JSON body field named `_method` (e.g. `_method=PUT` or
 *                `_method=DELETE`), and the server dispatches on that value.
 *
 * The JSON body is read once from php://input into $data, and the outer switch
 * routes on the actual request method while the inner switch routes on the
 * tunneled `_method` value.
 */

require_once "../common.php";
header("Content-Type: application/json");
$data = json_decode(file_get_contents("php://input"), true);

// Outer switch: InfinityFree only lets us receive GET and POST, so we only
// handle those two real HTTP methods here.
switch ($_SERVER["REQUEST_METHOD"]) {
    case "GET":
        if (isset($_GET["id"])) {
            $task = executePreparedQuery($db, <<<SQL
                SELECT * FROM `todos` WHERE `id` = :id
            SQL, [
                ":id" => $_GET["id"]
            ])->fetchArray(SQLITE3_ASSOC);

            if ($task == false) {
                http_response_code(404);
                echo json_encode(["message" => "Task not found."]);
                exit;
            }

            echo json_encode($task);
            exit;
        }

        $result = executePreparedQuery($db, <<<SQL
            SELECT * FROM `todos`
        SQL);

        $tasks = [];

        while ($task = $result->fetchArray(SQLITE3_ASSOC)) {
            $tasks[] = $task;
        }

        echo json_encode($tasks);
        exit;
    case "POST":
        // Inner switch: since PUT/DELETE are blocked by InfinityFree, the real
        // verb is tunneled through the `_method` field in the JSON body.
        switch ($data["_method"]) {
            case "POST":
                executePreparedQuery($db, <<<SQL
                    INSERT INTO `todos` (`task`) VALUES (:task)
                SQL, [
                    ":task" => $data["task"]
                ]);

                echo json_encode(["message" => "Task created."]);
                exit;
            case "PUT":
                // Tunneled update: `_method=PUT` + ?id= identifies the task.
                if (isset($_GET["id"]) == false) {
                    http_response_code(400);
                    echo json_encode(["message" => "Missing id."]);
                    exit;
                }

                if (isset($data["task"])) {
                    executePreparedQuery($db, <<<SQL
                        UPDATE `todos` SET `task` = :task WHERE `id` = :id
                    SQL, [
                        ":task" => $data["task"],
                        ":id" => $_GET["id"]
                    ]);
                }

                if (isset($data["is_completed"])) {
                    executePreparedQuery($db, <<<SQL
                        UPDATE `todos` SET `is_completed` = :is_completed WHERE `id` = :id
                    SQL, [
                        ":is_completed" => $data["is_completed"],
                        ":id" => $_GET["id"]
                    ]);
                }

                echo json_encode(["message" => "Task updated."]);
                exit;
            case "DELETE":
                // Tunneled delete: `_method=DELETE` + ?id= identifies the task.
                if (isset($_GET["id"]) == false) {
                    http_response_code(400);
                    echo json_encode(["message" => "Missing id."]);
                    exit;
                }

                executePreparedQuery($db, <<<SQL
                    DELETE FROM `todos` WHERE `id` = :id
                SQL, [
                    ":id" => $_GET["id"]
                ]);

                echo json_encode(["message" => "Task deleted."]);
                exit;
            default:
                http_response_code(422);
                echo json_encode(["message" => "Method not allowed."]);
                exit;
        }
    default:
        http_response_code(405);
        echo json_encode(["message" => "Method not allowed."]);
        exit;
}
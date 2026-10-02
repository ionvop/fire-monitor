<?php

/**
 * Task (todos) CRUD endpoint.
 *
 * A full CRUD example over the `todos` table demonstrating the API
 * conventions used across this backend.
 *
 * Endpoints:
 *   GET    /api/tasks/            -> list all tasks
 *   GET    /api/tasks/?id=1       -> get one task
 *   POST   /api/tasks/            -> create a task
 *   PUT    /api/tasks/?id=1       -> update a task (partial: `task` and/or `is_completed`)
 *   DELETE /api/tasks/?id=1       -> delete a task
 *
 * The JSON body is read once from php://input into $data and dispatched on the
 * real HTTP verb.
 */

require_once "../common.php";
header("Content-Type: application/json");
$data = json_decode(file_get_contents("php://input"), true);

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
        executePreparedQuery($db, <<<SQL
            INSERT INTO `todos` (`task`) VALUES (:task)
        SQL, [
            ":task" => $data["task"]
        ]);

        echo json_encode(["message" => "Task created."]);
        exit;
    case "PUT":
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
        http_response_code(405);
        echo json_encode(["message" => "Method not allowed."]);
        exit;
}
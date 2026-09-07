<?php

/**
 * PWA push-subscription endpoint.
 *
 * Stores the browser's Web Push subscription (endpoint + p256dh + auth keys)
 * so the server can later send push notifications when a fire is detected.
 *
 * Endpoints (InfinityFree: only GET and POST are allowed):
 *   GET  /api/subscriptions/            -> list all subscriptions
 *   GET  /api/subscriptions/?id=1       -> get one subscription
 *   POST /api/subscriptions/            -> save a subscription (upsert by endpoint)
 *   POST /api/subscriptions/?id=1       -> delete a subscription (_method=DELETE)
 *
 * Saving uses an upsert keyed on the unique `endpoint`, so a PWA that
 * re-subscribes (or whose token rotates) updates the existing row instead of
 * erroring on the UNIQUE constraint.
 */

require_once "../common.php";
header("Content-Type: application/json");
$data = json_decode(file_get_contents("php://input"), true);
$method = $data["_method"] ?? ($_POST["_method"] ?? "POST");

switch ($_SERVER["REQUEST_METHOD"]) {
    case "GET":
        if (isset($_GET["id"])) {
            $sub = executePreparedQuery($db, <<<SQL
                SELECT * FROM `subscriptions` WHERE `id` = :id
            SQL, [
                ":id" => $_GET["id"]
            ])->fetchArray(SQLITE3_ASSOC);

            if ($sub == false) {
                http_response_code(404);
                echo json_encode(["message" => "Subscription not found."]);
                exit;
            }

            echo json_encode($sub);
            exit;
        }

        $result = executePreparedQuery($db, <<<SQL
            SELECT * FROM `subscriptions` ORDER BY `id` DESC
        SQL);

        $subscriptions = [];

        while ($sub = $result->fetchArray(SQLITE3_ASSOC)) {
            $subscriptions[] = $sub;
        }

        echo json_encode($subscriptions);
        exit;
    case "POST":
        switch ($method) {
            case "POST":
                // Validate required push-token fields.
                $endpoint = $data["endpoint"] ?? null;
                $p256dh = $data["p256dh"] ?? null;
                $auth = $data["auth"] ?? null;

                if ($endpoint == null || $p256dh == null || $auth == null) {
                    http_response_code(400);
                    echo json_encode(["message" => "Missing endpoint, p256dh, or auth."]);
                    exit;
                }

                // Upsert keyed on the unique endpoint.
                executePreparedQuery($db, <<<SQL
                    INSERT INTO `subscriptions` (`endpoint`, `p256dh`, `auth`)
                    VALUES (:endpoint, :p256dh, :auth)
                    ON CONFLICT (`endpoint`) DO UPDATE SET
                        `p256dh` = excluded.`p256dh`,
                        `auth` = excluded.`auth`
                SQL, [
                    ":endpoint" => $endpoint,
                    ":p256dh" => $p256dh,
                    ":auth" => $auth
                ]);

                echo json_encode(["message" => "Subscription saved."]);
                exit;
            case "DELETE":
                if (isset($_GET["id"]) == false) {
                    http_response_code(400);
                    echo json_encode(["message" => "Missing id."]);
                    exit;
                }

                executePreparedQuery($db, <<<SQL
                    DELETE FROM `subscriptions` WHERE `id` = :id
                SQL, [
                    ":id" => $_GET["id"]
                ]);

                echo json_encode(["message" => "Subscription deleted."]);
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

The new purpose of this ESP32 server is to simply control the three servos:

- The first servo controls the horizontal movement of the turret.
- The second servo controls the vertical movement of the turret.
- The third servo controls the firing of the turret.

You may modify the endpoints to be more aligned with standard API specifications.

Please keep these functionalities and remove everything else such as:

- The surveillance mode.
- The HTML control panel provided on the root page.
- Things I forgot to mention if any.

If you're wondering about inconsistencies you may find, I recently just removed the code for ESP32-CAM because we're planning on switching to a webcam.
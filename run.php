<?php 

$x_coord = $_GET['x'];
$y_coord = $_GET['y'];

$command = './php_app.py ' . $x_coord . ' ' . $y_coord;
$output = passthru($command);
echo $output;

?>
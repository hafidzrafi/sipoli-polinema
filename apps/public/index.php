<?php

declare(strict_types=1);

/**
 * TEMPORARY front controller - VALENIA-17 frontend smoke test.
 * Will be replaced by the real router (VALENIA-06).
 */

$path = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?: '/';

// Serve real static files (e.g. /assets/app.css); never expose this script
$file = __DIR__ . $path;
if ($path !== '/' && $path !== '/index.php' && is_file($file)) {
    return false;
}

// htmx fragment endpoint - returns an HTML partial, no layout
if ($path === '/greeting') {
    header('Content-Type: text/html; charset=UTF-8');
    echo '<span class="inline-flex items-center gap-1 text-emerald-600">'
        . '<i class="ph ph-check-circle"></i>Halo dari server! - ' . date('H:i:s') . '</span>';
    exit;
}

// Default: render home inside the shared layout
$title = 'VALENIA - Frontend Smoke Test';
ob_start();
require __DIR__ . '/../src/View/home.php';
$content = ob_get_clean();
require __DIR__ . '/../src/View/layouts/app.php';

<?php
/** @var string $title */
/** @var string $content */
?>
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?= htmlspecialchars($title ?? 'VALENIA') ?></title>

    <!-- Tailwind (built locally) -->
    <link rel="stylesheet" href="/assets/app.css">

    <!-- Phosphor Icons -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@phosphor-icons/web@2.1.2/src/regular/style.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@phosphor-icons/web@2.1.2/src/bold/style.css">

    <!-- htmx -->
    <script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/dist/htmx.min.js" defer></script>
</head>
<body class="min-h-screen bg-slate-50 text-slate-800 antialiased">
    <?= $content ?? '' ?>

    <!-- Alpine.js -->
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.17.0/dist/cdn.min.js"></script>
</body>
</html>

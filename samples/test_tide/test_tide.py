from datetime import datetime, timezone
import bisect

# Charger les données des marées
marees = [
    ("2025-01-01 04:21", 5.95, "PM"),
    ("2025-01-01 10:38", 1.45, "BM"),
    ("2025-01-01 16:44", 5.70, "PM"),
    ("2025-01-01 22:56", 1.56, "BM"),
    ("2025-01-02 05:02", 6.01, "PM"),
    ("2025-01-02 11:20", 1.36, "BM"),
    ("2025-01-02 17:23", 5.69, "PM"),
    ("2025-01-02 23:38", 1.52, "BM"),
    ("2025-04-02 05:45", 6.00, "PM"),
    ("2025-04-02 12:02", 1.35, "BM"),
    ("2025-04-02 18:06", 5.62, "PM"),
]

# Convertir les données en objets datetime
marees = [(datetime.strptime(m[0], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc), m[1], m[2]) for m in marees]

# Obtenir la date et l'heure actuelles en UTC
now_datetime = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
now = datetime.now(timezone.utc)
print(f"now = {now}")
print(f"now_datetime = {now_datetime}")

# Extraire uniquement les horaires pour recherche rapide
times = [m[0] for m in marees]

# Trouver l'index où insérer l'heure actuelle
index = bisect.bisect(times, now)

if index == 0:
    print("L'heure actuelle est avant les premières données. Impossible de déterminer la marée.")
elif index == len(marees):
    print("L'heure actuelle est après les dernières données. Impossible de déterminer la marée.")
else:
    prev_maree = marees[index - 1]
    next_maree = marees[index]

    if prev_maree[2] == "BM" and next_maree[2] == "PM":
        print("La marée est montante.")
    elif prev_maree[2] == "PM" and next_maree[2] == "BM":
        print("La marée est descendante.")
    else:
        print("Erreur dans les données des marées.")

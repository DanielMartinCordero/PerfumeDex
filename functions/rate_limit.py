"""Límite de llamadas por usuario para las Cloud Functions.

Lógica pura (sin Firestore ni red): se puede probar sin emulador
(ver test_rate_limit.py). main.py la usa antes de buscar tiendas.

El historial vive en la memoria de cada copia (instancia) de la función, no
en Firestore: así comprobar el límite no cuesta lecturas ni escrituras. La
pega es que cada copia lleva su cuenta, y hay como mucho 3 copias
(max_instances): en el peor caso un usuario consigue el triple de llamadas.
Sigue siendo un tope pequeño y fijo, que es lo que importa.
"""

# Llamadas permitidas por usuario dentro de la ventana de tiempo.
MAX_CALLS = 10

# Tamaño de la ventana, en segundos.
WINDOW_SEC = 60

# Usuarios distintos que se recuerdan como mucho. Al llegar a este número se
# olvidan los que ya no tienen llamadas recientes, para que la memoria no
# crezca sin fin.
MAX_TRACKED_USERS = 5000


def allow_call(history, uid, now, max_calls=MAX_CALLS, window_sec=WINDOW_SEC):
    """Dice si el usuario puede hacer otra llamada ahora, y la apunta.

    history: diccionario {uid: [instantes de sus llamadas recientes]}. Lo
             modifica esta función.
    now:     instante actual en segundos (time.monotonic()).

    Devuelve True si la llamada se permite y False si ha superado el límite.
    Las llamadas rechazadas no se apuntan: quien insiste no alarga su castigo.
    """
    oldest_valid = now - window_sec
    recent = [t for t in history.get(uid, ()) if t > oldest_valid]

    if len(recent) >= max_calls:
        history[uid] = recent
        return False

    recent.append(now)
    history[uid] = recent

    if len(history) > MAX_TRACKED_USERS:
        _forget_idle_users(history, oldest_valid)
    return True


def _forget_idle_users(history, oldest_valid):
    """Borra del historial a los usuarios sin llamadas dentro de la ventana."""
    idle = [
        uid
        for uid, calls in history.items()
        if not calls or calls[-1] <= oldest_valid
    ]
    for uid in idle:
        del history[uid]

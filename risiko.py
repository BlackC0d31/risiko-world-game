#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RISIKO in Python
================
  python risiko.py            -> avvia il gioco (menu: contro il computer / online)
  python risiko.py server     -> avvia il server di gioco (da mettere su un hosting gratuito)

Dipendenze: pip install -r requirements.txt (il server richiede solo websockets>=13)
  La mappa geografica usa il file mappa_risiko.json nella stessa cartella.
  Contro il computer: scegli FACILE / NORMALE / DIFFICILE / ESPERTO dal menu.

Comandi in partita
  Rinforzo : clic sinistro su un tuo territorio = +1 armata, clic destro = tutte le armate rimaste
  Attacco  : clic su un tuo territorio (>=2 armate), poi su un nemico confinante
             clic sinistro = 1 lancio di dadi, clic destro = attacco a oltranza ("blitz")
  Sposta   : tasto "Sposta", poi origine e destinazione (sx = tutte meno una, dx = una sola). Termina il turno.
  Tasti    : S salva | L carica | M effetti on/off | N musica on/off | C colori | H aiuto | Esc menu
"""
import sys, os, json, random, math, time, threading, queue, asyncio
from array import array

try:
    import pygame
except ImportError:          # il server non ha bisogno di pygame
    pygame = None

# ------------------------------------------------------------------ CONFIG
DEFAULT_SERVER = "wss://risiko-world-server.onrender.com"  # server multiplayer RISIKO World
SAVE_MANUAL = "risiko_salvataggio.json"
SAVE_AUTO = "risiko_autosave.json"
CONFIG = "risiko_config.json"
MAP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mappa_risiko.json")
MUSIC_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "colonna_sonora.ogg")
DIFFICULTIES = {
    "facile": ("FACILE", "Mosse semplici, pochi attacchi, rinforzi poco mirati"),
    "normale": ("NORMALE", "Attacca quando è in vantaggio e difende le frontiere"),
    "difficile": ("DIFFICILE", "Pianifica gli attacchi e punta ai bonus continentali"),
    "esperto": ("ESPERTO", "Priorità agli obiettivi, gestione delle armate e contrattacchi"),
}

START_ARMIES = 35
TRADE = [4, 6, 8, 10, 12, 15]
CARD_NAMES = ["Cannone", "Fante", "Cavaliere"]

CONT = {  # bonus armate, colore
    "Nord America": (5, (240, 200, 60)), "Sud America": (2, (240, 130, 50)),
    "Europa": (5, (80, 210, 220)), "Africa": (3, (165, 110, 60)),
    "Asia": (7, (80, 190, 90)), "Oceania": (2, (180, 100, 210)),
}
NA, SA, EU, AF, AS_, OC = CONT.keys()
T = {  # chiave: (nome, continente, x, y)
    "AK": ("Alaska", NA, 70, 90), "NW": ("Terr. Nord-Ovest", NA, 160, 90),
    "GR": ("Groenlandia", NA, 380, 50), "AB": ("Alberta", NA, 150, 150),
    "ON": ("Ontario", NA, 230, 150), "QU": ("Quebec", NA, 310, 150),
    "UW": ("Stati Uniti Occ.", NA, 190, 215), "UE": ("Stati Uniti Or.", NA, 250, 225),
    "AC": ("America Centrale", NA, 273, 291),
    "VE": ("Venezuela", SA, 260, 350), "PE": ("Perù", SA, 250, 420),
    "BR": ("Brasile", SA, 335, 410), "AR": ("Argentina", SA, 275, 500),
    "IS": ("Islanda", EU, 435, 119), "SC": ("Scandinavia", EU, 545, 118),
    "GB": ("Gran Bretagna", EU, 465, 175), "EN": ("Europa Sett.", EU, 525, 185),
    "EW": ("Europa Occ.", EU, 470, 255), "ES": ("Europa Mer.", EU, 560, 243),
    "UC": ("Ucraina", EU, 640, 150),
    "AN": ("Africa del Nord", AF, 490, 345), "EG": ("Egitto", AF, 575, 325),
    "AO": ("Africa Orient.", AF, 610, 405), "CO": ("Congo", AF, 555, 445),
    "AS": ("Africa del Sud", AF, 570, 525), "MA": ("Madagascar", AF, 665, 515),
    "UR": ("Urali", AS_, 745, 130), "SI": ("Siberia", AS_, 800, 85),
    "JA": ("Jacuzia", AS_, 885, 65), "KA": ("Kamchatka", AS_, 975, 95),
    "IR": ("Irkutsk", AS_, 885, 140), "MO": ("Mongolia", AS_, 885, 205),
    "GI": ("Giappone", AS_, 944, 175), "AF": ("Afghanistan", AS_, 725, 220),
    "CI": ("Cina", AS_, 815, 265), "MD": ("Medio Oriente", AS_, 696, 284),
    "IN": ("India", AS_, 775, 304), "SM": ("Siam", AS_, 845, 345),
    "ID": ("Indonesia", OC, 867, 424), "NG": ("Nuova Guinea", OC, 949, 439),
    "OW": ("Austr. Occ.", OC, 885, 525), "OE": ("Austr. Or.", OC, 957, 514),
}
EDGES = """AK-NW AK-AB AK-KA NW-AB NW-ON NW-GR GR-ON GR-QU GR-IS AB-ON AB-UW ON-QU ON-UW ON-UE
QU-UE UW-UE UW-AC UE-AC AC-VE VE-PE VE-BR PE-BR PE-AR BR-AR BR-AN IS-SC IS-GB SC-GB SC-EN SC-UC
GB-EN GB-EW EN-EW EN-ES EN-UC EW-ES EW-AN ES-UC ES-MD ES-EG ES-AN UC-UR UC-AF UC-MD AN-EG AN-AO
AN-CO EG-MD EG-AO AO-CO AO-AS AO-MA AO-MD CO-AS AS-MA UR-SI UR-CI UR-AF SI-JA SI-IR SI-MO SI-CI
JA-IR JA-KA KA-IR KA-MO KA-GI IR-MO MO-GI MO-CI AF-CI AF-IN AF-MD CI-SM CI-IN MD-IN IN-SM SM-ID
ID-NG ID-OW NG-OW NG-OE OW-OE""".split()
EDGES = [tuple(e.split("-")) for e in EDGES]
ADJ = {k: set() for k in T}
for _a, _b in EDGES:
    ADJ[_a].add(_b); ADJ[_b].add(_a)
CT = {c: [k for k in T if T[k][1] == c] for c in CONT}
assert len(T) == 42 and all(a in T and b in T for a, b in EDGES)

GOALS = [
    {"t": "terr", "n": 24, "c": [], "d": "Conquista 24 territori"},
    {"t": "cont", "c": [AS_, SA], "d": "Conquista tutta l'Asia e il Sud America"},
    {"t": "cont", "c": [AS_, AF], "d": "Conquista tutta l'Asia e l'Africa"},
    {"t": "cont", "c": [NA, AF], "d": "Conquista tutto il Nord America e l'Africa"},
    {"t": "cont", "c": [NA, OC], "d": "Conquista tutto il Nord America e l'Oceania"},
    {"t": "cont+", "c": [EU, SA], "d": "Conquista Europa, Sud America e un terzo continente"},
    {"t": "cont+", "c": [EU, OC], "d": "Conquista Europa, Oceania e un terzo continente"},
]

# ------------------------------------------------------------------ MOTORE DI GIOCO (condiviso)
def reinf(s, p):
    n = max(3, sum(1 for k in T if s["owner"][k] == p) // 3)
    for c, ks in CT.items():
        if all(s["owner"][k] == p for k in ks):
            n += CONT[c][0]
    return n

def goal_met(s, p):
    g, ow = s["goals"][p], s["owner"]
    full = [c for c in CT if all(ow[k] == p for k in CT[c])]
    if g["t"] == "terr":
        return sum(1 for k in T if ow[k] == p) >= g["n"]
    ok = all(c in full for c in g["c"])
    return ok and (g["t"] == "cont" or len(full) > len(g["c"]))

def can_trade(s, p):
    cnt = [s["cards"][p].count(i) for i in range(3)]
    return max(cnt) >= 3 or min(cnt) >= 1

def log(s, msg):
    s["log"] = (s["log"] + [msg])[-6:]

class Game:
    def __init__(self, state=None):
        self.s = state or self.new()

    @staticmethod
    def new(names=("Giocatore 1", "Giocatore 2")):
        keys = list(T); random.shuffle(keys)
        owner = {k: i % 2 for i, k in enumerate(keys)}
        armies = {k: 1 for k in T}
        for p in (0, 1):
            mine = [k for k in T if owner[k] == p]
            for _ in range(START_ARMIES - len(mine)):
                armies[random.choice(mine)] += 1
        s = dict(owner=owner, armies=armies, turn=0, phase="reinforce", pool=0,
                 goals=random.sample(GOALS, 2), cards=[[], []], trades=0, conq=False,
                 winner=None, log=["Si comincia! Piazza le tue armate."], names=list(names),
                 turnno=1, seq=0, ev="start", ai_actions=0)
        s["pool"] = reinf(s, 0)
        return s

    def apply(self, a, who):
        s = self.s
        try:
            if s["winner"] is not None:
                return "La partita è finita"
            if who != s["turn"]:
                return "Non è il tuo turno"
            err, ev = self._apply(a, who)
        except (KeyError, ValueError, TypeError, AttributeError):
            return "Azione non valida"
        if err:
            return err
        s["seq"] += 1; s["ev"] = ev
        return None

    def _apply(self, a, p):
        s = self.s; ow, ar = s["owner"], s["armies"]; t = a.get("t")
        if t == "place":
            k = a["a"]
            if s["phase"] != "reinforce" or s["pool"] < 1: return "Non puoi piazzare armate ora", 0
            if k not in T or ow[k] != p: return "Scegli un tuo territorio", 0
            n = max(1, min(int(a.get("n", 1)), s["pool"]))
            ar[k] += n; s["pool"] -= n
            if s["pool"] == 0 and not can_trade(s, p):
                s["phase"] = "attack"; log(s, "Rinforzo finito: fase di attacco.")
            return None, "place"
        if t == "trade":
            if s["phase"] != "reinforce": return "Le carte si cambiano nel rinforzo", 0
            cs = s["cards"][p]; cnt = [cs.count(i) for i in range(3)]
            if max(cnt) >= 3: rem = [cnt.index(max(cnt))] * 3
            elif min(cnt) >= 1: rem = [0, 1, 2]
            else: return "Nessuna combinazione di carte valida", 0
            for r in rem: cs.remove(r)
            i = s["trades"]; s["trades"] += 1
            bonus = TRADE[i] if i < len(TRADE) else 15 + 5 * (i - len(TRADE) + 1)
            s["pool"] += bonus; s["phase"] = "reinforce"
            log(s, f"{s['names'][p]} cambia le carte: +{bonus} armate.")
            return None, "trade"
        if t == "next":
            if s["phase"] != "reinforce": return "Sei già in attacco", 0
            if s["pool"] > 0: return "Piazza prima tutte le armate", 0
            if len(s["cards"][p]) >= 5: return "Hai 5 carte: devi cambiarle", 0
            s["phase"] = "attack"; log(s, "Fase di attacco."); return None, "click"
        if t == "attack":
            return self._attack(p, a["a"], a["b"], bool(a.get("blitz")))
        if t == "fortify":
            x, y = a["a"], a["b"]; n = int(a["n"])
            if s["phase"] != "attack": return "Prima il rinforzo", 0
            if x not in T or y not in T or ow[x] != p or ow[y] != p: return "Scegli due tuoi territori", 0
            if y not in ADJ[x]: return "I territori non confinano", 0
            if n < 1 or n > ar[x] - 1: return "Armate insufficienti", 0
            ar[x] -= n; ar[y] += n
            log(s, f"{s['names'][p]} sposta {n} armate: {T[x][0]} → {T[y][0]}.")
            self._end(p); return None, "end"
        if t == "end":
            if s["phase"] != "attack": return "Termina prima il rinforzo", 0
            self._end(p); return None, "end"
        return "Azione sconosciuta", 0

    def _attack(self, p, a, b, blitz):
        s = self.s; ow, ar = s["owner"], s["armies"]
        if s["phase"] != "attack": return "Non è la fase di attacco", 0
        if a not in T or b not in T or ow[a] != p or ow[b] == p: return "Attacco non valido", 0
        if b not in ADJ[a]: return "I territori non confinano", 0
        if ar[a] < 2: return "Servono almeno 2 armate per attaccare", 0
        LA = LD = 0; ev = "dice"; nm = s["names"][p]
        while True:
            na, nd = min(3, ar[a] - 1), min(3, ar[b])
            ra = sorted((random.randint(1, 6) for _ in range(na)), reverse=True)
            rd = sorted((random.randint(1, 6) for _ in range(nd)), reverse=True)
            la = ld = 0
            for x, y in zip(ra, rd):
                if x > y: ld += 1
                else: la += 1
            ar[a] -= la; ar[b] -= ld; LA += la; LD += ld
            if ar[b] <= 0:
                m = min(na, ar[a] - 1)
                ar[a] -= m; ar[b] = m; ow[b] = p; s["conq"] = True; ev = "conquer"
                break
            if not blitz or ar[a] < 2: break
        if blitz:
            r = "CONQUISTATO" if ev == "conquer" else "respinto"
            log(s, f"{nm}: {T[a][0]} → {T[b][0]} (blitz) perdite -{LA}/-{LD}: {r}")
        else:
            d = lambda v: "-".join(map(str, v))
            log(s, f"{nm}: {T[a][0]} → {T[b][0]}  dadi {d(ra)} vs {d(rd)}  perdite -{LA}/-{LD}"
                   + ("  CONQUISTATO!" if ev == "conquer" else ""))
        if ev == "conquer" and (not any(ow[k] != p for k in T) or goal_met(s, p)):
            s["winner"] = p; ev = "win"
            log(s, f"{nm} HA VINTO!")
        return None, ev

    def _end(self, p):
        s = self.s
        if s["conq"] and s["winner"] is None:
            s["cards"][p].append(random.randint(0, 2))
        s["conq"] = False; s["turn"] = 1 - p; s["phase"] = "reinforce"
        s["turnno"] += 1; s["pool"] = reinf(s, s["turn"]); s["ai_actions"] = 0
        log(s, f"Turno di {s['names'][s['turn']]}: {s['pool']} armate da piazzare.")

# ------------------------------------------------------------------ INTELLIGENZA ARTIFICIALE

def ai_step(g, p, difficulty="normale"):
    """Un'azione AI alla volta, per animarla senza bloccare la finestra.

    I quattro livelli usano lo stesso regolamento e lo stesso generatore dadi.
    Cambiano pianificazione, valutazione del rischio e limiti di attacco.
    """
    if difficulty not in DIFFICULTIES:
        difficulty = "normale"
    s = g.s
    ow, ar = s["owner"], s["armies"]
    mine = [k for k in T if ow[k] == p]
    if not mine:
        return g.apply({"t": "end"}, p) if s["phase"] == "attack" else None

    def enemies(k):
        return [n for n in ADJ[k] if ow[n] != p]

    goal = s["goals"][p]
    goal_cont = set(goal.get("c", []))
    own_counts = {c: sum(ow[x] == p for x in CT[c]) for c in CT}

    def region_value(k):
        c = T[k][1]
        owned, total = own_counts[c], len(CT[c])
        # I continenti vicini al completamento valgono di più.
        finish = 8 if owned == total - 1 else 4 if owned == total - 2 else 0
        strategic = 4 if c in goal_cont else 0
        return CONT[c][0] * (owned / total) + finish + strategic

    def attack_value(a, b):
        diff = ar[a] - ar[b]
        value = diff * 1.0 + region_value(b) * (1.4 if difficulty == "esperto" else 0.9)
        if ar[b] == 1:
            value += 3
        if difficulty == "esperto":
            # Preservare un'armata capace di difendere le proprie frontiere.
            threat = max((ar[e] for e in enemies(a) if e != b), default=0)
            value -= max(0, threat - (ar[a] - ar[b])) * 1.5
            if ar[a] <= ar[b] + 2:
                value -= 5
            # Il bonus di carte è un buon motivo per una conquista sicura.
            if not s["conq"]:
                value += 2
        return value + random.random() * (2 if difficulty == "normale" else 0.4)

    if s["phase"] == "reinforce":
        if can_trade(s, p):
            return g.apply({"t": "trade"}, p)
        if s["pool"] > 0:
            border = [k for k in mine if enemies(k)] or mine
            if difficulty == "facile":
                target = random.choice(border)
                n = min(s["pool"], random.randint(1, 3))
            elif difficulty == "normale":
                target = max(border, key=lambda k: (sum(ar[e] for e in enemies(k)) - ar[k]) +
                             (3 if any(T[e][1] in goal_cont for e in enemies(k)) else 0) +
                             random.random() * 2)
                n = min(s["pool"], 3)
            else:
                def deployment_value(k):
                    es = enemies(k)
                    if not es:
                        return -100
                    best_target = max(es, key=lambda e: region_value(e) + (6 if ar[e] <= 2 else 0))
                    front_threat = max(ar[e] for e in es)
                    attack_ready = max(0, ar[k] - ar[best_target])
                    return (region_value(best_target) * 1.2 + min(front_threat, 8) * 0.7
                            + min(len(es), 4) + (5 if attack_ready >= 0 else 0)
                            - ar[k] * 0.45 + random.random() * 0.8)
                target = max(border, key=deployment_value)
                n = s["pool"]  # accumulare rinforzi in un punto di sfondamento
            return g.apply({"t": "place", "a": target, "n": n}, p)
        return g.apply({"t": "next"}, p)

    actions = s.get("ai_actions", 0)
    max_attacks = {"facile": 3, "normale": 10, "difficile": 18, "esperto": 24}[difficulty]
    candidates = []
    if actions < max_attacks:
        for a in mine:
            if ar[a] < 2:
                continue
            for b in enemies(a):
                gap = ar[a] - ar[b]
                if difficulty == "facile":
                    viable = gap >= 1
                elif difficulty == "normale":
                    viable = gap >= 2
                elif difficulty == "difficile":
                    viable = gap >= 3 or (ar[b] == 1 and ar[a] >= 3)
                else:
                    viable = gap >= 2 or (ar[b] == 1 and ar[a] >= 3)
                if viable:
                    candidates.append((attack_value(a, b), a, b))
    if candidates and (difficulty != "facile" or random.random() < (0.64 if actions == 0 else 0.42)):
        if difficulty == "facile":
            _, a, b = random.choice(candidates)
            blitz = False
        else:
            _, a, b = max(candidates)
            blitz = difficulty != "esperto" or ar[a] >= ar[b] + 3
        s["ai_actions"] = actions + 1
        return g.apply({"t": "attack", "a": a, "b": b, "blitz": blitz}, p)

    # Consolidamento. Muove le armate dalle retrovie a un fronte adiacente.
    options = []
    for a in mine:
        if ar[a] < 2:
            continue
        own_nb = [b for b in ADJ[a] if ow[b] == p]
        for b in own_nb:
            e_b, e_a = enemies(b), enemies(a)
            if not e_b or (difficulty != "facile" and e_a):
                continue
            risk = max((ar[e] for e in e_a), default=0)
            spare = ar[a] - 1
            if risk:
                spare = max(0, ar[a] - max(2, risk))
            if spare <= 0:
                continue
            score = sum(ar[e] for e in e_b) * 0.6 + region_value(b) + spare * 0.4
            score += random.random()
            options.append((score, a, b, spare))
    if options and (difficulty != "facile" or random.random() < 0.25):
        _, a, b, spare = max(options)
        return g.apply({"t": "fortify", "a": a, "b": b, "n": spare}, p)
    return g.apply({"t": "end"}, p)

# ------------------------------------------------------------------ SERVER
def run_server(port):
    from http import HTTPStatus
    from websockets.asyncio.server import serve
    ROOMS = {}

    async def health(conn, req):  # risponde ai controlli HTTP degli hosting
        if req.headers.get("Upgrade", "").lower() != "websocket":
            return conn.respond(HTTPStatus.OK, "Risiko server OK\n")

    async def snd(ws, d):
        try: await ws.send(json.dumps(d))
        except Exception: pass

    async def bcast(code):
        r = ROOMS.get(code)
        if r:
            n = sum(1 for c in r["c"] if c)
            for c in r["c"]:
                if c: await snd(c, {"op": "state", "state": r["g"].s, "peers": n})

    async def handler(ws):
        code = me = None
        try:
            async for raw in ws:
                m = json.loads(raw); op = m.get("op")
                if op == "create":
                    code = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=4))
                    me = 1 if int(m.get("slot", 0)) == 1 else 0
                    ROOMS[code] = {"g": Game(m.get("state")), "c": [None, None]}
                    ROOMS[code]["c"][me] = ws
                elif op == "join":
                    code = str(m.get("room", "")).upper().strip(); r = ROOMS.get(code)
                    if not r: code = None; await snd(ws, {"op": "err", "msg": "Stanza inesistente"}); continue
                    free = [i for i in (0, 1) if r["c"][i] is None]
                    if not free: code = None; await snd(ws, {"op": "err", "msg": "Stanza piena"}); continue
                    me = free[0]; r["c"][me] = ws
                elif op == "act" and code in ROOMS:
                    r = ROOMS[code]
                    if not all(r["c"]):
                        await snd(ws, {"op": "err", "msg": "In attesa dell'avversario"}); continue
                    e = r["g"].apply(m.get("action", {}), me)
                    if e: await snd(ws, {"op": "err", "msg": e}); continue
                    await bcast(code); continue
                else:
                    continue
                if op in ("create", "join"):
                    ROOMS[code]["g"].s["names"][me] = str(m.get("name") or f"Giocatore {me + 1}")[:16]
                    await snd(ws, {"op": "hello", "room": code, "me": me})
                    await bcast(code)
        except Exception:
            pass
        finally:
            r = ROOMS.get(code)
            if r and me is not None and r["c"][me] is ws:
                r["c"][me] = None
                await bcast(code)
                if not any(r["c"]):
                    asyncio.get_running_loop().call_later(3600, lambda: (not any(r["c"])) and ROOMS.pop(code, None))

    async def main():
        async with serve(handler, "0.0.0.0", port, process_request=health):
            print(f"Server Risiko in ascolto sulla porta {port}")
            await asyncio.Future()
    asyncio.run(main())

# ------------------------------------------------------------------ CLIENT
W, H, MAPW, MAPH = 1360, 720, 1060, 620
R = 16
ISL = {"IS": 46, "GB": 52, "MA": 44, "GI": 48, "ID": 48, "NG": 50, "OE": 52, "OW": 58}

def _clip(pts, mx, my, nx, ny):
    out = []
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        dp = (p[0] - mx) * nx + (p[1] - my) * ny; dq = (q[0] - mx) * nx + (q[1] - my) * ny
        if dp >= 0: out.append(p)
        if (dp >= 0) != (dq >= 0):
            u = dp / (dp - dq); out.append((p[0] + u * (q[0] - p[0]), p[1] + u * (q[1] - p[1])))
    return out

def build_polys():
    """Forma dei territori: cellette di Voronoi irregolari attorno ai centri, tagliate sui confini."""
    polys = {}
    for k, (_, _, x, y) in T.items():
        r = ISL.get(k, 74); rnd = random.Random(k); n = 20
        pts = [(x + r * rnd.uniform(0.82, 1.08) * math.cos(2 * math.pi * i / n),
                y + r * rnd.uniform(0.82, 1.08) * math.sin(2 * math.pi * i / n)) for i in range(n)]
        for k2, (_, _, x2, y2) in T.items():
            if k2 != k and (x2 - x) ** 2 + (y2 - y) ** 2 < 170 ** 2:
                pts = _clip(pts, (x + x2) / 2, (y + y2) / 2, x - x2, y - y2)
        polys[k] = [(round(min(max(px, 1), MAPW - 1)), round(min(max(py, 1), MAPH - 1))) for px, py in pts]
    return polys

def inside(pt, poly):
    x, y = pt; c = False
    for i, (x1, y1) in enumerate(poly):
        x2, y2 = poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c

POLY = build_polys()  # fallback se manca il file geografico

def load_geographic_map():
    """Forme costiere reali + territori di Risiko, senza dipendenze geografiche."""
    try:
        with open(MAP_FILE, encoding="utf-8") as f:
            data = json.load(f)["territories"]
        shapes = {k: [[(int(x), int(y)) for x, y in ring]
                      for ring in data[k] if len(ring) >= 3] for k in T}
        if len(shapes) != 42 or any(not v for v in shapes.values()):
            raise ValueError("Mappa incompleta")
        return shapes
    except (OSError, ValueError, KeyError, TypeError):
        return {k: [poly] for k, poly in POLY.items()}

MAP_SHAPES = load_geographic_map()

def map_parts(k):
    return MAP_SHAPES[k]

PCOL = [(45, 120, 255), (235, 60, 60)]
PMONO = [(235, 235, 235), (55, 55, 55)]
OCEAN, OCEAN_MONO = (22, 38, 66), (34, 34, 38)

class Net:
    def __init__(self):
        self.q = queue.Queue(); self.ws = None

    def start(self, url, first):
        threading.Thread(target=self._run, args=(url, first), daemon=True).start()

    def _run(self, url, first):
        try:
            from websockets.sync.client import connect
            self.ws = connect(url, open_timeout=90)
            self.ws.send(json.dumps(first))
            for m in self.ws:
                self.q.put(json.loads(m))
        except Exception as e:
            self.q.put({"op": "closed", "why": str(e)[:80]})
            return
        self.q.put({"op": "closed", "why": "connessione chiusa"})

    def send(self, d):
        try: self.ws.send(json.dumps(d))
        except Exception: self.q.put({"op": "closed", "why": "invio fallito"})

    def close(self):
        try: self.ws.close()
        except Exception: pass

def synth(parts, vol=0.35):
    rate = 22050; buf = array("h")
    for f, ms in parts:
        n = int(rate * ms / 1000)
        for i in range(n):
            env = min(1, i / 200) * (1 - i / n)
            v = random.uniform(-1, 1) if f == 0 else math.sin(2 * math.pi * f * i / rate)
            buf.append(int(32767 * vol * env * v))
    return pygame.mixer.Sound(buffer=buf.tobytes())

def clipboard():
    """Testo degli appunti con fallback per Linux X11/Wayland e Tk.

    Pygame apre una finestra propria e non offre un campo di testo del browser.
    Il metodo precedente usava solo tkinter, che puo' mancare in un venv Kali.
    """
    # Clipboard gestito dalla libreria gia' utilizzata dal gioco.
    try:
        if not pygame.scrap.get_init():
            pygame.scrap.init()
        raw = pygame.scrap.get(pygame.SCRAP_TEXT)
        if raw:
            val = raw.decode('utf-8', errors='replace') if isinstance(raw, bytes) else str(raw)
            val = val.replace('\x00', '').strip()
            if val:
                return val
    except (AttributeError, pygame.error, ValueError, UnicodeError):
        pass

    # Nel caso di Pygame/SDL su X11 o Wayland senza supporto scrap.
    try:
        import subprocess
        for cmd in (("wl-paste", "--no-newline"),
                    ("xclip", "-selection", "clipboard", "-o"),
                    ("xsel", "--clipboard", "--output")):
            try:
                p = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=1, check=False)
                if p.returncode == 0 and p.stdout.strip():
                    return p.stdout.strip()
            except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
                continue
    except ImportError:
        pass

    # Ultima risorsa, se tkinter e' disponibile nell'installazione Python.
    try:
        import tkinter
        r = tkinter.Tk()
        r.withdraw()
        try:
            return r.clipboard_get().strip()
        finally:
            r.destroy()
    except Exception:
        return ""

class App:
    def __init__(self):
        pygame.init()
        self.scr = pygame.display.set_mode((W, H)); pygame.display.set_caption("RISIKO")
        self.clock = pygame.time.Clock()
        f = "dejavusans,arial,helvetica"
        self.f = {n: pygame.font.SysFont(f, n, bold=b) for n, b in
                  [(11, False), (14, False), (16, False), (18, True), (20, True), (28, True), (64, True)]}
        self.cfg = {"url": DEFAULT_SERVER, "sound": True, "colors": True, "name": "Giocatore", "difficulty": "normale", "music": True}
        try: self.cfg.update(json.load(open(CONFIG)))
        except Exception: pass
        # Corregge il segnaposto del server presente nelle versioni precedenti.
        if "INSERISCI-IL-TUO-SERVER" in str(self.cfg.get("url", "")):
            self.cfg["url"] = DEFAULT_SERVER
        self.sounds = {}
        try:
            pygame.mixer.init(22050, -16, 1, 512)
            S = synth
            self.sounds = {"click": S([(700, 40)]), "place": S([(440, 70)]), "dice": S([(0, 160)], .25),
                           "conquer": S([(523, 90), (659, 90), (784, 180)]),
                           "win": S([(523, 130), (659, 130), (784, 130), (1047, 400)]),
                           "lose": S([(392, 220), (330, 220), (262, 450)]),
                           "err": S([(150, 130)], .4), "turn": S([(880, 70), (660, 90)], .25)}
        except Exception:
            self.cfg["sound"] = False
        # La musica viene riprodotta in streaming: non si caricano in RAM
        # gli oltre 11 minuti del brano. Rimane attiva nel menu e in partita.
        self.music_available = False
        self.music_started = False
        self.music_paused = False
        if pygame.mixer.get_init() and os.path.isfile(MUSIC_FILE):
            try:
                pygame.mixer.music.load(MUSIC_FILE)
                pygame.mixer.music.set_volume(0.26)  # volume discreto sotto agli effetti
                self.music_available = True
                if self.cfg.get("music", True):
                    pygame.mixer.music.play(-1, fade_ms=1000)
                    self.music_started = True
            except (pygame.error, OSError):
                self.music_available = False
        self.msg_t = ("", 0); self.maps = {}

    # ---- utilità
    def save_cfg(self):
        try: json.dump(self.cfg, open(CONFIG, "w"))
        except Exception: pass

    def snd(self, n):
        if self.cfg["sound"] and n in self.sounds: self.sounds[n].play()

    def toggle_music(self):
        """N o pulsante Musica: pausa/riprende senza azzerare la posizione."""
        if not self.music_available:
            self.flash("Musica non disponibile: controlla colonna_sonora.ogg")
            return
        enable = not bool(self.cfg.get("music", True))
        try:
            if enable:
                if self.music_started and self.music_paused:
                    pygame.mixer.music.unpause()
                else:
                    pygame.mixer.music.play(-1, fade_ms=700)
                    self.music_started = True
                self.music_paused = False
            elif self.music_started:
                pygame.mixer.music.pause()
                self.music_paused = True
            self.cfg["music"] = enable
            self.save_cfg()  # la scelta resta valida ai successivi avvii
            self.snd("click")
        except pygame.error:
            self.music_available = False
            self.flash("Errore nella riproduzione della musica")

    def flash(self, t, err=True):
        self.msg_t = (t, time.time() + 3)
        if err: self.snd("err")

    def txt(self, s, size, col, pos, center=False, shadow=True):
        fnt = self.f[size]
        if shadow:
            im = fnt.render(s, True, (0, 0, 0)); r = im.get_rect(center=pos) if center else im.get_rect(topleft=pos)
            self.scr.blit(im, r.move(1, 1))
        im = fnt.render(s, True, col); r = im.get_rect(center=pos) if center else im.get_rect(topleft=pos)
        self.scr.blit(im, r)

    def button(self, rect, label, enabled=True, mouse=None):
        hov = enabled and mouse and rect.collidepoint(mouse)
        c = (80, 110, 170) if hov else (50, 70, 115) if enabled else (45, 48, 56)
        pygame.draw.rect(self.scr, c, rect, border_radius=7)
        pygame.draw.rect(self.scr, (130, 150, 200) if enabled else (70, 74, 84), rect, 1, border_radius=7)
        self.txt(label, 16, (255, 255, 255) if enabled else (130, 130, 140), rect.center, True, False)

    def ask(self, prompt, default=""):
        txt = str(default)
        selected = False
        status = ""
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT: pygame.quit(); sys.exit()
                if e.type == pygame.KEYDOWN:
                    ctrl = bool(e.mod & (pygame.KMOD_CTRL | pygame.KMOD_META))
                    if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER): return txt.strip()
                    if e.key == pygame.K_ESCAPE: return None
                    if ctrl and e.key == pygame.K_a:
                        selected = True
                        status = "Testo selezionato: Ctrl+V per sostituirlo"
                    elif ctrl and e.key == pygame.K_v:
                        pasted = clipboard()
                        if pasted:
                            txt = pasted if selected else txt + pasted
                            selected = False
                            status = "Testo incollato"
                        else:
                            status = "Appunti vuoti: prova a installare xclip (sudo apt install xclip)"
                    elif e.key == pygame.K_BACKSPACE:
                        txt = "" if selected else txt[:-1]
                        selected = False
                    elif e.key == pygame.K_DELETE:
                        txt = ""
                        selected = False
                    elif not ctrl and e.unicode and e.unicode.isprintable():
                        txt = e.unicode if selected else txt + e.unicode
                        selected = False
            self.scr.fill(OCEAN)
            self.txt(prompt, 28, (255, 255, 255), (W // 2, 250), True)
            box = pygame.Rect(100, 300, W - 200, 50)
            pygame.draw.rect(self.scr, (15, 25, 45), box, border_radius=8)
            pygame.draw.rect(self.scr, (130, 150, 200), box, 2, border_radius=8)
            shown = txt + ("|" if int(time.time() * 2) % 2 else "")
            self.txt(shown, 20, (255, 235, 140) if selected else (255, 255, 255),
                     (box.x + 12, box.y + 13))
            self.txt("Invio = conferma · Esc = annulla · Ctrl+A = seleziona · Ctrl+V = incolla", 14, (170, 180, 200), (W // 2, 390), True)
            if status:
                self.txt(status, 14, (230, 210, 140), (W // 2, 418), True)
            pygame.display.flip(); self.clock.tick(30)

    # ---- salvataggi
    def save(self, path):
        try:
            d = {"mode": self.mode, "state": self.g.s, "me": self.me, "url": self.url,
                 "difficulty": getattr(self, "difficulty", "normale")}
            json.dump(d, open(path + ".tmp", "w")); os.replace(path + ".tmp", path)
            return True
        except Exception:
            return False

    @staticmethod
    def load(path):
        try: return json.load(open(path))
        except Exception: return None

    # ---- menu
    def menu(self):
        while True:
            items = [("Gioca contro il computer", "ai", True),
                     ("Online: crea una stanza", "create", True),
                     ("Online: entra in una stanza (codice)", "join", True),
                     ("Riprendi l'ultima partita (autosalvataggio)", "auto", os.path.exists(SAVE_AUTO)),
                     ("Carica il salvataggio manuale", "manual", os.path.exists(SAVE_MANUAL)),
                     (f"Effetti: {'ON' if self.cfg['sound'] else 'OFF'}", "snd", True),
                     (f"Musica: {'ON' if self.cfg.get('music', True) else 'OFF'}" if self.music_available
                      else "Musica: non disponibile", "music", self.music_available),
                     (f"Colori: {'ON' if self.cfg['colors'] else 'OFF'}", "col", True),
                     ("Esci", "quit", True)]
            mouse = pygame.mouse.get_pos()
            rects = [pygame.Rect(W // 2 - 220, 190 + i * 55, 440, 46) for i in range(len(items))]
            for e in pygame.event.get():
                if e.type == pygame.QUIT: return "quit"
                if e.type == pygame.KEYDOWN and e.key == pygame.K_n:
                    self.toggle_music()
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    for r, (_, k, en) in zip(rects, items):
                        if en and r.collidepoint(e.pos):
                            self.snd("click")
                            if k == "snd": self.cfg["sound"] = not self.cfg["sound"] and bool(self.sounds); self.save_cfg()
                            elif k == "music": self.toggle_music()
                            elif k == "col": self.cfg["colors"] = not self.cfg["colors"]; self.save_cfg()
                            else: return k
            self.scr.fill(OCEAN if self.cfg["colors"] else OCEAN_MONO)
            self.txt("RISIKO", 64, (240, 200, 60) if self.cfg["colors"] else (230, 230, 230), (W // 2, 90), True)
            self.txt("La conquista del mondo in Python", 18, (190, 200, 220), (W // 2, 145), True)
            for r, (lab, k, en) in zip(rects, items): self.button(r, lab, en, mouse)
            pygame.display.flip(); self.clock.tick(30)

    def choose_difficulty(self):
        """Schermata dedicata: non sovraccarica il menu principale."""
        levels = list(DIFFICULTIES.items())
        rects = [pygame.Rect(W // 2 - 295, 208 + i * 92, 590, 78)
                 for i in range(len(levels))]
        back = pygame.Rect(W // 2 - 160, 617, 320, 44)
        while True:
            mouse = pygame.mouse.get_pos()
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    return None
                if e.type == pygame.KEYDOWN and e.key == pygame.K_n:
                    self.toggle_music()
                if e.type == pygame.KEYDOWN and pygame.K_1 <= e.key <= pygame.K_4:
                    level = levels[e.key - pygame.K_1][0]
                    self.cfg["difficulty"] = level; self.save_cfg()
                    return level
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    if back.collidepoint(e.pos):
                        return None
                    for r, (level, _) in zip(rects, levels):
                        if r.collidepoint(e.pos):
                            self.snd("click")
                            self.cfg["difficulty"] = level; self.save_cfg()
                            return level
            self.scr.fill(OCEAN if self.cfg["colors"] else OCEAN_MONO)
            self.txt("SCEGLI LA DIFFICOLTÀ", 28, (243, 208, 105), (W // 2, 82), True)
            self.txt("Affronta il computer: regole e dadi identici a ogni livello", 18,
                     (185, 202, 226), (W // 2, 137), True)
            for i, (r, (level, (title, description))) in enumerate(zip(rects, levels)):
                hov = r.collidepoint(mouse)
                selected = level == self.cfg.get("difficulty")
                pygame.draw.rect(self.scr, (62, 87, 133) if hov else (32, 48, 77), r, border_radius=12)
                pygame.draw.rect(self.scr, (239, 201, 94) if selected else (115, 139, 178),
                                 r, 2 if selected else 1, border_radius=12)
                self.txt(f"{i + 1}.  {title}", 20, (255, 255, 255), (r.x + 22, r.y + 12))
                self.txt(description, 14, (199, 212, 234), (r.x + 22, r.y + 48))
                if selected: self.txt("SCELTO", 14, (244, 218, 132), (r.right - 98, r.y + 16))
            self.button(back, "Indietro (Esc)", True, mouse)
            pygame.display.flip(); self.clock.tick(30)

    def run(self):
        while True:
            k = self.menu()
            if k == "quit": break
            if k == "ai":
                level = self.choose_difficulty()
                if level:
                    self.play("ai", Game(Game.new(("Tu", "Computer"))), 0, None, None,
                              difficulty=level)
            elif k in ("create", "join"):
                url = self.ask("Indirizzo del server (wss://...)", self.cfg["url"])
                if not url: continue
                if "://" not in url: url = ("ws://" if url.startswith(("localhost", "127.")) else "wss://") + url
                nm = self.ask("Il tuo nome", self.cfg["name"])
                if nm is None: continue
                self.cfg.update(url=url, name=nm or "Giocatore"); self.save_cfg()
                if k == "create":
                    first = {"op": "create", "name": self.cfg["name"], "state": None, "slot": 0}
                else:
                    code = self.ask("Codice della stanza")
                    if not code: continue
                    first = {"op": "join", "room": code, "name": self.cfg["name"]}
                net = Net(); net.start(url, first)
                self.play("online", None, 0, net, url)
            elif k in ("auto", "manual"):
                d = self.load(SAVE_AUTO if k == "auto" else SAVE_MANUAL)
                if not d: self.flash("Salvataggio non leggibile"); continue
                if d["mode"] == "ai":
                    self.play("ai", Game(d["state"]), 0, None, None,
                               difficulty=d.get("difficulty", "normale"))
                else:
                    url = self.ask("Server per riprendere la partita online", d.get("url") or self.cfg["url"])
                    if not url: continue
                    if "://" not in url: url = "wss://" + url
                    net = Net()
                    net.start(url, {"op": "create", "name": self.cfg["name"], "state": d["state"], "slot": d["me"]})
                    self.play("online", None, d["me"], net, url)
        pygame.quit()

    # ---- partita
    def play(self, mode, g, me, net, url, difficulty="normale"):
        self.mode, self.g, self.me, self.net, self.url = mode, g, me, net, url
        self.difficulty = difficulty if difficulty in DIFFICULTIES else "normale"
        self.sel = None; self.fort = False; self.room = None; self.peers = 1 if mode == "online" else 2
        self.help = False; self.lastseq = g.s["seq"] if g else -1
        last_ai = 0
        if g: self.msg_t = ("Partita pronta" if g.s["seq"] else "Si comincia!", time.time() + 2)
        while True:
            now = time.time()
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.leave(); pygame.quit(); sys.exit()
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE: self.leave(); return
                    if e.key == pygame.K_h: self.help = not self.help
                    if e.key == pygame.K_m: self.do("snd")
                    if e.key == pygame.K_n: self.do("music")
                    if e.key == pygame.K_c: self.do("col")
                    if e.key == pygame.K_s: self.do("save")
                    if e.key == pygame.K_l: self.do("load")
                if e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 3) and self.g:
                    if self.click(e.pos, e.button) == "menu": self.leave(); return
            if net:
                while not net.q.empty():
                    m = net.q.get_nowait(); op = m["op"]
                    if op == "hello": self.room, self.me = m["room"], m["me"]
                    elif op == "state":
                        if self.g: self.g.s = m["state"]
                        else: self.g = Game(m["state"])
                        self.peers = m["peers"]; self.on_state()
                    elif op == "err": self.flash(m["msg"])
                    elif op == "closed":
                        if self.g: self.save(SAVE_AUTO)
                        self.leave(); self.flash("Connessione persa: " + m.get("why", ""))
                        return
            g = self.g
            if mode == "ai" and g.s["winner"] is None and g.s["turn"] == 1 and now - last_ai > (0.32 if self.difficulty == "esperto" else 0.4):
                last_ai = now; ai_step(g, 1, self.difficulty); self.on_state()
            self.draw()
            pygame.display.flip(); self.clock.tick(60)

    def leave(self):
        if self.g: self.save(SAVE_AUTO) if self.g.s["winner"] is None else None
        if self.net: self.net.close()

    def on_state(self):
        s = self.g.s
        if s["seq"] != self.lastseq:
            self.lastseq = s["seq"]; ev = s["ev"]
            if s["winner"] is not None: self.snd("win" if s["winner"] == self.me else "lose")
            elif ev == "end": self.snd("turn" if s["turn"] == self.me else "click")
            elif ev in ("place", "dice", "conquer"): self.snd(ev)
            elif ev == "trade": self.snd("conquer")
            elif ev == "click": self.snd("click")
        if self.sel and (s["owner"][self.sel] != self.me or s["turn"] != self.me or
                         (not self.fort and s["armies"][self.sel] < 2)):
            self.sel = None
        if s["turn"] != self.me or s["phase"] != "attack": self.fort = False; self.sel = None
        if s["winner"] is not None:
            try: os.remove(SAVE_AUTO)
            except OSError: pass
        else: self.save(SAVE_AUTO)

    def act(self, a):
        if self.mode == "ai":
            e = self.g.apply(a, 0)
            if e: self.flash(e)
            else: self.on_state()
        else:
            self.net.send({"op": "act", "action": a})

    def hit(self, pos):
        for k, (_, _, x, y) in T.items():
            if (pos[0] - x) ** 2 + (pos[1] - y) ** 2 <= (R + 4) ** 2: return k
        if pos[0] < MAPW and pos[1] < MAPH:
            for k, parts in MAP_SHAPES.items():
                if any(inside(pos, ring) for ring in parts): return k

    def buttons(self):
        s = self.g.s; mine = s["turn"] == self.me and s["winner"] is None
        ph = s["phase"]
        labels = [("Cambia carte", "trade", mine and ph == "reinforce" and can_trade(s, self.me)),
                  ("Vai all'attacco" if ph == "reinforce" else ("Sposta: SI" if self.fort else "Sposta"),
                   "next" if ph == "reinforce" else "fort", mine and (ph == "attack" or s["pool"] == 0)),
                  ("Fine turno", "end", mine and ph == "attack"), ("Menu", "menu", True),
                  ("Salva", "save", True), ("Carica", "load", self.mode == "ai"),
                  (f"Effetti: {'ON' if self.cfg['sound'] else 'OFF'}", "snd", True),
                  (f"Musica: {'ON' if self.cfg.get('music', True) else 'OFF'}" if self.music_available
                   else "Musica assente", "music", self.music_available),
                  (f"Colori: {'ON' if self.cfg['colors'] else 'OFF'}", "col", True)]
        return [(l, pygame.Rect(372 + (i % 5) * 136, 632 + (i // 5) * 44, 132, 38), k, en)
                for i, (l, k, en) in enumerate(labels)]

    def do(self, k):
        if k == "snd": self.cfg["sound"] = not self.cfg["sound"] and bool(self.sounds); self.save_cfg(); self.snd("click")
        elif k == "music": self.toggle_music()
        elif k == "col": self.cfg["colors"] = not self.cfg["colors"]; self.save_cfg()
        elif k == "save" and self.g:
            self.flash("Partita salvata" if self.save(SAVE_MANUAL) else "Salvataggio fallito", False)
            self.snd("click")
        elif k == "load":
            if self.mode != "ai": self.flash("Caricamento disponibile solo contro il computer"); return
            d = self.load(SAVE_MANUAL)
            if d and d["mode"] == "ai":
                self.g.s = d["state"]; self.difficulty = d.get("difficulty", "normale"); self.sel = None; self.fort = False; self.lastseq = self.g.s["seq"]
                self.flash("Partita caricata", False)
            else: self.flash("Nessun salvataggio manuale di una partita contro il computer")
        elif k == "menu": return "menu"
        elif k == "fort": self.fort = not self.fort; self.sel = None; self.snd("click")
        elif k in ("trade", "next", "end"): self.act({"t": k})

    def click(self, pos, btn):
        for _, rect, k, en in self.buttons():
            if rect.collidepoint(pos):
                return self.do(k) if en else None
        k = self.hit(pos)
        if not k: return
        s = self.g.s; ow, ar = s["owner"], s["armies"]
        if s["winner"] is not None: return
        if s["turn"] != self.me: return self.flash("Non è il tuo turno")
        if self.peers < 2: return self.flash("In attesa dell'avversario")
        own = ow[k] == self.me
        if s["phase"] == "reinforce":
            if own: self.act({"t": "place", "a": k, "n": 1 if btn == 1 else s["pool"]})
            else: self.flash("Rinforza un tuo territorio")
        elif self.fort:
            if self.sel is None:
                if own and ar[k] > 1: self.sel = k
                else: self.flash("Scegli un tuo territorio con almeno 2 armate")
            elif k == self.sel: self.sel = None
            elif own: self.act({"t": "fortify", "a": self.sel, "b": k, "n": ar[self.sel] - 1 if btn == 1 else 1})
        else:
            if own:
                if ar[k] > 1: self.sel = k
                else: self.flash("Servono almeno 2 armate")
            elif self.sel: self.act({"t": "attack", "a": self.sel, "b": k, "blitz": btn == 3})
            else: self.flash("Seleziona prima un tuo territorio")

    # ---- disegno
    def wrap(self, text, size, width):
        lines, cur = [], ""
        for w in text.split():
            t = (cur + " " + w).strip()
            if self.f[size].size(t)[0] <= width: cur = t
            else: lines.append(cur); cur = w
        return lines + [cur] if cur else lines

    def para(self, text, size, col, x, y, width, gap=2):
        for l in self.wrap(text, size, width):
            self.txt(l, size, col, (x, y), shadow=False); y += self.f[size].get_height() + gap
        return y

    def basemap(self, col):
        """Mappa continentale vettoriale: coste geografiche e confini di gioco."""
        if col in self.maps:
            return self.maps[col]
        sf = pygame.Surface((MAPW, MAPH))
        sf.fill((24, 53, 74) if col else OCEAN_MONO)
        grid = (37, 67, 86) if col else (48, 48, 53)
        for x in range(30, MAPW, 62):
            pygame.draw.line(sf, grid, (x, 0), (x, MAPH), 1)
        for y in range(27, MAPH, 62):
            pygame.draw.line(sf, grid, (0, y), (MAPW, y), 1)
        # Piccole coordinate e mare a tinte fredde per un'estetica cartografica.
        for y, label in [(35, "60° N"), (310, "EQUATORE"), (575, "40° S")]:
            pygame.draw.line(sf, (47, 83, 98) if col else grid, (0, y), (MAPW, y), 1)
            fnt = self.f[11]
            sf.blit(fnt.render(label, True, (90, 133, 151) if col else (105, 105, 110)), (8, y + 4))
        # Le rotte marittime restano visibili sopra il mare, sotto le terre.
        route = (104, 178, 194) if col else (112, 112, 120)
        def dashed(p0, p1, dash=9, gap=6):
            dx, dy = p1[0] - p0[0], p1[1] - p0[1]
            dist = math.hypot(dx, dy)
            if dist < 1:
                return
            ux, uy = dx / dist, dy / dist
            step = 0
            while step < dist:
                stop = min(dist, step + dash)
                pygame.draw.line(sf, route, (int(p0[0] + ux * step), int(p0[1] + uy * step)),
                                 (int(p0[0] + ux * stop), int(p0[1] + uy * stop)), 2)
                step += dash + gap
        for a, b in EDGES:
            if {a, b} == {"AK", "KA"}:
                dashed(T["AK"][2:], (0, 95))
                dashed(T["KA"][2:], (MAPW, 95))
            else:
                dashed(T[a][2:], T[b][2:])
        # Le terre non sono più cellette casuali: sono le sagome del planisfero.
        for i, (k, parts) in enumerate(MAP_SHAPES.items()):
            if col:
                rgb = CONT[T[k][1]][1]
                var = (-10, 0, 9, 17)[i % 4]
                fill = tuple(max(0, min(255, n + var)) for n in rgb)
                border = (31, 49, 60)
            else:
                v = 94 + list(CONT).index(T[k][1]) * 20 + (i % 3) * 6
                fill, border = (v, v, v), (39, 39, 44)
            for ring in parts:
                if len(ring) < 3: continue
                pygame.draw.polygon(sf, fill, ring)
                pygame.draw.polygon(sf, border, ring, 2 if len(ring) > 8 else 1)
        self.maps[col] = sf
        return sf

    def draw(self):
        sc, col = self.scr, self.cfg["colors"]
        sc.fill((16, 24, 40))
        if not self.g:
            self.txt("Connessione al server in corso...", 28, (255, 255, 255), (W // 2, 300), True)
            self.txt("I server gratuiti possono impiegare fino a 1 minuto a svegliarsi.", 16, (190, 200, 220), (W // 2, 345), True)
            self.txt("Esc = annulla", 16, (190, 200, 220), (W // 2, 380), True); return
        s = self.g.s; ow, ar = s["owner"], s["armies"]
        sc.blit(self.basemap(col), (0, 0))
        pc = PCOL if col else PMONO
        hl = {}
        if self.sel and not self.fort: hl = {n: (255, 235, 70) for n in ADJ[self.sel] if ow[n] != self.me}
        if self.sel and self.fort: hl = {n: (110, 255, 140) for n in ADJ[self.sel] if ow[n] == self.me}
        for k, c in hl.items():
            for ring in map_parts(k):
                pygame.draw.polygon(sc, c, ring, 3)
        if self.sel:
            for ring in map_parts(self.sel):
                pygame.draw.polygon(sc, (255, 255, 255), ring, 4)
        hover = self.hit(pygame.mouse.get_pos())
        for k, (name, cont, x, y) in T.items():
            c = pc[ow[k]]
            pygame.draw.circle(sc, (10, 10, 14), (x, y), R + 2); pygame.draw.circle(sc, c, (x, y), R)
            tc = (0, 0, 0) if sum(c) > 380 else (255, 255, 255)
            im = self.f[16].render(str(ar[k]), True, tc); sc.blit(im, im.get_rect(center=(x, y)))
            self.txt(name if k == hover else k, 11, (255, 255, 255),
                     (x, y + R + 9), True)
        # pannello inferiore
        pygame.draw.rect(sc, (14, 20, 34), (0, MAPH, MAPW, H - MAPH))
        pygame.draw.line(sc, (90, 110, 160), (0, MAPH), (MAPW, MAPH), 2)
        p = s["turn"]; ph = "RINFORZO" if s["phase"] == "reinforce" else ("SPOSTAMENTO" if self.fort else "ATTACCO")
        pygame.draw.circle(sc, pc[p], (22, MAPH + 22), 9)
        self.txt(f"Turno {s['turnno']} · {s['names'][p]} · {ph}", 20, (255, 255, 255), (38, MAPH + 11))
        if s["phase"] == "reinforce": self.txt(f"Armate da piazzare: {s['pool']}", 16, (240, 210, 120), (38, MAPH + 40))
        y = MAPH + 62
        for l in self.wrap(s["log"][-1], 14, 350)[:2]:
            self.txt(l, 14, (230, 235, 245), (14, y), shadow=False); y += 17
        mouse = pygame.mouse.get_pos()
        for lab, rect, k, en in self.buttons(): self.button(rect, lab, en, mouse)
        self.draw_guide()
        if hover:
            name, cont = T[hover][:2]
            self.txt(f"{name}  ·  {cont}  ·  {ar[hover]} armate", 14,
                     (255, 255, 255), (12, 8), shadow=False)
        if self.room: self.txt(f"Stanza: {self.room}", 20, (255, 255, 255), (MAPW - 170, 8))
        if time.time() < self.msg_t[1]:
            self.txt(self.msg_t[0], 20, (255, 170, 60), (MAPW // 2, 40), True)
        if self.mode == "online" and self.peers < 2 and s["winner"] is None:
            self.overlay(["In attesa dell'avversario...", f"Codice stanza: {self.room or '...'}",
                          "Comunicalo all'altro giocatore (menu → Online → entra)"])
        if s["winner"] is not None:
            w = s["winner"]
            self.overlay([("HAI VINTO!" if w == self.me else "HAI PERSO!") + f"  ({s['names'][w]})", "Esc per tornare al menu"])
        if self.help:
            self.overlay(["REGOLE RAPIDE", "1) Rinforzo: piazza le armate sui tuoi territori (+ carte).",
                          "2) Attacco: 3 dadi max per lato, vince il più alto, parità al difensore.",
                          "3) Se conquisti almeno un territorio ricevi una carta a fine turno.",
                          "4) Sposta: un solo spostamento tra territori confinanti, poi il turno passa.",
                          "5) Vince chi completa il proprio obiettivo o elimina l'avversario.",
                          "4 livelli AI nel menu: Facile, Normale, Difficile, Esperto.",
                           "S salva · L carica · M effetti · N musica · C colori · H chiudi · Esc menu"])

    def instructions(self):
        s = self.g.s; me = self.me; ar = s["armies"]
        if s["winner"] is not None: return ["Partita finita. Premi Esc per tornare al menu."]
        if self.mode == "online" and self.peers < 2: return ["Attendi che l'avversario entri con il codice stanza."]
        if s["turn"] != me: return [f"Tocca a {s['names'][s['turn']]}: attendi la sua mossa."]
        if s["phase"] == "reinforce":
            L = []
            if s["pool"] > 0:
                L += [f"Hai {s['pool']} armate da piazzare.", "Clic sinistro su un TUO territorio: +1 armata.",
                      "Clic destro: piazza tutte le armate rimaste."]
            if can_trade(s, me):
                L.append("Hai un tris di carte: «Cambia carte» dà armate extra" +
                         (" (obbligatorio con 5 carte)." if len(s["cards"][me]) >= 5 else "."))
            if s["pool"] == 0: L.append("Rinforzo finito: premi «Vai all'attacco».")
            return L
        if self.fort:
            if self.sel is None:
                return ["Clic sul tuo territorio di partenza (2+ armate).", "Poi su un tuo territorio confinante (bordo verde).",
                        "Sx = tutte meno una · Dx = una sola.", "Dopo lo spostamento il turno termina."]
            return [f"Partenza: {T[self.sel][0]} ({ar[self.sel]} armate).", "Scegli la destinazione (bordo verde).",
                    "Sx = tutte meno una · Dx = una sola."]
        if self.sel:
            return [f"Origine: {T[self.sel][0]} ({ar[self.sel]} armate).", "Clic su un nemico con bordo giallo per attaccare.",
                    "Sx = 1 lancio · Dx = blitz fino alla conquista.", "Clic su un altro tuo territorio per cambiare origine."]
        return ["Clic su un tuo territorio con almeno 2 armate.", "Poi su un nemico confinante (bordo giallo).",
                "Sx = 1 lancio di dadi · Dx = blitz.", "Conquistando almeno un territorio ricevi una carta.",
                "Hai finito? «Sposta» (opzionale) oppure «Fine turno»."]

    def draw_guide(self):
        sc, s = self.scr, self.g.s; X = MAPW + 14; Wd = W - MAPW - 28
        pc = PCOL if self.cfg["colors"] else PMONO
        pygame.draw.rect(sc, (16, 24, 40), (MAPW, 0, W - MAPW, H))
        pygame.draw.line(sc, (90, 110, 160), (MAPW, 0), (MAPW, H), 2)
        self.txt("GUIDA ALLE MOSSE", 20, (240, 200, 60), (X, 10))
        if self.mode == "ai":
            self.txt("AI: " + DIFFICULTIES[self.difficulty][0], 14,
                     (120, 221, 238), (X + 163, 37), shadow=False)
        cur = -1
        if s["turn"] == self.me and s["winner"] is None: cur = 0 if s["phase"] == "reinforce" else (2 if self.fort else 1)
        y = 62 if self.mode == "ai" else 42
        for i, t in enumerate(["1  Rinforzo: piazza le armate", "2  Attacco: conquista territori", "3  Sposta / Fine turno"]):
            if i == cur: pygame.draw.rect(sc, (50, 80, 140), (X - 6, y - 3, Wd + 12, 22), border_radius=5)
            self.txt(t, 14, (255, 255, 255) if i == cur else (150, 160, 180), (X, y), shadow=False); y += 24
        y += 8
        self.txt("Cosa fare ora", 18, (255, 255, 255), (X, y)); y += 26
        for line in self.instructions():
            self.txt("•", 14, (120, 200, 255), (X, y), shadow=False)
            y = self.para(line, 14, (210, 220, 240), X + 14, y, Wd - 14) + 3
        y += 8
        self.txt("Il tuo obiettivo", 18, (240, 200, 60), (X, y)); y += 24
        y = self.para(s["goals"][self.me]["d"], 14, (235, 235, 245), X, y, Wd) + 4
        cs = s["cards"][self.me]
        cards = ", ".join(f"{cs.count(i)} {CARD_NAMES[i]}" for i in range(3) if i in cs) or "nessuna"
        y = self.para("Carte: " + cards, 14, (200, 210, 230), X, y, Wd) + 2
        nt = [sum(1 for k in T if s["owner"][k] == q) for q in (0, 1)]
        for q in (0, 1):
            pygame.draw.circle(sc, pc[q], (X + 7 + q * 140, y + 8), 7)
            self.txt(f"{s['names'][q][:9]}: {nt[q]}", 14, (220, 225, 240), (X + 20 + q * 140, y), shadow=False)
        y += 30
        self.txt("Continenti (bonus armate)", 16, (255, 255, 255), (X, y)); y += 22
        for c, (b, cc) in CONT.items():
            pygame.draw.rect(sc, cc if self.cfg["colors"] else (150, 150, 150), (X, y + 2, 14, 12), border_radius=3)
            self.txt(c, 14, (210, 220, 240), (X + 22, y), shadow=False)
            self.txt(f"+{b}", 14, (240, 210, 120), (X + Wd - 24, y), shadow=False); y += 18
        y += 8
        self.txt("Ultime mosse", 16, (255, 255, 255), (X, y)); y += 22
        for i, m in enumerate(reversed(s["log"])):
            if y > H - 20: break
            y = self.para(m, 12 if False else 14, (235, 240, 250) if i == 0 else (140, 150, 170), X, y, Wd, 1) + 3

    def overlay(self, lines):
        sh = pygame.Surface((MAPW, MAPH), pygame.SRCALPHA); sh.fill((0, 0, 0, 170)); self.scr.blit(sh, (0, 0))
        y = MAPH // 2 - 17 * len(lines)
        for i, l in enumerate(lines):
            self.txt(l, 28 if i == 0 else 18, (255, 255, 255), (MAPW // 2, y + i * 34), True)

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "server":
        port = int(os.environ.get("PORT", sys.argv[2] if len(sys.argv) > 2 else 8765))
        return run_server(port)
    if pygame is None:
        sys.exit("Installa le dipendenze:  pip install pygame websockets")
    App().run()

if __name__ == "__main__":
    main()

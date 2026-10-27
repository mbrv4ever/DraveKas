# -*- coding: utf-8 -*-
# DraveKas - Copyright (C) 2026 Dravenlock (Roger & Claudio).
"""kas_data.py - het huishoudboekje zelf: posten, vaste lasten en spaardoelen, en het uitwisselen tussen pc en telefoon.

Gedeeld door de pc-app en de telefoon-app (alleen standaard-Python, geen extra pakketten).

Alles is een 'record' met een uniek id en een tijd van de laatste wijziging. Bij het uitwisselen wint steeds de nieuwste
versie, dus je kunt op allebei de apparaten iets invoeren. Verwijderen = het record krijgt 'weg': True (dan weet het
andere apparaat het ook).

Bedragen staan in centen (hele getallen), zodat er nooit afrondfoutjes komen.
"""
import json
import os
import socket
import threading
import time
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

POORTEN = [37865, 41865, 43865, 45865, 39865]   # uitwisselen (http): de eerste die vrij is (Windows houdt soms poorten vast)
POORT = POORTEN[0]
ZOEKPOORT = 37866       # de telefoon zoekt de pc op de wifi (udp)

UIT = [("boodschappen", "Boodschappen"), ("huis", "Huis en energie"), ("dieren", "Dieren"), ("vervoer", "Vervoer"),
       ("zorg", "Zorg"), ("kleding", "Kleding"), ("vrije_tijd", "Vrije tijd"), ("cadeaus", "Cadeaus"),
       ("abonnement", "Abonnementen"), ("sparen", "Sparen"), ("overig", "Overig")]
IN = [("loon", "Loon of uitkering"), ("toeslag", "Toeslag"), ("verkoop", "Verkoop"), ("gekregen", "Gekregen"),
      ("overig_in", "Overig")]
NAAM = dict(UIT + IN)
KLEUR = {"boodschappen": "#46c86e", "huis": "#5aa0ff", "dieren": "#ff961e", "vervoer": "#ffde3c", "zorg": "#ff6e8c",
         "kleding": "#c88cff", "vrije_tijd": "#3cd2d2", "cadeaus": "#ff8cd2", "abonnement": "#a0a0c8",
         "sparen": "#9a5ae6", "overig": "#8c8c9a"}
MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober",
           "november", "december"]


def euro(cent, teken=True):
    """1234567 -> '€ 12.345,67'"""
    neg = cent < 0
    cent = abs(int(cent))
    hele, rest = divmod(cent, 100)
    s = "{:,}".format(hele).replace(",", ".") + ",%02d" % rest
    return ("- " if neg else "") + ("€ " if teken else "") + s


def lees_bedrag(tekst):
    """'12,50' of '12.50' of '1.234,5' -> centen (of None)."""
    t = (tekst or "").strip().replace("€", "").replace(" ", "")
    if not t:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") > 1:
        t = t.replace(".", "")
    try:
        return int(round(float(t) * 100))
    except ValueError:
        return None


def vandaag():
    return time.strftime("%Y-%m-%d")


def maand_van(datum):
    return datum[:7]


def maandnaam(ym):
    j, m = ym.split("-")
    return "%s %s" % (MAANDEN[int(m) - 1], j)


def vorige_maand(ym, n=1):
    j, m = map(int, ym.split("-"))
    m -= n
    while m < 1:
        m += 12
        j -= 1
    while m > 12:
        m -= 12
        j += 1
    return "%04d-%02d" % (j, m)


# ------------------------------------------------------------------ getallen in woorden (voor Leon)
_EEN = ["nul", "een", "twee", "drie", "vier", "vijf", "zes", "zeven", "acht", "negen", "tien", "elf", "twaalf",
        "dertien", "veertien", "vijftien", "zestien", "zeventien", "achttien", "negentien"]
_TIEN = ["", "", "twintig", "dertig", "veertig", "vijftig", "zestig", "zeventig", "tachtig", "negentig"]


def onder_honderd(n):
    if n < 20:
        return _EEN[n]
    t, e = divmod(n, 10)
    if not e:
        return _TIEN[t]
    verbind = "ën" if _EEN[e].endswith("e") else "en"
    return _EEN[e] + verbind + _TIEN[t]


def getal_delen(n):
    """Een getal (0 - 999.999) als lijst stukjes: [2, 'honderd', 50] - voor de losse geluidjes op de telefoon."""
    n = int(n)
    if n == 0:
        return [0]
    uit = []
    duizend, rest = divmod(n, 1000)
    if duizend:
        if duizend > 1:
            uit += getal_delen(duizend)
        uit.append("duizend")
    honderd, rest = divmod(rest, 100)
    if honderd:
        if honderd > 1:
            uit.append(honderd)
        uit.append("honderd")
    if rest:
        uit.append(rest)
    return uit


def getal_woorden(n):
    return "".join(onder_honderd(d) if isinstance(d, int) else d for d in getal_delen(n))


# ------------------------------------------------------------------ het boekje
class Kas:
    def __init__(self, map_):
        self.map = map_
        os.makedirs(map_, exist_ok=True)
        self.pad = os.path.join(map_, "kas.json")
        self.lock = threading.RLock()
        self.data = {"apparaat": uuid.uuid4().hex[:12], "records": {}, "code": "%04d" % (uuid.uuid4().int % 10000)}
        try:
            with open(self.pad, encoding="utf-8") as f:
                self.data.update(json.load(f))
        except Exception:
            pass
        self.bij_wijziging = None          # functie die gebeld wordt als er iets verandert (bv. na uitwisselen)

    # --- opslaan
    def bewaar(self):
        with self.lock:
            tmp = self.pad + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False)
            os.replace(tmp, self.pad)
            # een reservekopie per dag (laatste 14 dagen)
            rk = os.path.join(self.map, "reserve")
            os.makedirs(rk, exist_ok=True)
            dag = os.path.join(rk, "kas_%s.json" % vandaag())
            if not os.path.exists(dag):
                with open(dag, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, ensure_ascii=False)
                oud = sorted(x for x in os.listdir(rk) if x.startswith("kas_"))
                for x in oud[:-14]:
                    try:
                        os.remove(os.path.join(rk, x))
                    except OSError:
                        pass

    def zet(self, rec, bewaren=True):
        with self.lock:
            rec = dict(rec)
            rec.setdefault("id", uuid.uuid4().hex)
            rec["gewijzigd"] = time.time()
            rec["door"] = self.data["apparaat"]
            self.data["records"][rec["id"]] = rec
            if bewaren:
                self.bewaar()
            return rec

    def weg(self, rid):
        with self.lock:
            r = self.data["records"].get(rid)
            if r:
                r = dict(r)
                r["weg"] = True
                self.zet(r)

    def alle(self, soort):
        with self.lock:
            return [r for r in self.data["records"].values() if r.get("soort") == soort and not r.get("weg")]

    # --- invoeren
    def post(self, richting, bedrag, cat, oms="", datum=None, doel=None):
        return self.zet(dict(soort="post", richting=richting, bedrag=int(bedrag), cat=cat, oms=oms.strip()[:80],
                             datum=datum or vandaag(), doel=doel))

    def vast(self, naam, bedrag, richting="uit", cat="huis", dag=1, rid=None, actief=True):
        rec = dict(soort="vast", naam=naam.strip()[:40], bedrag=int(bedrag), richting=richting, cat=cat,
                   dag=max(1, min(28, int(dag))), actief=actief,
                   vanaf=time.strftime("%Y-%m"))
        if rid:
            oud = self.data["records"].get(rid, {})
            rec["id"], rec["vanaf"] = rid, oud.get("vanaf", rec["vanaf"])
        r = self.zet(rec)
        self.vaste_lasten_bijwerken()
        return r

    def doel(self, naam, bedrag, rid=None):
        rec = dict(soort="doel", naam=naam.strip()[:40], doelbedrag=int(bedrag))
        if rid:
            rec["id"] = rid
        return self.zet(rec)

    def vaste_lasten_bijwerken(self):
        """Voor elke actieve vaste last: in elke maand (vanaf het begin t/m nu) een post, met een vast id."""
        nu = time.strftime("%Y-%m")
        nieuw = False
        with self.lock:
            for v in self.alle("vast"):
                if not v.get("actief", True):
                    continue
                ym = v.get("vanaf", nu)
                stappen = 0
                while ym <= nu and stappen < 36:
                    pid = "%s-%s" % (v["id"], ym)
                    if pid not in self.data["records"]:
                        dag = min(v.get("dag", 1), 28)
                        self.data["records"][pid] = dict(
                            id=pid, soort="post", richting=v["richting"], bedrag=v["bedrag"], cat=v["cat"],
                            oms=v["naam"], datum="%s-%02d" % (ym, dag), vast=v["id"], gewijzigd=time.time() - 1e6,
                            door=self.data["apparaat"])
                        nieuw = True
                    ym = vorige_maand(ym, -1)
                    stappen += 1
            if nieuw:
                self.bewaar()

    # --- uitrekenen
    def posten(self, ym=None):
        p = self.alle("post")
        if ym:
            p = [x for x in p if maand_van(x["datum"]) == ym]
        return sorted(p, key=lambda x: (x["datum"], x.get("gewijzigd", 0)), reverse=True)

    def maand(self, ym):
        p = self.posten(ym)
        inn = sum(x["bedrag"] for x in p if x["richting"] == "in")
        uit = sum(x["bedrag"] for x in p if x["richting"] == "uit")
        per = {}
        for x in p:
            if x["richting"] == "uit":
                per[x["cat"]] = per.get(x["cat"], 0) + x["bedrag"]
        return dict(inn=inn, uit=uit, over=inn - uit, per=sorted(per.items(), key=lambda kv: -kv[1]))

    def gespaard(self, doel_id):
        return sum(x["bedrag"] for x in self.alle("post") if x.get("doel") == doel_id and x["richting"] == "uit")

    # --- uitwisselen
    def samenvoegen(self, records):
        """Records van het andere apparaat erbij: per id wint de nieuwste. Geeft het aantal veranderingen terug."""
        n = 0
        with self.lock:
            for r in records:
                if not isinstance(r, dict) or "id" not in r:
                    continue
                mijn = self.data["records"].get(r["id"])
                if mijn is None or r.get("gewijzigd", 0) > mijn.get("gewijzigd", 0):
                    self.data["records"][r["id"]] = r
                    n += 1
            if n:
                self.bewaar()
        if n:
            self.vaste_lasten_bijwerken()
        return n

    def alle_records(self):
        with self.lock:
            return list(self.data["records"].values())


# ------------------------------------------------------------------ de pc als 'kluis' op de wifi
class Kluis:
    """Kleine server (op de pc, of op je eigen server): de telefoon stuurt zijn records en krijgt alles terug."""

    def __init__(self, kas, poort=POORT, zoeken=True):
        self.kas, self.poort, self.zoeken = kas, poort, zoeken
        self.laatst = None           # (tijd, aantal) van de laatste uitwisseling
        self.httpd = None

    def start(self):
        kas, kluis = self.kas, self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _stuur(self, code, obj):
                b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_GET(self):
                if self.path.startswith("/hallo"):
                    self._stuur(200, dict(app="DraveKas", naam=socket.gethostname()))
                else:
                    self._stuur(404, dict(fout="onbekend"))

            def do_POST(self):
                if not self.path.startswith("/uitwisselen"):
                    return self._stuur(404, dict(fout="onbekend"))
                if self.headers.get("X-Kas-Code", "") != kas.data["code"]:
                    return self._stuur(403, dict(fout="verkeerde code"))
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                    if n > 20_000_000:
                        return self._stuur(413, dict(fout="te groot"))
                    binnen = json.loads(self.rfile.read(n).decode("utf-8"))
                    veranderd = kas.samenvoegen(binnen.get("records", []))
                    kluis.laatst = (time.time(), veranderd)
                    if veranderd and kas.bij_wijziging:
                        kas.bij_wijziging()
                    self._stuur(200, dict(records=kas.alle_records()))
                except Exception as e:
                    self._stuur(400, dict(fout=str(e)[:200]))

        fout = None
        for p in ([self.poort] + [x for x in POORTEN if x != self.poort]) if self.poort in POORTEN else [self.poort]:
            try:
                self.httpd = ThreadingHTTPServer(("0.0.0.0", p), H)
                self.poort = p
                break
            except OSError as e:
                fout = e
        if not self.httpd:
            raise fout
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        if self.zoeken:
            threading.Thread(target=self._antwoord_zoekers, daemon=True).start()

    def _antwoord_zoekers(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("", ZOEKPOORT))
        except OSError:
            return
        while True:
            try:
                data, adres = s.recvfrom(256)
                if data.startswith(b"DRAVEKAS?"):
                    s.sendto(b"DRAVEKAS!%d" % self.poort, adres)
            except OSError:
                time.sleep(1)

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()


def eigen_ip():
    """Het adres van dit apparaat op de wifi (om in de telefoon in te vullen als zoeken niet lukt)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def tailscale_ip():
    """Het vaste Tailscale-adres (100.x.x.x) als Tailscale aan staat, anders None. Werkt thuis en onderweg."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("100.100.100.100", 1))
        ip = s.getsockname()[0]
        s.close()
        if ip.startswith("100."):
            return ip
    except OSError:
        pass
    return None


def zoek_kluis(wacht=2.0):
    """De telefoon roept op de wifi: 'is hier een DraveKas?' Geeft 'http://ip:poort' terug, of None."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.settimeout(wacht)
        s.sendto(b"DRAVEKAS?", ("255.255.255.255", ZOEKPOORT))
        data, adres = s.recvfrom(256)
        s.close()
        if data.startswith(b"DRAVEKAS!"):
            return "http://%s:%s" % (adres[0], int(data[9:]))
    except (OSError, ValueError):
        return None
    return None


def uitwisselen(kas, adres, code, tijd=12, ssl_ctx=None):
    """Stuur alles naar de kluis (pc of server) en voeg terug wat die heeft. Geeft (ok, tekst) terug."""
    adres = adres.rstrip("/")
    if not adres.startswith("http"):
        adres = "http://" + adres
    if adres.count(":") < 2:                      # geen poort opgegeven: de gewone poorten proberen
        laatste = (False, "De pc is niet te vinden.")
        for p in POORTEN:
            laatste = uitwisselen(kas, "%s:%d" % (adres, p), code, tijd=min(tijd, 4), ssl_ctx=ssl_ctx)
            if laatste[0] or "code" in laatste[1]:
                return laatste
        return laatste
    body = json.dumps(dict(records=kas.alle_records()), ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(adres + "/uitwisselen", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "X-Kas-Code": code,
                                          "User-Agent": "DraveKas/0.1"})
    if ssl_ctx is None and adres.startswith("https"):
        try:
            import ssl
            import certifi
            ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            ssl_ctx = None
    try:
        with urllib.request.urlopen(req, timeout=tijd, context=ssl_ctx) as r:
            terug = json.loads(r.read().decode("utf-8"))
        n = kas.samenvoegen(terug.get("records", []))
        kas.data["laatst_uitgewisseld"] = time.time()
        kas.bewaar()
        return True, ("Bijgewerkt: %d nieuw of veranderd." % n) if n else "Alles is bijgewerkt."
    except urllib.error.HTTPError as e:
        return False, "De code klopt niet." if e.code == 403 else "Fout %d bij de kluis." % e.code
    except Exception:
        return False, "De pc is niet te vinden. Staat DraveKas open op de pc, en zit je op dezelfde wifi?"


if __name__ == "__main__":
    # Losse kluis voor op je eigen server:  python kas_data.py <map> [poort]
    import sys
    kas = Kas(sys.argv[1] if len(sys.argv) > 1 else "DraveKas-kluis")
    poort = int(sys.argv[2]) if len(sys.argv) > 2 else POORT
    Kluis(kas, poort, zoeken=False).start()
    print("DraveKas-kluis draait op poort %d, code %s. Stoppen: Ctrl+C" % (poort, kas.data["code"]))
    while True:
        time.sleep(3600)

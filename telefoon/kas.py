# -*- coding: utf-8 -*-
# DraveKas voor Android - Copyright (C) 2026 Dravenlock (Roger & Claudio).
"""kas.py - DraveKas op de telefoon: groot en duidelijk, met eigen cijfertoetsen, en uitwisselen met de pc via de wifi.

De pc-app is de 'kluis'. Thuis wisselt de telefoon vanzelf alles uit (bij het openen en met 'Bijwerken').
Staat er op de pc een eigen server ingesteld, dan kan de telefoon onderweg met die server uitwisselen.
"""
import json
import os
import threading
import time

import pygame

import kas_data as kd

VERSIE = "0.1"
ANDROID = "ANDROID_PRIVATE" in os.environ or "ANDROID_ARGUMENT" in os.environ
HIER = os.path.dirname(os.path.abspath(__file__))

ZWART = (10, 8, 16)
PANEEL = (24, 18, 38)
PAARS = (150, 90, 230)
PAARS_D = (70, 40, 120)
ZILVER = (226, 226, 236)
GRIJS = (150, 146, 166)
GEEL = (255, 222, 60)
ROOD = (225, 70, 70)
ROOD_D = (122, 36, 36)
GROEN = (90, 230, 140)
GROEN_D = (29, 107, 58)
WIT = (250, 250, 255)


def kleur(hexa):
    hexa = hexa.lstrip("#")
    return tuple(int(hexa[i:i + 2], 16) for i in (0, 2, 4))


def data_map():
    basis = (os.environ.get("ANDROID_PRIVATE") or HIER) if ANDROID else HIER
    p = os.path.join(basis, "DraveKas-data")
    os.makedirs(p, exist_ok=True)
    return p


class Stem:
    """Leon: vaste zinnetjes en getallen achter elkaar."""

    def __init__(self):
        self.clips, self.rij, self.kanaal, self.vrij = {}, [], None, 0
        try:
            pygame.mixer.init(22050, -16, 1, 1024)
            m = os.path.join(HIER, "stem_kas")
            for f in os.listdir(m):
                if f.endswith(".wav"):
                    self.clips[f[:-4]] = pygame.mixer.Sound(os.path.join(m, f))
        except Exception:
            self.clips = {}

    def zeg(self, delen):
        self.stil()
        self.rij = [d for d in delen if d in self.clips]

    def stil(self):
        self.rij = []
        if self.kanaal:
            self.kanaal.stop()

    def bezig(self):
        return bool(self.rij) or (self.kanaal is not None and self.kanaal.get_busy())

    def update(self):
        nu = time.time()
        if self.kanaal is not None and self.kanaal.get_busy():
            self.vrij = nu + 0.06
            return
        if self.rij and nu >= self.vrij:
            self.kanaal = self.clips[self.rij.pop(0)].play()
            self.vrij = nu + 0.15


def euro_clips(cent):
    """Een bedrag als Leon-stukjes: [n2, honderd, n50, euro]."""
    delen = []
    for d in kd.getal_delen(round(abs(cent) / 100)):
        delen.append("n%d" % d if isinstance(d, int) else d)
    return delen + ["euro"]


class App:
    def __init__(self):
        pygame.init()
        self.data = data_map()
        self.kas = kd.Kas(self.data)
        self.kas.vaste_lasten_bijwerken()
        self.inst = {"pc": "", "code": ""}
        try:
            with open(os.path.join(self.data, "instellingen.json"), encoding="utf-8") as f:
                self.inst.update(json.load(f))
        except Exception:
            pass
        if ANDROID:
            info = pygame.display.Info()
            pw, ph = max(1, info.current_w), max(1, info.current_h)
            self.W, self.H = 540, int(540 * max(pw, ph) / min(pw, ph))
            self.venster = pygame.display.set_mode((self.W, self.H), pygame.FULLSCREEN | pygame.SCALED)
        else:
            self.W, self.H = 540, 1040
            self.venster = pygame.display.set_mode((self.W, self.H))
        pygame.display.set_caption("DraveKas")
        fb = os.path.join(HIER, "assets", "DejaVuSans-Bold.ttf")
        fr = os.path.join(HIER, "assets", "DejaVuSans.ttf")
        self.f_reus = pygame.font.Font(fb, 76)
        self.f_groot = pygame.font.Font(fb, 40)
        self.f = pygame.font.Font(fb, 28)
        self.f_mid = pygame.font.Font(fb, 23)
        self.f_klein = pygame.font.Font(fr, 21)
        self.f_mini = pygame.font.Font(fr, 16)
        self.klok = pygame.time.Clock()
        self.stem = Stem()
        self.scherm = "nu"
        self.ym = time.strftime("%Y-%m")
        self.knoppen, self.sleep, self.scroll, self.max_scroll = [], None, 0, 0
        self.melding = None
        self.bezig = False
        self.invoer = None                 # dict(richting, bedrag-tekst, cat, doel, post) tijdens het invoeren
        self.vraag = None                  # (tekst, actie) bij 'zeker weten?'
        self.stop = False
        self.antwoord = None
        threading.Thread(target=self._uitwisselen, args=(True,), daemon=True).start()

    # ------------------------------------------------------------ hulp
    def bewaar(self):
        try:
            with open(os.path.join(self.data, "instellingen.json"), "w", encoding="utf-8") as f:
                json.dump(self.inst, f)
        except Exception:
            pass

    def meld(self, t, s=3.0):
        self.melding = (t, time.time() + s)

    def tekst(self, t, font, kleur_, x, y, midden=False, rechts=False, max_b=None):
        if max_b:
            while font.size(t)[0] > max_b and len(t) > 3:
                t = t[:-4] + "..."
        img = font.render(t, True, kleur_)
        r = img.get_rect()
        if midden:
            r.midtop = (x, y)
        elif rechts:
            r.topright = (x, y)
        else:
            r.topleft = (x, y)
        self.venster.blit(img, r)
        return r

    def breek(self, tekst, font, breed):
        regels, nu = [], ""
        for w in tekst.split():
            if font.size((nu + " " + w).strip())[0] <= breed:
                nu = (nu + " " + w).strip()
            else:
                regels.append(nu)
                nu = w
        if nu:
            regels.append(nu)
        return regels or [""]

    def knop(self, rect, label, actie, kleur_=PAARS_D, rand=PAARS, font=None, tekstkleur=ZILVER):
        r = pygame.Rect(rect)
        pygame.draw.rect(self.venster, kleur_, r, border_radius=14)
        pygame.draw.rect(self.venster, rand, r, 3, border_radius=14)
        if label:
            f = font or self.f
            while f.size(label)[0] > r.w - 16 and f is not self.f_mini:
                f = {self.f_groot: self.f, self.f: self.f_mid, self.f_mid: self.f_klein}.get(f, self.f_mini)
            img = f.render(label, True, tekstkleur)
            self.venster.blit(img, img.get_rect(center=r.center))
        self.knoppen.append((r, actie))
        return r

    def naar(self, s):
        self.scherm = s
        self.scroll = 0

    def kop(self, titel, terug=True):
        W = self.W
        if terug:
            self.knop((16, 16, 140, 72), "Terug", lambda: self.naar("nu"), kleur_=PANEEL)
            self.tekst(titel, self.f_groot, ZILVER, 176, 28, max_b=W - 190)
        else:
            self.tekst(titel, self.f_groot, ZILVER, 20, 24)

    # ------------------------------------------------------------ uitwisselen
    def _uitwisselen(self, stil=False):
        if self.bezig:
            return
        self.bezig = True
        try:
            code = self.inst.get("code", "")
            if not code:
                if not stil:
                    self.antwoord = (False, "Nog niet gekoppeld. Tik op Koppelen.")
                return
            adressen = [a for a in [self.inst.get("pc")] if a]
            gevonden = kd.zoek_kluis(1.5)
            if gevonden and gevonden not in adressen:
                adressen.insert(0, gevonden)
            for a in adressen:
                ok, t = kd.uitwisselen(self.kas, a, code, tijd=6)
                if ok:
                    if a != self.inst.get("pc"):
                        self.inst["pc"] = a
                        self.bewaar()
                    self.antwoord = (True, t)
                    return
            srv = self.kas.data["records"].get("server") or {}
            if srv.get("adres") and not srv.get("weg"):
                ok, t = kd.uitwisselen(self.kas, srv["adres"], srv.get("code", ""), tijd=10)
                if ok:
                    self.antwoord = (True, "Via je server. " + t)
                    return
            if not stil:
                self.antwoord = (False, "De pc is niet te vinden. Staat DraveKas open op de pc, en zit je op dezelfde wifi?")
        finally:
            self.bezig = False

    def bijwerken(self):
        self.meld("Bijwerken...", 8)
        threading.Thread(target=self._uitwisselen, daemon=True).start()

    # ------------------------------------------------------------ schermen
    def scherm_nu(self):
        v, W, H = self.venster, self.W, self.H
        self.tekst("DraveKas", self.f_groot, ZILVER, 20, 24)
        self.knop((W - 150, 16, 134, 72), "Menu", lambda: self.naar("menu"), kleur_=PANEEL)
        # maand kiezen
        self.knop((16, 106, 74, 64), "<", lambda: self.zet_maand(-1), kleur_=PANEEL, font=self.f_groot)
        self.tekst(kd.maandnaam(self.ym).capitalize(), self.f, GEEL, W // 2, 120, midden=True)
        self.knop((W - 90, 106, 74, 64), ">", lambda: self.zet_maand(1), kleur_=PANEEL, font=self.f_groot)
        m = self.kas.maand(self.ym)
        goed = m["over"] >= 0
        k = pygame.Rect(16, 190, W - 32, 250)
        pygame.draw.rect(v, PANEEL, k, border_radius=18)
        pygame.draw.rect(v, GROEN if goed else ROOD, k, 4, border_radius=18)
        self.tekst("Nog over" if goed else "Tekort", self.f, ZILVER, k.x + 22, k.y + 18)
        bedrag = kd.euro(m["over"])
        f = self.f_reus if self.f_reus.size(bedrag)[0] < k.w - 40 else self.f_groot
        self.tekst(bedrag, f, GROEN if goed else ROOD, k.x + 22, k.y + 66)
        self.tekst("Erin:  " + kd.euro(m["inn"]), self.f_mid, (200, 240, 212), k.x + 22, k.y + 168)
        self.tekst("Eruit:  " + kd.euro(m["uit"]), self.f_mid, (255, 208, 208), k.x + 22, k.y + 204)
        y = k.bottom + 20
        bw = (W - 48) // 2
        self.knop((16, y, bw, 110), "+ Erbij", lambda: self.start_invoer("in"), kleur_=GROEN_D, rand=GROEN, font=self.f_groot)
        self.knop((32 + bw, y, bw, 110), "- Uitgave", lambda: self.start_invoer("uit"), kleur_=ROOD_D, rand=ROOD,
                  font=self.f_groot)
        y += 130
        self.knop((16, y, bw, 86), "Lijst", lambda: self.naar("lijst"), kleur_=PANEEL)
        self.knop((32 + bw, y, bw, 86), "Spaardoelen", lambda: self.naar("doelen"), kleur_=PANEEL)
        y += 102
        self.knop((16, y, bw, 86), "Lees voor", self.lees_voor, kleur_=PAARS, rand=GEEL, tekstkleur=ZWART)
        self.knop((32 + bw, y, bw, 86), "Bijwerken", self.bijwerken, kleur_=PANEEL)
        y += 100
        laatst = self.kas.data.get("laatst_uitgewisseld")
        t = ("Bijgewerkt met de pc: " + time.strftime("%d-%m %H:%M", time.localtime(laatst))) if laatst else \
            ("Nog niet gekoppeld met de pc: kies Menu, Koppelen." if not self.inst.get("code") else "Nog niet bijgewerkt.")
        for i, r in enumerate(self.breek(t, self.f_klein, W - 40)):
            self.tekst(r, self.f_klein, GRIJS, 20, y + i * 28)

    def zet_maand(self, d):
        self.ym = kd.vorige_maand(self.ym, -d)

    # --- invoeren: eerst het bedrag (cijfertoetsen), dan de soort
    def start_invoer(self, richting, cat=None, doel=None):
        self.invoer = dict(richting=richting, tekst="", cat=cat, doel=doel)
        self.naar("bedrag")

    def scherm_bedrag(self):
        v, W, H = self.venster, self.W, self.H
        iv = self.invoer
        self.kop("Geld erbij" if iv["richting"] == "in" else ("Sparen" if iv.get("doel") else "Uitgave"))
        veld = pygame.Rect(16, 110, W - 32, 120)
        pygame.draw.rect(v, WIT, veld, border_radius=14)
        pygame.draw.rect(v, GEEL, veld, 4, border_radius=14)
        t = "€ " + (iv["tekst"] or "0")
        self.tekst(t, self.f_reus, ZWART, veld.right - 20, veld.y + 18, rechts=True)
        toetsen = ["1", "2", "3", "4", "5", "6", "7", "8", "9", ",", "0", "<"]
        kw, kh = (W - 32 - 2 * 12) // 3, 108
        for i, t in enumerate(toetsen):
            x = 16 + (i % 3) * (kw + 12)
            y = 252 + (i // 3) * (kh + 12)
            self.knop((x, y, kw, kh), "wissen" if t == "<" else t, lambda t=t: self.toets(t), kleur_=PANEEL,
                      font=self.f_groot if t != "<" else self.f)
        y = 252 + 4 * (kh + 12) + 8
        verder = "Opslaan" if iv.get("cat") else "Volgende: soort"
        self.knop((16, y, W - 32, 100), verder, self.na_bedrag, kleur_=PAARS, rand=GEEL, tekstkleur=ZWART, font=self.f_groot)

    def toets(self, t):
        iv = self.invoer
        s = iv["tekst"]
        if t == "<":
            iv["tekst"] = s[:-1]
        elif t == ",":
            if "," not in s:
                iv["tekst"] = (s or "0") + ","
        elif "," in s and len(s.split(",")[1]) >= 2:
            pass
        elif len(s) < 9:
            iv["tekst"] = (s + t) if s != "0" else t

    def na_bedrag(self):
        c = kd.lees_bedrag(self.invoer["tekst"])
        if not c:
            self.meld("Typ eerst een bedrag.", 2)
            return
        self.invoer["bedrag"] = c
        if self.invoer.get("cat"):
            self.bewaar_invoer()
        else:
            self.naar("soort")

    def scherm_soort(self):
        W = self.W
        iv = self.invoer
        self.kop("Welke soort?")
        self.tekst(kd.euro(iv["bedrag"]), self.f, GEEL, 20, 104)
        lijst = kd.IN if iv["richting"] == "in" else kd.UIT
        bw = (W - 44) // 2
        for i, (code, naam) in enumerate(lijst):
            x = 16 + (i % 2) * (bw + 12)
            y = 150 + (i // 2) * 96
            rand = kleur(kd.KLEUR.get(code, "#9a5ae6"))
            self.knop((x, y, bw, 84), naam, lambda c=code: self.kies_soort(c), kleur_=PANEEL, rand=rand)

    def kies_soort(self, code):
        self.invoer["cat"] = code
        if code == "sparen":
            doelen = self.kas.alle("doel")
            if len(doelen) == 1:
                self.invoer["doel"] = doelen[0]["id"]
            elif doelen:
                self.naar("kies_doel")
                return
        self.bewaar_invoer()

    def scherm_kies_doel(self):
        W = self.W
        self.kop("Welk spaardoel?")
        y = 120
        for d in self.kas.alle("doel"):
            self.knop((16, y, W - 32, 90), d["naam"], lambda d=d: (self.invoer.__setitem__("doel", d["id"]), self.bewaar_invoer()),
                      kleur_=PANEEL)
            y += 104

    def bewaar_invoer(self):
        iv = self.invoer
        oms = kd.NAAM.get(iv["cat"], "")
        if iv.get("doel"):
            d = self.kas.data["records"].get(iv["doel"], {})
            oms = "Sparen: " + d.get("naam", "")
        self.kas.post(iv["richting"], iv["bedrag"], iv["cat"], oms, doel=iv.get("doel"))
        self.meld("Opgeslagen: %s %s" % ("+" if iv["richting"] == "in" else "-", kd.euro(iv["bedrag"])), 2.5)
        self.invoer = None
        self.naar("nu")
        threading.Thread(target=self._uitwisselen, args=(True,), daemon=True).start()

    # --- lijst
    def scherm_lijst(self):
        v, W, H = self.venster, self.W, self.H
        self.kop(kd.maandnaam(self.ym).capitalize())
        posten = self.kas.posten(self.ym)
        if not posten:
            self.tekst("Nog niets deze maand.", self.f, GRIJS, 20, 130)
            return
        self.tekst("Tik op een post om hem te verwijderen.", self.f_klein, GRIJS, 20, 100)
        boven = 140
        oud = v.get_clip()
        v.set_clip(pygame.Rect(0, boven, W, H - boven))
        y = boven - self.scroll
        for p in posten:
            if y + 96 > boven - 100 and y < H:
                r = pygame.Rect(16, y, W - 32, 88)
                self.knop(r, "", lambda p=p: self.vraag_weg(p), kleur_=PANEEL,
                          rand=kleur(kd.KLEUR.get(p["cat"], "#9a5ae6")) if p["richting"] == "uit" else GROEN)
                d = p["datum"].split("-")
                self.tekst("%d-%d  %s" % (int(d[2]), int(d[1]), kd.NAAM.get(p["cat"], p["cat"])), self.f_mid, ZILVER,
                           r.x + 16, r.y + 10, max_b=r.w - 200)
                if p.get("oms") and p["oms"] != kd.NAAM.get(p["cat"]):
                    self.tekst(p["oms"], self.f_klein, GRIJS, r.x + 16, r.y + 48, max_b=r.w - 200)
                self.tekst(("+ " if p["richting"] == "in" else "- ") + kd.euro(p["bedrag"], False), self.f_mid,
                           GROEN if p["richting"] == "in" else (255, 190, 190), r.right - 16, r.y + 28, rechts=True)
            y += 100
        v.set_clip(oud)
        self.knoppen = [k for k in self.knoppen if k[0].y >= boven - 4 or k[0].y < 100]
        self.max_scroll = max(0, len(posten) * 100 - (H - boven) + 20)

    def vraag_weg(self, p):
        tekst = "%s %s verwijderen?" % (kd.NAAM.get(p["cat"], ""), kd.euro(p["bedrag"]))
        self.vraag = (tekst, lambda: (self.kas.weg(p["id"]), self.meld("Verwijderd.", 2),
                                      threading.Thread(target=self._uitwisselen, args=(True,), daemon=True).start()))

    # --- doelen
    def scherm_doelen(self):
        v, W = self.venster, self.W
        self.kop("Spaardoelen")
        doelen = self.kas.alle("doel")
        y = 112
        if not doelen:
            for i, r in enumerate(self.breek("Nog geen spaardoelen. Maak er een op de pc (DraveKas, Spaardoelen). "
                                             "Na het bijwerken staat hij hier ook.", self.f_klein, W - 40)):
                self.tekst(r, self.f_klein, GRIJS, 20, y + i * 30)
            return
        for d in doelen:
            g = self.kas.gespaard(d["id"])
            r = pygame.Rect(16, y, W - 32, 186)
            pygame.draw.rect(v, PANEEL, r, border_radius=16)
            pygame.draw.rect(v, PAARS, r, 3, border_radius=16)
            self.tekst(d["naam"], self.f, ZILVER, r.x + 18, r.y + 14, max_b=r.w - 36)
            self.tekst("%s van %s" % (kd.euro(g), kd.euro(d["doelbedrag"])), self.f_klein, GEEL, r.x + 18, r.y + 56)
            balk = pygame.Rect(r.x + 18, r.y + 92, r.w - 36, 30)
            deel = max(0.0, min(1.0, g / max(1, d["doelbedrag"])))
            pygame.draw.rect(v, (36, 26, 58), balk, border_radius=10)
            pygame.draw.rect(v, GROEN if deel >= 1 else PAARS, (balk.x, balk.y, max(30, int(balk.w * deel)), balk.h),
                             border_radius=10)
            self.tekst("%d%%" % round(deel * 100), self.f_mid, WIT, balk.centerx, balk.y + 2, midden=True)
            self.knop((r.right - 220, r.y + 132, 202, 46), "Geld erin", lambda d=d: self.start_invoer("uit", "sparen", d["id"]),
                      kleur_=PAARS_D, font=self.f_mid)
            y += 200

    # --- menu en koppelen
    def scherm_menu(self):
        W = self.W
        self.kop("Menu")
        y = 120
        for label, actie in (("Koppelen met de pc", lambda: self.start_koppel()),
                             ("Nu bijwerken", self.bijwerken),
                             ("Leon testen", lambda: self.stem.zeg(["k_nog", "n12", "euro", "k_over"]))):
            self.knop((16, y, W - 32, 90), label, actie, kleur_=PANEEL)
            y += 104
        y += 10
        info = ["Gekoppeld met de pc: " + ("ja" if self.inst.get("code") else "nee")]
        if self.inst.get("pc"):
            info.append("Pc: " + self.inst["pc"].replace("http://", ""))
        srv = self.kas.data["records"].get("server") or {}
        if srv.get("adres") and not srv.get("weg"):
            info.append("Onderweg via je server: aan")
        info.append("Alles blijft op je eigen telefoon en pc.")
        info.append("DraveKas %s  -  Dravenlock (Roger & Claudio)" % VERSIE)
        for t in info:
            for r in self.breek(t, self.f_klein, W - 40):
                self.tekst(r, self.f_klein, PAARS if t.startswith("DraveKas") else GRIJS, 20, y)
                y += 30
            y += 6

    def start_koppel(self):
        self.koppel = dict(stap="code", tekst="")
        self.naar("koppel")

    def scherm_koppel(self):
        v, W = self.venster, self.W
        kp = self.koppel
        self.kop("Koppelen" if kp["stap"] == "code" else "Adres van de pc")
        uitleg = ("Open DraveKas op de pc, kies 'Telefoon koppelen' en typ de code van 4 cijfers die daar staat."
                  if kp["stap"] == "code" else
                  "De pc is niet vanzelf gevonden. Typ nu het ADRES (met puntjes) dat op de pc bij 'Telefoon koppelen' staat. Of laat leeg.")
        y = 104
        for r in self.breek(uitleg, self.f_klein, W - 40):
            self.tekst(r, self.f_klein, GRIJS, 20, y)
            y += 28
        veld = pygame.Rect(16, y + 10, W - 32, 100)
        pygame.draw.rect(v, WIT, veld, border_radius=14)
        pygame.draw.rect(v, GEEL, veld, 4, border_radius=14)
        self.tekst(kp["tekst"] or (" " if kp["stap"] == "code" else "(leeg)"), self.f_groot, ZWART, veld.centerx, veld.y + 24,
                   midden=True)
        toetsen = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "." if kp["stap"] == "ip" else "", "0", "<"]
        kw, kh = (W - 56) // 3, 96
        ty = veld.bottom + 20
        for i, t in enumerate(toetsen):
            if not t:
                continue
            x = 16 + (i % 3) * (kw + 12)
            self.knop((x, ty + (i // 3) * (kh + 10), kw, kh), "wissen" if t == "<" else t,
                      lambda t=t: self.koppel_toets(t), kleur_=PANEEL, font=self.f_groot if t != "<" else self.f)
        y = ty + 4 * (kh + 10) + 6
        self.knop((16, y, W - 32, 96), "Koppelen" if kp["stap"] == "code" else "Klaar", self.koppel_verder,
                  kleur_=PAARS, rand=GEEL, tekstkleur=ZWART, font=self.f_groot)

    def koppel_toets(self, t):
        kp = self.koppel
        if t == "<":
            kp["tekst"] = kp["tekst"][:-1]
        elif len(kp["tekst"]) < (4 if kp["stap"] == "code" else 15):
            kp["tekst"] += t

    def koppel_verder(self):
        kp = self.koppel
        if kp["stap"] == "code":
            if len(kp["tekst"]) != 4:
                self.meld("De code heeft 4 cijfers.", 2)
                return
            self.inst["code"] = kp["tekst"]
            self.bewaar()
            self.meld("Zoeken naar de pc...", 10)
            threading.Thread(target=self._koppel_test, daemon=True).start()
        else:
            if kp["tekst"]:
                if kp["tekst"].count(".") != 3:
                    self.meld("Een adres heeft 3 puntjes, zoals 100.64.12.34", 6)
                    return
                self.inst["pc"] = "http://%s" % kp["tekst"]
                self.bewaar()
            self.bijwerken()
            self.naar("nu")

    def _koppel_test(self):
        t0 = time.time()
        while self.bezig and time.time() - t0 < 30:     # wacht tot een lopende uitwisseling klaar is
            time.sleep(0.2)
        self.antwoord = None
        self._uitwisselen()
        ok = self.antwoord and self.antwoord[0]
        if ok:
            self.naar("nu")
        else:
            self.koppel = dict(stap="ip", tekst="")

    # --- Leon
    def lees_voor(self):
        if self.stem.bezig():
            self.stem.stil()
            return
        m = self.kas.maand(self.ym)
        delen = ["k_deze_maand_in"] + euro_clips(m["inn"]) + ["k_binnen", "k_je_gaf"] + euro_clips(m["uit"]) + ["k_uit"]
        if m["over"] >= 0:
            delen += ["k_nog"] + euro_clips(m["over"]) + ["k_over"]
        else:
            delen += ["k_let_op_tekort"] + euro_clips(m["over"]) + ["k_tekort"]
        self.stem.zeg(delen)

    # ------------------------------------------------------------ tekenen en de lus
    def teken(self):
        self.knoppen = []
        self.venster.fill(ZWART)
        getattr(self, "scherm_" + self.scherm)()
        tekst = None
        if self.vraag:
            r = pygame.Rect(24, self.H // 2 - 130, self.W - 48, 260)
            pygame.draw.rect(self.venster, PANEEL, r, border_radius=18)
            pygame.draw.rect(self.venster, GEEL, r, 4, border_radius=18)
            for i, regel in enumerate(self.breek(self.vraag[0], self.f, r.w - 40)[:3]):
                self.tekst(regel, self.f, ZILVER, r.centerx, r.y + 26 + i * 38, midden=True)
            self.knoppen = []
            bw = (r.w - 60) // 2
            self.knop((r.x + 20, r.bottom - 106, bw, 86), "Ja", self.vraag_ja, kleur_=ROOD_D, rand=ROOD)
            self.knop((r.x + 40 + bw, r.bottom - 106, bw, 86), "Nee", lambda: setattr(self, "vraag", None), kleur_=PANEEL)
        elif self.melding and time.time() < self.melding[1]:
            tekst = self.melding[0]
        if tekst:
            r = pygame.Rect(30, self.H // 2 - 60, self.W - 60, 120)
            pygame.draw.rect(self.venster, PANEEL, r, border_radius=16)
            pygame.draw.rect(self.venster, GEEL, r, 4, border_radius=16)
            regels = self.breek(tekst, self.f_mid, r.w - 30)[:3]
            for i, regel in enumerate(regels):
                self.tekst(regel, self.f_mid, ZILVER, r.centerx, r.centery - len(regels) * 16 + i * 32, midden=True)
        pygame.display.flip()

    def vraag_ja(self):
        actie = self.vraag[1]
        self.vraag = None
        actie()

    def klik(self, pos):
        for r, actie in reversed(self.knoppen):
            if r.collidepoint(pos):
                actie()
                return

    def terug(self):
        if self.vraag:
            self.vraag = None
        elif self.scherm == "nu":
            self.stop = True
        elif self.scherm == "soort":
            self.naar("bedrag")
        else:
            self.invoer = None
            self.naar("nu")

    def run(self):
        while not self.stop:
            self.klok.tick(30)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.stop = True
                elif e.type == pygame.KEYDOWN:
                    if e.key in (pygame.K_AC_BACK, pygame.K_ESCAPE):
                        self.terug()
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    self.sleep = (e.pos, self.scroll, False)
                elif e.type == pygame.MOUSEMOTION and self.sleep and e.buttons[0]:
                    (sx, sy), s0, _ = self.sleep
                    if abs(e.pos[1] - sy) > 20 and self.scherm == "lijst":
                        self.scroll = max(0, min(self.max_scroll, s0 - (e.pos[1] - sy)))
                        self.sleep = ((sx, sy), s0, True)
                elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                    if self.sleep and not self.sleep[2]:
                        self.klik(e.pos)
                    self.sleep = None
            if self.antwoord:
                ok, t = self.antwoord
                self.antwoord = None
                self.meld(t, 3.5 if ok else 15)
            self.stem.update()
            self.teken()
        self.kas.bewaar()
        pygame.quit()


def main():
    App().run()


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
# DraveKas - Copyright (C) 2026 Dravenlock (Roger & Claudio).
"""dravekas.py - DraveKas voor de pc: een groot en duidelijk huishoudboekje.

Wat er deze maand nog over is, staat groot in beeld. Met vaste lasten, spaardoelen en een overzicht per soort.
De pc is de 'kluis': de telefoon-app wisselt via de wifi thuis alles uit. Wil je, dan wisselt de pc ook met je eigen server.
Leon leest voor hoe je ervoor staat.
"""
import json
import os
import sys
import threading
import time

from PyQt6.QtCore import QDate, QObject, QRectF, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (QApplication, QComboBox, QDateEdit, QDialog, QGridLayout, QHBoxLayout, QLabel,
                             QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
                             QScrollArea, QSizePolicy, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

import kas_data as kd
import leon

VERSIE = "0.1"
NAAM = "DraveKas"


def app_map():
    return os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))


def bron_map():
    return getattr(sys, "_MEIPASS", app_map())


DATA = os.path.join(app_map(), "DraveKas-data")          # naast de app (dus op D:, niet op C:)
os.makedirs(DATA, exist_ok=True)


def stijl(f):
    p = lambda n: "%dpt" % round(n * f)
    return """
* { font-family: 'Segoe UI'; color: #e2e2ec; }
QMainWindow, QWidget#basis, QDialog, QScrollArea, QWidget#vel { background: #0a0810; }
QLabel#titel { font-size: %(t)s; font-weight: 700; }
QLabel#maand { font-size: %(m)s; font-weight: 700; color: #ffde3c; }
QLabel#kop { font-size: %(kop)s; font-weight: 700; }
QLabel#klein { font-size: %(klein)s; color: #9a96aa; }
QLabel#tekst { font-size: %(tekst)s; }
QDialog QLabel { font-size: %(tekst)s; }
QPushButton { background: #18122a; border: 2px solid #9a5ae6; border-radius: 12px; padding: 9px 15px;
              font-size: %(knop)s; font-weight: 600; }
QPushButton:hover { border-color: #ffde3c; }
QPushButton:checked { background: #9a5ae6; color: #0a0810; border-color: #ffde3c; }
QPushButton#groen { background: #1d6b3a; border-color: #46c86e; font-size: %(groot)s; padding: 14px 20px; }
QPushButton#rood { background: #7a2424; border-color: #ff6e6e; font-size: %(groot)s; padding: 14px 20px; }
QPushButton#paars { background: #9a5ae6; color: #0a0810; border-color: #ffde3c; font-size: %(groot)s; padding: 12px 18px; }
QLineEdit, QComboBox, QDateEdit, QSpinBox { background: #fafaff; color: #0a0810; border: 3px solid #ffde3c;
              border-radius: 10px; padding: 7px 10px; font-size: %(knop)s; }
QLineEdit#bedrag { font-size: %(groot2)s; font-weight: 700; }
QComboBox QAbstractItemView { background: #fafaff; color: #0a0810; font-size: %(knop)s; }
QListWidget { background: #0f0b1a; border: 2px solid #46307a; border-radius: 12px; font-size: %(tekst)s; }
QListWidget::item { border-bottom: 1px solid #241a3a; padding: 8px; }
QListWidget::item:selected { background: #2c1d50; }
""" % dict(t=p(26), m=p(20), kop=p(18), klein=p(12), tekst=p(15), knop=p(14), groot=p(17), groot2=p(28))


class Signalen(QObject):
    leon = pyqtSignal(int, str)
    veranderd = pyqtSignal()
    server = pyqtSignal(bool, str)


class Grafiek(QWidget):
    """Staafjes: waar ging het geld heen deze maand."""

    def __init__(self):
        super().__init__()
        self.per, self.f = [], 1.0
        self.setMinimumHeight(220)

    def zet(self, per, f):
        self.per, self.f = per, f
        rij = round(46 * f)
        self.setMinimumHeight(max(80, rij * max(1, len(per)) + 10))
        self.update()

    def paintEvent(self, e):
        q = QPainter(self)
        q.setRenderHint(QPainter.RenderHint.Antialiasing)
        f = self.f
        rij = round(46 * f)
        if not self.per:
            q.setPen(QColor("#9a96aa"))
            q.setFont(QFont("Segoe UI", round(14 * f)))
            q.drawText(QRectF(0, 0, self.width(), 60), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       "Nog geen uitgaven deze maand.")
            return
        hoogste = max(b for _, b in self.per) or 1
        lw = round(200 * f)
        bw = round(170 * f)
        breed = max(50, self.width() - lw - bw - 20)
        for i, (cat, bedrag) in enumerate(self.per):
            y = i * rij + 4
            q.setPen(QColor("#e2e2ec"))
            q.setFont(QFont("Segoe UI", round(14 * f), QFont.Weight.DemiBold))
            q.drawText(QRectF(0, y, lw - 10, rij - 10), Qt.AlignmentFlag.AlignVCenter, kd.NAAM.get(cat, cat))
            w = max(6, breed * bedrag / hoogste)
            q.setPen(Qt.PenStyle.NoPen)
            q.setBrush(QColor(kd.KLEUR.get(cat, "#9a5ae6")))
            q.drawRoundedRect(QRectF(lw, y + 6, w, rij - 18), 8, 8)
            q.setPen(QColor("#ffde3c"))
            q.drawText(QRectF(lw + w + 10, y, bw, rij - 10), Qt.AlignmentFlag.AlignVCenter, kd.euro(bedrag))


class Balk(QWidget):
    """Een spaardoel-balk die vol loopt."""

    def __init__(self, deel, f):
        super().__init__()
        self.deel, self.f = max(0.0, min(1.0, deel)), f
        self.setFixedHeight(round(30 * f))

    def paintEvent(self, e):
        q = QPainter(self)
        q.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0, 0, self.width(), self.height())
        q.setPen(Qt.PenStyle.NoPen)
        q.setBrush(QColor("#241a3a"))
        q.drawRoundedRect(r, 10, 10)
        q.setBrush(QColor("#46c86e" if self.deel >= 1 else "#9a5ae6"))
        q.drawRoundedRect(QRectF(0, 0, max(self.height(), self.width() * self.deel), self.height()), 10, 10)
        q.setPen(QColor("#ffffff"))
        q.setFont(QFont("Segoe UI", round(12 * self.f), QFont.Weight.Bold))
        q.drawText(r, Qt.AlignmentFlag.AlignCenter, "%d%%" % round(self.deel * 100))


class PostVenster(QDialog):
    """Geld erbij of een uitgave invoeren (of aanpassen)."""

    def __init__(self, hoofd, richting, post=None):
        super().__init__(hoofd)
        self.hoofd, self.richting, self.post = hoofd, richting, post
        self.setWindowTitle("Geld erbij" if richting == "in" else "Uitgave")
        self.setMinimumWidth(720)
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        k = QLabel("Hoeveel?")
        k.setObjectName("kop")
        lay.addWidget(k)
        self.bedrag = QLineEdit()
        self.bedrag.setObjectName("bedrag")
        self.bedrag.setPlaceholderText("0,00")
        lay.addWidget(self.bedrag)
        k2 = QLabel("Wat voor soort?")
        k2.setObjectName("kop")
        lay.addWidget(k2)
        grid = QGridLayout()
        self.cats = {}
        lijst = kd.IN if richting == "in" else kd.UIT
        for i, (code, naam) in enumerate(lijst):
            b = QPushButton(naam)
            b.setCheckable(True)
            b.clicked.connect(lambda _, c=code: self.kies(c))
            grid.addWidget(b, i // 3, i % 3)
            self.cats[code] = b
        lay.addLayout(grid)
        self.doelrij = QWidget()
        dl = QHBoxLayout(self.doelrij)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.addWidget(QLabel("Voor welk spaardoel?"))
        self.doel = QComboBox()
        for d in hoofd.kas.alle("doel"):
            self.doel.addItem(d["naam"], d["id"])
        dl.addWidget(self.doel, 1)
        lay.addWidget(self.doelrij)
        self.oms = QLineEdit()
        self.oms.setPlaceholderText("Omschrijving (mag leeg), bijvoorbeeld: Jumbo")
        lay.addWidget(self.oms)
        drij = QHBoxLayout()
        drij.addWidget(QLabel("Datum:"))
        self.datum = QDateEdit()
        self.datum.setCalendarPopup(True)
        self.datum.setDisplayFormat("d-M-yyyy")
        self.datum.setDate(QDate.currentDate())
        drij.addWidget(self.datum)
        drij.addStretch(1)
        lay.addLayout(drij)
        self.fout = QLabel("")
        self.fout.setStyleSheet("color: #ff8c8c; font-weight: 700;")
        lay.addWidget(self.fout)
        kn = QHBoxLayout()
        ok = QPushButton("Opslaan")
        ok.setObjectName("paars")
        ok.clicked.connect(self.opslaan)
        kn.addWidget(ok, 2)
        nee = QPushButton("Annuleren")
        nee.clicked.connect(self.reject)
        kn.addWidget(nee, 1)
        lay.addLayout(kn)
        self.gekozen = lijst[0][0]
        if post:
            self.bedrag.setText(kd.euro(post["bedrag"], False))
            self.gekozen = post["cat"]
            self.oms.setText(post.get("oms", ""))
            j, m, d = map(int, post["datum"].split("-"))
            self.datum.setDate(QDate(j, m, d))
            if post.get("doel"):
                self.doel.setCurrentIndex(max(0, self.doel.findData(post["doel"])))
        self.kies(self.gekozen)
        self.bedrag.setFocus()

    def kies(self, code):
        self.gekozen = code
        for c, b in self.cats.items():
            b.setChecked(c == code)
        self.doelrij.setVisible(code == "sparen" and self.doel.count() > 0)

    def opslaan(self):
        c = kd.lees_bedrag(self.bedrag.text())
        if not c or c <= 0:
            self.fout.setText("Vul een bedrag in, bijvoorbeeld 12,50")
            return
        datum = self.datum.date().toString("yyyy-MM-dd")
        doel = self.doel.currentData() if self.gekozen == "sparen" and self.doel.count() else None
        rec = dict(self.post or {}, soort="post", richting=self.richting, bedrag=c, cat=self.gekozen,
                   oms=self.oms.text().strip()[:80], datum=datum, doel=doel)
        self.hoofd.kas.zet(rec)
        self.accept()


class VastVenster(QDialog):
    def __init__(self, hoofd, vast=None):
        super().__init__(hoofd)
        self.hoofd, self.v = hoofd, vast
        self.setWindowTitle("Vaste last of vast inkomen")
        self.setMinimumWidth(620)
        lay = QVBoxLayout(self)
        self.naam = QLineEdit()
        self.naam.setPlaceholderText("Naam, bijvoorbeeld: Huur")
        lay.addWidget(self.naam)
        self.bedrag = QLineEdit()
        self.bedrag.setObjectName("bedrag")
        self.bedrag.setPlaceholderText("0,00")
        lay.addWidget(self.bedrag)
        rij = QHBoxLayout()
        self.richting = QComboBox()
        self.richting.addItem("Gaat eraf (uitgave)", "uit")
        self.richting.addItem("Komt erbij (inkomen)", "in")
        self.richting.currentIndexChanged.connect(self.vul_cats)
        rij.addWidget(self.richting, 2)
        self.cat = QComboBox()
        rij.addWidget(self.cat, 2)
        lay.addLayout(rij)
        drij = QHBoxLayout()
        drij.addWidget(QLabel("Elke maand op dag:"))
        self.dag = QSpinBox()
        self.dag.setRange(1, 28)
        drij.addWidget(self.dag)
        drij.addStretch(1)
        lay.addLayout(drij)
        self.fout = QLabel("")
        self.fout.setStyleSheet("color: #ff8c8c; font-weight: 700;")
        lay.addWidget(self.fout)
        kn = QHBoxLayout()
        ok = QPushButton("Opslaan")
        ok.setObjectName("paars")
        ok.clicked.connect(self.opslaan)
        kn.addWidget(ok, 2)
        nee = QPushButton("Annuleren")
        nee.clicked.connect(self.reject)
        kn.addWidget(nee, 1)
        lay.addLayout(kn)
        self.vul_cats()
        if vast:
            self.naam.setText(vast["naam"])
            self.bedrag.setText(kd.euro(vast["bedrag"], False))
            self.richting.setCurrentIndex(0 if vast["richting"] == "uit" else 1)
            self.vul_cats()
            self.cat.setCurrentIndex(max(0, self.cat.findData(vast["cat"])))
            self.dag.setValue(vast.get("dag", 1))
        else:
            self.cat.setCurrentIndex(max(0, self.cat.findData("huis")))

    def vul_cats(self):
        self.cat.clear()
        for code, naam in (kd.UIT if self.richting.currentData() == "uit" else kd.IN):
            self.cat.addItem(naam, code)

    def opslaan(self):
        c = kd.lees_bedrag(self.bedrag.text())
        if not self.naam.text().strip() or not c:
            self.fout.setText("Vul een naam en een bedrag in.")
            return
        self.hoofd.kas.vast(self.naam.text(), c, self.richting.currentData(), self.cat.currentData(), self.dag.value(),
                            rid=self.v["id"] if self.v else None)
        self.accept()


class Venster(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(NAAM)
        ico = os.path.join(bron_map(), "assets", "icon.ico")
        if os.path.exists(ico):
            self.setWindowIcon(QIcon(ico))
        self.kas = kd.Kas(DATA)
        self.kas.vaste_lasten_bijwerken()
        self.inst = {"groot": 1.0, "server": "", "servercode": ""}
        try:
            with open(os.path.join(DATA, "instellingen.json"), encoding="utf-8") as f:
                self.inst.update(json.load(f))
        except Exception:
            pass
        self.sig = Signalen()
        self.sig.leon.connect(self.leon_binnen)
        self.sig.veranderd.connect(self.ververs)
        self.sig.server.connect(lambda ok, t: (self.serverstatus.setText(t), self.ververs() if ok else None))
        self.kas.bij_wijziging = self.sig.veranderd.emit
        self.ym = time.strftime("%Y-%m")
        self.beurt, self.rij, self.wacht = 0, [], 0
        try:
            self.kluis = kd.Kluis(self.kas)
            self.kluis.start()
            self.kluis_fout = None
        except OSError as e:
            self.kluis, self.kluis_fout = None, str(e)

        basis = QWidget()
        basis.setObjectName("basis")
        self.setCentralWidget(basis)
        hoofd = QVBoxLayout(basis)
        hoofd.setContentsMargins(18, 14, 18, 12)
        boven = QHBoxLayout()
        logo = QLabel()
        png = os.path.join(bron_map(), "assets", "logo.png")
        if os.path.exists(png):
            logo.setPixmap(QPixmap(png).scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation))
        boven.addWidget(logo)
        t = QLabel(NAAM)
        t.setObjectName("titel")
        boven.addWidget(t)
        boven.addSpacing(24)
        terug = QPushButton("◀")
        terug.setToolTip("Vorige maand")
        terug.clicked.connect(lambda: self.zet_maand(-1))
        boven.addWidget(terug)
        self.maandlabel = QLabel("")
        self.maandlabel.setObjectName("maand")
        self.maandlabel.setMinimumWidth(240)
        self.maandlabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        boven.addWidget(self.maandlabel)
        verder = QPushButton("▶")
        verder.setToolTip("Volgende maand")
        verder.clicked.connect(lambda: self.zet_maand(1))
        boven.addWidget(verder)
        nu = QPushButton("Deze maand")
        nu.clicked.connect(lambda: self.zet_maand(0))
        boven.addWidget(nu)
        boven.addStretch(1)
        self.leesknop = QPushButton("🔊  Lees voor")
        self.leesknop.setObjectName("paars")
        self.leesknop.clicked.connect(self.lees_voor)
        boven.addWidget(self.leesknop)
        kl = QPushButton("A−")
        kl.clicked.connect(lambda: self.zet_groot(-0.1))
        boven.addWidget(kl)
        gr = QPushButton("A+")
        gr.clicked.connect(lambda: self.zet_groot(0.1))
        boven.addWidget(gr)
        hoofd.addLayout(boven)

        tabs = QHBoxLayout()
        self.tabs = {}
        self.stapel = QStackedWidget()
        for sl, label in (("over", "Overzicht"), ("posten", "Alle posten"), ("vast", "Vaste lasten"),
                          ("doelen", "Spaardoelen"), ("koppel", "Telefoon koppelen")):
            b = QPushButton(label)
            b.setCheckable(True)
            b.clicked.connect(lambda _, s=sl: self.kies_tab(s))
            tabs.addWidget(b)
            self.tabs[sl] = b
        hoofd.addLayout(tabs)
        hoofd.addWidget(self.stapel, 1)
        self.paginas = {}
        for sl in self.tabs:
            sc = QScrollArea()
            sc.setWidgetResizable(True)
            sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            sc.setStyleSheet("QScrollArea { border: none; }")
            self.stapel.addWidget(sc)
            self.paginas[sl] = sc
        self.status = QLabel("")
        self.status.setObjectName("klein")
        hoofd.addWidget(self.status)
        voet = QLabel("%s %s  ·  Alles blijft op je eigen pc en telefoon  ·  Stem: Leon  ·  Dravenlock (Roger & Claudio)"
                      % (NAAM, VERSIE))
        voet.setObjectName("klein")
        hoofd.addWidget(voet)

        self.uit = QAudioOutput()
        self.speler = QMediaPlayer()
        self.speler.setAudioOutput(self.uit)
        self.speler.mediaStatusChanged.connect(self.speler_status)
        self.serverstatus = QLabel("")
        self.resize(1400, 900)
        self.pas_stijl()
        self.tab = "over"
        self.kies_tab("over")
        self.klok = QTimer(self)
        self.klok.timeout.connect(self.elke_minuut)
        self.klok.start(60 * 1000)
        QTimer.singleShot(1500, self.met_server)

    # ------------------------------------------------------------ algemeen
    def bewaar_inst(self):
        try:
            with open(os.path.join(DATA, "instellingen.json"), "w", encoding="utf-8") as f:
                json.dump(self.inst, f, ensure_ascii=False)
        except Exception:
            pass

    def pas_stijl(self):
        QApplication.instance().setStyleSheet(stijl(self.inst["groot"]))

    def zet_groot(self, d):
        self.inst["groot"] = round(min(1.8, max(0.8, self.inst["groot"] + d)), 2)
        self.bewaar_inst()
        self.pas_stijl()
        self.ververs()

    def zet_maand(self, d):
        self.ym = time.strftime("%Y-%m") if d == 0 else kd.vorige_maand(self.ym, -d)
        self.ververs()

    def kies_tab(self, s):
        self.tab = s
        for k, b in self.tabs.items():
            b.setChecked(k == s)
        self.stapel.setCurrentWidget(self.paginas[s])
        self.ververs()

    def elke_minuut(self):
        self.kas.vaste_lasten_bijwerken()
        if int(time.time() // 60) % 10 == 0:
            self.met_server()
        if self.tab == "koppel":
            self.ververs()

    def ververs(self):
        self.maandlabel.setText(kd.maandnaam(self.ym).capitalize())
        getattr(self, "pagina_" + self.tab)()

    def nieuw_vel(self):
        vel = QWidget()
        vel.setObjectName("vel")
        lay = QVBoxLayout(vel)
        lay.setContentsMargins(4, 10, 4, 10)
        lay.setSpacing(14)
        self.paginas[self.tab].setWidget(vel)
        return lay

    @staticmethod
    def label(t, naam=None, wrap=True):
        lb = QLabel(t)
        if naam:
            lb.setObjectName(naam)
        lb.setWordWrap(wrap)
        return lb

    def kaart(self, kleur="#46307a"):
        w = QWidget()
        w.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        w.setStyleSheet("QWidget#kaartje { background: #120d20; border: 2px solid %s; border-radius: 16px; }" % kleur)
        w.setObjectName("kaartje")
        return w

    # ------------------------------------------------------------ overzicht
    def pagina_over(self):
        lay = self.nieuw_vel()
        f = self.inst["groot"]
        m = self.kas.maand(self.ym)
        groen = m["over"] >= 0
        k = self.kaart("#46c86e" if groen else "#ff6e6e")
        kl = QVBoxLayout(k)
        kl.setContentsMargins(24, 18, 24, 18)
        kl.addWidget(self.label("Nog over in %s" % kd.maandnaam(self.ym) if groen else "Tekort in %s" % kd.maandnaam(self.ym),
                                "kop"))
        groot = QLabel(kd.euro(m["over"]))
        groot.setStyleSheet("font-size: %dpt; font-weight: 800; color: %s;" % (round(54 * f), "#5ae68c" if groen else "#ff8080"))
        kl.addWidget(groot)
        rij = QHBoxLayout()
        a = QLabel("Erin:  " + kd.euro(m["inn"]))
        a.setStyleSheet("font-size: %dpt; color: #c8f0d4; font-weight: 600;" % round(17 * f))
        b = QLabel("Eruit:  " + kd.euro(m["uit"]))
        b.setStyleSheet("font-size: %dpt; color: #ffd0d0; font-weight: 600;" % round(17 * f))
        rij.addWidget(a)
        rij.addSpacing(40)
        rij.addWidget(b)
        rij.addStretch(1)
        kl.addLayout(rij)
        lay.addWidget(k)
        kn = QHBoxLayout()
        plus = QPushButton("+  Geld erbij")
        plus.setObjectName("groen")
        plus.clicked.connect(lambda: self.invoer("in"))
        kn.addWidget(plus)
        min_ = QPushButton("−  Uitgave")
        min_.setObjectName("rood")
        min_.clicked.connect(lambda: self.invoer("uit"))
        kn.addWidget(min_)
        lay.addLayout(kn)
        lay.addWidget(self.label("Waar ging het geld heen?", "kop"))
        g = Grafiek()
        g.zet(m["per"], f)
        lay.addWidget(g)
        doelen = self.kas.alle("doel")
        if doelen:
            lay.addWidget(self.label("Spaardoelen", "kop"))
            for d in doelen:
                lay.addLayout(self.doelrij(d, klein=True))
        lay.addStretch(1)

    def doelrij(self, d, klein=False):
        f = self.inst["groot"]
        rij = QHBoxLayout()
        gespaard = self.kas.gespaard(d["id"])
        n = QLabel("%s\n%s van %s" % (d["naam"], kd.euro(gespaard), kd.euro(d["doelbedrag"])))
        n.setStyleSheet("font-size: %dpt;" % round(14 * f))
        n.setMinimumWidth(round(300 * f))
        rij.addWidget(n)
        rij.addWidget(Balk(gespaard / max(1, d["doelbedrag"]), f), 1)
        return rij

    def invoer(self, richting, post=None):
        if PostVenster(self, richting, post).exec():
            self.status.setText("Opgeslagen.")
            self.ververs()

    # ------------------------------------------------------------ posten
    def pagina_posten(self):
        lay = self.nieuw_vel()
        kn = QHBoxLayout()
        plus = QPushButton("+  Geld erbij")
        plus.setObjectName("groen")
        plus.clicked.connect(lambda: self.invoer("in"))
        kn.addWidget(plus)
        min_ = QPushButton("−  Uitgave")
        min_.setObjectName("rood")
        min_.clicked.connect(lambda: self.invoer("uit"))
        kn.addWidget(min_)
        lay.addLayout(kn)
        posten = self.kas.posten(self.ym)
        lay.addWidget(self.label("%d posten in %s. Dubbelklik om aan te passen." % (len(posten), kd.maandnaam(self.ym)), "klein"))
        lijst = QListWidget()
        lijst.setMinimumHeight(420)
        for p in posten:
            j, mnd, d = p["datum"].split("-")
            teken = "+" if p["richting"] == "in" else "−"
            tekst = "%s-%s    %s  %s    %s%s" % (int(d), int(mnd), teken, kd.euro(p["bedrag"]), kd.NAAM.get(p["cat"], p["cat"]),
                                                ("  ·  " + p["oms"]) if p.get("oms") else "")
            if p.get("vast"):
                tekst += "   (vast)"
            it = QListWidgetItem(tekst)
            it.setForeground(QColor("#5ae68c" if p["richting"] == "in" else "#ffb4b4"))
            it.setData(Qt.ItemDataRole.UserRole, p["id"])
            lijst.addItem(it)
        lijst.itemDoubleClicked.connect(lambda it: self.pas_post(it.data(Qt.ItemDataRole.UserRole)))
        lay.addWidget(lijst, 1)
        weg = QPushButton("Gekozen post verwijderen")
        weg.clicked.connect(lambda: self.verwijder(lijst))
        lay.addWidget(weg)

    def pas_post(self, pid):
        p = self.kas.data["records"].get(pid)
        if p:
            self.invoer(p["richting"], p)

    def verwijder(self, lijst):
        it = lijst.currentItem()
        if not it:
            self.status.setText("Klik eerst op een post in de lijst.")
            return
        if QMessageBox.question(self, "Verwijderen", "Deze post verwijderen?\n\n" + it.text()) == QMessageBox.StandardButton.Yes:
            self.kas.weg(it.data(Qt.ItemDataRole.UserRole))
            self.ververs()

    # ------------------------------------------------------------ vaste lasten
    def pagina_vast(self):
        lay = self.nieuw_vel()
        lay.addWidget(self.label("Vaste lasten en vast inkomen staan elke maand vanzelf in je boekje.", "tekst"))
        nieuw = QPushButton("+  Nieuwe vaste last of vast inkomen")
        nieuw.setObjectName("paars")
        nieuw.clicked.connect(lambda: VastVenster(self).exec() and self.ververs())
        lay.addWidget(nieuw)
        lijst = QListWidget()
        lijst.setMinimumHeight(360)
        tot_in = tot_uit = 0
        for v in sorted(self.kas.alle("vast"), key=lambda v: (v["richting"], v.get("dag", 1))):
            if v["richting"] == "in":
                tot_in += v["bedrag"]
            else:
                tot_uit += v["bedrag"]
            it = QListWidgetItem("Dag %d    %s %s    %s  ·  %s" % (v.get("dag", 1), "+" if v["richting"] == "in" else "−",
                                                                kd.euro(v["bedrag"]), v["naam"], kd.NAAM.get(v["cat"], v["cat"])))
            it.setForeground(QColor("#5ae68c" if v["richting"] == "in" else "#ffb4b4"))
            it.setData(Qt.ItemDataRole.UserRole, v["id"])
            lijst.addItem(it)
        lijst.itemDoubleClicked.connect(lambda it: VastVenster(self, self.kas.data["records"][it.data(Qt.ItemDataRole.UserRole)]).exec()
                                        and self.ververs())
        lay.addWidget(lijst)
        lay.addWidget(self.label("Elke maand vast erin: %s  ·  vast eruit: %s" % (kd.euro(tot_in), kd.euro(tot_uit)), "kop"))
        weg = QPushButton("Gekozen vaste last stoppen")
        weg.setToolTip("Hij komt er dan niet meer bij. Wat al in je boekje stond, blijft staan.")
        weg.clicked.connect(lambda: self.stop_vast(lijst))
        lay.addWidget(weg)
        lay.addStretch(1)

    def stop_vast(self, lijst):
        it = lijst.currentItem()
        if it and QMessageBox.question(self, "Stoppen", "Deze vaste last stoppen?\n\n" + it.text()) == QMessageBox.StandardButton.Yes:
            self.kas.weg(it.data(Qt.ItemDataRole.UserRole))
            self.ververs()

    # ------------------------------------------------------------ spaardoelen
    def pagina_doelen(self):
        lay = self.nieuw_vel()
        lay.addWidget(self.label("Zet geld opzij voor iets moois. Kies bij een uitgave de soort 'Sparen' en het doel, "
                                 "of klik hieronder op 'Geld erin'.", "tekst"))
        rij = QHBoxLayout()
        self.dnaam = QLineEdit()
        self.dnaam.setPlaceholderText("Nieuw doel, bijvoorbeeld: WD-schijf")
        rij.addWidget(self.dnaam, 3)
        self.dbedrag = QLineEdit()
        self.dbedrag.setPlaceholderText("Doelbedrag, bv. 158,00")
        rij.addWidget(self.dbedrag, 2)
        ok = QPushButton("+ Toevoegen")
        ok.setObjectName("paars")
        ok.clicked.connect(self.nieuw_doel)
        rij.addWidget(ok, 1)
        lay.addLayout(rij)
        for d in self.kas.alle("doel"):
            k = self.kaart()
            kl = QVBoxLayout(k)
            kl.setContentsMargins(18, 14, 18, 14)
            kl.addLayout(self.doelrij(d))
            kn = QHBoxLayout()
            erin = QPushButton("Geld erin")
            erin.clicked.connect(lambda _, d=d: self.spaar(d))
            kn.addWidget(erin)
            weg = QPushButton("Doel verwijderen")
            weg.clicked.connect(lambda _, d=d: self.doel_weg(d))
            kn.addWidget(weg)
            kn.addStretch(1)
            kl.addLayout(kn)
            lay.addWidget(k)
        lay.addStretch(1)

    def nieuw_doel(self):
        c = kd.lees_bedrag(self.dbedrag.text())
        if not self.dnaam.text().strip() or not c:
            self.status.setText("Vul een naam en een doelbedrag in.")
            return
        self.kas.doel(self.dnaam.text(), c)
        self.ververs()

    def spaar(self, d):
        v = PostVenster(self, "uit")
        v.kies("sparen")
        v.doel.setCurrentIndex(max(0, v.doel.findData(d["id"])))
        v.oms.setText("Sparen: " + d["naam"])
        if v.exec():
            self.ververs()

    def doel_weg(self, d):
        if QMessageBox.question(self, "Verwijderen", "Het doel '%s' verwijderen?\n(Wat je al gespaard hebt, blijft in je boekje.)"
                                % d["naam"]) == QMessageBox.StandardButton.Yes:
            self.kas.weg(d["id"])
            self.ververs()

    # ------------------------------------------------------------ koppelen
    def pagina_koppel(self):
        lay = self.nieuw_vel()
        f = self.inst["groot"]
        k = self.kaart("#ffde3c")
        kl = QVBoxLayout(k)
        kl.setContentsMargins(24, 18, 24, 18)
        kl.addWidget(self.label("Je telefoon koppelen (via de wifi thuis)", "kop"))
        if self.kluis:
            kl.addWidget(self.label("1. Zet DraveKas op je telefoon en open hem.\n2. Tik op Koppelen en vul deze code in:", "tekst"))
            code = QLabel(self.kas.data["code"])
            code.setStyleSheet("font-size: %dpt; font-weight: 800; color: #ffde3c; letter-spacing: 12px;" % round(48 * f))
            kl.addWidget(code)
            kl.addWidget(self.label("Vindt de telefoon de pc niet vanzelf? Vul dan dit adres in:  %s" % kd.eigen_ip(), "tekst"))
            ts = kd.tailscale_ip()
            if ts:
                kl.addWidget(self.label("Met Tailscale (thuis én onderweg):  %s" % ts, "tekst"))
            if self.kluis.laatst:
                t, n = self.kluis.laatst
                kl.addWidget(self.label("Laatst uitgewisseld met je telefoon: %s (%d veranderingen)."
                                        % (time.strftime("%d-%m %H:%M", time.localtime(t)), n), "klein"))
            kl.addWidget(self.label("Vraagt Windows om toegang voor DraveKas? Kies dan 'Toegang toestaan' (alleen privénetwerk).",
                                    "klein"))
        else:
            kl.addWidget(self.label("De pc kan nu niet gevonden worden door de telefoon (%s). Is DraveKas misschien twee keer "
                                    "geopend?" % self.kluis_fout, "tekst"))
        lay.addWidget(k)
        k2 = self.kaart()
        kl2 = QVBoxLayout(k2)
        kl2.setContentsMargins(24, 18, 24, 18)
        kl2.addWidget(self.label("Ook onderweg (keuze): via je eigen server", "kop"))
        kl2.addWidget(self.label("Draait er op je server een DraveKas-kluis (zie de snelgids)? Vul hier het adres en de code in. "
                                 "De pc wisselt dan elke tien minuten ook met de server, en je telefoon kan dat onderweg ook.",
                                 "tekst"))
        rij = QHBoxLayout()
        self.sadres = QLineEdit(self.inst.get("server", ""))
        self.sadres.setPlaceholderText("https://jouw-server.nl:8765")
        rij.addWidget(self.sadres, 3)
        self.scode = QLineEdit(self.inst.get("servercode", ""))
        self.scode.setPlaceholderText("Code van de server")
        rij.addWidget(self.scode, 1)
        kl2.addLayout(rij)
        kn = QHBoxLayout()
        ok = QPushButton("Bewaren en nu uitwisselen")
        ok.clicked.connect(self.bewaar_server)
        kn.addWidget(ok)
        kn.addStretch(1)
        kl2.addLayout(kn)
        self.serverstatus = self.label("", "klein")
        kl2.addWidget(self.serverstatus)
        lay.addWidget(k2)
        lay.addWidget(self.label("Een reservekopie van je boekje komt elke dag vanzelf in de map DraveKas-data\\reserve.", "klein"))
        lay.addStretch(1)

    def bewaar_server(self):
        self.inst["server"] = self.sadres.text().strip()
        self.inst["servercode"] = self.scode.text().strip()
        self.bewaar_inst()
        # de telefoon krijgt het serveradres ook (bij het volgende uitwisselen), zodat hij onderweg kan uitwisselen
        self.kas.zet(dict(id="server", soort="instelling", adres=self.inst["server"], code=self.inst["servercode"],
                          weg=not self.inst["server"]))
        self.serverstatus.setText("Bezig met uitwisselen..." if self.inst["server"] else "Geen server ingesteld.")
        self.met_server()

    def met_server(self):
        if not self.inst.get("server"):
            return
        threading.Thread(target=lambda: self.sig.server.emit(*kd.uitwisselen(self.kas, self.inst["server"],
                                                                             self.inst.get("servercode", ""))),
                         daemon=True).start()

    # ------------------------------------------------------------ Leon
    def lees_voor(self):
        if self.speler.playbackState() == QMediaPlayer.PlaybackState.PlayingState or self.wacht:
            self.beurt += 1
            self.rij, self.wacht = [], 0
            self.speler.stop()
            self.leesknop.setText("🔊  Lees voor")
            return
        m = self.kas.maand(self.ym)
        e = lambda c: kd.getal_woorden(round(abs(c) / 100)) + " euro"
        naam = kd.MAANDEN[int(self.ym[5:]) - 1]
        zinnen = ["In %s kwam er %s binnen." % (naam, e(m["inn"])), "Je gaf %s uit." % e(m["uit"])]
        if m["over"] >= 0:
            zinnen.append("Je hebt nog %s over." % e(m["over"]))
        else:
            zinnen.append("Let op: je komt %s tekort." % e(m["over"]))
        if m["per"]:
            zinnen.append("Het meeste ging naar %s: %s." % (kd.NAAM.get(m["per"][0][0], "").lower(), e(m["per"][0][1])))
        for d in self.kas.alle("doel"):
            g = self.kas.gespaard(d["id"])
            zinnen.append("Voor %s heb je %s gespaard, van de %s." % (d["naam"], e(g), e(d["doelbedrag"])))
        self.beurt += 1
        b = self.beurt
        self.rij, self.wacht = [], len(zinnen)
        self.leesknop.setText("■  Stop")
        if leon.status != "klaar":
            self.status.setText("Leon maakt zich klaar, een paar tellen...")
        threading.Thread(target=lambda: [self.sig.leon.emit(b, leon.maak(z, os.path.join(DATA, "leon")) or "") for z in zinnen],
                         daemon=True).start()

    def leon_binnen(self, b, pad):
        if b != self.beurt:
            return
        self.wacht -= 1
        if pad:
            self.rij.append(pad)
            if self.speler.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                self.volgende()
        elif leon.status == "geen":
            self.status.setText("Leon kan nu niet praten.")
        if not self.wacht and not self.rij and self.speler.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self.leesknop.setText("🔊  Lees voor")

    def volgende(self):
        if self.rij:
            self.speler.setSource(QUrl.fromLocalFile(self.rij.pop(0)))
            self.speler.play()
        elif not self.wacht:
            self.leesknop.setText("🔊  Lees voor")

    def speler_status(self, st):
        if st in (QMediaPlayer.MediaStatus.EndOfMedia, QMediaPlayer.MediaStatus.InvalidMedia):
            self.volgende()

    def closeEvent(self, e):
        self.kas.bewaar()
        if self.kluis:
            self.kluis.stop()
        super().closeEvent(e)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(NAAM)
    app.setFont(QFont("Segoe UI", 12))
    v = Venster()
    v.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

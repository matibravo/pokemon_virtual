#!/usr/bin/env python3
import fcntl
import math
import os
import random
import sys
import tempfile

from PyQt5.QtCore import Qt, QTimer, QSize, QRect, QRectF, QPointF
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen, QFont, QFontMetrics, QPainterPath, QImage, QMovie, QTransform
from PyQt5.QtWidgets import (QApplication, QLabel, QMenu, QAction)

# Config
MARGIN = 80
WALK_SPEED = 4.5
REACT_DUR = 1000.0
LOCK_FILE = '/tmp/gengar-pet.lock'

CHUCKLES = [
    "Jejeje... ¿Tienes miedo?",
    "Boo! No era para tanto...",
    "Soy tu peor pesadilla... tierna.",
    "¿Buscas a alguien más valiente?",
    "Shhh... no le digas a nadie que estoy aquí.",
    "Mwahahaha... *se ríe falsamente*",
    "Zzzz... eh, ¿me mirabas?",
    "Soy el fantasma de tus tareas pendientes.",
    "Puedo atravesar paredes... pero no puertas.",
    "Ten cuidado, te estoy vigilando... con cariño.",
    "¿Te he asustado ya? Dame otra oportunidad.",
    "Soy Gengar... pero en versión doméstica.",
    "No toques eso... ya lo toqué yo antes.",
    "Mmm... qué rico olor a miedo.",
    "Buuu~",
    "Yo también tenía sueño, pero tú me despertaste.",
    "El miedo es temporal... el cachondeo es eterno.",
    "Ni me acerco a tu código sin permiso.",
    "¡Oye! Deja de mirarme, me pongo nervioso.",
    "Soy un fantasma con clase.",
    "Acércate... un poquito más... nah, mejor no.",
    "Los fantasmas también merecen cariño.",
    "Entre fantasmas nos entendemos.",
    "Me caes bien... no se lo digas a nadie.",
]

# Pet configs
PETS = {
    'gengar': {
        'walk': 'gengar_walk.gif',
        'static': 'gengar.png',
        'scale': 3.33,
        'tongue': True,
    },
    'charmander': {
        'walk': 'charmander_walk.gif',
        'static': 'charmander.png',
        'scale': 5.0,
        'tongue': False,
    },
}

class Bubble(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.ToolTip | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        f = QFont()
        f.setPointSize(12)
        f.setBold(True)
        self.setFont(f)
        self.setStyleSheet("color: #101010;")
        self.setText("")
        self.hide()
        self.pad_x = 18
        self.pad_top = 14
        self.pad_bottom = 28
        self.max_w = 320
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)
        self.setFixedSize(180, 60)

    def show_text(self, text):
        fm = QFontMetrics(self.font())
        rect = fm.boundingRect(
            QRect(0, 0, self.max_w, 10000),
            Qt.TextWordWrap | Qt.AlignCenter,
            text,
        )
        w = max(140, min(self.max_w, rect.width())) + 2 * self.pad_x
        h = rect.height() + self.pad_top + self.pad_bottom
        self.setFixedSize(w, h)
        self.setContentsMargins(self.pad_x, self.pad_top, self.pad_x, self.pad_bottom)
        self.setText(text)
        self.show()
        self.timer.start(7000)

    def reposition(self, pet):
        g = QApplication.primaryScreen().geometry()
        x = pet.x() + pet.width() + 8
        y = pet.y() - self.height() - 4
        if x + self.width() > g.right():
            x = pet.x() - self.width() - 8
        if y < g.top():
            y = pet.y() + pet.height() + 4
        self.move(x, y)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        tail_h = 12
        body = QRectF(5, 5, self.width() - 10, self.height() - 5 - tail_h)
        path = QPainterPath()
        path.addRoundedRect(body, 12, 12)
        tail = QPainterPath()
        cx = self.width() / 2.0
        tail.moveTo(cx - 8, body.bottom() - 1)
        tail.lineTo(cx, body.bottom() + tail_h)
        tail.lineTo(cx + 8, body.bottom() - 1)
        tail.closeSubpath()
        path = path.united(tail)
        p.setPen(QPen(QColor(40, 30, 55, 220), 2))
        p.setBrush(QColor(255, 255, 255, 245))
        p.drawPath(path)
        super().paintEvent(e)

class Gengar(QLabel):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(False)
        self.setFocusPolicy(Qt.NoFocus)
        self.resize(200, 200)
        self.setScaledContents(False)

        self.bubble = Bubble()
        self.paused = False
        self.mode = 'gengar'
        self.cfg = PETS[self.mode]

        self.movie = None
        self.static_pm = None

        self.moving = False
        self.at_corner = True
        self.corner_i = 0
        self.xf, self.yf = 0.0, 0.0
        self.phase = 0.0
        self.dir = 1
        self.pause_left = 0.0
        self.react_t = 0.0
        self.tongue_out = False
        self.ghost_fade_t = 0.0

        self._pending_click = False
        self._ignore_release = False
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._single_click)

        self._load_assets()

        self.timer_step = QTimer(self)
        self.timer_step.timeout.connect(self._step)
        self.timer_step.start(40)

        self.react_timer = QTimer(self)
        self.react_timer.timeout.connect(self._react_update)
        self.react_timer.start(16)

        self.tongue_timer = QTimer(self)
        self.tongue_timer.setSingleShot(True)
        self.tongue_timer.timeout.connect(self._tongue)
        if self.cfg['tongue']:
            self.tongue_timer.start(random.randint(20000, 40000))

        self.tongue_off_timer = QTimer(self)
        self.tongue_off_timer.setSingleShot(True)
        self.tongue_off_timer.timeout.connect(self._tongue_off)

        self.ghost_timer = QTimer(self)
        self.ghost_timer.setSingleShot(True)
        self.ghost_timer.timeout.connect(self._start_ghost_fade)
        self.ghost_timer.start(random.randint(30000, 90000))

        self.context_menu = QMenu(self)
        self.act_joke = QAction("Cuenta un chiste", self)
        self.act_joke.triggered.connect(self._joke)
        self.act_pause = QAction("Pausar", self)
        self.act_pause.triggered.connect(self._toggle_pause)
        self.act_exit = QAction("Salir", self)
        self.act_exit.triggered.connect(QApplication.quit)
        self.context_menu.addAction(self.act_joke)
        self.context_menu.addAction(self.act_pause)
        self.context_menu.addAction(self.act_exit)

        self._place_initial()

    def _load_assets(self):
        base = os.path.dirname(os.path.abspath(__file__))
        cfg = self.cfg
        gif = os.path.join(base, cfg['walk'])
        png = os.path.join(base, cfg['static'])
        if self.movie:
            self.movie.stop()
        self.movie = QMovie(gif)
        self.movie.setSpeed(self.cfg.get('anim_speed', 60))
        self.static_pm = QPixmap(png)
        self.movie.frameChanged.connect(self._on_frame)
        self.movie.start()

    def _on_frame(self):
        pm = self.movie.currentPixmap().copy()
        if pm.isNull():
            pm = self.static_pm.copy()
        if self.cfg['tongue'] and self.tongue_out:
            pm = self._add_tongue(pm)
        w = int(pm.width() * self.cfg['scale'])
        h = int(pm.height() * self.cfg['scale'])
        if self.dir < 0:
            pm = pm.transformed(QTransform().scale(-1, 1))
        pm = pm.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if self.ghost_fade_t > 0:
            img = pm.toImage()
            alpha = int(160 + 95 * (1.0 - self.ghost_fade_t))
            for y in range(img.height()):
                for x in range(img.width()):
                    c = img.pixelColor(x, y)
                    if c.alpha() > 0:
                        img.setPixelColor(x, y, QColor(c.red(), c.green(), c.blue(), min(200, max(60, alpha))))
            pm = QPixmap.fromImage(img)
        self.setPixmap(pm)
        self.resize(pm.size())

    def _add_tongue(self, pm):
        img = pm.toImage().convertToFormat(QImage.Format_ARGB32)
        w, h = img.width(), img.height()
        rows = {}
        for y in range(h):
            rx = []
            for x in range(w):
                c = img.pixelColor(x, y)
                if c.alpha() > 60 and c.red() > 200 and c.green() > 185 and c.blue() > 185:
                    rx.append(x)
            if len(rx) >= 3:
                rows[y] = rx
        if not rows:
            return pm
        ybot = max(rows)
        tail = [y for y in rows if y >= ybot - 3]
        xs = [x for y in tail for x in rows[y]]
        cx = (min(xs) + max(xs)) // 2
        tw = max(12, int(w * 0.20))
        th = max(12, int(h * 0.22))
        x0, y0 = cx - tw // 2, ybot - 1
        p = QPixmap(pm)
        painter = QPainter(p)
        painter.setRenderHint(QPainter.Antialiasing, False)
        rect = QRectF(x0, y0, tw, th)
        path = QPainterPath()
        path.addRoundedRect(rect, tw * 0.6, th * 0.7)
        painter.setPen(QPen(QColor(0x66, 0x1A, 0x36), 1))
        painter.setBrush(QColor(0xFF, 0xA0, 0xD0))
        painter.drawPath(path)
        painter.end()
        return p

    def _tongue(self):
        if self.cfg['tongue']:
            self._show_tongue()
            self.tongue_timer.start(random.randint(22000, 45000))

    def _show_tongue(self, ms=2600):
        self.tongue_out = True
        self.tongue_off_timer.start(ms)

    def _tongue_off(self):
        self.tongue_out = False

    def _corners(self):
        g = QApplication.primaryScreen().geometry()
        L, T = g.left(), g.top()
        R, B = g.right(), g.bottom()
        w, h = self.width(), self.height()
        lx, rx = float(L + MARGIN), float(R - MARGIN - w)
        ty, by = float(T + MARGIN), float(B - MARGIN - h)
        return [(lx, by), (rx, by), (rx, ty), (lx, ty)]

    def _place_initial(self):
        c = self._corners()
        self.corner_i = random.randrange(4)
        self.xf, self.yf = c[self.corner_i]
        self.at_corner = True
        self.pause_left = random.uniform(2.0, 5.0)
        self.move(int(self.xf), int(self.yf))

    def _step(self):
        if self.bubble.isVisible():
            self.bubble.reposition(self)
        if self.paused:
            return
        if self.at_corner:
            self.pause_left -= 0.04
            if self.pause_left <= 0:
                self.at_corner = False
                self.corner_i = (self.corner_i + 1) % 4
        else:
            corners = self._corners()
            self.phase += 0.20
            tx, ty = corners[self.corner_i]
            dx, dy = tx - self.xf, ty - self.yf
            if abs(dx) >= abs(dy):
                self.xf += math.copysign(min(WALK_SPEED, abs(dx)), dx)
                self.yf = ty
                if abs(dx) > 0.01:
                    self.dir = 1 if dx > 0 else -1
            else:
                self.yf += math.copysign(min(WALK_SPEED, abs(dy)), dy)
                self.xf = tx
            self.moving = True
            if abs(tx - self.xf) < 0.5 and abs(ty - self.yf) < 0.5:
                self.xf, self.yf = float(tx), float(ty)
                self.at_corner = True
                self.pause_left = random.uniform(2.0, 6.0)
                self.moving = False

        bounce = abs(math.sin(self.phase)) * 7 if self.moving else 0.0
        flutter = 2.0 * math.sin(self.phase * 0.5)
        react = 0.0
        if self.react_t > 0:
            prog = 1.0 - (self.react_t / REACT_DUR)
            react = math.sin(math.pi * prog) * 26.0

        self.move(int(self.xf), int(self.yf - bounce - flutter - react))

    def _react_update(self):
        if self.react_t > 0:
            self.react_t -= 16.0
            if self.react_t <= 0:
                self.react_t = 0.0
                self.movie.start()
        if self.ghost_fade_t > 0:
            self.ghost_fade_t -= 0.016
            if self.ghost_fade_t <= 0:
                self.ghost_fade_t = 0.0
                self.setWindowOpacity(1.0)

    def _joke(self):
        self.react()

    def react(self):
        self.movie.jumpToFrame(0)
        self.react_t = REACT_DUR
        self._show_tongue(2800)
        if self.cfg['tongue']:
            QTimer.singleShot(300, lambda: self._show_tongue(2400))
        self.bubble.show_text(random.choice(CHUCKLES))
        if random.random() < 0.15:
            self._start_ghost_fade()

    def _start_ghost_fade(self):
        self.ghost_fade_t = 1.0
        self.ghost_timer.start(random.randint(45000, 120000))

    def _toggle_pause(self):
        self.paused = not self.paused
        self.act_pause.setText("Reanudar" if self.paused else "Pausar")
        if self.paused:
            self.movie.stop()
        else:
            self.movie.start()

    def contextMenuEvent(self, e):
        self.context_menu.exec_(e.globalPos())

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.context_menu.exec_(e.globalPos())
        else:
            super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            if self._ignore_release:
                self._ignore_release = False
            else:
                self._pending_click = True
                self._click_timer.start(220)
        else:
            super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._click_timer.stop()
            self._pending_click = False
            self._ignore_release = True
            self._switch_pet()
        else:
            super().mouseDoubleClickEvent(e)

    def _single_click(self):
        if self._pending_click:
            self._pending_click = False
            self.react()

    def _switch_pet(self):
        self.mode = 'charmander' if self.mode == 'gengar' else 'gengar'
        self.cfg = PETS[self.mode]
        # reset tongue timers based on pet
        if self.cfg['tongue']:
            self.tongue_timer.start(random.randint(20000, 40000))
            self.tongue_off_timer.stop()
            self.tongue_out = False
        else:
            self.tongue_timer.stop()
            self.tongue_off_timer.stop()
            self.tongue_out = False
        self._load_assets()
        # restart movie
        self.movie.start()

def main():
    if os.path.exists(LOCK_FILE):
        try:
            fd = os.open(LOCK_FILE, os.O_WRONLY | os.O_CREAT)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            sys.exit(0)
    else:
        fd = os.open(LOCK_FILE, os.O_WRONLY | os.O_CREAT)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            sys.exit(0)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    pet = Gengar()
    pet.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()

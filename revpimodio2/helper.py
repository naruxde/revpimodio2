# -*- coding: utf-8 -*-
#
# python3-RevPiModIO
#
# Webpage: https://revpimodio.org/
# (c) Sven Sager, License: LGPLv3
#
"""RevPiModIO Helperklassen und Tools."""
import warnings
from math import ceil
from threading import Event, Lock, Thread
from timeit import default_timer


class EventCallback(Thread):

    """Thread fuer das interne Aufrufen von Event-Funktionen.

    Der Eventfunktion, welche dieser Thread aufruft, wird der Thread selber
    als Parameter uebergeben. Darauf muss bei der definition der Funktion
    geachtet werden z.B. "def event(th):". Bei umfangreichen Funktionen kann
    dieser ausgewertet werden um z.B. doppeltes Starten zu verhindern.
    Ueber EventCallback.ioname kann der Name des IO-Objekts abgerufen werden,
    welches das Event ausgeloest hast. EventCallback.iovalue gibt den Wert des
    IO-Objekts zum Ausloesezeitpunkt zurueck.
    Der Thread stellt das EventCallback.exit Event als Abbruchbedingung fuer
    die aufgerufene Funktion zur Verfuegung.
    Durch Aufruf der Funktion EventCallback.stop() wird das exit-Event gesetzt
    und kann bei Schleifen zum Abbrechen verwendet werden.
    Mit dem .exit() Event auch eine Wartefunktion realisiert
    werden: "th.exit.wait(0.5)" - Wartet 500ms oder bricht sofort ab, wenn
    fuer den Thread .stop() aufgerufen wird.

    while not th.exit.is_set():
        # IO-Arbeiten
        th.exit.wait(0.5)

    """

    def __init__(self, func, name, value):
        """Init EventCallback class.

        @param func Funktion die beim Start aufgerufen werden soll
        @param name IO-Name
        @param value IO-Value zum Zeitpunkt des Events

        """
        super().__init__()
        self.daemon = True
        self.exit = Event()
        self.func = func
        self.ioname = name
        self.iovalue = value

    def run(self):
        """Ruft die registrierte Funktion auf."""
        self.func(self)

    def stop(self):
        """Setzt das exit-Event mit dem die Funktion beendet werden kann."""
        self.exit.set()


class Cycletools():

    """Werkzeugkasten fuer Cycleloop-Funktion.

    Diese Klasse enthaelt Werkzeuge fuer Zyklusfunktionen, wie Taktmerker
    und Flankenmerker.
    Zu beachten ist, dass die Flankenmerker beim ersten Zyklus alle den Wert
    True haben! Ueber den Merker Cycletools.first kann ermittelt werden,
    ob es sich um den ersten Zyklus handelt.

    Taktmerker flag1c, flag5c, flag10c, usw. haben den als Zahl angegebenen
    Wert an Zyklen jeweils False und True.
    Beispiel: flag5c hat 5 Zyklen den Wert False und in den naechsten 5 Zyklen
    den Wert True.

    Flankenmerker flank5c, flank10c, usw. haben immer im, als Zahl angebenen
    Zyklus fuer einen Zyklusdurchlauf den Wert True, sonst False.
    Beispiel: flank5c hat immer alle 5 Zyklen den Wert True.

    Diese Merker koennen z.B. verwendet werden um, an Outputs angeschlossene,
    Lampen synchron blinken zu lassen.

    """

    def __init__(self, cycletime):
        """Init Cycletools class."""
        self.__cycle = 0
        self.__cycletime = cycletime
        self.__ucycle = 0
        self.__dict_ton = {}
        self.__dict_tof = {}
        self.__dict_tp = {}

        # Taktmerker
        self.first = True
        self.flag1c = False
        self.flag5c = False
        self.flag10c = False
        self.flag15c = False
        self.flag20c = False

        # Flankenmerker
        self.flank5c = True
        self.flank10c = True
        self.flank15c = True
        self.flank20c = True

    def _docycle(self):
        """Zyklusarbeiten."""
        # Einschaltverzoegerung
        for tof in self.__dict_tof:
            if self.__dict_tof[tof] > 0:
                self.__dict_tof[tof] -= 1

        # Ausschaltverzoegerung
        for ton in self.__dict_ton:
            if self.__dict_ton[ton][1]:
                if self.__dict_ton[ton][0] > 0:
                    self.__dict_ton[ton][0] -= 1
                self.__dict_ton[ton][1] = False
            else:
                self.__dict_ton[ton][0] = -1

        # Impuls
        for tp in self.__dict_tp:
            if self.__dict_tp[tp][1]:
                if self.__dict_tp[tp][0] > 0:
                    self.__dict_tp[tp][0] -= 1
                else:
                    self.__dict_tp[tp][1] = False
            else:
                self.__dict_tp[tp][0] = -1

        # Flankenmerker
        self.flank5c = False
        self.flank10c = False
        self.flank15c = False
        self.flank20c = False

        # Logische Flags
        self.first = False
        self.flag1c = not self.flag1c

        # Berechnete Flags
        self.__cycle += 1
        if self.__cycle == 5:
            self.__ucycle += 1
            if self.__ucycle == 3:
                self.flank15c = True
                self.flag15c = not self.flag15c
                self.__ucycle = 0
            if self.flag5c:
                if self.flag10c:
                    self.flank20c = True
                    self.flag20c = not self.flag20c
                self.flank10c = True
                self.flag10c = not self.flag10c
            self.flank5c = True
            self.flag5c = not self.flag5c
            self.__cycle = 0

    def get_tof(self, name):
        """Wert der Ausschaltverzoegerung.
        @param name Eindeutiger Name des Timers
        @return Wert <class 'bool'> der Ausschaltverzoegerung"""
        return self.__dict_tof.get(name, 0) > 0

    def get_tofc(self, name):
        """Wert der Ausschaltverzoegerung.
        @param name Eindeutiger Name des Timers
        @return Wert <class 'bool'> der Ausschaltverzoegerung"""
        return self.__dict_tof.get(name, 0) > 0

    def set_tof(self, name, milliseconds):
        """Startet bei Aufruf einen ausschaltverzoegerten Timer.

        @param name Eindeutiger Name fuer Zugriff auf Timer
        @param milliseconds Verzoegerung in Millisekunden

        """
        self.__dict_tof[name] = ceil(milliseconds / self.__cycletime)

    def set_tofc(self, name, cycles):
        """Startet bei Aufruf einen ausschaltverzoegerten Timer.

        @param name Eindeutiger Name fuer Zugriff auf Timer
        @param cycles Zyklusanzahl, der Verzoegerung wenn nicht neu gestartet

        """
        self.__dict_tof[name] = cycles

    def get_ton(self, name):
        """Einschaltverzoegerung.
        @param name Eindeutiger Name des Timers
        @return Wert <class 'bool'> der Einschaltverzoegerung"""
        return self.__dict_ton.get(name, [-1])[0] == 0

    def get_tonc(self, name):
        """Einschaltverzoegerung.
        @param name Eindeutiger Name des Timers
        @return Wert <class 'bool'> der Einschaltverzoegerung"""
        return self.__dict_ton.get(name, [-1])[0] == 0

    def set_ton(self, name, milliseconds):
        """Startet einen einschaltverzoegerten Timer.

        @param name Eindeutiger Name fuer Zugriff auf Timer
        @param milliseconds Millisekunden, der Verzoegerung wenn neu gestartet

        """
        if self.__dict_ton.get(name, [-1])[0] == -1:
            self.__dict_ton[name] = \
                [ceil(milliseconds / self.__cycletime), True]
        else:
            self.__dict_ton[name][1] = True

    def set_tonc(self, name, cycles):
        """Startet einen einschaltverzoegerten Timer.

        @param name Eindeutiger Name fuer Zugriff auf Timer
        @param cycles Zyklusanzahl, der Verzoegerung wenn neu gestartet

        """
        if self.__dict_ton.get(name, [-1])[0] == -1:
            self.__dict_ton[name] = [cycles, True]
        else:
            self.__dict_ton[name][1] = True

    def get_tp(self, name):
        """Impulstimer.
        @param name Eindeutiger Name des Timers
        @return Wert <class 'bool'> des Impulses"""
        return self.__dict_tp.get(name, [-1])[0] > 0

    def get_tpc(self, name):
        """Impulstimer.
        @param name Eindeutiger Name des Timers
        @return Wert <class 'bool'> des Impulses"""
        return self.__dict_tp.get(name, [-1])[0] > 0

    def set_tp(self, name, milliseconds):
        """Startet einen Impuls Timer.

        @param name Eindeutiger Name fuer Zugriff auf Timer
        @param milliseconds Millisekunden, die der Impuls anstehen soll

        """
        if self.__dict_tp.get(name, [-1])[0] == -1:
            self.__dict_tp[name] = \
                [ceil(milliseconds / self.__cycletime), True]
        else:
            self.__dict_tp[name][1] = True

    def set_tpc(self, name, cycles):
        """Startet einen Impuls Timer.

        @param name Eindeutiger Name fuer Zugriff auf Timer
        @param cycles Zyklusanzahl, die der Impuls anstehen soll

        """
        if self.__dict_tp.get(name, [-1])[0] == -1:
            self.__dict_tp[name] = [cycles, True]
        else:
            self.__dict_tp[name][1] = True


class ProcimgWriter(Thread):

    """Klasse fuer Synchroniseriungs-Thread.

    Diese Klasse wird als Thread gestartet, wenn das Prozessabbild zyklisch
    synchronisiert werden soll. Diese Funktion wird hauptsaechlich fuer das
    Event-Handling verwendet.

    """

    def __init__(self, parentmodio):
        """Init ProcimgWriter class.
        @param parentmodio Parent Object"""
        super().__init__()
        self._adjwait = 0
        self._ioerror = 0
        self._maxioerrors = 0
        self._modio = parentmodio
        self._refresh = 0.05
        self._work = Event()

        self.daemon = True
        self.lck_refresh = Lock()
        self.newdata = Event()

    def _get_ioerrors(self):
        """Ruft aktuelle Anzahl der Fehler ab.
        @return Aktuelle Fehleranzahl"""
        return self._ioerror

    def _gotioerror(self):
        """IOError Verwaltung fuer autorefresh."""
        self._ioerror += 1
        if self._maxioerrors != 0 and self._ioerror >= self._maxioerrors:
            raise RuntimeError(
                "reach max io error count {} on process image".format(
                    self._maxioerrors
                )
            )
        warnings.warn(
            "count {} io errors on process image".format(self._ioerror),
            RuntimeWarning
        )

    def get_maxioerrors(self):
        """Gibt die Anzahl der maximal erlaubten Fehler zurueck.
        @return Anzahl erlaubte Fehler"""
        return self._maxioerrors

    def get_refresh(self):
        """Gibt Zykluszeit zurueck.
        @return <class 'int'> Zykluszeit in Millisekunden"""
        return int(self._refresh * 1000)

    def run(self):
        """Startet die automatische Prozessabbildsynchronisierung."""
        fh = self._modio._create_myfh()
        self._adjwait = self._refresh
        while not self._work.is_set():
            ot = default_timer()

            # Lockobjekt holen und Fehler werfen, wenn nicht schnell genug
            if not self.lck_refresh.acquire(timeout=self._adjwait):
                warnings.warn(
                    "cycle time of {} ms exceeded on lock".format(
                        int(self._refresh * 1000)
                    ),
                    RuntimeWarning
                )
                continue

            try:
                fh.seek(0)
                bytesbuff = bytearray(fh.read(self._modio._length))
            except IOError:
                self._gotioerror()
                self.lck_refresh.release()
                self._work.wait(self._adjwait)
                continue

            if self._modio._monitoring:
                # Inputs und Outputs in Puffer
                for dev in self._modio._lst_refresh:
                    dev._filelock.acquire()
                    dev._ba_devdata[:] = bytesbuff[dev._slc_devoff]
                    dev._filelock.release()
            else:
                # Inputs in Puffer, Outputs in Prozessabbild
                ioerr = False
                for dev in self._modio._lst_refresh:
                    dev._filelock.acquire()
                    dev._ba_devdata[dev._slc_inp] = bytesbuff[dev._slc_inpoff]
                    try:
                        fh.seek(dev._slc_outoff.start)
                        fh.write(dev._ba_devdata[dev._slc_out])
                    except IOError:
                        ioerr = True
                    finally:
                        dev._filelock.release()

                if self._modio._buffedwrite:
                    try:
                        fh.flush()
                    except IOError:
                        ioerr = True

                if ioerr:
                    self._gotioerror()
                    self.lck_refresh.release()
                    self._work.wait(self._adjwait)
                    continue

            self.lck_refresh.release()

            # Alle aufwecken
            self.newdata.set()
            self._work.wait(self._adjwait)

            # Wartezeit anpassen um echte self._refresh zu erreichen
            if default_timer() - ot >= self._refresh:
                self._adjwait -= 0.001
                if self._adjwait < 0:
                    warnings.warn(
                        "cycle time of {} ms exceeded".format(
                            int(self._refresh * 1000)
                        ),
                        RuntimeWarning
                    )
                    self._adjwait = 0
            else:
                self._adjwait += 0.001

        # Alle am Ende erneut aufwecken
        self.newdata.set()
        fh.close()

    def stop(self):
        """Beendet die automatische Prozessabbildsynchronisierung."""
        self._work.set()

    def set_maxioerrors(self, value):
        """Setzt die Anzahl der maximal erlaubten Fehler.
        @param value Anzahl erlaubte Fehler"""
        if type(value) == int and value >= 0:
            self._maxioerrors = value
        else:
            raise ValueError("value must be 0 or a positive integer")

    def set_refresh(self, value):
        """Setzt die Zykluszeit in Millisekunden.
        @param value <class 'int'> Millisekunden"""
        if type(value) == int and 10 <= value <= 2000:
            waitdiff = self._refresh - self._adjwait
            self._refresh = value / 1000
            self._adjwait = self._refresh - waitdiff
        else:
            raise ValueError(
                "refresh time must be 10 to 2000 milliseconds"
            )

    ioerrors = property(_get_ioerrors)
    maxioerrors = property(get_maxioerrors, set_maxioerrors)
    refresh = property(get_refresh, set_refresh)

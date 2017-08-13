#
# python3-RevPiModIO
#
# Webpage: https://revpimodio.org/
# (c) Sven Sager, License: LGPLv3
#
# -*- coding: utf-8 -*-
import warnings

from . import app as appmodule
from . import device as devicemodule
from . import helper as helpermodule
from . import io as iomodule
from . import summary as summarymodule

from .__init__ import RISING, FALLING, BOTH

from json import load as jload
from os import access, F_OK, R_OK
from signal import signal, SIG_DFL, SIGINT, SIGTERM
from threading import Thread, Event


class RevPiModIO(object):

    """Klasse fuer die Verwaltung aller piCtory Informationen.

    Diese Klasse uebernimmt die gesamte Konfiguration aus piCtory und bilded
    die Devices und IOs ab. Sie uebernimmt die exklusive Verwaltung des
    Prozessabbilds und stellt sicher, dass die Daten synchron sind.
    Sollten nur einzelne Devices gesteuert werden, verwendet man
    RevPiModIOSelected() und uebergibt bei Instantiierung eine Liste mit
    Device Positionen oder Device Namen.

    """

    def __init__(self, **kwargs):
        """Instantiiert die Grundfunktionen.

        @param kwargs Weitere Parameter:
            - auto_refresh: Wenn True, alle Devices zu auto_refresh hinzufuegen
            - configrsc: Pfad zur piCtory Konfigurationsdatei
            - procimg: Pfad zum Prozessabbild
            - monitoring: In- und Outputs werden gelesen, niemals geschrieben
            - simulator: Laed das Modul als Simulator und vertauscht IOs
            - syncoutputs: Aktuell gesetzte Outputs vom Prozessabbild einlesen

        """
        self._auto_refresh = kwargs.get("auto_refresh", False)
        self._configrsc = kwargs.get("configrsc", None)
        self._monitoring = kwargs.get("monitoring", False)
        self._procimg = kwargs.get("procimg", "/dev/piControl0")
        self._simulator = kwargs.get("simulator", False)
        self._syncoutputs = kwargs.get("syncoutputs", True)

        # TODO: bei simulator und procimg prüfen ob datei existiert / anlegen?

        # Private Variablen
        self.__cleanupfunc = None
        self._buffedwrite = False
        self._device = []
        self._exit = Event()
        self._imgwriter = None
        self._length = 0
        self._looprunning = False
        self._lst_devselect = []
        self._lst_refresh = []
        self._myfh = self._create_myfh()
        self._th_mainloop = None
        self._waitexit = Event()

        # Modulvariablen
        self.core = None

        # piCtory Klassen
        self.app = None
        self.device = None
        self.devices = None
        self.io = None
        self.summary = None

        # Nur Konfigurieren, wenn nicht vererbt
        if type(self) == RevPiModIO:
            self._configure()

    def __del__(self):
        """Zerstoert alle Klassen um aufzuraeumen."""
        self.exit(full=True)
        self._myfh.close()

    def __evt_exit(self, signum, sigframe):
        """Eventhandler fuer Programmende.
        @param signum Signalnummer
        @param sigframe Signalframe"""
        signal(SIGINT, SIG_DFL)
        signal(SIGTERM, SIG_DFL)
        self.exit(full=True)
        if self.__cleanupfunc is not None:
            self.readprocimg()
            self.__cleanupfunc()
            self.writeprocimg()

    def _configure(self):
        """Verarbeitet die piCtory Konfigurationsdatei."""
        jconfigrsc = self.get_jconfigrsc()

        # App Klasse instantiieren
        self.app = appmodule.App(jconfigrsc["App"])

        # Devicefilter anwenden
        if len(self._lst_devselect) > 0:
            lst_found = []

            if type(self) == RevPiModIODriver:
                _searchtype = "VIRTUAL"
            else:
                _searchtype = None

            # Angegebene Devices suchen
            for dev in jconfigrsc["Devices"]:
                if _searchtype is None or dev["type"] == _searchtype:
                    if dev["name"] in self._lst_devselect:
                        lst_found.append(dev)
                    elif dev["position"].isnumeric() \
                            and int(dev["position"]) in self._lst_devselect:
                        lst_found.append(dev)

        # Devices aus JSON oder Filter übernehmen
        lst_devices = jconfigrsc["Devices"] if len(self._lst_devselect) == 0 \
            else lst_found

        # Device und IO Klassen anlegen
        self.device = devicemodule.DeviceList()
        self.io = iomodule.IOList()

        # Devices initialisieren
        err_names = []
        for device in sorted(lst_devices, key=lambda x: x["position"]):

            # Bei VDev in alter piCtory Version, Position eindeutig machen
            if device["position"] == "adap.":
                device["position"] = -1
                # NOTE: Testen mit alter piCtory Version
                while device["position"] in self.device:
                    device["position"] -= 1

            if device["type"] == "BASE":
                # Core
                dev_new = devicemodule.Core(
                    self, device, simulator=self._simulator
                )
                self.core = dev_new

                # Für RS485 errors defaults laden und schreiben
                # NOTE: Soll das wirklich gemacht werden?
                for io in dev_new.get_outs():
                    io.set_value(io.defaultvalue)
                if not self._monitoring:
                    self.writeprocimg(True, dev_new)

            elif device["type"] == "LEFT_RIGHT":
                # IOs
                dev_new = devicemodule.Device(
                    self, device, simulator=self._simulator
                )
            elif device["type"] == "VIRTUAL":
                # Virtuals
                dev_new = devicemodule.Virtual(
                    self, device, simulator=self._simulator
                )
            elif device["type"] == "EDGE":
                # Gateways
                dev_new = devicemodule.Gateway(
                    self, device, simulator=self._simulator
                )
            else:
                # Device-Type nicht gefunden
                warnings.warn(
                    "device type {} unknown",
                    Warning
                )
                dev_new = None

            if dev_new is not None:
                self._device.append(dev_new)

                # Offset prüfen, muss mit Länge übereinstimmen
                if self._length < dev_new.offset:
                    self._length = dev_new.offset

                self._length += dev_new._length

                # Auf doppelte Namen prüfen, da piCtory dies zulässt
                if hasattr(self.device, dev_new.name):
                    err_names.append(dev_new.name)

                # DeviceList für direkten Zugriff aufbauen
                setattr(self.device, dev_new.name, dev_new)

        # dict_devname zerstören, wenn doppelte Namen vorhanden sind
        for errdev in err_names:
            delattr(self.device, errdev)
            warnings.warn(
                "equal device name in pictory configuration. can not "
                "build device to acces by name. you can access all devices "
                "by position number pos_XX only!",
                Warning
            )

        # ImgWriter erstellen
        self._imgwriter = helpermodule.ProcimgWriter(self)

        # Aktuellen Outputstatus von procimg einlesen
        if self._syncoutputs:
            self.syncoutputs(force=True)

        # NOTE: Nur noch bis Final für kompatibilität
        # Devices Klasse instantiieren
        self.devices = devicemodule.Devicelist(self)

        # Optional ins auto_refresh aufnehmen
        if self._auto_refresh:
            for dev in self._device:
                dev.auto_refresh()

        # Summary Klasse instantiieren
        self.summary = summarymodule.Summary(jconfigrsc["Summary"])

    def _create_myfh(self):
        """Erstellt FileObject mit Pfad zum procimg.
        return FileObject"""
        self._buffedwrite = False
        return open(self._procimg, "r+b", 0)

    def _get_configrsc(self):
        """Getter function.
        @return Pfad der verwendeten piCtory Konfiguration"""
        return self._configrsc

    def _get_cycletime(self):
        """Gibt Aktualisierungsrate in ms der Prozessabbildsynchronisierung aus.
        @return Millisekunden"""
        return self._imgwriter.refresh

    def _get_length(self):
        """Getter function.
        @return Laenge in Bytes der Devices"""
        return self._length

    def _get_monitoring(self):
        """Getter function.
        @return True, wenn als Monitoring gestartet"""
        return self._monitoring

    def _get_procimg(self):
        """Getter function.
        @return Pfad des verwendeten Prozessabbilds"""
        return self._procimg

    def _get_simulator(self):
        """Getter function.
        @return True, wenn als Simulator gestartet"""
        return self._simulator

    def _set_cycletime(self, milliseconds):
        """Setzt Aktualisierungsrate der Prozessabbild-Synchronisierung.
        @param milliseconds int() in Millisekunden"""
        self._imgwriter.refresh = milliseconds

    def auto_refresh_maxioerrors(self, value=None):
        """Maximale IO Fehler fuer auto_refresh.
        @param value Setzt maximale Anzahl bis exception ausgeloest wird
        @return Maximale Anzahl bis exception ausgeloest wird"""
        if value is None:
            return self._imgwriter.maxioerrors
        elif type(value) == int and value >= 0:
            self._imgwriter.maxioerrors = value

    def auto_refresh_resetioerrors(self):
        """Setzt aktuellen IOError-Zaehler auf 0 zurueck."""
        self._imgwriter.maxioerrors = 0

    def cleanup(self):
        """Beendet auto_refresh und alle Threads."""
        # TODO: wirklich alles löschen
        self.exit(full=True)
        self._myfh.close()
        self.app = None
        self.device = None
        self.devices = None
        self.io = None
        self.summary = None

    def cycleloop(self, func, cycletime=50):
        """Startet den Cycleloop.

        Der aktuelle Programmthread wird hier bis Aufruf von
        RevPiDevicelist.exit() "gefangen". Er fuehrt nach jeder Aktualisierung
        des Prozessabbilds die uebergebene Funktion "func" aus und arbeitet sie
        ab. Waehrend der Ausfuehrung der Funktion wird das Prozessabbild nicht
        weiter aktualisiert. Die Inputs behalten bis zum Ende den aktuellen
        Wert. Gesetzte Outputs werden nach Ende des Funktionsdurchlaufs in das
        Prozessabbild geschrieben.

        Verlassen wird der Cycleloop, wenn die aufgerufene Funktion einen
        Rueckgabewert nicht gleich None liefert, oder durch Aufruf von
        revpimodio.exit().

        HINWEIS: Die Aktualisierungszeit und die Laufzeit der Funktion duerfen
        die eingestellte auto_refresh Zeit, bzw. uebergebene cycletime nicht
        ueberschreiten!

        Ueber den Parameter cycletime kann die Aktualisierungsrate fuer das
        Prozessabbild gesetzt werden (selbe Funktion wie
        set_refreshtime(milliseconds)).

        @param func Funktion, die ausgefuehrt werden soll
        @param cycletime auto_refresh Wert in Millisekunden
        @return None

        """
        # Prüfen ob ein Loop bereits läuft
        if self._looprunning:
            raise RuntimeError(
                "can not start multiple loops mainloop/cycleloop"
            )

        # Prüfen ob Devices in auto_refresh sind
        if len(self._lst_refresh) == 0:
            raise RuntimeError("no device with auto_refresh activated")

        # Prüfen ob Funktion callable ist
        if not callable(func):
            raise RuntimeError(
                "registered function '{}' ist not callable".format(func)
            )

        # Zykluszeit übernehmen
        if cycletime != self._imgwriter.refresh:
            self._imgwriter.refresh = cycletime

        # Cycleloop starten
        self._looprunning = True
        cycleinfo = helpermodule.Cycletools()
        ec = None
        while ec is None and not self._exit.is_set():
            # Auf neue Daten warten und nur ausführen wenn set()
            if not self._imgwriter.newdata.wait(2.5):
                if not self._exit.is_set() and not self._imgwriter.is_alive():
                    raise RuntimeError("auto_refresh thread not running")
                continue
            self._imgwriter.newdata.clear()

            # Vor Aufruf der Funktion auto_refresh sperren
            self._imgwriter.lck_refresh.acquire()

            # Funktion aufrufen und auswerten
            ec = func(cycleinfo)
            cycleinfo._docycle()

            # auto_refresh freigeben
            self._imgwriter.lck_refresh.release()

        # Cycleloop beenden
        self._looprunning = False

        return ec

    def exit(self, full=True):
        """Beendet mainloop() und optional auto_refresh.

        Wenn sich das Programm im mainloop() befindet, wird durch Aufruf
        von exit() die Kontrolle wieder an das Hauptprogramm zurueckgegeben.

        Der Parameter full ist mit True vorbelegt und entfernt alle Devices aus
        dem auto_refresh. Der Thread fuer die Prozessabbildsynchronisierung
        wird dann gestoppt und das Programm kann sauber beendet werden.

        @param full Entfernt auch alle Devices aus auto_refresh"""
        self._exit.set()
        self._waitexit.set()
        if full:
            if self._imgwriter.is_alive():
                self._imgwriter.stop()
                self._imgwriter.join(self._imgwriter._refresh)
            while len(self._lst_refresh) > 0:
                dev = self._lst_refresh.pop()
                dev._selfupdate = False
                if not self._monitoring:
                    self.writeprocimg(True, dev)

    def get_jconfigrsc(self):
        """Laed die piCotry Konfiguration und erstellt ein dict().
        @return dict() der piCtory Konfiguration"""
        # piCtory Konfiguration prüfen
        if self._configrsc is not None:
            if not access(self._configrsc, F_OK | R_OK):
                raise RuntimeError(
                    "can not access pictory configuration at {}".format(
                        self._configrsc))
        else:
            # piCtory Konfiguration an bekannten Stellen prüfen
            lst_rsc = ["/etc/revpi/config.rsc", "/opt/KUNBUS/config.rsc"]
            for rscfile in lst_rsc:
                if access(rscfile, F_OK | R_OK):
                    self._configrsc = rscfile
                    break
            if self._configrsc is None:
                raise RuntimeError(
                    "can not access known pictory configurations at {} - "
                    "use 'configrsc' parameter so specify location"
                    "".format(", ".join(lst_rsc))
                )

        with open(self._configrsc, "r") as fhconfigrsc:
            return jload(fhconfigrsc)

    def handlesignalend(self, cleanupfunc=None):
        """Signalhandler fuer Programmende verwalten.

        Wird diese Funktion aufgerufen, uebernimmt RevPiModIO die SignalHandler
        fuer SIGINT und SIGTERM. Diese werden Empfangen, wenn das
        Betriebssystem oder der Benutzer das Steuerungsprogramm sauber beenden
        will.

        Die optionale Funktion "cleanupfunc" wird als letztes nach dem letzten
        Einlesen der Inputs ausgefuehrt. Dort gesetzte Outputs werden nach
        Ablauf der Funktion ein letztes Mal geschrieben.
        Gedacht ist dies fuer Aufraeumarbeiten, wie z.B. das abschalten der
        LEDs am RevPi-Core.

        Nach einmaligem Empfangen eines der Signale und dem Beenden der
        RevPiModIO Thrads / Funktionen werden die SignalHandler wieder
        freigegeben.

        @param cleanupfunc Funktion wird nach dem letzten Lesen der Inputs
        ausgefuehrt, gefolgt vom letzten Schreiben der Outputs

        """
        # Prüfen ob Funktion callable ist
        if not callable(cleanupfunc):
            raise RuntimeError(
                "registered function '{}' ist not callable".format(cleanupfunc)
            )
        self.__cleanupfunc = cleanupfunc
        signal(SIGINT, self.__evt_exit)
        signal(SIGTERM, self.__evt_exit)

    def mainloop(self, freeze=False, blocking=True):
        """Startet den Mainloop mit Eventueberwachung.

        Der aktuelle Programmthread wird hier bis Aufruf von
        RevPiDevicelist.exit() "gefangen" (es sei denn blocking=False). Er
        durchlaeuft die Eventueberwachung und prueft Aenderungen der, mit
        einem Event registrierten, IOs. Wird eine Veraenderung erkannt,
        fuert das Programm die dazugehoerigen Funktionen der Reihe nach aus.

        Wenn der Parameter "freeze" mit True angegeben ist, wird die
        Prozessabbildsynchronisierung angehalten bis alle Eventfunktionen
        ausgefuehrt wurden. Inputs behalten fuer die gesamte Dauer ihren
        aktuellen Wert und Outputs werden erst nach Durchlauf aller Funktionen
        in das Prozessabbild geschrieben.

        Wenn der Parameter "blocking" mit False angegeben wird, aktiviert
        dies die Eventueberwachung und blockiert das Programm NICHT an der
        Stelle des Aufrufs. Eignet sich gut fuer die GUI Programmierung, wenn
        Events vom RevPi benoetigt werden, aber das Programm weiter ausgefuehrt
        werden soll.

        @param freeze Wenn True, Prozessabbildsynchronisierung anhalten
        @param blocking Wenn False, blockiert das Programm NICHT
        @return None

        """
        # Prüfen ob ein Loop bereits läuft
        if self._looprunning:
            raise RuntimeError(
                "can not start multiple loops mainloop/cycleloop"
            )

        # Prüfen ob Devices in auto_refresh sind
        if len(self._lst_refresh) == 0:
            raise RuntimeError("no device with auto_refresh activated")

        # Thread erstellen, wenn nicht blockieren soll
        if not blocking:
            self._th_mainloop = Thread(
                target=self.mainloop,
                kwargs={"freeze": freeze, "blocking": True}
            )
            self._th_mainloop.start()
            return

        # Event säubern vor Eintritt in Mainloop
        self._exit.clear()
        self._looprunning = True

        # Beim Eintritt in mainloop Bytecopy erstellen
        for dev in self._lst_refresh:
            dev._filelock.acquire()
            dev._ba_datacp = dev._ba_devdata[:]
            dev._filelock.release()

        lst_fire = []
        while not self._exit.is_set():

            # Auf neue Daten warten und nur ausführen wenn set()
            if not self._imgwriter.newdata.wait(2.5):
                if not self._exit.is_set() and not self._imgwriter.is_alive():
                    raise RuntimeError("auto_refresh thread not running")
                continue

            self._imgwriter.newdata.clear()

            # Während Auswertung refresh sperren
            self._imgwriter.lck_refresh.acquire()

            for dev in self._lst_refresh:

                if len(dev._dict_events) == 0 \
                        or dev._ba_datacp == dev._ba_devdata:
                    continue

                for io_event in dev._dict_events:

                    if dev._ba_datacp[io_event.slc_address] == \
                            dev._ba_devdata[io_event.slc_address]:
                        continue

                    if io_event._bitaddress >= 0:
                        boolcp = bool(int.from_bytes(
                            dev._ba_datacp[io_event.slc_address],
                            byteorder=io_event._byteorder
                        ) & 1 << io_event._bitaddress)
                        boolor = bool(int.from_bytes(
                            dev._ba_devdata[io_event.slc_address],
                            byteorder=io_event._byteorder
                        ) & 1 << io_event._bitaddress)

                        if boolor == boolcp:
                            continue

                        for regfunc in dev._dict_events[io_event]:
                            if regfunc[1] == BOTH \
                                    or regfunc[1] == RISING and boolor \
                                    or regfunc[1] == FALLING and not boolor:
                                lst_fire.append(
                                    (regfunc, io_event.name, io_event.value)
                                )

                    else:
                        for regfunc in dev._dict_events[io_event]:
                            lst_fire.append(
                                (regfunc, io_event.name, io_event.value)
                            )

                # Nach Verarbeitung aller IOs die Bytes kopieren
                dev._filelock.acquire()
                dev._ba_datacp = dev._ba_devdata[:]
                dev._filelock.release()

            # Refreshsperre aufheben wenn nicht freeze
            if not freeze:
                self._imgwriter.lck_refresh.release()

            # Erst nach Datenübernahme alle Events feuern
            while len(lst_fire) > 0:
                tup_fire = lst_fire.pop()
                event_func = tup_fire[0][0]
                passname = tup_fire[1]
                passvalue = tup_fire[2]
                if tup_fire[0][2]:
                    th = helpermodule.EventCallback(
                        event_func, passname, passvalue
                    )
                    th.start()
                else:
                    # Direct callen da Prüfung in RevPiDevice.reg_event ist
                    event_func(passname, passvalue)

            # Refreshsperre aufheben wenn freeze
            if freeze:
                self._imgwriter.lck_refresh.release()

        # Mainloop verlassen
        self._looprunning = False

    def readprocimg(self, force=False, device=None):
        """Einlesen aller Inputs aller/eines Devices vom Prozessabbild.

        @param force auch Devices mit autoupdate=False
        @param device nur auf einzelnes Device anwenden
        @return True, wenn Arbeiten an allen Devices erfolgreich waren

        """
        if device is None:
            mylist = self._device
        else:
            # TODO: Devicesuchen ändern
            dev = device if issubclass(type(device), devicemodule.Device) \
                else self.device.__getitem__(device)

            if dev._selfupdate:
                raise RuntimeError(
                    "can not read process image, while device '{}|{}'"
                    "is in auto_refresh mode".format(dev.position, dev.name)
                )
            mylist = [dev]

        # Daten komplett einlesen
        try:
            self._myfh.seek(0)
            bytesbuff = self._myfh.read(self._length)
        except IOError:
            warnings.warn(
                "read error on process image '{}'".format(self.myfh.name),
                RuntimeWarning
            )
            return False

        for dev in mylist:
            if (force or dev.autoupdate) and not dev._selfupdate:

                # FileHandler sperren
                dev._filelock.acquire()

                if self._monitoring:
                    # Alles vom Bus einlesen
                    dev._ba_devdata[:] = bytesbuff[dev.slc_devoff]
                else:
                    # Inputs vom Bus einlesen
                    dev._ba_devdata[dev.slc_inp] = bytesbuff[dev.slc_inpoff]

                    # Mems vom Bus lesen
                    dev._ba_devdata[dev.slc_mem] = bytesbuff[dev.slc_memoff]

                dev._filelock.release()

        return True

    def setdefaultvalues(self, force=False, device=None):
        """Alle Outputbuffer werden auf die piCtory default Werte gesetzt.
        @param force auch Devices mit autoupdate=False
        @param device nur auf einzelnes Device anwenden"""
        if self._monitoring:
            raise RuntimeError(
                "can not set default values, while system is in monitoring "
                "mode"
            )

        if device is None:
            mylist = self._device
        else:
            dev = device if issubclass(type(device), devicemodule.Device) \
                else self.__getitem__(device)
            mylist = [dev]

        for dev in mylist:
            if (force or dev.autoupdate):
                for io in dev.get_outs():
                    io.set_value(io.defaultvalue)

    def syncoutputs(self, force=False, device=None):
        """Lesen aller aktuell gesetzten Outputs im Prozessabbild.

        @param force auch Devices mit autoupdate=False
        @param device nur auf einzelnes Device anwenden
        @return True, wenn Arbeiten an allen Devices erfolgreich waren

        """
        if device is None:
            mylist = self._device
        else:
            dev = device if issubclass(type(device), devicemodule.Device) \
                else self.__getitem__(device)

            if dev._selfupdate:
                raise RuntimeError(
                    "can not sync process image, while device '{}|{}'"
                    "is in auto_refresh mode".format(dev.position, dev.name)
                )
            mylist = [dev]

        try:
            self._myfh.seek(0)
            bytesbuff = self._myfh.read(self._length)
        except IOError:
            warnings.warn(
                "read error on process image '{}'".format(self._myfh.name),
                RuntimeWarning
            )
            return False

        for dev in mylist:
            if (force or dev.autoupdate) and not dev._selfupdate:
                dev._filelock.acquire()
                # Outputs vom Bus einlesen
                dev._ba_devdata[dev.slc_out] = bytesbuff[dev.slc_outoff]
                dev._filelock.release()
        return True

    def writedefaultinputs(self, virtual_device):
        """Schreibt fuer ein virtuelles Device piCtory Defaultinputwerte.

        Sollten in piCtory Defaultwerte fuer Inputs eines virtuellen Devices
        angegeben sein, werden diese nur beim Systemstart oder einem piControl
        Reset gesetzt. Sollte danach das Prozessabbild mit NULL ueberschrieben,
        gehen diese Werte verloren.
        Diese Funktion kann nur auf virtuelle Devices angewendet werden!

        @param virtual_device Virtuelles Device fuer Wiederherstellung
        @return True, wenn Arbeiten am virtuellen Device erfolgreich waren

        """
        if self._monitoring:
            raise RuntimeError(
                "can not write process image, while system is in monitoring "
                "mode"
            )

        # Device suchen
        dev = virtual_device if issubclass(type(virtual_device), devicemodule.Device) \
            else self.__getitem__(virtual_device)

        # Prüfen ob es ein virtuelles Device ist
        if not issubclass(type(dev), devicemodule.Virtual):
            raise RuntimeError(
                "this function can be used for virtual devices only"
            )

        workokay = True
        dev._filelock.acquire()

        for io in dev.get_inps():
            dev._ba_devdata[io.slc_address] = io.defaultvalue

        # Outpus auf Bus schreiben
        try:
            self._myfh.seek(dev.slc_inpoff.start)
            self._myfh.write(dev._ba_devdata[dev.slc_inp])
            if self._buffedwrite:
                self._myfh.flush()
        except IOError:
            warnings.warn(
                "write error on process image '{}'"
                "".format(self._myfh.name),
                RuntimeWarning
            )
            workokay = False

        dev._filelock.release()
        return workokay

    def writeprocimg(self, force=False, device=None):
        """Schreiben aller Outputs aller Devices ins Prozessabbild.

        @param force auch Devices mit autoupdate=False
        @param device nur auf einzelnes Device anwenden
        @return True, wenn Arbeiten an allen Devices erfolgreich waren

        """
        if self._monitoring:
            raise RuntimeError(
                "can not write process image, while system is in monitoring "
                "mode"
            )

        if device is None:
            mylist = self._device
        else:
            dev = device if issubclass(type(device), devicemodule.Device) \
                else self.__getitem__(device)

            if dev._selfupdate:
                raise RuntimeError(
                    "can not write process image, while device '{}|{}'"
                    "is in auto_refresh mode".format(dev.position, dev.name)
                )
            mylist = [dev]

        workokay = True
        for dev in mylist:
            if (force or dev.autoupdate) and not dev._selfupdate:
                dev._filelock.acquire()

                # Outpus auf Bus schreiben
                try:
                    self._myfh.seek(dev.slc_outoff.start)
                    self._myfh.write(dev._ba_devdata[dev.slc_out])
                except IOError:
                    workokay = False

                dev._filelock.release()

        if self._buffedwrite:
            try:
                self._myfh.flush()
            except IOError:
                workokay = False

        if not workokay:
            warnings.warn(
                "write error on process image '{}'"
                "".format(self._myfh.name),
                RuntimeWarning
            )

        return workokay

    configrsc = property(_get_configrsc)
    cycletime = property(_get_cycletime, _set_cycletime)
    length = property(_get_length)
    monitoring = property(_get_monitoring)
    procimg = property(_get_procimg)
    simulator = property(_get_simulator)


class RevPiModIOSelected(RevPiModIO):

    """Klasse fuer die Verwaltung einzelner Devices aus piCtory.

    Diese Klasse uebernimmt nur angegebene Devices der piCtory Konfiguration
    und bilded sie inkl. IOs ab. Sie uebernimmt die exklusive Verwaltung des
    Adressbereichs im Prozessabbild an dem sich die angegebenen Devices
    befinden und stellt sicher, dass die Daten synchron sind.

    """

    def __init__(self, deviceselection, **kwargs):
        """Instantiiert nur fuer angegebene Devices die Grundfunktionen.

        Der Parameter deviceselection kann eine einzelne
        Device Position / einzelner Device Name sein oder eine Liste mit
        mehreren Positionen / Namen

        @param deviceselection Positionsnummer oder Devicename
        @param kwargs Weitere Parameter
        @see #RevPiModIO.__init__ RevPiModIO.__init__(...)

        """
        super().__init__(**kwargs)

        # Device liste erstellen
        if type(deviceselection) == list:
            for dev in deviceselection:
                self._lst_devselect.append(dev)
        else:
            self._lst_devselect.append(deviceselection)

        for vdev in self._lst_devselect:
            if type(vdev) != int and type(vdev) != str:
                raise ValueError(
                    "need device position as int() or device name as str()"
                )

        self._configure()

        if len(self._device) == 0:
            if type(self) == RevPiModIODriver:
                raise RuntimeError(
                    "could not find any given VIRTUAL devices in config"
                )
            else:
                raise RuntimeError(
                    "could not find any given devices in config"
                )
        elif len(self._device) != len(self._lst_devselect):
            if type(self) == RevPiModIODriver:
                raise RuntimeError(
                    "could not find all given VIRTUAL devices in config"
                )
            else:
                raise RuntimeError(
                    "could not find all given devices in config"
                )


class RevPiModIODriver(RevPiModIOSelected):

    """Klasse um eigene Treiber fuer die virtuellen Devices zu erstellen.

    Mit dieser Klasse werden nur angegebene Virtuelle Devices mit RevPiModIO
    verwaltet. Bei Instantiierung werden automatisch die Inputs und Outputs
    verdreht, um das Schreiben der Inputs zu ermoeglichen. Die Daten koennen
    dann ueber logiCAD an den Devices abgerufen werden.

    """

    def __init__(self, vdev, **kwargs):
        """Instantiiert die Grundfunktionen.

        @param vdev Virtuelles Device fuer die Verwendung / oder list()
        @param kwargs Weitere Parameter (nicht monitoring und simulator)
        @see #RevPiModIO.__init__ RevPiModIO.__init__(...)

        """
        kwargs["monitoring"] = False
        kwargs["simulator"] = True
        super().__init__(vdev, **kwargs)

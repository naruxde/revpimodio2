#
# python3-RevPiModIO
#
# Webpage: https://revpimodio.org/
# (c) Sven Sager, License: LGPLv3
#
# -*- coding: utf-8 -*-
import struct
from .helper import ProcimgWriter
from .io import IOBase, IOType, IntIO, StructIO
from .__init__ import BOTH
from threading import Lock


class DeviceList(object):

    """Basisklasse fuer direkten Zugriff auf Device Objekte."""

    def __init__(self):
        """Init DeviceList class."""
        self.__dict_position = {}

    def __contains__(self, key):
        """Prueft ob Device existiert.
        @param key DeviceName str() / Positionsnummer int()
        @return True, wenn Device vorhanden"""
        if type(key) == int:
            return key in self.__dict_position
        else:
            return hasattr(self, key)

    def __getitem__(self, key):
        """Gibt angegebenes Device zurueck.
        @param key DeviceName str() / Positionsnummer int()
        @return Gefundenes Device()-Objekt"""
        if type(key) == int:
            return self.__dict_position[key]
        else:
            return getattr(self, key)

    def __setattr__(self, key, value):
        """Setzt Attribute nur wenn Device.
        @param key Attributname
        @param value Attributobjekt"""
        if issubclass(type(value), Device):
            object.__setattr__(self, key, value)
            self.__dict_position[value.position] = value
        elif key == "_DeviceList__dict_position":
            object.__setattr__(self, key, value)


class Devicelist():

    """Enthaelt alle Devices des RevolutionPi Buses."""

    def __init__(self, parentmodio):
        """Instantiiert die einzelnen Bus-Devices.

        @param procimg Dateiname des piControl Devices

        """
        self._modio = parentmodio
        self.core = self._modio.core

    def __contains__(self, key):
        """Prueft ob Device existiert.
        @param key DeviceName str() / Positionsnummer int()
        @return True, wenn device vorhanden"""
        return key in self._modio.device

    def __getitem__(self, key):
        """Gibt angegebenes Device zurueck.
        @param key DeviceName str() / Positionsnummer int()
        @return Gefundenes RevPiDevice()-Objekt"""
        return self._modio.device[key]

    def __iter__(self):
        """Gibt alle Devices zurueck.
        @return Iterator alle Devices"""
        return iter(self._modio._device)

    def __len__(self):
        """Gibt Anzahl der Devices zurueck.
        @return int() Anzahl der Devices"""
        return len(self._modio._device)

    def auto_refresh(self, device, remove=False):
        """Registriert ein Device fuer die automatische Synchronisierung.
        @param device Device fuer Synchronisierung
        @param remove bool() True entfernt Device aus Synchronisierung"""

        dev = device if issubclass(type(device), Device) \
            else self._modio.device[device]

        dev.auto_refresh(remove)

    def auto_refresh_maxioerrors(self, value=None):
        """Maximale IO Fehler fuer auto_refresh.
        @param value Setzt maximale Anzahl bis exception ausgeloest wird
        @return Maximale Anzahl bis exception ausgeloest wird"""
        return self._modio.auto_refresh_maxioerrors(value)

    def auto_refresh_resetioerrors(self):
        """Setzt aktuellen IOError-Zaehler auf 0 zurueck."""
        self._modio.auto_refresh_resetioerrors()

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
        return self._modio.cycleloop(func, cycletime)

    def exit(self, full=True):
        """Beendet mainloop() und optional auto_refresh.

        Wenn sich das Programm im mainloop() befindet, wird durch Aufruf
        von exit() die Kontrolle wieder an das Hauptprogramm zurueckgegeben.

        Der Parameter full ist mit True vorbelegt und entfernt alle Devices aus
        dem auto_refresh. Der Thread fuer die Prozessabbildsynchronisierung
        wird dann gestoppt und das Programm kann sauber beendet werden.

        @param full Entfernt auch alle Devices aus auto_refresh"""
        self._modio.exit(full)

    def get_devbyname(self, name):
        """Gibt durch Namen angegebenes Device zurueck.
        @param name Devicename aus piCtory
        @return Gefundenes RevPiDevice()"""
        return self._modio.device[name]

    def get_devbyposition(self, position):
        """Gibt durch Position angegebenes Device zurueck.
        @param position Deviceposition aus piCtory
        @return Gefundenes RevPiDevice()"""
        return self._modio.device[position]

    def get_refreshtime(self):
        """Gibt Aktualisierungsrate in ms der Prozessabbildsynchronisierung aus.
        @return Millisekunden"""
        return self._modio._imgwriter.refresh

    def readprocimg(self, force=False, device=None):
        """Einlesen aller Inputs aller Devices vom Prozessabbild.

        @param force auch Devices mit autoupdate=False
        @param device nur auf einzelnes Device anwenden
        @return True, wenn Arbeiten an allen Devices erfolgreich waren

        """
        return self._modio.readprocimg(force, device)

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
        return self._modio.mainloop(freeze, blocking)

    def set_refreshtime(self, milliseconds):
        """Setzt Aktualisierungsrate der Prozessabbild-Synchronisierung.
        @param milliseconds int() in Millisekunden"""
        self._modio.set_refreshtime(milliseconds)

    def setdefaultvalues(self, force=False, device=None):
        """Alle Outputbuffer werden auf die piCtory default Werte gesetzt.
        @param force auch Devices mit autoupdate=False
        @param device nur auf einzelnes Device anwenden"""
        self._modio.setdefaultvalues(force, device)

    def syncoutputs(self, force=False, device=None):
        """Lesen aller aktuell gesetzten Outputs im Prozessabbild.

        @param force auch Devices mit autoupdate=False
        @param device nur auf einzelnes Device anwenden
        @return True, wenn Arbeiten an allen Devices erfolgreich waren

        """
        return self._modio.syncoutputs(force, device)

    def updateprocimg(self, force=False, device=None):
        """Schreiben/Lesen aller Outputs/Inputs aller Devices im Prozessab.

        @param force auch Devices mit autoupdate=False
        @param device nur auf einzelnes Device anwenden
        @return True, wenn Arbeiten an allen Devices erfolgreich waren

        """
        return self.readprocimg(force=force, device=device) and \
            self.writeprocimg(force=force, device=device)

    def wait(self, device, io, **kwargs):
        """Wartet auf Wertaenderung eines IOs.

        Die Wertaenderung wird immer uerberprueft, wenn fuer Devices
        in RevPiDevicelist.auto_refresh() neue Daten gelesen wurden.

        Bei Wertaenderung, wird das Warten mit 0 als Rueckgabewert beendet.

        HINWEIS: Wenn RevPiProcimgWriter() keine neuen Daten liefert, wird
        bis in die Ewigkeit gewartet (nicht bei Angabe von "timeout").

        Wenn edge mit RISING oder FALLING angegeben wird muss diese Flanke
        ausgeloest werden. Sollte der Wert 1 sein beim Eintritt mit Flanke
        RISING, wird das Warten erst bei Aenderung von 0 auf 1 beendet.

        Als exitevent kann ein threading.Event()-Objekt uebergeben werden,
        welches das Warten bei is_set() sofort mit 1 als Rueckgabewert
        beendet.

        Wenn der Wert okvalue an dem IO fuer das Warten anliegt, wird
        das Warten sofort mit -1 als Rueckgabewert beendet.

        Der Timeoutwert bricht beim Erreichen das Warten sofort mit
        Wert 2 Rueckgabewert ab. (Das Timeout wird ueber die Zykluszeit
        der auto_refresh Funktion berechnet, entspricht also nicht exact den
        angegeben Millisekunden! Es wird immer nach oben gerundet!)

        @param device Device auf dem sich der IO befindet
        @param io Name des IOs auf dessen Aenderung gewartet wird
        @param kwargs Weitere Parameter:
            - edge: Flanke RISING, FALLING, BOTH bei der mit True beendet wird
            - exitevent: thrading.Event() fuer vorzeitiges Beenden mit False
            - okvalue: IO-Wert, bei dem das Warten sofort mit True beendet wird
            - timeout: Zeit in ms nach der mit False abgebrochen wird
        @return int() erfolgreich Werte <= 0
            - Erfolgreich gewartet
                Wert 0: IO hat den Wert gewechselt
                Wert -1: okvalue stimmte mit IO ueberein
            - Fehlerhaft gewartet
                Wert 1: exitevent wurde gesetzt
                Wert 2: timeout abgelaufen
                Wert 100: RevPiDevicelist.exit() wurde aufgerufen

        """
        dev = device if issubclass(type(device), Device) \
            else self.__getitem__(device)

        io_watch = dev[io]
        if type(io_watch) == list:
            if len(io_watch) == 1:
                io_watch = io_watch[0]
            else:
                raise KeyError(
                    "byte '{}' contains more than one bit-input".format(io)
                )

        # kwargs auswerten
        edge = kwargs.get("edge", BOTH)
        evt_exit = kwargs.get("exitevent", None)
        val_ok = kwargs.get("okvalue", None)
        flt_timeout = kwargs.get("timeout", 0)

        return io_watch.wait(edge, evt_exit, val_ok, flt_timeout)

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
        return self._modio.writedefaultinputs(virtual_device)

    def writeprocimg(self, force=False, device=None):
        """Schreiben aller Outputs aller Devices ins Prozessabbild.

        @param force auch Devices mit autoupdate=False
        @param device nur auf einzelnes Device anwenden
        @return True, wenn Arbeiten an allen Devices erfolgreich waren

        """
        return self._modio.writeprocimg(force, device)


class Device(object):

    """Basisklasse fuer alle Device-Objekte der RevPiDevicelist()-Klasse.

    Die Basisfunktionalitaet generiert bei Instantiierung alle IOs und
    erweitert den Prozessabbildpuffer um die benoetigten Bytes. Ueber diese
    Klasse oder von dieser abgeleiteten Klassen, werden alle IOs angesprochen.
    Sie verwaltet ihren Prozessabbildpuffer und sorgt fuer die Aktualisierung
    der IO-Werte.

    """

    def __init__(self, parentmodio, dict_device, **kwargs):
        """Instantiierung der Device()-Klasse.

        @param parent RevpiModIO parent object
        @param dict_device dict() fuer dieses Device aus piCotry Konfiguration
        @param kwargs Weitere Parameter:
            - autoupdate: Wenn True fuehrt dieses Device Arbeiten am
              Prozessabbild bei Aufruf der RevPiDevicelist-Funktionen aus
            - simulator: Laed das Modul als Simulator und vertauscht IOs

        """
        self._modio = parentmodio

        self._dict_events = {}
        self._filelock = Lock()
        self._length = 0
        self._lst_io = []
        self._selfupdate = False

        self.autoupdate = kwargs.get("autoupdate", True)

        # Wertzuweisung aus dict_device
        self.name = dict_device.pop("name")
        self.offset = int(dict_device.pop("offset"))
        self.position = int(dict_device.pop("position"))
        self.producttype = int(dict_device.pop("productType"))

        # Neues bytearray und Kopie für mainloop anlegen
        self._ba_devdata = bytearray()
        self._ba_datacp = bytearray()

        # Erst inp/out/mem poppen, dann in Klasse einfügen
        if kwargs.get("simulator", False):
            self.slc_inp = self._buildio(dict_device.pop("out"), IOType.INP)
            self.slc_out = self._buildio(dict_device.pop("inp"), IOType.OUT)
        else:
            self.slc_inp = self._buildio(dict_device.pop("inp"), IOType.INP)
            self.slc_out = self._buildio(dict_device.pop("out"), IOType.OUT)
        self.slc_mem = self._buildio(dict_device.pop("mem"), IOType.MEM)

        # Alle IOs nach Adresse sortieren
        self._lst_io.sort(key=lambda x: x.slc_address.start)

        # SLCs mit offset berechnen
        self.slc_devoff = slice(self.offset, self.offset + self._length)
        self.slc_inpoff = slice(
            self.slc_inp.start + self.offset, self.slc_inp.stop + self.offset
        )
        self.slc_outoff = slice(
            self.slc_out.start + self.offset, self.slc_out.stop + self.offset
        )
        self.slc_memoff = slice(
            self.slc_mem.start + self.offset, self.slc_mem.stop + self.offset
        )

        # Alle restlichen attribute an Klasse anhängen
        self.__dict__.update(dict_device)

        # Spezielle Konfiguration von abgeleiteten Klassen durchführen
        self._devconfigure()

    def __bytes__(self):
        """Gibt alle Daten des Devices als bytes() zurueck.
        @return Devicedaten als bytes()"""
        return bytes(self._ba_devdata)

    def __contains__(self, key):
        """Prueft ob IO existiert.
        @param key IO-Name str() / Positionsnummer int()
        @return True, wenn device vorhanden"""
        if type(key) == str:
            return hasattr(self._modio.io, key)
        if type(key) == int:
            key += self.offset
            return key in self._modio.io \
                and len(self._modio.io[key]) > 0
        else:
            return key in self._lst_io

    def __getitem__(self, key):
        """Gibt angegebenes IO-Objekt zurueck.
        @param key Name order Byteadresse des IOs
        @return IO-Objekt wenn Name, sonst list() mit IO-Objekt"""
        if type(key) == int:
            key += self.offset
            if key in self._modio.io:
                return self._modio.io[key]
            else:
                raise KeyError("byte '{}' does not exist".format(key))
        else:
            if hasattr(self._modio.io, key):
                return getattr(self._modio.io, key)
            else:
                raise KeyError("'{}' does not exist".format(key))

    def __int__(self):
        """Gibt die Positon im RevPi Bus zurueck.
        @return Positionsnummer"""
        return self.position

    def __iter__(self):
        """Gibt Iterator aller IOs zurueck.
        @return iter() aller IOs"""
        return iter(self._lst_io)

    def __str__(self):
        """Gibt den Namen des Devices zurueck.
        @return Devicename"""
        return self.name

    def __setitem__(self, key, value):
        """Setzt den Wert des angegebenen Inputs.
        @param key Name oder Byte des Inputs
        @param value Wert der gesetzt werden soll"""
        if type(key) == int:
            key += self.offset
            if key in self._modio.io:
                if len(self._modio.io[key]) == 1:
                    self._modio.io[key][0].value = value
                elif len(self._modio.io[key]) == 0:
                    raise KeyError("byte '{}' contains no input".format(key))
                else:
                    raise KeyError(
                        "byte '{}' contains more than one bit-input"
                        "".format(key)
                    )
            else:
                raise KeyError("byte '{}' does not exist".format(key))
        else:
            getattr(self._modio.io, key).value = value

    def _buildio(self, dict_io, iotype):
        """Erstellt aus der piCtory-Liste die IOs fuer dieses Device.

        @param dict_io dict()-Objekt aus piCtory Konfiguration
        @param iotype IOType() Wert
        @return slice()-Objekt mit Start und Stop Position dieser IOs

        """
        if len(dict_io) > 0:
            int_min, int_max = 4096, 0
            for key in sorted(dict_io, key=lambda x: int(x)):

                # Neuen IO anlegen
                if bool(dict_io[key][7]) or self.producttype == 95:
                    # Bei Bitwerten oder Core RevPiIOBase verwenden
                    io_new = IOBase(
                        self,
                        dict_io[key],
                        iotype,
                        byteorder="little"
                    )
                else:
                    io_new = IntIO(
                        self,
                        dict_io[key],
                        iotype,
                        byteorder="little"
                    )

                # IO registrieren
                if hasattr(self._modio.io, io_new.name):
                    raise NameError(
                        "name '{}' already exists on device '{}'".format(
                            io_new._name, self.name
                        )
                    )
                else:
                    # Namesregister aufbauen
                    setattr(self._modio.io, io_new._name, io_new)

                    # Speicherbereich zuweisen
                    self._ba_devdata.extend(bytes(io_new._length))

                    # IO eintragen
                    self._lst_io.append(io_new)
                    self._length += io_new._length

                # Kleinste und größte Speicheradresse ermitteln
                if io_new.slc_address.start < int_min:
                    int_min = io_new.slc_address.start
                if io_new.slc_address.stop > int_max:
                    int_max = io_new.slc_address.stop

            return slice(int_min, int_max)

        else:
            return slice(0, 0)

    def _devconfigure(self):
        """Funktion zum ueberschreiben von abgeleiteten Klassen."""
        pass

    def auto_refresh(self, remove=False):
        """Registriert ein Device fuer die automatische Synchronisierung.
        @param remove bool() True entfernt Device aus Synchronisierung"""
        if not remove and self not in self._modio._lst_refresh:

            # Daten bei Aufnahme direkt einlesen!
            self._modio.readprocimg(True, self)

            # Datenkopie anlegen
            self._filelock.acquire()
            self._ba_datacp = self._ba_devdata[:]
            self._filelock.release()

            self._selfupdate = True
            self._modio._lst_refresh.append(self)

            # Thread starten, wenn er noch nicht läuft
            if not self._modio._imgwriter.is_alive():

                # Alte Einstellungen speichern
                imgmaxioerrors = self._modio._imgwriter.maxioerrors
                imgrefresh = self._modio._imgwriter.refresh

                # ImgWriter mit alten Einstellungen erstellen
                self._modio._imgwriter = ProcimgWriter(self._modio)
                self._modio._imgwriter.maxioerrors = imgmaxioerrors
                self._modio._imgwriter.refresh = imgrefresh
                self._modio._imgwriter.start()

        elif remove and self in self._modio._lst_refresh:
            # Sicher aus Liste entfernen
            with self._modio._imgwriter.lck_refresh:
                self._modio._lst_refresh.remove(self)
            self._selfupdate = False

            # Beenden, wenn keien Devices mehr in Liste sind
            if len(self._modio._lst_refresh) == 0:
                self._modio._imgwriter.stop()

            # Daten beim Entfernen noch einmal schreiben
            if not self._modio._monitoring:
                self._modio.writeprocimg(True, self)

    def get_inps(self):
        """Gibt eine Liste aller Inputs zurueck.
        @return list() Inputs"""
        return [
            io for io in self._lst_io if io._iotype == IOType.INP
        ]

    def get_outs(self):
        """Gibt eine Liste aller Outputs zurueck.
        @return list() Outputs"""
        return [
            io for io in self._lst_io if io._iotype == IOType.OUT
        ]

    def get_mems(self):
        """Gibt eine Liste aller mems zurueck.
        @return list() Mems"""
        return [
            io for io in self._lst_io if io._iotype == IOType.MEM
        ]

    def get_iobyabsaddress(self, address):
        """Gibt das IO-Objekt an angegebenen Byte im Prozessabbild zurueck.
        @param address Byteadresse im Prozessabbild
        @return list() mit IO-Objekt/en"""
        return self[address - self.offset]

    def get_iobyaddress(self, address):
        """Gibt das IO-Objekt an angegebenen Byte des Devices zurueck.
        @param address Byteadresse im Deviceabbild
        @return list() mit IO-Objekt/en"""
        return self[address]

    def get_iobyname(self, name):
        """Gibt das IO-Objekt mit angegebenen Namen zurueck.
        @param name Name des IO-Objekts
        @return IO-Objekt"""
        return getattr(self._modio.io, name)

    def reg_event(self, io_name, func, edge=BOTH, as_thread=False):
        """Registriert ein Event bei der Eventueberwachung.

        @param io_name Name des Inputs oder Outputs der ueberwacht wird
        @param func Funktion die bei Aenderung aufgerufen werden soll
        @param edge Ausfuehren bei RISING, FALLING or BOTH Wertaenderung
        @param as_thread Bei True, Funktion als RevPiCallback-Thread ausfuehren

        """
        io_event = self.__getitem__(io_name)
        if type(io_event) == list:
            if len(io_event) == 1:
                io_event = io_event[0]
            elif len(io_event) == 0:
                raise KeyError(
                    "byte '{}' contains no io object".format(io_name))
            else:
                raise KeyError(
                    "byte '{}' contains more than one bit io object".format(
                        io_name
                    )
                )

        # NOTE: Abgelaufen
        io_event.reg_event(func, edge, as_thread)

    def unreg_event(self, io_name, func=None, edge=None):
        """Entfernt ein Event aus der Eventueberwachung.

        @param io_name Name des Inputs, dessen Events entfert werden sollen
        @param func Nur Events mit angegebener Funktion
        @param edge Nur Events mit angegebener Funktion und angegebener Edge

        """
        io_event = self.__getitem__(io_name)
        if type(io_event) == list:
            if len(io_event) == 1:
                io_event = io_event[0]
            elif len(io_event) == 0:
                raise KeyError(
                    "byte '{}' contains no io object".format(io_name))
            else:
                raise KeyError(
                    "byte '{}' contains more than one bit io object".format(
                        io_name
                    )
                )

        # NOTE: Abgelaufen
        io_event.unreg_event(func, edge)


class Core(Device):

    """Klasse fuer den RevPi Core.

    Stellt Funktionen fuer die LEDs und den Status zur Verfuegung.

    """

    def _devconfigure(self):
        """Core-Klasse vorbereiten."""
        self._iocycle = None
        self._iotemperatur = None
        self._iofrequency = None
        self._ioerrorcnt = None
        self._ioled = 1
        self._ioerrorlimit1 = None
        self._ioerrorlimit2 = None

        int_lenio = len(self._lst_io)
        if int_lenio == 6:
            # Core 1.1
            self._iocycle = 1
            self._ioerrorcnt = 2
            self._ioled = 3
            self._ioerrorlimit1 = 4
            self._ioerrorlimit2 = 5
        elif int_lenio == 8:
            # core 1.2
            self._iocycle = 1
            self._ioerrorcnt = 2
            self._iotemperatur = 3
            self._iofrequency = 4
            self._ioled = 5
            self._ioerrorlimit1 = 6
            self._ioerrorlimit2 = 7

    def _errorlimit(self, io_id, errorlimit):
        """Verwaltet das Lesen und Schreiben der ErrorLimits.
        @param io_id Index des IOs fuer ErrorLimit
        @return Aktuellen ErrorLimit oder None wenn nicht verfuegbar"""
        if errorlimit is None:
            return None if io_id is None else int.from_bytes(
                self._lst_io[io_id].get_value(),
                byteorder=self._lst_io[io_id]._byteorder
            )
        else:
            if 0 <= errorlimit <= 65535:
                self._lst_io[io_id].set_value(errorlimit.to_bytes(
                    2, byteorder=self._lst_io[io_id]._byteorder
                ))
            else:
                raise ValueError(
                    "errorlimit value int() must be between 0 and 65535"
                )

    def get_status(self):
        """Gibt den RevPi Core Status zurueck.
        @return Status als int()"""
        return int.from_bytes(
            self._lst_io[0].get_value(), byteorder=self._lst_io[0]._byteorder
        )

    def get_leda1(self):
        """Gibt den Zustand der LED A1 vom core zurueck.
        @return 0=aus, 1=gruen, 2=rot"""
        int_led = int.from_bytes(
            self._lst_io[self._ioled].get_value(),
            byteorder=self._lst_io[self._ioled]._byteorder
        )
        led = int_led & 1
        led += int_led & 2
        return led

    def get_leda2(self):
        """Gibt den Zustand der LED A2 vom core zurueck.
        @return 0=aus, 1=gruen, 2=rot"""
        int_led = int.from_bytes(
            self._lst_io[self._ioled].get_value(),
            byteorder=self._lst_io[self._ioled]._byteorder
        )
        led = 1 if bool(int_led & 4) else 0
        led = led + 2 if bool(int_led & 8) else led
        return led

    def set_leda1(self, value):
        """Setzt den Zustand der LED A1 vom core.
        @param value 0=aus, 1=gruen, 2=rot"""
        if 0 <= value <= 3:
            int_led = (self.get_leda2() << 2) + value
            self._lst_io[self._ioled].set_value(int_led.to_bytes(
                length=1, byteorder=self._lst_io[self._ioled]._byteorder
            ))
        else:
            raise ValueError("led status int() must be between 0 and 3")

    def set_leda2(self, value):
        """Setzt den Zustand der LED A2 vom core.
        @param value 0=aus, 1=gruen, 2=rot"""
        if 0 <= value <= 3:
            int_led = (value << 2) + self.get_leda1()
            self._lst_io[self._ioled].set_value(int_led.to_bytes(
                length=1, byteorder=self._lst_io[self._ioled]._byteorder
            ))
        else:
            raise ValueError("led status int() must be between 0 and 3")

    A1 = property(get_leda1, set_leda1)
    A2 = property(get_leda2, set_leda2)
    status = property(get_status)

    @property
    def picontrolrunning(self):
        """Statusbit fuer piControl-Treiber laeuft.
        @return True, wenn Treiber laeuft"""
        return bool(int.from_bytes(
            self._lst_io[0].get_value(),
            byteorder=self._lst_io[0]._byteorder
        ) & 1)

    @property
    def unconfdevice(self):
        """Statusbit fuer ein IO-Modul nicht mit PiCtory konfiguriert.
        @return True, wenn IO Modul nicht konfiguriert"""
        return bool(int.from_bytes(
            self._lst_io[0].get_value(),
            byteorder=self._lst_io[0]._byteorder
        ) & 2)

    @property
    def missingdeviceorgate(self):
        """Statusbit fuer ein IO-Modul fehlt oder piGate konfiguriert.
        @return True, wenn IO-Modul fehlt oder piGate konfiguriert"""
        return bool(int.from_bytes(
            self._lst_io[0].get_value(),
            byteorder=self._lst_io[0]._byteorder
        ) & 4)

    @property
    def overunderflow(self):
        """Statusbit Modul belegt mehr oder weniger Speicher als konfiguriert.
        @return True, wenn falscher Speicher belegt ist"""
        return bool(int.from_bytes(
            self._lst_io[0].get_value(),
            byteorder=self._lst_io[0]._byteorder
        ) & 8)

    @property
    def leftgate(self):
        """Statusbit links vom RevPi ist ein piGate Modul angeschlossen.
        @return True, wenn piGate links existiert"""
        return bool(int.from_bytes(
            self._lst_io[0].get_value(),
            byteorder=self._lst_io[0]._byteorder
        ) & 16)

    @property
    def rightgate(self):
        """Statusbit rechts vom RevPi ist ein piGate Modul angeschlossen.
        @return True, wenn piGate rechts existiert"""
        return bool(int.from_bytes(
            self._lst_io[0].get_value(),
            byteorder=self._lst_io[0]._byteorder
        ) & 32)

    @property
    def iocycle(self):
        """Gibt Zykluszeit der Prozessabbildsynchronisierung zurueck.
        @return Zykluszeit in ms"""
        return None if self._iocycle is None else int.from_bytes(
            self._lst_io[self._iocycle].get_value(),
            byteorder=self._lst_io[self._iocycle]._byteorder
        )

    @property
    def temperatur(self):
        """Gibt CPU-Temperatur zurueck.
        @return CPU-Temperatur in Celsius"""
        return None if self._iotemperatur is None else int.from_bytes(
            self._lst_io[self._iotemperatur].get_value(),
            byteorder=self._lst_io[self._iotemperatur]._byteorder
        )

    @property
    def frequency(self):
        """Gibt CPU Taktfrequenz zurueck.
        @return CPU Taktfrequenz in MHz"""
        return None if self._iofrequency is None else int.from_bytes(
            self._lst_io[self._iofrequency].get_value(),
            byteorder=self._lst_io[self._iofrequency]._byteorder
        ) * 10

    @property
    def ioerrorcount(self):
        """Gibt Fehleranzahl auf RS485 piBridge Bus zurueck.
        @return Fehleranzahl der piBridge"""
        return None if self._ioerrorcnt is None else int.from_bytes(
            self._lst_io[self._ioerrorcnt].get_value(),
            byteorder=self._lst_io[self._ioerrorcnt]._byteorder
        )

    @property
    def errorlimit1(self):
        """Gibt RS485 ErrorLimit1 Wert zurueck.
        @return Aktueller Wert fuer ErrorLimit1"""
        return self._errorlimit(self._ioerrorlimit1, None)

    @errorlimit1.setter
    def errorlimit1(self, value):
        """Setzt RS485 ErrorLimit1 auf neuen Wert.
        @param value Neuer ErrorLimit1 Wert"""
        self._errorlimit(self._ioerrorlimit1, value)

    @property
    def errorlimit2(self):
        """Gibt RS485 ErrorLimit2 Wert zurueck.
        @return Aktueller Wert fuer ErrorLimit2"""
        return self._errorlimit(self._ioerrorlimit2, None)

    @errorlimit2.setter
    def errorlimit2(self, value):
        """Setzt RS485 ErrorLimit2 auf neuen Wert.
        @param value Neuer ErrorLimit2 Wert"""
        self._errorlimit(self._ioerrorlimit2, value)


class Gateway(Device):

    """Klasse fuer die RevPi Gateway-Devices.

    Stellt neben den Funktionen von RevPiDevice weitere Funktionen fuer die
    Gateways bereit. Es koennen ueber die reg_*-Funktionen eigene IOs definiert
    werden, die ein RevPiStructIO-Objekt abbilden.
    Dieser IO-Typ kann Werte ueber mehrere Bytes verarbeiten und zurueckgeben.

    """

    def __init__(self, parent, dict_device, **kwargs):
        """Erweitert RevPiDevice um reg_*-Funktionen.
        @see #RevPiDevice.__init__ RevPiDevice.__init__(...)"""
        super().__init__(parent, dict_device, **kwargs)

        # TODO: evtl. an modio.io anhängen
        self._dict_iorefbyte = {}
        self._dict_iorefname = {}
        self._dict_slc = {
            IOType.INP: self.slc_inp,
            IOType.OUT: self.slc_out,
            IOType.MEM: self.slc_mem
        }

    def _create_io(self, name, startio, frm, io_type, **kwargs):
        """Erstellt einen neuen IO und ersetzt den/die Bestehenden.

        @param name Name des neuen IO
        @param startio IO ab dem eingefuegt wird
        @param frm struct() formatierung (1 Zeichen)
        @param io_type IOType() Wert
        @param kwargs Weitere Parameter:
            - bmk: Bezeichnung fuer IO
            - bit: Registriert IO als bool() am angegebenen Bit im Byte
            - byteorder: Byteorder fuer diesen IO, Standardwert=little
            - defaultvalue: Standardwert fuer IO, Standard ist 0

        """
        if len(frm) == 1:

            # Byteorder prüfen und übernehmen
            byteorder = kwargs.get("byteorder", "little")
            if not (byteorder == "little" or byteorder == "big"):
                raise ValueError("byteorder must be 'little' or 'big'")
            bofrm = "<" if byteorder == "little" else ">"

            bitaddress = "" if frm != "?" else str(kwargs.get("bit", 0))
            if bitaddress == "" or \
                    (int(bitaddress) >= 0 and int(bitaddress) < 8):

                bitlength = "1" if bitaddress.isnumeric() else \
                    struct.calcsize(bofrm + frm) * 8

                if startio in self._dict_iorefname:
                    startaddress = self._dict_iorefname[startio]
                else:
                    startaddress = self.__getitem__(startio).slc_address.start

                # [name,default,anzbits,adressbyte,export,adressid,bmk,bitaddress]
                list_value = [
                    name,
                    kwargs.get("defaultvalue", 0),
                    bitlength,
                    startaddress,
                    False,
                    str(startaddress).rjust(4, "0"),
                    kwargs.get("bmk", ""),
                    bitaddress
                ]

                # Neuen IO instantiieren
                io_new = StructIO(
                    self,
                    list_value,
                    io_type,
                    byteorder,
                    bofrm + frm
                )
                io_new._byteorder = byteorder

                # Platz für neuen IO prüfen
                if (io_new.slc_address.start >=
                        self._dict_slc[io_type].start and
                        io_new.slc_address.stop <=
                        self._dict_slc[io_type].stop):

                    self._replace_io(io_new)

                else:
                    raise BufferError(
                        "registered value does not fit process image scope"
                    )
            else:
                raise AttributeError(
                    "bitaddress must be a value between 0 and 7"
                )
        else:
            raise AttributeError("parameter frm has to be a single sign")

    def _getbytename(self, iobyte):
        """Ermittelt den Namen eines IOs auf der Byteadresse.
        @param iobyte Bytenummer
        @return IO-Namen"""

        # Wenn IO schon ausgetauscht wurde
        if iobyte in self._dict_iorefbyte:
            return self._dict_iorefbyte[iobyte]

        # Wenn IO jetzt ausgetauscht wird
        if iobyte in self._modio.io:
            intlen = len(self._modio.io[iobyte])
            if intlen == 1:
                return self._modio.io[iobyte][0].name
            elif len == 0:
                raise KeyError("byte '{}' contains no input".format(iobyte))
            else:
                raise KeyError(
                    "byte '{}' contains more than one bit-input".format(iobyte)
                )
        else:
            raise KeyError("byte '{}' does not exist".format(iobyte))

    def _replace_io(self, io):
        """Ersetzt bestehende IOs durch den neu Registrierten.
        @param io Neuer IO der eingefuegt werden soll"""
        if hasattr(self._modio.io, io.name):
            raise NameError(
                "name '{}' already exists on device '{}'".format(
                    io._name, self.name
                )
            )
        else:
            dict_oldio = {}
            for oldio in self._lst_io:
                # Alle IOs Prüfen ob sie im neuen Speicherbereich sind
                errstart = oldio.slc_address.start >= io.slc_address.start \
                    and oldio.slc_address.start < io.slc_address.stop
                errstop = oldio.slc_address.stop > io.slc_address.start \
                    and oldio.slc_address.stop <= io.slc_address.stop

                if errstart or errstop:
                    if type(oldio) == StructIO:
                        # Hier gibt es schon einen neuen IO
                        if oldio._bitaddress >= 0:
                            if io._bitaddress == oldio._bitaddress:
                                raise MemoryError(
                                    "bit {} already assigned to '{}'".format(
                                        io._bitaddress, oldio._name
                                    )
                                )

                        else:
                            # Bereits überschriebene bytes() sind ungültig
                            raise MemoryError(
                                "new io '{}' overlaps memory of '{}'".format(
                                    io._name, oldio._name
                                )
                            )

                    else:
                        # IOs im Speicherbereich des neuen IO merken
                        dict_oldio[oldio.name] = oldio

            for oldio in dict_oldio.values():
                if io._bitaddress >= 0:
                    # ios für ref bei bitaddress speichern
                    self._dict_iorefbyte[oldio.slc_address.start] = oldio.name
                    self._dict_iorefname[oldio.name] = oldio.slc_address.start

                # ios aus listen entfernen
                delattr(self._modio.io, oldio.name)
                self._lst_io.remove(oldio)

            # Namensregister erweitern
            setattr(self._modio.io, io.name, io)

            # io einfügen (auch wenn nicht richtige stelle wegen BitOffset)
            self._lst_io.insert(io.slc_address.start, io)

            # Liste neu sortieren
            self._lst_io.sort(key=lambda x: x.slc_address.start)

    def get_rawbytes(self):
        """Gibt die Bytes aus, die dieses Device verwendet.
        @return bytes() des Devices"""
        return bytes(self._ba_devdata)

    def reg_inp(self, name, startinp, frm, **kwargs):
        """Registriert einen neuen Input.

        @param name Name des neuen Inputs
        @param startinp Inputname ab dem eingefuegt wird
        @param frm struct() formatierung (1 Zeichen)
        @param kwargs Weitere Parameter:
            - bmk: Bezeichnung fuer Input
            - bit: Registriert Input als bool() am angegebenen Bit im Byte
            - byteorder: Byteorder fuer den Input, Standardwert=little
            - defaultvalue: Standardwert fuer Input, Standard ist 0
            - event: Funktion fuer Eventhandling registrieren
            - as_thread: Fuehrt die event-Funktion als RevPiCallback-Thread aus
            - edge: event-Ausfuehren bei RISING, FALLING or BOTH Wertaenderung
        @see <a target="_blank"
        href="https://docs.python.org/3/library/struct.html#format-characters"
        >Python3 struct()</a>

        """
        if type(startinp) == int:
            # Byte int() umwandeln in Namen
            startinp = self._getbytename(startinp)

        if type(startinp) == str:
            self._create_io(name, startinp, frm, IOType.INP, **kwargs)
        else:
            raise TypeError(
                "start input must be str() or int() not {}".format(
                    type(startinp)
                )
            )

        # Optional Event eintragen
        reg_event = kwargs.get("event", None)
        if reg_event is not None:
            as_thread = kwargs.get("as_thread", False)
            edge = kwargs.get("edge", None)
            self.reg_event(name, reg_event, as_thread=as_thread, edge=edge)

    def reg_out(self, name, startout, frm, **kwargs):
        """Registriert einen neuen Output.

        @param name Name des neuen Outputs
        @param startout Outputname ab dem eingefuegt wird
        @param frm struct() formatierung (1 Zeichen)
        @param kwargs Weitere Parameter:
            - bmk: Bezeichnung fuer Output
            - bit: Registriert Outputs als bool() am angegebenen Bit im Byte
            - byteorder: Byteorder fuer den Output, Standardwert=little
            - defaultvalue: Standardwert fuer Output, Standard ist 0
            - event: Funktion fuer Eventhandling registrieren
            - as_thread: Fuehrt die event-Funktion als RevPiCallback-Thread aus
            - edge: event-Ausfuehren bei RISING, FALLING or BOTH Wertaenderung
        @see <a target="_blank"
        href="https://docs.python.org/3/library/struct.html#format-characters"
        >Python3 struct()</a>

        """
        if type(startout) == int:
            # Byte int() umwandeln in Namen
            startout = self._getbytename(startout)

        if type(startout) == str:
            self._create_io(name, startout, frm, IOType.OUT, **kwargs)
        else:
            raise TypeError(
                "start output must be str() or int() not {}".format(
                    type(startout)
                )
            )

        # Optional Event eintragen
        reg_event = kwargs.get("event", None)
        if reg_event is not None:
            as_thread = kwargs.get("as_thread", False)
            edge = kwargs.get("edge", None)
            self.reg_event(name, reg_event, as_thread=as_thread, edge=edge)


class Virtual(Gateway):

    """Klasse fuer die RevPi Virtual-Devices.

    Stellt die selben Funktionen wie RevPiGateway zur Verfuegung. Es koennen
    ueber die reg_*-Funktionen eigene IOs definiert werden, die ein
    RevPiStructIO-Objekt abbilden.
    Dieser IO-Typ kann Werte ueber mehrere Bytes verarbeiten und zurueckgeben.
    @see #RevPiGateway RevPiGateway

    """

    pass

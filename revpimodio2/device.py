#
# python3-RevPiModIO
#
# Webpage: https://revpimodio.org/
# (c) Sven Sager, License: LGPLv3
#
# -*- coding: utf-8 -*-
"""Modul fuer die Verwaltung der Devices."""
from threading import Lock
from .__init__ import IOType
from .helper import ProcimgWriter


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

    def __iter__(self):
        """Gibt Iterator aller Devices zurueck.
        @return iter() aller Devices"""
        for dev in sorted(self.__dict_position):
            yield self.__dict_position[dev]

    def __len__(self):
        """Gibt Anzahl der Devices zurueck.
        return Anzahl der Devices"""
        return len(self.__dict_position)

    def __setattr__(self, key, value):
        """Setzt Attribute nur wenn Device.
        @param key Attributname
        @param value Attributobjekt"""
        if issubclass(type(value), Device):
            object.__setattr__(self, key, value)
            self.__dict_position[value.position] = value
        elif key == "_DeviceList__dict_position":
            object.__setattr__(self, key, value)


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
        """Prueft ob IO auf diesem Device liegt.
        @param key IO-Name str() / IO-Bytenummer int()
        @return True, wenn device vorhanden"""
        if type(key) == str:
            return hasattr(self._modio.io, key) \
                and getattr(self._modio.io, key)._parentdevice == self
        elif type(key) == int:
            return key in self._modio.io \
                and len(self._modio.io[key]) > 0 \
                and self._modio.io[key][0]._parentdevice == self
        else:
            return key._parentdevice == self

    def __int__(self):
        """Gibt die Positon im RevPi Bus zurueck.
        @return Positionsnummer"""
        return self.position

    def __iter__(self):
        """Gibt Iterator aller IOs zurueck.
        @return iter() aller IOs"""
        for i_byte in range(self.slc_devoff.start, self.slc_devoff.stop):
            for io in self._modio.io[i_byte]:
                yield io

    def __len__(self):
        """Gibt Anzahl der Bytes zurueck, die dieses Device belegt.
        @return int()"""
        return self._length

    def __str__(self):
        """Gibt den Namen des Devices zurueck.
        @return Devicename"""
        return self.name

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
                    io_new = iomodule.IOBase(
                        self,
                        dict_io[key],
                        iotype,
                        byteorder="little"
                    )
                else:
                    io_new = iomodule.IntIO(
                        self,
                        dict_io[key],
                        iotype,
                        byteorder="little"
                    )

                # IO registrieren
                self._modio.io._register_new_io_object(io_new)

                # Speicherbereich zuweisen
                self._ba_devdata.extend(bytes(io_new._length))

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

    def get_allios(self):
        """Gibt eine Liste aller Inputs und Outputs zurueck.
        @return list() Input und Output, keine MEMs"""
        return [
            io for io in self._modio.io
            if io._parentdevice == self and io._iotype != IOType.MEM
        ]

    def get_inps(self):
        """Gibt eine Liste aller Inputs zurueck.
        @return list() Inputs"""
        return [
            io for io in self._modio.io
            if io._parentdevice == self and io._iotype == IOType.INP
        ]

    def get_outs(self):
        """Gibt eine Liste aller Outputs zurueck.
        @return list() Outputs"""
        return [
            io for io in self._modio.io
            if io._parentdevice == self and io._iotype == IOType.OUT
        ]

    def get_mems(self):
        """Gibt eine Liste aller mems zurueck.
        @return list() Mems"""
        return [
            io for io in self._modio.io
            if io._parentdevice == self and io._iotype == IOType.MEM
        ]


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

        # Eigene IO-Liste aufbauen
        self._lst_io = [x for x in self.__iter__()]

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

        self._dict_slc = {
            IOType.INP: self.slc_inp,
            IOType.OUT: self.slc_out,
            IOType.MEM: self.slc_mem
        }

    def get_rawbytes(self):
        """Gibt die Bytes aus, die dieses Device verwendet.
        @return bytes() des Devices"""
        return bytes(self._ba_devdata)


class Virtual(Gateway):

    """Klasse fuer die RevPi Virtual-Devices.

    Stellt die selben Funktionen wie RevPiGateway zur Verfuegung. Es koennen
    ueber die reg_*-Funktionen eigene IOs definiert werden, die ein
    RevPiStructIO-Objekt abbilden.
    Dieser IO-Typ kann Werte ueber mehrere Bytes verarbeiten und zurueckgeben.
    @see #RevPiGateway RevPiGateway

    """

    pass


# Nachträglicher Import
from . import io as iomodule

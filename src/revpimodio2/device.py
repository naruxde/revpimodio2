# -*- coding: utf-8 -*-
"""Modul fuer die Verwaltung der Devices."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2023 Sven Sager"
__license__ = "LGPLv3"

import warnings
from threading import Event, Lock, Thread

from ._internal import INP, OUT, MEM, PROCESS_IMAGE_SIZE
from .helper import ProcimgWriter
from .io import IOBase, IntIO, IntIOCounter, IntIOReplaceable, MemIO
from .pictory import ProductType


class DeviceList(object):
    """Basisklasse fuer direkten Zugriff auf Device Objekte."""

    def __init__(self):
        """Init DeviceList class."""
        self.__dict_position = {}

    def __contains__(self, key):
        """
        Prueft ob Device existiert.

        :param key: DeviceName <class 'str'> / Positionsnummer <class 'int'>
        :return: True, wenn Device vorhanden
        """
        if type(key) == int:
            return key in self.__dict_position
        elif type(key) == str:
            return hasattr(self, key)
        else:
            return key in self.__dict_position.values()

    def __delattr__(self, key, delcomplete=True):
        """
        Entfernt angegebenes Device.

        :param key: Device zum entfernen
        :param delcomplete: Wenn True wird Device komplett entfernt
        """
        if delcomplete:
            # Device finden
            if type(key) == int:
                dev_del = self.__dict_position[key]
                key = dev_del._name
            else:
                dev_del = getattr(self, key)

            # Reinigungsjobs
            dev_del.autorefresh(False)
            for io in dev_del:
                delattr(dev_del._modio.io, io._name)

            # Device aus dict löschen
            del self.__dict_position[dev_del._position]

        if hasattr(self, key):
            object.__delattr__(self, key)

    def __delitem__(self, key):
        """
        Entfernt Device an angegebener Position.

        :param key: Deviceposition zum entfernen
        """
        if isinstance(key, Device):
            key = key._position
        self.__delattr__(key)

    def __getitem__(self, key):
        """
        Gibt angegebenes Device zurueck.

        :param key: DeviceName <class 'str'> / Positionsnummer <class 'int'>
        :return: Gefundenes <class 'Device'>-Objekt
        """
        if type(key) == int:
            if key not in self.__dict_position:
                raise IndexError("no device on position {0}".format(key))
            return self.__dict_position[key]
        else:
            return getattr(self, key)

    def __iter__(self):
        """
        Gibt Iterator aller Devices zurueck.

        Die Reihenfolge ist nach Position im Prozessabbild sortiert und nicht
        nach Positionsnummer (Dies entspricht der Positionierung aus piCtory)!

        :return: <class 'iter'> aller Devices
        """
        for dev in sorted(
                self.__dict_position,
                key=lambda key: self.__dict_position[key]._offset):
            yield self.__dict_position[dev]

    def __len__(self):
        """
        Gibt Anzahl der Devices zurueck.

        :return: Anzahl der Devices"""
        return len(self.__dict_position)

    def __setattr__(self, key, value):
        """
        Setzt Attribute nur wenn Device.

        :param key: Attributname
        :param value: Attributobjekt
        """
        if isinstance(value, Device):
            object.__setattr__(self, key, value)
            self.__dict_position[value._position] = value
        elif key == "_DeviceList__dict_position":
            object.__setattr__(self, key, value)


class Device(object):
    """
    Basisklasse fuer alle Device-Objekte.

    Die Basisfunktionalitaet generiert bei Instantiierung alle IOs und
    erweitert den Prozessabbildpuffer um die benoetigten Bytes. Sie verwaltet
    ihren Prozessabbildpuffer und sorgt fuer die Aktualisierung der IO-Werte.
    """

    __slots__ = "__my_io_list", "_ba_devdata", "_ba_datacp", \
        "_dict_events", "_filelock", "_modio", "_name", \
        "_offset", "_position", "_producttype", "_selfupdate", \
        "_slc_devoff", "_slc_inp", "_slc_inpoff", "_slc_mem", \
        "_slc_memoff", "_slc_out", "_slc_outoff", "_shared_procimg", \
        "_shared_write", \
        "bmk", "catalognr", "comment", "extend", \
        "guid", "id", "inpvariant", "outvariant", "type"

    def __init__(self, parentmodio, dict_device, simulator=False):
        """
        Instantiierung der Device-Klasse.

        :param parentmodio: RevpiModIO parent object
        :param dict_device: <class 'dict'> fuer dieses Device aus piCotry
        :param simulator: Laedt das Modul als Simulator und vertauscht IOs
        """
        self._modio = parentmodio

        self._ba_devdata = bytearray()
        self._ba_datacp = bytearray()  # Copy for event detection
        self._dict_events = {}
        self._filelock = Lock()
        self.__my_io_list = []
        self._selfupdate = False
        self._shared_procimg = False
        self._shared_write = []
        self.shared_procimg(parentmodio._shared_procimg)  # Set with register

        # Wertzuweisung aus dict_device
        self._name = dict_device.get("name")
        self._offset = int(dict_device.get("offset"))
        self._position = int(dict_device.get("position"))
        self._producttype = int(dict_device.get("productType"))

        # Offset-Check for broken piCtory configuration
        if self._offset < parentmodio.length:
            warnings.warn(
                "Device offset ERROR in piCtory configuration! Offset of '{0}' "
                "must be {1} but is {2} - Overlapping devices overwrite the "
                "same memory, which has unpredictable effects!!!"
                "".format(self._name, parentmodio.length, self._offset),
                Warning
            )
        # IOM-Objekte erstellen und Adressen in SLCs speichern
        if simulator:
            self._slc_inp = self._buildio(
                dict_device.get("out"), INP)
            self._slc_out = self._buildio(
                dict_device.get("inp"), OUT)
        else:
            self._slc_inp = self._buildio(
                dict_device.get("inp"), INP)
            self._slc_out = self._buildio(
                dict_device.get("out"), OUT)
        self._slc_mem = self._buildio(
            dict_device.get("mem"), MEM
        )

        # SLCs mit offset berechnen
        self._slc_devoff = slice(self._offset, self._offset + self.length)
        self._slc_inpoff = slice(
            self._slc_inp.start + self._offset,
            self._slc_inp.stop + self._offset
        )
        self._slc_outoff = slice(
            self._slc_out.start + self._offset,
            self._slc_out.stop + self._offset
        )
        self._slc_memoff = slice(
            self._slc_mem.start + self._offset,
            self._slc_mem.stop + self._offset
        )

        # Alle restlichen attribute an Klasse anhängen
        self.bmk = dict_device.get("bmk", "")
        self.catalognr = dict_device.get("catalogNr", "")
        self.comment = dict_device.get("comment", "")
        self.extend = dict_device.get("extend", {})
        self.guid = dict_device.get("GUID", "")
        self.id = dict_device.get("id", "")
        self.inpvariant = dict_device.get("inpVariant", 0)
        self.outvariant = dict_device.get("outVariant", 0)
        self.type = dict_device.get("type", "")

        # Spezielle Konfiguration von abgeleiteten Klassen durchführen
        self._devconfigure()

        # IO Liste aktualisieren für schnellen Indexzugriff
        self._update_my_io_list()

    def __bytes__(self):
        """
        Gibt alle Daten des Devices als <class 'bytes'> zurueck.

        :return: Devicedaten als <class 'bytes'>
        """
        return bytes(self._ba_devdata)

    def __contains__(self, key):
        """
        Prueft ob IO auf diesem Device liegt.

        :param key: IO-Name <class 'str'> / IO-Bytenummer <class 'int'>
        :return: True, wenn IO auf Device vorhanden
        """
        if isinstance(key, IOBase):
            # Umwandlung für key
            key = key._name

        if type(key) == int:
            if key in self._modio.io:
                for io in self._modio.io[key]:
                    if io is not None and io._parentdevice == self:
                        return True
            return False
        else:
            return key in self._modio.io \
                and getattr(self._modio.io, key)._parentdevice == self

    def __getitem__(self, key):
        """
        Gibt IO an angegebener Stelle zurueck.

        :param key: Index des IOs auf dem device als <class 'int'>
        :return: Gefundenes IO-Objekt
        """
        return self.__my_io_list[key]

    def __int__(self):
        """
        Gibt die Positon im RevPi Bus zurueck.

        :return: Positionsnummer
        """
        return self._position

    def __iter__(self):
        """
        Gibt Iterator aller IOs zurueck.

        :return: <class 'iter'> aller IOs
        """
        return self.__getioiter(self._slc_devoff, None)

    def __len__(self):
        """
        Gibt Anzahl der Bytes zurueck, die dieses Device belegt.

        :return: <class 'int'>
        """
        return len(self._ba_devdata)

    def __str__(self):
        """
        Gibt den Namen des Devices zurueck.

        :return: Devicename
        """
        return self._name

    def __getioiter(self, ioslc: slice, export):
        """
        Gibt <class 'iter'> mit allen IOs zurueck.

        :param ioslc: IO Abschnitt <class 'slice'>
        :param export: Filter fuer 'Export' Flag in piCtory
        :return: IOs als Iterator
        """
        for lst_io in self._modio.io[ioslc]:
            for io in lst_io:
                if io is not None and (export is None or io.export == export):
                    yield io

    def _buildio(self, dict_io: dict, iotype: int) -> slice:
        """
        Erstellt aus der piCtory-Liste die IOs fuer dieses Device.

        :param dict_io: <class 'dict'>-Objekt aus piCtory Konfiguration
        :param iotype: <class 'int'> Wert
        :return: <class 'slice'> mit Start und Stop Position dieser IOs
        """
        if len(dict_io) <= 0:
            return slice(0, 0)

        int_min, int_max = PROCESS_IMAGE_SIZE, 0
        for key in sorted(dict_io, key=lambda x: int(x)):

            # Neuen IO anlegen
            if iotype == MEM:
                # Memory setting
                io_new = MemIO(
                    self, dict_io[key],
                    iotype,
                    "little",
                    False
                )
            elif bool(dict_io[key][7]):
                # Bei Bitwerten IOBase verwenden
                io_new = IOBase(
                    self, dict_io[key], iotype, "little", False
                )
            elif isinstance(self, DioModule) and \
                    dict_io[key][3] in self._lst_counter:
                # Counter IO auf einem DI oder DIO
                io_new = IntIOCounter(
                    self._lst_counter.index(dict_io[key][3]),
                    self, dict_io[key],
                    iotype,
                    "little",
                    False
                )
            elif isinstance(self, Gateway):
                # Ersetzbare IOs erzeugen
                io_new = IntIOReplaceable(
                    self, dict_io[key],
                    iotype,
                    "little",
                    False
                )
            else:
                io_new = IntIO(
                    self, dict_io[key],
                    iotype,
                    "little",
                    # Bei AIO (103) signed auf True setzen
                    self._producttype == ProductType.AIO
                )

            if io_new.address < self._modio.length:
                warnings.warn(
                    "IO {0} is not in the device offset and will be ignored"
                    "".format(io_new.name),
                    Warning
                )
            else:
                # IO registrieren
                self._modio.io._private_register_new_io_object(io_new)

            # Kleinste und größte Speicheradresse ermitteln
            if io_new._slc_address.start < int_min:
                int_min = io_new._slc_address.start
            if io_new._slc_address.stop > int_max:
                int_max = io_new._slc_address.stop

        self._ba_devdata += bytearray(int_max - int_min)
        return slice(int_min, int_max)

    def _devconfigure(self):
        """Funktion zum ueberschreiben von abgeleiteten Klassen."""
        pass

    def _get_offset(self) -> int:
        """
        Gibt den Deviceoffset im Prozessabbild zurueck.

        :return: Deviceoffset
        """
        return self._offset

    def _get_producttype(self) -> int:
        """
        Gibt den Produkttypen des device zurueck.

        :return: Deviceprodukttyp
        """
        return self._producttype

    def _update_my_io_list(self) -> None:
        """Erzeugt eine neue IO Liste fuer schnellen Zugriff."""
        self.__my_io_list = list(self.__iter__())

    def autorefresh(self, activate=True) -> None:
        """
        Registriert dieses Device fuer die automatische Synchronisierung.

        :param activate: Default True fuegt Device zur Synchronisierung hinzu
        """
        if activate and self not in self._modio._lst_refresh:

            # Daten bei Aufnahme direkt einlesen!
            self._modio.readprocimg(self)

            # Datenkopie anlegen
            with self._filelock:
                self._ba_datacp = self._ba_devdata[:]

            self._selfupdate = True

            # Sicher in Liste einfügen
            with self._modio._imgwriter.lck_refresh:
                self._modio._lst_refresh.append(self)

            # Thread starten, wenn er noch nicht läuft
            if not self._modio._imgwriter.is_alive():
                # Alte Einstellungen speichern
                imgrefresh = self._modio._imgwriter.refresh

                # ImgWriter mit alten Einstellungen erstellen
                self._modio._imgwriter = ProcimgWriter(self._modio)
                self._modio._imgwriter.refresh = imgrefresh
                self._modio._imgwriter.start()

        elif not activate and self in self._modio._lst_refresh:
            # Sicher aus Liste entfernen
            with self._modio._imgwriter.lck_refresh:
                self._modio._lst_refresh.remove(self)
            self._selfupdate = False

            # Beenden, wenn keien Devices mehr in Liste sind
            if len(self._modio._lst_refresh) == 0:
                self._modio._imgwriter.stop()

            # Daten beim Entfernen noch einmal schreiben
            if not self._modio._monitoring:
                self._modio.writeprocimg(self)

    def get_allios(self, export=None) -> list:
        """
        Gibt eine Liste aller Inputs und Outputs zurueck, keine MEMs.

        Bleibt Parameter 'export' auf None werden alle Inputs und Outputs
        zurueckgegeben. Wird 'export' auf True/False gesetzt, werden nur Inputs
        und Outputs zurueckgegeben, bei denen der Wert 'Export' in piCtory
        uebereinstimmt.

        :param export: Nur In-/Outputs mit angegebenen 'Export' Wert in piCtory
        :return: <class 'list'> Input und Output, keine MEMs
        """
        return list(self.__getioiter(
            slice(self._slc_inpoff.start, self._slc_outoff.stop), export
        ))

    def get_inputs(self, export=None) -> list:
        """
        Gibt eine Liste aller Inputs zurueck.

        Bleibt Parameter 'export' auf None werden alle Inputs zurueckgegeben.
        Wird 'export' auf True/False gesetzt, werden nur Inputs zurueckgegeben,
        bei denen der Wert 'Export' in piCtory uebereinstimmt.

        :param export: Nur Inputs mit angegebenen 'Export' Wert in piCtory
        :return: <class 'list'> Inputs
        """
        return list(self.__getioiter(self._slc_inpoff, export))

    def get_outputs(self, export=None) -> list:
        """
        Gibt eine Liste aller Outputs zurueck.

        Bleibt Parameter 'export' auf None werden alle Outputs zurueckgegeben.
        Wird 'export' auf True/False gesetzt, werden nur Outputs
        zurueckgegeben, bei denen der Wert 'Export' in piCtory uebereinstimmt.

        :param export: Nur Outputs mit angegebenen 'Export' Wert in piCtory
        :return: <class 'list'> Outputs
        """
        return list(self.__getioiter(self._slc_outoff, export))

    def get_memories(self, export=None) -> list:
        """
        Gibt eine Liste aller Memoryobjekte zurueck.

        Bleibt Parameter 'export' auf None werden alle Mems zurueckgegeben.
        Wird 'export' auf True/False gesetzt, werden nur Mems zurueckgegeben,
        bei denen der Wert 'Export' in piCtory uebereinstimmt.

        :param export: Nur Mems mit angegebenen 'Export' Wert in piCtory
        :return: <class 'list'> Mems
        """
        return list(self.__getioiter(self._slc_memoff, export))

    def readprocimg(self) -> bool:
        """
        Alle Inputs fuer dieses Device vom Prozessabbild einlesen.


        Same  see

        :return: True, wenn erfolgreich ausgefuehrt
        :ref: :func:`revpimodio2.modio.RevPiModIO.readprocimg()`
        """
        return self._modio.readprocimg(self)

    def setdefaultvalues(self) -> None:
        """
        Alle Outputbuffer fuer dieses Device auf default Werte setzen.

        :return: True, wenn erfolgreich ausgefuehrt
        :ref: :func:`revpimodio2.modio.RevPiModIO.setdefaultvalues()`
        """
        self._modio.setdefaultvalues(self)

    def shared_procimg(self, activate: bool) -> None:
        """
        Activate sharing of process image just for this device.

        :param activate: Set True to activate process image sharing
        """
        with self._filelock:
            self._shared_write.clear()
        self._shared_procimg = True if activate else False
        if self._shared_procimg and self not in self._modio._lst_shared:
            self._modio._lst_shared.append(self)
        elif not self._shared_procimg and self in self._modio._lst_shared:
            self._modio._lst_shared.remove(self)

    def syncoutputs(self) -> bool:
        """
        Lesen aller Outputs im Prozessabbild fuer dieses Device.

        :return: True, wenn erfolgreich ausgefuehrt
        :ref: :func:`revpimodio2.modio.RevPiModIO.syncoutputs()`
        """
        return self._modio.syncoutputs(self)

    def writeprocimg(self) -> bool:
        """
        Schreiben aller Outputs dieses Devices ins Prozessabbild.

        :return: True, wenn erfolgreich ausgefuehrt
        :ref: :func:`revpimodio2.modio.RevPiModIO.writeprocimg()`
        """
        return self._modio.writeprocimg(self)

    length = property(__len__)
    name = property(__str__)
    offset = property(_get_offset)
    position = property(__int__)
    producttype = property(_get_producttype)


class Base(Device):
    """Klasse fuer alle Base-Devices wie Core / Connect usw."""

    __slots__ = ()

    pass


class Core(Base):
    """
    Klasse fuer den RevPi Core.

    Stellt Funktionen fuer die LEDs und den Status zur Verfuegung.
    """

    __slots__ = "_slc_cycle", "_slc_errorcnt", "_slc_statusbyte", \
        "_slc_temperature", "_slc_errorlimit1", "_slc_errorlimit2", \
        "_slc_frequency", "_slc_led", "a1green", "a1red", \
        "a2green", "a2red", "wd"

    def __setattr__(self, key, value):
        """Verhindert Ueberschreibung der LEDs."""
        if hasattr(self, key) and key in (
                "a1green", "a1red", "a2green", "a2red", "wd"):
            raise AttributeError(
                "direct assignment is not supported - use .value Attribute"
            )
        else:
            object.__setattr__(self, key, value)

    def _devconfigure(self) -> None:
        """Core-Klasse vorbereiten."""

        # Statische IO Verknüpfungen je nach Core-Variante
        # 2 Byte = Core1.0
        self._slc_statusbyte = slice(0, 1)
        self._slc_led = slice(1, 2)

        self._slc_cycle = None
        self._slc_temperature = None
        self._slc_frequency = None
        self._slc_errorcnt = None
        self._slc_errorlimit1 = None
        self._slc_errorlimit2 = None
        if self.length == 9:
            #  9 Byte = Core1.1
            self._slc_cycle = slice(1, 2)
            self._slc_errorcnt = slice(2, 4)
            self._slc_led = slice(4, 5)
            self._slc_errorlimit1 = slice(5, 7)
            self._slc_errorlimit2 = slice(7, 9)
        elif self.length == 11:
            # 11 Byte = Core1.2 / Connect
            self._slc_cycle = slice(1, 2)
            self._slc_errorcnt = slice(2, 4)
            self._slc_temperature = slice(4, 5)
            self._slc_frequency = slice(5, 6)
            self._slc_led = slice(6, 7)
            self._slc_errorlimit1 = slice(7, 9)
            self._slc_errorlimit2 = slice(9, 11)

        # Exportflags prüfen (Byte oder Bit)
        lst_led = self._modio.io[self._slc_devoff][self._slc_led.start]
        if len(lst_led) == 8:
            exp_a1green = lst_led[0].export
            exp_a1red = lst_led[1].export
            exp_a2green = lst_led[2].export
            exp_a2red = lst_led[3].export
        else:
            exp_a1green = lst_led[0].export
            exp_a1red = exp_a1green
            exp_a2green = exp_a1green
            exp_a2red = exp_a1green

        # Echte IOs erzeugen
        self.a1green = IOBase(self, [
            "core.a1green", 0, 1, self._slc_led.start,
            exp_a1green, None, "LED_A1_GREEN", "0"
        ], OUT, "little", False)
        self.a1red = IOBase(self, [
            "core.a1red", 0, 1, self._slc_led.start,
            exp_a1red, None, "LED_A1_RED", "1"
        ], OUT, "little", False)
        self.a2green = IOBase(self, [
            "core.a2green", 0, 1, self._slc_led.start,
            exp_a2green, None, "LED_A2_GREEN", "2"
        ], OUT, "little", False)
        self.a2red = IOBase(self, [
            "core.a2red", 0, 1, self._slc_led.start,
            exp_a2red, None, "LED_A2_RED", "3"
        ], OUT, "little", False)

        # Watchdog einrichten (Core=soft / Connect=soft/hard)
        self.wd = IOBase(self, [
            "core.wd", 0, 1, self._slc_led.start,
            False, None, "WatchDog", "7"
        ], OUT, "little", False)

    def __errorlimit(self, slc_io: slice, errorlimit: int) -> None:
        """
        Verwaltet das Schreiben der ErrorLimits.

        :param slc_io: Byte Slice vom ErrorLimit
        :return: Aktuellen ErrorLimit oder None wenn nicht verfuegbar
        """
        if 0 <= errorlimit <= 65535:
            self._ba_devdata[slc_io] = \
                errorlimit.to_bytes(2, byteorder="little")
        else:
            raise ValueError(
                "errorlimit value must be between 0 and 65535"
            )

    def _get_status(self) -> int:
        """
        Gibt den RevPi Core Status zurueck.

        :return: Status als <class 'int'>
        """
        return int.from_bytes(
            self._ba_devdata[self._slc_statusbyte], byteorder="little"
        )

    def _get_leda1(self) -> int:
        """
        Gibt den Zustand der LED A1 vom Core zurueck.

        :return: 0=aus, 1=gruen, 2=rot
        """
        # 0b00000011 = 3
        return self._ba_devdata[self._slc_led.start] & 3

    def _get_leda2(self) -> int:
        """
        Gibt den Zustand der LED A2 vom Core zurueck.

        :return: 0=aus, 1=gruen, 2=rot
        """
        # 0b00001100 = 12
        return (self._ba_devdata[self._slc_led.start] & 12) >> 2

    def _set_leda1(self, value: int) -> None:
        """
        Setzt den Zustand der LED A1 vom Core.

        :param value: 0=aus, 1=gruen, 2=rot
        """
        if 0 <= value <= 3:
            self.a1green(bool(value & 1))
            self.a1red(bool(value & 2))
        else:
            raise ValueError("led status must be between 0 and 3")

    def _set_leda2(self, value: int) -> None:
        """
        Setzt den Zustand der LED A2 vom Core.

        :param value: 0=aus, 1=gruen, 2=rot
        """
        if 0 <= value <= 3:
            self.a2green(bool(value & 1))
            self.a2red(bool(value & 2))
        else:
            raise ValueError("led status must be between 0 and 3")

    def wd_toggle(self):
        """Toggle watchdog bit to prevent a timeout."""
        self.wd.value = not self.wd.value

    A1 = property(_get_leda1, _set_leda1)
    A2 = property(_get_leda2, _set_leda2)
    status = property(_get_status)

    @property
    def picontrolrunning(self) -> bool:
        """
        Statusbit fuer piControl-Treiber laeuft.

        :return: True, wenn Treiber laeuft
        """
        return bool(int.from_bytes(
            self._ba_devdata[self._slc_statusbyte], byteorder="little"
        ) & 1)

    @property
    def unconfdevice(self) -> bool:
        """
        Statusbit fuer ein IO-Modul nicht mit PiCtory konfiguriert.

        :return: True, wenn IO Modul nicht konfiguriert
        """
        return bool(int.from_bytes(
            self._ba_devdata[self._slc_statusbyte], byteorder="little"
        ) & 2)

    @property
    def missingdeviceorgate(self) -> bool:
        """
        Statusbit fuer ein IO-Modul fehlt oder piGate konfiguriert.

        :return: True, wenn IO-Modul fehlt oder piGate konfiguriert
        """
        return bool(int.from_bytes(
            self._ba_devdata[self._slc_statusbyte], byteorder="little"
        ) & 4)

    @property
    def overunderflow(self) -> bool:
        """
        Statusbit Modul belegt mehr oder weniger Speicher als konfiguriert.

        :return: True, wenn falscher Speicher belegt ist
        """
        return bool(int.from_bytes(
            self._ba_devdata[self._slc_statusbyte], byteorder="little"
        ) & 8)

    @property
    def leftgate(self) -> bool:
        """
        Statusbit links vom RevPi ist ein piGate Modul angeschlossen.

        :return: True, wenn piGate links existiert
        """
        return bool(int.from_bytes(
            self._ba_devdata[self._slc_statusbyte], byteorder="little"
        ) & 16)

    @property
    def rightgate(self) -> bool:
        """
        Statusbit rechts vom RevPi ist ein piGate Modul angeschlossen.

        :return: True, wenn piGate rechts existiert
        """
        return bool(int.from_bytes(
            self._ba_devdata[self._slc_statusbyte], byteorder="little"
        ) & 32)

    @property
    def iocycle(self) -> int:
        """
        Gibt Zykluszeit der Prozessabbildsynchronisierung zurueck.

        :return: Zykluszeit in ms ( -1 wenn nicht verfuegbar)
        """
        return -1 if self._slc_cycle is None else int.from_bytes(
            self._ba_devdata[self._slc_cycle], byteorder="little"
        )

    @property
    def temperature(self) -> int:
        """
        Gibt CPU-Temperatur zurueck.

        :return: CPU-Temperatur in Celsius (-273 wenn nich verfuegbar)
        """
        return -273 if self._slc_temperature is None else int.from_bytes(
            self._ba_devdata[self._slc_temperature], byteorder="little"
        )

    @property
    def frequency(self) -> int:
        """
        Gibt CPU Taktfrequenz zurueck.

        :return: CPU Taktfrequenz in MHz (-1 wenn nicht verfuegbar)
        """
        return -1 if self._slc_frequency is None else int.from_bytes(
            self._ba_devdata[self._slc_frequency], byteorder="little"
        ) * 10

    @property
    def ioerrorcount(self) -> int:
        """
        Gibt Fehleranzahl auf RS485 piBridge Bus zurueck.

        :return: Fehleranzahl der piBridge (-1 wenn nicht verfuegbar)
        """
        return -1 if self._slc_errorcnt is None else int.from_bytes(
            self._ba_devdata[self._slc_errorcnt], byteorder="little"
        )

    @property
    def errorlimit1(self) -> int:
        """
        Gibt RS485 ErrorLimit1 Wert zurueck.

        :return: Aktueller Wert fuer ErrorLimit1 (-1 wenn nicht verfuegbar)
        """
        return -1 if self._slc_errorlimit1 is None else int.from_bytes(
            self._ba_devdata[self._slc_errorlimit1], byteorder="little"
        )

    @errorlimit1.setter
    def errorlimit1(self, value: int) -> None:
        """
        Setzt RS485 ErrorLimit1 auf neuen Wert.

        :param value: Neuer ErrorLimit1 Wert
        """
        if self._slc_errorlimit1 is None:
            raise RuntimeError(
                "selected core item in piCtory does not support errorlimit1"
            )
        else:
            self.__errorlimit(self._slc_errorlimit1, value)

    @property
    def errorlimit2(self) -> int:
        """
        Gibt RS485 ErrorLimit2 Wert zurueck.

        :return: Aktueller Wert fuer ErrorLimit2 (-1 wenn nicht verfuegbar)
        """
        return -1 if self._slc_errorlimit2 is None else int.from_bytes(
            self._ba_devdata[self._slc_errorlimit2], byteorder="little"
        )

    @errorlimit2.setter
    def errorlimit2(self, value: int) -> None:
        """
        Setzt RS485 ErrorLimit2 auf neuen Wert.

        :param value: Neuer ErrorLimit2 Wert
        """
        if self._slc_errorlimit2 is None:
            raise RuntimeError(
                "selected core item in piCtory does not support errorlimit2"
            )
        else:
            self.__errorlimit(self._slc_errorlimit2, value)


class Connect(Core):
    """Klasse fuer den RevPi Connect.

    Stellt Funktionen fuer die LEDs, Watchdog und den Status zur Verfuegung.
    """

    __slots__ = "__evt_wdtoggle", "__th_wdtoggle", "a3green", "a3red", \
        "x2in", "x2out"

    def __setattr__(self, key, value):
        """Verhindert Ueberschreibung der speziellen IOs."""
        if hasattr(self, key) and key in (
                "a3green", "a3red", "x2in", "x2out"):
            raise AttributeError(
                "direct assignment is not supported - use .value Attribute"
            )
        super(Connect, self).__setattr__(key, value)

    def __wdtoggle(self) -> None:
        """WD Ausgang alle 10 Sekunden automatisch toggeln."""
        while not self.__evt_wdtoggle.wait(10):
            self.wd.value = not self.wd.value

    def _devconfigure(self) -> None:
        """Connect-Klasse vorbereiten."""
        super()._devconfigure()

        self.__evt_wdtoggle = Event()
        self.__th_wdtoggle = None

        # Exportflags prüfen (Byte oder Bit)
        lst_myios = self._modio.io[self._slc_devoff]
        lst_led = lst_myios[self._slc_led.start]
        if len(lst_led) == 8:
            exp_a3green = lst_led[4].export
            exp_a3red = lst_led[5].export
            exp_x2out = lst_led[6].export
            exp_wd = lst_led[7].export
        else:
            exp_a3green = lst_led[0].export
            exp_a3red = exp_a3green
            exp_x2out = exp_a3green
            exp_wd = exp_a3green
        lst_status = lst_myios[self._slc_statusbyte.start]
        if len(lst_status) == 8:
            exp_x2in = lst_status[6].export
        else:
            exp_x2in = lst_status[0].export

        # Echte IOs erzeugen
        self.a3green = IOBase(self, [
            "core.a3green", 0, 1, self._slc_led.start,
            exp_a3green, None, "LED_A3_GREEN", "4"
        ], OUT, "little", False)
        self.a3red = IOBase(self, [
            "core.a3red", 0, 1, self._slc_led.start,
            exp_a3red, None, "LED_A3_RED", "5"
        ], OUT, "little", False)

        # IO Objekte für WD und X2 in/out erzeugen
        self.x2in = IOBase(self, [
            "core.x2in", 0, 1, self._slc_statusbyte.start,
            exp_x2in, None, "Connect_X2_IN", "6"
        ], INP, "little", False)
        self.x2out = IOBase(self, [
            "core.x2out", 0, 1, self._slc_led.start,
            exp_x2out, None, "Connect_X2_OUT", "6"
        ], OUT, "little", False)

        # Export hardware watchdog to use it with other systems
        self.wd._export = int(exp_wd)  # Do this without mrk for export!

    def _get_leda3(self) -> int:
        """
        Gibt den Zustand der LED A3 vom Connect zurueck.

        :return: 0=aus, 1=gruen, 2=rot
        """
        # 0b00110000 = 48
        return (self._ba_devdata[self._slc_led.start] & 48) >> 4

    def _get_wdtoggle(self) -> bool:
        """
        Ruft den Wert fuer Autowatchdog ab.

        :return: True, wenn Autowatchdog aktiv ist
        """
        return self.__th_wdtoggle is not None and self.__th_wdtoggle.is_alive()

    def _set_leda3(self, value: int) -> None:
        """
        Setzt den Zustand der LED A3 vom Connect.

        :param: value 0=aus, 1=gruen, 2=rot
        """
        if 0 <= value <= 3:
            self.a3green(bool(value & 1))
            self.a3red(bool(value & 2))
        else:
            raise ValueError("led status must be between 0 and 3")

    def _set_wdtoggle(self, value: bool) -> None:
        """
        Setzt den Wert fuer Autowatchdog.

        Wird dieser Wert auf True gesetzt, wechselt im Hintergrund das noetige
        Bit zum toggeln des Watchdogs alle 10 Sekunden zwichen True und False.
        Dieses Bit wird bei autorefresh=True natuerlich automatisch in das
        Prozessabbild geschrieben.

        WICHTIG: Sollte autorefresh=False sein, muss zyklisch
                 .writeprocimg() aufgerufen werden, um den Wert in das
                 Prozessabbild zu schreiben!!!

        :param value: True zum aktivieren, Fals zum beenden
        """
        if self._modio._monitoring:
            raise RuntimeError(
                "can not toggle watchdog, while system is in monitoring mode"
            )
        if self._modio._simulator:
            raise RuntimeError(
                "can not toggle watchdog, while system is in simulator mode"
            )

        if not value:
            self.__evt_wdtoggle.set()

        elif not self._get_wdtoggle():
            # Watchdogtoggler erstellen
            self.__evt_wdtoggle.clear()
            self.__th_wdtoggle = Thread(target=self.__wdtoggle, daemon=True)
            self.__th_wdtoggle.start()

    A3 = property(_get_leda3, _set_leda3)
    wdautotoggle = property(_get_wdtoggle, _set_wdtoggle)


class Compact(Base):
    """
    Klasse fuer den RevPi Compact.

    Stellt Funktionen fuer die LEDs zur Verfuegung. Auf IOs wird ueber das .io
    Objekt zugegriffen.
    """

    __slots__ = "_slc_temperature", "_slc_frequency", "_slc_led", \
        "a1green", "a1red", "a2green", "a2red", "wd"

    def __setattr__(self, key, value):
        """Verhindert Ueberschreibung der LEDs."""
        if hasattr(self, key) and key in (
                "a1green", "a1red", "a2green", "a2red", "wd"):
            raise AttributeError(
                "direct assignment is not supported - use .value Attribute"
            )
        else:
            object.__setattr__(self, key, value)

    def _devconfigure(self) -> None:
        """Core-Klasse vorbereiten."""

        # Statische IO Verknüpfungen des Compacts
        self._slc_led = slice(23, 24)
        self._slc_temperature = slice(0, 1)
        self._slc_frequency = slice(1, 2)

        # Exportflags prüfen (Byte oder Bit)
        lst_led = self._modio.io[self._slc_devoff][self._slc_led.start]
        if len(lst_led) == 8:
            exp_a1green = lst_led[0].export
            exp_a1red = lst_led[1].export
            exp_a2green = lst_led[2].export
            exp_a2red = lst_led[3].export
        else:
            exp_a1green = lst_led[0].export
            exp_a1red = exp_a1green
            exp_a2green = exp_a1green
            exp_a2red = exp_a1green

        # Echte IOs erzeugen
        self.a1green = IOBase(self, [
            "core.a1green", 0, 1, self._slc_led.start,
            exp_a1green, None, "LED_A1_GREEN", "0"
        ], OUT, "little", False)
        self.a1red = IOBase(self, [
            "core.a1red", 0, 1, self._slc_led.start,
            exp_a1red, None, "LED_A1_RED", "1"
        ], OUT, "little", False)
        self.a2green = IOBase(self, [
            "core.a2green", 0, 1, self._slc_led.start,
            exp_a2green, None, "LED_A2_GREEN", "2"
        ], OUT, "little", False)
        self.a2red = IOBase(self, [
            "core.a2red", 0, 1, self._slc_led.start,
            exp_a2red, None, "LED_A2_RED", "3"
        ], OUT, "little", False)

        # Software watchdog einrichten
        self.wd = IOBase(self, [
            "core.wd", 0, 1, self._slc_led.start,
            False, None, "WatchDog", "7"
        ], OUT, "little", False)

    def _get_leda1(self) -> int:
        """
        Gibt den Zustand der LED A1 vom Compact zurueck.

        :return: 0=aus, 1=gruen, 2=rot
        """
        # 0b00000011 = 3
        return self._ba_devdata[self._slc_led.start] & 3

    def _get_leda2(self) -> int:
        """
        Gibt den Zustand der LED A2 vom Compact zurueck.

        :return: 0=aus, 1=gruen, 2=rot
        """
        # 0b00001100 = 12
        return (self._ba_devdata[self._slc_led.start] & 12) >> 2

    def _set_leda1(self, value: int) -> None:
        """
        Setzt den Zustand der LED A1 vom Compact.

        :param value: 0=aus, 1=gruen, 2=rot
        """
        if 0 <= value <= 3:
            self.a1green(bool(value & 1))
            self.a1red(bool(value & 2))
        else:
            raise ValueError("led status must be between 0 and 3")

    def _set_leda2(self, value: int) -> None:
        """
        Setzt den Zustand der LED A2 vom Compact.

        :param value: 0=aus, 1=gruen, 2=rot
        """
        if 0 <= value <= 3:
            self.a2green(bool(value & 1))
            self.a2red(bool(value & 2))
        else:
            raise ValueError("led status must be between 0 and 3")

    def wd_toggle(self):
        """Toggle watchdog bit to prevent a timeout."""
        self.wd.value = not self.wd.value

    A1 = property(_get_leda1, _set_leda1)
    A2 = property(_get_leda2, _set_leda2)

    @property
    def temperature(self) -> int:
        """
        Gibt CPU-Temperatur zurueck.

        :return: CPU-Temperatur in Celsius (-273 wenn nich verfuegbar)
        """
        return -273 if self._slc_temperature is None else int.from_bytes(
            self._ba_devdata[self._slc_temperature], byteorder="little"
        )

    @property
    def frequency(self) -> int:
        """
        Gibt CPU Taktfrequenz zurueck.

        :return: CPU Taktfrequenz in MHz (-1 wenn nicht verfuegbar)
        """
        return -1 if self._slc_frequency is None else int.from_bytes(
            self._ba_devdata[self._slc_frequency], byteorder="little"
        ) * 10


class Flat(Base):
    """
    Klasse fuer den RevPi Flat.

    Stellt Funktionen fuer die LEDs zur Verfuegung. Auf IOs wird ueber das .io
    Objekt zugegriffen.
    """

    __slots__ = "_slc_temperature", "_slc_frequency", "_slc_led", \
        "_slc_switch", "_slc_dout", \
        "a1green", "a1red", "a2green", "a2red", \
        "a3green", "a3red", "a4green", "a4red", \
        "a5green", "a5red", "relais", "switch", "wd"

    def __setattr__(self, key, value):
        """Verhindert Ueberschreibung der LEDs."""
        if hasattr(self, key) and key in (
                "a1green", "a1red", "a2green", "a2red",
                "a3green", "a3red", "a4green", "a4red",
                "a5green", "a5red", "relais", "switch", "wd"):
            raise AttributeError(
                "direct assignment is not supported - use .value Attribute"
            )
        else:
            object.__setattr__(self, key, value)

    def _devconfigure(self) -> None:
        """Core-Klasse vorbereiten."""

        # Statische IO Verknüpfungen des Compacts
        self._slc_led = slice(7, 9)
        self._slc_temperature = slice(4, 5)
        self._slc_frequency = slice(5, 6)
        self._slc_switch = slice(6, 7)
        self._slc_dout = slice(11, 12)

        # Exportflags prüfen (Byte oder Bit)
        lst_led = self._modio.io[self._slc_devoff][self._slc_led.start]
        if len(lst_led) == 8:
            exp_a1green = lst_led[0].export
            exp_a1red = lst_led[1].export
            exp_a2green = lst_led[2].export
            exp_a2red = lst_led[3].export
            exp_a3green = lst_led[4].export
            exp_a3red = lst_led[5].export
            exp_a4green = lst_led[6].export
            exp_a4red = lst_led[7].export

            # Next byte
            lst_led = self._modio.io[self._slc_devoff][self._slc_led.start + 1]
            exp_a5green = lst_led[0].export
            exp_a5red = lst_led[1].export
        else:
            exp_a1green = lst_led[0].export
            exp_a1red = exp_a1green
            exp_a2green = exp_a1green
            exp_a2red = exp_a1green
            exp_a3green = exp_a1green
            exp_a3red = exp_a1green
            exp_a4green = exp_a1green
            exp_a4red = exp_a1green
            exp_a5green = exp_a1green
            exp_a5red = exp_a1green

        # Echte IOs erzeugen
        self.a1green = IOBase(self, [
            "core.a1green", 0, 1, self._slc_led.start,
            exp_a1green, None, "LED_A1_GREEN", "0"
        ], OUT, "little", False)
        self.a1red = IOBase(self, [
            "core.a1red", 0, 1, self._slc_led.start,
            exp_a1red, None, "LED_A1_RED", "1"
        ], OUT, "little", False)
        self.a2green = IOBase(self, [
            "core.a2green", 0, 1, self._slc_led.start,
            exp_a2green, None, "LED_A2_GREEN", "2"
        ], OUT, "little", False)
        self.a2red = IOBase(self, [
            "core.a2red", 0, 1, self._slc_led.start,
            exp_a2red, None, "LED_A2_RED", "3"
        ], OUT, "little", False)
        self.a3green = IOBase(self, [
            "core.a3green", 0, 1, self._slc_led.start,
            exp_a3green, None, "LED_A3_GREEN", "4"
        ], OUT, "little", False)
        self.a3red = IOBase(self, [
            "core.a3red", 0, 1, self._slc_led.start,
            exp_a3red, None, "LED_A3_RED", "5"
        ], OUT, "little", False)
        self.a4green = IOBase(self, [
            "core.a4green", 0, 1, self._slc_led.start,
            exp_a4green, None, "LED_A4_GREEN", "6"
        ], OUT, "little", False)
        self.a4red = IOBase(self, [
            "core.a4red", 0, 1, self._slc_led.start,
            exp_a4red, None, "LED_A4_RED", "7"
        ], OUT, "little", False)
        self.a5green = IOBase(self, [
            "core.a5green", 0, 1, self._slc_led.start,
            exp_a5green, None, "LED_A5_GREEN", "8"
        ], OUT, "little", False)
        self.a5red = IOBase(self, [
            "core.a5red", 0, 1, self._slc_led.start,
            exp_a5red, None, "LED_A5_RED", "9"
        ], OUT, "little", False)

        # Real IO for switch
        lst_io = self._modio.io[self._slc_devoff][self._slc_switch.start]
        exp_io = lst_io[0].export
        self.switch = IOBase(self, [
            "flat.switch", 0, 1, self._slc_switch.start,
            exp_io, None, "Flat_Switch", "0"
        ], INP, "little", False)

        # Real IO for relais
        lst_io = self._modio.io[self._slc_devoff][self._slc_dout.start]
        exp_io = lst_io[0].export
        self.relais = IOBase(self, [
            "flat.relais", 0, 1, self._slc_dout.start,
            exp_io, None, "Flat_Relais", "0"
        ], OUT, "little", False)

        # Software watchdog einrichten
        self.wd = IOBase(self, [
            "core.wd", 0, 1, self._slc_led.start,
            False, None, "WatchDog", "15"
        ], OUT, "little", False)

    def _get_leda1(self) -> int:
        """
        Get value of LED A1 from RevPi Flat device.

        :return: 0=off, 1=green, 2=red
        """
        return self._ba_devdata[self._slc_led.start] & 0b11

    def _get_leda2(self) -> int:
        """
        Get value of LED A2 from RevPi Flat device.

        :return: 0=off, 1=green, 2=red
        """
        return (self._ba_devdata[self._slc_led.start] & 0b1100) >> 2

    def _get_leda3(self) -> int:
        """
        Get value of LED A3 from RevPi Flat device.

        :return: 0=off, 1=green, 2=red
        """
        return (self._ba_devdata[self._slc_led.start] & 0b110000) >> 4

    def _get_leda4(self) -> int:
        """
        Get value of LED A4 from RevPi Flat device.

        :return: 0=off, 1=green, 2=red
        """
        return (self._ba_devdata[self._slc_led.start] & 0b11000000) >> 6

    def _get_leda5(self) -> int:
        """
        Get value of LED A5 from RevPi Flat device.

        :return: 0=off, 1=green, 2=red
        """
        return self._ba_devdata[self._slc_led.start + 1] & 0b11

    def _set_leda1(self, value: int) -> None:
        """
        Set LED A1 on RevPi Flat device.

        :param value: 0=off, 1=green, 2=red
        """
        if 0 <= value <= 3:
            self.a1green(bool(value & 1))
            self.a1red(bool(value & 2))
        else:
            raise ValueError("led status must be between 0 and 3")

    def _set_leda2(self, value: int) -> None:
        """
        Set LED A2 on RevPi Flat device.

        :param value: 0=off, 1=green, 2=red
        """
        if 0 <= value <= 3:
            self.a2green(bool(value & 1))
            self.a2red(bool(value & 2))
        else:
            raise ValueError("led status must be between 0 and 3")

    def _set_leda3(self, value: int) -> None:
        """
        Set LED A3 on RevPi Flat device.

        :param value: 0=off, 1=green, 2=red
        """
        if 0 <= value <= 3:
            self.a3green(bool(value & 1))
            self.a3red(bool(value & 2))
        else:
            raise ValueError("led status must be between 0 and 3")

    def _set_leda4(self, value: int) -> None:
        """
        Set LED A4 on RevPi Flat device.

        :param value: 0=off, 1=green, 2=red
        """
        if 0 <= value <= 3:
            self.a4green(bool(value & 1))
            self.a4red(bool(value & 2))
        else:
            raise ValueError("led status must be between 0 and 3")

    def _set_leda5(self, value: int) -> None:
        """
        Set LED A5 on RevPi Flat device.

        :param value: 0=off, 1=green, 2=red
        """
        if 0 <= value <= 3:
            self.a5green(bool(value & 1))
            self.a5red(bool(value & 2))
        else:
            raise ValueError("led status must be between 0 and 3")

    def wd_toggle(self):
        """Toggle watchdog bit to prevent a timeout."""
        self.wd.value = not self.wd.value

    A1 = property(_get_leda1, _set_leda1)
    A2 = property(_get_leda2, _set_leda2)
    A3 = property(_get_leda3, _set_leda3)
    A4 = property(_get_leda4, _set_leda4)
    A5 = property(_get_leda5, _set_leda5)

    @property
    def temperature(self) -> int:
        """
        Gibt CPU-Temperatur zurueck.

        :return: CPU-Temperatur in Celsius (-273 wenn nich verfuegbar)
        """
        return -273 if self._slc_temperature is None else int.from_bytes(
            self._ba_devdata[self._slc_temperature], byteorder="little"
        )

    @property
    def frequency(self) -> int:
        """
        Gibt CPU Taktfrequenz zurueck.

        :return: CPU Taktfrequenz in MHz (-1 wenn nicht verfuegbar)
        """
        return -1 if self._slc_frequency is None else int.from_bytes(
            self._ba_devdata[self._slc_frequency], byteorder="little"
        ) * 10


class DioModule(Device):
    """Stellt ein DIO / DI / DO Modul dar."""

    __slots__ = "_lst_counter"

    def __init__(self, parentmodio, dict_device, simulator=False):
        """
        Erweitert Device-Klasse zum Erkennen von IntIOCounter.

        :rev: :func:`Device.__init__()`
        """
        # Stringliste der Byteadressen (alle Module sind gleich)
        self._lst_counter = list(map(str, range(6, 70, 4)))

        # Basisklasse laden
        super().__init__(parentmodio, dict_device, simulator=simulator)


class Gateway(Device):
    """
    Klasse fuer die RevPi Gateway-Devices.

    Stellt neben den Funktionen von RevPiDevice weitere Funktionen fuer die
    Gateways bereit. IOs auf diesem Device stellen die replace_io Funktion
    zur verfuegung, ueber die eigene IOs definiert werden, die ein
    RevPiStructIO-Objekt abbilden.
    Dieser IO-Typ kann Werte ueber mehrere Bytes verarbeiten und zurueckgeben.

    :ref: :func:`revpimodio2.io.IntIOReplaceable.replace_io()`
    """

    __slots__ = "_dict_slc"

    def __init__(self, parent, dict_device, simulator=False):
        """
        Erweitert Device-Klasse um get_rawbytes-Funktionen.

        :ref: :func:`Device.__init__()`
        """
        super().__init__(parent, dict_device, simulator)

        self._dict_slc = {
            INP: self._slc_inp,
            OUT: self._slc_out,
            MEM: self._slc_mem
        }

    def get_rawbytes(self) -> bytes:
        """
        Gibt die Bytes aus, die dieses Device verwendet.

        :return: <class 'bytes'> des Devices
        """
        return bytes(self._ba_devdata)


class Virtual(Gateway):
    """
    Klasse fuer die RevPi Virtual-Devices.

    Stellt die selben Funktionen wie Gateway zur Verfuegung. Es koennen
    ueber die reg_*-Funktionen eigene IOs definiert werden, die ein
    RevPiStructIO-Objekt abbilden.
    Dieser IO-Typ kann Werte ueber mehrere Bytes verarbeiten und zurueckgeben.

    :ref: :func:`Gateway`
    """

    __slots__ = ()

    def writeinputdefaults(self):
        """
        Schreibt fuer ein virtuelles Device piCtory Defaultinputwerte.

        Sollten in piCtory Defaultwerte fuer Inputs eines virtuellen Devices
        angegeben sein, werden diese nur beim Systemstart oder einem piControl
        Reset gesetzt. Sollte danach das Prozessabbild mit NULL ueberschrieben,
        gehen diese Werte verloren.
        Diese Funktion kann nur auf virtuelle Devices angewendet werden!

        :return: True, wenn Arbeiten am virtuellen Device erfolgreich waren
        """
        if self._modio._monitoring:
            raise RuntimeError(
                "can not write process image, while system is in monitoring "
                "mode"
            )

        workokay = True
        self._filelock.acquire()

        for io in self.get_inputs():
            self._ba_devdata[io._slc_address] = io._defaultvalue

        # Inputs auf Bus schreiben
        self._modio._myfh_lck.acquire()
        try:
            self._modio._myfh.seek(self._slc_inpoff.start)
            self._modio._myfh.write(self._ba_devdata[self._slc_inp])
            if self._modio._buffedwrite:
                self._modio._myfh.flush()
        except IOError as e:
            self._modio._gotioerror("write_inp_def", e)
            workokay = False
        finally:
            self._modio._myfh_lck.release()

        self._filelock.release()
        return workokay

# -*- coding: utf-8 -*-
"""RevPiModIO Hauptklasse fuer piControl0 Zugriff."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2023 Sven Sager"
__license__ = "LGPLv3"

import warnings
from collections import namedtuple
from configparser import ConfigParser
from json import load as jload
from multiprocessing import cpu_count
from os import F_OK, R_OK, access
from os import stat as osstat
from queue import Empty
from signal import SIGINT, SIGTERM, SIG_DFL, signal
from stat import S_ISCHR
from threading import Event, Lock, Thread
from timeit import default_timer

from . import app as appmodule
from . import device as devicemodule
from . import helper as helpermodule
from . import summary as summarymodule
from ._internal import acheck, RISING, FALLING, BOTH
from .errors import DeviceNotFoundError
from .io import IOList
from .io import StructIO
from .pictory import DeviceType, ProductType

DevSelect = namedtuple("DevSelect", ["type", "other_device_key", "values"])
"""Leave type, key empty for auto search name and position depending on type in values."""


class RevPiModIO(object):
    """
    Klasse fuer die Verwaltung der piCtory Konfiguration.

    Diese Klasse uebernimmt die gesamte Konfiguration aus piCtory und
    laedt die Devices und IOs. Sie uebernimmt die exklusive Verwaltung des
    Prozessabbilds und stellt sicher, dass die Daten synchron sind.
    Sollten nur einzelne Devices gesteuert werden, verwendet man
    RevPiModIOSelected() und uebergibt bei Instantiierung eine Liste mit
    Device Positionen oder Device Namen.
    """

    __slots__ = "__cleanupfunc", \
        "_autorefresh", "_buffedwrite", "_configrsc", "_debug", "_devselect", \
        "_exit", "_exit_level", "_imgwriter", "_ioerror", \
        "_length", "_looprunning", "_lst_devselect", "_lst_refresh", \
        "_lst_shared", \
        "_maxioerrors", "_monitoring", "_myfh", "_myfh_lck", \
        "_procimg", "_replace_io_file", "_run_on_pi", \
        "_set_device_based_cycle_time", "_simulator", "_shared_procimg", \
        "_syncoutputs", "_th_mainloop", "_waitexit", \
        "app", "core", "device", "exitsignal", "io", "summary"

    def __init__(
            self, autorefresh=False, monitoring=False, syncoutputs=True,
            procimg=None, configrsc=None, simulator=False, debug=True,
            replace_io_file=None, shared_procimg=False, direct_output=False):
        """
        Instantiiert die Grundfunktionen.

        :param autorefresh: Wenn True, alle Devices zu autorefresh hinzufuegen
        :param monitoring: In- und Outputs werden gelesen, niemals geschrieben
        :param syncoutputs: Aktuell gesetzte Outputs vom Prozessabbild einlesen
        :param procimg: Abweichender Pfad zum Prozessabbild
        :param configrsc: Abweichender Pfad zur piCtory Konfigurationsdatei
        :param simulator: Laedt das Modul als Simulator und vertauscht IOs
        :param debug: Gibt alle Warnungen inkl. Zyklusprobleme aus
        :param replace_io_file: Replace IO Konfiguration aus Datei laden
        :param shared_procimg: Share process image with other processes, this
                               could be insecure for automation
        :param direct_output: Deprecated, use shared_procimg
        """
        # Parameterprüfung
        acheck(
            bool, autorefresh=autorefresh, monitoring=monitoring,
            syncoutputs=syncoutputs, simulator=simulator, debug=debug,
            shared_procimg=shared_procimg, direct_output=direct_output
        )
        acheck(
            str, procimg_noneok=procimg, configrsc_noneok=configrsc,
            replace_io_file_noneok=replace_io_file
        )

        # TODO: Remove in next release
        if direct_output:
            warnings.warn(DeprecationWarning(
                "direct_output is deprecated - use shared_procimg instead!"
            ))

        self._autorefresh = autorefresh
        self._configrsc = configrsc
        self._monitoring = monitoring
        self._procimg = "/dev/piControl0" if procimg is None else procimg
        self._set_device_based_cycle_time = True
        self._simulator = simulator
        self._shared_procimg = shared_procimg or direct_output
        self._syncoutputs = syncoutputs

        # TODO: bei simulator und procimg prüfen ob datei existiert / anlegen?

        # Private Variablen
        self.__cleanupfunc = None
        self._buffedwrite = False
        self._debug = 1
        self._devselect = DevSelect(DeviceType.IGNORED, "", ())
        self._exit = Event()
        self._exit_level = 0
        self._imgwriter = None
        self._ioerror = 0
        self._length = 0
        self._looprunning = False
        self._lst_refresh = []
        self._lst_shared = []
        self._maxioerrors = 0
        self._myfh = None
        self._myfh_lck = Lock()
        self._replace_io_file = replace_io_file
        self._th_mainloop = None
        self._waitexit = Event()

        # Modulvariablen
        self.core = None

        # piCtory Klassen
        self.app = None
        self.device = None
        self.io = None
        self.summary = None

        # Event für Benutzeraktionen
        self.exitsignal = Event()

        # Wert über setter setzen
        self.debug = debug

        try:
            self._run_on_pi = S_ISCHR(osstat(self._procimg).st_mode)
        except Exception:
            self._run_on_pi = False

        # Nur Konfigurieren, wenn nicht vererbt
        if type(self) == RevPiModIO:
            self._configure(self.get_jconfigrsc())

    def __del__(self):
        """Zerstoert alle Klassen um aufzuraeumen."""
        if hasattr(self, "_exit"):
            self.exit(full=True)
            if self._myfh is not None:
                self._myfh.close()

    def __evt_exit(self, signum, sigframe) -> None:
        """
        Eventhandler fuer Programmende.

        :param signum: Signalnummer
        :param sigframe: Signalframe
        """
        signal(SIGINT, SIG_DFL)
        signal(SIGTERM, SIG_DFL)
        self._exit_level |= 4
        self.exit(full=True)

    def __exit_jobs(self):
        """Shutdown sub systems."""
        if self._exit_level & 1:
            # Nach Ausführung kann System weiter verwendet werden
            self._exit_level ^= 1

            # ProcimgWriter beenden und darauf warten
            if self._imgwriter is not None and self._imgwriter.is_alive():
                self._imgwriter.stop()
                self._imgwriter.join(2.5)

            # Alle Devices aus Autorefresh entfernen
            while len(self._lst_refresh) > 0:
                dev = self._lst_refresh.pop()
                dev._selfupdate = False
                if not self._monitoring:
                    self.writeprocimg(dev)

        # Execute clean up function
        if self._exit_level & 4 and self.__cleanupfunc is not None:
            self._exit_level ^= 4
            self.readprocimg()
            self.__cleanupfunc()
            if not self._monitoring:
                self.writeprocimg()

        if self._exit_level & 2:
            self._myfh.close()
            self.app = None
            self.core = None
            self.device = None
            self.io = None
            self.summary = None

    def _configure(self, jconfigrsc: dict) -> None:
        """
        Verarbeitet die piCtory Konfigurationsdatei.

        :param jconfigrsc: Data to build IOs as <class 'dict'> of JSON
        """
        # Filehandler konfigurieren, wenn er noch nicht existiert
        if self._myfh is None:
            self._myfh = self._create_myfh()

        # App Klasse instantiieren
        self.app = appmodule.App(jconfigrsc["App"])

        # Apply device filter
        if self._devselect.values:

            # Check for supported types in values
            for dev in self._devselect.values:
                if type(dev) not in (int, str):
                    raise ValueError(
                        "need device position as <class 'int'> or "
                        "device name as <class 'str'>"
                    )

            lst_devices = []
            for dev in jconfigrsc["Devices"]:
                if self._devselect.type and self._devselect.type != dev["type"]:
                    continue
                if self._devselect.other_device_key:
                    key_value = str(dev[self._devselect.other_device_key])
                    if key_value not in self._devselect.values:
                        # The list is always filled with <class 'str'>
                        continue
                else:
                    # Auto search depending of value item type
                    if not (dev["name"] in self._devselect.values
                            or int(dev["position"]) in self._devselect.values):
                        continue

                lst_devices.append(dev)
        else:
            # Devices aus JSON übernehmen
            lst_devices = jconfigrsc["Devices"]

        # Device und IO Klassen anlegen
        self.device = devicemodule.DeviceList()
        self.io = IOList()

        # Devices initialisieren
        err_names_check = {}
        for device in sorted(lst_devices, key=lambda x: x["offset"]):

            # VDev alter piCtory Versionen auf Kunbus-Standard ändern
            if device["position"] == "adap.":
                device["position"] = 64
                while device["position"] in self.device:
                    device["position"] += 1

            if device["type"] == DeviceType.BASE:
                # Basedevices
                pt = int(device["productType"])
                if pt == ProductType.REVPI_CORE:
                    # RevPi Core
                    dev_new = devicemodule.Core(
                        self, device, simulator=self._simulator
                    )
                    self.core = dev_new
                elif pt == ProductType.REVPI_CONNECT:
                    # RevPi Connect
                    dev_new = devicemodule.Connect(
                        self, device, simulator=self._simulator
                    )
                    self.core = dev_new
                elif pt == ProductType.REVPI_COMPACT:
                    # RevPi Compact
                    dev_new = devicemodule.Compact(
                        self, device, simulator=self._simulator
                    )
                    self.core = dev_new
                elif pt == ProductType.REVPI_FLAT:
                    # RevPi Flat
                    dev_new = devicemodule.Flat(
                        self, device, simulator=self._simulator
                    )
                    self.core = dev_new
                else:
                    # Base immer als Fallback verwenden
                    dev_new = devicemodule.Base(
                        self, device, simulator=self._simulator
                    )
            elif device["type"] == DeviceType.LEFT_RIGHT:
                # IOs
                pt = int(device["productType"])
                if pt == ProductType.DIO \
                        or pt == ProductType.DI \
                        or pt == ProductType.DO:
                    # DIO / DI / DO
                    dev_new = devicemodule.DioModule(
                        self, device, simulator=self._simulator
                    )
                else:
                    # Alle anderen IO-Devices
                    dev_new = devicemodule.Device(
                        self, device, simulator=self._simulator
                    )
            elif device["type"] == DeviceType.VIRTUAL:
                # Virtuals
                dev_new = devicemodule.Virtual(
                    self, device, simulator=self._simulator
                )
            elif device["type"] == DeviceType.EDGE:
                # Gateways
                dev_new = devicemodule.Gateway(
                    self, device, simulator=self._simulator
                )
            elif device["type"] == DeviceType.RIGHT:
                # Connectdevice
                dev_new = None
            else:
                # Device-Type nicht gefunden
                warnings.warn(
                    "device type '{0}' on position {1} unknown"
                    "".format(device["type"], device["position"]),
                    Warning
                )
                dev_new = None

            if dev_new is not None:
                # Offset prüfen, muss mit Länge übereinstimmen
                if self._length < dev_new.offset:
                    self._length = dev_new.offset

                self._length += dev_new.length

                # Build dict with device name and positions and check later
                if dev_new.name not in err_names_check:
                    err_names_check[dev_new.name] = []
                err_names_check[dev_new.name].append(str(dev_new.position))

                # DeviceList für direkten Zugriff aufbauen
                setattr(self.device, dev_new.name, dev_new)

        # Check equal device names and destroy name attribute of device class
        for check_dev in err_names_check:
            if len(err_names_check[check_dev]) == 1:
                continue
            self.device.__delattr__(check_dev, False)
            warnings.warn(
                "equal device name '{0}' in pictory configuration. you can "
                "access this devices by position number .device[{1}] only!"
                "".format(check_dev, "|".join(err_names_check[check_dev])),
                Warning
            )

        # ImgWriter erstellen
        self._imgwriter = helpermodule.ProcimgWriter(self)

        if self._set_device_based_cycle_time:
            # Refreshzeit CM1 25 Hz / CM3 50 Hz
            self._imgwriter.refresh = 20 if cpu_count() > 1 else 40

        # Aktuellen Outputstatus von procimg einlesen
        if self._syncoutputs:
            self.syncoutputs()

        # Für RS485 errors am core defaults laden sollte procimg NULL sein
        if isinstance(self.core, devicemodule.Core) and \
                not (self._monitoring or self._simulator):
            if self.core._slc_errorlimit1 is not None:
                io = self.io[
                    self.core.offset + self.core._slc_errorlimit1.start
                    ][0]
                io.set_value(io._defaultvalue)
            if self.core._slc_errorlimit2 is not None:
                io = self.io[
                    self.core.offset + self.core._slc_errorlimit2.start
                    ][0]
                io.set_value(io._defaultvalue)

            # RS485 errors schreiben
            self.writeprocimg(self.core)

        # Set replace IO before autostart to prevent cycle time exhausting
        self._configure_replace_io(self._get_cpreplaceio())

        # Optional ins autorefresh aufnehmen
        if self._autorefresh:
            self.autorefresh_all()

        # Summary Klasse instantiieren
        self.summary = summarymodule.Summary(jconfigrsc["Summary"])

    def _configure_replace_io(self, creplaceio: ConfigParser) -> None:
        """
        Importiert ersetzte IOs in diese Instanz.

        Importiert ersetzte IOs, welche vorher mit .export_replaced_ios(...)
        in eine Datei exportiert worden sind. Diese IOs werden in dieser
        Instanz wiederhergestellt.

        :param creplaceio: Data to replace ios as <class 'ConfigParser'>
        """
        for io in creplaceio:
            if io == "DEFAULT":
                continue

            # IO prüfen
            parentio = creplaceio[io].get("replace", "")

            # Funktionsaufruf vorbereiten
            dict_replace = {
                "frm": creplaceio[io].get("frm"),
                "byteorder": creplaceio[io].get("byteorder", "little"),
                "bmk": creplaceio[io].get("bmk", ""),
            }

            # Get bitaddress from config file
            if "bit" in creplaceio[io]:
                try:
                    dict_replace["bit"] = creplaceio[io].getint("bit")
                except Exception:
                    raise ValueError(
                        "replace_io_file: could not convert '{0}' "
                        "bit '{1}' to integer"
                        "".format(io, creplaceio[io]["bit"])
                    )

            if "wordorder" in creplaceio[io]:
                dict_replace["wordorder"] = creplaceio[io]["wordorder"]

            if "export" in creplaceio[io]:
                try:
                    dict_replace["export"] = creplaceio[io].getboolean("export")
                except Exception:
                    raise ValueError(
                        "replace_io_file: could not convert '{0}' "
                        "export '{1}' to bool"
                        "".format(io, creplaceio[io]["export"])
                    )

            # Convert defaultvalue from config file
            if "defaultvalue" in creplaceio[io]:
                if dict_replace["frm"] == "?":
                    try:
                        dict_replace["defaultvalue"] = \
                            creplaceio[io].getboolean("defaultvalue")
                    except Exception:
                        raise ValueError(
                            "replace_io_file: could not convert '{0}' "
                            "defaultvalue '{1}' to boolean"
                            "".format(io, creplaceio[io]["defaultvalue"])
                        )
                elif dict_replace["frm"].find("s") >= 0:
                    buff = bytearray()
                    try:
                        dv_array = creplaceio[io].get("defaultvalue").split(" ")
                        for byte_int in dv_array:
                            buff.append(int(byte_int))
                        dict_replace["defaultvalue"] = bytes(buff)
                    except Exception as e:
                        raise ValueError(
                            "replace_io_file: could not convert '{0}' "
                            "defaultvalue to bytes | {1}"
                            "".format(io, e)
                        )
                else:
                    try:
                        dict_replace["defaultvalue"] = \
                            creplaceio[io].getint("defaultvalue")
                    except Exception:
                        raise ValueError(
                            "replace_io_file: could not convert '{0}' "
                            "defaultvalue '{1}' to integer"
                            "".format(io, creplaceio[io]["defaultvalue"])
                        )

            # IO ersetzen
            try:
                self.io[parentio].replace_io(name=io, **dict_replace)
            except Exception as e:
                # NOTE: Bei Selected/Driver kann nicht geprüft werden
                if len(self._devselect.values) == 0:
                    raise RuntimeError(
                        "replace_io_file: can not replace '{0}' with '{1}' "
                        "| RevPiModIO message: {2}".format(parentio, io, e)
                    )

    def _create_myfh(self):
        """
        Erstellt FileObject mit Pfad zum procimg.

        :return: FileObject
        """
        self._buffedwrite = False
        return open(self._procimg, "r+b", 0)

    def _get_configrsc(self) -> str:
        """
        Getter function.

        :return: Pfad der verwendeten piCtory Konfiguration
        """
        return self._configrsc

    def _get_cpreplaceio(self) -> ConfigParser:
        """
        Laedt die replace_io_file Konfiguration und verarbeitet sie.

        :return: <class 'ConfigParser'> der replace io daten
        """
        cp = ConfigParser()

        if self._replace_io_file:
            try:
                with open(self._replace_io_file, "r") as fh:
                    cp.read_file(fh)
            except Exception as e:
                raise RuntimeError(
                    "replace_io_file: could not read/parse file '{0}' | {1}"
                    "".format(self._replace_io_file, e)
                )

        return cp

    def _get_cycletime(self) -> int:
        """
        Gibt Aktualisierungsrate in ms der Prozessabbildsynchronisierung aus.

        :return: Millisekunden
        """
        return self._imgwriter.refresh

    def _get_debug(self) -> bool:
        """
        Gibt Status des Debugflags zurueck.

        :return: Status des Debugflags
        """
        return self._debug == 1

    def _get_ioerrors(self) -> int:
        """
        Getter function.

        :return: Aktuelle Anzahl gezaehlter Fehler
        """
        return self._ioerror

    def _get_length(self) -> int:
        """
        Getter function.

        :return: Laenge in Bytes der Devices
        """
        return self._length

    def _get_maxioerrors(self) -> int:
        """
        Getter function.

        :return: Anzahl erlaubte Fehler
        """
        return self._maxioerrors

    def _get_monitoring(self) -> bool:
        """
        Getter function.

        :return: True, wenn als Monitoring gestartet
        """
        return self._monitoring

    def _get_procimg(self) -> str:
        """
        Getter function.

        :return: Pfad des verwendeten Prozessabbilds
        """
        return self._procimg

    def _get_replace_io_file(self) -> str:
        """
        Gibt Pfad zur verwendeten replace IO Datei aus.

        :return: Pfad zur replace IO Datei
        """
        return self._replace_io_file

    def _get_simulator(self) -> bool:
        """
        Getter function.

        :return: True, wenn als Simulator gestartet
        """
        return self._simulator

    def _gotioerror(self, action: str, e=None, show_warn=True) -> None:
        """
        IOError Verwaltung fuer Prozessabbildzugriff.

        :param action: Zusatzinformationen zum loggen
        :param e: Exception to log if debug is enabled
        :param show_warn: Warnung anzeigen
        """
        self._ioerror += 1
        if self._maxioerrors != 0 and self._ioerror >= self._maxioerrors:
            raise RuntimeError(
                "reach max io error count {0} on process image"
                "".format(self._maxioerrors)
            )

        if not show_warn or self._debug == -1:
            return

        if self._debug == 0:
            warnings.warn(
                "got io error on process image",
                RuntimeWarning
            )
        else:
            warnings.warn(
                "got io error during '{0}' and count {1} errors now | {2}"
                "".format(action, self._ioerror, str(e)),
                RuntimeWarning
            )

    def _set_cycletime(self, milliseconds: int) -> None:
        """
        Setzt Aktualisierungsrate der Prozessabbild-Synchronisierung.

        :param milliseconds: <class 'int'> in Millisekunden
        """
        if self._looprunning:
            raise RuntimeError(
                "can not change cycletime when cycleloop or mainloop is "
                "running"
            )
        else:
            self._imgwriter.refresh = milliseconds

    def _set_debug(self, value: bool) -> None:
        """
        Setzt debugging Status um mehr Meldungen zu erhalten oder nicht.

        :param value: Wenn True, werden umfangreiche Medungen angezeigt
        """
        if type(value) == bool:
            value = int(value)
        if not type(value) == int:
            # Wert -1 ist zum kompletten deaktivieren versteckt
            raise TypeError("value must be <class 'bool'> or <class 'int'>")
        if not -1 <= value <= 1:
            raise ValueError("value must be True/False or -1, 0, 1")

        self._debug = value

        if value == -1:
            warnings.filterwarnings("ignore", module="revpimodio2")
        elif value == 0:
            warnings.filterwarnings("default", module="revpimodio2")
        else:
            warnings.filterwarnings("always", module="revpimodio2")

    def _set_maxioerrors(self, value: int) -> None:
        """
        Setzt Anzahl der maximal erlaubten Fehler bei Prozessabbildzugriff.

        :param value: Anzahl erlaubte Fehler
        """
        if type(value) == int and value >= 0:
            self._maxioerrors = value
        else:
            raise ValueError("value must be 0 or a positive integer")

    def _simulate_ioctl(self, request: int, arg=b'') -> None:
        """
        Simuliert IOCTL Funktionen auf procimg Datei.

        :param request: IO Request
        :param arg: Request argument
        """
        if request == 19216:
            # Einzelnes Bit setzen
            byte_address = int.from_bytes(arg[:2], byteorder="little")
            bit_address = arg[2]
            new_value = bool(0 if len(arg) <= 3 else arg[3])

            # Simulatonsmodus schreibt direkt in Datei
            with self._myfh_lck:
                self._myfh.seek(byte_address)
                int_byte = int.from_bytes(
                    self._myfh.read(1), byteorder="little"
                )
                int_bit = 1 << bit_address

                if not bool(int_byte & int_bit) == new_value:
                    if new_value:
                        int_byte += int_bit
                    else:
                        int_byte -= int_bit

                    self._myfh.seek(byte_address)
                    self._myfh.write(int_byte.to_bytes(1, byteorder="little"))
                    if self._buffedwrite:
                        self._myfh.flush()

        elif request == 19220:
            # Counterwert auf 0 setzen
            dev_position = arg[0]
            bit_field = int.from_bytes(arg[2:], byteorder="little")
            io_byte = -1

            for i in range(16):
                if bool(bit_field & 1 << i):
                    io_byte = self.device[dev_position].offset \
                              + int(self.device[dev_position]._lst_counter[i])
                    break

            if io_byte == -1:
                raise RuntimeError("could not reset counter io in file")

            with self._myfh_lck:
                self._myfh.seek(io_byte)
                self._myfh.write(b'\x00\x00\x00\x00')
                if self._buffedwrite:
                    self._myfh.flush()

    def autorefresh_all(self) -> None:
        """Setzt alle Devices in autorefresh Funktion."""
        for dev in self.device:
            dev.autorefresh()

    def cleanup(self) -> None:
        """Beendet autorefresh und alle Threads."""
        self._exit_level |= 2
        self.exit(full=True)

    def cycleloop(self, func, cycletime=50, blocking=True):
        """
        Startet den Cycleloop.

        Der aktuelle Programmthread wird hier bis Aufruf von
        .exit() "gefangen". Er fuehrt nach jeder Aktualisierung
        des Prozessabbilds die uebergebene Funktion "func" aus und arbeitet sie
        ab. Waehrend der Ausfuehrung der Funktion wird das Prozessabbild nicht
        weiter aktualisiert. Die Inputs behalten bis zum Ende den aktuellen
        Wert. Gesetzte Outputs werden nach Ende des Funktionsdurchlaufs in das
        Prozessabbild geschrieben.

        Verlassen wird der Cycleloop, wenn die aufgerufene Funktion einen
        Rueckgabewert nicht gleich None liefert (z.B. return True), oder durch
        Aufruf von .exit().

        HINWEIS: Die Aktualisierungszeit und die Laufzeit der Funktion duerfen
        die eingestellte autorefresh Zeit, bzw. uebergebene cycletime nicht
        ueberschreiten!

        Ueber den Parameter cycletime wird die gewuenschte Zukluszeit der
        uebergebenen Funktion gesetzt. Der Standardwert betraegt
        50 Millisekunden, in denen das Prozessabild eingelesen, die uebergebene
        Funktion ausgefuert und das Prozessabbild geschrieben wird.

        :param func: Funktion, die ausgefuehrt werden soll
        :param cycletime: Zykluszeit in Millisekunden - Standardwert 50 ms
        :param blocking: Wenn False, blockiert das Programm hier NICHT
        :return: None or the return value of the cycle function
        """
        # Prüfen ob ein Loop bereits läuft
        if self._looprunning:
            raise RuntimeError(
                "can not start multiple loops mainloop/cycleloop"
            )

        # Prüfen ob Devices in autorefresh sind
        if len(self._lst_refresh) == 0:
            raise RuntimeError(
                "no device with autorefresh activated - use autorefresh=True "
                "or call .autorefresh_all() before entering cycleloop"
            )

        # Prüfen ob Funktion callable ist
        if not callable(func):
            raise RuntimeError(
                "registered function '{0}' ist not callable".format(func)
            )

        # Thread erstellen, wenn nicht blockieren soll
        if not blocking:
            self._th_mainloop = Thread(
                target=self.cycleloop,
                args=(func,),
                kwargs={"cycletime": cycletime, "blocking": True}
            )
            self._th_mainloop.start()
            return

        # Zykluszeit übernehmen
        old_cycletime = self._imgwriter.refresh
        if not cycletime == self._imgwriter.refresh:
            # Set new cycle time and wait one imgwriter cycle to sync fist cycle
            self._imgwriter.refresh = cycletime
            self._imgwriter.newdata.clear()
            self._imgwriter.newdata.wait(self._imgwriter._refresh)

        # Benutzerevent
        self.exitsignal.clear()

        # Cycleloop starten
        self._exit.clear()
        self._looprunning = True
        cycleinfo = helpermodule.Cycletools(self._imgwriter.refresh, self)
        e = None  # Exception
        ec = None  # Return value of cycle_function
        self._imgwriter.newdata.clear()
        try:
            while ec is None and not cycleinfo.last:
                # Auf neue Daten warten und nur ausführen wenn set()
                if not self._imgwriter.newdata.wait(2.5):
                    if not self._imgwriter.is_alive():
                        self.exit(full=False)
                        e = RuntimeError("autorefresh thread not running")
                        break

                    # Just warn, user has to use maxioerrors to kill program
                    warnings.warn(RuntimeWarning(
                        "no new io data in cycle loop for 2500 milliseconds"
                    ))
                    cycleinfo.last = self._exit.is_set()
                    continue

                self._imgwriter.newdata.clear()

                # Vor Aufruf der Funktion autorefresh sperren
                self._imgwriter.lck_refresh.acquire()

                # Vorbereitung für cycleinfo
                cycleinfo._start_timer = default_timer()
                cycleinfo.last = self._exit.is_set()

                # Funktion aufrufen und auswerten
                ec = func(cycleinfo)
                cycleinfo._docycle()

                # autorefresh freigeben
                self._imgwriter.lck_refresh.release()
        except Exception as ex:
            if self._imgwriter.lck_refresh.locked():
                self._imgwriter.lck_refresh.release()
            if self._th_mainloop is None:
                self.exit(full=False)
            e = ex
        finally:
            # Cycleloop beenden
            self._looprunning = False
            self._th_mainloop = None

        # Alte autorefresh Zeit setzen
        self._imgwriter.refresh = old_cycletime

        # Exitstrategie ausführen
        self.__exit_jobs()

        # Auf Fehler prüfen die im loop geworfen wurden
        if e is not None:
            raise e

        return ec

    def exit(self, full=True) -> None:
        """
        Beendet mainloop() und optional autorefresh.

        Wenn sich das Programm im mainloop() befindet, wird durch Aufruf
        von exit() die Kontrolle wieder an das Hauptprogramm zurueckgegeben.

        Der Parameter full ist mit True vorbelegt und entfernt alle Devices aus
        dem autorefresh. Der Thread fuer die Prozessabbildsynchronisierung
        wird dann gestoppt und das Programm kann sauber beendet werden.

        :param full: Entfernt auch alle Devices aus autorefresh
        """
        self._exit_level |= 1 if full else 0

        # Echten Loopwert vor Events speichern
        full = full and not self._looprunning

        # Benutzerevent
        self.exitsignal.set()

        self._exit.set()
        self._waitexit.set()

        # Auf beenden von mainloop thread warten
        if self._th_mainloop is not None and self._th_mainloop.is_alive():
            self._th_mainloop.join(2.5)

        if full:
            self.__exit_jobs()

    def export_replaced_ios(self, filename="replace_ios.conf") -> None:
        """
        Exportiert ersetzte IOs dieser Instanz.

        Exportiert alle ersetzten IOs, welche mit .replace_io(...) angelegt
        wurden. Die Datei kann z.B. fuer RevPiPyLoad verwendet werden um Daten
        in den neuen Formaten per MQTT zu uebertragen oder mit RevPiPyControl
        anzusehen.

        @param filename Dateiname fuer Exportdatei
        """
        acheck(str, filename=filename)

        cp = ConfigParser()
        for io in self.io:
            if isinstance(io, StructIO):

                # Required values
                cp.add_section(io.name)
                cp[io.name]["replace"] = io._parentio_name
                cp[io.name]["frm"] = io.frm

                # Optional values
                if io._bitshift:
                    cp[io.name]["bit"] = str(io._bitaddress)
                if io._byteorder != "little":
                    cp[io.name]["byteorder"] = io._byteorder
                if io._wordorder:
                    cp[io.name]["wordorder"] = io._wordorder
                if type(io.defaultvalue) is bytes:
                    if any(io.defaultvalue):
                        # Convert each byte to an integer
                        cp[io.name]["defaultvalue"] = \
                            " ".join(map(str, io.defaultvalue))
                elif io.defaultvalue != 0:
                    cp[io.name]["defaultvalue"] = str(io.defaultvalue)
                if io.bmk != "":
                    cp[io.name]["bmk"] = io.bmk
                if io._export & 2:
                    cp[io.name]["export"] = str(io._export & 1)

        try:
            with open(filename, "w") as fh:
                cp.write(fh)
        except Exception as e:
            raise RuntimeError(
                "could not write export file '{0}' | {1}"
                "".format(filename, e)
            )

    def get_jconfigrsc(self) -> dict:
        """
        Laedt die piCtory Konfiguration und erstellt ein <class 'dict'>.

        :return: <class 'dict'> der piCtory Konfiguration
        """
        # piCtory Konfiguration prüfen
        if self._configrsc is not None:
            if not access(self._configrsc, F_OK | R_OK):
                raise RuntimeError(
                    "can not access pictory configuration at {0}".format(
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
                    "can not access known pictory configurations at {0} - "
                    "use 'configrsc' parameter so specify location"
                    "".format(", ".join(lst_rsc))
                )

        with open(self._configrsc, "r") as fhconfigrsc:
            try:
                jdata = jload(fhconfigrsc)
            except Exception:
                raise RuntimeError(
                    "can not read piCtory configuration - check your hardware "
                    "configuration http://revpi_ip/"
                )
            return jdata

    def handlesignalend(self, cleanupfunc=None) -> None:
        """
        Signalhandler fuer Programmende verwalten.

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

        :param cleanupfunc: Funktion wird nach dem Beenden ausgefuehrt
        """
        # Prüfen ob Funktion callable ist
        if not (cleanupfunc is None or callable(cleanupfunc)):
            raise RuntimeError(
                "registered function '{0}' ist not callable"
                "".format(cleanupfunc)
            )
        self.__cleanupfunc = cleanupfunc
        signal(SIGINT, self.__evt_exit)
        signal(SIGTERM, self.__evt_exit)

    def mainloop(self, blocking=True) -> None:
        """
        Startet den Mainloop mit Eventueberwachung.

        Der aktuelle Programmthread wird hier bis Aufruf von
        RevPiDevicelist.exit() "gefangen" (es sei denn blocking=False). Er
        durchlaeuft die Eventueberwachung und prueft Aenderungen der, mit
        einem Event registrierten, IOs. Wird eine Veraenderung erkannt,
        fuert das Programm die dazugehoerigen Funktionen der Reihe nach aus.

        Wenn der Parameter "blocking" mit False angegeben wird, aktiviert
        dies die Eventueberwachung und blockiert das Programm NICHT an der
        Stelle des Aufrufs. Eignet sich gut fuer die GUI Programmierung, wenn
        Events vom RevPi benoetigt werden, aber das Programm weiter ausgefuehrt
        werden soll.

        :param blocking: Wenn False, blockiert das Programm hier NICHT
        """
        # Prüfen ob ein Loop bereits läuft
        if self._looprunning:
            raise RuntimeError(
                "can not start multiple loops mainloop/cycleloop"
            )

        # Prüfen ob Devices in autorefresh sind
        if len(self._lst_refresh) == 0:
            raise RuntimeError(
                "no device with autorefresh activated - use autorefresh=True "
                "or call .autorefresh_all() before entering mainloop"
            )

        # Thread erstellen, wenn nicht blockieren soll
        if not blocking:
            self._th_mainloop = Thread(
                target=self.mainloop, kwargs={"blocking": True}
            )
            self._th_mainloop.start()
            return

        # Benutzerevent
        self.exitsignal.clear()

        # Event säubern vor Eintritt in Mainloop
        self._exit.clear()
        self._looprunning = True

        # Beim Eintritt in mainloop Bytecopy erstellen und prefire anhängen
        for dev in self._lst_refresh:
            with dev._filelock:
                dev._ba_datacp = dev._ba_devdata[:]

                # Prefire Events vorbereiten
                for io in dev._dict_events:
                    for regfunc in dev._dict_events[io]:
                        if not regfunc.prefire:
                            continue

                        if regfunc.edge == BOTH \
                                or regfunc.edge == RISING and io.value \
                                or regfunc.edge == FALLING and not io.value:
                            if regfunc.as_thread:
                                self._imgwriter._eventqth.put(
                                    (regfunc, io._name, io.value), False
                                )
                            else:
                                self._imgwriter._eventq.put(
                                    (regfunc, io._name, io.value), False
                                )

        # ImgWriter mit Eventüberwachung aktivieren
        self._imgwriter._collect_events(True)
        e = None
        runtime = -1 if self._debug == -1 else 0

        while not self._exit.is_set():

            # Laufzeit der Eventqueue auf 0 setzen
            if self._imgwriter._eventq.qsize() == 0:
                runtime = -1 if self._debug == -1 else 0

            try:
                tup_fire = self._imgwriter._eventq.get(timeout=1)

                # Messung Laufzeit der Queue starten
                if runtime == 0:
                    runtime = default_timer()

                # Direct callen da Prüfung in io.IOBase.reg_event ist
                tup_fire[0].func(tup_fire[1], tup_fire[2])
                self._imgwriter._eventq.task_done()

                # Laufzeitprüfung
                if runtime != -1 and \
                        default_timer() - runtime > self._imgwriter._refresh:
                    runtime = -1
                    warnings.warn(
                        "can not execute all event functions in one cycle - "
                        "optimize your event functions or rise .cycletime",
                        RuntimeWarning
                    )
            except Empty:
                if not self._exit.is_set() and not self._imgwriter.is_alive():
                    e = RuntimeError("autorefresh thread not running")
                    break
            except Exception as ex:
                e = ex
                break

        # Mainloop verlassen
        self._imgwriter._collect_events(False)
        self._looprunning = False
        self._th_mainloop = None

        # Auf Fehler prüfen die im loop geworfen wurden
        if e is not None:
            self.exit(full=False)
            self.__exit_jobs()
            raise e

        # Exitstrategie ausführen
        self.__exit_jobs()

    def readprocimg(self, device=None) -> bool:
        """
        Einlesen aller Inputs aller/eines Devices vom Prozessabbild.

        Devices mit aktiverem autorefresh werden ausgenommen!

        :param device: nur auf einzelnes Device anwenden
        :return: True, wenn Arbeiten an allen Devices erfolgreich waren
        """
        if device is None:
            mylist = self.device
        else:
            dev = device if isinstance(device, devicemodule.Device) \
                else self.device.__getitem__(device)

            if dev._selfupdate:
                raise RuntimeError(
                    "can not read process image, while device '{0}|{1}'"
                    "is in autorefresh mode".format(dev._position, dev._name)
                )
            mylist = [dev]

        # Daten komplett einlesen
        self._myfh_lck.acquire()
        try:
            self._myfh.seek(0)
            bytesbuff = self._myfh.read(self._length)
        except IOError as e:
            self._gotioerror("readprocimg", e)
            return False
        finally:
            self._myfh_lck.release()

        for dev in mylist:
            if not dev._selfupdate:

                # FileHandler sperren
                dev._filelock.acquire()

                if self._monitoring or dev._shared_procimg:
                    # Alles vom Bus einlesen
                    dev._ba_devdata[:] = bytesbuff[dev._slc_devoff]
                else:
                    # Inputs vom Bus einlesen
                    dev._ba_devdata[dev._slc_inp] = bytesbuff[dev._slc_inpoff]

                dev._filelock.release()

        return True

    def resetioerrors(self) -> None:
        """Setzt aktuellen IOError-Zaehler auf 0 zurueck."""
        self._ioerror = 0

    def setdefaultvalues(self, device=None) -> None:
        """
        Alle Outputbuffer werden auf die piCtory default Werte gesetzt.

        :param device: nur auf einzelnes Device anwenden
        """
        if self._monitoring:
            raise RuntimeError(
                "can not set default values, while system is in monitoring "
                "mode"
            )

        if device is None:
            mylist = self.device
        else:
            dev = device if isinstance(device, devicemodule.Device) \
                else self.device.__getitem__(device)
            mylist = [dev]

        for dev in mylist:
            for io in dev.get_outputs():
                io.set_value(io._defaultvalue)

    def syncoutputs(self, device=None) -> bool:
        """
        Lesen aller aktuell gesetzten Outputs im Prozessabbild.

        Devices mit aktiverem autorefresh werden ausgenommen!

        :param device: nur auf einzelnes Device anwenden
        :return: True, wenn Arbeiten an allen Devices erfolgreich waren
        """
        if device is None:
            mylist = self.device
        else:
            dev = device if isinstance(device, devicemodule.Device) \
                else self.device.__getitem__(device)

            if dev._selfupdate:
                raise RuntimeError(
                    "can not sync outputs, while device '{0}|{1}'"
                    "is in autorefresh mode".format(dev._position, dev._name)
                )
            mylist = [dev]

        self._myfh_lck.acquire()
        try:
            self._myfh.seek(0)
            bytesbuff = self._myfh.read(self._length)
        except IOError as e:
            self._gotioerror("syncoutputs", e)
            return False
        finally:
            self._myfh_lck.release()

        for dev in mylist:
            if not dev._selfupdate:
                dev._filelock.acquire()
                dev._ba_devdata[dev._slc_out] = bytesbuff[dev._slc_outoff]
                dev._filelock.release()

        return True

    def writeprocimg(self, device=None) -> bool:
        """
        Schreiben aller Outputs aller Devices ins Prozessabbild.

        Devices mit aktiverem autorefresh werden ausgenommen!

        :param device: nur auf einzelnes Device anwenden
        :return: True, wenn Arbeiten an allen Devices erfolgreich waren
        """
        if self._monitoring:
            raise RuntimeError(
                "can not write process image, while system is in monitoring "
                "mode"
            )

        if device is None:
            mylist = self.device
        else:
            dev = device if isinstance(device, devicemodule.Device) \
                else self.device.__getitem__(device)

            if dev._selfupdate:
                raise RuntimeError(
                    "can not write process image, while device '{0}|{1}'"
                    "is in autorefresh mode".format(dev._position, dev._name)
                )
            mylist = [dev]

        global_ex = None
        for dev in mylist:
            if dev._selfupdate:
                # Do not update this device
                continue

            dev._filelock.acquire()

            if dev._shared_procimg:
                for io in dev._shared_write:
                    if not io._write_to_procimg():
                        global_ex = IOError(
                            "error on shared procimg while write"
                        )
                dev._shared_write.clear()
            else:
                # Outpus auf Bus schreiben
                self._myfh_lck.acquire()
                try:
                    self._myfh.seek(dev._slc_outoff.start)
                    self._myfh.write(dev._ba_devdata[dev._slc_out])
                except IOError as e:
                    global_ex = e
                finally:
                    self._myfh_lck.release()

            dev._filelock.release()

        if self._buffedwrite:
            try:
                self._myfh.flush()
            except IOError as e:
                global_ex = e

        if global_ex:
            self._gotioerror("writeprocimg", global_ex)
            return False

        return True

    debug = property(_get_debug, _set_debug)
    configrsc = property(_get_configrsc)
    cycletime = property(_get_cycletime, _set_cycletime)
    ioerrors = property(_get_ioerrors)
    length = property(_get_length)
    maxioerrors = property(_get_maxioerrors, _set_maxioerrors)
    monitoring = property(_get_monitoring)
    procimg = property(_get_procimg)
    replace_io_file = property(_get_replace_io_file)
    simulator = property(_get_simulator)


class RevPiModIOSelected(RevPiModIO):
    """
    Klasse fuer die Verwaltung einzelner Devices aus piCtory.

    Diese Klasse uebernimmt nur angegebene Devices der piCtory Konfiguration
    und bildet sie inkl. IOs ab. Sie uebernimmt die exklusive Verwaltung des
    Adressbereichs im Prozessabbild an dem sich die angegebenen Devices
    befinden und stellt sicher, dass die Daten synchron sind.
    """

    __slots__ = ()

    def __init__(
            self, deviceselection, autorefresh=False, monitoring=False,
            syncoutputs=True, procimg=None, configrsc=None,
            simulator=False, debug=True, replace_io_file=None,
            shared_procimg=False, direct_output=False):
        """
        Instantiiert nur fuer angegebene Devices die Grundfunktionen.

        Der Parameter deviceselection kann eine einzelne
        Device Position / einzelner Device Name sein oder eine Liste mit
        mehreren Positionen / Namen

        :param deviceselection: Positionsnummer oder Devicename
        :ref: :func:`RevPiModIO.__init__(...)`
        """
        super().__init__(
            autorefresh, monitoring, syncoutputs, procimg, configrsc,
            simulator, debug, replace_io_file, shared_procimg, direct_output
        )

        if type(deviceselection) is not DevSelect:
            # Convert to tuple
            if type(deviceselection) not in (list, tuple):
                deviceselection = (deviceselection,)

            # Automatic search for name and position depends on type int / str
            self._devselect = DevSelect(DeviceType.IGNORED, "", deviceselection)

        else:
            self._devselect = deviceselection

        self._configure(self.get_jconfigrsc())

        if len(self.device) == 0:
            if self._devselect.type:
                raise DeviceNotFoundError(
                    "could not find ANY given {0} devices in config"
                    "".format(self._devselect.type)
                )
            else:
                raise DeviceNotFoundError(
                    "could not find ANY given devices in config"
                )
        elif not self._devselect.other_device_key \
                and len(self.device) != len(self._devselect.values):
            if self._devselect.type:
                raise DeviceNotFoundError(
                    "could not find ALL given {0} devices in config"
                    "".format(self._devselect.type)
                )
            else:
                raise DeviceNotFoundError(
                    "could not find ALL given devices in config"
                )


class RevPiModIODriver(RevPiModIOSelected):
    """
    Klasse um eigene Treiber fuer die virtuellen Devices zu erstellen.

    Mit dieser Klasse werden nur angegebene Virtuelle Devices mit RevPiModIO
    verwaltet. Bei Instantiierung werden automatisch die Inputs und Outputs
    verdreht, um das Schreiben der Inputs zu ermoeglichen. Die Daten koennen
    dann ueber logiCAD an den Devices abgerufen werden.
    """

    __slots__ = ()

    def __init__(
            self, virtdev, autorefresh=False,
            syncoutputs=True, procimg=None, configrsc=None, debug=True,
            replace_io_file=None, shared_procimg=False, direct_output=False):
        """
        Instantiiert die Grundfunktionen.

        Parameter 'monitoring' und 'simulator' stehen hier nicht zur
        Verfuegung, da diese automatisch gesetzt werden.

        :param virtdev: Virtuelles Device oder mehrere als <class 'list'>
        :ref: :func:`RevPiModIO.__init__()`
        """
        # Parent mit monitoring=False und simulator=True laden
        if type(virtdev) not in (list, tuple):
            virtdev = (virtdev,)
        dev_select = DevSelect(DeviceType.VIRTUAL, "", virtdev)
        super().__init__(
            dev_select, autorefresh, False, syncoutputs, procimg, configrsc,
            True, debug, replace_io_file, shared_procimg, direct_output
        )


def run_plc(
        func, cycletime=50, replace_io_file=None, debug=True,
        procimg=None, configrsc=None):
    """
    Run Revoluton Pi as real plc with cycle loop and exclusive IO access.

    This function is just a shortcut to run the module in cycle loop mode and
    handle the program exit signal. You will access the .io, .core, .device
    via the cycletools in your cycle function.

    Shortcut for this source code:
        rpi = RevPiModIO(autorefresh=True, replace_io_file=..., debug=...)
        rpi.handlesignalend()
        return rpi.cycleloop(func, cycletime)

    :param func: Function to run every set milliseconds
    :param cycletime: Cycle time in milliseconds
    :param replace_io_file: Load replace IO configuration from file
    :param debug: Print all warnings and detailed error messages
    :param procimg: Use different process image
    :param configrsc: Use different piCtory configuration
    :return: None or the return value of the cycle function
    """
    rpi = RevPiModIO(
        autorefresh=True,
        replace_io_file=replace_io_file,
        debug=debug,
        procimg=procimg,
        configrsc=configrsc,
    )
    rpi.handlesignalend()
    return rpi.cycleloop(func, cycletime)

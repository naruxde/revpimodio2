# -*- coding: utf-8 -*-
"""RevPiModIO Modul fuer die Verwaltung der IOs."""
import struct
from re import match as rematch
from threading import Event

from revpimodio2 import BOTH, FALLING, INP, MEM, OUT, RISING, consttostr, \
    PROCESS_IMAGE_SIZE

__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2020 Sven Sager"
__license__ = "LGPLv3"

try:
    # Funktioniert nur auf Unix
    from fcntl import ioctl
except Exception:
    ioctl = None


class IOEvent(object):
    """Basisklasse fuer IO-Events."""

    __slots__ = "as_thread", "delay", "edge", "func", "overwrite", "prefire"

    def __init__(self, func, edge, as_thread, delay, overwrite, prefire):
        """Init IOEvent class."""
        self.as_thread = as_thread
        self.delay = delay
        self.edge = edge
        self.func = func
        self.overwrite = overwrite
        self.prefire = prefire


class IOList(object):
    """Basisklasse fuer direkten Zugriff auf IO Objekte."""

    def __init__(self):
        """Init IOList class."""
        self.__dict_iobyte = {k: [] for k in range(PROCESS_IMAGE_SIZE)}
        self.__dict_iorefname = {}

    def __contains__(self, key):
        """
        Prueft ob IO existiert.

        :param key: IO-Name <class 'str'> oder Bytenummer <class 'int'>
        :return: True, wenn IO vorhanden / Byte belegt
        """
        if type(key) == int:
            return len(self.__dict_iobyte.get(key, [])) > 0
        else:
            return hasattr(self, key) and type(getattr(self, key)) != DeadIO

    def __delattr__(self, key):
        """
        Entfernt angegebenen IO.

        :param key: IO zum entfernen
        """
        io_del = object.__getattribute__(self, key)

        # Alte Events vom Device löschen
        io_del.unreg_event()

        # IO aus Byteliste und Attributen entfernen
        if io_del._bitshift:
            self.__dict_iobyte[io_del.address][io_del._bitaddress] = None

            # Do not use any() because we want to know None, not 0
            if self.__dict_iobyte[io_del.address] == \
                    [None, None, None, None, None, None, None, None]:
                self.__dict_iobyte[io_del.address] = []
        else:
            self.__dict_iobyte[io_del.address].remove(io_del)

        object.__delattr__(self, key)
        io_del._parentdevice._update_my_io_list()

    def __getattr__(self, key):
        """
        Verwaltet geloeschte IOs (Attribute, die nicht existieren).

        :param key: Name oder Byte eines alten IOs
        :return: Alten IO, wenn in Ref-Listen
        """
        if key in self.__dict_iorefname:
            return self.__dict_iorefname[key]
        else:
            raise AttributeError("can not find io '{0}'".format(key))

    def __getitem__(self, key):
        """
        Ruft angegebenen IO ab.

        Wenn der Key <class 'str'> ist, wird ein einzelner IO geliefert. Wird
        der Key als <class 'int'> uebergeben, wird eine <class 'list'>
        geliefert mit 0, 1 oder 8 Eintraegen.
        Wird als Key <class 'slice'> gegeben, werden die Listen in einer Liste
        zurueckgegeben.

        :param key: IO Name als <class 'str> oder Byte als <class 'int'>.
        :return: IO Objekt oder Liste der IOs
        """
        if type(key) == int:
            if key not in self.__dict_iobyte:
                raise IndexError("byte '{0}' does not exist".format(key))
            return self.__dict_iobyte[key]
        elif type(key) == slice:
            return [
                self.__dict_iobyte[int_io]
                for int_io in range(
                    key.start, key.stop, 1 if key.step is None else key.step
                )
            ]
        else:
            return getattr(self, key)

    def __iter__(self):
        """
        Gibt Iterator aller IOs zurueck.

        :return: Iterator aller IOs
        """
        for int_io in sorted(self.__dict_iobyte):
            for io in self.__dict_iobyte[int_io]:
                if io is not None:
                    yield io

    def __len__(self):
        """
        Gibt die Anzahl aller IOs zurueck.

        :return: Anzahl aller IOs
        """
        int_ios = 0
        for int_io in self.__dict_iobyte:
            for io in self.__dict_iobyte[int_io]:
                if io is not None:
                    int_ios += 1
        return int_ios

    def __setattr__(self, key, value):
        """Verbietet aus Leistungsguenden das direkte Setzen von Attributen."""
        if key in (
                "_IOList__dict_iobyte",
                "_IOList__dict_iorefname"
        ):
            object.__setattr__(self, key, value)
        else:
            raise AttributeError(
                "direct assignment is not supported - use .value Attribute"
            )

    def __private_replace_oldio_with_newio(self, io) -> None:
        """
        Ersetzt bestehende IOs durch den neu Registrierten.

        :param io: Neuer IO der eingefuegt werden soll
        """
        # Scanbereich festlegen
        if io._bitshift:
            scan_start = io._parentio_address
            scan_stop = scan_start + io._parentio_length
        else:
            scan_start = io.address
            scan_stop = scan_start + (1 if io._length == 0 else io._length)

        # Defaultvalue über mehrere Bytes sammeln
        calc_defaultvalue = b''

        for i in range(scan_start, scan_stop):
            for oldio in self.__dict_iobyte[i]:

                if type(oldio) == StructIO:
                    # Hier gibt es schon einen neuen IO
                    if oldio._bitshift:
                        if io._bitshift == oldio._bitshift:
                            raise MemoryError(
                                "bit {0} already assigned to '{1}'".format(
                                    io._bitaddress, oldio._name
                                )
                            )
                    else:
                        # Bereits überschriebene bytes sind ungültig
                        raise MemoryError(
                            "new io '{0}' overlaps memory of '{1}'".format(
                                io._name, oldio._name
                            )
                        )
                elif oldio is not None:
                    # IOs im Speicherbereich des neuen IO merken
                    if io._bitshift:
                        # ios für ref bei bitaddress speichern
                        self.__dict_iorefname[oldio._name] = DeadIO(oldio)
                    else:
                        # Defaultwert berechnen
                        oldio.byteorder = io._byteorder
                        if io._byteorder == "little":
                            calc_defaultvalue += oldio._defaultvalue
                        else:
                            calc_defaultvalue = \
                                oldio._defaultvalue + calc_defaultvalue

                    # ios aus listen entfernen
                    delattr(self, oldio._name)

        if io._defaultvalue is None:
            # Nur bei StructIO und keiner gegebenen defaultvalue übernehmen
            if io._bitshift:
                io._defaultvalue = bool(
                    io._parentio_defaultvalue[
                        io._parentio_address - io.address
                    ] & io._bitshift
                )
            else:
                io._defaultvalue = calc_defaultvalue

    def _private_register_new_io_object(self, new_io) -> None:
        """
        Registriert neues IO Objekt unabhaenging von __setattr__.

        :param new_io: Neues IO Objekt
        """
        if isinstance(new_io, IOBase):
            if hasattr(self, new_io._name):
                raise AttributeError(
                    "attribute {0} already exists - can not set io"
                    "".format(new_io._name)
                )

            if type(new_io) is StructIO:
                self.__private_replace_oldio_with_newio(new_io)

            object.__setattr__(self, new_io._name, new_io)

            # Bytedict für Adresszugriff anpassen
            if new_io._bitshift:
                if len(self.__dict_iobyte[new_io.address]) != 8:
                    # "schnell" 8 Einträge erstellen da es BIT IOs sind
                    self.__dict_iobyte[new_io.address] += \
                        [None, None, None, None, None, None, None, None]
                self.__dict_iobyte[new_io.address][new_io._bitaddress] = new_io
            else:
                self.__dict_iobyte[new_io.address].append(new_io)

            if type(new_io) is StructIO:
                new_io._parentdevice._update_my_io_list()
        else:
            raise TypeError("io must be <class 'IOBase'> or sub class")


class DeadIO(object):
    """Klasse, mit der ersetzte IOs verwaltet werden."""

    __slots__ = "__deadio"

    def __init__(self, deadio):
        """
        Instantiierung der DeadIO-Klasse.

        :param deadio: IO, der ersetzt wurde
        """
        self.__deadio = deadio

    def replace_io(self, name: str, frm: str, **kwargs) -> None:
        """
        Stellt Funktion fuer weiter Bit-Ersetzungen bereit.

        :ref: :func:IntIOReplaceable.replace_io()
        """
        self.__deadio.replace_io(name, frm, **kwargs)

    _parentdevice = property(lambda self: None)


class IOBase(object):
    """
    Basisklasse fuer alle IO-Objekte.

    Die Basisfunktionalitaet ermoeglicht das Lesen und Schreiben der Werte
    als <class bytes'> oder <class 'bool'>. Dies entscheidet sich bei der
    Instantiierung.
    Wenn eine Bittadresse angegeben wird, werden <class 'bool'>-Werte erwartet
    und zurueckgegeben, ansonsten <class bytes'>.

    Diese Klasse dient als Basis fuer andere IO-Klassen mit denen die Werte
    auch als <class 'int'> verwendet werden koennen.
    """

    __slots__ = "__bit_ioctl_off", "__bit_ioctl_on", "_bitaddress", \
                "_bitshift", "_bitlength", "_byteorder", "_defaultvalue", \
                "_export", "_iotype", "_length", "_name", "_parentdevice", \
                "_read_only_io", "_signed", "_slc_address", "bmk"

    def __init__(self, parentdevice, valuelist: list, iotype: int, byteorder: str, signed: bool):
        """
        Instantiierung der IOBase-Klasse.

        :param parentdevice: Parentdevice auf dem der IO liegt
        :param valuelist: Datenliste fuer Instantiierung
            ["name","defval","bitlen","startaddrdev",exp,"idx","bmk","bitaddr"]
        :param iotype: <class 'int'> Wert
        :param byteorder: Byteorder 'little'/'big' fuer <class 'int'> Berechnung
        :param signed: Intberechnung mit Vorzeichen durchfuehren
        """
        # ["name","defval","bitlen","startaddrdev",exp,"idx","bmk","bitaddr"]
        # [  0   ,   1    ,   2    ,       3      , 4 ,  5  ,  6  ,    7    ]
        self._parentdevice = parentdevice

        # Bitadressen auf Bytes aufbrechen und umrechnen
        self._bitaddress = -1 if valuelist[7] == "" else int(valuelist[7]) % 8
        self._bitshift = None if self._bitaddress == -1 else 1 << self._bitaddress

        # Längenberechnung
        self._bitlength = int(valuelist[2])
        self._length = 1 if self._bitaddress == 0 else int(self._bitlength / 8)

        self.__bit_ioctl_off = None
        self.__bit_ioctl_on = None
        self._read_only_io = iotype != OUT
        self._byteorder = byteorder
        self._iotype = iotype
        self._name = valuelist[0]
        self._signed = signed
        self.bmk = valuelist[6]
        self._export = int(valuelist[4]) & 1

        int_startaddress = int(valuelist[3])
        if self._bitshift:
            # Höhere Bits als 7 auf nächste Bytes umbrechen
            int_startaddress += int(int(valuelist[7]) / 8)
            self._slc_address = slice(
                int_startaddress, int_startaddress + 1
            )

            # Defaultvalue ermitteln, sonst False
            if valuelist[1] is None and type(self) == StructIO:
                self._defaultvalue = None
            else:
                try:
                    self._defaultvalue = bool(int(valuelist[1]))
                except Exception:
                    self._defaultvalue = False

            # Ioctl für Bitsetzung setzen
            self.__bit_ioctl_off = struct.pack(
                "<HB", self._get_address(), self._bitaddress
            )
            self.__bit_ioctl_on = self.__bit_ioctl_off + b'\x01'
        else:
            self._slc_address = slice(
                int_startaddress, int_startaddress + self._length
            )
            if str(valuelist[1]).isdigit():
                # Defaultvalue aus Zahl in Bytes umrechnen
                self._defaultvalue = int(valuelist[1]).to_bytes(
                    self._length, byteorder=self._byteorder
                )
            elif valuelist[1] is None and type(self) == StructIO:
                # Auf None setzen um später berechnete Werte zu übernehmen
                self._defaultvalue = None
            elif type(valuelist[1]) == bytes:
                # Defaultvalue direkt von bytes übernehmen
                if len(valuelist[1]) == self._length:
                    self._defaultvalue = valuelist[1]
                else:
                    raise ValueError(
                        "given bytes for default value must have a length "
                        "of {0} but {1} was given"
                        "".format(self._length, len(valuelist[1]))
                    )
            else:
                # Defaultvalue mit leeren Bytes füllen
                self._defaultvalue = bytes(self._length)

                # Versuchen String in ASCII Bytes zu wandeln
                if type(valuelist[1]) == str:
                    try:
                        buff = valuelist[1].encode("ASCII")
                        if len(buff) <= self._length:
                            self._defaultvalue = \
                                buff + bytes(self._length - len(buff))
                    except Exception:
                        pass

    def __bool__(self):
        """
        <class 'bool'>-Wert der Klasse.

        :return: <class 'bool'> Nur False wenn False oder 0 sonst True
        """
        if self._bitshift:
            return bool(
                self._parentdevice._ba_devdata[self._slc_address.start]
                & self._bitshift
            )
        else:
            return any(self._parentdevice._ba_devdata[self._slc_address])

    def __call__(self, value=None):
        if value is None:
            # Inline get_value()
            if self._bitshift:
                return bool(
                    self._parentdevice._ba_devdata[self._slc_address.start]
                    & self._bitshift
                )
            else:
                return bytes(self._parentdevice._ba_devdata[self._slc_address])
        else:
            self.set_value(value)

    def __len__(self):
        """
        Gibt die Bytelaenge des IO zurueck.

        :return: Bytelaenge des IO - 0 bei BITs
        """
        return 0 if self._bitaddress > 0 else self._length

    def __str__(self):
        """
        <class 'str'>-Wert der Klasse.

        :return: Namen des IOs
        """
        return self._name

    def __reg_xevent(self, func, delay: int, edge: int, as_thread: bool, overwrite: bool, prefire: bool) -> None:
        """
        Verwaltet reg_event und reg_timerevent.

        :param func: Funktion die bei Aenderung aufgerufen werden soll
        :param delay: Verzoegerung in ms zum Ausloesen - auch bei Wertaenderung
        :param edge: Ausfuehren bei RISING, FALLING or BOTH Wertaenderung
        :param as_thread: Bei True, Funktion als EventCallback-Thread ausfuehren
        :param overwrite: Wenn True, wird Event bei ueberschrieben
        :param prefire: Ausloesen mit aktuellem Wert, wenn mainloop startet
        """
        # Prüfen ob Funktion callable ist
        if not callable(func):
            raise ValueError(
                "registered function '{0}' is not callable".format(func)
            )
        if type(delay) != int or delay < 0:
            raise ValueError(
                "'delay' must be <class 'int'> and greater or equal 0"
            )
        if edge != BOTH and not self._bitshift:
            raise ValueError(
                "parameter 'edge' can be used with bit io objects only"
            )
        if prefire and self._parentdevice._modio._looprunning:
            raise RuntimeError(
                "prefire can not be used if mainloop is running"
            )

        if self not in self._parentdevice._dict_events:
            with self._parentdevice._filelock:
                self._parentdevice._dict_events[self] = \
                    [IOEvent(func, edge, as_thread, delay, overwrite, prefire)]
        else:
            # Prüfen ob Funktion schon registriert ist
            for regfunc in self._parentdevice._dict_events[self]:
                if regfunc.func != func:
                    # Nächsten Eintrag testen
                    continue

                if edge == BOTH or regfunc.edge == BOTH:
                    if self._bitshift:
                        raise RuntimeError(
                            "io '{0}' with function '{1}' already in list "
                            "with edge '{2}' - edge '{3}' not allowed anymore"
                            "".format(
                                self._name, func,
                                consttostr(regfunc.edge), consttostr(edge)
                            )
                        )
                    else:
                        raise RuntimeError(
                            "io '{0}' with function '{1}' already in list."
                            "".format(self._name, func)
                        )

                elif regfunc.edge == edge:
                    raise RuntimeError(
                        "io '{0}' with function '{1}' for given edge '{2}' "
                        "already in list".format(
                            self._name, func, consttostr(edge)
                        )
                    )

            # Eventfunktion einfügen
            with self._parentdevice._filelock:
                self._parentdevice._dict_events[self].append(
                    IOEvent(func, edge, as_thread, delay, overwrite, prefire)
                )

    def _get_address(self) -> int:
        """
        Gibt die absolute Byteadresse im Prozessabbild zurueck.

        :return: Absolute Byteadresse
        """
        return self._parentdevice._offset + self._slc_address.start

    def _get_byteorder(self) -> str:
        """
        Gibt konfigurierte Byteorder zurueck.

        :return: <class 'str'> Byteorder
        """
        return self._byteorder

    def _get_export(self) -> bool:
        """Return value of export flag."""
        return bool(self._export & 1)

    def _get_iotype(self) -> int:
        """
        Gibt io type zurueck.

        :return: <class 'int'> io type
        """
        return self._iotype

    def _set_export(self, value: bool) -> None:
        """Set value of export flag and remember this change for export."""
        if type(value) != bool:
            raise ValueError("Value must be <class 'bool'>")
        self._export = 2 + int(value)

    def _write_to_procimg(self) -> bool:
        """
        Write value of io directly to the process image.

        :return: True after successful write operation
        """
        if not self._parentdevice._shared_procimg:
            raise RuntimeError("device is not marked for shared_procimg")

        # note: Will not be removed from _shared_write on direct call

        if self._bitshift:
            # Write single bit to process image
            value = \
                self._parentdevice._ba_devdata[self._slc_address.start] & \
                self._bitshift
            if self._parentdevice._modio._run_on_pi:
                # IOCTL auf dem RevPi
                with self._parentdevice._modio._myfh_lck:
                    try:
                        # Set value durchführen (Funktion K+16)
                        ioctl(
                            self._parentdevice._modio._myfh,
                            19216,
                            self.__bit_ioctl_on if value
                            else self.__bit_ioctl_off
                        )
                    except Exception as e:
                        self._parentdevice._modio._gotioerror("ioset", e)
                        return False

            elif hasattr(self._parentdevice._modio._myfh, "ioctl"):
                # IOCTL über Netzwerk
                with self._parentdevice._modio._myfh_lck:
                    try:
                        self._parentdevice._modio._myfh.ioctl(
                            19216,
                            self.__bit_ioctl_on if value
                            else self.__bit_ioctl_off
                        )
                    except Exception as e:
                        self._parentdevice._modio._gotioerror(
                            "net_ioset", e)
                        return False

            else:
                # IOCTL in Datei simulieren
                try:
                    # Set value durchführen (Funktion K+16)
                    self._parentdevice._modio._simulate_ioctl(
                        19216,
                        self.__bit_ioctl_on if value
                        else self.__bit_ioctl_off
                    )
                except Exception as e:
                    self._parentdevice._modio._gotioerror("file_ioset", e)
                    return False

        else:
            value = bytes(self._parentdevice._ba_devdata[self._slc_address])
            with self._parentdevice._modio._myfh_lck:
                try:
                    self._parentdevice._modio._myfh.seek(
                        self._get_address()
                    )
                    self._parentdevice._modio._myfh.write(value)
                    if self._parentdevice._modio._buffedwrite:
                        self._parentdevice._modio._myfh.flush()
                except IOError as e:
                    self._parentdevice._modio._gotioerror("ioset", e)
                    return False

        return True

    def get_defaultvalue(self):
        """
        Gibt die Defaultvalue von piCtory zurueck.

        :return: Defaultvalue als <class 'byte'> oder <class 'bool'>
        """
        return self._defaultvalue

    def get_value(self):
        """
        Gibt den Wert des IOs zurueck.

        :return: IO-Wert als <class 'bytes'> oder <class 'bool'>
        """
        if self._bitshift:
            return bool(
                self._parentdevice._ba_devdata[self._slc_address.start]
                & self._bitshift
            )
        else:
            return bytes(self._parentdevice._ba_devdata[self._slc_address])

    def reg_event(
            self, func, delay=0, edge=BOTH, as_thread=False, prefire=False):
        """
        Registriert fuer IO ein Event bei der Eventueberwachung.

        Die uebergebene Funktion wird ausgefuehrt, wenn sich der IO Wert
        aendert. Mit Angabe von optionalen Parametern kann das
        Ausloeseverhalten gesteuert werden.

        HINWEIS: Die delay-Zeit muss in die .cycletime passen, ist dies nicht
        der Fall, wird IMMER aufgerundet!

        :param func: Funktion die bei Aenderung aufgerufen werden soll
        :param delay: Verzoegerung in ms zum Ausloesen wenn Wert gleich bleibt
        :param edge: Ausfuehren bei RISING, FALLING or BOTH Wertaenderung
        :param as_thread: Bei True, Funktion als EventCallback-Thread ausfuehren
        :param prefire: Ausloesen mit aktuellem Wert, wenn mainloop startet
        """
        self.__reg_xevent(func, delay, edge, as_thread, True, prefire)

    def reg_timerevent(self, func, delay, edge=BOTH, as_thread=False):
        """
        Registriert fuer IO einen Timer, welcher nach delay func ausfuehrt.

        Der Timer wird gestartet, wenn sich der IO Wert aendert und fuehrt die
        uebergebene Funktion aus - auch wenn sich der IO Wert in der
        zwischenzeit geaendert hat. Sollte der Timer nicht abelaufen sein und
        die Bedingugn erneut zutreffen, wird der Timer NICHT auf den delay Wert
        zurueckgesetzt oder ein zweites Mal gestartet. Fuer dieses Verhalten
        kann .reg_event(..., delay=wert) verwendet werden.

        HINWEIS: Die delay-Zeit muss in die .cycletime passen, ist dies nicht
        der Fall, wird IMMER aufgerundet!

        :param func: Funktion die bei Aenderung aufgerufen werden soll
        :param delay: Verzoegerung in ms zum Ausloesen - auch bei Wertaenderung
        :param edge: Ausfuehren bei RISING, FALLING or BOTH Wertaenderung
        :param as_thread: Bei True, Funktion als EventCallback-Thread ausfuehren
        """
        self.__reg_xevent(func, delay, edge, as_thread, False, False)

    def set_value(self, value) -> None:
        """
        Setzt den Wert des IOs.

        :param value: IO-Wert als <class bytes'> oder <class 'bool'>
        """
        if self._read_only_io:
            if self._iotype == INP:
                if self._parentdevice._modio._simulator:
                    raise RuntimeError(
                        "can not write to output '{0}' in simulator mode"
                        "".format(self._name)
                    )
                else:
                    raise RuntimeError(
                        "can not write to input '{0}'".format(self._name)
                    )
            elif self._iotype == MEM:
                raise RuntimeError(
                    "can not write to memory '{0}'".format(self._name)
                )
            raise RuntimeError(
                "the io object '{0}' is read only".format(self._name)
            )

        if self._bitshift:
            # Versuchen egal welchen Typ in Bool zu konvertieren
            value = bool(value)

            # Für Bitoperationen sperren
            self._parentdevice._filelock.acquire()

            if self._parentdevice._shared_procimg \
                    and self not in self._parentdevice._shared_write:
                # Mark this IO for write operations
                self._parentdevice._shared_write.append(self)

            # Hier gibt es immer nur ein byte, als int holen
            int_byte = self._parentdevice._ba_devdata[self._slc_address.start]

            # Aktuellen Wert vergleichen und ggf. setzen
            if not bool(int_byte & self._bitshift) == value:
                if value:
                    int_byte += self._bitshift
                else:
                    int_byte -= self._bitshift

                # Zurückschreiben wenn verändert
                self._parentdevice._ba_devdata[self._slc_address.start] = \
                    int_byte

            self._parentdevice._filelock.release()

        else:
            if type(value) != bytes:
                raise TypeError(
                    "'{0}' requires a <class 'bytes'> object, not {1}".format(
                        self._name, type(value)
                    )
                )

            if self._length != len(value):
                raise ValueError(
                    "'{0}' requires a <class 'bytes'> object of "
                    "length {1}, but {2} was given".format(
                        self._name, self._length, len(value)
                    )
                )

            if self._parentdevice._shared_procimg \
                    and self not in self._parentdevice._shared_write:
                with self._parentdevice._filelock:
                    # Mark this IO as changed
                    self._parentdevice._shared_write.append(self)

            self._parentdevice._ba_devdata[self._slc_address] = value

    def unreg_event(self, func=None, edge=None) -> None:
        """
        Entfernt ein Event aus der Eventueberwachung.

        :param func: Nur Events mit angegebener Funktion
        :param edge: Nur Events mit angegebener Funktion und angegebener Edge
        """
        if self in self._parentdevice._dict_events:
            if func is None:
                with self._parentdevice._filelock:
                    del self._parentdevice._dict_events[self]
            else:
                newlist = []
                for regfunc in self._parentdevice._dict_events[self]:
                    if regfunc.func != func or edge is not None \
                            and regfunc.edge != edge:
                        newlist.append(regfunc)

                # Wenn Funktionen übrig bleiben, diese übernehmen
                with self._parentdevice._filelock:
                    if len(newlist) > 0:
                        self._parentdevice._dict_events[self] = newlist
                    else:
                        del self._parentdevice._dict_events[self]

    def wait(self, edge=BOTH, exitevent=None, okvalue=None, timeout=0) -> int:
        """
        Wartet auf Wertaenderung eines IOs.

        Die Wertaenderung wird immer uerberprueft, wenn fuer Devices
        mit aktiviertem autorefresh neue Daten gelesen wurden.

        Bei Wertaenderung, wird das Warten mit 0 als Rueckgabewert beendet.

        HINWEIS: Wenn <class 'ProcimgWriter'> keine neuen Daten liefert, wird
        bis in die Ewigkeit gewartet (nicht bei Angabe von "timeout").

        Wenn edge mit RISING oder FALLING angegeben wird, muss diese Flanke
        ausgeloest werden. Sollte der Wert 1 sein beim Eintritt mit Flanke
        RISING, wird das Warten erst bei Aenderung von 0 auf 1 beendet.

        Als exitevent kann ein <class 'threading.Event'>-Objekt uebergeben
        werden, welches das Warten bei is_set() sofort mit 1 als Rueckgabewert
        beendet.

        Wenn der Wert okvalue an dem IO fuer das Warten anliegt, wird
        das Warten sofort mit -1 als Rueckgabewert beendet.

        Der Timeoutwert bricht beim Erreichen das Warten sofort mit
        Wert 2 Rueckgabewert ab. (Das Timeout wird ueber die Zykluszeit
        der autorefresh Funktion berechnet, entspricht also nicht exakt den
        angegeben Millisekunden! Es wird immer nach oben gerundet!)

        :param edge: Flanke RISING, FALLING, BOTH die eintreten muss
        :param exitevent: <class 'thrading.Event'> fuer vorzeitiges Beenden
        :param okvalue: IO-Wert, bei dem das Warten sofort beendet wird
        :param timeout: Zeit in ms nach der abgebrochen wird
        :return: <class 'int'> erfolgreich Werte <= 0

        - Erfolgreich gewartet
            - Wert 0: IO hat den Wert gewechselt
            - Wert -1: okvalue stimmte mit IO ueberein
        - Fehlerhaft gewartet
            - Wert 1: exitevent wurde gesetzt
            - Wert 2: timeout abgelaufen
            - Wert 100: Devicelist.exit() wurde aufgerufen

        """
        # Prüfen ob Device in autorefresh ist
        if not self._parentdevice._selfupdate:
            raise RuntimeError(
                "autorefresh is not activated for device '{0}|{1}' - there "
                "will never be new data".format(
                    self._parentdevice._position, self._parentdevice._name
                )
            )
        if not (RISING <= edge <= BOTH):
            raise ValueError(
                "parameter 'edge' must be revpimodio2.RISING, "
                "revpimodio2.FALLING or revpimodio2.BOTH"
            )
        if not (exitevent is None or type(exitevent) == Event):
            raise TypeError(
                "parameter 'exitevent' must be <class 'threading.Event'>"
            )
        if type(timeout) != int or timeout < 0:
            raise ValueError(
                "parameter 'timeout' must be <class 'int'> and greater than 0"
            )
        if edge != BOTH and not self._bitshift:
            raise ValueError(
                "parameter 'edge' can be used with bit Inputs only"
            )

        # Abbruchwert prüfen
        if okvalue == self.value:
            return -1

        # WaitExit Event säubern
        self._parentdevice._modio._waitexit.clear()

        val_start = self.value
        timeout = timeout / 1000
        bool_timecount = timeout > 0
        if exitevent is None:
            exitevent = Event()

        flt_timecount = 0 if bool_timecount else -1
        while not self._parentdevice._modio._waitexit.is_set() \
                and not exitevent.is_set() \
                and flt_timecount < timeout:

            if self._parentdevice._modio._imgwriter.newdata.wait(2.5):
                self._parentdevice._modio._imgwriter.newdata.clear()

                if val_start != self.value:
                    if edge == BOTH \
                            or edge == RISING and not val_start \
                            or edge == FALLING and val_start:
                        return 0
                    else:
                        val_start = not val_start
                if bool_timecount:
                    flt_timecount += \
                        self._parentdevice._modio._imgwriter._refresh
            elif bool_timecount:
                flt_timecount += 2.5

        # Abbruchevent wurde gesetzt
        if exitevent.is_set():
            return 1

        # RevPiModIO mainloop wurde verlassen
        if self._parentdevice._modio._waitexit.is_set():
            return 100

        # Timeout abgelaufen
        return 2

    address = property(_get_address)
    byteorder = property(_get_byteorder)
    defaultvalue = property(get_defaultvalue)
    export = property(_get_export, _set_export)
    length = property(__len__)
    name = property(__str__)
    type = property(_get_iotype)
    value = property(get_value, set_value)


class IntIO(IOBase):
    """
    Klasse fuer den Zugriff auf die Daten mit Konvertierung in int.

    Diese Klasse erweitert die Funktion von <class 'IOBase'> um Funktionen,
    ueber die mit <class 'int'> Werten gearbeitet werden kann. Fuer die
    Umwandlung koennen 'Byteorder' (Default 'little') und 'signed' (Default
    False) als Parameter gesetzt werden.

    :ref: :class:`IOBase`
    """

    __slots__ = ()

    def __int__(self):
        """
        Gibt IO-Wert zurueck mit Beachtung byteorder/signed.

        :return: IO-Wert als <class 'int'>
        """
        return int.from_bytes(
            self._parentdevice._ba_devdata[self._slc_address],
            byteorder=self._byteorder,
            signed=self._signed
        )

    def __call__(self, value=None):
        if value is None:
            # Inline get_intvalue()
            return int.from_bytes(
                self._parentdevice._ba_devdata[self._slc_address],
                byteorder=self._byteorder,
                signed=self._signed
            )
        else:
            # Inline from set_intvalue()
            if type(value) == int:
                self.set_value(value.to_bytes(
                    self._length,
                    byteorder=self._byteorder,
                    signed=self._signed
                ))
            else:
                raise TypeError(
                    "'{0}' need a <class 'int'> value, but {1} was given"
                    "".format(self._name, type(value))
                )

    def _get_signed(self) -> bool:
        """
        Ruft ab, ob der Wert Vorzeichenbehaftet behandelt werden soll.

        :return: True, wenn Vorzeichenbehaftet
        """
        return self._signed

    def _set_byteorder(self, value: str) -> None:
        """
        Setzt Byteorder fuer <class 'int'> Umwandlung.

        :param value: <class 'str'> 'little' or 'big'
        """
        if not (value == "little" or value == "big"):
            raise ValueError("byteorder must be 'little' or 'big'")
        if self._byteorder != value:
            self._byteorder = value
            self._defaultvalue = self._defaultvalue[::-1]

    def _set_signed(self, value: bool) -> None:
        """
        Left fest, ob der Wert Vorzeichenbehaftet behandelt werden soll.

        :param value: True, wenn mit Vorzeichen behandel
        """
        if type(value) != bool:
            raise TypeError("signed must be <class 'bool'> True or False")
        self._signed = value

    def get_intdefaultvalue(self) -> int:
        """
        Gibt die Defaultvalue als <class 'int'> zurueck.

        :return: <class 'int'> Defaultvalue
        """
        return int.from_bytes(
            self._defaultvalue, byteorder=self._byteorder, signed=self._signed
        )

    def get_intvalue(self) -> int:
        """
        Gibt IO-Wert zurueck mit Beachtung byteorder/signed.

        :return: IO-Wert als <class 'int'>
        """
        return int.from_bytes(
            self._parentdevice._ba_devdata[self._slc_address],
            byteorder=self._byteorder,
            signed=self._signed
        )

    def set_intvalue(self, value: int) -> None:
        """
        Setzt IO mit Beachtung byteorder/signed.

        :param value: <class 'int'> Wert
        """
        if type(value) == int:
            self.set_value(value.to_bytes(
                self._length,
                byteorder=self._byteorder,
                signed=self._signed
            ))
        else:
            raise TypeError(
                "'{0}' need a <class 'int'> value, but {1} was given"
                "".format(self._name, type(value))
            )

    byteorder = property(IOBase._get_byteorder, _set_byteorder)
    defaultvalue = property(get_intdefaultvalue)
    signed = property(_get_signed, _set_signed)
    value = property(get_intvalue, set_intvalue)


class IntIOCounter(IntIO):
    """Erweitert die IntIO-Klasse um die .reset() Funktion fuer Counter."""

    __slots__ = ("__ioctl_arg",)

    def __init__(
            self, counter_id,
            parentdevice, valuelist, iotype, byteorder, signed):
        """
        Instantiierung der IntIOCounter-Klasse.

        :param counter_id: ID fuer den Counter, zu dem der IO gehoert (0-15)
        :ref: :func:`IOBase.__init__(...)`
        """
        if not isinstance(counter_id, int):
            raise TypeError("counter_id must be <class 'int'>")
        if not 0 <= counter_id <= 15:
            raise ValueError("counter_id must be 0 - 15")

        # Deviceposition + leer + Counter_ID
        # ID-Bits: 7|6|5|4|3|2|1|0|15|14|13|12|11|10|9|8
        self.__ioctl_arg = \
            parentdevice._position.to_bytes(1, "little") + b'\x00' + \
            (1 << counter_id).to_bytes(2, "little")

        """
        IOCTL fuellt dieses struct, welches durch padding im Speicher nach
        uint8_t ein byte frei hat. Es muessen also 4 Byte uebergeben werden
        wobei das Bitfield die Byteorder little hat!!!

        typedef struct SDIOResetCounterStr
        {
            uint8_t     i8uAddress;   // Address of module
            uint16_t    i16uBitfield; // bitfield, if bit n is 1, reset
        } SDIOResetCounter;
        """

        # Basisklasse laden
        super().__init__(parentdevice, valuelist, iotype, byteorder, signed)

    def reset(self) -> None:
        """Setzt den Counter des Inputs zurueck."""
        if self._parentdevice._modio._monitoring:
            raise RuntimeError(
                "can not reset counter, while system is in monitoring mode"
            )
        if self._parentdevice._modio._simulator:
            raise RuntimeError(
                "can not reset counter, while system is in simulator mode"
            )

        if self._parentdevice._modio._run_on_pi:
            # IOCTL auf dem RevPi
            with self._parentdevice._modio._myfh_lck:
                try:
                    # Counter reset durchführen (Funktion K+20)
                    ioctl(
                        self._parentdevice._modio._myfh,
                        19220, self.__ioctl_arg
                    )
                except Exception as e:
                    self._parentdevice._modio._gotioerror("iorst", e)

        elif hasattr(self._parentdevice._modio._myfh, "ioctl"):
            # IOCTL über Netzwerk
            with self._parentdevice._modio._myfh_lck:
                try:
                    self._parentdevice._modio._myfh.ioctl(
                        19220, self.__ioctl_arg
                    )
                except Exception as e:
                    self._parentdevice._modio._gotioerror("net_iorst", e)

        else:
            # IOCTL in Datei simulieren
            try:
                # Set value durchführen (Funktion K+20)
                self._parentdevice._modio._simulate_ioctl(
                    19220, self.__ioctl_arg
                )
            except Exception as e:
                self._parentdevice._modio._gotioerror("file_iorst", e)


class IntIOReplaceable(IntIO):
    """Erweitert die IntIO-Klasse um die .replace_io Funktion."""

    __slots__ = ()

    def replace_io(self, name: str, frm: str, **kwargs) -> None:
        """
        Ersetzt bestehenden IO mit Neuem.

        Wenn die kwargs fuer byteorder und defaultvalue nicht angegeben werden,
        uebernimmt das System die Daten aus dem ersetzten IO.

        Es darf nur ein einzelnes Formatzeichen 'frm' uebergeben werden. Daraus
        wird dann die benoetigte Laenge an Bytes berechnet und der Datentyp
        festgelegt. Moeglich sind:
        - Bits / Bytes: ?, c, s
        - Integer     : bB, hH, iI, lL, qQ
        - Float       : e, f, d

        Eine Ausnahme ist die Formatierung 's'. Hier koennen mehrere Bytes
        zu einem langen IO zusammengefasst werden. Die Formatierung muss
        '8s' fuer z.B. 8 Bytes sein - NICHT 'ssssssss'!

        Wenn durch die Formatierung mehr Bytes benoetigt werden, als
        der urspruenglige IO hat, werden die nachfolgenden IOs ebenfalls
        verwendet und entfernt.

        :param name: Name des neuen Inputs
        :param frm: struct formatierung (1 Zeichen) oder 'ANZAHLs' z.B. '8s'
        :param kwargs: Weitere Parameter

        - bmk: interne Bezeichnung fuer IO
        - bit: Registriert IO als <class 'bool'> am angegebenen Bit im Byte
        - byteorder: Byteorder fuer den IO, Standardwert=little
        - defaultvalue: Standardwert fuer IO
        - event: Funktion fuer Eventhandling registrieren
        - delay: Verzoegerung in ms zum Ausloesen wenn Wert gleich bleibt
        - edge: Event ausfuehren bei RISING, FALLING or BOTH Wertaenderung
        - as_thread: Fuehrt die event-Funktion als RevPiCallback-Thread aus
        - prefire: Ausloesen mit aktuellem Wert, wenn mainloop startet

        `<https://docs.python.org/3/library/struct.html#format-characters>`_
        """
        # StructIO erzeugen
        io_new = StructIO(
            self,
            name,
            frm,
            **kwargs
        )

        # StructIO in IO-Liste einfügen
        self._parentdevice._modio.io._private_register_new_io_object(io_new)

        # Optional Event eintragen
        reg_event = kwargs.get("event", None)
        if reg_event is not None:
            io_new.reg_event(
                reg_event,
                kwargs.get("delay", 0),
                kwargs.get("edge", BOTH),
                kwargs.get("as_thread", False)
            )


class StructIO(IOBase):
    """
    Klasse fuer den Zugriff auf Daten ueber ein definierten struct.

    Sie stellt ueber struct die Werte in der gewuenschten Formatierung
    bereit. Der struct-Formatwert wird bei der Instantiierung festgelegt.
    """

    __slots__ = "__frm", "_parentio_address", "_parentio_defaultvalue", \
                "_parentio_length", "_parentio_name"

    def __init__(self, parentio, name: str, frm: str, **kwargs):
        """
        Erstellt einen IO mit struct-Formatierung.

        :param parentio: ParentIO Objekt, welches ersetzt wird
        :param name: Name des neuen IO
        :param frm: struct formatierung (1 Zeichen) oder 'ANZAHLs' z.B. '8s'
        :param kwargs: Weitere Parameter:
            - bmk: Bezeichnung fuer IO
            - bit: Registriert IO als <class 'bool'> am angegebenen Bit im Byte
            - byteorder: Byteorder fuer IO, Standardwert vom ersetzten IO
            - defaultvalue: Standardwert fuer IO, Standard vom ersetzten IO
        """
        # Structformatierung prüfen
        regex = rematch("^([0-9]*s|[cbB?hHiIlLqQefd])$", frm)

        if regex is not None:
            # Byteorder prüfen und übernehmen
            byteorder = kwargs.get("byteorder", parentio._byteorder)
            if not (byteorder == "little" or byteorder == "big"):
                raise ValueError("byteorder must be 'little' or 'big'")
            bofrm = "<" if byteorder == "little" else ">"

            # Namen des parent fuer export merken
            self._parentio_name = parentio._name

            if frm == "?":
                bitaddress = kwargs.get("bit", 0)
                max_bits = parentio._length * 8
                if not (0 <= bitaddress < max_bits):
                    raise ValueError(
                        "bitaddress must be a value between 0 and {0}"
                        "".format(max_bits - 1)
                    )
                bitlength = 1

                # Bitweise Ersetzung erfordert diese Informationen zusätzlich
                if parentio._byteorder == byteorder:
                    self._parentio_defaultvalue = parentio._defaultvalue
                else:
                    self._parentio_defaultvalue = parentio._defaultvalue[::-1]
                self._parentio_address = parentio.address
                self._parentio_length = parentio._length
            else:
                bitaddress = ""
                bitlength = struct.calcsize(bofrm + frm) * 8
                self._parentio_address = None
                self._parentio_defaultvalue = None
                self._parentio_length = None

            # [name,default,anzbits,adressbyte,export,adressid,bmk,bitaddress]
            valuelist = [
                name,
                # Darf nur bei StructIO None sein, wird nur dann berechnet
                kwargs.get("defaultvalue", None),
                bitlength,
                parentio._slc_address.start,
                False,
                str(parentio._slc_address.start).rjust(4, "0"),
                kwargs.get("bmk", ""),
                bitaddress
            ]
        else:
            raise ValueError(
                "parameter frm has to be a single sign from [cbB?hHiIlLqQefd] "
                "or 'COUNTs' e.g. '8s'"
            )

        # Basisklasse instantiieren
        super().__init__(
            parentio._parentdevice,
            valuelist,
            parentio._iotype,
            byteorder,
            frm == frm.lower()
        )
        self.__frm = bofrm + frm
        if "export" in kwargs:
            # Use export property to remember given value for export
            self.export = kwargs["export"]
        else:
            # User could change parent IO settings before replace to force
            # export, so use parent settings for the new IO
            self._export = parentio._export

        # Platz für neuen IO prüfen
        if not (self._slc_address.start >=
                parentio._parentdevice._dict_slc[parentio._iotype].start and
                self._slc_address.stop <=
                parentio._parentdevice._dict_slc[parentio._iotype].stop):
            raise BufferError(
                "registered value does not fit process image scope"
            )

    def __call__(self, value=None):
        if value is None:
            # Inline get_structdefaultvalue()
            if self._bitshift:
                return self.get_value()
            else:
                return struct.unpack(self.__frm, self.get_value())[0]
        else:
            # Inline set_structvalue()
            if self._bitshift:
                self.set_value(value)
            else:
                self.set_value(struct.pack(self.__frm, value))

    def _get_frm(self) -> str:
        """
        Ruft die struct Formatierung ab.

        :return: struct Formatierung
        """
        return self.__frm[1:]

    def _get_signed(self) -> bool:
        """
        Ruft ab, ob der Wert Vorzeichenbehaftet behandelt werden soll.

        :return: True, wenn Vorzeichenbehaftet
        """
        return self._signed

    def get_structdefaultvalue(self):
        """
        Gibt die Defaultvalue mit struct Formatierung zurueck.

        :return: Defaultvalue vom Typ der struct-Formatierung
        """
        if self._bitshift:
            return self._defaultvalue
        else:
            return struct.unpack(self.__frm, self._defaultvalue)[0]

    def get_structvalue(self):
        """
        Gibt den Wert mit struct Formatierung zurueck.

        :return: Wert vom Typ der struct-Formatierung
        """
        if self._bitshift:
            return self.get_value()
        else:
            return struct.unpack(self.__frm, self.get_value())[0]

    def set_structvalue(self, value):
        """
        Setzt den Wert mit struct Formatierung.

        :param value: Wert vom Typ der struct-Formatierung
        """
        if self._bitshift:
            self.set_value(value)
        else:
            self.set_value(struct.pack(self.__frm, value))

    defaultvalue = property(get_structdefaultvalue)
    frm = property(_get_frm)
    signed = property(_get_signed)
    value = property(get_structvalue, set_structvalue)


class MemIO(IOBase):
    """
    Erstellt einen IO für die Memory Werte in piCtory.

    Dieser Typ ist nur für lesenden Zugriff vorgesehen und kann verschiedene
    Datentypen über .value zurückgeben. Damit hat man nun auch Zugriff
    auf Strings, welche in piCtory vergeben werden.
    """

    def get_variantvalue(self):
        val = bytes(self._defaultvalue)

        if self._bitlength > 64:
            # STRING
            try:
                val = val.strip(b'\x00').decode()
            except Exception:
                pass
            return val

        else:
            # INT
            return int.from_bytes(val, self._byteorder, signed=self._signed)

    defaultvalue = property(get_variantvalue)
    value = property(get_variantvalue)

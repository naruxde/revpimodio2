# -*- coding: utf-8 -*-
#
# python3-RevPiModIO
#
# Webpage: https://revpimodio.org/
# (c) Sven Sager, License: LGPLv3
#
"""RevPiModIO Modul fuer die Verwaltung der IOs."""
import struct
from threading import Event
from revpimodio2 import RISING, FALLING, BOTH, consttostr


class Type(object):

    """IO Typen."""

    INP = 300
    OUT = 301
    MEM = 302


class IOList(object):

    """Basisklasse fuer direkten Zugriff auf IO Objekte."""

    def __init__(self):
        """Init IOList class."""
        self.__dict_iobyte = {k: [] for k in range(4096)}
        self.__dict_iorefname = {}

    def __contains__(self, key):
        """Prueft ob IO existiert.
        @param key IO-Name <class 'str'> oder Byte <class 'int'>
        @return True, wenn IO vorhanden / Byte belegt"""
        if type(key) == int:
            return key in self.__dict_iobyte \
                and len(self.__dict_iobyte[key]) > 0
        else:
            return hasattr(self, key) and type(getattr(self, key)) != DeadIO

    def __delattr__(self, key):
        """Entfernt angegebenen IO.
        @param key IO zum entfernen"""
        io_del = object.__getattribute__(self, key)

        # Alte Events vom Device löschen
        io_del.unreg_event()

        # IO aus Byteliste und Attributen entfernen
        if io_del._bitaddress < 0:
            self.__dict_iobyte[io_del.address].remove(io_del)
        else:
            self.__dict_iobyte[io_del.address][io_del._bitaddress] = None
            if self.__dict_iobyte[io_del.address] == \
                    [None, None, None, None, None, None, None, None]:
                self.__dict_iobyte[io_del.address] = []

        object.__delattr__(self, key)

    def __getattr__(self, key):
        """Verwaltet geloeschte IOs (Attribute, die nicht existieren).
        @param key Name oder Byte eines alten IOs
        @return Alten IO, wenn in Ref-Listen"""
        if key in self.__dict_iorefname:
            return self.__dict_iorefname[key]
        else:
            raise AttributeError("can not find io '{}'".format(key))

    def __getitem__(self, key):
        """Ruft angegebenen IO ab.

        Wenn der Key <class 'str'> ist, wird ein einzelner IO geliefert. Wird
        der Key als <class 'int'> uebergeben, wird eine <class 'list'>
        geliefert mit 0, 1 oder 8 Eintraegen.
        Wird als Key <class 'slice'> gegeben, werden die Listen in einer Liste
        zurueckgegeben.

        @param key IO Name als <class 'str> oder Byte als <class 'int'>.
        @return IO Objekt oder Liste der IOs

        """
        if type(key) == int:
            if key not in self.__dict_iobyte:
                raise KeyError("byte '{}' does not exist".format(key))
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
        """Gibt Iterator aller IOs zurueck.
        @return Iterator aller IOs"""
        for int_io in sorted(self.__dict_iobyte):
            for io in self.__dict_iobyte[int_io]:
                if io is not None:
                    yield io

    def __len__(self):
        """Gibt die Anzahl aller IOs zurueck.
        @return Anzahl aller IOs"""
        int_ios = 0
        for int_io in self.__dict_iobyte:
            for io in self.__dict_iobyte[int_io]:
                if io is not None:
                    int_ios += 1
        return int_ios

    def __setattr__(self, key, value):
        """Verbietet aus Leistungsguenden das direkte Setzen von Attributen."""
        if key in [
                "_IOList__dict_iobyte",
                "_IOList__dict_iorefname"
                ]:
            object.__setattr__(self, key, value)
        else:
            raise TypeError(
                "direct assignment is not supported - use .value Attribute"
            )

    def __private_replace_oldio_with_newio(self, io):
        """Ersetzt bestehende IOs durch den neu Registrierten.
        @param io Neuer IO der eingefuegt werden soll"""

        # Scanbereich festlegen
        if io._bitaddress < 0:
            scan_start = io.address
            scan_stop = scan_start + (1 if io._length == 0 else io._length)
        else:
            scan_start = io._parentio_address
            scan_stop = scan_start + io._parentio_length

        # Defaultvalue über mehrere Bytes sammeln
        calc_defaultvalue = b''

        for i in range(scan_start, scan_stop):
            for oldio in self.__dict_iobyte[i]:

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
                        # Bereits überschriebene bytes sind ungültig
                        raise MemoryError(
                            "new io '{}' overlaps memory of '{}'".format(
                                io._name, oldio._name
                            )
                        )
                elif oldio is not None:
                    # IOs im Speicherbereich des neuen IO merken
                    if io._bitaddress >= 0:
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
            if io._bitaddress < 0:
                io._defaultvalue = calc_defaultvalue
            else:
                io._defaultvalue = bool(io._parentio_defaultvalue[
                    io._parentio_address - io.address
                ] & (1 << io._bitaddress))

    def _private_register_new_io_object(self, new_io):
        """Registriert neues IO Objekt unabhaenging von __setattr__.
        @param new_io Neues IO Objekt"""
        if issubclass(type(new_io), IOBase):
            if hasattr(self, new_io._name):
                raise AttributeError(
                    "attribute {} already exists - can not set io".format(
                        new_io._name
                    )
                )

            if type(new_io) is StructIO:
                self.__private_replace_oldio_with_newio(new_io)

            object.__setattr__(self, new_io._name, new_io)

            # Bytedict für Adresszugriff anpassen
            if new_io._bitaddress < 0:
                self.__dict_iobyte[new_io.address].append(new_io)
            else:
                if len(self.__dict_iobyte[new_io.address]) != 8:
                    # "schnell" 8 Einträge erstellen da es BIT IOs sind
                    self.__dict_iobyte[new_io.address] += [
                        None, None, None, None, None, None, None, None
                    ]
                self.__dict_iobyte[new_io.address][new_io._bitaddress] = new_io
        else:
            raise AttributeError("io must be <class 'IOBase'> or sub class")


class DeadIO(object):

    """Klasse, mit der ersetzte IOs verwaltet werden."""

    def __init__(self, deadio):
        """Instantiierung der DeadIO-Klasse.
        @param deadio IO, der ersetzt wurde"""
        self.__deadio = deadio

    def replace_io(self, name, frm, **kwargs):
        """Stellt Funktion fuer weiter Bit-Ersetzungen bereit.
        @see #IOBase.replace_io replace_io(...)"""
        self.__deadio.replace_io(name, frm, **kwargs)


class IOBase(object):

    """Basisklasse fuer alle IO-Objekte.

    Die Basisfunktionalitaet ermoeglicht das Lesen und Schreiben der Werte
    als <class bytes'> oder <class 'bool'>. Dies entscheidet sich bei der
    Instantiierung.
    Wenn eine Bittadresse angegeben wird, werden <class 'bool'>-Werte erwartet
    und zurueckgegeben, ansonsten <class bytes'>.

    Diese Klasse dient als Basis fuer andere IO-Klassen mit denen die Werte
    auch als <class 'int'> verwendet werden koennen.

    """

    def __init__(self, parentdevice, valuelist, iotype, byteorder, signed):
        """Instantiierung der IOBase-Klasse.

        @param parentdevice Parentdevice auf dem der IO liegt
        @param valuelist Datenliste fuer Instantiierung
        @param iotype <class 'Type'> Wert
        @param byteorder Byteorder 'little'/'big' fuer <class 'int'> Berechnung
        @param sigend Intberechnung mit Vorzeichen durchfuehren

        """
        self._parentdevice = parentdevice

        # Bitadressen auf Bytes aufbrechen und umrechnen
        self._bitaddress = -1 if valuelist[7] == "" else int(valuelist[7]) % 8

        # Längenberechnung
        self._bitlength = int(valuelist[2])
        self._length = 1 if self._bitaddress == 0 else int(self._bitlength / 8)

        self._byteorder = byteorder
        self._iotype = iotype
        self._name = valuelist[0]
        self._signed = signed
        self.bmk = valuelist[6]

        int_startaddress = int(valuelist[3])
        if self._bitaddress == -1:
            self._slc_address = slice(
                int_startaddress, int_startaddress + self._length
            )
            # Defaultvalue aus Zahl in Bytes umrechnen
            if str(valuelist[1]).isdigit():
                self._defaultvalue = int(valuelist[1]).to_bytes(
                    self._length, byteorder=self._byteorder
                )
            elif valuelist[1] is None and type(self) == StructIO:
                self._defaultvalue = None
            elif type(valuelist[1]) == bytes:
                # Defaultvalue direkt von bytes übernehmen
                if len(valuelist[1]) == self._length:
                    self._defaultvalue = valuelist[1]
                else:
                    raise ValueError(
                        "given bytes for default value must have a length "
                        "of {} but {} was given"
                        "".format(self._length, len(valuelist[1]))
                    )
            else:
                self._defaultvalue = bytes(self._length)

        else:
            # Höhere Bits als 7 auf nächste Bytes umbrechen
            int_startaddress += int((int(valuelist[7]) % 16) / 8)
            self._slc_address = slice(
                int_startaddress, int_startaddress + 1
            )
            self._defaultvalue = None if valuelist[1] is None \
                else bool(int(valuelist[1]))

    def __bool__(self):
        """<class 'bool'>-Wert der Klasse.
        @return <class 'bool'> Nur False wenn False oder 0 sonst True"""
        if self._bitaddress >= 0:
            int_byte = int.from_bytes(
                self._parentdevice._ba_devdata[self._slc_address],
                byteorder=self._byteorder
            )
            return bool(int_byte & 1 << self._bitaddress)
        else:
            return bool(self._parentdevice._ba_devdata[self._slc_address])

    def __len__(self):
        """Gibt die Bytelaenge des IO zurueck.
        @return Bytelaenge des IO - 0 bei BITs"""
        return 0 if self._bitaddress > 0 else self._length

    def __str__(self):
        """<class 'str'>-Wert der Klasse.
        @return Namen des IOs"""
        return self._name

    def _get_address(self):
        """Gibt die absolute Byteadresse im Prozessabbild zurueck.
        @return Absolute Byteadresse"""
        return self._parentdevice._offset + self._slc_address.start

    def _get_byteorder(self):
        """Gibt konfigurierte Byteorder zurueck.
        @return <class 'str'> Byteorder"""
        return self._byteorder

    def _get_iotype(self):
        """Gibt io.Type zurueck.
        @return <class 'int'> io.Type"""
        return self._iotype

    def get_defaultvalue(self):
        """Gibt die Defaultvalue von piCtory zurueck.
        @return Defaultvalue als <class 'byte'> oder <class 'bool'>"""
        return self._defaultvalue

    def get_value(self):
        """Gibt den Wert des IOs zurueck.
        @return IO-Wert als <class 'bytes'> oder <class 'bool'>"""
        if self._bitaddress >= 0:
            int_byte = int.from_bytes(
                self._parentdevice._ba_devdata[self._slc_address],
                byteorder=self._byteorder
            )
            return bool(int_byte & 1 << self._bitaddress)
        else:
            return bytes(self._parentdevice._ba_devdata[self._slc_address])

    def reg_event(self, func, delay=0, edge=BOTH, as_thread=False):
        """Registriert fuer IO ein Event bei der Eventueberwachung.

        Die uebergebene Funktion wird ausgefuehrt, wenn sich der IO Wert
        aendert. Mit Angabe von optionalen Parametern kann das
        Ausloeseverhalten gesteuert werden.

        HINWEIS: Die delay-Zeit muss in die .cycletime passen, ist dies nicht
        der Fall, wird IMMER aufgerundet!

        @param func Funktion die bei Aenderung aufgerufen werden soll
        @param delay Verzoegerung in ms zum Ausloesen wenn Wert gleich bleibt
        @param edge Ausfuehren bei RISING, FALLING or BOTH Wertaenderung
        @param as_thread Bei True, Funktion als EventCallback-Thread ausfuehren

        """
        # Prüfen ob Funktion callable ist
        if not callable(func):
            raise AttributeError(
                "registered function '{}' is not callable".format(func)
            )
        if type(delay) != int or delay < 0:
            raise AttributeError(
                "'delay' must be <class 'int'> and greater or equal 0"
            )
        if edge != BOTH and self._bitaddress < 0:
            raise AttributeError(
                "parameter 'edge' can be used with bit io objects only"
            )

        if self not in self._parentdevice._dict_events:
            self._parentdevice._dict_events[self] = \
                [(func, edge, as_thread, delay, True)]
        else:
            # Prüfen ob Funktion schon registriert ist
            for regfunc in self._parentdevice._dict_events[self]:
                if regfunc[0] != func:
                    # Nächsten Eintrag testen
                    continue

                if edge == BOTH or regfunc[1] == BOTH:
                    if self._bitaddress < 0:
                        raise AttributeError(
                            "io '{}' with function '{}' already in list."
                            "".format(self._name, func)
                        )
                    else:
                        raise AttributeError(
                            "io '{}' with function '{}' already in list with "
                            "edge '{}' - edge '{}' not allowed anymore".format(
                                self._name, func,
                                consttostr(regfunc[1]), consttostr(edge)
                            )
                        )
                elif regfunc[1] == edge:
                    raise AttributeError(
                        "io '{}' with function '{}' for given edge '{}' "
                        "already in list".format(
                            self._name, func, consttostr(edge)
                        )
                    )

            # Eventfunktion einfügen
            self._parentdevice._dict_events[self].append(
                (func, edge, as_thread, delay, True)
            )

    def reg_timerevent(self, func, delay, edge=BOTH, as_thread=False):
        """Registriert fuer IO einen Timer, welcher nach delay func ausfuehrt.

        Der Timer wird gestartet, wenn sich der IO Wert aendert und fuehrt die
        uebergebene Funktion aus - auch wenn sich der IO Wert in der
        zwischenzeit geaendert hat. Sollte der Timer nicht abelaufen sein und
        die Bedingugn erneut zutreffen, wird der Timer NICHT auf den delay Wert
        zurueckgesetzt oder ein zweites Mal gestartet. Fuer dieses Verhalten
        kann .reg_event(..., delay=wert) verwendet werden.

        HINWEIS: Die delay-Zeit muss in die .cycletime passen, ist dies nicht
        der Fall, wird IMMER aufgerundet!

        @param func Funktion die bei Aenderung aufgerufen werden soll
        @param delay Verzoegerung in ms zum Ausloesen - auch bei Wertaenderung
        @param edge Ausfuehren bei RISING, FALLING or BOTH Wertaenderung
        @param as_thread Bei True, Funktion als EventCallback-Thread ausfuehren

        """
        # Prüfen ob Funktion callable ist
        if not callable(func):
            raise AttributeError(
                "registered function '{}' is not callable".format(func)
            )
        if type(delay) != int or delay < 0:
            raise AttributeError(
                "'delay' must be <class 'int'> and greater or equal 0"
            )
        if edge != BOTH and self._bitaddress < 0:
            raise AttributeError(
                "parameter 'edge' can be used with bit io objects only"
            )

        if self not in self._parentdevice._dict_events:
            self._parentdevice._dict_events[self] = \
                [(func, edge, as_thread, delay, False)]
        else:
            # Prüfen ob Funktion schon registriert ist
            for regfunc in self._parentdevice._dict_events[self]:
                if regfunc[0] != func:
                    # Nächsten Eintrag testen
                    continue

                if edge == BOTH or regfunc[1] == BOTH:
                    if self._bitaddress < 0:
                        raise AttributeError(
                            "io '{}' with function '{}' already in list."
                            "".format(self._name, func)
                        )
                    else:
                        raise AttributeError(
                            "io '{}' with function '{}' already in list with "
                            "edge '{}' - edge '{}' not allowed anymore".format(
                                self._name, func,
                                consttostr(regfunc[1]), consttostr(edge)
                            )
                        )
                elif regfunc[1] == edge:
                    raise AttributeError(
                        "io '{}' with function '{}' for given edge '{}' "
                        "already in list".format(
                            self._name, func, consttostr(edge)
                        )
                    )

            # Eventfunktion einfügen
            self._parentdevice._dict_events[self].append(
                (func, edge, as_thread, delay, False)
            )

    def replace_io(self, name, frm, **kwargs):
        """Ersetzt bestehenden IO mit Neuem.

        Wenn die kwargs fuer byteorder und defaultvalue nicht angegeben werden,
        uebernimmt das System die Daten aus dem ersetzten IO.

        @param name Name des neuen Inputs
        @param frm struct Formatierung (1 Zeichen)
        @param kwargs Weitere Parameter:
            - bmk: interne Bezeichnung fuer IO
            - bit: Registriert IO als <class 'bool'> am angegebenen Bit im Byte
            - byteorder: Byteorder fuer den IO, Standardwert=little
            - defaultvalue: Standardwert fuer IO
            - event: Funktion fuer Eventhandling registrieren
            - delay: Verzoegerung in ms zum Ausloesen wenn Wert gleich bleibt
            - edge: Event ausfuehren bei RISING, FALLING or BOTH Wertaenderung
            - as_thread: Fuehrt die event-Funktion als RevPiCallback-Thread aus
        @see <a target="_blank"
        href="https://docs.python.org/3/library/struct.html#format-characters"
        >Python3 struct</a>

        """
        if not issubclass(type(self._parentdevice), Gateway):
            raise RuntimeError(
                "this function can be used for ios on gatway or virtual "
                "devices only"
            )
        if type(self) == StructIO:
            raise RuntimeError(
                "this io is already a replaced one"
            )

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

    def set_value(self, value):
        """Setzt den Wert des IOs.
        @param value IO-Wert als <class bytes'> oder <class 'bool'>"""
        if self._iotype == Type.OUT:
            if self._bitaddress >= 0:
                # Versuchen egal welchen Typ in Bool zu konvertieren
                value = bool(value)

                # ganzes Byte laden
                byte_buff = self._parentdevice._ba_devdata[self._slc_address]

                # Bytes in integer umwandeln
                int_len = len(byte_buff)
                int_byte = int.from_bytes(byte_buff, byteorder=self._byteorder)
                int_bit = 1 << self._bitaddress

                # Aktuellen Wert vergleichen und ggf. setzen
                if not bool(int_byte & int_bit) == value:
                    if value:
                        int_byte += int_bit
                    else:
                        int_byte -= int_bit

                    # Zurückschreiben wenn verändert
                    self._parentdevice._ba_devdata[self._slc_address] = \
                        int_byte.to_bytes(int_len, byteorder=self._byteorder)

            else:
                if type(value) == bytes:
                    if self._length == len(value):
                        self._parentdevice._ba_devdata[self._slc_address] = \
                            value
                    else:
                        raise ValueError(
                            "'{}' requires a <class 'bytes'> object of length "
                            "{}, but {} was given".format(
                                self._name, self._length, len(value)
                            )
                        )
                else:
                    raise ValueError(
                        "'{}' requires a <class 'bytes'> object, not {}"
                        "".format(self._name, type(value))
                    )

        elif self._iotype == Type.INP:
            if self._parentdevice._modio._simulator:
                raise AttributeError(
                    "can not write to output '{}' in simulator mode"
                    "".format(self._name)
                )
            else:
                raise AttributeError(
                    "can not write to input '{}'".format(self._name)
                )
        elif self._iotype == Type.MEM:
            raise AttributeError(
                "can not write to memory '{}'".format(self._name)
            )

    def unreg_event(self, func=None, edge=None):
        """Entfernt ein Event aus der Eventueberwachung.

        @param func Nur Events mit angegebener Funktion
        @param edge Nur Events mit angegebener Funktion und angegebener Edge

        """
        if self in self._parentdevice._dict_events:
            if func is None:
                del self._parentdevice._dict_events[self]
            else:
                newlist = []
                for regfunc in self._parentdevice._dict_events[self]:
                    if regfunc[0] != func or edge is not None \
                            and regfunc[1] != edge:

                        newlist.append(regfunc)

                # Wenn Funktionen übrig bleiben, diese übernehmen
                if len(newlist) > 0:
                    self._parentdevice._dict_events[self] = newlist
                else:
                    del self._parentdevice._dict_events[self]

    def wait(self, edge=BOTH, exitevent=None, okvalue=None, timeout=0):
        """Wartet auf Wertaenderung eines IOs.

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

        @param edge Flanke RISING, FALLING, BOTH die eintreten muss
        @param exitevent <class 'thrading.Event'> fuer vorzeitiges Beenden
        @param okvalue IO-Wert, bei dem das Warten sofort beendet wird
        @param timeout Zeit in ms nach der abgebrochen wird
        @return <class 'int'> erfolgreich Werte <= 0
            - Erfolgreich gewartet
                Wert 0: IO hat den Wert gewechselt
                Wert -1: okvalue stimmte mit IO ueberein
            - Fehlerhaft gewartet
                Wert 1: exitevent wurde gesetzt
                Wert 2: timeout abgelaufen
                Wert 100: Devicelist.exit() wurde aufgerufen

        """
        # Prüfen ob Device in autorefresh ist
        if not self._parentdevice._selfupdate:
            raise RuntimeError(
                "autorefresh is not activated for device '{}|{}' - there "
                "will never be new data".format(
                    self._parentdevice._position, self._parentdevice._name
                )
            )

        if edge != BOTH and self._bitaddress < 0:
            raise AttributeError(
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
    length = property(__len__)
    name = property(__str__)
    type = property(_get_iotype)
    value = property(get_value, set_value)


class IntIO(IOBase):

    """Klasse fuer den Zugriff auf die Daten mit Konvertierung in int.

    Diese Klasse erweitert die Funktion von <class 'IOBase'> um Funktionen,
    ueber die mit <class 'int'> Werten gearbeitet werden kann. Fuer die
    Umwandlung koennen 'Byteorder' (Default 'little') und 'signed' (Default
    False) als Parameter gesetzt werden.
    @see #IOBase IOBase

    """

    def __int__(self):
        """Gibt IO-Wert zurueck mit Beachtung byteorder/signed.
        @return IO-Wert als <class 'int'>"""
        return int.from_bytes(
            self._parentdevice._ba_devdata[self._slc_address],
            byteorder=self._byteorder,
            signed=self._signed
        )

    def _get_signed(self):
        """Ruft ab, ob der Wert Vorzeichenbehaftet behandelt werden soll.
        @return True, wenn Vorzeichenbehaftet"""
        return self._signed

    def _set_byteorder(self, value):
        """Setzt Byteorder fuer <class 'int'> Umwandlung.
        @param value <class 'str'> 'little' or 'big'"""
        if not (value == "little" or value == "big"):
            raise ValueError("byteorder must be 'little' or 'big'")
        if self._byteorder != value:
            self._byteorder = value
            self._defaultvalue = self._defaultvalue[::-1]

    def _set_signed(self, value):
        """Left fest, ob der Wert Vorzeichenbehaftet behandelt werden soll.
        @param value True, wenn mit Vorzeichen behandel"""
        if type(value) != bool:
            raise ValueError("signed must be <class 'bool'> True or False")
        self._signed = value

    def get_intdefaultvalue(self):
        """Gibt die Defaultvalue als <class 'int'> zurueck.
        @return <class 'int'> Defaultvalue"""
        return int.from_bytes(
            self._defaultvalue, byteorder=self._byteorder, signed=self._signed
        )

    def get_intvalue(self):
        """Gibt IO-Wert zurueck mit Beachtung byteorder/signed.
        @return IO-Wert als <class 'int'>"""
        return int.from_bytes(
            self._parentdevice._ba_devdata[self._slc_address],
            byteorder=self._byteorder,
            signed=self._signed
        )

    def set_intvalue(self, value):
        """Setzt IO mit Beachtung byteorder/signed.
        @param value <class 'int'> Wert"""
        if type(value) == int:
            self.set_value(value.to_bytes(
                self._length,
                byteorder=self._byteorder,
                signed=self._signed
            ))
        else:
            raise ValueError(
                "'{}' need a <class 'int'> value, but {} was given"
                "".format(self._name, type(value))
            )

    byteorder = property(IOBase._get_byteorder, _set_byteorder)
    defaultvalue = property(get_intdefaultvalue)
    signed = property(_get_signed, _set_signed)
    value = property(get_intvalue, set_intvalue)


class StructIO(IOBase):

    """Klasse fuer den Zugriff auf Daten ueber ein definierten struct.

    Sie stellt ueber struct die Werte in der gewuenschten Formatierung
    bereit. Der struct-Formatwert wird bei der Instantiierung festgelegt.
    @see #IOBase IOBase

    """

    def __init__(self, parentio, name, frm, **kwargs):
        """Erstellt einen IO mit struct-Formatierung.

        @param parentio ParentIO Objekt, welches ersetzt wird
        @param name Name des neuen IO
        @param frm struct formatierung (1 Zeichen)
        @param kwargs Weitere Parameter:
            - bmk: Bezeichnung fuer IO
            - bit: Registriert IO als <class 'bool'> am angegebenen Bit im Byte
            - byteorder: Byteorder fuer IO, Standardwert vom ersetzter IO
            - defaultvalue: Standardwert fuer IO, Standard vom ersetzter IO

        """
        if len(frm) == 1:
            # Byteorder prüfen und übernehmen
            byteorder = kwargs.get("byteorder", parentio._byteorder)
            if not (byteorder == "little" or byteorder == "big"):
                raise ValueError("byteorder must be 'little' or 'big'")
            bofrm = "<" if byteorder == "little" else ">"

            if frm == "?":
                bitaddress = kwargs.get("bit", 0)
                max_bits = parentio._length * 8
                if not (0 <= bitaddress < max_bits):
                    raise AttributeError(
                        "bitaddress must be a value between 0 and {}"
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

            # [name,default,anzbits,adressbyte,export,adressid,bmk,bitaddress]
            valuelist = [
                name,
                kwargs.get("defaultvalue", None),
                bitlength,
                parentio._slc_address.start,
                False,
                str(parentio._slc_address.start).rjust(4, "0"),
                kwargs.get("bmk", ""),
                bitaddress
            ]
        else:
            raise AttributeError("parameter frm has to be a single sign")

        # Basisklasse instantiieren
        super().__init__(
            parentio._parentdevice,
            valuelist,
            parentio._iotype,
            byteorder,
            frm == frm.lower()
        )
        self.__frm = bofrm + frm

        # Platz für neuen IO prüfen
        if not (self._slc_address.start >=
                parentio._parentdevice._dict_slc[parentio._iotype].start and
                self._slc_address.stop <=
                parentio._parentdevice._dict_slc[parentio._iotype].stop):

            raise BufferError(
                "registered value does not fit process image scope"
            )

    def _get_frm(self):
        """Ruft die struct Formatierung ab.
        @return struct Formatierung"""
        return self.__frm

    def _get_signed(self):
        """Ruft ab, ob der Wert Vorzeichenbehaftet behandelt werden soll.
        @return True, wenn Vorzeichenbehaftet"""
        return self._signed

    def get_structdefaultvalue(self):
        """Gibt die Defaultvalue mit struct Formatierung zurueck.
        @return Defaultvalue vom Typ der struct-Formatierung"""
        if self._bitaddress >= 0:
            return self._defaultvalue
        else:
            return struct.unpack(self.__frm, self._defaultvalue)[0]

    def get_structvalue(self):
        """Gibt den Wert mit struct Formatierung zurueck.
        @return Wert vom Typ der struct-Formatierung"""
        if self._bitaddress >= 0:
            return self.get_value()
        else:
            return struct.unpack(self.__frm, self.get_value())[0]

    def set_structvalue(self, value):
        """Setzt den Wert mit struct Formatierung.
        @param value Wert vom Typ der struct-Formatierung"""
        if self._bitaddress >= 0:
            self.set_value(value)
        else:
            self.set_value(struct.pack(self.__frm, value))

    defaultvalue = property(get_structdefaultvalue)
    frm = property(_get_frm)
    signed = property(_get_signed)
    value = property(get_structvalue, set_structvalue)


# Nachträglicher Import
from .device import Gateway

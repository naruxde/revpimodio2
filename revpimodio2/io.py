#
# python3-RevPiModIO
#
# Webpage: https://revpimodio.org/
# (c) Sven Sager, License: LGPLv3
#
# -*- coding: utf-8 -*-
"""RevPiModIO Modul fuer die Verwaltung der IOs."""
import struct
from threading import Event
from .__init__ import RISING, FALLING, BOTH


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
        @param key IO-Name str() oder Byte int()
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
                for int_io in range(key.start, key.stop)
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
        int_length = 1 if io._length == 0 else io._length
        for i in range(io.address, io.address + int_length):
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
                        # Bereits überschriebene bytes() sind ungültig
                        raise MemoryError(
                            "new io '{}' overlaps memory of '{}'".format(
                                io._name, oldio._name
                            )
                        )
                elif oldio is not None:
                    # IOs im Speicherbereich des neuen IO merken
                    if io._bitaddress >= 0:
                        # ios für ref bei bitaddress speichern
                        self.__dict_iorefname[oldio.name] = DeadIO(oldio)

                    # ios aus listen entfernen
                    delattr(self, oldio.name)

    def _private_register_new_io_object(self, new_io):
        """Registriert neues IO Objekt unabhaenging von __setattr__.
        @param new_io Neues IO Objekt"""
        if issubclass(type(new_io), IOBase):
            if hasattr(self, new_io.name):
                raise AttributeError(
                    "attribute {} already exists - can not set io".format(
                        new_io.name
                    )
                )

            if type(new_io) is StructIO:
                self.__private_replace_oldio_with_newio(new_io)

            object.__setattr__(self, new_io.name, new_io)

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
        """Instantiierung der DeadIO()-Klasse.
        @param deadio IO, der ersetzt wurde"""
        self.__deadio = deadio

    def replace_io(self, name, frm, **kwargs):
        """Stellt Funktion fuer weiter Bit-Ersetzungen bereit.
        @see #IOBase.replace_io replace_io(...)"""
        self.__deadio.replace_io(name, frm, **kwargs)


class IOBase(object):

    """Basisklasse fuer alle IO-Objekte.

    Die Basisfunktionalitaet ermoeglicht das Lesen und Schreiben der Werte
    als bytes() oder bool(). Dies entscheidet sich bei der Instantiierung.
    Wenn eine Bittadresse angegeben wird, werden bool()-Werte erwartet
    und zurueckgegeben, ansonsten bytes().

    Diese Klasse dient als Basis fuer andere IO-Klassen mit denen die Werte
    auch als int() verwendet werden koennen.

    """

    def __init__(self, parentdevice, valuelist, iotype, byteorder, signed):
        """Instantiierung der IOBase()-Klasse.

        @param parentdevice Parentdevice auf dem der IO liegt
        @param valuelist Datenliste fuer Instantiierung
        @param iotype io.Type() Wert
        @param byteorder Byteorder 'little' / 'big' fuer int() Berechnung
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
            if str(valuelist[1]).isnumeric():
                self.defaultvalue = int(valuelist[1]).to_bytes(
                    self._length, byteorder=self._byteorder
                )
            else:
                # Defaultvalue direkt von bytes übernehmen
                if type(valuelist[1]) == bytes:
                    if len(valuelist[1]) != self._length:
                        raise ValueError(
                            "given bytes for default value must have a length "
                            "of {}".format(self._length)
                        )
                    else:
                        self.defaultvalue = valuelist[1]
                else:
                    self.defaultvalue = bytes(self._length)

        else:
            # Höhere Bits als 7 auf nächste Bytes umbrechen
            int_startaddress += int((int(valuelist[7]) % 16) / 8)
            self._slc_address = slice(
                int_startaddress, int_startaddress + 1
            )
            self.defaultvalue = bool(int(valuelist[1]))

    def __bool__(self):
        """bool()-wert der Klasse.
        @return IO-Wert als bool(). Nur False wenn False oder 0 sonst True"""
        if self._bitaddress >= 0:
            int_byte = int.from_bytes(
                self._parentdevice._ba_devdata[self._slc_address],
                byteorder=self._byteorder
            )
            return bool(int_byte & 1 << self._bitaddress)
        else:
            return bool(self._parentdevice._ba_devdata[self._slc_address])

    def __str__(self):
        """str()-wert der Klasse.
        @return Namen des IOs"""
        return self._name

    def _get_address(self):
        """Gibt die absolute Byteadresse im Prozessabbild zurueck.
        @return Absolute Byteadresse"""
        return self._parentdevice.offset + self._slc_address.start

    def _get_byteorder(self):
        """Gibt konfigurierte Byteorder zurueck.
        @return str() Byteorder"""
        return self._byteorder

    def _get_iotype(self):
        """Gibt io.Type zurueck.
        @return int() io.Type"""
        return self._iotype

    def _get_length(self):
        """Gibt die Bytelaenge des IO zurueck.
        @return Bytelaenge des IO"""
        return self._length

    def _get_name(self):
        """Gibt den Namen des IOs zurueck.
        @return IO Name"""
        return self._name

    def get_value(self):
        """Gibt den Wert des IOs als bytes() oder bool() zurueck.
        @return IO-Wert"""
        if self._bitaddress >= 0:
            int_byte = int.from_bytes(
                self._parentdevice._ba_devdata[self._slc_address],
                byteorder=self._byteorder
            )
            return bool(int_byte & 1 << self._bitaddress)
        else:
            return bytes(self._parentdevice._ba_devdata[self._slc_address])

    def reg_event(self, func, edge=BOTH, as_thread=False):
        """Registriert ein Event bei der Eventueberwachung.

        @param func Funktion die bei Aenderung aufgerufen werden soll
        @param edge Ausfuehren bei RISING, FALLING or BOTH Wertaenderung
        @param as_thread Bei True, Funktion als EventCallback-Thread ausfuehren

        """
        # Prüfen ob Funktion callable ist
        if not callable(func):
            raise RuntimeError(
                "registered function '{}' ist not callable".format(func)
            )

        if edge != BOTH and self._bitaddress < 0:
            raise AttributeError(
                "parameter 'edge' can be used with bit io objects only"
            )

        if self not in self._parentdevice._dict_events:
            self._parentdevice._dict_events[self] = [(func, edge, as_thread)]
        else:
            # Prüfen ob Funktion schon registriert ist
            for regfunc in self._parentdevice._dict_events[self]:

                if regfunc[0] == func and edge == BOTH:
                    if self._bitaddress < 0:
                        raise AttributeError(
                            "io '{}' with function '{}' already in list."
                            "".format(self._name, func)
                        )
                    else:
                        raise AttributeError(
                            "io '{}' with function '{}' already in list. "
                            "edge 'BOTH' not allowed anymore".format(
                                self._name, func
                            )
                        )
                elif regfunc[0] == func and regfunc[1] == edge:
                    raise AttributeError(
                        "io '{}' with function '{}' for given edge "
                        "already in list".format(self._name, func)
                    )
                else:
                    self._parentdevice._dict_events[self].append(
                        (func, edge, as_thread)
                    )
                    break

    def replace_io(self, name, frm, **kwargs):
        """Ersetzt bestehenden IO mit Neuem.

        @param name Name des neuen Inputs
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
        if not issubclass(type(self._parentdevice), Gateway):
            raise RuntimeError(
                "this function can be used for ios on gatway or virtual "
                "devices only"
            )

        # StructIO erzeugen und in IO-Liste einfügen
        io_new = StructIO(
            self,
            name,
            frm,
            **kwargs
        )
        self._parentdevice._modio.io._private_register_new_io_object(io_new)

        # Optional Event eintragen
        reg_event = kwargs.get("event", None)
        if reg_event is not None:
            io_new.reg_event(
                reg_event,
                as_thread=kwargs.get("as_thread", False),
                edge=kwargs.get("edge", BOTH)
            )

    def set_value(self, value):
        """Setzt den Wert des IOs mit bytes() oder bool().
        @param value IO-Wert als bytes() oder bool()"""
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

        HINWEIS: Wenn ProcimgWriter() keine neuen Daten liefert, wird
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
        der autorefresh Funktion berechnet, entspricht also nicht exact den
        angegeben Millisekunden! Es wird immer nach oben gerundet!)

        @param edge Flanke RISING, FALLING, BOTH bei der mit True beendet wird
        @param exitevent thrading.Event() fuer vorzeitiges Beenden mit False
        @param okvalue IO-Wert, bei dem das Warten sofort mit True beendet wird
        @param timeout Zeit in ms nach der mit False abgebrochen wird
        @return int() erfolgreich Werte <= 0
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
                    self._parentdevice.position, self._parentdevice.name
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
    length = property(_get_length)
    name = property(_get_name)
    type = property(_get_iotype)
    value = property(get_value, set_value)


class IntIO(IOBase):

    """Klasse fuer den Zugriff auf die Daten mit Konvertierung in int().

    Diese Klasse erweitert die Funktion von IOBase() um Funktionen,
    ueber die mit int() Werten gearbeitet werden kann. Fuer die Umwandlung
    koennen 'Byteorder' (Default 'little') und 'signed' (Default False) als
    Parameter gesetzt werden.
    @see #IOBase IOBase

    """

    def __int__(self):
        """Gibt IO als int() Wert zurueck mit Beachtung byteorder/signed.
        @return int() ohne Vorzeichen"""
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
        """Setzt Byteorder fuer int() Umwandlung.
        @param value str() 'little' or 'big'"""
        if not (value == "little" or value == "big"):
            raise ValueError("byteorder must be 'little' or 'big'")
        self._byteorder = value

    def _set_signed(self, value):
        """Left fest, ob der Wert Vorzeichenbehaftet behandelt werden soll.
        @param value True, wenn mit Vorzeichen behandel"""
        if type(value) != bool:
            raise ValueError("signed must be <class 'bool'> True or False")
        self._signed = value

    def get_int(self):
        """Gibt IO als int() Wert zurueck mit Beachtung byteorder/signed.
        @return int() Wert"""
        return int.from_bytes(
            self._parentdevice._ba_devdata[self._slc_address],
            byteorder=self._byteorder,
            signed=self._signed
        )

    def set_int(self, value):
        """Setzt IO mit Beachtung byteorder/signed.
        @param value int()"""
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
    signed = property(_get_signed, _set_signed)
    value = property(get_int, set_int)


class StructIO(IOBase):

    """Klasse fuer den Zugriff auf Daten ueber ein definierten struct().

    Diese Klasse ueberschreibt get_value() und set_value() der IOBase()
    Klasse. Sie stellt ueber struct die Werte in der gewuenschten Formatierung
    bereit. Der struct-Formatwert wird bei der Instantiierung festgelegt.
    @see #IOBase IOBase

    """

    def __init__(self, parentio, name, frm, **kwargs):
        """Erstellt einen IO mit struct-Formatierung.

        @param parentio ParentIO Objekt, welches ersetzt wird
        @param name Name des neuen IO
        @param frm struct() formatierung (1 Zeichen)
        @param kwargs Weitere Parameter:
            - bmk: Bezeichnung fuer Output
            - bit: Registriert Outputs als bool() am angegebenen Bit im Byte
            - byteorder: Byteorder fuer den Input, Standardwert=little
            - defaultvalue: Standardwert fuer Output, Standard ist 0

        """
        if len(frm) == 1:
            # Byteorder prüfen und übernehmen
            byteorder = kwargs.get("byteorder", "little")
            if not (byteorder == "little" or byteorder == "big"):
                raise ValueError("byteorder must be 'little' or 'big'")
            bofrm = "<" if byteorder == "little" else ">"

            bitaddress = "" if frm != "?" else str(kwargs.get("bit", 0))
            if bitaddress == "" or (0 <= int(bitaddress) < 8):

                bitlength = "1" if bitaddress.isnumeric() else \
                    struct.calcsize(bofrm + frm) * 8

                # [name,default,anzbits,adressbyte,export,adressid,bmk,bitaddress]
                valuelist = [
                    name,
                    kwargs.get("defaultvalue", 0),
                    bitlength,
                    parentio._slc_address.start,
                    False,
                    str(parentio._slc_address.start).rjust(4, "0"),
                    kwargs.get("bmk", ""),
                    bitaddress
                ]

            else:
                raise AttributeError(
                    "bitaddress must be a value between 0 and 7"
                )
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
        """Ruft die struct() Formatierung ab.
        @return struct() Formatierung"""
        return self.__frm

    def _get_signed(self):
        """Ruft ab, ob der Wert Vorzeichenbehaftet behandelt werden soll.
        @return True, wenn Vorzeichenbehaftet"""
        return self._signed

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

    frm = property(_get_frm)
    signed = property(_get_signed)
    value = property(get_structvalue, set_structvalue)


# Nachträglicher Import
from .device import Gateway

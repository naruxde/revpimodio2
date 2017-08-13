#
# python3-RevPiModIO
#
# Webpage: https://revpimodio.org/
# (c) Sven Sager, License: LGPLv3
#
# -*- coding: utf-8 -*-
import struct
from .__init__ import RISING, FALLING, BOTH
from .device import Gateway
from threading import Event


class IOType(object):

    """IO Typen."""

    INP = 300
    OUT = 301
    MEM = 302


class IOList(object):

    """Basisklasse fuer direkten Zugriff auf IO Objekte."""

    def __init__(self):
        """Init IOList clacc."""
        self.__dict_iobyte = {k: [] for k in range(4096)}

    def __contains__(self, key):
        """Prueft ob IO existiert.
        @param key IO-Name str()
        @return True, wenn IO vorhanden"""
        if type(key) == int:
            return key in self.__dict_iobyte \
                and len(self.__dict_iobyte[key]) > 0
        else:
            return hasattr(self, key)

    def __delattr__(self, key):
        """Entfernt angegebenen IO.
        @param key IO zum entfernen"""
        # TODO: Prüfen ob auch Bit sein kann
        dev = getattr(self, key)
        self.__dict_iobyte[dev.address].remove(dev)
        object.__delattr__(self, key)

    def __getitem__(self, key):
        """Ruft angegebenen IO ab.
        @param key IO Name oder Byte
        @return IO Object"""
        if type(key) == int:
            if key in self.__dict_iobyte:
                return self.__dict_iobyte[key]
            else:
                raise KeyError("byte '{}' does not exist".format(key))
        else:
            return getattr(self, key)

    def __setitem__(self, key, value):
        """Setzt IO Wert.
        @param key IO Name oder Byte
        @param value Wert, auf den der IO gesetzt wird"""
        if type(key) == int:
            if key in self.__dict_iobyte:
                if len(self.__dict_iobyte[key]) == 1:
                    self.__dict_iobyte[key][0].value = value
                elif len(self.__dict_iobyte[key]) == 0:
                    raise KeyError("byte '{}' contains no input".format(key))
                else:
                    raise KeyError(
                        "byte '{}' contains more than one bit-input"
                        "".format(key)
                    )
            else:
                raise KeyError("byte '{}' does not exist".format(key))
        else:
            getattr(self, key).value = value

    def __setattr__(self, key, value):
        """Setzt IO Wert.
        @param key IO Name oder Byte
        @param value Wert, auf den der IO gesetzt wird"""
        if issubclass(type(value), IOBase):
            if hasattr(self, key):
                raise AttributeError(
                    "attribute {} already exists - can not set io".format(key)
                )
            object.__setattr__(self, key, value)

            # Bytedict erstellen für Adresszugriff
            if value._bitaddress < 0:
                self.__dict_iobyte[value.address].append(value)
            else:
                if len(self.__dict_iobyte[value.address]) != 8:
                    # "schnell" 8 Einträge erstellen da es BIT IOs sind
                    self.__dict_iobyte[value.address] += [
                        None, None, None, None, None, None, None, None
                    ]
                self.__dict_iobyte[value.address][value._bitaddress] = value

        elif key == "_IOList__dict_iobyte":
            object.__setattr__(self, key, value)

        else:
            getattr(self, key).value = value

    def _testme(self):
        # NOTE: Nur Debugging
        for x in self.__dict_iobyte:
            if len(self.__dict_iobyte[x]) > 0:
                print(x, self.__dict_iobyte[x])

    def reg_inp(self, name, frm, **kwargs):
        """Registriert einen neuen Input an Adresse von Diesem.

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
        if not issubclass(self._parentdevice, Gateway):
            raise RuntimeError(
                "this function can be used on gatway or virtual devices only"
            )

        self._create_io(name, startinp, frm, IOType.INP, **kwargs)

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
        if not issubclass(self._parentdevice, Gateway):
            raise RuntimeError(
                "this function can be used on gatway or virtual devices only"
            )

        self._create_io(name, startout, frm, IOType.OUT, **kwargs)

        # Optional Event eintragen
        reg_event = kwargs.get("event", None)
        if reg_event is not None:
            as_thread = kwargs.get("as_thread", False)
            edge = kwargs.get("edge", None)
            self.reg_event(name, reg_event, as_thread=as_thread, edge=edge)


class IOBase(object):

    """Basisklasse fuer alle IO-Objekte.

    Die Basisfunktionalitaet ermoeglicht das Lesen und Schreiben der Werte
    als bytes() oder bool(). Dies entscheidet sich bei der Instantiierung.
    Wenn eine Bittadresse angegeben wird, werden bool()-Werte erwartet
    und zurueckgegeben, ansonsten bytes().

    Diese Klasse dient als Basis fuer andere IO-Klassen mit denen die Werte
    auch als int() verwendet werden koennen.

    """

    def __init__(self, parentdevice, valuelist, iotype, byteorder):
        """Instantiierung der IOBase()-Klasse.

        @param parentdevice Parentdevice auf dem der IO liegt
        @param valuelist Datenliste fuer Instantiierung
        @param iotype IOType() Wert
        @param byteorder Byteorder 'little' / 'big' fuer int() Berechnung

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
        self._signed = False
        self.bmk = valuelist[6]

        int_startaddress = int(valuelist[3])
        if self._bitaddress == -1:
            self.slc_address = slice(
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
            self.slc_address = slice(
                int_startaddress, int_startaddress + 1
            )
            self.defaultvalue = bool(int(valuelist[1]))

    def __bool__(self):
        """bool()-wert der Klasse.
        @return IO-Wert als bool(). Nur False wenn False oder 0 sonst True"""
        return bool(self.get_value())

    def __bytes__(self):
        """bytes()-wert der Klasse.
        @return IO-Wert als bytes()"""
        if self._bitaddress >= 0:
            int_byte = int.from_bytes(
                self._parentdevice._ba_devdata[self.slc_address],
                byteorder=self._byteorder
            )
            return b'\x01' if bool(int_byte & 1 << self._bitaddress) \
                else b'\x00'
        else:
            return bytes(self._parentdevice._ba_devdata[self.slc_address])

    def __str__(self):
        """str()-wert der Klasse.
        @return Namen des IOs"""
        return self._name

    def _get_byteorder(self):
        """Gibt konfigurierte Byteorder zurueck.
        @return str() Byteorder"""
        return self._byteorder

    def get_address(self):
        """Gibt die absolute Byteadresse im Prozessabbild zurueck.
        @return Absolute Byteadresse"""
        return self._parentdevice.offset + self.slc_address.start

    def get_length(self):
        """Gibt die Bytelaenge des IO zurueck.
        @return Bytelaenge des IO"""
        return self._length

    def get_name(self):
        """Gibt den Namen des IOs zurueck.
        @return IO Name"""
        return self._name

    def get_value(self):
        """Gibt den Wert des IOs als bytes() oder bool() zurueck.
        @return IO-Wert"""
        if self._bitaddress >= 0:
            int_byte = int.from_bytes(
                self._parentdevice._ba_devdata[self.slc_address],
                byteorder=self._byteorder
            )
            return bool(int_byte & 1 << self._bitaddress)

        else:
            return bytes(self._parentdevice._ba_devdata[self.slc_address])

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

    def set_value(self, value):
        """Setzt den Wert des IOs mit bytes() oder bool().
        @param value IO-Wert als bytes() oder bool()"""
        if self._iotype == IOType.OUT:
            if self._bitaddress >= 0:
                # Versuchen egal welchen Typ in Bool zu konvertieren
                value = bool(value)

                # ganzes Byte laden
                byte_buff = self._parentdevice._ba_devdata[self.slc_address]

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
                    self._parentdevice._ba_devdata[self.slc_address] = \
                        int_byte.to_bytes(int_len, byteorder=self._byteorder)

            else:
                if type(value) == bytes:
                    if self._length == len(value):
                        self._parentdevice._ba_devdata[self.slc_address] = \
                            value
                    else:
                        raise ValueError(
                            "requires a bytes() object of length {}, but"
                            " {} was given".format(self._length, len(value))
                        )
                else:
                    raise ValueError(
                        "requires a bytes() object, not {}".format(type(value))
                    )

        elif self._iotype == IOType.INP:
            raise AttributeError("can not write to input")
        elif self._iotype == IOType.MEM:
            raise AttributeError("can not write to memory")

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
        in Devicelist.auto_refresh() neue Daten gelesen wurden.

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
        der auto_refresh Funktion berechnet, entspricht also nicht exact den
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
        # Prüfen ob Device in auto_refresh ist
        if not self._parentdevice._selfupdate:
            raise RuntimeError(
                "auto_refresh is not activated for device '{}|{}' - there "
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
        self._parentdevice._parent._waitexit.clear()

        val_start = self.value
        timeout = timeout / 1000
        bool_timecount = timeout > 0
        if exitevent is None:
            exitevent = Event()

        flt_timecount = 0 if bool_timecount else -1
        while not self._parentdevice._parent._waitexit.is_set() \
                and not exitevent.is_set() \
                and flt_timecount < timeout:

            if self._parentdevice._parent.imgwriter.newdata.wait(2.5):
                self._parentdevice._parent.imgwriter.newdata.clear()

                if val_start != self.value:
                    if edge == BOTH \
                            or edge == RISING and not val_start \
                            or edge == FALLING and val_start:
                        return 0
                    else:
                        val_start = not val_start
                if bool_timecount:
                    flt_timecount += \
                        self._parentdevice._parent.imgwriter._refresh
            elif bool_timecount:
                # TODO: Prüfen
                flt_timecount += 1

        # Abbruchevent wurde gesetzt
        if exitevent.is_set():
            return 1

        # RevPiModIO mainloop wurde verlassen
        if self._parentdevice._parent._waitexit.is_set():
            return 100

        # Timeout abgelaufen
        return 2

    address = property(get_address)
    length = property(get_length)
    name = property(get_name)
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
        return self.get_int()

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
            raise ValueError("signed must be bool() True or False")
        self._signed = value

    def get_int(self):
        """Gibt IO als int() Wert zurueck mit Beachtung byteorder/signed.
        @return int() Wert"""
        return int.from_bytes(
            self._parentdevice._ba_devdata[self.slc_address],
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
                "need an int() value, but {} was given".format(type(value))
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

    def __init__(self, parentdevice, valuelist, iotype, byteorder, frm):
        """Erweitert IOBase um struct-Formatierung.
        @see #IOBase.__init__ IOBase.__init__(...)"""
        super().__init__(parentdevice, valuelist, iotype, byteorder)
        self.frm = frm

    def get_structvalue(self):
        """Gibt den Wert mit struct Formatierung zurueck.
        @return Wert vom Typ der struct-Formatierung"""
        if self._bitaddress >= 0:
            return self.get_value()
        else:
            return struct.unpack(self.frm, self.get_value())[0]

    def set_structvalue(self, value):
        """Setzt den Wert mit struct Formatierung.
        @param value Wert vom Typ der struct-Formatierung"""
        if self._bitaddress >= 0:
            self.set_value(value)
        else:
            self.set_value(struct.pack(self.frm, value))

    byteorder = property(IOBase._get_byteorder)
    value = property(get_structvalue, set_structvalue)

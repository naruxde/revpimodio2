# -*- coding: utf-8 -*-
#
# python3-RevPiModIO
#
# Webpage: https://revpimodio.org/
# (c) Sven Sager, License: LGPLv3
#
"""RevPiModIO Hauptklasse fuer Netzwerkzugriff."""
import socket
from json import loads as jloads
from threading import Thread, Event, Lock

from .device import Device
from .modio import RevPiModIO as _RevPiModIO

# Synchronisierungsbefehl
_syssync = b'\x01\x06\x16\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x17'
# Disconnectbefehl
_sysexit = b'\x01EX\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x17'
# DirtyBytes von Server entfernen
_sysdeldirty = b'\x01EY\x00\x00\x00\x00\xFF\x00\x00\x00\x00\x00\x00\x00\x17'
# piCtory Konfiguration laden
_syspictory = b'\x01PI\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x17'
# Übertragene Bytes schreiben
_sysflush = b'\x01SD\x00\x00\x00\x00\x1c\x00\x00\x00\x00\x00\x00\x00\x17'


class NetFH(Thread):

    """Netzwerk File Handler fuer das Prozessabbild.

    Dieses FileObject-like Object verwaltet das Lesen und Schriben des
    Prozessabbilds ueber das Netzwerk. Ein entfernter Revolution Pi kann
    so gesteuert werden.

    """

    def __init__(self, address, timeout=500):
        """Init NetFH-class."""
        super().__init__()
        self.daemon = True

        self.__by_buff = b''
        self.__int_buff = 0
        self.__dictdirty = {}
        self.__flusherr = False
        self.__sockact = False
        self.__sockerr = Event()
        self.__sockend = False
        self.__socklock = Lock()
        self.__timeout = timeout / 1000
        self.__trigger = False
        self.__waitsync = self.__timeout / 2

        socket.setdefaulttimeout(self.__timeout)

        # Verbindung herstellen
        self._address = address
        self._slavesock = None
        self._connect()

        if self._slavesock is None:
            raise FileNotFoundError("can not connect to revpi slave")

        # NetFH konfigurieren
        self.__position = 0
        self.start()

    def __del__(self):
        """NetworkFileHandler beenden."""
        self.close()

    def _connect(self):
        """Stellt die Verbindung zu einem RevPiSlave her."""
        # Neuen Socket aufbauen
        so = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            so.connect(self._address)
        except:
            so.close()
        else:
            # Alten Socket trennen
            with self.__socklock:
                if self._slavesock is not None:
                    self._slavesock.close()

                self._slavesock = so
                self.__sockerr.clear()

            # Timeout setzen
            self.set_timeout(int(self.__timeout * 1000))

            # DirtyBytes übertragen
            for pos in self.__dictdirty:
                self.set_dirtybytes(pos, self.__dictdirty[pos])

    def clear_dirtybytes(self, position=None):
        """Entfernt die konfigurierten Dirtybytes vom RevPi Slave.
        @param position Startposition der Dirtybytes"""
        if self.__sockend:
            raise ValueError("I/O operation on closed file")

        with self.__socklock:
            if position is None:
                # Alle Dirtybytes löschen
                self._slavesock.sendall(_sysdeldirty)
            else:
                # Nur bestimmte Dirtybytes löschen
                self._slavesock.sendall(
                    b'\x01EY' +
                    position.to_bytes(length=2, byteorder="little") +
                    b'\x00\x00\xFE\x00\x00\x00\x00\x00\x00\x00\x17'
                )

            check = self._slavesock.recv(1)
            if check != b'\x1e':
                self.__sockerr.set()
                raise IOError("clear dirtybytes error on network")

        # Daten bei Erfolg übernehmen
        if position is None:
            self.__dictdirty = {}
        elif position in self.__dictdirty:
            del self.__dictdirty[position]

        self.__trigger = True

    def close(self):
        """Verbindung trennen."""
        self.__sockend = True
        self.__sockerr.set()

        # Vom Socket sauber trennen
        if self._slavesock is not None:
            with self.__socklock:
                try:
                    if self.__sockend:
                        self._slavesock.send(_sysexit)
                    else:
                        self._slavesock.shutdown(socket.SHUT_RDWR)
                except:
                    pass
            self._slavesock.close()

    def flush(self):
        """Schreibpuffer senden."""
        if self.__sockend:
            raise ValueError("flush of closed file")

        with self.__socklock:
            self._slavesock.sendall(
                self.__by_buff + _sysflush
            )

            # Rückmeldebyte auswerten
            blockok = self._slavesock.recv(1)
            if blockok != b'\x1e':
                self.__sockerr.set()
                self.__flusherr = True
                raise IOError("flush error on network")
            else:
                self.__flusherr = False

                # Puffer leeren
                self.__int_buff = 0
                self.__by_buff = b''

            self.__trigger = True

    def get_closed(self):
        """Pruefen ob Verbindung geschlossen ist.
        @return True, wenn Verbindung geschlossen ist"""
        return self.__sockend

    def get_name(self):
        """Verbindugnsnamen zurueckgeben.
        @return <class 'str'> IP:PORT"""
        return "{}:{}".format(*self._address)

    def get_timeout(self):
        """Gibt aktuellen Timeout zurueck.
        @return <class 'int'> in Millisekunden"""
        return int(self.__timeout * 1000)

    def read(self, length):
        """Daten ueber das Netzwerk lesen.
        @param length Anzahl der Bytes
        @return Gelesene <class 'bytes'>"""
        if self.__sockend:
            raise ValueError("read of closed file")

        with self.__socklock:
            self._slavesock.send(
                b'\x01DA' +
                self.__position.to_bytes(length=2, byteorder="little") +
                length.to_bytes(length=2, byteorder="little") +
                b'\x00\x00\x00\x00\x00\x00\x00\x00\x17'
            )

            bytesbuff = bytearray()
            while not self.__sockend and len(bytesbuff) < length:
                rbytes = self._slavesock.recv(1024)

                if rbytes == b'':
                    self.__sockerr.set()
                    raise IOError("read error on network")
                bytesbuff += rbytes

            self.__position += length
            self.__trigger = True

        return bytes(bytesbuff)

    def readpictory(self):
        """Ruft die piCtory Konfiguration ab.
        @return <class 'bytes'> piCtory Datei"""
        if self.__sockend:
            raise ValueError("read of closed file")

        with self.__socklock:
            self._slavesock.send(_syspictory)

            byte_buff = bytearray()
            while not self.__sockend:
                data = self._slavesock.recv(1024)

                byte_buff += data
                if data.find(b'\x04') >= 0:
                    # NOTE: Nur suchen oder Ende prüfen?
                    return byte_buff[:-1]

            self.__sockerr.set()
            raise IOError("readpictory error on network")

            self.__trigger = True

    def run(self):
        """Handler fuer Synchronisierung."""
        while not self.__sockend:

            # Auf Fehlermeldung warten
            if self.__sockerr.wait(self.__waitsync):
                if not self.__sockend:
                    # Im Fehlerfall neu verbinden
                    self._connect()

            elif not self.__sockend:
                # Kein Fehler aufgetreten, sync durchführen wenn socket frei
                if not self.__trigger and \
                        self.__socklock.acquire(blocking=False):
                    try:
                        self._slavesock.send(_syssync)
                        data = self._slavesock.recv(2)
                    except IOError:
                        print("ioerror in run()")
                        self.__sockerr.set()
                    else:
                        if data != b'\x06\x16':
                            print("data error in run():", str(data))
                            self.__sockerr.set()
                    self.__socklock.release()

                self.__trigger = False

    def seek(self, position):
        """Springt an angegebene Position.
        @param position An diese Position springen"""
        if self.__sockend:
            raise ValueError("seek of closed file")
        self.__position = int(position)

    def set_dirtybytes(self, position, dirtybytes):
        """Konfiguriert Dirtybytes fuer Prozessabbild bei Verbindungsfehler.
        @param positon Startposition zum Schreiben
        @param dirtybytes <class 'bytes'> die geschrieben werden sollen"""
        if self.__sockend:
            raise ValueError("I/O operation on closed file")

        with self.__socklock:
            self._slavesock.sendall(
                b'\x01EY' +
                position.to_bytes(length=2, byteorder="little") +
                len(dirtybytes).to_bytes(length=2, byteorder="little") +
                b'\x00\x00\x00\x00\x00\x00\x00\x00\x17' +
                dirtybytes
            )

            check = self._slavesock.recv(1)
            if check != b'\x1e':
                self.__sockerr.set()
                raise IOError("set dirtybytes error on network")

            # Daten erfolgreich übernehmen
            self.__dictdirty[position] = dirtybytes

            self.__trigger = True

    def set_timeout(self, value):
        """Setzt Timeoutwert fuer Verbindung.
        @param value Timeout in Millisekunden"""
        if self.__sockend:
            raise ValueError("I/O operation on closed file")

        if type(value) == int and (0 < value <= 65535):
            self.__timeout = value / 1000
            self.__waitsync = self.__timeout / 2 - 0.05

            # Timeouts in Sockets übernehmen
            socket.setdefaulttimeout(self.__timeout)
            self._slavesock.settimeout(self.__timeout)

            with self.__socklock:
                self._slavesock.send(
                    b'\x01CF' +
                    value.to_bytes(length=2, byteorder="little") +
                    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x17'
                )
                check = self._slavesock.recv(1)
                if check != b'\x1e':
                    self.__sockerr.set()
                    raise IOError("set timeout error on network")

                self.__trigger = True

        else:
            raise ValueError("value must between 1 and 65535 milliseconds")

    def tell(self):
        """Gibt aktuelle Position zurueck.
        @return int aktuelle Position"""
        if self.__sockend:
            raise ValueError("I/O operation on closed file")
        return self.__position

    def write(self, bytebuff):
        """Daten ueber das Netzwerk schreiben.
        @param bytebuff Bytes zum schreiben
        @return <class 'int'> Anzahl geschriebener bytes"""
        if self.__sockend:
            raise ValueError("write to closed file")

        if self.__flusherr:
            raise IOError("I/O error since last flush")

        with self.__socklock:
            self.__int_buff += 1

            # Datenblöcke mit Group Seperator in Puffer ablegen
            self.__by_buff += b'\x01SD' + \
                self.__position.to_bytes(length=2, byteorder="little") + \
                len(bytebuff).to_bytes(length=2, byteorder="little") + \
                b'\x1d\x00\x00\x00\x00\x00\x00\x00\x17' + \
                bytebuff

        # TODO: Bufferlänge und dann flushen?

        return len(bytebuff)

    closed = property(get_closed)
    name = property(get_name)
    timeout = property(get_timeout, set_timeout)


class RevPiNetIO(_RevPiModIO):

    """Klasse fuer die Verwaltung der piCtory Konfiguration ueber das Netzwerk.

    Diese Klasse uebernimmt die gesamte Konfiguration aus piCtory und bilded
    die Devices und IOs ab. Sie uebernimmt die exklusive Verwaltung des
    Prozessabbilds und stellt sicher, dass die Daten synchron sind.
    Sollten nur einzelne Devices gesteuert werden, verwendet man
    RevPiModIOSelected() und uebergibt bei Instantiierung eine Liste mit
    Device Positionen oder Device Namen.

    """

    def __init__(
            self, address, autorefresh=False, monitoring=False,
            syncoutputs=True, simulator=False):
        """Instantiiert die Grundfunktionen.

        @param address: IP-Adresse <class 'str'> / (IP, Port) <class 'tuple'>
        @param autorefresh Wenn True, alle Devices zu autorefresh hinzufuegen
        @param monitoring In- und Outputs werden gelesen, niemals geschrieben
        @param syncoutputs Aktuell gesetzte Outputs vom Prozessabbild einlesen
        @param simulator Laed das Modul als Simulator und vertauscht IOs

        """
        # Adresse verarbeiten
        if type(address) == str:
            # TODO: IP-Adresse prüfen
            self._address = (address, 55234)
        elif type(address) == tuple:
            if len(address) == 2 \
                    and type(address[0]) == str \
                    and type(address[1]) == int:

                # Werte prüfen
                # TODO: IP-Adresse prüfen
                if not 0 < address[1] <= 65535:
                    raise ValueError("port number out of range 1 - 65535")

                self._address = address
            else:
                raise ValueError(
                    "address tuple must be (<class 'str'>, <class 'int'>)"
                )
        else:
            raise ValueError(
                "parameter address must be <class 'str'> or <class 'tuple'> "
                "like (<class 'str'>, <class 'int'>)"
            )

        # Vererben
        super().__init__(
            autorefresh,
            monitoring,
            syncoutputs,
            "{}:{}".format(*self._address),
            None,
            simulator
        )

        # Netzwerkfilehandler anlegen
        self._myfh = self._create_myfh()

        # Nur Konfigurieren, wenn nicht vererbt
        if type(self) == RevPiNetIO:
            self._configure(self.get_jconfigrsc())

    def _create_myfh(self):
        """Erstellt NetworkFileObject.
        return FileObject"""
        self._buffedwrite = True
        return NetFH(self._address)

    def disconnect(self):
        """Trennt Verbindungen und beendet autorefresh inkl. alle Threads."""
        self.cleanup()

    def get_jconfigrsc(self):
        """Laed die piCotry Konfiguration und erstellt ein <class 'dict'>.
        @return <class 'dict'> der piCtory Konfiguration"""
        mynh = NetFH(self._address)
        byte_buff = mynh.readpictory()
        mynh.close()
        return jloads(byte_buff.decode("utf-8"))

    def net_cleardefaultvalues(self, device=None):
        """Loescht Defaultwerte vom PLC Slave.
        @param device nur auf einzelnes Device anwenden, sonst auf Alle"""

        if self.monitoring:
            raise RuntimeError(
                "can not send default values, while system is in "
                "monitoring mode"
            )

        if device is None:
            self._myfh.clear_dirtybytes()
        else:
            dev = device if issubclass(type(device), Device) \
                else self.device.__getitem__(device)
            mylist = [dev]

            for dev in mylist:
                self._myfh.clear_dirtybytes(dev._offset + dev._slc_out.start)

    def net_setdefaultvalues(self, device=None):
        """Konfiguriert den PLC Slave mit den piCtory Defaultwerten.
        @param device nur auf einzelnes Device anwenden, sonst auf Alle"""

        if self.monitoring:
            raise RuntimeError(
                "can not send default values, while system is in "
                "monitoring mode"
            )

        if device is None:
            mylist = self.device
        else:
            dev = device if issubclass(type(device), Device) \
                else self.device.__getitem__(device)
            mylist = [dev]

        for dev in mylist:
            dirtybytes = bytearray()
            for lst_io in self.io[dev._slc_outoff]:
                listlen = len(lst_io)

                if listlen == 1:
                    # Byteorientierte Outputs direkt übernehmen
                    dirtybytes += lst_io[0]._defaultvalue

                elif listlen > 1:
                    # Bitorientierte Outputs in ein Byte zusammenfassen
                    int_byte = 0
                    lstbyte = lst_io.copy()
                    lstbyte.reverse()

                    for bitio in lstbyte:
                        # Von hinten die bits nach vorne schieben
                        int_byte <<= 1
                        if bitio is not None:
                            int_byte += 1 if bitio._defaultvalue else 0

                    # Errechneten Int-Wert in ein Byte umwandeln
                    dirtybytes += \
                        int_byte.to_bytes(length=1, byteorder="little")

            # Dirtybytes an PLC Slave senden
            self._myfh.set_dirtybytes(
                dev._offset + dev._slc_out.start, dirtybytes
            )


class RevPiNetIOSelected(RevPiNetIO):

    """Klasse fuer die Verwaltung einzelner Devices aus piCtory.

    Diese Klasse uebernimmt nur angegebene Devices der piCtory Konfiguration
    und bilded sie inkl. IOs ab. Sie uebernimmt die exklusive Verwaltung des
    Adressbereichs im Prozessabbild an dem sich die angegebenen Devices
    befinden und stellt sicher, dass die Daten synchron sind.

    """

    def __init__(
            self, address, deviceselection, autorefresh=False,
            monitoring=False, syncoutputs=True, simulator=False):
        """Instantiiert nur fuer angegebene Devices die Grundfunktionen.

        Der Parameter deviceselection kann eine einzelne
        Device Position / einzelner Device Name sein oder eine Liste mit
        mehreren Positionen / Namen

        @param address: IP-Adresse <class 'str'> / (IP, Port) <class 'tuple'>
        @param deviceselection Positionsnummer oder Devicename
        @see #RevPiNetIO.__init__ RevPiNetIO.__init__(...)

        """
        super().__init__(
            address, autorefresh, monitoring, syncoutputs, simulator
        )

        # Device liste erstellen
        if type(deviceselection) == list:
            for dev in deviceselection:
                self._lst_devselect.append(dev)
        else:
            self._lst_devselect.append(deviceselection)

        for vdev in self._lst_devselect:
            if type(vdev) != int and type(vdev) != str:
                raise ValueError(
                    "need device position as <class 'int'> or device name as "
                    "<class 'str'>"
                )

        self._configure(self.get_jconfigrsc())

        if len(self.device) == 0:
            if type(self) == RevPiNetIODriver:
                raise RuntimeError(
                    "could not find any given VIRTUAL devices in config"
                )
            else:
                raise RuntimeError(
                    "could not find any given devices in config"
                )
        elif len(self.device) != len(self._lst_devselect):
            if type(self) == RevPiNetIODriver:
                raise RuntimeError(
                    "could not find all given VIRTUAL devices in config"
                )
            else:
                raise RuntimeError(
                    "could not find all given devices in config"
                )


class RevPiNetIODriver(RevPiNetIOSelected):

    """Klasse um eigene Treiber fuer die virtuellen Devices zu erstellen.

    Mit dieser Klasse werden nur angegebene Virtuelle Devices mit RevPiModIO
    verwaltet. Bei Instantiierung werden automatisch die Inputs und Outputs
    verdreht, um das Schreiben der Inputs zu ermoeglichen. Die Daten koennen
    dann ueber logiCAD an den Devices abgerufen werden.

    """

    def __init__(
            self, address, virtdev, autorefresh=False, monitoring=False,
            syncoutputs=True):
        """Instantiiert die Grundfunktionen.

        Parameter 'monitoring' und 'simulator' stehen hier nicht zur
        Verfuegung, da diese automatisch gesetzt werden.

        @param address: IP-Adresse <class 'str'> / (IP, Port) <class 'tuple'>
        @param virtdev Virtuelles Device oder mehrere als <class 'list'>
        @see #RevPiModIO.__init__ RevPiModIO.__init__(...)

        """
        # Parent mit monitoring=False und simulator=True laden
        super().__init__(
            address, virtdev, autorefresh, False, syncoutputs, True
        )

# -*- coding: utf-8 -*-
"""RevPiModIO Hauptklasse fuer Netzwerkzugriff."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2018 Sven Sager"
__license__ = "LGPLv3"
import socket
import warnings
from configparser import ConfigParser
from json import loads as jloads
from re import compile
from revpimodio2 import DeviceNotFoundError
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
_syspictoryh = b'\x01PH\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x17'
# ReplaceIO Konfiguration laden
_sysreplaceio = b'\x01RP\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x17'
_sysreplaceioh = b'\x01RH\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x17'
# Übertragene Bytes schreiben
_sysflush = b'\x01SD\x00\x00\x00\x00\x1c\x00\x00\x00\x00\x00\x00\x00\x17'
# Hashvalues
HASH_FAIL = b'\xff' * 16


class AclException(Exception):

    """Probleme mit Berechtigungen."""

    pass


class ConfigChanged(Exception):

    """Aenderung der piCtory oder replace_ios Datei."""

    pass


class NetFH(Thread):

    """Netzwerk File Handler fuer das Prozessabbild.

    Dieses FileObject-like Object verwaltet das Lesen und Schriben des
    Prozessabbilds ueber das Netzwerk. Ein entfernter Revolution Pi kann
    so gesteuert werden.

    """

    __slots__ = "__by_buff", "__check_replace_ios", "__config_changed", \
        "__int_buff", "__dictdirty", "__flusherr", "__replace_ios_h", \
        "__pictory_h",  "__position", "__sockact", "__sockerr", "__sockend", \
        "__socklock", "__timeout", "__trigger", "__waitsync", "_address", \
        "_slavesock", "daemon"

    def __init__(self, address, check_replace_ios, timeout=500):
        """Init NetFH-class.

        @param address IP Adresse, Port des RevPi als <class 'tuple'>
        @param check_replace_ios Prueft auf Veraenderungen der Datei
        @param timeout Timeout in Millisekunden der Verbindung

        """
        super().__init__()
        self.daemon = True

        self.__by_buff = b''
        self.__check_replace_ios = check_replace_ios
        self.__config_changed = False
        self.__int_buff = 0
        self.__dictdirty = {}
        self.__flusherr = False
        self.__replace_ios_h = b''
        self.__pictory_h = b''
        self.__sockact = False
        self.__sockerr = Event()
        self.__sockend = Event()
        self.__socklock = Lock()
        self.__timeout = None
        self.__trigger = False
        self.__waitsync = None
        self._address = address
        self._slavesock = None

        # Parameterprüfung
        if not isinstance(address, tuple):
            raise TypeError(
                "parameter address must be <class 'tuple'> ('IP', PORT)"
            )
        if not isinstance(timeout, int):
            raise TypeError("parameter timeout must be <class 'int'>")

        # Verbindung herstellen
        self.__set_systimeout(timeout)
        self._connect()

        if self._slavesock is None:
            raise FileNotFoundError("can not connect to revpi slave")

        # NetFH konfigurieren
        self.__position = 0
        self.start()

    def __del__(self):
        """NetworkFileHandler beenden."""
        self.close()

    def __check_acl(self, bytecode):
        """Pueft ob ACL auf RevPi den Vorgang erlaubt oder wirft exception."""
        if bytecode == b'\x18':

            # Alles beenden, wenn nicht erlaubt
            self.__sockend.set()
            self.__sockerr.set()
            self._slavesock.close()
            raise AclException(
                "write access to the process image is not permitted - use "
                "monitoring=True or check aclplcslave.conf on RevPi and "
                "reload revpipyload!"
            )

    def __set_systimeout(self, value):
        """Systemfunktion fuer Timeoutberechnung.
        @param value Timeout in Millisekunden 100 - 60000"""

        if isinstance(value, int) and (100 <= value <= 60000):
            self.__timeout = value / 1000

            socket.setdefaulttimeout(self.__timeout)

            # Timeouts in Socket setzen
            if self._slavesock is not None:
                self._slavesock.settimeout(self.__timeout)

            # 45 Prozent vom Timeout für Synctimer verwenden
            self.__waitsync = self.__timeout / 10 * 4.5

        else:
            raise ValueError("value must between 10 and 60000 milliseconds")

    def _connect(self):
        """Stellt die Verbindung zu einem RevPiSlave her."""
        # Neuen Socket aufbauen
        so = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            so.connect(self._address)

            # Hashwerte anfordern
            recv_len = 16
            so.sendall(_syspictoryh)
            if self.__check_replace_ios:
                so.sendall(_sysreplaceioh)
                recv_len += 16

            # Hashwerte empfangen
            byte_buff = bytearray()
            zero_byte = 0
            while not self.__sockend.is_set() and len(byte_buff) < recv_len:
                data = so.recv(recv_len)
                if data == b'':
                    zero_byte += 1
                    if zero_byte == 100:
                        raise OSError("too many zero bytes on hash load")
                byte_buff += data

            # Änderung an piCtory prüfen
            if self.__pictory_h and byte_buff[:16] != self.__pictory_h:
                self.__config_changed = True
                self.close()
                raise ConfigChanged(
                    "configuration on revolution pi was changed")
            else:
                self.__pictory_h = byte_buff[:16]

            # Änderung an replace_ios prüfen
            if self.__check_replace_ios and self.__replace_ios_h \
                    and byte_buff[16:] != self.__replace_ios_h:
                self.__config_changed = True
                self.close()
                raise ConfigChanged(
                    "configuration on revolution pi was changed")
            else:
                self.__replace_ios_h = byte_buff[16:]
        except ConfigChanged:
            so.close()
            raise
        except Exception:
            so.close()
        else:
            # Alten Socket trennen
            with self.__socklock:
                if self._slavesock is not None:
                    self._slavesock.close()

                self._slavesock = so
                self.__sockerr.clear()
                self.__flusherr = False

            # Timeout setzen
            self.set_timeout(int(self.__timeout * 1000))

            # DirtyBytes übertragen
            for pos in self.__dictdirty:
                self.set_dirtybytes(pos, self.__dictdirty[pos])

    def _direct_send(self, send_bytes, recv_count):
        """Fuer debugging direktes Senden von Daten.

        @param send_bytes Bytes, die gesendet werden sollen
        @param recv_count Anzahl der Empfangsbytes
        @returns Empfangende Bytes

        """
        if self.__sockend.is_set():
            raise ValueError("I/O operation on closed file")

        with self.__socklock:
            self._slavesock.sendall(send_bytes)
            # FIXME: Schleife bis Daten empfangen sind einbauen
            recv = self._slavesock.recv(recv_count)
            self.__trigger = True
            return recv

    def clear_dirtybytes(self, position=None):
        """Entfernt die konfigurierten Dirtybytes vom RevPi Slave.
        @param position Startposition der Dirtybytes"""
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
            raise ValueError("I/O operation on closed file")

        error = False
        try:
            self.__socklock.acquire()

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

                # ACL prüfen und ggf Fehler werfen
                self.__check_acl(check)

                raise IOError("clear dirtybytes error on network")
        except AclException:
            raise
        except Exception:
            error = True
        finally:
            self.__socklock.release()

        # Daten immer übernehmen
        if position is None:
            self.__dictdirty = {}
        elif position in self.__dictdirty:
            del self.__dictdirty[position]

        if error:
            # Fehler nach übernahme der Daten auslösen um diese zu setzen
            self.__sockerr.set()

        self.__trigger = True

    def close(self):
        """Verbindung trennen."""
        if self.__sockend.is_set():
            return

        self.__sockend.set()
        self.__sockerr.set()

        # Vom Socket sauber trennen
        if self._slavesock is not None:
            try:
                self.__socklock.acquire()
                self._slavesock.send(_sysexit)

                # NOTE: Wird das benötigt?
                self._slavesock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            finally:
                self.__socklock.release()

            self._slavesock.close()

    def flush(self):
        """Schreibpuffer senden."""
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
            raise ValueError("flush of closed file")

        with self.__socklock:
            self._slavesock.sendall(
                self.__by_buff + _sysflush
            )

            # Rückmeldebyte auswerten
            blockok = self._slavesock.recv(1)

            # Puffer immer leeren
            self.__int_buff = 0
            self.__by_buff = b''

            if blockok != b'\x1e':

                # ACL prüfen und ggf Fehler werfen
                self.__check_acl(blockok)

                self.__flusherr = True
                self.__sockerr.set()
                raise IOError("flush error on network")
            else:
                self.__flusherr = False

            self.__trigger = True

    def get_closed(self):
        """Pruefen ob Verbindung geschlossen ist.
        @return True, wenn Verbindung geschlossen ist"""
        return self.__sockend.is_set()

    def get_config_changed(self):
        """Pruefen ob RevPi Konfiguration geaendert wurde.
        @return True, wenn RevPi Konfiguration geaendert ist"""
        return self.__config_changed

    def get_name(self):
        """Verbindugnsnamen zurueckgeben.
        @return <class 'str'> IP:PORT"""
        return "{0}:{1}".format(*self._address)

    def get_reconnecting(self):
        """Interner reconnect aktiv wegen Netzwerkfehlern.
        @return True, wenn reconnect aktiv"""
        return self.__sockerr.is_set()

    def get_timeout(self):
        """Gibt aktuellen Timeout zurueck.
        @return <class 'int'> in Millisekunden"""
        return int(self.__timeout * 1000)

    def ioctl(self, request, arg=b''):
        """IOCTL Befehle ueber das Netzwerk senden.
        @param request Request as <class 'int'>
        @param arg Argument as <class 'byte'>"""
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
            raise ValueError("read of closed file")

        if not (isinstance(arg, bytes) and len(arg) <= 1024):
            raise TypeError("arg must be <class 'bytes'>")

        with self.__socklock:
            self._slavesock.send(
                b'\x01IC' +
                request.to_bytes(length=4, byteorder="little") +
                len(arg).to_bytes(length=2, byteorder="little") +
                b'\x00\x00\x00\x00\x00\x00\x17'
            )
            self._slavesock.sendall(arg)

            # Rückmeldebyte auswerten
            check = self._slavesock.recv(1)
            if check != b'\x1e':

                # ACL prüfen und ggf Fehler werfen
                self.__check_acl(check)

                self.__sockerr.set()
                raise IOError("ioctl error on network")

            self.__trigger = True

    def read(self, length):
        """Daten ueber das Netzwerk lesen.
        @param length Anzahl der Bytes
        @return Gelesene <class 'bytes'>"""
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
            raise ValueError("read of closed file")

        with self.__socklock:
            self._slavesock.send(
                b'\x01DA' +
                self.__position.to_bytes(length=2, byteorder="little") +
                length.to_bytes(length=2, byteorder="little") +
                b'\x00\x00\x00\x00\x00\x00\x00\x00\x17'
            )

            bytesbuff = bytearray()
            while not self.__sockend.is_set() and len(bytesbuff) < length:
                rbytes = self._slavesock.recv(256)

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
        if self.__sockend.is_set():
            raise ValueError("read of closed file")

        if self.__pictory_h == HASH_FAIL:
            raise RuntimeError(
                "could not read/parse piCtory configuration over network"
            )

        with self.__socklock:
            self._slavesock.send(_syspictory)

            byte_buff = bytearray()
            zero_byte = 0
            while not self.__sockend.is_set() and zero_byte < 100:
                data = self._slavesock.recv(128)
                if data == b'':
                    zero_byte += 1

                byte_buff += data
                if data.find(b'\x04') >= 0:
                    self.__trigger = True

                    # NOTE: Nur suchen oder Ende prüfen?
                    return bytes(byte_buff[:-1])

            self.__sockerr.set()
            raise IOError("readpictory error on network")

    def readreplaceio(self):
        """Ruft die replace_io Konfiguration ab.
        @return <class 'bytes'> replace_io_file"""
        if self.__sockend.is_set():
            raise ValueError("read of closed file")

        if self.__replace_ios_h == HASH_FAIL:
            raise RuntimeError(
                "replace_io_file: could not read/parse over network"
            )

        with self.__socklock:
            self._slavesock.send(_sysreplaceio)

            byte_buff = bytearray()
            zero_byte = 0
            while not self.__sockend.is_set() and zero_byte < 100:
                data = self._slavesock.recv(128)
                if data == b'':
                    zero_byte += 1

                byte_buff += data
                if data.find(b'\x04') >= 0:
                    self.__trigger = True

                    # NOTE: Nur suchen oder Ende prüfen?
                    return bytes(byte_buff[:-1])

            self.__sockerr.set()
            raise IOError("readreplaceio error on network")

    def run(self):
        """Handler fuer Synchronisierung."""
        state_reconnect = False
        while not self.__sockend.is_set():

            # Bei Fehlermeldung neu verbinden
            if self.__sockerr.is_set():
                if not state_reconnect:
                    state_reconnect = True
                    warnings.warn(
                        "got a network error and try to reconnect",
                        RuntimeWarning
                    )
                self._connect()
                if self.__sockerr.is_set():
                    # Verhindert bei Scheitern 100% CPU last
                    self.__sockend.wait(self.__waitsync)
                else:
                    state_reconnect = False
                    warnings.warn(
                        "successfully reconnected after network error",
                        RuntimeWarning
                    )

            # Kein Fehler aufgetreten, sync durchführen wenn socket frei
            if not self.__trigger and \
                    self.__socklock.acquire(blocking=False):
                try:
                    self._slavesock.send(_syssync)
                    data = self._slavesock.recv(2)
                except IOError:
                    self.__sockerr.set()
                else:
                    if data != b'\x06\x16':
                        warnings.warn(
                            "data error on network sync",
                            RuntimeWarning
                        )
                        self.__sockerr.set()

                self.__socklock.release()

            self.__trigger = False

            # Warten nach Sync damit Instantiierung funktioniert
            self.__sockerr.wait(self.__waitsync)

    def seek(self, position):
        """Springt an angegebene Position.
        @param position An diese Position springen"""
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
            raise ValueError("seek of closed file")
        self.__position = int(position)

    def set_dirtybytes(self, position, dirtybytes):
        """Konfiguriert Dirtybytes fuer Prozessabbild bei Verbindungsfehler.
        @param positon Startposition zum Schreiben
        @param dirtybytes <class 'bytes'> die geschrieben werden sollen"""
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
            raise ValueError("I/O operation on closed file")

        error = False
        try:
            self.__socklock.acquire()

            self._slavesock.sendall(
                b'\x01EY' +
                position.to_bytes(length=2, byteorder="little") +
                len(dirtybytes).to_bytes(length=2, byteorder="little") +
                b'\x00\x00\x00\x00\x00\x00\x00\x00\x17' +
                dirtybytes
            )

            check = self._slavesock.recv(1)
            if check != b'\x1e':

                # ACL prüfen und ggf Fehler werfen
                self.__check_acl(check)

                raise IOError("set dirtybytes error on network")
        except AclException:
            raise
        except Exception:
            error = True
        finally:
            self.__socklock.release()

        # Daten immer übernehmen
        self.__dictdirty[position] = dirtybytes

        if error:
            # Fehler nach übernahme der Daten auslösen um diese zu setzen
            self.__sockerr.set()

        self.__trigger = True

    def set_timeout(self, value):
        """Setzt Timeoutwert fuer Verbindung.
        @param value Timeout in Millisekunden"""
        if self.__sockend.is_set():
            raise ValueError("I/O operation on closed file")

        # Timeoutwert verarbeiten (könnte Exception auslösen)
        self.__set_systimeout(value)

        try:
            self.__socklock.acquire()

            self._slavesock.send(
                b'\x01CF' +
                value.to_bytes(length=2, byteorder="little") +
                b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x17'
            )
            check = self._slavesock.recv(1)
            if check != b'\x1e':
                raise IOError("set timeout error on network")
        except Exception:
            self.__sockerr.set()
        finally:
            self.__socklock.release()

        self.__trigger = True

    def tell(self):
        """Gibt aktuelle Position zurueck.
        @return int aktuelle Position"""
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
            raise ValueError("I/O operation on closed file")
        return self.__position

    def write(self, bytebuff):
        """Daten ueber das Netzwerk schreiben.
        @param bytebuff Bytes zum schreiben
        @return <class 'int'> Anzahl geschriebener bytes"""
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
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
    config_changed = property(get_config_changed)
    name = property(get_name)
    reconnecting = property(get_reconnecting)
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

    __slots__ = "_address"

    def __init__(
            self, address, autorefresh=False, monitoring=False,
            syncoutputs=True, simulator=False, debug=True,
            replace_io_file=None, direct_output=False):
        """Instantiiert die Grundfunktionen.

        @param address: IP-Adresse <class 'str'> / (IP, Port) <class 'tuple'>
        @param autorefresh Wenn True, alle Devices zu autorefresh hinzufuegen
        @param monitoring In- und Outputs werden gelesen, niemals geschrieben
        @param syncoutputs Aktuell gesetzte Outputs vom Prozessabbild einlesen
        @param simulator Laedt das Modul als Simulator und vertauscht IOs
        @param debug Gibt bei allen Fehlern komplette Meldungen aus
        @param replace_io_file Replace IO Konfiguration aus Datei laden
        @param direct_output Write outputs immediately to process image (slow)

        """
        check_ip = compile(
            r"^(?P<ipn>(25[0-5]|(2[0-4]|[01]?\d|)\d))(\.(?P=ipn)){3}$"
        )

        # Adresse verarbeiten
        if isinstance(address, str):
            self._address = (address, 55234)
        elif isinstance(address, tuple):
            if len(address) == 2 \
                    and isinstance(address[0], str) \
                    and isinstance(address[1], int):

                # Werte prüfen
                if not 0 < address[1] <= 65535:
                    raise ValueError("port number out of range 1 - 65535")

                self._address = address
            else:
                raise TypeError(
                    "address tuple must be (<class 'str'>, <class 'int'>)"
                )
        else:
            raise TypeError(
                "parameter address must be <class 'str'> or <class 'tuple'> "
                "like (<class 'str'>, <class 'int'>)"
            )

        # IP-Adresse prüfen und ggf. auflösen
        if check_ip.match(self._address[0]) is None:
            try:
                ipv4 = socket.gethostbyname(self._address[0])
                self._address = (ipv4, self._address[1])
            except Exception:
                raise ValueError(
                    "ip '{0}' is no valid IPv4 address"
                    "".format(self._address[0])
                )

        # Vererben
        super().__init__(
            autorefresh=autorefresh,
            monitoring=monitoring,
            syncoutputs=syncoutputs,
            procimg="{0}:{1}".format(*self._address),
            configrsc=None,
            simulator=simulator,
            debug=debug,
            replace_io_file=replace_io_file,
            direct_output=direct_output,
        )

        # Netzwerkfilehandler anlegen
        self._myfh = self._create_myfh()

        # Nur Konfigurieren, wenn nicht vererbt
        if type(self) == RevPiNetIO:
            self._configure(self.get_jconfigrsc())
            self._configure_replace_io(self._get_cpreplaceio())

    def _create_myfh(self):
        """Erstellt NetworkFileObject.
        return FileObject"""
        self._buffedwrite = True
        return NetFH(self._address, self._replace_io_file == ":network:")

    def _get_cpreplaceio(self):
        """Laed die replace_io Konfiguration ueber das Netzwerk.
        @return <class 'ConfigParser'> der replace io daten"""

        # Normale Verwendung über Elternklasse erledigen
        if self._replace_io_file != ":network:":
            return super()._get_cpreplaceio()

        # Replace IO Daten über das Netzwerk beziehen
        byte_buff = self._myfh.readreplaceio()

        cp = ConfigParser()
        try:
            cp.read_string(byte_buff.decode("utf-8"))
        except Exception as e:
            raise RuntimeError(
                "replace_io_file: could not read/parse network data | {0}"
                "".format(e)
            )
        return cp

    def disconnect(self):
        """Trennt Verbindungen und beendet autorefresh inkl. alle Threads."""
        self.cleanup()

    def exit(self, full=True):
        """Beendet mainloop() und optional autorefresh.
        @see #RevPiModIO.exit(...)"""
        try:
            super().exit(full)
        except ConfigChanged:
            pass

    def get_config_changed(self):
        """Pruefen ob RevPi Konfiguration geaendert wurde.

        In diesem Fall ist die Verbindung geschlossen und RevPiNetIO muss
        neu instanziert werden.

        @return True, wenn RevPi Konfiguration geaendert ist"""
        return self._myfh.config_changed

    def get_jconfigrsc(self):
        """Laedt die piCotry Konfiguration und erstellt ein <class 'dict'>.
        @return <class 'dict'> der piCtory Konfiguration"""
        mynh = NetFH(self._address, False)
        byte_buff = mynh.readpictory()
        mynh.close()
        return jloads(byte_buff.decode("utf-8"))

    def get_reconnecting(self):
        """Interner reconnect aktiv wegen Netzwerkfehlern.

        Das Modul versucht intern die Verbindung neu herzustellen. Es ist
        kein weiteres Zutun noetig.

        @return True, wenn reconnect aktiv"""
        return self._myfh.reconnecting

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
            dev = device if isinstance(device, Device) \
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
            dev = device if isinstance(device, Device) \
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

    config_changed = property(get_config_changed)
    reconnecting = property(get_reconnecting)


class RevPiNetIOSelected(RevPiNetIO):

    """Klasse fuer die Verwaltung einzelner Devices aus piCtory.

    Diese Klasse uebernimmt nur angegebene Devices der piCtory Konfiguration
    und bilded sie inkl. IOs ab. Sie uebernimmt die exklusive Verwaltung des
    Adressbereichs im Prozessabbild an dem sich die angegebenen Devices
    befinden und stellt sicher, dass die Daten synchron sind.

    """

    __slots__ = ()

    def __init__(
            self, address, deviceselection, autorefresh=False,
            monitoring=False, syncoutputs=True, simulator=False, debug=True,
            replace_io_file=None, direct_output=False):
        """Instantiiert nur fuer angegebene Devices die Grundfunktionen.

        Der Parameter deviceselection kann eine einzelne
        Device Position / einzelner Device Name sein oder eine Liste mit
        mehreren Positionen / Namen

        @param address: IP-Adresse <class 'str'> / (IP, Port) <class 'tuple'>
        @param deviceselection Positionsnummer oder Devicename
        @see #RevPiNetIO.__init__ RevPiNetIO.__init__(...)

        """
        super().__init__(
            address, autorefresh, monitoring, syncoutputs, simulator, debug,
            replace_io_file, direct_output
        )

        # Device liste erstellen
        if type(deviceselection) == list:
            for dev in deviceselection:
                self._lst_devselect.append(dev)
        else:
            self._lst_devselect.append(deviceselection)

        for vdev in self._lst_devselect:
            if type(vdev) != int and type(vdev) != str:
                raise TypeError(
                    "need device position as <class 'int'> or device name as "
                    "<class 'str'>"
                )

        self._configure(self.get_jconfigrsc())
        self._configure_replace_io(self._get_cpreplaceio())

        if len(self.device) == 0:
            if type(self) == RevPiNetIODriver:
                raise DeviceNotFoundError(
                    "could not find any given VIRTUAL devices in config"
                )
            else:
                raise DeviceNotFoundError(
                    "could not find any given devices in config"
                )
        elif len(self.device) != len(self._lst_devselect):
            if type(self) == RevPiNetIODriver:
                raise DeviceNotFoundError(
                    "could not find all given VIRTUAL devices in config"
                )
            else:
                raise DeviceNotFoundError(
                    "could not find all given devices in config"
                )


class RevPiNetIODriver(RevPiNetIOSelected):

    """Klasse um eigene Treiber fuer die virtuellen Devices zu erstellen.

    Mit dieser Klasse werden nur angegebene Virtuelle Devices mit RevPiModIO
    verwaltet. Bei Instantiierung werden automatisch die Inputs und Outputs
    verdreht, um das Schreiben der Inputs zu ermoeglichen. Die Daten koennen
    dann ueber logiCAD an den Devices abgerufen werden.

    """

    __slots__ = ()

    def __init__(
            self, address, virtdev, autorefresh=False, monitoring=False,
            syncoutputs=True, debug=True, replace_io_file=None,
            direct_output=False):
        """Instantiiert die Grundfunktionen.

        Parameter 'monitoring' und 'simulator' stehen hier nicht zur
        Verfuegung, da diese automatisch gesetzt werden.

        @param address: IP-Adresse <class 'str'> / (IP, Port) <class 'tuple'>
        @param virtdev Virtuelles Device oder mehrere als <class 'list'>
        @see #RevPiModIO.__init__ RevPiModIO.__init__(...)

        """
        # Parent mit monitoring=False und simulator=True laden
        super().__init__(
            address, virtdev, autorefresh, False, syncoutputs, True, debug,
            replace_io_file, direct_output
        )

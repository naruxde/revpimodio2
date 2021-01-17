# -*- coding: utf-8 -*-
"""RevPiModIO Hauptklasse fuer Netzwerkzugriff."""
import socket
import warnings
from configparser import ConfigParser
from json import loads as jloads
from re import compile
from struct import pack, unpack
from threading import Event, Lock, Thread

from revpimodio2 import DeviceNotFoundError
from .device import Device
from .modio import RevPiModIO as _RevPiModIO

__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2020 Sven Sager"
__license__ = "LGPLv3"

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
# Hashvalues
HASH_FAIL = b'\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff'
# Header start/stop
HEADER_START = b'\x01'
HEADER_STOP = b'\x17'


class AclException(Exception):
    """Probleme mit Berechtigungen."""

    pass


class ConfigChanged(Exception):
    """Aenderung der piCtory oder replace_ios Datei."""

    pass


class NetFH(Thread):
    """
    Netzwerk File Handler fuer das Prozessabbild.

    Dieses FileObject-like Object verwaltet das Lesen und Schriben des
    Prozessabbilds ueber das Netzwerk. Ein entfernter Revolution Pi kann
    so gesteuert werden.
    """

    __slots__ = "__buff_size", "__buff_block", "__buff_recv", \
                "__by_buff", "__check_replace_ios", "__config_changed", \
                "__int_buff", "__dictdirty", "__flusherr", "__replace_ios_h", \
                "__pictory_h", "__position", "__sockerr", "__sockend", \
                "__socklock", "__timeout", "__waitsync", "_address", \
                "_slavesock", "daemon"

    def __init__(self, address: tuple, check_replace_ios: bool, timeout=500):
        """
        Init NetFH-class.

        :param address: IP Adresse, Port des RevPi als <class 'tuple'>
        :param check_replace_ios: Prueft auf Veraenderungen der Datei
        :param timeout: Timeout in Millisekunden der Verbindung
        """
        super().__init__()
        self.daemon = True

        self.__buff_size = 2048  # Values up to 32 are static in code!
        self.__buff_block = bytearray(self.__buff_size)
        self.__buff_recv = bytearray()
        self.__by_buff = bytearray()
        self.__check_replace_ios = check_replace_ios
        self.__config_changed = False
        self.__int_buff = 0
        self.__dictdirty = {}
        self.__replace_ios_h = b''
        self.__pictory_h = b''
        self.__sockerr = Event()
        self.__sockend = Event()
        self.__socklock = Lock()
        self.__timeout = None
        self.__waitsync = None
        self._address = address
        self._slavesock = None  # type: socket.socket

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

    def __check_acl(self, bytecode: bytes) -> None:
        """
        Pueft ob ACL auf RevPi den Vorgang erlaubt.

        Ist der Vorgang nicht zulässig, wird der Socket sofort geschlossen
        und eine Exception geworfen.

        :param bytecode: Antwort, die geprueft werden solll
        """
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

    def __set_systimeout(self, value: int) -> None:
        """
        Systemfunktion fuer Timeoutberechnung.

        :param value: Timeout in Millisekunden 100 - 60000
        """
        if isinstance(value, int) and (100 <= value <= 60000):
            self.__timeout = value / 1000

            # Timeouts in Socket setzen
            if self._slavesock is not None:
                self._slavesock.settimeout(self.__timeout)

            # 45 Prozent vom Timeout für Synctimer verwenden
            self.__waitsync = self.__timeout / 100 * 45

        else:
            raise ValueError("value must between 10 and 60000 milliseconds")

    def _connect(self) -> None:
        """Stellt die Verbindung zu einem RevPiSlave her."""
        # Neuen Socket aufbauen
        so = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            so.connect(self._address)
            so.settimeout(self.__timeout)

            # Hashwerte anfordern
            recv_len = 16
            so.sendall(_syspictoryh)
            if self.__check_replace_ios:
                so.sendall(_sysreplaceioh)
                recv_len += 16

            # Hashwerte empfangen mit eigenen Puffern, da nicht gelocked
            buff_recv = bytearray(recv_len)
            while recv_len > 0:
                block = so.recv(recv_len)
                if block == b'':
                    raise OSError("lost connection on hash receive")
                buff_recv += block
                recv_len -= len(block)

            # Änderung an piCtory prüfen
            if self.__pictory_h and buff_recv[:16] != self.__pictory_h:
                self.__config_changed = True
                self.close()
                raise ConfigChanged(
                    "configuration on revolution pi was changed")
            else:
                self.__pictory_h = buff_recv[:16]

            # Änderung an replace_ios prüfen
            if self.__check_replace_ios and self.__replace_ios_h \
                    and buff_recv[16:] != self.__replace_ios_h:
                self.__config_changed = True
                self.close()
                raise ConfigChanged(
                    "configuration on revolution pi was changed")
            else:
                self.__replace_ios_h = buff_recv[16:]
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

            # Timeout setzen
            self.set_timeout(int(self.__timeout * 1000))

            # DirtyBytes übertragen
            for pos in self.__dictdirty:
                self.set_dirtybytes(pos, self.__dictdirty[pos])

    def _direct_sr(self, send_bytes: bytes, recv_len: int) -> bytes:
        """
        Secure send and receive function for network handler.

        Will raise exception on closed network handler or network errors and
        set the sockerr flag.

        :param send_bytes: Bytes to send or empty
        :param recv_len: Amount of bytes to receive
        :return: Received bytes
        """
        if self.__sockend.is_set():
            raise ValueError("I/O operation on closed file")
        if self.__sockerr.is_set():
            raise IOError("not allowed while reconnect")

        try:
            self.__socklock.acquire()

            counter = 0
            send_len = len(send_bytes)
            while counter < send_len:
                # Send loop to trigger timeout of socket on each send
                sent = self._slavesock.send(send_bytes[counter:])
                if sent == 0:
                    self.__sockerr.set()
                    raise IOError("lost network connection while send")
                counter += sent

            self.__buff_recv.clear()
            while recv_len > 0:
                count = self._slavesock.recv_into(
                    self.__buff_block, min(recv_len, self.__buff_size)
                )
                if count == 0:
                    raise IOError("lost network connection while receive")
                self.__buff_recv += self.__buff_block[:count]
                recv_len -= count

            # Create copy in socklock environment
            return_buffer = bytes(self.__buff_recv)
        except Exception:
            self.__sockerr.set()
            raise

        finally:
            self.__socklock.release()

        return return_buffer

    def clear_dirtybytes(self, position=None) -> None:
        """
        Entfernt die konfigurierten Dirtybytes vom RevPi Slave.

        Diese Funktion wirft keine Exception bei einem uebertragungsfehler,
        veranlasst aber eine Neuverbindung.

        :param position: Startposition der Dirtybytes
        """
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
            raise ValueError("I/O operation on closed file")

        # Daten immer übernehmen
        if position is None:
            self.__dictdirty.clear()
        elif position in self.__dictdirty:
            del self.__dictdirty[position]

        try:
            if position is None:
                # Alle Dirtybytes löschen
                buff = self._direct_sr(_sysdeldirty, 1)
            else:
                # Nur bestimmte Dirtybytes löschen
                # b CM ii xx c0000000 b = 16
                buff = self._direct_sr(pack(
                    "=c2sH2xc7xc",
                    HEADER_START, b'EY', position, b'\xfe', HEADER_STOP
                ), 1)
            if buff != b'\x1e':
                # ACL prüfen und ggf Fehler werfen
                self.__check_acl(buff)

                raise IOError("clear dirtybytes error on network")
        except AclException:
            self.__dictdirty.clear()
            raise
        except Exception:
            self.__sockerr.set()

    def close(self) -> None:
        """Verbindung trennen."""
        if self.__sockend.is_set():
            return

        self.__sockend.set()
        self.__sockerr.set()

        # Vom Socket sauber trennen
        if self._slavesock is not None:
            try:
                self.__socklock.acquire()
                self._slavesock.sendall(_sysexit)
                self._slavesock.shutdown(socket.SHUT_WR)
            except Exception:
                pass
            finally:
                self.__socklock.release()

            self._slavesock.close()

    def flush(self) -> None:
        """Schreibpuffer senden."""
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
            raise ValueError("flush of closed file")

        if self.__int_buff == 0:
            return

        try:
            # b CM ii ii 00000000 b = 16
            buff = self._direct_sr(pack(
                "=c2sHH8xc",
                HEADER_START, b'FD', self.__int_buff, len(self.__by_buff), HEADER_STOP
            ) + self.__by_buff, 1)
        except Exception:
            raise
        finally:
            # Puffer immer leeren
            self.__int_buff = 0
            self.__by_buff.clear()

        if buff != b'\x1e':
            # ACL prüfen und ggf Fehler werfen
            self.__check_acl(buff)

            self.__sockerr.set()
            raise IOError("flush error on network")

    def get_closed(self) -> bool:
        """
        Pruefen ob Verbindung geschlossen ist.

        :return: True, wenn Verbindung geschlossen ist
        """
        return self.__sockend.is_set()

    def get_config_changed(self) -> bool:
        """
        Pruefen ob RevPi Konfiguration geaendert wurde.

        :return: True, wenn RevPi Konfiguration geaendert ist
        """
        return self.__config_changed

    def get_name(self) -> str:
        """
        Verbindugnsnamen zurueckgeben.

        :return: <class 'str'> IP:PORT
        """
        return "{0}:{1}".format(*self._address)

    def get_reconnecting(self) -> bool:
        """
        Interner reconnect aktiv wegen Netzwerkfehlern.

        :return: True, wenn reconnect aktiv
        """
        return self.__sockerr.is_set()

    def get_timeout(self) -> int:
        """
        Gibt aktuellen Timeout zurueck.

        :return: <class 'int'> in Millisekunden
        """
        return int(self.__timeout * 1000)

    def ioctl(self, request: int, arg=b'') -> None:
        """
        IOCTL Befehle ueber das Netzwerk senden.

        :param request: Request as <class 'int'>
        :param arg: Argument as <class 'byte'>
        """
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
            raise ValueError("read of closed file")

        if not (isinstance(arg, bytes) and len(arg) <= 1024):
            raise TypeError("arg must be <class 'bytes'>")

        # b CM xx ii iiii0000 b = 16
        buff = self._direct_sr(pack(
            "=c2s2xHI4xc",
            HEADER_START, b'IC', len(arg), request, HEADER_STOP
        ) + arg, 1)
        if buff != b'\x1e':
            # ACL prüfen und ggf Fehler werfen
            self.__check_acl(buff)

            self.__sockerr.set()
            raise IOError("ioctl error on network")

    def read(self, length: int) -> bytes:
        """
        Daten ueber das Netzwerk lesen.

        :param length: Anzahl der Bytes
        :return: Gelesene <class 'bytes'>
        """
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
            raise ValueError("read of closed file")

        # b CM ii ii 00000000 b = 16
        buff = self._direct_sr(pack(
            "=c2sHH8xc",
            HEADER_START, b'DA', self.__position, length, HEADER_STOP
        ), length)

        self.__position += length
        return buff

    def readinto(self, buffer: bytearray) -> int:
        """
        Read data from network into a buffer.

        :param buffer: Use Buffer to write bytes into
        :return: Amount of read bytes
        """
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
            raise ValueError("read of closed file")

        length = len(buffer)

        # b CM ii ii 00000000 b = 16
        buff = self._direct_sr(pack(
            "=c2sHH8xc",
            HEADER_START, b'DA', self.__position, length, HEADER_STOP
        ), length)

        buffer[:] = buff
        return len(buffer)

    def readpictory(self) -> bytes:
        """
        Ruft die piCtory Konfiguration ab.

        :return: <class 'bytes'> piCtory Datei
        """
        if self.__sockend.is_set():
            raise ValueError("read of closed file")

        if self.__pictory_h == HASH_FAIL:
            raise RuntimeError(
                "could not read/parse piCtory configuration over network"
            )

        buff = self._direct_sr(_syspictory, 4)
        recv_length, = unpack("=I", buff)
        return self._direct_sr(b'', recv_length)

    def readreplaceio(self) -> bytes:
        """
        Ruft die replace_io Konfiguration ab.

        :return: <class 'bytes'> replace_io_file
        """
        if self.__sockend.is_set():
            raise ValueError("read of closed file")

        if self.__replace_ios_h == HASH_FAIL:
            raise RuntimeError(
                "replace_io_file: could not read/parse over network"
            )

        buff = self._direct_sr(_sysreplaceio, 4)
        recv_length, = unpack("=I", buff)
        return self._direct_sr(b'', recv_length)

    def run(self) -> None:
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
                    # Verhindert beim Scheitern 100% CPU last
                    self.__sockend.wait(self.__waitsync)
                    continue
                else:
                    state_reconnect = False
                    warnings.warn(
                        "successfully reconnected after network error",
                        RuntimeWarning
                    )

            # Kein Fehler aufgetreten, sync durchführen wenn socket frei
            if self.__socklock.acquire(blocking=False):
                try:
                    self._slavesock.sendall(_syssync)

                    self.__buff_recv.clear()
                    recv_lenght = 2
                    while recv_lenght > 0:
                        count = self._slavesock.recv_into(
                            self.__buff_block, recv_lenght
                        )
                        if count == 0:
                            raise IOError("lost network connection on sync")
                        self.__buff_recv += self.__buff_block[:count]
                        recv_lenght -= count

                except IOError:
                    self.__sockerr.set()
                else:
                    if self.__buff_recv != b'\x06\x16':
                        warnings.warn(
                            "data error on network sync",
                            RuntimeWarning
                        )
                        self.__sockerr.set()
                        continue
                finally:
                    self.__socklock.release()

            # Warten nach Sync damit Instantiierung funktioniert
            self.__sockerr.wait(self.__waitsync)

    def seek(self, position: int) -> None:
        """Springt an angegebene Position.
        @param position An diese Position springen"""
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
            raise ValueError("seek of closed file")
        self.__position = int(position)

    def set_dirtybytes(self, position: int, dirtybytes: bytes) -> None:
        """
        Konfiguriert Dirtybytes fuer Prozessabbild bei Verbindungsfehler.

        Diese Funktion wirft keine Exception bei einem uebertragungsfehler,
        veranlasst aber eine Neuverbindung.

        :param position: Startposition zum Schreiben
        :param dirtybytes: <class 'bytes'> die geschrieben werden sollen
        """
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
            raise ValueError("I/O operation on closed file")

        # Daten immer übernehmen
        self.__dictdirty[position] = dirtybytes

        try:
            # b CM ii ii 00000000 b = 16
            buff = self._direct_sr(pack(
                "=c2sHH8xc",
                HEADER_START, b'EY', position, len(dirtybytes), HEADER_STOP
            ) + dirtybytes, 1)

            if buff != b'\x1e':
                # ACL prüfen und ggf Fehler werfen
                self.__check_acl(buff)

                raise IOError("set dirtybytes error on network")
        except AclException:
            # Not allowed, clear for reconnect
            self.__dictdirty.clear()
            raise
        except Exception:
            self.__sockerr.set()

    def set_timeout(self, value: int) -> None:
        """
        Setzt Timeoutwert fuer Verbindung.

        :param value: Timeout in Millisekunden
        """
        if self.__sockend.is_set():
            raise ValueError("I/O operation on closed file")

        # Timeoutwert verarbeiten (könnte Exception auslösen)
        self.__set_systimeout(value)

        try:
            # b CM ii xx 00000000 b = 16
            buff = self._direct_sr(pack(
                "=c2sH10xc",
                HEADER_START, b'CF', value, HEADER_STOP
            ), 1)
            if buff != b'\x1e':
                raise IOError("set timeout error on network")
        except Exception:
            self.__sockerr.set()

    def tell(self) -> int:
        """
        Gibt aktuelle Position zurueck.

        :return: Aktuelle Position
        """
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
            raise ValueError("I/O operation on closed file")
        return self.__position

    def write(self, bytebuff: bytes) -> int:
        """
        Daten ueber das Netzwerk schreiben.

        :param bytebuff: Bytes zum schreiben
        :return: <class 'int'> Anzahl geschriebener bytes
        """
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
            raise ValueError("write to closed file")
        if self.__sockerr.is_set():
            raise IOError("not allowed while reconnect")

        with self.__socklock:
            self.__int_buff += 1

            # Datenblock mit Position und Länge in Puffer ablegen
            self.__by_buff += self.__position.to_bytes(length=2, byteorder="little") + \
                len(bytebuff).to_bytes(length=2, byteorder="little") + \
                bytebuff

        # TODO: Bufferlänge und dann flushen?

        return len(bytebuff)

    closed = property(get_closed)
    config_changed = property(get_config_changed)
    name = property(get_name)
    reconnecting = property(get_reconnecting)
    timeout = property(get_timeout, set_timeout)


class RevPiNetIO(_RevPiModIO):
    """
    Klasse fuer die Verwaltung der piCtory Konfiguration ueber das Netzwerk.

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
            replace_io_file=None, shared_procimg=False, direct_output=False):
        """
        Instantiiert die Grundfunktionen.

        :param address: IP-Adresse <class 'str'> / (IP, Port) <class 'tuple'>
        :param autorefresh: Wenn True, alle Devices zu autorefresh hinzufuegen
        :param monitoring: In- und Outputs werden gelesen, niemals geschrieben
        :param syncoutputs: Aktuell gesetzte Outputs vom Prozessabbild einlesen
        :param simulator: Laedt das Modul als Simulator und vertauscht IOs
        :param debug: Gibt bei allen Fehlern komplette Meldungen aus
        :param replace_io_file: Replace IO Konfiguration aus Datei laden
        :param shared_procimg: Share process image with other processes (insecure for automation, little slower)
        :param direct_output: Deprecated, use shared_procimg
        """
        check_ip = compile(
            r"^(25[0-5]|(2[0-4]|[01]?\d|)\d)(\.(25[0-5]|(2[0-4]|[01]?\d|)\d)){3}$"
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
                    "can not resolve ip address for hostname '{0}'"
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
            shared_procimg=shared_procimg,
            direct_output=direct_output,
        )

        # Netzwerkfilehandler anlegen
        self._myfh = self._create_myfh()

        # Nur Konfigurieren, wenn nicht vererbt
        if type(self) == RevPiNetIO:
            self._configure(self.get_jconfigrsc())
            self._configure_replace_io(self._get_cpreplaceio())

    def _create_myfh(self):
        """
        Erstellt NetworkFileObject.

        :return: FileObject
        """
        self._buffedwrite = True
        return NetFH(self._address, self._replace_io_file == ":network:")

    def _get_cpreplaceio(self) -> ConfigParser:
        """
        Laed die replace_io Konfiguration ueber das Netzwerk.

        :return: <class 'ConfigParser'> der replace io daten
        """
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

    def disconnect(self) -> None:
        """Trennt Verbindungen und beendet autorefresh inkl. alle Threads."""
        self.cleanup()

    def exit(self, full=True) -> None:
        """
        Beendet mainloop() und optional autorefresh.

        :ref: :func:`RevPiModIO.exit()`
        """
        try:
            super().exit(full)
        except ConfigChanged:
            pass

    def get_config_changed(self) -> bool:
        """
        Pruefen ob RevPi Konfiguration geaendert wurde.

        In diesem Fall ist die Verbindung geschlossen und RevPiNetIO muss
        neu instanziert werden.

        :return: True, wenn RevPi Konfiguration geaendert ist
        """
        return self._myfh.config_changed

    def get_jconfigrsc(self) -> dict:
        """
        Laedt die piCotry Konfiguration und erstellt ein <class 'dict'>.

        :return: <class 'dict'> der piCtory Konfiguration
        """
        mynh = NetFH(self._address, False)
        byte_buff = mynh.readpictory()
        mynh.close()
        return jloads(byte_buff.decode("utf-8"))

    def get_reconnecting(self) -> bool:
        """
        Interner reconnect aktiv wegen Netzwerkfehlern.

        Das Modul versucht intern die Verbindung neu herzustellen. Es ist
        kein weiteres Zutun noetig.

        :return: True, wenn reconnect aktiv
        """
        return self._myfh.reconnecting

    def net_cleardefaultvalues(self, device=None) -> None:
        """
        Loescht Defaultwerte vom PLC Slave.

        :param device: nur auf einzelnes Device anwenden, sonst auf Alle
        """
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

    def net_setdefaultvalues(self, device=None) -> None:
        """
        Konfiguriert den PLC Slave mit den piCtory Defaultwerten.

        Diese Werte werden auf dem RevPi gesetzt, wenn die Verbindung
        unerwartet (Netzwerkfehler) unterbrochen wird.

        :param device: nur auf einzelnes Device anwenden, sonst auf Alle
        """
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
    """
    Klasse fuer die Verwaltung einzelner Devices aus piCtory.

    Diese Klasse uebernimmt nur angegebene Devices der piCtory Konfiguration
    und bilded sie inkl. IOs ab. Sie uebernimmt die exklusive Verwaltung des
    Adressbereichs im Prozessabbild an dem sich die angegebenen Devices
    befinden und stellt sicher, dass die Daten synchron sind.
    """

    __slots__ = ()

    def __init__(
            self, address, deviceselection, autorefresh=False,
            monitoring=False, syncoutputs=True, simulator=False, debug=True,
            replace_io_file=None, shared_procimg=False, direct_output=False):
        """
        Instantiiert nur fuer angegebene Devices die Grundfunktionen.

        Der Parameter deviceselection kann eine einzelne
        Device Position / einzelner Device Name sein oder eine Liste mit
        mehreren Positionen / Namen

        :param address: IP-Adresse <class 'str'> / (IP, Port) <class 'tuple'>
        :param deviceselection: Positionsnummer oder Devicename
        :ref: :func:`RevPiNetIO.__init__()`
        """
        super().__init__(
            address, autorefresh, monitoring, syncoutputs, simulator, debug,
            replace_io_file, shared_procimg, direct_output
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
    """
    Klasse um eigene Treiber fuer die virtuellen Devices zu erstellen.

    Mit dieser Klasse werden nur angegebene Virtuelle Devices mit RevPiModIO
    verwaltet. Bei Instantiierung werden automatisch die Inputs und Outputs
    verdreht, um das Schreiben der Inputs zu ermoeglichen. Die Daten koennen
    dann ueber logiCAD an den Devices abgerufen werden.
    """

    __slots__ = ()

    def __init__(
            self, address, virtdev, autorefresh=False,
            syncoutputs=True, debug=True, replace_io_file=None,
            shared_procimg=False, direct_output=False):
        """
        Instantiiert die Grundfunktionen.

        Parameter 'monitoring' und 'simulator' stehen hier nicht zur
        Verfuegung, da diese automatisch gesetzt werden.

        :param address: IP-Adresse <class 'str'> / (IP, Port) <class 'tuple'>
        :param virtdev: Virtuelles Device oder mehrere als <class 'list'>
        :ref: :func:`RevPiModIO.__init__()`
        """
        # Parent mit monitoring=False und simulator=True laden
        super().__init__(
            address, virtdev, autorefresh, False, syncoutputs, True, debug,
            replace_io_file, shared_procimg, direct_output
        )

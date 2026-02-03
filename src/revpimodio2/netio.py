# -*- coding: utf-8 -*-
"""RevPiModIO main class for network access."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2023 Sven Sager"
__license__ = "LGPLv2"

import socket
import warnings
from configparser import ConfigParser
from json import loads as jloads
from re import compile
from struct import pack, unpack
from threading import Event, Lock, Thread

from .device import Device
from .errors import DeviceNotFoundError
from .modio import DevSelect, RevPiModIO as _RevPiModIO
from .pictory import DeviceType

# Synchronization command
_syssync = b"\x01\x06\x16\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x17"
# Disconnectbefehl
_sysexit = b"\x01EX\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x17"
# Remove DirtyBytes from server
_sysdeldirty = b"\x01EY\x00\x00\x00\x00\xff\x00\x00\x00\x00\x00\x00\x00\x17"
# Load piCtory configuration
_syspictory = b"\x01PI\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x17"
_syspictoryh = b"\x01PH\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x17"
# Load ReplaceIO configuration
_sysreplaceio = b"\x01RP\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x17"
_sysreplaceioh = b"\x01RH\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x17"
# Hashvalues
HASH_FAIL = b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
# Header start/stop
HEADER_START = b"\x01"
HEADER_STOP = b"\x17"


class AclException(Exception):
    """Problems with permissions."""

    pass


class ConfigChanged(Exception):
    """Change to the piCtory or replace_ios file."""

    pass


class NetFH(Thread):
    """
        Network file handler for the process image.

    This file-object-like object manages reading and writing of the
    process image via the network. A remote Revolution Pi can be controlled this way.
    """

    __slots__ = (
        "__buff_size",
        "__buff_block",
        "__buff_recv",
        "__by_buff",
        "__check_replace_ios",
        "__config_changed",
        "__int_buff",
        "__dictdirty",
        "__flusherr",
        "__replace_ios_h",
        "__pictory_h",
        "__position",
        "__sockerr",
        "__sockend",
        "__socklock",
        "__timeout",
        "__waitsync",
        "_address",
        "_serversock",
        "daemon",
    )

    def __init__(self, address: tuple, check_replace_ios: bool, timeout=500):
        """
        Init NetFH-class.

        :param address: IP address, port of the RevPi as <class 'tuple'>
        :param check_replace_ios: Checks for changes to the file
        :param timeout: Timeout in milliseconds for the connection
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
        self.__replace_ios_h = b""
        self.__pictory_h = b""
        self.__sockerr = Event()
        self.__sockend = Event()
        self.__socklock = Lock()
        self.__timeout = None
        self.__waitsync = None
        self._address = address
        self._serversock = None  # type: socket.socket

        # Parameter validation
        if not isinstance(address, tuple):
            raise TypeError("parameter address must be <class 'tuple'> ('IP', PORT)")
        if not isinstance(timeout, int):
            raise TypeError("parameter timeout must be <class 'int'>")

        # Establish connection
        self.__set_systimeout(timeout)
        self._connect()

        if self._serversock is None:
            raise FileNotFoundError("can not connect to revpi server")

        # Configure NetFH
        self.__position = 0
        self.start()

    def __del__(self):
        """Terminate NetworkFileHandler."""
        self.close()

    def __check_acl(self, bytecode: bytes) -> None:
        """
                Checks if ACL allows the operation on RevPi.

        If the operation is not permitted, the socket is immediately closed
        and an exception is thrown.

        :param bytecode: Response to be checked
        """
        if bytecode == b"\x18":
            # Terminate everything if not permitted
            self.__sockend.set()
            self.__sockerr.set()
            self._serversock.close()
            raise AclException(
                "write access to the process image is not permitted - use "
                "monitoring=True or check aclplcserver.conf on RevPi and "
                "reload revpipyload!"
            )

    def __set_systimeout(self, value: int) -> None:
        """
                System function for timeout calculation.

        :param value: Timeout in milliseconds 100 - 60000
        """
        if isinstance(value, int) and (100 <= value <= 60000):
            self.__timeout = value / 1000

            # Set timeouts in socket
            if self._serversock is not None:
                self._serversock.settimeout(self.__timeout)

            # Use 45 percent of timeout for sync timer
            self.__waitsync = self.__timeout / 100 * 45

        else:
            raise ValueError("value must between 10 and 60000 milliseconds")

    def _connect(self) -> None:
        """Establishes the connection to a RevPiPlcServer."""
        # Build new socket
        so = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            so.connect(self._address)
            so.settimeout(self.__timeout)

            # Request hash values
            recv_len = 16
            so.sendall(_syspictoryh)
            if self.__check_replace_ios:
                so.sendall(_sysreplaceioh)
                recv_len += 16

            # Receive hash values with own buffers, as not locked
            buff_recv = bytearray(recv_len)
            while recv_len > 0:
                block = so.recv(recv_len)
                if block == b"":
                    raise OSError("lost connection on hash receive")
                buff_recv += block
                recv_len -= len(block)

            # Check for changes to piCtory
            if self.__pictory_h and buff_recv[:16] != self.__pictory_h:
                self.__config_changed = True
                self.close()
                raise ConfigChanged("configuration on revolution pi was changed")
            else:
                self.__pictory_h = buff_recv[:16]

            # Check for changes to replace_ios
            if (
                self.__check_replace_ios
                and self.__replace_ios_h
                and buff_recv[16:] != self.__replace_ios_h
            ):
                self.__config_changed = True
                self.close()
                raise ConfigChanged("configuration on revolution pi was changed")
            else:
                self.__replace_ios_h = buff_recv[16:]
        except ConfigChanged:
            so.close()
            raise
        except Exception:
            so.close()
        else:
            # Disconnect old socket
            with self.__socklock:
                if self._serversock is not None:
                    self._serversock.close()

                self._serversock = so
                self.__sockerr.clear()

            # Set timeout
            self.set_timeout(int(self.__timeout * 1000))

            # Transfer dirty bytes
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
                sent = self._serversock.send(send_bytes[counter:])
                if sent == 0:
                    self.__sockerr.set()
                    raise IOError("lost network connection while send")
                counter += sent

            self.__buff_recv.clear()
            while recv_len > 0:
                count = self._serversock.recv_into(
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
                Removes the configured dirty bytes from the RevPi server.

        This function does not throw an exception on transmission error,
        but triggers a reconnection.

        :param position: Start position of the dirty bytes
        """
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
            raise ValueError("I/O operation on closed file")

        # Always accept data
        if position is None:
            self.__dictdirty.clear()
        elif position in self.__dictdirty:
            del self.__dictdirty[position]

        try:
            if position is None:
                # Clear all dirty bytes
                buff = self._direct_sr(_sysdeldirty, 1)
            else:
                # Only clear specific dirty bytes
                # b CM ii xx c0000000 b = 16
                buff = self._direct_sr(
                    pack(
                        "=c2sH2xc7xc",
                        HEADER_START,
                        b"EY",
                        position,
                        b"\xfe",
                        HEADER_STOP,
                    ),
                    1,
                )
            if buff != b"\x1e":
                # Check ACL and throw error if necessary
                self.__check_acl(buff)

                raise IOError("clear dirtybytes error on network")
        except AclException:
            self.__dictdirty.clear()
            raise
        except Exception:
            self.__sockerr.set()

    def close(self) -> None:
        """Disconnect connection."""
        if self.__sockend.is_set():
            return

        self.__sockend.set()
        self.__sockerr.set()

        # Cleanly disconnect from socket
        if self._serversock is not None:
            try:
                self.__socklock.acquire()
                self._serversock.sendall(_sysexit)
                self._serversock.shutdown(socket.SHUT_WR)
            except Exception:
                pass
            finally:
                self.__socklock.release()

            self._serversock.close()

    def flush(self) -> None:
        """Send write buffer."""
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
            raise ValueError("flush of closed file")

        if self.__int_buff == 0:
            return

        try:
            # b CM ii ii 00000000 b = 16
            buff = self._direct_sr(
                pack(
                    "=c2sHH8xc",
                    HEADER_START,
                    b"FD",
                    self.__int_buff,
                    len(self.__by_buff),
                    HEADER_STOP,
                )
                + self.__by_buff,
                1,
            )
        except Exception:
            raise
        finally:
            # Always clear buffer
            self.__int_buff = 0
            self.__by_buff.clear()

        if buff != b"\x1e":
            # Check ACL and throw error if necessary
            self.__check_acl(buff)

            self.__sockerr.set()
            raise IOError("flush error on network")

    def get_closed(self) -> bool:
        """
                Check if connection is closed.

        :return: True if connection is closed
        """
        return self.__sockend.is_set()

    def get_config_changed(self) -> bool:
        """
                Check if RevPi configuration was changed.

        :return: True if RevPi configuration was changed
        """
        return self.__config_changed

    def get_name(self) -> str:
        """
                Return connection name.

        :return: <class 'str'> IP:PORT
        """
        return "{0}:{1}".format(*self._address)

    def get_reconnecting(self) -> bool:
        """
                Internal reconnect active due to network errors.

        :return: True if reconnect is active
        """
        return self.__sockerr.is_set()

    def get_timeout(self) -> int:
        """
                Returns current timeout.

        :return: <class 'int'> in milliseconds
        """
        return int(self.__timeout * 1000)

    def ioctl(self, request: int, arg=b"") -> None:
        """
        Send IOCTL commands via the network.

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
        buff = self._direct_sr(
            pack("=c2s2xHI4xc", HEADER_START, b"IC", len(arg), request, HEADER_STOP) + arg, 1
        )
        if buff != b"\x1e":
            # Check ACL and throw error if necessary
            self.__check_acl(buff)

            self.__sockerr.set()
            raise IOError("ioctl error on network")

    def read(self, length: int) -> bytes:
        """
                Read data via the network.

        :param length: Number of bytes
        :return: Read <class 'bytes'>
        """
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
            raise ValueError("read of closed file")

        # b CM ii ii 00000000 b = 16
        buff = self._direct_sr(
            pack("=c2sHH8xc", HEADER_START, b"DA", self.__position, length, HEADER_STOP), length
        )

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
        buff = self._direct_sr(
            pack("=c2sHH8xc", HEADER_START, b"DA", self.__position, length, HEADER_STOP), length
        )

        buffer[:] = buff
        return len(buffer)

    def readpictory(self) -> bytes:
        """
        Retrieves the piCtory configuration.

        :return: <class 'bytes'> piCtory file
        """
        if self.__sockend.is_set():
            raise ValueError("read of closed file")

        if self.__pictory_h == HASH_FAIL:
            raise RuntimeError("could not read/parse piCtory configuration over network")

        buff = self._direct_sr(_syspictory, 4)
        (recv_length,) = unpack("=I", buff)
        return self._direct_sr(b"", recv_length)

    def readreplaceio(self) -> bytes:
        """
        Retrieves the replace_io configuration.

        :return: <class 'bytes'> replace_io_file
        """
        if self.__sockend.is_set():
            raise ValueError("read of closed file")

        if self.__replace_ios_h == HASH_FAIL:
            raise RuntimeError("replace_io_file: could not read/parse over network")

        buff = self._direct_sr(_sysreplaceio, 4)
        (recv_length,) = unpack("=I", buff)
        return self._direct_sr(b"", recv_length)

    def run(self) -> None:
        """Handler for synchronization."""
        state_reconnect = False
        while not self.__sockend.is_set():
            # Reconnect on error message
            if self.__sockerr.is_set():
                if not state_reconnect:
                    state_reconnect = True
                    warnings.warn("got a network error and try to reconnect", RuntimeWarning)
                self._connect()
                if self.__sockerr.is_set():
                    # Prevents 100% CPU load on failure
                    self.__sockend.wait(self.__waitsync)
                    continue
                else:
                    state_reconnect = False
                    warnings.warn("successfully reconnected after network error", RuntimeWarning)

            # No error occurred, perform sync if socket is free
            if self.__socklock.acquire(blocking=False):
                try:
                    self._serversock.sendall(_syssync)

                    self.__buff_recv.clear()
                    recv_lenght = 2
                    while recv_lenght > 0:
                        count = self._serversock.recv_into(self.__buff_block, recv_lenght)
                        if count == 0:
                            raise IOError("lost network connection on sync")
                        self.__buff_recv += self.__buff_block[:count]
                        recv_lenght -= count

                except IOError:
                    self.__sockerr.set()
                else:
                    if self.__buff_recv != b"\x06\x16":
                        warnings.warn("data error on network sync", RuntimeWarning)
                        self.__sockerr.set()
                        continue
                finally:
                    self.__socklock.release()

            # Wait after sync so instantiation works
            self.__sockerr.wait(self.__waitsync)

    def seek(self, position: int) -> None:
        """Jump to specified position.
        @param position Jump to this position"""
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
            raise ValueError("seek of closed file")
        self.__position = int(position)

    def set_dirtybytes(self, position: int, dirtybytes: bytes) -> None:
        """
                Configures dirty bytes for process image on connection error.

                This function does not throw an exception on transmission error,
                but triggers a reconnection.

                :param position: Start position for writing
        :param dirtybytes: <class 'bytes'> to be written
        """
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
            raise ValueError("I/O operation on closed file")

        # Always accept data
        self.__dictdirty[position] = dirtybytes

        try:
            # b CM ii ii 00000000 b = 16
            buff = self._direct_sr(
                pack("=c2sHH8xc", HEADER_START, b"EY", position, len(dirtybytes), HEADER_STOP)
                + dirtybytes,
                1,
            )

            if buff != b"\x1e":
                # Check ACL and throw error if necessary
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
                Sets timeout value for connection.

        :param value: Timeout in milliseconds
        """
        if self.__sockend.is_set():
            raise ValueError("I/O operation on closed file")

        # Process timeout value (could throw exception)
        self.__set_systimeout(value)

        try:
            # b CM ii xx 00000000 b = 16
            buff = self._direct_sr(pack("=c2sH10xc", HEADER_START, b"CF", value, HEADER_STOP), 1)
            if buff != b"\x1e":
                raise IOError("set timeout error on network")
        except Exception:
            self.__sockerr.set()

    def tell(self) -> int:
        """
        Returns aktuelle Position.

        :return: Aktuelle Position
        """
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
            raise ValueError("I/O operation on closed file")
        return self.__position

    def write(self, bytebuff: bytes) -> int:
        """
                Write data via the network.

        :param bytebuff: Bytes to write
        :return: <class 'int'> Number of written bytes
        """
        if self.__config_changed:
            raise ConfigChanged("configuration on revolution pi was changed")
        if self.__sockend.is_set():
            raise ValueError("write to closed file")
        if self.__sockerr.is_set():
            raise IOError("not allowed while reconnect")

        with self.__socklock:
            self.__int_buff += 1

            # Store data block with position and length in buffer
            self.__by_buff += (
                self.__position.to_bytes(length=2, byteorder="little")
                + len(bytebuff).to_bytes(length=2, byteorder="little")
                + bytebuff
            )

        # TODO: Bufferlänge and dann flushen?

        return len(bytebuff)

    closed = property(get_closed)
    config_changed = property(get_config_changed)
    name = property(get_name)
    reconnecting = property(get_reconnecting)
    timeout = property(get_timeout, set_timeout)


class RevPiNetIO(_RevPiModIO):
    """
        Class for managing the piCtory configuration via the network.

    This class takes over the entire configuration from piCtory and maps
    the devices and IOs. It takes over exclusive management of the
    process image and ensures that the data is synchronized.
    If only individual devices should be controlled, use
    RevPiNetIOSelected() and pass a list with device positions or device names during instantiation.
    """

    __slots__ = "_address"

    def __init__(
        self,
        address,
        autorefresh=False,
        monitoring=False,
        syncoutputs=True,
        simulator=False,
        debug=True,
        replace_io_file=None,
        shared_procimg=False,
    ):
        """
                Instantiates the basic functions.

        :param address: IP address <class 'str'> / (IP, Port) <class 'tuple'>
        :param autorefresh: If True, add all devices to autorefresh
        :param monitoring: Inputs and outputs are read, never written
        :param syncoutputs: Read currently set outputs from process image
        :param simulator: Loads the module as simulator and swaps IOs
        :param debug: Output complete messages for all errors
        :param replace_io_file: Load replace IO configuration from file
                :param shared_procimg: Share process image with other processes, this
                                       could be insecure for automation
        """
        check_ip = compile(r"^(25[0-5]|(2[0-4]|[01]?\d|)\d)(\.(25[0-5]|(2[0-4]|[01]?\d|)\d)){3}$")

        # Process address
        if isinstance(address, str):
            self._address = (address, 55234)
        elif isinstance(address, tuple):
            if len(address) == 2 and isinstance(address[0], str) and isinstance(address[1], int):
                # Check values
                if not 0 < address[1] <= 65535:
                    raise ValueError("port number out of range 1 - 65535")

                self._address = address
            else:
                raise TypeError("address tuple must be (<class 'str'>, <class 'int'>)")
        else:
            raise TypeError(
                "parameter address must be <class 'str'> or <class 'tuple'> "
                "like (<class 'str'>, <class 'int'>)"
            )

        # Check IP address and resolve if necessary
        if check_ip.match(self._address[0]) is None:
            try:
                ipv4 = socket.gethostbyname(self._address[0])
                self._address = (ipv4, self._address[1])
            except Exception:
                raise ValueError(
                    "can not resolve ip address for hostname '{0}'".format(self._address[0])
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
        )
        self._set_device_based_cycle_time = False

        # Create network file handler
        self._myfh = self._create_myfh()

        # Only configure if not inherited
        if type(self) == RevPiNetIO:
            self._configure(self.get_jconfigrsc())

    def _create_myfh(self):
        """
        Creates NetworkFileObject.

        :return: FileObject
        """
        self._buffedwrite = True
        return NetFH(self._address, self._replace_io_file == ":network:")

    def _get_cpreplaceio(self) -> ConfigParser:
        """
        Loads the replace_io configuration via the network.

        :return: <class 'ConfigParser'> of the replace io data
        """
        # Handle normal usage via parent class
        if self._replace_io_file != ":network:":
            return super()._get_cpreplaceio()

        # Obtain replace IO data via the network
        byte_buff = self._myfh.readreplaceio()

        cp = ConfigParser()
        try:
            cp.read_string(byte_buff.decode("utf-8"))
        except Exception as e:
            raise RuntimeError("replace_io_file: could not read/parse network data | {0}".format(e))
        return cp

    def disconnect(self) -> None:
        """Disconnects connections and terminates autorefresh including all threads."""
        self.cleanup()

    def exit(self, full=True) -> None:
        """
        Terminates mainloop() and optionally autorefresh.

        :ref: :func:`RevPiModIO.exit()`
        """
        try:
            super().exit(full)
        except ConfigChanged:
            pass

    def get_config_changed(self) -> bool:
        """
                Check if RevPi configuration was changed.

        In this case, the connection is closed and RevPiNetIO must be
        reinstantiated.

        :return: True if RevPi configuration was changed
        """
        return self._myfh.config_changed

    def get_jconfigrsc(self) -> dict:
        """
                Loads the piCtory configuration and creates a <class 'dict'>.

        :return: <class 'dict'> of the piCtory configuration
        """
        mynh = NetFH(self._address, False)
        byte_buff = mynh.readpictory()
        mynh.close()
        return jloads(byte_buff.decode("utf-8"))

    def get_reconnecting(self) -> bool:
        """
                Internal reconnect active due to network errors.

        The module tries internally to reestablish the connection. No
        further action is needed.

        :return: True if reconnect is active
        """
        return self._myfh.reconnecting

    def net_cleardefaultvalues(self, device=None) -> None:
        """
        Clears default values from the PLC server.

        :param device: Only apply to single device, otherwise to all
        """
        if self.monitoring:
            raise RuntimeError("can not send default values, while system is in monitoring mode")

        if device is None:
            self._myfh.clear_dirtybytes()
        else:
            dev = device if isinstance(device, Device) else self.device.__getitem__(device)
            mylist = [dev]

            for dev in mylist:
                self._myfh.clear_dirtybytes(dev._offset + dev._slc_out.start)

    def net_setdefaultvalues(self, device=None) -> None:
        """
                Configures the PLC server with the piCtory default values.

        These values are set on the RevPi if the connection is
        unexpectedly interrupted (network error).

                :param device: Only apply to single device, otherwise to all
        """
        if self.monitoring:
            raise RuntimeError("can not send default values, while system is in monitoring mode")

        if device is None:
            mylist = self.device
        else:
            dev = device if isinstance(device, Device) else self.device.__getitem__(device)
            mylist = [dev]

        for dev in mylist:
            dirtybytes = bytearray()
            for lst_io in self.io[dev._slc_outoff]:
                listlen = len(lst_io)

                if listlen == 1:
                    # Take byte-oriented outputs directly
                    dirtybytes += lst_io[0]._defaultvalue

                elif listlen > 1:
                    # Combine bit-oriented outputs into one byte
                    int_byte = 0
                    lstbyte = lst_io.copy()
                    lstbyte.reverse()

                    for bitio in lstbyte:
                        # Shift the bits from back to front
                        int_byte <<= 1
                        if bitio is not None:
                            int_byte += 1 if bitio._defaultvalue else 0

                    # Convert calculated int value to a byte
                    dirtybytes += int_byte.to_bytes(length=1, byteorder="little")

            # Send dirtybytes to PLC server
            self._myfh.set_dirtybytes(dev._offset + dev._slc_out.start, dirtybytes)

    config_changed = property(get_config_changed)
    reconnecting = property(get_reconnecting)


class RevPiNetIOSelected(RevPiNetIO):
    """
        Class for managing individual devices from piCtory.

    This class only takes over specified devices from the piCtory configuration
    and maps them including IOs. It takes over exclusive management of the
    address range in the process image where the specified devices are located
    and ensures that the data is synchronized.
    """

    __slots__ = ()

    def __init__(
        self,
        address,
        deviceselection,
        autorefresh=False,
        monitoring=False,
        syncoutputs=True,
        simulator=False,
        debug=True,
        replace_io_file=None,
        shared_procimg=False,
    ):
        """
                Instantiates the basic functions only for specified devices.

                The parameter deviceselection can be a single
        device position / single device name or a list with
        multiple positions / names

        :param address: IP address <class 'str'> / (IP, Port) <class 'tuple'>
        :param deviceselection: Position number or device name
                :ref: :func:`RevPiNetIO.__init__()`
        """
        super().__init__(
            address,
            autorefresh,
            monitoring,
            syncoutputs,
            simulator,
            debug,
            replace_io_file,
            shared_procimg,
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
                    "could not find ANY given {0} devices in config".format(self._devselect.type)
                )
            else:
                raise DeviceNotFoundError("could not find ANY given devices in config")
        elif not self._devselect.other_device_key and len(self.device) != len(
            self._devselect.values
        ):
            if self._devselect.type:
                raise DeviceNotFoundError(
                    "could not find ALL given {0} devices in config".format(self._devselect.type)
                )
            else:
                raise DeviceNotFoundError("could not find ALL given devices in config")


class RevPiNetIODriver(RevPiNetIOSelected):
    """
    Class to create custom drivers for virtual devices.

    With this class, only specified virtual devices are managed with RevPiModIO.
    During instantiation, inputs and outputs are automatically swapped to allow
    writing of inputs. The data can then be retrieved from the devices via logiCAD.
    """

    __slots__ = ()

    def __init__(
        self,
        address,
        virtdev,
        autorefresh=False,
        syncoutputs=True,
        debug=True,
        replace_io_file=None,
        shared_procimg=False,
    ):
        """
                Instantiates the basic functions.

                Parameters 'monitoring' and 'simulator' are not available here,
        as these are set automatically.

        :param address: IP address <class 'str'> / (IP, Port) <class 'tuple'>
        :param virtdev: Virtual device or multiple as <class 'list'>
                :ref: :func:`RevPiModIO.__init__()`
        """
        # Load parent with monitoring=False and simulator=True
        if type(virtdev) not in (list, tuple):
            virtdev = (virtdev,)
        dev_select = DevSelect(DeviceType.VIRTUAL, "", virtdev)
        super().__init__(
            address,
            dev_select,
            autorefresh,
            False,
            syncoutputs,
            True,
            debug,
            replace_io_file,
            shared_procimg,
        )


def run_net_plc(address, func, cycletime=50, replace_io_file=None, debug=True):
    """
    Run Revoluton Pi as real plc with cycle loop and exclusive IO access.

    This function is just a shortcut to run the module in cycle loop mode and
    handle the program exit signal. You will access the .io, .core, .device
    via the cycletools in your cycle function.

    Shortcut for this source code:
        rpi = RevPiModIO(autorefresh=True, replace_io_file=..., debug=...)
        rpi.handlesignalend()
        return rpi.cycleloop(func, cycletime)

    :param address: IP address <class 'str'> / (IP, Port) <class 'tuple'>
    :param func: Function to run every set milliseconds
    :param cycletime: Cycle time in milliseconds
    :param replace_io_file: Load replace IO configuration from file
    :param debug: Print all warnings and detailed error messages
    :return: None or the return value of the cycle function
    """
    rpi = RevPiNetIO(
        address=address,
        autorefresh=True,
        replace_io_file=replace_io_file,
        debug=debug,
    )
    rpi.handlesignalend()
    return rpi.cycleloop(func, cycletime)

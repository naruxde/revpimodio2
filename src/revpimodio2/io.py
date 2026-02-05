# -*- coding: utf-8 -*-
"""RevPiModIO module for managing IOs."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2023 Sven Sager"
__license__ = "LGPLv2"

import struct
import warnings
from re import match as rematch
from threading import Event

from ._internal import consttostr, RISING, FALLING, BOTH, INP, OUT, MEM, PROCESS_IMAGE_SIZE

try:
    # Only works on Unix
    from fcntl import ioctl
except Exception:
    ioctl = None


class IOEvent(object):
    """Base class for IO events."""

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
    """Base class for direct access to IO objects."""

    def __init__(self, modio):
        """Init IOList class."""
        self.__dict_iobyte = {k: [] for k in range(PROCESS_IMAGE_SIZE)}
        self.__dict_iorefname = {}
        self.__modio = modio

    def __contains__(self, key):
        """
        Checks if IO exists.

        :param key: IO name <class 'str'> or byte number <class 'int'>
        :return: True if IO exists / byte is occupied
        """
        if type(key) == int:
            return len(self.__dict_iobyte.get(key, [])) > 0
        else:
            return hasattr(self, key) and type(getattr(self, key)) != DeadIO

    def __delattr__(self, key):
        """
        Removes specified IO.

        :param key: IO to remove
        """
        io_del = object.__getattribute__(self, key)

        # Delete old events from device
        io_del.unreg_event()

        # Remove IO from byte list and attributes
        if io_del._bitshift:
            self.__dict_iobyte[io_del.address][io_del._bitaddress] = None

            # Do not use any() because we want to know None, not 0
            if self.__dict_iobyte[io_del.address] == [
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            ]:
                self.__dict_iobyte[io_del.address] = []
        else:
            self.__dict_iobyte[io_del.address].remove(io_del)

        object.__delattr__(self, key)
        io_del._parentdevice._update_my_io_list()

    def __enter__(self):
        """
        Read inputs on entering context manager and write outputs on leaving.

        All entries are read when entering the context manager. Within the
        context manager, further .readprocimg() or .writeprocimg() calls can
        be made and the process image can be read or written. When exiting,
        all outputs are always written into the process image.

        When 'autorefresh=True' is used, all read or write actions in the
        background are performed automatically.
        """
        if not self.__modio._context_manager:
            # If ModIO itself is in a context manager, it sets the _looprunning=True flag itself
            if self.__modio._looprunning:
                raise RuntimeError("can not enter context manager inside mainloop or cycleloop")
            self.__modio._looprunning = True

        self.__modio.readprocimg()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Write outputs to process image before leaving the context manager."""
        if self.__modio._imgwriter.is_alive():
            # Reset new data flat to sync with imgwriter
            self.__modio._imgwriter.newdata.clear()

        # Write outputs on devices without autorefresh
        if not self.__modio._monitoring:
            self.__modio.writeprocimg()

        if self.__modio._imgwriter.is_alive():
            # Wait until imgwriter has written outputs
            self.__modio._imgwriter.newdata.wait(2.5)

        if not self.__modio._context_manager:
            # Do not reset if ModIO is in a context manager itself, it will handle that flag
            self.__modio._looprunning = False

    def __getattr__(self, key):
        """
        Manages deleted IOs (attributes that do not exist).

        :param key: Name or byte of an old IO
        :return: Old IO if in ref lists
        """
        if key in self.__dict_iorefname:
            return self.__dict_iorefname[key]
        else:
            raise AttributeError("can not find io '{0}'".format(key))

    def __getitem__(self, key):
        """
        Retrieves specified IO.

        If the key is <class 'str'>, a single IO is returned. If the key
        is passed as <class 'int'>, a <class 'list'> is returned with 0, 1
        or 8 entries. If a <class 'slice'> is given as key, the lists are
        returned in a list.

        :param key: IO name as <class 'str'> or byte as <class 'int'>.
        :return: IO object or list of IOs
        """
        if type(key) == int:
            if key not in self.__dict_iobyte:
                raise IndexError("byte '{0}' does not exist".format(key))
            return self.__dict_iobyte[key]
        elif type(key) == slice:
            return [
                self.__dict_iobyte[int_io]
                for int_io in range(key.start, key.stop, 1 if key.step is None else key.step)
            ]
        else:
            return getattr(self, key)

    def __iter__(self):
        """
        Returns iterator of all IOs.

        :return: Iterator of all IOs
        """
        for int_io in sorted(self.__dict_iobyte):
            for io in self.__dict_iobyte[int_io]:
                if io is not None:
                    yield io

    def __len__(self):
        """
        Returns the number of all IOs.

        :return: Number of all IOs
        """
        int_ios = 0
        for int_io in self.__dict_iobyte:
            for io in self.__dict_iobyte[int_io]:
                if io is not None:
                    int_ios += 1
        return int_ios

    def __setattr__(self, key, value):
        """Prohibits direct setting of attributes for performance reasons."""
        if key in (
            "_IOList__dict_iobyte",
            "_IOList__dict_iorefname",
            "_IOList__modio",
        ):
            object.__setattr__(self, key, value)
        else:
            raise AttributeError("direct assignment is not supported - use .value Attribute")

    def __private_replace_oldio_with_newio(self, io) -> None:
        """
        Replaces existing IOs with the newly registered one.

        :param io: New IO to be inserted
        """
        # Define scan range
        if io._bitshift:
            scan_start = io._parentio_address
            scan_stop = scan_start + io._parentio_length
        else:
            scan_start = io.address
            scan_stop = scan_start + (1 if io._length == 0 else io._length)

        # Collect default value over multiple bytes
        calc_defaultvalue = b""

        for i in range(scan_start, scan_stop):
            for oldio in self.__dict_iobyte[i]:
                if type(oldio) == StructIO:
                    # There is already a new IO here
                    if oldio._bitshift:
                        if (
                            io._bitshift == oldio._bitshift
                            and io._slc_address == oldio._slc_address
                        ):
                            raise MemoryError(
                                "bit {0} already assigned to '{1}'".format(
                                    io._bitaddress, oldio._name
                                )
                            )
                    else:
                        # Already overwritten bytes are invalid
                        raise MemoryError(
                            "new io '{0}' overlaps memory of '{1}'".format(io._name, oldio._name)
                        )
                elif oldio is not None:
                    # Remember IOs in the memory area of the new IO
                    if io._bitshift:
                        # Store IOs for ref at bitaddress
                        self.__dict_iorefname[oldio._name] = DeadIO(oldio)
                    else:
                        # Calculate default value
                        oldio.byteorder = io._byteorder
                        if io._byteorder == "little":
                            calc_defaultvalue += oldio._defaultvalue
                        else:
                            calc_defaultvalue = oldio._defaultvalue + calc_defaultvalue

                    # Remove IOs from lists
                    delattr(self, oldio._name)

        if io._defaultvalue is None:
            # Only take over for StructIO and no given defaultvalue
            if io._bitshift:
                io_byte_address = io._parentio_address - io.address
                io._defaultvalue = bool(io._parentio_defaultvalue[io_byte_address] & io._bitshift)
            else:
                io._defaultvalue = calc_defaultvalue

    def _private_register_new_io_object(self, new_io) -> None:
        """
        Registers new IO object independently of __setattr__.

        :param new_io: New IO object
        """
        if isinstance(new_io, IOBase):
            if hasattr(self, new_io._name):
                raise AttributeError(
                    "attribute {0} already exists - can not set io".format(new_io._name)
                )

            do_replace = type(new_io) is StructIO
            if do_replace:
                self.__private_replace_oldio_with_newio(new_io)

            # Adapt byte dict for address access
            if new_io._bitshift:
                if len(self.__dict_iobyte[new_io.address]) != 8:
                    # "Quickly" create 8 entries since these are BIT IOs
                    self.__dict_iobyte[new_io.address] += [
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                    ]
                # Check for overlapping IOs
                if (
                    not do_replace
                    and self.__dict_iobyte[new_io.address][new_io._bitaddress] is not None
                ):
                    warnings.warn(
                        "ignore io '{0}', as an io already exists at the address '{1} Bit {2}'. "
                        "this can be caused by an incorrect pictory configuration.".format(
                            new_io.name,
                            new_io.address,
                            new_io._bitaddress,
                        ),
                        Warning,
                    )
                    return

                self.__dict_iobyte[new_io.address][new_io._bitaddress] = new_io
            else:
                # Search the previous IO to calculate the length
                offset_end = new_io.address
                search_index = new_io.address
                while search_index >= 0:
                    previous_io = self.__dict_iobyte[search_index]
                    if len(previous_io) == 8:
                        # Bits on this address are always 1 byte
                        offset_end -= 1
                    elif len(previous_io) == 1:
                        # Found IO, calculate offset + length of IO
                        offset_end = previous_io[0].address + previous_io[0].length
                        break
                    search_index -= 1

                # Check if the length of the previous IO overlaps with the new IO
                if offset_end > new_io.address:
                    warnings.warn(
                        "ignore io '{0}', as an io already exists at the address '{1}'. "
                        "this can be caused by an incorrect pictory configuration.".format(
                            new_io.name,
                            new_io.address,
                        ),
                        Warning,
                    )
                    return

                self.__dict_iobyte[new_io.address].append(new_io)

            object.__setattr__(self, new_io._name, new_io)

            if type(new_io) is StructIO:
                new_io._parentdevice._update_my_io_list()
        else:
            raise TypeError("io must be <class 'IOBase'> or sub class")


class DeadIO(object):
    """Class for managing replaced IOs."""

    __slots__ = "__deadio"

    def __init__(self, deadio):
        """
        Instantiation of the DeadIO class.

        :param deadio: IO that was replaced
        """
        self.__deadio = deadio

    def replace_io(self, name: str, frm: str, **kwargs) -> None:
        """
        Provides function for further bit replacements.

        :ref: :func:IntIOReplaceable.replace_io()
        """
        self.__deadio.replace_io(name, frm, **kwargs)

    _parentdevice = property(lambda self: None)


class IOBase(object):
    """
    Base class for all IO objects.

    The basic functionality enables reading and writing of values as
    <class bytes'> or <class 'bool'>. This is decided during instantiation.
    If a bit address is specified, <class 'bool'> values are expected and
    returned, otherwise <class bytes'>.

    This class serves as a basis for other IO classes with which the values
    can also be used as <class 'int'>.
    """

    __slots__ = (
        "__bit_ioctl_off",
        "__bit_ioctl_on",
        "_bitaddress",
        "_bitshift",
        "_bitlength",
        "_byteorder",
        "_defaultvalue",
        "_export",
        "_iotype",
        "_length",
        "_name",
        "_parentdevice",
        "_read_only_io",
        "_signed",
        "_slc_address",
        "bmk",
    )

    def __init__(self, parentdevice, valuelist: list, iotype: int, byteorder: str, signed: bool):
        """
        Instantiation of the IOBase class.

        :param parentdevice: Parent device on which the IO is located
        :param valuelist: Data list for instantiation
            ["name","defval","bitlen","startaddrdev",exp,"idx","bmk","bitaddr"]
        :param iotype: <class 'int'> value
        :param byteorder: Byteorder 'little'/'big' for <class 'int'> calculation
        :param signed: Perform int calculation with sign
        """
        # ["name","defval","bitlen","startaddrdev",exp,"idx","bmk","bitaddr"]
        # [  0   ,   1    ,   2    ,       3      , 4 ,  5  ,  6  ,    7    ]
        self._parentdevice = parentdevice

        # Break down bit addresses to bytes and convert
        self._bitaddress = -1 if valuelist[7] == "" else int(valuelist[7]) % 8
        self._bitshift = None if self._bitaddress == -1 else 1 << self._bitaddress

        # Length calculation
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
            # Wrap bits higher than 7 to next bytes
            int_startaddress += int(int(valuelist[7]) / 8)
            self._slc_address = slice(int_startaddress, int_startaddress + 1)

            # Determine default value, otherwise False
            if valuelist[1] is None and type(self) == StructIO:
                self._defaultvalue = None
            else:
                try:
                    self._defaultvalue = bool(int(valuelist[1]))
                except Exception:
                    self._defaultvalue = False

            # Set ioctl for bit setting
            self.__bit_ioctl_off = struct.pack("<HB", self._get_address(), self._bitaddress)
            self.__bit_ioctl_on = self.__bit_ioctl_off + b"\x01"
        else:
            self._slc_address = slice(int_startaddress, int_startaddress + self._length)
            if str(valuelist[1]).isdigit():
                # Convert default value from number to bytes
                self._defaultvalue = int(valuelist[1]).to_bytes(
                    self._length, byteorder=self._byteorder
                )
            elif valuelist[1] is None and type(self) == StructIO:
                # Set to None to take over calculated values later
                self._defaultvalue = None
            elif type(valuelist[1]) == bytes:
                # Take default value directly from bytes
                if len(valuelist[1]) == self._length:
                    self._defaultvalue = valuelist[1]
                else:
                    raise ValueError(
                        "given bytes for default value must have a length "
                        "of {0} but {1} was given"
                        "".format(self._length, len(valuelist[1]))
                    )
            else:
                # Fill default value with empty bytes
                self._defaultvalue = bytes(self._length)

                # Try to convert string to ASCII bytes
                if type(valuelist[1]) == str:
                    try:
                        buff = valuelist[1].encode("ASCII")
                        if len(buff) <= self._length:
                            self._defaultvalue = buff + bytes(self._length - len(buff))
                    except Exception:
                        pass

    def __bool__(self):
        """
        <class 'bool'> value of the class.

        :return: <class 'bool'> Only False if False or 0, otherwise True
        """
        if self._bitshift:
            return bool(self._parentdevice._ba_devdata[self._slc_address.start] & self._bitshift)
        else:
            return any(self._parentdevice._ba_devdata[self._slc_address])

    def __call__(self, value=None):
        """
        Get or set the IO value using function call syntax.

        :param value: If None, returns current value; otherwise sets the value
        :return: Current IO value when called without arguments
        """
        if value is None:
            # Inline get_value()
            if self._bitshift:
                return bool(
                    self._parentdevice._ba_devdata[self._slc_address.start] & self._bitshift
                )
            else:
                return bytes(self._parentdevice._ba_devdata[self._slc_address])
        else:
            self.set_value(value)

    def __len__(self):
        """
        Returns the byte length of the IO.

        :return: Byte length of the IO - 0 for BITs
        """
        return 0 if self._bitaddress > 0 else self._length

    def __str__(self):
        """
        <class 'str'> value of the class.

        :return: Name of the IO
        """
        return self._name

    def __reg_xevent(
        self, func, delay: int, edge: int, as_thread: bool, overwrite: bool, prefire: bool
    ) -> None:
        """
        Manages reg_event and reg_timerevent.

        :param func: Function to be called on change
        :param delay: Delay in ms for triggering - also on value change
        :param edge: Execute on RISING, FALLING or BOTH value change
        :param as_thread: If True, execute function as EventCallback thread
        :param overwrite: If True, event will be overwritten
        :param prefire: Trigger with current value when mainloop starts
        """
        # Check if function is callable
        if not callable(func):
            raise ValueError("registered function '{0}' is not callable".format(func))
        if type(delay) != int or delay < 0:
            raise ValueError("'delay' must be <class 'int'> and greater or equal 0")
        if edge != BOTH and not self._bitshift:
            raise ValueError("parameter 'edge' can be used with bit io objects only")
        if prefire and self._parentdevice._modio._looprunning:
            raise RuntimeError("prefire can not be used if mainloop is running")

        if self not in self._parentdevice._dict_events:
            with self._parentdevice._filelock:
                self._parentdevice._dict_events[self] = [
                    IOEvent(func, edge, as_thread, delay, overwrite, prefire)
                ]
        else:
            # Check if function is already registered
            for regfunc in self._parentdevice._dict_events[self]:
                if regfunc.func != func:
                    # Test next entry
                    continue

                if edge == BOTH or regfunc.edge == BOTH:
                    if self._bitshift:
                        raise RuntimeError(
                            "io '{0}' with function '{1}' already in list "
                            "with edge '{2}' - edge '{3}' not allowed anymore"
                            "".format(self._name, func, consttostr(regfunc.edge), consttostr(edge))
                        )
                    else:
                        raise RuntimeError(
                            "io '{0}' with function '{1}' already in list."
                            "".format(self._name, func)
                        )

                elif regfunc.edge == edge:
                    raise RuntimeError(
                        "io '{0}' with function '{1}' for given edge '{2}' "
                        "already in list".format(self._name, func, consttostr(edge))
                    )

            # Insert event function
            with self._parentdevice._filelock:
                self._parentdevice._dict_events[self].append(
                    IOEvent(func, edge, as_thread, delay, overwrite, prefire)
                )

    def _get_address(self) -> int:
        """
        Returns the absolute byte address in the process image.

        :return: Absolute byte address
        """
        return self._parentdevice._offset + self._slc_address.start

    def _get_byteorder(self) -> str:
        """
        Returns configured byteorder.

        :return: <class 'str'> Byteorder
        """
        return self._byteorder

    def _get_export(self) -> bool:
        """Return value of export flag."""
        return bool(self._export & 1)

    def _get_iotype(self) -> int:
        """
        Returns io type.

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
            value = self._parentdevice._ba_devdata[self._slc_address.start] & self._bitshift
            if self._parentdevice._modio._run_on_pi:
                # IOCTL on the RevPi
                with self._parentdevice._modio._myfh_lck:
                    try:
                        # Perform set value (function K+16)
                        ioctl(
                            self._parentdevice._modio._myfh,
                            19216,
                            self.__bit_ioctl_on if value else self.__bit_ioctl_off,
                        )
                    except Exception as e:
                        self._parentdevice._modio._gotioerror("ioset", e)
                        return False

            elif hasattr(self._parentdevice._modio._myfh, "ioctl"):
                # IOCTL over network
                with self._parentdevice._modio._myfh_lck:
                    try:
                        self._parentdevice._modio._myfh.ioctl(
                            19216,
                            self.__bit_ioctl_on if value else self.__bit_ioctl_off,
                        )
                    except Exception as e:
                        self._parentdevice._modio._gotioerror("net_ioset", e)
                        return False

            else:
                # Simulate IOCTL in file
                try:
                    # Execute set value (function K+16)
                    self._parentdevice._modio._simulate_ioctl(
                        19216,
                        self.__bit_ioctl_on if value else self.__bit_ioctl_off,
                    )
                except Exception as e:
                    self._parentdevice._modio._gotioerror("file_ioset", e)
                    return False

        else:
            # Write one or more bytes to process image
            value = bytes(self._parentdevice._ba_devdata[self._slc_address])
            with self._parentdevice._modio._myfh_lck:
                try:
                    self._parentdevice._modio._myfh.seek(self._get_address())
                    self._parentdevice._modio._myfh.write(value)
                    if self._parentdevice._modio._buffedwrite:
                        self._parentdevice._modio._myfh.flush()
                except IOError as e:
                    self._parentdevice._modio._gotioerror("ioset", e)
                    return False

        return True

    def get_defaultvalue(self):
        """
        Returns the default value from piCtory.

        :return: Default value as <class 'byte'> or <class 'bool'>
        """
        return self._defaultvalue

    def get_value(self):
        """
        Returns the value of the IO.

        :return: IO value as <class 'bytes'> or <class 'bool'>
        """
        if self._bitshift:
            return bool(self._parentdevice._ba_devdata[self._slc_address.start] & self._bitshift)
        else:
            return bytes(self._parentdevice._ba_devdata[self._slc_address])

    def reg_event(self, func, delay=0, edge=BOTH, as_thread=False, prefire=False):
        """
        Registers an event for the IO in the event monitoring.

        The passed function is executed when the IO value changes. With
        specification of optional parameters, the trigger behavior can be
        controlled.

        NOTE: The delay time must fit into .cycletime, if not, it will
        ALWAYS be rounded up!

        :param func: Function to be called on change
        :param delay: Delay in ms for triggering if value stays the same
        :param edge: Execute on RISING, FALLING or BOTH value change
        :param as_thread: If True, execute function as EventCallback thread
        :param prefire: Trigger with current value when mainloop starts
        """
        self.__reg_xevent(func, delay, edge, as_thread, True, prefire)

    def reg_timerevent(self, func, delay, edge=BOTH, as_thread=False, prefire=False):
        """
        Registers a timer for the IO which executes func after delay.

        The timer is started when the IO value changes and executes the passed
        function - even if the IO value has changed in the meantime. If the
        timer has not expired and the condition is met again, the timer is NOT
        reset to the delay value or started a second time. For this behavior,
        .reg_event(..., delay=value) can be used.

        NOTE: The delay time must fit into .cycletime, if not, it will
        ALWAYS be rounded up!

        :param func: Function to be called on change
        :param delay: Delay in ms for triggering - also on value change
        :param edge: Execute on RISING, FALLING or BOTH value change
        :param as_thread: If True, execute function as EventCallback thread
        :param prefire: Trigger with current value when mainloop starts
        """
        self.__reg_xevent(func, delay, edge, as_thread, False, prefire)

    def set_value(self, value) -> None:
        """
        Sets the value of the IO.

        :param value: IO value as <class bytes'> or <class 'bool'>
        """
        if self._read_only_io:
            if self._iotype == INP:
                if self._parentdevice._modio._simulator:
                    raise RuntimeError(
                        "can not write to output '{0}' in simulator mode".format(self._name)
                    )
                else:
                    raise RuntimeError("can not write to input '{0}'".format(self._name))
            elif self._iotype == MEM:
                raise RuntimeError("can not write to memory '{0}'".format(self._name))
            raise RuntimeError("the io object '{0}' is read only".format(self._name))

        if self._bitshift:
            # Try to convert any type to bool
            value = bool(value)

            # Lock for bit operations
            self._parentdevice._filelock.acquire()

            if self._parentdevice._shared_procimg:
                # Mark this IO for write operations
                self._parentdevice._shared_write.add(self)

            # There is always only one byte here, get as int
            int_byte = self._parentdevice._ba_devdata[self._slc_address.start]

            # Compare current value and set if necessary
            if not bool(int_byte & self._bitshift) == value:
                if value:
                    int_byte += self._bitshift
                else:
                    int_byte -= self._bitshift

                # Write back if changed
                self._parentdevice._ba_devdata[self._slc_address.start] = int_byte

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
                    "length {1}, but {2} was given".format(self._name, self._length, len(value))
                )

            if self._parentdevice._shared_procimg:
                with self._parentdevice._filelock:
                    # Mark this IO as changed
                    self._parentdevice._shared_write.add(self)

            self._parentdevice._ba_devdata[self._slc_address] = value

    def unreg_event(self, func=None, edge=None) -> None:
        """
        Removes an event from event monitoring.

        :param func: Only events with specified function
        :param edge: Only events with specified function and specified edge
        """
        if self in self._parentdevice._dict_events:
            if func is None:
                with self._parentdevice._filelock:
                    del self._parentdevice._dict_events[self]
            else:
                newlist = []
                for regfunc in self._parentdevice._dict_events[self]:
                    if regfunc.func != func or edge is not None and regfunc.edge != edge:
                        newlist.append(regfunc)

                # If functions remain, take them over
                with self._parentdevice._filelock:
                    if len(newlist) > 0:
                        self._parentdevice._dict_events[self] = newlist
                    else:
                        del self._parentdevice._dict_events[self]

    def wait(self, edge=BOTH, exitevent=None, okvalue=None, timeout=0) -> int:
        """
        Waits for value change of an IO.

        The value change is always checked when new data has been read for devices
        with autorefresh enabled.

        On value change, waiting ends with 0 as return value.

        NOTE: If <class 'ProcimgWriter'> does not deliver new data,
        it will wait forever (not when "timeout" is specified).

        If edge is specified with RISING or FALLING, this edge must be
        triggered. If the value is 1 when entering with edge
        RISING, the wait will only end when changing from 0 to 1.

        A <class 'threading.Event'> object can be passed as exitevent,
        which ends the waiting immediately with 1 as return value
        when is_set().

        If the value okvalue is present at the IO for waiting, the
        waiting ends immediately with -1 as return value.

        The timeout value aborts the waiting immediately when reached with
        value 2 as return value. (The timeout is calculated via the cycle time
        of the autorefresh function, so it does not correspond exactly to the
        specified milliseconds! It is always rounded up!)

        :param edge: Edge RISING, FALLING, BOTH that must occur
        :param exitevent: <class 'threading.Event'> for early termination
        :param okvalue: IO value at which waiting ends immediately
        :param timeout: Time in ms after which to abort
        :return: <class 'int'> successful values <= 0

        - Successfully waited
            - Value 0: IO has changed value
            - Value -1: okvalue matched IO
        - Erroneously waited
            - Value 1: exitevent was set
            - Value 2: timeout expired
            - Value 100: Devicelist.exit() was called

        """
        # Check if device is in autorefresh
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
            raise TypeError("parameter 'exitevent' must be <class 'threading.Event'>")
        if type(timeout) != int or timeout < 0:
            raise ValueError("parameter 'timeout' must be <class 'int'> and greater than 0")
        if edge != BOTH and not self._bitshift:
            raise ValueError("parameter 'edge' can be used with bit Inputs only")

        # Check abort value
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
        while (
            not self._parentdevice._modio._waitexit.is_set()
            and not exitevent.is_set()
            and flt_timecount < timeout
        ):
            if self._parentdevice._modio._imgwriter.newdata.wait(2.5):
                self._parentdevice._modio._imgwriter.newdata.clear()

                if val_start != self.value:
                    if (
                        edge == BOTH
                        or edge == RISING
                        and not val_start
                        or edge == FALLING
                        and val_start
                    ):
                        return 0
                    else:
                        val_start = not val_start
                if bool_timecount:
                    flt_timecount += self._parentdevice._modio._imgwriter._refresh
            elif bool_timecount:
                flt_timecount += 2.5

        # Abort event was set
        if exitevent.is_set():
            return 1

        # RevPiModIO mainloop was exited
        if self._parentdevice._modio._waitexit.is_set():
            return 100

        # Timeout expired
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
    Class for accessing data with conversion to int.

    This class extends the functionality of <class 'IOBase'> with functions
    for working with <class 'int'> values. For the
    conversion, 'byteorder' (default 'little') and 'signed' (default
    False) can be set as parameters.

    :ref: :class:`IOBase`
    """

    __slots__ = ()

    def __int__(self):
        """
        Returns IO value considering byteorder/signed.

        :return: IO value as <class 'int'>
        """
        return int.from_bytes(
            self._parentdevice._ba_devdata[self._slc_address],
            byteorder=self._byteorder,
            signed=self._signed,
        )

    def __call__(self, value=None):
        """
        Get or set the integer IO value using function call syntax.

        :param value: If None, returns current integer value; otherwise sets the integer value
        :return: Current IO value as integer when called without arguments
        :raises TypeError: If value is not an integer
        """
        if value is None:
            # Inline get_intvalue()
            return int.from_bytes(
                self._parentdevice._ba_devdata[self._slc_address],
                byteorder=self._byteorder,
                signed=self._signed,
            )
        else:
            # Inline from set_intvalue()
            if type(value) == int:
                self.set_value(
                    value.to_bytes(
                        self._length,
                        byteorder=self._byteorder,
                        signed=self._signed,
                    )
                )
            else:
                raise TypeError(
                    "'{0}' need a <class 'int'> value, but {1} was given"
                    "".format(self._name, type(value))
                )

    def _get_signed(self) -> bool:
        """
        Retrieves whether the value should be treated as signed.

        :return: True if signed
        """
        return self._signed

    def _set_byteorder(self, value: str) -> None:
        """
        Sets byteorder for <class 'int'> conversion.

        :param value: <class 'str'> 'little' or 'big'
        """
        if not (value == "little" or value == "big"):
            raise ValueError("byteorder must be 'little' or 'big'")
        if self._byteorder != value:
            self._byteorder = value
            self._defaultvalue = self._defaultvalue[::-1]

    def _set_signed(self, value: bool) -> None:
        """
        Sets whether the value should be treated as signed.

        :param value: True if to be treated as signed
        """
        if type(value) != bool:
            raise TypeError("signed must be <class 'bool'> True or False")
        self._signed = value

    def get_intdefaultvalue(self) -> int:
        """
        Returns the default value as <class 'int'>.

        :return: <class 'int'> Default value
        """
        return int.from_bytes(self._defaultvalue, byteorder=self._byteorder, signed=self._signed)

    def get_intvalue(self) -> int:
        """
        Returns IO value considering byteorder/signed.

        :return: IO value as <class 'int'>
        """
        return int.from_bytes(
            self._parentdevice._ba_devdata[self._slc_address],
            byteorder=self._byteorder,
            signed=self._signed,
        )

    def set_intvalue(self, value: int) -> None:
        """
        Sets IO considering byteorder/signed.

        :param value: <class 'int'> Value
        """
        if type(value) == int:
            self.set_value(
                value.to_bytes(
                    self._length,
                    byteorder=self._byteorder,
                    signed=self._signed,
                )
            )
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
    """Extends the IntIO class with the .reset() function for counters."""

    __slots__ = ("__ioctl_arg",)

    def __init__(self, counter_id, parentdevice, valuelist, iotype, byteorder, signed):
        """
        Instantiation of the IntIOCounter class.

        :param counter_id: ID for the counter to which the IO belongs (0-15)
        :ref: :func:`IOBase.__init__(...)`
        """
        if not isinstance(counter_id, int):
            raise TypeError("counter_id must be <class 'int'>")
        if not 0 <= counter_id <= 15:
            raise ValueError("counter_id must be 0 - 15")

        # Device position + empty + Counter_ID
        # ID-Bits: 7|6|5|4|3|2|1|0|15|14|13|12|11|10|9|8
        self.__ioctl_arg = (
            parentdevice._position.to_bytes(1, "little")
            + b"\x00"
            + (1 << counter_id).to_bytes(2, "little")
        )

        """
        IOCTL fills this struct, which has one byte free in memory after
        uint8_t due to padding. Therefore 4 bytes must be passed
        where the bitfield has little byteorder!!!

        typedef struct SDIOResetCounterStr
        {
            uint8_t     i8uAddress;   // Address of module
            uint16_t    i16uBitfield; // bitfield, if bit n is 1, reset
        } SDIOResetCounter;
        """

        # Load base class
        super().__init__(parentdevice, valuelist, iotype, byteorder, signed)

    def reset(self) -> None:
        """Resets the counter of the input."""
        if self._parentdevice._modio._monitoring:
            raise RuntimeError("can not reset counter, while system is in monitoring mode")
        if self._parentdevice._modio._simulator:
            raise RuntimeError("can not reset counter, while system is in simulator mode")

        if self._parentdevice._modio._run_on_pi:
            # IOCTL on the RevPi
            with self._parentdevice._modio._myfh_lck:
                try:
                    # Execute counter reset (function K+20)
                    ioctl(self._parentdevice._modio._myfh, 19220, self.__ioctl_arg)
                except Exception as e:
                    self._parentdevice._modio._gotioerror("iorst", e)

        elif hasattr(self._parentdevice._modio._myfh, "ioctl"):
            # IOCTL over network
            with self._parentdevice._modio._myfh_lck:
                try:
                    self._parentdevice._modio._myfh.ioctl(19220, self.__ioctl_arg)
                except Exception as e:
                    self._parentdevice._modio._gotioerror("net_iorst", e)

        else:
            # Simulate IOCTL in file
            try:
                # Execute set value (function K+20)
                self._parentdevice._modio._simulate_ioctl(19220, self.__ioctl_arg)
            except Exception as e:
                self._parentdevice._modio._gotioerror("file_iorst", e)


class IntIOReplaceable(IntIO):
    """Extends the IntIO class with the .replace_io function."""

    __slots__ = ()

    def replace_io(self, name: str, frm: str, **kwargs) -> None:
        """
        Replaces existing IO with new one.

        If the kwargs for byteorder and defaultvalue are not specified,
        the system takes the data from the replaced IO.

        Only a single format character 'frm' may be passed. From this,
        the required length in bytes is calculated and the data type
        is determined. Possible values are:
        - Bits / Bytes: ?, c, s
        - Integer     : bB, hH, iI, lL, qQ
        - Float       : e, f, d

        An exception is the 's' format. Here, multiple bytes
        can be combined into one long IO. The formatting must be
        '8s' for e.g. 8 bytes - NOT 'ssssssss'!

        If more bytes are needed by the formatting than
        the original IO has, the following IOs will also be
        used and removed.

        :param name: Name of the new input
        :param frm: struct formatting (1 character) or 'NUMBERs' e.g. '8s'
        :param kwargs: Additional parameters

        - bmk: internal designation for IO
        - bit: Registers IO as <class 'bool'> at the specified bit in the byte
        - byteorder: Byteorder for the IO, default=little
        - wordorder: Wordorder is applied before byteorder
        - defaultvalue: Default value for IO
        - event: Register function for event handling
        - delay: Delay in ms for triggering when value remains the same
        - edge: Execute event on RISING, FALLING or BOTH value change
        - as_thread: Executes the event function as RevPiCallback thread
        - prefire: Trigger with current value when mainloop starts

        `<https://docs.python.org/3/library/struct.html#format-characters>`_
        """
        # Create StructIO
        io_new = StructIO(self, name, frm, **kwargs)

        # Insert StructIO into IO list
        self._parentdevice._modio.io._private_register_new_io_object(io_new)

        # Optional Event eintragen
        reg_event = kwargs.get("event", None)
        if reg_event is not None:
            io_new.reg_event(
                reg_event,
                kwargs.get("delay", 0),
                kwargs.get("edge", BOTH),
                kwargs.get("as_thread", False),
            )


class RelaisOutput(IOBase):
    """
    Class for relais outputs to access the cycle counters.

    This class extends the function of <class 'IOBase'> to the function
    'get_cycles' and the property 'cycles' to retrieve the relay cycle
    counters.

    :ref: :class:`IOBase`
    """

    def __init__(self, parentdevice, valuelist, iotype, byteorder, signed):
        """
        Extend <class 'IOBase'> with functions to access cycle counters.

        :ref: :func:`IOBase.__init__(...)`
        """
        super().__init__(parentdevice, valuelist, iotype, byteorder, signed)

        """
        typedef struct SROGetCountersStr
        {
            /* Address of module in current configuration */
            uint8_t i8uAddress;
            uint32_t counter[REVPI_RO_NUM_RELAY_COUNTERS];
        } SROGetCounters;
        """
        # Device position + padding + four counter with 4 byte each
        self.__ioctl_arg_format = "<BIIII"
        self.__ioctl_arg = struct.pack(
            self.__ioctl_arg_format,
            parentdevice._position,
            0,
            0,
            0,
            0,
        )

    def get_switching_cycles(self):
        """
        Get the number of switching cycles from this relay.

        If each relay output is represented as BOOL, this function returns a
        single integer value. If all relays are displayed as a BYTE, this
        function returns a tuple that contains the values of all relay outputs.
        The setting is determined by PiCtory and the selected output variant by
        the RO device.

        This function is only available locally on a Revolution Pi. This
        function cannot be used via RevPiNetIO.

        :return: Integer of switching cycles as single value or tuple of all
        """
        # Using ioctl request K+29 = 19229
        if self._parentdevice._modio._run_on_pi:
            # IOCTL to piControl on the RevPi
            with self._parentdevice._modio._myfh_lck:
                try:
                    ioctl_return_value = ioctl(
                        self._parentdevice._modio._myfh,
                        19229,
                        self.__ioctl_arg,
                    )
                except Exception as e:
                    # If not implemented, we return the max value and set an error
                    ioctl_return_value = b"\xff" * struct.calcsize(self.__ioctl_arg_format)
                    self._parentdevice._modio._gotioerror("rocounter", e)

        elif hasattr(self._parentdevice._modio._myfh, "ioctl"):
            # IOCTL over network
            """
            The ioctl function over the network does not return a value. Only the successful
            execution of the ioctl call is checked and reported back. If a new function has been
            implemented in RevPiPyLoad, the subsequent source code can be activated.

            with self._parentdevice._modio._myfh_lck:
                try:
                    ioctl_return_value = self._parentdevice._modio._myfh.ioctl(
                        19229, self.__ioctl_arg
                    )
                except Exception as e:
                    self._parentdevice._modio._gotioerror("net_rocounter", e)
            """
            raise RuntimeError("Can not be called over network via RevPiNetIO")

        else:
            # Simulate IOCTL on a regular file returns the value of relais index
            ioctl_return_value = self.__ioctl_arg

        if self._bitaddress == -1:
            # Return cycle values of all relais as tuple, if this is a BYTE output
            # Remove fist element, which is the ioctl request value
            return struct.unpack(self.__ioctl_arg_format, ioctl_return_value)[1:]
        else:
            # Return cycle value of just one relais as int, if this is a BOOL output
            # Increase bit-address by 1 to ignore first element, which is the ioctl request value
            return struct.unpack(self.__ioctl_arg_format, ioctl_return_value)[self._bitaddress + 1]

    switching_cycles = property(get_switching_cycles)


class IntRelaisOutput(IntIO, RelaisOutput):
    """
    Class for relais outputs to access the cycle counters.

    This class combines the function of <class 'IntIO'> and
    <class 'RelaisOutput'> to add the function 'get_cycles' and the property
    'cycles' to retrieve the relay cycle counters.

    Since both classes inherit from BaseIO, both __init__ functions are called
    and the logic is combined. In this case, there is only one 'self' object of
    IOBase, which of both classes in inheritance is extended with this.

    :ref: :class:`IOBase`
    """

    pass


class StructIO(IOBase):
    """
    Class for accessing data via a defined struct.

    It provides the values in the desired formatting via struct.
    The struct format value is defined during instantiation.
    """

    __slots__ = (
        "__frm",
        "_parentio_address",
        "_parentio_defaultvalue",
        "_parentio_length",
        "_parentio_name",
        "_wordorder",
    )

    def __init__(self, parentio, name: str, frm: str, **kwargs):
        """
        Creates an IO with struct formatting.

        :param parentio: ParentIO object that will be replaced
        :param name: Name of the new IO
        :param frm: struct formatting (1 character) or 'NUMBERs' e.g. '8s'
        :param kwargs: Additional parameters:
            - bmk: Description for IO
            - bit: Registers IO as <class 'bool'> at specified bit in byte
            - byteorder: Byteorder for IO, default from replaced IO
            - wordorder: Wordorder is applied before byteorder
            - defaultvalue: Default value for IO, default from replaced IO
        """
        # Check struct formatting
        regex = rematch("^([0-9]*s|[cbB?hHiIlLqQefd])$", frm)

        if regex is not None:
            # Check and take over byteorder
            byteorder = kwargs.get("byteorder", parentio._byteorder)
            if byteorder not in ("little", "big"):
                raise ValueError("byteorder must be 'little' or 'big'")
            bofrm = "<" if byteorder == "little" else ">"
            self._wordorder = kwargs.get("wordorder", None)

            # Remember parent name for export
            self._parentio_name = parentio._name

            if frm == "?":
                if self._wordorder:
                    raise ValueError("you can not use wordorder for bit based ios")
                bitaddress = kwargs.get("bit", 0)
                max_bits = parentio._length * 8
                if not (0 <= bitaddress < max_bits):
                    raise ValueError(
                        "bitaddress must be a value between 0 and {0}".format(max_bits - 1)
                    )
                bitlength = 1

                # Bitwise replacement requires this information additionally
                if parentio._byteorder == byteorder:
                    self._parentio_defaultvalue = parentio._defaultvalue
                else:
                    self._parentio_defaultvalue = parentio._defaultvalue[::-1]
                self._parentio_address = parentio.address
                self._parentio_length = parentio._length
            else:
                byte_length = struct.calcsize(bofrm + frm)
                bitaddress = ""
                bitlength = byte_length * 8
                self._parentio_address = None
                self._parentio_defaultvalue = None
                self._parentio_length = None
                if self._wordorder:
                    if self._wordorder not in ("little", "big"):
                        raise ValueError("wordorder must be 'little' or 'big'")
                    if byte_length % 2 != 0:
                        raise ValueError(
                            "the byte length of new io must must be even to use wordorder"
                        )

            # [name,default,anzbits,adressbyte,export,adressid,bmk,bitaddress]
            valuelist = [
                name,
                # May only be None for StructIO, is only calculated then
                kwargs.get("defaultvalue", None),
                bitlength,
                parentio._slc_address.start,
                False,
                str(parentio._slc_address.start).rjust(4, "0"),
                kwargs.get("bmk", ""),
                bitaddress,
            ]
        else:
            raise ValueError(
                "parameter frm has to be a single sign from [cbB?hHiIlLqQefd] "
                "or 'COUNTs' e.g. '8s'"
            )

        # Instantiate base class
        super().__init__(
            parentio._parentdevice, valuelist, parentio._iotype, byteorder, frm == frm.lower()
        )
        self.__frm = bofrm + frm
        if "export" in kwargs:
            # Use export property to remember given value for export
            self.export = kwargs["export"]
        else:
            # User could change parent IO settings before replace to force
            # export, so use parent settings for the new IO
            self._export = parentio._export

        # Check space for new IO
        if not (
            self._slc_address.start >= parentio._parentdevice._dict_slc[parentio._iotype].start
            and self._slc_address.stop <= parentio._parentdevice._dict_slc[parentio._iotype].stop
        ):
            raise BufferError("registered value does not fit process image scope")

    def __call__(self, value=None):
        """
        Get or set the structured IO value using function call syntax.

        Handles byte and word order conversion based on configuration.

        :param value: If None, returns current value unpacked using struct
            format; otherwise packs and sets the value
        :return: Current IO value unpacked according to struct format when
            called without arguments
        """
        if value is None:
            # Inline get_structdefaultvalue()
            if self._bitshift:
                return self.get_value()
            if self._wordorder == "little" and self._length > 2:
                return struct.unpack(
                    self.__frm,
                    self._swap_word_order(self.get_value()),
                )[0]
            return struct.unpack(self.__frm, self.get_value())[0]
        else:
            # Inline set_structvalue()
            if self._bitshift:
                self.set_value(value)
            elif self._wordorder == "little" and self._length > 2:
                self.set_value(self._swap_word_order(struct.pack(self.__frm, value)))
            else:
                self.set_value(struct.pack(self.__frm, value))

    def _get_frm(self) -> str:
        """
        Retrieves the struct formatting.

        :return: struct formatting
        """
        return self.__frm[1:]

    def _get_signed(self) -> bool:
        """
        Retrieves whether the value should be treated as signed.

        :return: True if signed
        """
        return self._signed

    @staticmethod
    def _swap_word_order(bytes_to_swap) -> bytes:
        """
        Swap word order of given bytes.

        :param bytes_to_swap: Already length checked bytes to swap words
        :return: Bytes with swapped word order
        """
        array_length = len(bytes_to_swap)
        swap_array = bytearray(bytes_to_swap)
        for i in range(0, array_length // 2, 2):
            swap_array[-i - 2 : array_length - i], swap_array[i : i + 2] = (
                swap_array[i : i + 2],
                swap_array[-i - 2 : array_length - i],
            )
        return bytes(swap_array)

    def get_structdefaultvalue(self):
        """
        Returns the default value with struct formatting.

        :return: Default value of struct formatting type
        """
        if self._bitshift:
            return self._defaultvalue
        if self._wordorder == "little" and self._length > 2:
            return struct.unpack(
                self.__frm,
                self._swap_word_order(self._defaultvalue),
            )[0]
        return struct.unpack(self.__frm, self._defaultvalue)[0]

    def get_wordorder(self) -> str:
        """
        Returns the wordorder for this IO.

        :return: "little", "big" or "ignored"
        """
        return self._wordorder or "ignored"

    def get_structvalue(self):
        """
        Returns the value with struct formatting.

        :return: Value of struct formatting type
        """
        if self._bitshift:
            return self.get_value()
        if self._wordorder == "little" and self._length > 2:
            return struct.unpack(
                self.__frm,
                self._swap_word_order(self.get_value()),
            )[0]
        return struct.unpack(self.__frm, self.get_value())[0]

    def set_structvalue(self, value):
        """
        Sets the value with struct formatting.

        :param value: Value of struct formatting type
        """
        if self._bitshift:
            self.set_value(value)
        elif self._wordorder == "little" and self._length > 2:
            self.set_value(self._swap_word_order(struct.pack(self.__frm, value)))
        else:
            self.set_value(struct.pack(self.__frm, value))

    defaultvalue = property(get_structdefaultvalue)
    frm = property(_get_frm)
    signed = property(_get_signed)
    value = property(get_structvalue, set_structvalue)
    wordorder = property(get_wordorder)


class MemIO(IOBase):
    """
    Creates an IO for the memory values in piCtory.

    This type is only intended for read access and can return various
    data types via .value. This also provides access to strings that
    are assigned in piCtory.
    """

    def get_variantvalue(self):
        """
        Get the default value as either string or integer based on bit length.

        For values > 64 bits, returns as decoded string. Otherwise returns as integer.

        :return: Default value as string (if > 64 bits) or integer
        """
        val = bytes(self._defaultvalue)

        if self._bitlength > 64:
            # STRING
            try:
                val = val.strip(b"\x00").decode()
            except Exception:
                pass
            return val

        else:
            # INT
            return int.from_bytes(val, self._byteorder, signed=self._signed)

    defaultvalue = property(get_variantvalue)
    value = property(get_variantvalue)

# -*- coding: utf-8 -*-
"""Module for managing devices."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2023 Sven Sager"
__license__ = "LGPLv2"

import warnings
from struct import unpack
from threading import Event, Lock, Thread

from ._internal import INP, OUT, MEM, PROCESS_IMAGE_SIZE
from .helper import ProcimgWriter
from .io import IOBase, IntIO, IntIOCounter, IntIOReplaceable, MemIO, RelaisOutput, IntRelaisOutput
from .pictory import ProductType


class DeviceList(object):
    """Base class for direct access to device objects."""

    def __init__(self):
        """Init DeviceList class."""
        self.__dict_position = {}

    def __contains__(self, key):
        """
        Checks if device exists.

        :param key: DeviceName <class 'str'> / Position number <class 'int'>
        :return: True if device exists
        """
        if type(key) == int:
            return key in self.__dict_position
        elif type(key) == str:
            return hasattr(self, key)
        else:
            return key in self.__dict_position.values()

    def __delattr__(self, key, delcomplete=True):
        """
        Removes specified device.

        :param key: Device to remove
        :param delcomplete: If True, device will be removed completely
        """
        if delcomplete:
            # Find device
            if type(key) == int:
                dev_del = self.__dict_position[key]
                key = dev_del._name
            else:
                dev_del = getattr(self, key)

            # Cleanup jobs
            dev_del.autorefresh(False)
            for io in dev_del:
                delattr(dev_del._modio.io, io._name)

            # Delete device from dict
            del self.__dict_position[dev_del._position]

        if hasattr(self, key):
            object.__delattr__(self, key)

    def __delitem__(self, key):
        """
        Removes device at specified position.

        :param key: Device position to remove
        """
        if isinstance(key, Device):
            key = key._position
        self.__delattr__(key)

    def __getitem__(self, key):
        """
        Returns specified device.

        :param key: DeviceName <class 'str'> / Position number <class 'int'>
        :return: Found <class 'Device'> object
        """
        if type(key) == int:
            if key not in self.__dict_position:
                raise IndexError("no device on position {0}".format(key))
            return self.__dict_position[key]
        else:
            return getattr(self, key)

    def __iter__(self):
        """
        Returns iterator of all devices.

        The order is sorted by position in the process image and not
        by position number (this corresponds to the positioning from piCtory)!

        :return: <class 'iter'> of all devices
        """
        for dev in sorted(self.__dict_position, key=lambda key: self.__dict_position[key]._offset):
            yield self.__dict_position[dev]

    def __len__(self):
        """
        Returns number of devices.

        :return: Number of devices"""
        return len(self.__dict_position)

    def __setattr__(self, key, value):
        """
        Sets attributes only if device.

        :param key: Attribute name
        :param value: Attribute object
        """
        if isinstance(value, Device):
            object.__setattr__(self, key, value)
            self.__dict_position[value._position] = value
        elif key == "_DeviceList__dict_position":
            object.__setattr__(self, key, value)


class Device(object):
    """
    Base class for all device objects.

    The base functionality generates all IOs upon instantiation and
    extends the process image buffer by the required bytes. It manages
    its process image buffer and ensures the updating of IO values.
    """

    __slots__ = (
        "__my_io_list",
        "_ba_devdata",
        "_ba_datacp",
        "_dict_events",
        "_filelock",
        "_modio",
        "_name",
        "_offset",
        "_position",
        "_producttype",
        "_selfupdate",
        "_slc_devoff",
        "_slc_inp",
        "_slc_inpoff",
        "_slc_mem",
        "_slc_memoff",
        "_slc_out",
        "_slc_outoff",
        "_shared_procimg",
        "_shared_write",
        "bmk",
        "catalognr",
        "comment",
        "extend",
        "guid",
        "id",
        "inpvariant",
        "outvariant",
        "type",
    )

    def __init__(self, parentmodio, dict_device, simulator=False):
        """
        Instantiation of the Device class.

        :param parentmodio: RevpiModIO parent object
        :param dict_device: <class 'dict'> for this device from piCtory
        :param simulator: Loads the module as simulator and swaps IOs
        """
        self._modio = parentmodio

        self._ba_devdata = bytearray()
        self._ba_datacp = bytearray()  # Copy for event detection
        self._dict_events = {}
        self._filelock = Lock()
        self.__my_io_list = []
        self._selfupdate = False
        self._shared_procimg = False
        self._shared_write = set()

        # Value assignment from dict_device
        self._name = dict_device.get("name")
        self._offset = int(dict_device.get("offset"))
        self._position = int(dict_device.get("position"))
        self._producttype = int(dict_device.get("productType"))

        # Offset-Check for broken piCtory configuration
        if self._offset < parentmodio.length:
            warnings.warn(
                "Device offset ERROR in piCtory configuration! Offset of '{0}' "
                "must be {1} but is {2} - Overlapping devices overwrite the "
                "same memory, which has unpredictable effects!!!"
                "".format(self._name, parentmodio.length, self._offset),
                Warning,
            )
        # Create IOM objects and store addresses in SLCs
        if simulator:
            self._slc_inp = self._buildio(dict_device.get("out"), INP)
            self._slc_out = self._buildio(dict_device.get("inp"), OUT)
        else:
            self._slc_inp = self._buildio(dict_device.get("inp"), INP)
            self._slc_out = self._buildio(dict_device.get("out"), OUT)
        self._slc_mem = self._buildio(dict_device.get("mem"), MEM)

        # Calculate SLCs with offset
        self._slc_devoff = slice(self._offset, self._offset + self.length)
        self._slc_inpoff = slice(
            self._slc_inp.start + self._offset,
            self._slc_inp.stop + self._offset,
        )
        self._slc_outoff = slice(
            self._slc_out.start + self._offset,
            self._slc_out.stop + self._offset,
        )
        self._slc_memoff = slice(
            self._slc_mem.start + self._offset,
            self._slc_mem.stop + self._offset,
        )

        # Attach all remaining attributes to class
        self.bmk = dict_device.get("bmk", "")
        """Component designator from piCtory configuration."""
        self.catalognr = dict_device.get("catalogNr", "")
        """Catalog number of the device (deprecated)."""
        self.comment = dict_device.get("comment", "")
        """Comment text from piCtory configuration."""
        self.extend = dict_device.get("extend", {})
        """Extended configuration data from piCtory."""
        self.guid = dict_device.get("GUID", "")
        """Global unique identifier of the device."""
        self.id = dict_device.get("id", "")
        """Device identifier from piCtory configuration."""
        self.inpvariant = dict_device.get("inpVariant", 0)
        """Input variant number."""
        self.outvariant = dict_device.get("outVariant", 0)
        """Output variant number."""
        self.type = dict_device.get("type", "")
        """Device position type string."""

        # Perform special configuration from derived classes
        self._devconfigure()

        # Update IO list for fast index access
        self._update_my_io_list()

    def __bytes__(self):
        """
        Returns all device data as <class 'bytes'>.

        :return: Device data as <class 'bytes'>
        """
        return bytes(self._ba_devdata)

    def __contains__(self, key):
        """
        Checks if IO is on this device.

        :param key: IO-Name <class 'str'> / IO-Bytenummer <class 'int'>
        :return: True if IO is present on device
        """
        if isinstance(key, IOBase):
            # Conversion for key
            key = key._name

        if type(key) == int:
            if key in self._modio.io:
                for io in self._modio.io[key]:
                    if io is not None and io._parentdevice == self:
                        return True
            return False
        else:
            return key in self._modio.io and getattr(self._modio.io, key)._parentdevice == self

    def __getitem__(self, key):
        """
        Returns IO at specified position.

        :param key: Index of the IO on the device as <class 'int'>
        :return: Found IO object
        """
        return self.__my_io_list[key]

    def __int__(self):
        """
        Returns the position on the RevPi bus.

        :return: Position number
        """
        return self._position

    def __iter__(self):
        """
        Returns iterator of all IOs.

        :return: <class 'iter'> of all IOs
        """
        return self.__getioiter(self._slc_devoff, None)

    def __len__(self):
        """
        Returns number of bytes occupied by this device.

        :return: <class 'int'>
        """
        return len(self._ba_devdata)

    def __str__(self):
        """
        Returns the name of the device.

        :return: Device name
        """
        return self._name

    def __getioiter(self, ioslc: slice, export):
        """
        Returns <class 'iter'> with all IOs.

        :param ioslc: IO section <class 'slice'>
        :param export: Filter for 'Export' flag in piCtory
        :return: IOs as Iterator
        """
        for lst_io in self._modio.io[ioslc]:
            for io in lst_io:
                if io is not None and (export is None or io.export == export):
                    yield io

    def _buildio(self, dict_io: dict, iotype: int) -> slice:
        """
        Creates the IOs for this device from the piCtory list.

        :param dict_io: <class 'dict'> object from piCtory configuration
        :param iotype: <class 'int'> value
        :return: <class 'slice'> with start and stop position of these IOs
        """
        if len(dict_io) <= 0:
            return slice(0, 0)

        int_min, int_max = PROCESS_IMAGE_SIZE, 0
        for key in sorted(dict_io, key=lambda x: int(x)):
            # Create new IO
            if iotype == MEM:
                # Memory setting
                io_new = MemIO(self, dict_io[key], iotype, "little", False)
            elif isinstance(self, RoModule) and dict_io[key][3] == "1":
                # Relays of RO are on device address "1" and has a cycle counter
                if dict_io[key][7]:
                    # Each relais output has a single bit
                    io_new = RelaisOutput(self, dict_io[key], iotype, "little", False)
                else:
                    # All relais outputs are in one byte
                    io_new = IntRelaisOutput(self, dict_io[key], iotype, "little", False)

            elif bool(dict_io[key][7]):
                # Use IOBase for bit values
                io_new = IOBase(self, dict_io[key], iotype, "little", False)
            elif isinstance(self, DioModule) and dict_io[key][3] in self._lst_counter:
                # Counter IO on a DI or DIO
                io_new = IntIOCounter(
                    self._lst_counter.index(dict_io[key][3]),
                    self,
                    dict_io[key],
                    iotype,
                    "little",
                    False,
                )
            elif isinstance(self, Gateway):
                # Create replaceable IOs
                io_new = IntIOReplaceable(self, dict_io[key], iotype, "little", False)
            else:
                io_new = IntIO(
                    self,
                    dict_io[key],
                    iotype,
                    "little",
                    # Set signed to True for AIO (103)
                    self._producttype == ProductType.AIO,
                )

            if io_new.address < self._modio.length:
                warnings.warn(
                    "IO {0} is not in the device offset and will be ignored".format(io_new.name),
                    Warning,
                )
            else:
                # Register IO
                self._modio.io._private_register_new_io_object(io_new)

            # Determine smallest and largest memory address
            if io_new._slc_address.start < int_min:
                int_min = io_new._slc_address.start
            if io_new._slc_address.stop > int_max:
                int_max = io_new._slc_address.stop

        self._ba_devdata += bytearray(int_max - int_min)
        return slice(int_min, int_max)

    def _devconfigure(self):
        """Function to override in derived classes."""
        pass

    def _get_offset(self) -> int:
        """
        Returns the device offset in the process image.

        :return: Device offset
        """
        return self._offset

    def _get_producttype(self) -> int:
        """
        Returns the product type of the device.

        :return: Device product type
        """
        return self._producttype

    def _update_my_io_list(self) -> None:
        """Creates a new IO list for fast access."""
        self.__my_io_list = list(self.__iter__())

    def autorefresh(self, activate=True) -> None:
        """
        Registers this device for automatic synchronization.

        :param activate: Default True adds device to synchronization
        """
        if activate and self not in self._modio._lst_refresh:
            # Read data directly when adding!
            self._modio.readprocimg(self)

            # Create data copy
            with self._filelock:
                self._ba_datacp = self._ba_devdata[:]

            self._selfupdate = True

            # Safely insert into list
            with self._modio._imgwriter.lck_refresh:
                self._modio._lst_refresh.append(self)

            # Start thread if it is not yet running
            if not self._modio._imgwriter.is_alive():
                # Save old settings
                imgrefresh = self._modio._imgwriter.refresh

                # Create ImgWriter with old settings
                self._modio._imgwriter = ProcimgWriter(self._modio)
                self._modio._imgwriter.refresh = imgrefresh
                self._modio._imgwriter.start()

        elif not activate and self in self._modio._lst_refresh:
            # Safely remove from list
            with self._modio._imgwriter.lck_refresh:
                self._modio._lst_refresh.remove(self)
            self._selfupdate = False

            # Terminate if no more devices are in the list
            if len(self._modio._lst_refresh) == 0:
                self._modio._imgwriter.stop()

            # Write data once more when removing
            if not self._modio._monitoring:
                self._modio.writeprocimg(self)

    def get_allios(self, export=None) -> list:
        """
        Returns a list of all inputs and outputs, no MEMs.

        If parameter 'export' remains None, all inputs and outputs will be
        returned. If 'export' is set to True/False, only inputs
        and outputs will be returned for which the 'Export' value in piCtory
        matches.

        :param export: Only in-/outputs with specified 'Export' value in piCtory
        :return: <class 'list'> Input and Output, no MEMs
        """
        return list(self.__getioiter(slice(self._slc_inpoff.start, self._slc_outoff.stop), export))

    def get_inputs(self, export=None) -> list:
        """
        Returns a list of all inputs.

        If parameter 'export' remains None, all inputs will be returned.
        If 'export' is set to True/False, only inputs will be returned
        for which the 'Export' value in piCtory matches.

        :param export: Only inputs with specified 'Export' value in piCtory
        :return: <class 'list'> Inputs
        """
        return list(self.__getioiter(self._slc_inpoff, export))

    def get_outputs(self, export=None) -> list:
        """
        Returns a list of all outputs.

        If parameter 'export' remains None, all outputs will be returned.
        If 'export' is set to True/False, only outputs
        returned, for which the value 'Export' in piCtory matches.

        :param export: Only outputs with specified 'Export' value in piCtory
        :return: <class 'list'> Outputs
        """
        return list(self.__getioiter(self._slc_outoff, export))

    def get_memories(self, export=None) -> list:
        """
        Returns a list of all memory objects.

        If parameter 'export' remains None, all mems will be returned.
        If 'export' is set to True/False, only mems will be returned
        for which the 'Export' value in piCtory matches.

        :param export: Only mems with specified 'Export' value in piCtory
        :return: <class 'list'> Mems
        """
        return list(self.__getioiter(self._slc_memoff, export))

    def readprocimg(self) -> bool:
        """
        Read all inputs for this device from process image.

        :return: True if successfully executed
        :ref: :func:`revpimodio2.modio.RevPiModIO.readprocimg()`
        """
        return self._modio.readprocimg(self)

    def setdefaultvalues(self) -> None:
        """
        Set all output buffers for this device to default values.

        :return: True if successfully executed
        :ref: :func:`revpimodio2.modio.RevPiModIO.setdefaultvalues()`
        """
        self._modio.setdefaultvalues(self)

    def shared_procimg(self, activate: bool) -> None:
        """
        Activate sharing of process image just for this device.

        :param activate: Set True to activate process image sharing
        """
        with self._filelock:
            self._shared_write.clear()
        self._shared_procimg = True if activate else False

    def syncoutputs(self) -> bool:
        """
        Read all outputs in process image for this device.

        :return: True if successfully executed
        :ref: :func:`revpimodio2.modio.RevPiModIO.syncoutputs()`
        """
        return self._modio.syncoutputs(self)

    def writeprocimg(self) -> bool:
        """
        Write all outputs of this device to process image.

        :return: True if successfully executed
        :ref: :func:`revpimodio2.modio.RevPiModIO.writeprocimg()`
        """
        return self._modio.writeprocimg(self)

    length = property(__len__)
    name = property(__str__)
    offset = property(_get_offset)
    position = property(__int__)
    producttype = property(_get_producttype)


class Base(Device):
    """Class for all base devices like Core / Connect etc."""

    __slots__ = ()

    pass


class GatewayMixin:
    """Mixin class providing piGate module detection functionality."""

    @property
    def leftgate(self) -> bool:
        """
        Status bit indicating a piGate module is connected on the left side.

        :return: True if piGate left exists
        """
        return bool(int.from_bytes(self._ba_devdata[self._slc_statusbyte], byteorder="little") & 16)

    @property
    def rightgate(self) -> bool:
        """
        Status bit indicating a piGate module is connected on the right side.

        :return: True if piGate right exists
        """
        return bool(int.from_bytes(self._ba_devdata[self._slc_statusbyte], byteorder="little") & 32)


class ModularBase(Base):
    """
    Class for all modular base devices like Core / Connect etc..

    Provides functions for the status.
    """

    __slots__ = (
        "_slc_cycle",
        "_slc_errorcnt",
        "_slc_statusbyte",
        "_slc_temperature",
        "_slc_errorlimit1",
        "_slc_errorlimit2",
        "_slc_frequency",
        "_slc_led",
    )

    def __errorlimit(self, slc_io: slice, errorlimit: int) -> None:
        """
        Manages writing the error limits.

        :param slc_io: Byte Slice of the ErrorLimit
        :return: Current ErrorLimit or None if not available
        """
        if 0 <= errorlimit <= 65535:
            self._ba_devdata[slc_io] = errorlimit.to_bytes(2, byteorder="little")
        else:
            raise ValueError("errorlimit value must be between 0 and 65535")

    def _get_status(self) -> int:
        """
        Returns the RevPi Core status.

        :return: Status as <class 'int'>
        """
        return int.from_bytes(self._ba_devdata[self._slc_statusbyte], byteorder="little")

    @property
    def picontrolrunning(self) -> bool:
        """
        Status bit indicating piControl driver is running.

        :return: True if driver is running
        """
        return bool(int.from_bytes(self._ba_devdata[self._slc_statusbyte], byteorder="little") & 1)

    @property
    def unconfdevice(self) -> bool:
        """
        Status bit for an IO module not configured with piCtory.

        :return: True if IO module is not configured
        """
        return bool(int.from_bytes(self._ba_devdata[self._slc_statusbyte], byteorder="little") & 2)

    @property
    def missingdeviceorgate(self) -> bool:
        """
        Status bit for an IO module missing or piGate configured.

        :return: True if IO module is missing or piGate is configured
        """
        return bool(int.from_bytes(self._ba_devdata[self._slc_statusbyte], byteorder="little") & 4)

    @property
    def overunderflow(self) -> bool:
        """
        Status bit: Module occupies more or less memory than configured.

        :return: True if wrong memory is occupied
        """
        return bool(int.from_bytes(self._ba_devdata[self._slc_statusbyte], byteorder="little") & 8)

    @property
    def iocycle(self) -> int:
        """
        Returns cycle time of process image synchronization.

        :return: Cycle time in ms (-1 if not available)
        """
        return (
            -1
            if self._slc_cycle is None
            else int.from_bytes(self._ba_devdata[self._slc_cycle], byteorder="little")
        )

    @property
    def temperature(self) -> int:
        """
        Returns CPU temperature.

        :return: CPU temperature in Celsius (-273 if not available)
        """
        return (
            -273
            if self._slc_temperature is None
            else int.from_bytes(self._ba_devdata[self._slc_temperature], byteorder="little")
        )

    @property
    def frequency(self) -> int:
        """
        Returns CPU clock frequency.

        :return: CPU clock frequency in MHz (-1 if not available)
        """
        return (
            -1
            if self._slc_frequency is None
            else int.from_bytes(self._ba_devdata[self._slc_frequency], byteorder="little") * 10
        )

    @property
    def ioerrorcount(self) -> int:
        """
        Returns error count on RS485 piBridge bus.

        :return: Number of errors of the piBridge (-1 if not available)
        """
        return (
            -1
            if self._slc_errorcnt is None
            else int.from_bytes(self._ba_devdata[self._slc_errorcnt], byteorder="little")
        )

    @property
    def errorlimit1(self) -> int:
        """
        Returns RS485 ErrorLimit1 value.

        :return: Current value for ErrorLimit1 (-1 if not available)
        """
        return (
            -1
            if self._slc_errorlimit1 is None
            else int.from_bytes(self._ba_devdata[self._slc_errorlimit1], byteorder="little")
        )

    @errorlimit1.setter
    def errorlimit1(self, value: int) -> None:
        """
        Sets RS485 ErrorLimit1 to new value.

        :param value: New ErrorLimit1 value
        """
        if self._slc_errorlimit1 is None:
            raise RuntimeError("selected core item in piCtory does not support errorlimit1")
        else:
            self.__errorlimit(self._slc_errorlimit1, value)

    @property
    def errorlimit2(self) -> int:
        """
        Returns RS485 ErrorLimit2 value.

        :return: Current value for ErrorLimit2 (-1 if not available)
        """
        return (
            -1
            if self._slc_errorlimit2 is None
            else int.from_bytes(self._ba_devdata[self._slc_errorlimit2], byteorder="little")
        )

    @errorlimit2.setter
    def errorlimit2(self, value: int) -> None:
        """
        Sets RS485 ErrorLimit2 to new value.

        :param value: New ErrorLimit2 value
        """
        if self._slc_errorlimit2 is None:
            raise RuntimeError("selected core item in piCtory does not support errorlimit2")
        else:
            self.__errorlimit(self._slc_errorlimit2, value)

    status = property(_get_status)


class Core(ModularBase, GatewayMixin):
    """
    Class for the RevPi Core.

    Provides functions for the LEDs and the status.
    """

    __slots__ = "a1green", "a1red", "a2green", "a2red", "wd"

    def __setattr__(self, key, value):
        """Prevents overwriting the LEDs."""
        if hasattr(self, key) and key in ("a1green", "a1red", "a2green", "a2red", "wd"):
            raise AttributeError("direct assignment is not supported - use .value Attribute")
        else:
            object.__setattr__(self, key, value)

    def _devconfigure(self) -> None:
        """Prepare Core class."""
        super()._devconfigure()

        # Static IO links depending on Core variant
        # 2 Byte = Core1.0
        self._slc_statusbyte = slice(0, 1)
        self._slc_led = slice(1, 2)

        self._slc_cycle = None
        self._slc_temperature = None
        self._slc_frequency = None
        self._slc_errorcnt = None
        self._slc_errorlimit1 = None
        self._slc_errorlimit2 = None
        if self.length == 9:
            #  9 Byte = Core1.1
            self._slc_cycle = slice(1, 2)
            self._slc_errorcnt = slice(2, 4)
            self._slc_led = slice(4, 5)
            self._slc_errorlimit1 = slice(5, 7)
            self._slc_errorlimit2 = slice(7, 9)
        elif self.length == 11:
            # 11 Byte = Core1.2 / Connect
            self._slc_cycle = slice(1, 2)
            self._slc_errorcnt = slice(2, 4)
            self._slc_temperature = slice(4, 5)
            self._slc_frequency = slice(5, 6)
            self._slc_led = slice(6, 7)
            self._slc_errorlimit1 = slice(7, 9)
            self._slc_errorlimit2 = slice(9, 11)

        # Check export flags (Byte or Bit)
        lst_led = self._modio.io[self._slc_devoff][self._slc_led.start]
        if len(lst_led) == 8:
            exp_a1green = lst_led[0].export
            exp_a1red = lst_led[1].export
            exp_a2green = lst_led[2].export
            exp_a2red = lst_led[3].export
        else:
            exp_a1green = lst_led[0].export
            exp_a1red = exp_a1green
            exp_a2green = exp_a1green
            exp_a2red = exp_a1green

        # Create actual IOs
        self.a1green = IOBase(
            self,
            ["core.a1green", 0, 1, self._slc_led.start, exp_a1green, None, "LED_A1_GREEN", "0"],
            OUT,
            "little",
            False,
        )
        """LED A1 green."""
        self.a1red = IOBase(
            self,
            ["core.a1red", 0, 1, self._slc_led.start, exp_a1red, None, "LED_A1_RED", "1"],
            OUT,
            "little",
            False,
        )
        """LED A1 red."""
        self.a2green = IOBase(
            self,
            ["core.a2green", 0, 1, self._slc_led.start, exp_a2green, None, "LED_A2_GREEN", "2"],
            OUT,
            "little",
            False,
        )
        """LED A2 green."""
        self.a2red = IOBase(
            self,
            ["core.a2red", 0, 1, self._slc_led.start, exp_a2red, None, "LED_A2_RED", "3"],
            OUT,
            "little",
            False,
        )
        """LED A2 red."""

        # Watchdog einrichten (Core=soft / Connect=soft/hard)
        self.wd = IOBase(
            self,
            ["core.wd", 0, 1, self._slc_led.start, False, None, "WatchDog", "7"],
            OUT,
            "little",
            False,
        )
        """Watchdog bit."""

    def _get_leda1(self) -> int:
        """
        Returns the state of LED A1 from the Core.

        :return: 0=off, 1=green, 2=red
        """
        # 0b00000011 = 3
        return self._ba_devdata[self._slc_led.start] & 3

    def _get_leda2(self) -> int:
        """
        Returns the state of LED A2 from the Core.

        :return: 0=off, 1=green, 2=red
        """
        # 0b00001100 = 12
        return (self._ba_devdata[self._slc_led.start] & 12) >> 2

    def _set_leda1(self, value: int) -> None:
        """
        Sets the state of LED A1 from the Core.

        :param value: 0=off, 1=green, 2=red
        """
        if 0 <= value <= 3:
            self.a1green(bool(value & 1))
            self.a1red(bool(value & 2))
        else:
            raise ValueError("led status must be between 0 and 3")

    def _set_leda2(self, value: int) -> None:
        """
        Sets the state of LED A2 from the Core.

        :param value: 0=off, 1=green, 2=red
        """
        if 0 <= value <= 3:
            self.a2green(bool(value & 1))
            self.a2red(bool(value & 2))
        else:
            raise ValueError("led status must be between 0 and 3")

    def wd_toggle(self):
        """Toggle watchdog bit to prevent a timeout."""
        self.wd.value = not self.wd.value

    A1 = property(_get_leda1, _set_leda1)
    A2 = property(_get_leda2, _set_leda2)


class Connect(Core):
    """Class for the RevPi Connect.

    Provides functions for the LEDs, watchdog and the status.
    """

    __slots__ = "__evt_wdtoggle", "__th_wdtoggle", "a3green", "a3red", "x2in", "x2out"

    def __setattr__(self, key, value):
        """Prevents overwriting the special IOs."""
        if hasattr(self, key) and key in ("a3green", "a3red", "x2in", "x2out"):
            raise AttributeError("direct assignment is not supported - use .value Attribute")
        super(Connect, self).__setattr__(key, value)

    def __wdtoggle(self) -> None:
        """Automatically toggle WD output every 10 seconds."""
        while not self.__evt_wdtoggle.wait(10):
            self.wd.value = not self.wd.value

    def _devconfigure(self) -> None:
        """Prepare Connect class."""
        super()._devconfigure()

        self.__evt_wdtoggle = Event()
        self.__th_wdtoggle = None

        # Check export flags (Byte or Bit)
        lst_myios = self._modio.io[self._slc_devoff]
        lst_led = lst_myios[self._slc_led.start]
        if len(lst_led) == 8:
            exp_a3green = lst_led[4].export
            exp_a3red = lst_led[5].export
            exp_x2out = lst_led[6].export
            exp_wd = lst_led[7].export
        else:
            exp_a3green = lst_led[0].export
            exp_a3red = exp_a3green
            exp_x2out = exp_a3green
            exp_wd = exp_a3green
        lst_status = lst_myios[self._slc_statusbyte.start]
        if len(lst_status) == 8:
            exp_x2in = lst_status[6].export
        else:
            exp_x2in = lst_status[0].export

        # Create actual IOs
        self.a3green = IOBase(
            self,
            ["core.a3green", 0, 1, self._slc_led.start, exp_a3green, None, "LED_A3_GREEN", "4"],
            OUT,
            "little",
            False,
        )
        """LED A3 green."""
        self.a3red = IOBase(
            self,
            ["core.a3red", 0, 1, self._slc_led.start, exp_a3red, None, "LED_A3_RED", "5"],
            OUT,
            "little",
            False,
        )
        """LED A3 red."""

        # Create IO objects for WD and X2 in/out
        self.x2in = IOBase(
            self,
            ["core.x2in", 0, 1, self._slc_statusbyte.start, exp_x2in, None, "Connect_X2_IN", "6"],
            INP,
            "little",
            False,
        )
        """Digital input on X2 connector."""
        self.x2out = IOBase(
            self,
            ["core.x2out", 0, 1, self._slc_led.start, exp_x2out, None, "Connect_X2_OUT", "6"],
            OUT,
            "little",
            False,
        )
        """Digital output on X2 connector."""

        # Export hardware watchdog to use it with other systems
        self.wd._export = int(exp_wd)  # Do this without mrk for export!

    def _get_leda3(self) -> int:
        """
        Returns the state of LED A3 of the Connect.

        :return: 0=off, 1=green, 2=red
        """
        # 0b00110000 = 48
        return (self._ba_devdata[self._slc_led.start] & 48) >> 4

    def _get_wdtoggle(self) -> bool:
        """
        Retrieves the automatic watchdog toggle status.

        :return: True if automatic watchdog toggle is active
        """
        return self.__th_wdtoggle is not None and self.__th_wdtoggle.is_alive()

    def _set_leda3(self, value: int) -> None:
        """
        Sets the state of LED A3 on the Connect.

        :param: value 0=off, 1=green, 2=red
        """
        if 0 <= value <= 3:
            self.a3green(bool(value & 1))
            self.a3red(bool(value & 2))
        else:
            raise ValueError("led status must be between 0 and 3")

    def _set_wdtoggle(self, value: bool) -> None:
        """
        Sets the automatic watchdog toggle.

        If this value is set to True, the necessary bit to toggle the
        watchdog is switched between True and False every 10 seconds in
        the background.
        This bit is automatically written to the process image with
        autorefresh=True.

        IMPORTANT: If autorefresh=False, .writeprocimg() must be called
        cyclically to write the value to the process image!!!

        :param value: True to activate, False to terminate
        """
        if self._modio._monitoring:
            raise RuntimeError("can not toggle watchdog, while system is in monitoring mode")
        if self._modio._simulator:
            raise RuntimeError("can not toggle watchdog, while system is in simulator mode")

        if not value:
            self.__evt_wdtoggle.set()

        elif not self._get_wdtoggle():
            # Create watchdog toggler
            self.__evt_wdtoggle.clear()
            self.__th_wdtoggle = Thread(target=self.__wdtoggle, daemon=True)
            self.__th_wdtoggle.start()

    A3 = property(_get_leda3, _set_leda3)
    wdautotoggle = property(_get_wdtoggle, _set_wdtoggle)


class ModularBaseConnect_4_5(ModularBase):
    """Class for overlapping functions of Connect 4/5."""

    __slots__ = (
        "_slc_output",
        "a1red",
        "a1green",
        "a1blue",
        "a2red",
        "a2green",
        "a2blue",
        "a3red",
        "a3green",
        "a3blue",
        "a4red",
        "a4green",
        "a4blue",
        "a5red",
        "a5green",
        "a5blue",
    )

    def __setattr__(self, key, value):
        """Prevents overwriting the special IOs."""
        if hasattr(self, key) and key in (
            "a1red",
            "a1green",
            "a1blue",
            "a2red",
            "a2green",
            "a2blue",
            "a3red",
            "a3green",
            "a3blue",
            "a4red",
            "a4green",
            "a4blue",
            "a5red",
            "a5green",
            "a5blue",
        ):
            raise AttributeError("direct assignment is not supported - use .value Attribute")
        super().__setattr__(key, value)

    def __led_calculator(self, led_value: int) -> int:
        """
        Calculate the LED value of Connect 4/5.

        Only the Connect 4/5 have swapped LED colors red and green. We have to recalculate that
        values to match our values for GREEN, RED and BLUE.
        """
        led_calculated = led_value & 0b001
        led_calculated <<= 1
        led_calculated += bool(led_value & 0b010)
        led_calculated += led_value & 0b100
        return led_calculated

    def _devconfigure(self) -> None:
        """Prepare Connect 4/5 class."""
        super()._devconfigure()

        self._slc_statusbyte = slice(0, 1)
        self._slc_cycle = slice(1, 2)
        self._slc_errorcnt = slice(2, 4)
        self._slc_temperature = slice(4, 5)
        self._slc_frequency = slice(5, 6)
        self._slc_output = slice(6, 7)
        self._slc_errorlimit1 = slice(7, 9)
        self._slc_errorlimit2 = slice(9, 11)
        self._slc_led = slice(11, 13)

        # Check export flags (Byte or Bit)
        lst_myios = self._modio.io[self._slc_devoff]
        lst_led = lst_myios[self._slc_led.start]
        lst_output = lst_myios[self._slc_output.start]

        if len(lst_led) == 16:
            exp_a1red = lst_led[0].export
            exp_a1green = lst_led[1].export
            exp_a1blue = lst_led[2].export
            exp_a2red = lst_led[3].export
            exp_a2green = lst_led[4].export
            exp_a2blue = lst_led[5].export
            exp_a3red = lst_led[6].export
            exp_a3green = lst_led[7].export
            exp_a3blue = lst_led[8].export
            exp_a4red = lst_led[9].export
            exp_a4green = lst_led[10].export
            exp_a4blue = lst_led[11].export
            exp_a5red = lst_led[12].export
            exp_a5green = lst_led[13].export
            exp_a5blue = lst_led[14].export
        else:
            exp_a1red = lst_led[0].export
            exp_a1green = exp_a1red
            exp_a1blue = exp_a1red
            exp_a2red = exp_a1red
            exp_a2green = exp_a1red
            exp_a2blue = exp_a1red
            exp_a3red = exp_a1red
            exp_a3green = exp_a1red
            exp_a3blue = exp_a1red
            exp_a4red = exp_a1red
            exp_a4green = exp_a1red
            exp_a4blue = exp_a1red
            exp_a5red = exp_a1red
            exp_a5green = exp_a1red
            exp_a5blue = exp_a1red

        # Create actual IOs
        self.a1red = IOBase(
            self,
            ["core.a1red", 0, 1, self._slc_led.start, exp_a1red, None, "LED_A1_RED", "0"],
            OUT,
            "little",
            False,
        )
        """LED A1 red."""
        self.a1green = IOBase(
            self,
            ["core.a1green", 0, 1, self._slc_led.start, exp_a1green, None, "LED_A1_GREEN", "1"],
            OUT,
            "little",
            False,
        )
        """LED A1 green."""
        self.a1blue = IOBase(
            self,
            ["core.a1blue", 0, 1, self._slc_led.start, exp_a1blue, None, "LED_A1_BLUE", "2"],
            OUT,
            "little",
            False,
        )
        """LED A1 blue."""

        self.a2red = IOBase(
            self,
            ["core.a2red", 0, 1, self._slc_led.start, exp_a2red, None, "LED_A2_RED", "3"],
            OUT,
            "little",
            False,
        )
        """LED A2 red."""
        self.a2green = IOBase(
            self,
            ["core.a2green", 0, 1, self._slc_led.start, exp_a2green, None, "LED_A2_GREEN", "4"],
            OUT,
            "little",
            False,
        )
        """LED A2 green."""
        self.a2blue = IOBase(
            self,
            ["core.a2blue", 0, 1, self._slc_led.start, exp_a2blue, None, "LED_A2_BLUE", "5"],
            OUT,
            "little",
            False,
        )
        """LED A2 blue."""

        self.a3red = IOBase(
            self,
            ["core.a3red", 0, 1, self._slc_led.start, exp_a3red, None, "LED_A3_RED", "6"],
            OUT,
            "little",
            False,
        )
        """LED A3 red."""
        self.a3green = IOBase(
            self,
            ["core.a3green", 0, 1, self._slc_led.start, exp_a3green, None, "LED_A3_GREEN", "7"],
            OUT,
            "little",
            False,
        )
        """LED A3 green."""
        self.a3blue = IOBase(
            self,
            ["core.a3blue", 0, 1, self._slc_led.start, exp_a3blue, None, "LED_A3_BLUE", "8"],
            OUT,
            "little",
            False,
        )
        """LED A3 blue."""

        self.a4red = IOBase(
            self,
            ["core.a4red", 0, 1, self._slc_led.start, exp_a4red, None, "LED_A4_RED", "9"],
            OUT,
            "little",
            False,
        )
        """LED A4 red."""
        self.a4green = IOBase(
            self,
            ["core.a4green", 0, 1, self._slc_led.start, exp_a4green, None, "LED_A4_GREEN", "10"],
            OUT,
            "little",
            False,
        )
        """LED A4 green."""
        self.a4blue = IOBase(
            self,
            ["core.a4blue", 0, 1, self._slc_led.start, exp_a4blue, None, "LED_A4_BLUE", "11"],
            OUT,
            "little",
            False,
        )
        """LED A4 blue."""

        self.a5red = IOBase(
            self,
            ["core.a5red", 0, 1, self._slc_led.start, exp_a5red, None, "LED_A5_RED", "12"],
            OUT,
            "little",
            False,
        )
        """LED A5 red."""
        self.a5green = IOBase(
            self,
            ["core.a5green", 0, 1, self._slc_led.start, exp_a5green, None, "LED_A5_GREEN", "13"],
            OUT,
            "little",
            False,
        )
        """LED A5 green."""
        self.a5blue = IOBase(
            self,
            ["core.a5blue", 0, 1, self._slc_led.start, exp_a5blue, None, "LED_A5_BLUE", "14"],
            OUT,
            "little",
            False,
        )
        """LED A5 blue."""

    def _get_leda1(self) -> int:
        """
        Returns the state of LED A1 of the Connect.

        :return: 0=off, 1=green, 2=red, 4=blue, mixed RGB colors
        """
        return self.__led_calculator(self._ba_devdata[self._slc_led.start] & 0b00000111)

    def _get_leda2(self) -> int:
        """
        Returns the state of LED A2 from the Core.

        :return: 0=off, 1=green, 2=red, 4=blue, mixed RGB colors
        """
        return self.__led_calculator((self._ba_devdata[self._slc_led.start] & 0b00111000) >> 3)

    def _get_leda3(self) -> int:
        """
        Returns the state of LED A3 of the Core.

        :return: 0=off, 1=green, 2=red, 4=blue, mixed RGB colors
        """
        word_led = self._ba_devdata[self._slc_led]
        return self.__led_calculator((unpack("<H", word_led)[0] & 0b0000000111000000) >> 6)

    def _get_leda4(self) -> int:
        """
        Returns the state of LED A4 of the Core.

        :return: 0=off, 1=green, 2=red, 4=blue, mixed RGB colors
        """
        return self.__led_calculator((self._ba_devdata[self._slc_led.start + 1] & 0b00001110) >> 1)

    def _get_leda5(self) -> int:
        """
        Returns the state of LED A5 of the Core.

        :return: 0=off, 1=green, 2=red, 4=blue, mixed RGB colors
        """
        return self.__led_calculator((self._ba_devdata[self._slc_led.start + 1] & 0b01110000) >> 4)

    def _set_leda1(self, value: int) -> None:
        """
        Sets the state of LED A1 on the Connect.

        :param: value 0=off, 1=green, 2=red, 4=blue, mixed RGB colors
        """
        if 0 <= value <= 7:
            self.a1red(bool(value & 2))
            self.a1green(bool(value & 1))
            self.a1blue(bool(value & 4))
        else:
            raise ValueError("led status must be between 0 and 7")

    def _set_leda2(self, value: int) -> None:
        """
        Sets the state of LED A2 on the Connect.

        :param: value 0=off, 1=green, 2=red, 4=blue, mixed RGB colors
        """
        if 0 <= value <= 7:
            self.a2red(bool(value & 2))
            self.a2green(bool(value & 1))
            self.a2blue(bool(value & 4))
        else:
            raise ValueError("led status must be between 0 and 7")

    def _set_leda3(self, value: int) -> None:
        """
        Sets the state of LED A3 on the Connect.

        :param: value 0=off, 1=green, 2=red, 4=blue, mixed RGB colors
        """
        if 0 <= value <= 7:
            self.a3red(bool(value & 2))
            self.a3green(bool(value & 1))
            self.a3blue(bool(value & 4))
        else:
            raise ValueError("led status must be between 0 and 7")

    def _set_leda4(self, value: int) -> None:
        """
        Sets the state of LED A4 on the Connect.

        :param: value 0=off, 1=green, 2=red, 4=blue, mixed RGB colors
        """
        if 0 <= value <= 7:
            self.a4red(bool(value & 2))
            self.a4green(bool(value & 1))
            self.a4blue(bool(value & 4))
        else:
            raise ValueError("led status must be between 0 and 7")

    def _set_leda5(self, value: int) -> None:
        """
        Sets the state of LED A5 on the Connect.

        :param: value 0=off, 1=green, 2=red, 4=blue, mixed RGB colors
        """
        if 0 <= value <= 7:
            self.a5red(bool(value & 2))
            self.a5green(bool(value & 1))
            self.a5blue(bool(value & 4))
        else:
            raise ValueError("led status must be between 0 and 7")

    def wd_toggle(self):
        """Toggle watchdog bit to prevent a timeout."""
        raise NotImplementedError(
            "On the Connect 4/5, the hardware watchdog was removed from the process image by "
            "KUNBUS. This function is no longer available on Connect 4/5 devices."
        )

    A1 = property(_get_leda1, _set_leda1)
    A2 = property(_get_leda2, _set_leda2)
    A3 = property(_get_leda3, _set_leda3)
    A4 = property(_get_leda4, _set_leda4)
    A5 = property(_get_leda5, _set_leda5)


class Connect5(ModularBaseConnect_4_5, GatewayMixin):
    """Class for the RevPi Connect 5.

    Provides functions for the LEDs and the status.
    """

    pass


class Connect4(ModularBaseConnect_4_5):
    """Class for the RevPi Connect 4.

    Provides functions for the LEDs and the status.
    """

    __slots__ = (
        "x2in",
        "x2out",
    )

    def __setattr__(self, key, value):
        """Prevents overwriting the special IOs."""
        if hasattr(self, key) and key in (
            "x2in",
            "x2out",
        ):
            raise AttributeError("direct assignment is not supported - use .value Attribute")
        super().__setattr__(key, value)

    def _devconfigure(self) -> None:
        """Prepare Connect4 class."""
        super()._devconfigure()

        # Check export flags (Byte or Bit)
        lst_myios = self._modio.io[self._slc_devoff]
        lst_output = lst_myios[self._slc_output.start]

        if len(lst_output) == 8:
            # prepared for future extension with wdtoggle
            exp_x2out = lst_output[0].export
        else:
            exp_x2out = lst_output[0].export

        lst_status = lst_myios[self._slc_statusbyte.start]
        if len(lst_status) == 8:
            exp_x2in = lst_status[6].export
        else:
            exp_x2in = lst_status[0].export

        # Create IO objects for X2 in/out
        self.x2in = IOBase(
            self,
            ["core.x2in", 0, 1, self._slc_statusbyte.start, exp_x2in, None, "Connect_X2_IN", "6"],
            INP,
            "little",
            False,
        )
        """Digital input on X2 connector."""
        self.x2out = IOBase(
            self,
            ["core.x2out", 0, 1, self._slc_output.start, exp_x2out, None, "Connect_X2_OUT", "0"],
            OUT,
            "little",
            False,
        )
        """Digital output on X2 connector."""


class Compact(Base):
    """
    Class for the RevPi Compact.

    Provides functions for the LEDs. IOs are accessed via the .io
    object.
    """

    __slots__ = (
        "_slc_temperature",
        "_slc_frequency",
        "_slc_led",
        "a1green",
        "a1red",
        "a2green",
        "a2red",
        "wd",
    )

    def __setattr__(self, key, value):
        """Prevents overwriting the LEDs."""
        if hasattr(self, key) and key in ("a1green", "a1red", "a2green", "a2red", "wd"):
            raise AttributeError("direct assignment is not supported - use .value Attribute")
        else:
            object.__setattr__(self, key, value)

    def _devconfigure(self) -> None:
        """Prepare Core class."""
        super()._devconfigure()

        # Link static IOs of the Compact
        self._slc_led = slice(23, 24)
        self._slc_temperature = slice(0, 1)
        self._slc_frequency = slice(1, 2)

        # Check export flags (Byte or Bit)
        lst_led = self._modio.io[self._slc_devoff][self._slc_led.start]
        if len(lst_led) == 8:
            exp_a1green = lst_led[0].export
            exp_a1red = lst_led[1].export
            exp_a2green = lst_led[2].export
            exp_a2red = lst_led[3].export
        else:
            exp_a1green = lst_led[0].export
            exp_a1red = exp_a1green
            exp_a2green = exp_a1green
            exp_a2red = exp_a1green

        # Create actual IOs
        self.a1green = IOBase(
            self,
            ["core.a1green", 0, 1, self._slc_led.start, exp_a1green, None, "LED_A1_GREEN", "0"],
            OUT,
            "little",
            False,
        )
        """LED A1 green."""
        self.a1red = IOBase(
            self,
            ["core.a1red", 0, 1, self._slc_led.start, exp_a1red, None, "LED_A1_RED", "1"],
            OUT,
            "little",
            False,
        )
        """LED A1 red."""
        self.a2green = IOBase(
            self,
            ["core.a2green", 0, 1, self._slc_led.start, exp_a2green, None, "LED_A2_GREEN", "2"],
            OUT,
            "little",
            False,
        )
        """LED A2 green."""
        self.a2red = IOBase(
            self,
            ["core.a2red", 0, 1, self._slc_led.start, exp_a2red, None, "LED_A2_RED", "3"],
            OUT,
            "little",
            False,
        )
        """LED A2 red."""

        # Software watchdog einrichten
        self.wd = IOBase(
            self,
            ["core.wd", 0, 1, self._slc_led.start, False, None, "WatchDog", "7"],
            OUT,
            "little",
            False,
        )
        """Watchdog bit."""

    def _get_leda1(self) -> int:
        """
        Returns the state of LED A1 of the Compact.

        :return: 0=off, 1=green, 2=red
        """
        # 0b00000011 = 3
        return self._ba_devdata[self._slc_led.start] & 3

    def _get_leda2(self) -> int:
        """
        Returns the state of LED A2 of the Compact.

        :return: 0=off, 1=green, 2=red
        """
        # 0b00001100 = 12
        return (self._ba_devdata[self._slc_led.start] & 12) >> 2

    def _set_leda1(self, value: int) -> None:
        """
        Sets the state of LED A1 on the Compact.

        :param value: 0=off, 1=green, 2=red
        """
        if 0 <= value <= 3:
            self.a1green(bool(value & 1))
            self.a1red(bool(value & 2))
        else:
            raise ValueError("led status must be between 0 and 3")

    def _set_leda2(self, value: int) -> None:
        """
        Sets the state of LED A2 on the Compact.

        :param value: 0=off, 1=green, 2=red
        """
        if 0 <= value <= 3:
            self.a2green(bool(value & 1))
            self.a2red(bool(value & 2))
        else:
            raise ValueError("led status must be between 0 and 3")

    def wd_toggle(self):
        """Toggle watchdog bit to prevent a timeout."""
        self.wd.value = not self.wd.value

    A1 = property(_get_leda1, _set_leda1)
    A2 = property(_get_leda2, _set_leda2)

    @property
    def temperature(self) -> int:
        """
        Returns CPU temperature.

        :return: CPU temperature in Celsius (-273 if not available)
        """
        return (
            -273
            if self._slc_temperature is None
            else int.from_bytes(self._ba_devdata[self._slc_temperature], byteorder="little")
        )

    @property
    def frequency(self) -> int:
        """
        Returns CPU clock frequency.

        :return: CPU clock frequency in MHz (-1 if not available)
        """
        return (
            -1
            if self._slc_frequency is None
            else int.from_bytes(self._ba_devdata[self._slc_frequency], byteorder="little") * 10
        )


class Flat(Base):
    """
    Class for the RevPi Flat.

    Provides functions for the LEDs. IOs are accessed via the .io
    object zugegriffen.
    """

    __slots__ = (
        "_slc_temperature",
        "_slc_frequency",
        "_slc_led",
        "_slc_switch",
        "_slc_dout",
        "a1green",
        "a1red",
        "a2green",
        "a2red",
        "a3green",
        "a3red",
        "a4green",
        "a4red",
        "a5green",
        "a5red",
        "relais",
        "switch",
        "wd",
    )

    def __setattr__(self, key, value):
        """Prevents overwriting the LEDs."""
        if hasattr(self, key) and key in (
            "a1green",
            "a1red",
            "a2green",
            "a2red",
            "a3green",
            "a3red",
            "a4green",
            "a4red",
            "a5green",
            "a5red",
            "relais",
            "switch",
            "wd",
        ):
            raise AttributeError("direct assignment is not supported - use .value Attribute")
        else:
            object.__setattr__(self, key, value)

    def _devconfigure(self) -> None:
        """Prepare Core class."""
        super()._devconfigure()

        # Statische IO Verknüpfungen of the Compacts
        self._slc_led = slice(7, 9)
        self._slc_temperature = slice(4, 5)
        self._slc_frequency = slice(5, 6)
        self._slc_switch = slice(6, 7)
        self._slc_dout = slice(11, 12)

        # Check export flags (Byte or Bit)
        lst_led = self._modio.io[self._slc_devoff][self._slc_led.start]
        if len(lst_led) == 8:
            exp_a1green = lst_led[0].export
            exp_a1red = lst_led[1].export
            exp_a2green = lst_led[2].export
            exp_a2red = lst_led[3].export
            exp_a3green = lst_led[4].export
            exp_a3red = lst_led[5].export
            exp_a4green = lst_led[6].export
            exp_a4red = lst_led[7].export

            # Next byte
            lst_led = self._modio.io[self._slc_devoff][self._slc_led.start + 1]
            exp_a5green = lst_led[0].export
            exp_a5red = lst_led[1].export
        else:
            exp_a1green = lst_led[0].export
            exp_a1red = exp_a1green
            exp_a2green = exp_a1green
            exp_a2red = exp_a1green
            exp_a3green = exp_a1green
            exp_a3red = exp_a1green
            exp_a4green = exp_a1green
            exp_a4red = exp_a1green
            exp_a5green = exp_a1green
            exp_a5red = exp_a1green

        # Create actual IOs
        self.a1green = IOBase(
            self,
            ["core.a1green", 0, 1, self._slc_led.start, exp_a1green, None, "LED_A1_GREEN", "0"],
            OUT,
            "little",
            False,
        )
        """LED A1 green."""
        self.a1red = IOBase(
            self,
            ["core.a1red", 0, 1, self._slc_led.start, exp_a1red, None, "LED_A1_RED", "1"],
            OUT,
            "little",
            False,
        )
        """LED A1 red."""
        self.a2green = IOBase(
            self,
            ["core.a2green", 0, 1, self._slc_led.start, exp_a2green, None, "LED_A2_GREEN", "2"],
            OUT,
            "little",
            False,
        )
        """LED A2 green."""
        self.a2red = IOBase(
            self,
            ["core.a2red", 0, 1, self._slc_led.start, exp_a2red, None, "LED_A2_RED", "3"],
            OUT,
            "little",
            False,
        )
        """LED A2 red."""
        self.a3green = IOBase(
            self,
            ["core.a3green", 0, 1, self._slc_led.start, exp_a3green, None, "LED_A3_GREEN", "4"],
            OUT,
            "little",
            False,
        )
        """LED A3 green."""
        self.a3red = IOBase(
            self,
            ["core.a3red", 0, 1, self._slc_led.start, exp_a3red, None, "LED_A3_RED", "5"],
            OUT,
            "little",
            False,
        )
        """LED A3 red."""
        self.a4green = IOBase(
            self,
            ["core.a4green", 0, 1, self._slc_led.start, exp_a4green, None, "LED_A4_GREEN", "6"],
            OUT,
            "little",
            False,
        )
        """LED A4 green."""
        self.a4red = IOBase(
            self,
            ["core.a4red", 0, 1, self._slc_led.start, exp_a4red, None, "LED_A4_RED", "7"],
            OUT,
            "little",
            False,
        )
        """LED A4 red."""
        self.a5green = IOBase(
            self,
            ["core.a5green", 0, 1, self._slc_led.start, exp_a5green, None, "LED_A5_GREEN", "8"],
            OUT,
            "little",
            False,
        )
        """LED A5 green."""
        self.a5red = IOBase(
            self,
            ["core.a5red", 0, 1, self._slc_led.start, exp_a5red, None, "LED_A5_RED", "9"],
            OUT,
            "little",
            False,
        )
        """LED A5 red."""

        # Real IO for switch
        lst_io = self._modio.io[self._slc_devoff][self._slc_switch.start]
        exp_io = lst_io[0].export
        self.switch = IOBase(
            self,
            ["flat.switch", 0, 1, self._slc_switch.start, exp_io, None, "Flat_Switch", "0"],
            INP,
            "little",
            False,
        )
        """Switch input."""

        # Real IO for relais
        lst_io = self._modio.io[self._slc_devoff][self._slc_dout.start]
        exp_io = lst_io[0].export
        self.relais = IOBase(
            self,
            ["flat.relais", 0, 1, self._slc_dout.start, exp_io, None, "Flat_Relais", "0"],
            OUT,
            "little",
            False,
        )
        """Relais output."""

        # Software watchdog einrichten
        self.wd = IOBase(
            self,
            ["core.wd", 0, 1, self._slc_led.start, False, None, "WatchDog", "15"],
            OUT,
            "little",
            False,
        )
        """Watchdog bit."""

    def _get_leda1(self) -> int:
        """
        Get value of LED A1 from RevPi Flat device.

        :return: 0=off, 1=green, 2=red
        """
        return self._ba_devdata[self._slc_led.start] & 0b11

    def _get_leda2(self) -> int:
        """
        Get value of LED A2 from RevPi Flat device.

        :return: 0=off, 1=green, 2=red
        """
        return (self._ba_devdata[self._slc_led.start] & 0b1100) >> 2

    def _get_leda3(self) -> int:
        """
        Get value of LED A3 from RevPi Flat device.

        :return: 0=off, 1=green, 2=red
        """
        return (self._ba_devdata[self._slc_led.start] & 0b110000) >> 4

    def _get_leda4(self) -> int:
        """
        Get value of LED A4 from RevPi Flat device.

        :return: 0=off, 1=green, 2=red
        """
        return (self._ba_devdata[self._slc_led.start] & 0b11000000) >> 6

    def _get_leda5(self) -> int:
        """
        Get value of LED A5 from RevPi Flat device.

        :return: 0=off, 1=green, 2=red
        """
        return self._ba_devdata[self._slc_led.start + 1] & 0b11

    def _set_leda1(self, value: int) -> None:
        """
        Set LED A1 on RevPi Flat device.

        :param value: 0=off, 1=green, 2=red
        """
        if 0 <= value <= 3:
            self.a1green(bool(value & 1))
            self.a1red(bool(value & 2))
        else:
            raise ValueError("led status must be between 0 and 3")

    def _set_leda2(self, value: int) -> None:
        """
        Set LED A2 on RevPi Flat device.

        :param value: 0=off, 1=green, 2=red
        """
        if 0 <= value <= 3:
            self.a2green(bool(value & 1))
            self.a2red(bool(value & 2))
        else:
            raise ValueError("led status must be between 0 and 3")

    def _set_leda3(self, value: int) -> None:
        """
        Set LED A3 on RevPi Flat device.

        :param value: 0=off, 1=green, 2=red
        """
        if 0 <= value <= 3:
            self.a3green(bool(value & 1))
            self.a3red(bool(value & 2))
        else:
            raise ValueError("led status must be between 0 and 3")

    def _set_leda4(self, value: int) -> None:
        """
        Set LED A4 on RevPi Flat device.

        :param value: 0=off, 1=green, 2=red
        """
        if 0 <= value <= 3:
            self.a4green(bool(value & 1))
            self.a4red(bool(value & 2))
        else:
            raise ValueError("led status must be between 0 and 3")

    def _set_leda5(self, value: int) -> None:
        """
        Set LED A5 on RevPi Flat device.

        :param value: 0=off, 1=green, 2=red
        """
        if 0 <= value <= 3:
            self.a5green(bool(value & 1))
            self.a5red(bool(value & 2))
        else:
            raise ValueError("led status must be between 0 and 3")

    def wd_toggle(self):
        """Toggle watchdog bit to prevent a timeout."""
        self.wd.value = not self.wd.value

    A1 = property(_get_leda1, _set_leda1)
    A2 = property(_get_leda2, _set_leda2)
    A3 = property(_get_leda3, _set_leda3)
    A4 = property(_get_leda4, _set_leda4)
    A5 = property(_get_leda5, _set_leda5)

    @property
    def temperature(self) -> int:
        """
        Returns CPU temperature.

        :return: CPU temperature in Celsius (-273 if not available)
        """
        return (
            -273
            if self._slc_temperature is None
            else int.from_bytes(self._ba_devdata[self._slc_temperature], byteorder="little")
        )

    @property
    def frequency(self) -> int:
        """
        Returns CPU clock frequency.

        :return: CPU clock frequency in MHz (-1 if not available)
        """
        return (
            -1
            if self._slc_frequency is None
            else int.from_bytes(self._ba_devdata[self._slc_frequency], byteorder="little") * 10
        )


class DioModule(Device):
    """Represents a DIO / DI / DO module."""

    __slots__ = "_lst_counter"

    def __init__(self, parentmodio, dict_device, simulator=False):
        """
        Extends Device class for detecting IntIOCounter.

        :rev: :func:`Device.__init__()`
        """
        # Stringliste the Byteadressen (all Module are gleich)
        self._lst_counter = list(map(str, range(6, 70, 4)))

        # Load base class
        super().__init__(parentmodio, dict_device, simulator=simulator)


class RoModule(Device):
    """Relais output (RO) module with"""

    def __init__(self, parentmodio, dict_device, simulator=False):
        """
        Relais outputs of this device has a cycle counter for the relais.

        :rev: :func:`Device.__init__()`
        """
        super().__init__(parentmodio, dict_device, simulator=simulator)


class Gateway(Device):
    """
    Class for the RevPi Gateway-Devices.

    Provides additional functions for the RevPi Gateway devices besides
    the functions from RevPiDevice.
    Gateways are ready. IOs on this device provide the replace_io
    function, which allows defining custom IOs that map to a
    RevPiStructIO object.
    This IO type can process and return values via multiple bytes.

    :ref: :func:`revpimodio2.io.IntIOReplaceable.replace_io()`
    """

    __slots__ = "_dict_slc"

    def __init__(self, parent, dict_device, simulator=False):
        """
        Extends Device class with get_rawbytes functions.

        :ref: :func:`Device.__init__()`
        """
        super().__init__(parent, dict_device, simulator)

        self._dict_slc = {
            INP: self._slc_inp,
            OUT: self._slc_out,
            MEM: self._slc_mem,
        }

    def get_rawbytes(self) -> bytes:
        """
        Returns the bytes used by this device.

        :return: <class 'bytes'> of the Devices
        """
        return bytes(self._ba_devdata)


class Virtual(Gateway):
    """
    Class for the RevPi Virtual-Devices.

    Provides the same functions as Gateway. Custom IOs can be
    defined via the replace_io functions that map to RevPiStructIO objects.
    This IO type can process and return values via multiple bytes.

    :ref: :func:`Gateway`
    """

    __slots__ = ()

    def writeinputdefaults(self):
        """
        Writes piCtory default input values for a virtual device.

        If default values for inputs of a virtual device are specified
        in piCtory, these are only set at system startup or a piControl
        reset. If the process image is subsequently overwritten with NULL,
        these values will be lost.
        This function can only be applied to virtual devices!

        :return: True if operations on the virtual device were successful
        """
        if self._modio._monitoring:
            raise RuntimeError("can not write process image, while system is in monitoring mode")

        workokay = True
        self._filelock.acquire()

        for io in self.get_inputs():
            self._ba_devdata[io._slc_address] = io._defaultvalue

        # Write inputs to bus
        self._modio._myfh_lck.acquire()
        try:
            self._modio._myfh.seek(self._slc_inpoff.start)
            self._modio._myfh.write(self._ba_devdata[self._slc_inp])
            if self._modio._buffedwrite:
                self._modio._myfh.flush()
        except IOError as e:
            self._modio._gotioerror("write_inp_def", e)
            workokay = False
        finally:
            self._modio._myfh_lck.release()

        self._filelock.release()
        return workokay

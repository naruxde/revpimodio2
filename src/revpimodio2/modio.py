# -*- coding: utf-8 -*-
"""RevPiModIO main class for piControl0 access."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2023 Sven Sager"
__license__ = "LGPLv2"

import warnings
from configparser import ConfigParser
from json import load as jload
from multiprocessing import cpu_count
from os import F_OK, R_OK, access
from os import stat as osstat
from queue import Empty
from signal import SIGINT, SIGTERM, SIG_DFL, signal
from stat import S_ISCHR
from threading import Event, Lock, Thread
from timeit import default_timer

from . import app as appmodule
from . import device as devicemodule
from . import helper as helpermodule
from . import summary as summarymodule
from ._internal import acheck, RISING, FALLING, BOTH
from .errors import DeviceNotFoundError
from .io import IOList
from .io import StructIO
from .pictory import DeviceType, ProductType


class DevSelect:
    __slots__ = "type", "other_device_key", "values"

    def __init__(
        self,
        device_type=DeviceType.IGNORED,
        search_key: str = None,
        search_values=(),
    ):
        """
        Create a customized search filter for RevPiModIOSelected search.

        If you leave search_key set to None or empty string, the default, the
        given search_values will automatically select the search_key. This
        depends on the data type in the tuple. A string value searches for
        device name, an integer value searches for device position.

        :param device_type: Set a filter for just this device types
        :param search_key: Set a property of device to search values or auto
        :param search_values: Search for this values
        """
        self.type = device_type
        self.other_device_key = search_key or ""
        self.values = search_values


class RevPiModIO(object):
    """
    Class for managing the piCtory configuration.

    This class takes over the entire configuration from piCtory and
    loads the devices and IOs. It takes over exclusive management of the
    process image and ensures that the data is synchronized.
    If only individual devices are to be controlled, use
    RevPiModIOSelected() and pass a list with
    device positions or device names during instantiation.
    """

    __slots__ = (
        "__cleanupfunc",
        "_autorefresh",
        "_buffedwrite",
        "_configrsc",
        "_context_manager",
        "_debug",
        "_devselect",
        "_exit",
        "_exit_level",
        "_imgwriter",
        "_ioerror",
        "_length",
        "_looprunning",
        "_lst_devselect",
        "_lst_refresh",
        "_maxioerrors",
        "_monitoring",
        "_myfh",
        "_myfh_lck",
        "_procimg",
        "_replace_io_file",
        "_run_on_pi",
        "_set_device_based_cycle_time",
        "_simulator",
        "_init_shared_procimg",
        "_syncoutputs",
        "_th_mainloop",
        "_waitexit",
        "app",
        "core",
        "device",
        "exitsignal",
        "io",
        "summary",
    )

    def __init__(
        self,
        autorefresh=False,
        monitoring=False,
        syncoutputs=True,
        procimg=None,
        configrsc=None,
        simulator=False,
        debug=True,
        replace_io_file=None,
        shared_procimg=False,
    ):
        """
        Instantiates the basic functions.

        :param autorefresh: If True, add all devices to autorefresh
        :param monitoring: Inputs and outputs are read, never written
        :param syncoutputs: Read currently set outputs from process image
        :param procimg: Alternative path to process image
        :param configrsc: Alternative path to piCtory configuration file
        :param simulator: Loads the module as simulator and swaps IOs
        :param debug: Output all warnings including cycle problems
        :param replace_io_file: Load replace IO configuration from file
        :param shared_procimg: Share process image with other processes, this
                               could be insecure for automation
        """
        # Parameter validation
        acheck(
            bool,
            autorefresh=autorefresh,
            monitoring=monitoring,
            syncoutputs=syncoutputs,
            simulator=simulator,
            debug=debug,
            shared_procimg=shared_procimg,
        )
        acheck(
            str,
            procimg_noneok=procimg,
            configrsc_noneok=configrsc,
            replace_io_file_noneok=replace_io_file,
        )

        self._autorefresh = autorefresh
        self._configrsc = configrsc
        self._context_manager = False
        self._monitoring = monitoring
        self._procimg = "/dev/piControl0" if procimg is None else procimg
        self._set_device_based_cycle_time = True
        self._simulator = simulator
        self._init_shared_procimg = shared_procimg
        self._syncoutputs = syncoutputs

        # TODO: check if file exists for simulator and procimg / create it?

        # Private variables
        self.__cleanupfunc = None
        self._buffedwrite = False
        self._debug = 1
        self._devselect = DevSelect()
        self._exit = Event()
        self._exit_level = 0
        self._imgwriter = None
        self._ioerror = 0
        self._length = 0
        self._looprunning = False
        self._lst_refresh = []
        self._maxioerrors = 0
        self._myfh = None
        self._myfh_lck = Lock()
        self._replace_io_file = replace_io_file
        self._th_mainloop = None
        self._waitexit = Event()

        # Module variables
        self.core = None

        # piCtory classes
        self.app = None
        self.device = None
        self.io = None
        self.summary = None

        # Event for user actions
        self.exitsignal = Event()

        # Set value via setter
        self.debug = debug

        try:
            self._run_on_pi = S_ISCHR(osstat(self._procimg).st_mode)
        except Exception:
            self._run_on_pi = False

        # Only configure if not inherited
        if type(self) == RevPiModIO:
            self._configure(self.get_jconfigrsc())

    def __del__(self):
        """Destroys all classes to clean up."""
        if hasattr(self, "_exit"):
            self.exit(full=True)
            if self._myfh is not None:
                self._myfh.close()

    def __enter__(self):
        # todo: Remove this context manager in future
        warnings.warn(
            "This context manager is deprecated and will be removed!\n\n"
            "You should use the context manager of the IO object `with revpi.io:` "
            "or with a single device `with revpi.device.my_device:`.\n\n"
            "This deprecated context manager can be reproduced as follows:\n"
            "```"
            "revpi = revpimodio2.RevPiModIO()"
            "with revpi.io:"
            "    ..."
            "```",
            DeprecationWarning,
        )
        if self._context_manager:
            raise RuntimeError("can not use multiple context managers of same instance")
        if self._looprunning:
            raise RuntimeError("can not enter context manager with running mainloop or cycleloop")
        self._context_manager = True
        self._looprunning = True

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._monitoring:
            self.writeprocimg()
        self.exit(full=True)
        self._looprunning = False
        self._context_manager = False

    def __evt_exit(self, signum, sigframe) -> None:
        """
        Event handler for program termination.

        :param signum: Signal number
        :param sigframe: Signal frame
        """
        signal(SIGINT, SIG_DFL)
        signal(SIGTERM, SIG_DFL)
        self._exit_level |= 4
        self.exit(full=True)

    def __exit_jobs(self):
        """Shutdown sub systems."""
        if self._exit_level & 1:
            # System can continue to be used after execution
            self._exit_level ^= 1

            # Stop ProcimgWriter and wait for it
            if self._imgwriter is not None and self._imgwriter.is_alive():
                self._imgwriter.stop()
                self._imgwriter.join(2.5)

            # Remove all devices from autorefresh
            while len(self._lst_refresh) > 0:
                dev = self._lst_refresh.pop()
                dev._selfupdate = False
                if not self._monitoring:
                    self.writeprocimg(dev)

        # Execute clean up function
        if self._exit_level & 4 and self.__cleanupfunc is not None:
            self._exit_level ^= 4
            self.readprocimg()
            self.__cleanupfunc()
            if not self._monitoring:
                self.writeprocimg()

        if self._exit_level & 2:
            self._myfh.close()
            self.app = None
            self.core = None
            self.device = None
            self.io = None
            self.summary = None

    def _configure(self, jconfigrsc: dict) -> None:
        """
        Processes the piCtory configuration file.

        :param jconfigrsc: Data to build IOs as <class 'dict'> of JSON
        """
        # Configure file handler if it doesn't exist yet
        if self._myfh is None:
            self._myfh = self._create_myfh()

        # Instantiate App class
        self.app = appmodule.App(jconfigrsc["App"])

        # Apply device filter
        if self._devselect.values:
            # Check for supported types in values
            for dev in self._devselect.values:
                if type(dev) not in (int, str):
                    raise ValueError(
                        "need device position as <class 'int'> or device name as <class 'str'>"
                    )

            lst_devices = []
            for dev in jconfigrsc["Devices"]:
                if self._devselect.type and self._devselect.type != dev["type"]:
                    continue
                if self._devselect.other_device_key:
                    key_value = str(dev[self._devselect.other_device_key])
                    if key_value not in self._devselect.values:
                        # The list is always filled with <class 'str'>
                        continue
                else:
                    # Auto search depending of value item type
                    if not (
                        dev["name"] in self._devselect.values
                        or int(dev["position"]) in self._devselect.values
                    ):
                        continue

                lst_devices.append(dev)
        else:
            # Take devices from JSON
            lst_devices = jconfigrsc["Devices"]

        # Create Device and IO classes
        self.device = devicemodule.DeviceList()
        self.io = IOList(self)

        # Initialize devices
        err_names_check = {}
        for device in sorted(lst_devices, key=lambda x: x["offset"]):
            # Pre-check of values
            if float(device.get("offset")) != int(device.get("offset")):
                # Offset misconfigured
                warnings.warn(
                    "Offset value {0} of device {1} on position {2} is invalid. "
                    "This device and all IOs are ignored.".format(
                        device.get("offset"),
                        device.get("name"),
                        device.get("position"),
                    )
                )
                continue

            # Change VDev of old piCtory versions to KUNBUS standard
            if device["position"] == "adap.":
                device["position"] = 64
                while device["position"] in self.device:
                    device["position"] += 1

            if device["type"] == DeviceType.BASE:
                # Base devices
                pt = int(device["productType"])
                if pt == ProductType.REVPI_CORE:
                    # RevPi Core
                    dev_new = devicemodule.Core(self, device, simulator=self._simulator)
                    self.core = dev_new
                elif pt == ProductType.REVPI_CONNECT:
                    # RevPi Connect
                    dev_new = devicemodule.Connect(self, device, simulator=self._simulator)
                    self.core = dev_new
                elif pt == ProductType.REVPI_CONNECT_4:
                    # RevPi Connect 4
                    dev_new = devicemodule.Connect4(self, device, simulator=self._simulator)
                    self.core = dev_new
                elif pt == ProductType.REVPI_CONNECT_5:
                    # RevPi Connect 5
                    dev_new = devicemodule.Connect5(self, device, simulator=self._simulator)
                    self.core = dev_new
                elif pt == ProductType.REVPI_COMPACT:
                    # RevPi Compact
                    dev_new = devicemodule.Compact(self, device, simulator=self._simulator)
                    self.core = dev_new
                elif pt == ProductType.REVPI_FLAT:
                    # RevPi Flat
                    dev_new = devicemodule.Flat(self, device, simulator=self._simulator)
                    self.core = dev_new
                else:
                    # Always use Base as fallback
                    dev_new = devicemodule.Base(self, device, simulator=self._simulator)
            elif device["type"] == DeviceType.LEFT_RIGHT:
                # IOs
                pt = int(device["productType"])
                if pt == ProductType.DIO or pt == ProductType.DI or pt == ProductType.DO:
                    # DIO / DI / DO
                    dev_new = devicemodule.DioModule(self, device, simulator=self._simulator)
                elif pt == ProductType.RO:
                    # RO
                    dev_new = devicemodule.RoModule(self, device, simulator=self._simulator)
                else:
                    # All other IO devices
                    dev_new = devicemodule.Device(self, device, simulator=self._simulator)
            elif device["type"] == DeviceType.VIRTUAL:
                # Virtuals
                dev_new = devicemodule.Virtual(self, device, simulator=self._simulator)
            elif device["type"] == DeviceType.EDGE:
                # Gateways
                dev_new = devicemodule.Gateway(self, device, simulator=self._simulator)
            elif device["type"] == DeviceType.RIGHT:
                # Connectdevice
                dev_new = None
            else:
                # Device type not found
                warnings.warn(
                    "device type '{0}' on position {1} unknown"
                    "".format(device["type"], device["position"]),
                    Warning,
                )
                dev_new = None

            if dev_new is not None:
                # Check offset, must match length
                if self._length < dev_new.offset:
                    self._length = dev_new.offset

                self._length += dev_new.length

                # Build dict with device name and positions and check later
                if dev_new.name not in err_names_check:
                    err_names_check[dev_new.name] = []
                err_names_check[dev_new.name].append(str(dev_new.position))

                # Set shared_procimg mode, if requested on instantiation
                dev_new.shared_procimg(self._init_shared_procimg)

                # Build DeviceList for direct access
                setattr(self.device, dev_new.name, dev_new)

        # Check equal device names and destroy name attribute of device class
        for check_dev in err_names_check:
            if len(err_names_check[check_dev]) == 1:
                continue
            self.device.__delattr__(check_dev, False)
            warnings.warn(
                "equal device name '{0}' in pictory configuration. you can "
                "access this devices by position number .device[{1}] only!"
                "".format(check_dev, "|".join(err_names_check[check_dev])),
                Warning,
            )

        # Create ImgWriter
        self._imgwriter = helpermodule.ProcimgWriter(self)

        if self._set_device_based_cycle_time:
            # Refresh time CM1 25 Hz / CM3 50 Hz
            self._imgwriter.refresh = 20 if cpu_count() > 1 else 40

        # Read current output status from procimg
        if self._syncoutputs:
            self.syncoutputs()

        # For RS485 errors at core, load defaults if procimg should be NULL
        if isinstance(self.core, devicemodule.Core) and not (self._monitoring or self._simulator):
            if self.core._slc_errorlimit1 is not None:
                io = self.io[self.core.offset + self.core._slc_errorlimit1.start][0]
                io.set_value(io._defaultvalue)
            if self.core._slc_errorlimit2 is not None:
                io = self.io[self.core.offset + self.core._slc_errorlimit2.start][0]
                io.set_value(io._defaultvalue)

            # Write RS485 errors
            self.writeprocimg(self.core)

        # Set replace IO before autostart to prevent cycle time exhausting
        self._configure_replace_io(self._get_cpreplaceio())

        # Optionally add to autorefresh
        if self._autorefresh:
            self.autorefresh_all()

        # Instantiate Summary class
        self.summary = summarymodule.Summary(jconfigrsc["Summary"])

    def _configure_replace_io(self, creplaceio: ConfigParser) -> None:
        """
        Imports replaced IOs into this instance.

        Imports replaced IOs that were previously exported to a file using
        .export_replaced_ios(...). These IOs are restored in this instance.

        :param creplaceio: Data to replace ios as <class 'ConfigParser'>
        """
        for io in creplaceio:
            if io == "DEFAULT":
                continue

            # Check IO
            parentio = creplaceio[io].get("replace", "")

            # Prepare function call
            dict_replace = {
                "frm": creplaceio[io].get("frm"),
                "byteorder": creplaceio[io].get("byteorder", "little"),
                "bmk": creplaceio[io].get("bmk", ""),
            }

            # Get bitaddress from config file
            if "bit" in creplaceio[io]:
                try:
                    dict_replace["bit"] = creplaceio[io].getint("bit")
                except Exception:
                    raise ValueError(
                        "replace_io_file: could not convert '{0}' "
                        "bit '{1}' to integer"
                        "".format(io, creplaceio[io]["bit"])
                    )

            if "wordorder" in creplaceio[io]:
                dict_replace["wordorder"] = creplaceio[io]["wordorder"]

            if "export" in creplaceio[io]:
                try:
                    dict_replace["export"] = creplaceio[io].getboolean("export")
                except Exception:
                    raise ValueError(
                        "replace_io_file: could not convert '{0}' "
                        "export '{1}' to bool"
                        "".format(io, creplaceio[io]["export"])
                    )

            # Convert defaultvalue from config file
            if "defaultvalue" in creplaceio[io]:
                if dict_replace["frm"] == "?":
                    try:
                        dict_replace["defaultvalue"] = creplaceio[io].getboolean("defaultvalue")
                    except Exception:
                        raise ValueError(
                            "replace_io_file: could not convert '{0}' "
                            "defaultvalue '{1}' to boolean"
                            "".format(io, creplaceio[io]["defaultvalue"])
                        )
                elif dict_replace["frm"].find("s") >= 0:
                    buff = bytearray()
                    try:
                        dv_array = creplaceio[io].get("defaultvalue").split(" ")
                        for byte_int in dv_array:
                            buff.append(int(byte_int))
                        dict_replace["defaultvalue"] = bytes(buff)
                    except Exception as e:
                        raise ValueError(
                            "replace_io_file: could not convert '{0}' "
                            "defaultvalue to bytes | {1}"
                            "".format(io, e)
                        )
                else:
                    try:
                        dict_replace["defaultvalue"] = creplaceio[io].getint("defaultvalue")
                    except Exception:
                        raise ValueError(
                            "replace_io_file: could not convert '{0}' "
                            "defaultvalue '{1}' to integer"
                            "".format(io, creplaceio[io]["defaultvalue"])
                        )

            # Replace IO
            try:
                self.io[parentio].replace_io(name=io, **dict_replace)
            except Exception as e:
                # NOTE: Cannot be checked for Selected/Driver
                if len(self._devselect.values) == 0:
                    raise RuntimeError(
                        "replace_io_file: can not replace '{0}' with '{1}' "
                        "| RevPiModIO message: {2}".format(parentio, io, e)
                    )

    def _create_myfh(self):
        """
        Creates FileObject with path to procimg.

        :return: FileObject
        """
        self._buffedwrite = False
        return open(self._procimg, "r+b", 0)

    def _get_configrsc(self) -> str:
        """
        Getter function.

        :return: Path of the used piCtory configuration
        """
        return self._configrsc

    def _get_cpreplaceio(self) -> ConfigParser:
        """
        Loads the replace_io_file configuration and processes it.

        :return: <class 'ConfigParser'> of the replace io data
        """
        cp = ConfigParser()

        if self._replace_io_file:
            try:
                with open(self._replace_io_file, "r") as fh:
                    cp.read_file(fh)
            except Exception as e:
                raise RuntimeError(
                    "replace_io_file: could not read/parse file '{0}' | {1}"
                    "".format(self._replace_io_file, e)
                )

        return cp

    def _get_cycletime(self) -> int:
        """
        Returns the refresh rate in ms of the process image synchronization.

        :return: Milliseconds
        """
        return self._imgwriter.refresh

    def _get_debug(self) -> bool:
        """
        Returns the status of the debug flag.

        :return: Status of the debug flag
        """
        return self._debug == 1

    def _get_ioerrors(self) -> int:
        """
        Getter function.

        :return: Current number of counted errors
        """
        return self._ioerror

    def _get_length(self) -> int:
        """
        Getter function.

        :return: Length in bytes of the devices
        """
        return self._length

    def _get_maxioerrors(self) -> int:
        """
        Getter function.

        :return: Number of allowed errors
        """
        return self._maxioerrors

    def _get_monitoring(self) -> bool:
        """
        Getter function.

        :return: True if started as monitoring
        """
        return self._monitoring

    def _get_procimg(self) -> str:
        """
        Getter function.

        :return: Path of the used process image
        """
        return self._procimg

    def _get_replace_io_file(self) -> str:
        """
        Returns the path to the used replace IO file.

        :return: Path to the replace IO file
        """
        return self._replace_io_file

    def _get_simulator(self) -> bool:
        """
        Getter function.

        :return: True if started as simulator
        """
        return self._simulator

    def _gotioerror(self, action: str, e=None, show_warn=True) -> None:
        """
        IOError management for process image access.

        :param action: Additional information for logging
        :param e: Exception to log if debug is enabled
        :param show_warn: Show warning
        """
        self._ioerror += 1
        if self._maxioerrors != 0 and self._ioerror >= self._maxioerrors:
            raise RuntimeError(
                "reach max io error count {0} on process image".format(self._maxioerrors)
            )

        if not show_warn or self._debug == -1:
            return

        if self._debug == 0:
            warnings.warn("got io error on process image", RuntimeWarning)
        else:
            warnings.warn(
                "got io error during '{0}' and count {1} errors now | {2}"
                "".format(action, self._ioerror, str(e)),
                RuntimeWarning,
            )

    def _set_cycletime(self, milliseconds: int) -> None:
        """
        Sets the refresh rate of the process image synchronization.

        :param milliseconds: <class 'int'> in milliseconds
        """
        if self._looprunning:
            raise RuntimeError("can not change cycletime when cycleloop or mainloop is running")
        else:
            self._imgwriter.refresh = milliseconds

    def _set_debug(self, value: bool) -> None:
        """
        Sets debugging status to get more messages or not.

        :param value: If True, extensive messages are displayed
        """
        if type(value) == bool:
            value = int(value)
        if not type(value) == int:
            # Value -1 is hidden for complete deactivation
            raise TypeError("value must be <class 'bool'> or <class 'int'>")
        if not -1 <= value <= 1:
            raise ValueError("value must be True/False or -1, 0, 1")

        self._debug = value

        if value == -1:
            warnings.filterwarnings("ignore", module="revpimodio2")
        elif value == 0:
            warnings.filterwarnings("default", module="revpimodio2")
        else:
            warnings.filterwarnings("always", module="revpimodio2")

    def _set_maxioerrors(self, value: int) -> None:
        """
        Sets the number of maximum allowed errors for process image access.

        :param value: Number of allowed errors
        """
        if type(value) == int and value >= 0:
            self._maxioerrors = value
        else:
            raise ValueError("value must be 0 or a positive integer")

    def _simulate_ioctl(self, request: int, arg=b"") -> None:
        """
        Simulates IOCTL functions on procimg file.

        :param request: IO Request
        :param arg: Request argument
        """
        if request == 19216:
            # Set single bit
            byte_address = int.from_bytes(arg[:2], byteorder="little")
            bit_address = arg[2]
            new_value = bool(0 if len(arg) <= 3 else arg[3])

            # Simulation mode writes directly to file
            with self._myfh_lck:
                self._myfh.seek(byte_address)
                int_byte = int.from_bytes(self._myfh.read(1), byteorder="little")
                int_bit = 1 << bit_address

                if not bool(int_byte & int_bit) == new_value:
                    if new_value:
                        int_byte += int_bit
                    else:
                        int_byte -= int_bit

                    self._myfh.seek(byte_address)
                    self._myfh.write(int_byte.to_bytes(1, byteorder="little"))
                    if self._buffedwrite:
                        self._myfh.flush()

        elif request == 19220:
            # Set counter value to 0
            dev_position = arg[0]
            bit_field = int.from_bytes(arg[2:], byteorder="little")
            io_byte = -1

            for i in range(16):
                if bool(bit_field & 1 << i):
                    io_byte = self.device[dev_position].offset + int(
                        self.device[dev_position]._lst_counter[i]
                    )
                    break

            if io_byte == -1:
                raise RuntimeError("could not reset counter io in file")

            with self._myfh_lck:
                self._myfh.seek(io_byte)
                self._myfh.write(b"\x00\x00\x00\x00")
                if self._buffedwrite:
                    self._myfh.flush()

    def autorefresh_all(self) -> None:
        """Sets all devices to autorefresh function."""
        for dev in self.device:
            dev.autorefresh()

    def cleanup(self) -> None:
        """Terminates autorefresh and all threads."""
        self._exit_level |= 2
        self.exit(full=True)

    def cycleloop(self, func, cycletime=50, blocking=True):
        """
        Starts the cycle loop.

        The current program thread is "trapped" here until .exit() is called.
        After each update of the process image, it executes the passed
        function "func" and processes it. During execution of the function,
        the process image is not further updated. The inputs retain their
        current value until the end. Set outputs are written to the process
        image after the function run completes.

        The cycle loop is left when the called function returns a value
        not equal to None (e.g. return True), or by calling .exit().

        NOTE: The refresh time and the runtime of the function must not
        exceed the set autorefresh time or passed cycletime!

        The cycletime parameter sets the desired cycle time of the passed
        function. The default value is 50 milliseconds, in which the process
        image is read, the passed function is executed, and the process image
        is written.

        :param func: Function to be executed
        :param cycletime: Cycle time in milliseconds - default 50 ms
        :param blocking: If False, the program does NOT block here
        :return: None or the return value of the cycle function
        """
        # Check for context manager
        if self._context_manager:
            raise RuntimeError("Can not start cycleloop inside a context manager (with statement)")
        # Check if a loop is already running
        if self._looprunning:
            raise RuntimeError("can not start multiple loops mainloop/cycleloop")

        # Check if devices are in autorefresh
        if len(self._lst_refresh) == 0:
            raise RuntimeError(
                "no device with autorefresh activated - use autorefresh=True "
                "or call .autorefresh_all() before entering cycleloop"
            )

        # Check if function is callable
        if not callable(func):
            raise RuntimeError("registered function '{0}' ist not callable".format(func))

        # Create thread if it should not block
        if not blocking:
            self._th_mainloop = Thread(
                target=self.cycleloop,
                args=(func,),
                kwargs={"cycletime": cycletime, "blocking": True},
            )
            self._th_mainloop.start()
            return

        # Take over cycle time
        old_cycletime = self._imgwriter.refresh
        if not cycletime == self._imgwriter.refresh:
            # Set new cycle time and wait one imgwriter cycle to sync fist cycle
            self._imgwriter.refresh = cycletime
            self._imgwriter.newdata.clear()
            self._imgwriter.newdata.wait(self._imgwriter._refresh)

        # User event
        self.exitsignal.clear()

        # Start cycle loop
        self._exit.clear()
        self._looprunning = True
        cycleinfo = helpermodule.Cycletools(self._imgwriter.refresh, self)
        e = None  # Exception
        ec = None  # Return value of cycle_function
        self._imgwriter.newdata.clear()
        try:
            while ec is None and not cycleinfo.last:
                # Wait for new data and only execute if set()
                if not self._imgwriter.newdata.wait(2.5):
                    if not self._imgwriter.is_alive():
                        self.exit(full=False)
                        e = RuntimeError("autorefresh thread not running")
                        break

                    # Just warn, user has to use maxioerrors to kill program
                    warnings.warn(
                        RuntimeWarning("no new io data in cycle loop for 2500 milliseconds")
                    )
                    cycleinfo.last = self._exit.is_set()
                    continue

                self._imgwriter.newdata.clear()

                # Lock autorefresh before calling the function
                self._imgwriter.lck_refresh.acquire()

                # Preparation for cycleinfo
                cycleinfo._start_timer = default_timer()
                cycleinfo.last = self._exit.is_set()

                # Call and evaluate function
                ec = func(cycleinfo)
                cycleinfo._docycle()

                # Release autorefresh
                self._imgwriter.lck_refresh.release()
        except Exception as ex:
            if self._imgwriter.lck_refresh.locked():
                self._imgwriter.lck_refresh.release()
            if self._th_mainloop is None:
                self.exit(full=False)
            e = ex
        finally:
            # End cycle loop
            self._looprunning = False
            self._th_mainloop = None

        # Set old autorefresh time
        self._imgwriter.refresh = old_cycletime

        # Execute exit strategy
        self.__exit_jobs()

        # Check for errors that were thrown in the loop
        if e is not None:
            raise e

        return ec

    def exit(self, full=True) -> None:
        """
        Terminates mainloop() and optionally autorefresh.

        If the program is in mainloop(), calling exit() returns control
        to the main program.

        The full parameter defaults to True and removes all devices from
        autorefresh. The thread for process image synchronization is then
        stopped and the program can be terminated cleanly.

        :param full: Also removes all devices from autorefresh
        """
        self._exit_level |= 1 if full else 0

        # Save actual loop value before events
        full = full and not self._looprunning

        # User event
        self.exitsignal.set()

        self._exit.set()
        self._waitexit.set()

        # Auf beenden von mainloop thread warten
        if self._th_mainloop is not None and self._th_mainloop.is_alive():
            self._th_mainloop.join(2.5)

        if full:
            self.__exit_jobs()

    def export_replaced_ios(self, filename="replace_ios.conf") -> None:
        """
        Exports replaced IOs of this instance.

        Exports all replaced IOs that were created with .replace_io(...).
        The file can be used, for example, for RevPiPyLoad to transfer data
        in the new formats via MQTT or to view with RevPiPyControl.

        @param filename Filename for export file
        """
        acheck(str, filename=filename)

        cp = ConfigParser()
        for io in self.io:
            if isinstance(io, StructIO):
                # Required values
                cp.add_section(io.name)
                cp[io.name]["replace"] = io._parentio_name
                cp[io.name]["frm"] = io.frm

                # Optional values
                if io._bitshift:
                    cp[io.name]["bit"] = str(io._bitaddress)
                if io._byteorder != "little":
                    cp[io.name]["byteorder"] = io._byteorder
                if io._wordorder:
                    cp[io.name]["wordorder"] = io._wordorder
                if type(io.defaultvalue) is bytes:
                    if any(io.defaultvalue):
                        # Convert each byte to an integer
                        cp[io.name]["defaultvalue"] = " ".join(map(str, io.defaultvalue))
                elif io.defaultvalue != 0:
                    cp[io.name]["defaultvalue"] = str(io.defaultvalue)
                if io.bmk != "":
                    cp[io.name]["bmk"] = io.bmk
                if io._export & 2:
                    cp[io.name]["export"] = str(io._export & 1)

        try:
            with open(filename, "w") as fh:
                cp.write(fh)
        except Exception as e:
            raise RuntimeError("could not write export file '{0}' | {1}".format(filename, e))

    def get_jconfigrsc(self) -> dict:
        """
        Loads the piCtory configuration and creates a <class 'dict'>.

        :return: <class 'dict'> of the piCtory configuration
        """
        # Check piCtory configuration
        if self._configrsc is not None:
            if not access(self._configrsc, F_OK | R_OK):
                raise RuntimeError(
                    "can not access pictory configuration at {0}".format(self._configrsc)
                )
        else:
            # Check piCtory configuration at known locations
            lst_rsc = ["/etc/revpi/config.rsc", "/opt/KUNBUS/config.rsc"]
            for rscfile in lst_rsc:
                if access(rscfile, F_OK | R_OK):
                    self._configrsc = rscfile
                    break
            if self._configrsc is None:
                raise RuntimeError(
                    "can not access known pictory configurations at {0} - "
                    "use 'configrsc' parameter so specify location"
                    "".format(", ".join(lst_rsc))
                )

        with open(self._configrsc, "r") as fhconfigrsc:
            try:
                jdata = jload(fhconfigrsc)
            except Exception:
                raise RuntimeError(
                    "can not read piCtory configuration - check your hardware "
                    "configuration http://revpi_ip/"
                )
            return jdata

    def handlesignalend(self, cleanupfunc=None) -> None:
        """
        Manage signal handler for program termination.

        When this function is called, RevPiModIO takes over the SignalHandler
        for SIGINT and SIGTERM. These are received when the operating system
        or the user wants to cleanly terminate the control program.

        The optional function "cleanupfunc" is executed last after the last
        reading of the inputs. Outputs set there are written one last time
        after the function completes.
        This is intended for cleanup work, such as switching off the
        LEDs on the RevPi-Core.

        After receiving one of the signals once and terminating the
        RevPiModIO threads / functions, the SignalHandler are released
        again.

        :param cleanupfunc: Function to be executed after termination
        """
        # Check if function is callable
        if not (cleanupfunc is None or callable(cleanupfunc)):
            raise RuntimeError("registered function '{0}' ist not callable".format(cleanupfunc))
        self.__cleanupfunc = cleanupfunc
        signal(SIGINT, self.__evt_exit)
        signal(SIGTERM, self.__evt_exit)

    def mainloop(self, blocking=True) -> None:
        """
        Starts the mainloop with event monitoring.

        The current program thread is "trapped" here until
        RevPiDevicelist.exit() is called (unless blocking=False). It
        runs through the event monitoring and checks for changes of
        registered IOs with an event. If a change is detected,
        the program executes the associated functions in sequence.

        If the parameter "blocking" is specified as False, this activates
        event monitoring and does NOT block the program at the point of call.
        Well suited for GUI programming when events from the RevPi are needed
        but the program should continue to execute.

        :param blocking: If False, the program does NOT block here
        """
        # Check for context manager
        if self._context_manager:
            raise RuntimeError("Can not start mainloop inside a context manager (with statement)")
        # Check if a loop is already running
        if self._looprunning:
            raise RuntimeError("can not start multiple loops mainloop/cycleloop")

        # Check if devices are in autorefresh
        if len(self._lst_refresh) == 0:
            raise RuntimeError(
                "no device with autorefresh activated - use autorefresh=True "
                "or call .autorefresh_all() before entering mainloop"
            )

        # Create thread if it should not block
        if not blocking:
            self._th_mainloop = Thread(target=self.mainloop, kwargs={"blocking": True})
            self._th_mainloop.start()
            return

        # User event
        self.exitsignal.clear()

        # Clean event before entering mainloop
        self._exit.clear()
        self._looprunning = True

        # Create byte copy and attach prefire when entering mainloop
        for dev in self._lst_refresh:
            with dev._filelock:
                dev._ba_datacp = dev._ba_devdata[:]

                # Prepare prefire events
                for io in dev._dict_events:
                    for regfunc in dev._dict_events[io]:
                        if not regfunc.prefire:
                            continue

                        if (
                            regfunc.edge == BOTH
                            or regfunc.edge == RISING
                            and io.value
                            or regfunc.edge == FALLING
                            and not io.value
                        ):
                            if regfunc.as_thread:
                                self._imgwriter._eventqth.put((regfunc, io._name, io.value), False)
                            else:
                                self._imgwriter._eventq.put((regfunc, io._name, io.value), False)

        # Activate ImgWriter with event monitoring
        self._imgwriter._collect_events(True)
        e = None
        runtime = -1 if self._debug == -1 else 0

        while not self._exit.is_set():
            # Set runtime of event queue to 0
            if self._imgwriter._eventq.qsize() == 0:
                runtime = -1 if self._debug == -1 else 0

            try:
                tup_fire = self._imgwriter._eventq.get(timeout=1)

                # Start measuring runtime of the queue
                if runtime == 0:
                    runtime = default_timer()

                # Call directly since check is in io.IOBase.reg_event
                tup_fire[0].func(tup_fire[1], tup_fire[2])
                self._imgwriter._eventq.task_done()

                # Runtime check
                if runtime != -1 and default_timer() - runtime > self._imgwriter._refresh:
                    runtime = -1
                    warnings.warn(
                        "can not execute all event functions in one cycle - "
                        "optimize your event functions or rise .cycletime",
                        RuntimeWarning,
                    )
            except Empty:
                if not self._exit.is_set() and not self._imgwriter.is_alive():
                    e = RuntimeError("autorefresh thread not running")
                    break
            except Exception as ex:
                e = ex
                break

        # Leave mainloop
        self._imgwriter._collect_events(False)
        self._looprunning = False
        self._th_mainloop = None

        # Check for errors that were thrown in the loop
        if e is not None:
            self.exit(full=False)
            self.__exit_jobs()
            raise e

        # Execute exit strategy
        self.__exit_jobs()

    def readprocimg(self, device=None) -> bool:
        """
        Read all inputs of all/one device from the process image.

        Devices with active autorefresh are excluded!

        :param device: Only apply to single device
        :return: True if work on all devices was successful
        """
        if device is None:
            mylist = self.device
        else:
            dev = (
                device
                if isinstance(device, devicemodule.Device)
                else self.device.__getitem__(device)
            )

            if dev._selfupdate:
                raise RuntimeError(
                    "can not read process image, while device '{0}|{1}'"
                    "is in autorefresh mode".format(dev._position, dev._name)
                )
            mylist = [dev]

        # Read data completely
        self._myfh_lck.acquire()
        try:
            self._myfh.seek(0)
            bytesbuff = self._myfh.read(self._length)
        except IOError as e:
            self._gotioerror("readprocimg", e)
            return False
        finally:
            self._myfh_lck.release()

        for dev in mylist:
            if not dev._selfupdate:
                # Lock file handler
                dev._filelock.acquire()

                if self._monitoring or dev._shared_procimg:
                    # Read everything from the bus
                    dev._ba_devdata[:] = bytesbuff[dev._slc_devoff]
                else:
                    # Read inputs from the bus
                    dev._ba_devdata[dev._slc_inp] = bytesbuff[dev._slc_inpoff]

                dev._filelock.release()

        return True

    def resetioerrors(self) -> None:
        """Resets current IOError counter to 0."""
        self._ioerror = 0

    def setdefaultvalues(self, device=None) -> None:
        """
        All output buffers are set to the piCtory default values.

        :param device: Only apply to single device
        """
        if self._monitoring:
            raise RuntimeError("can not set default values, while system is in monitoring mode")

        if device is None:
            mylist = self.device
        else:
            dev = (
                device
                if isinstance(device, devicemodule.Device)
                else self.device.__getitem__(device)
            )
            mylist = [dev]

        for dev in mylist:
            for io in dev.get_outputs():
                io.set_value(io._defaultvalue)

    def syncoutputs(self, device=None) -> bool:
        """
        Read all currently set outputs in the process image.

        Devices with active autorefresh are excluded!

        :param device: Only apply to single device
        :return: True if work on all devices was successful
        """
        if device is None:
            mylist = self.device
        else:
            dev = (
                device
                if isinstance(device, devicemodule.Device)
                else self.device.__getitem__(device)
            )

            if dev._selfupdate:
                raise RuntimeError(
                    "can not sync outputs, while device '{0}|{1}'"
                    "is in autorefresh mode".format(dev._position, dev._name)
                )
            mylist = [dev]

        self._myfh_lck.acquire()
        try:
            self._myfh.seek(0)
            bytesbuff = self._myfh.read(self._length)
        except IOError as e:
            self._gotioerror("syncoutputs", e)
            return False
        finally:
            self._myfh_lck.release()

        for dev in mylist:
            if not dev._selfupdate:
                dev._filelock.acquire()
                dev._ba_devdata[dev._slc_out] = bytesbuff[dev._slc_outoff]
                dev._filelock.release()

        return True

    def writeprocimg(self, device=None) -> bool:
        """
        Write all outputs of all devices to the process image.

        Devices with active autorefresh are excluded!

        :param device: Only apply to single device
        :return: True if work on all devices was successful
        """
        if self._monitoring:
            raise RuntimeError("can not write process image, while system is in monitoring mode")

        if device is None:
            mylist = self.device
        else:
            dev = (
                device
                if isinstance(device, devicemodule.Device)
                else self.device.__getitem__(device)
            )

            if dev._selfupdate:
                raise RuntimeError(
                    "can not write process image, while device '{0}|{1}'"
                    "is in autorefresh mode".format(dev._position, dev._name)
                )
            mylist = [dev]

        global_ex = None
        for dev in mylist:
            if dev._selfupdate:
                # Do not update this device
                continue

            dev._filelock.acquire()

            if dev._shared_procimg:
                for io in dev._shared_write:
                    if not io._write_to_procimg():
                        global_ex = IOError("error on shared procimg while write")
                dev._shared_write.clear()
            else:
                # Write outputs to bus
                self._myfh_lck.acquire()
                try:
                    self._myfh.seek(dev._slc_outoff.start)
                    self._myfh.write(dev._ba_devdata[dev._slc_out])
                except IOError as e:
                    global_ex = e
                finally:
                    self._myfh_lck.release()

            dev._filelock.release()

        if self._buffedwrite:
            try:
                self._myfh.flush()
            except IOError as e:
                global_ex = e

        if global_ex:
            self._gotioerror("writeprocimg", global_ex)
            return False

        return True

    debug = property(_get_debug, _set_debug)
    configrsc = property(_get_configrsc)
    cycletime = property(_get_cycletime, _set_cycletime)
    ioerrors = property(_get_ioerrors)
    length = property(_get_length)
    maxioerrors = property(_get_maxioerrors, _set_maxioerrors)
    monitoring = property(_get_monitoring)
    procimg = property(_get_procimg)
    replace_io_file = property(_get_replace_io_file)
    simulator = property(_get_simulator)


class RevPiModIOSelected(RevPiModIO):
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
        deviceselection,
        autorefresh=False,
        monitoring=False,
        syncoutputs=True,
        procimg=None,
        configrsc=None,
        simulator=False,
        debug=True,
        replace_io_file=None,
        shared_procimg=False,
    ):
        """
        Instantiates the basic functions only for specified devices.

        The deviceselection parameter can be a single device position /
        single device name or a list with multiple positions / names.

        :param deviceselection: Position number or device name
        :ref: :func:`RevPiModIO.__init__(...)`
        """
        super().__init__(
            autorefresh,
            monitoring,
            syncoutputs,
            procimg,
            configrsc,
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


class RevPiModIODriver(RevPiModIOSelected):
    """
    Class to create custom drivers for virtual devices.

    With this class, only specified virtual devices are managed with RevPiModIO.
    During instantiation, inputs and outputs are automatically swapped to allow
    writing of inputs. The data can then be retrieved from the devices via logiCAD.
    """

    __slots__ = ()

    def __init__(
        self,
        virtdev,
        autorefresh=False,
        syncoutputs=True,
        procimg=None,
        configrsc=None,
        debug=True,
        replace_io_file=None,
        shared_procimg=False,
    ):
        """
        Instantiates the basic functions.

        Parameters 'monitoring' and 'simulator' are not available here
        as they are set automatically.

        :param virtdev: Virtual device or multiple as <class 'list'>
        :ref: :func:`RevPiModIO.__init__()`
        """
        # Load parent with monitoring=False and simulator=True
        if type(virtdev) not in (list, tuple):
            virtdev = (virtdev,)
        dev_select = DevSelect(DeviceType.VIRTUAL, "", virtdev)
        super().__init__(
            dev_select,
            autorefresh,
            False,
            syncoutputs,
            procimg,
            configrsc,
            True,
            debug,
            replace_io_file,
            shared_procimg,
        )


def run_plc(func, cycletime=50, replace_io_file=None, debug=True, procimg=None, configrsc=None):
    """
    Run Revoluton Pi as real plc with cycle loop and exclusive IO access.

    This function is just a shortcut to run the module in cycle loop mode and
    handle the program exit signal. You will access the .io, .core, .device
    via the cycletools in your cycle function.

    Shortcut for this source code:
        rpi = RevPiModIO(autorefresh=True, replace_io_file=..., debug=...)
        rpi.handlesignalend()
        return rpi.cycleloop(func, cycletime)

    :param func: Function to run every set milliseconds
    :param cycletime: Cycle time in milliseconds
    :param replace_io_file: Load replace IO configuration from file
    :param debug: Print all warnings and detailed error messages
    :param procimg: Use different process image
    :param configrsc: Use different piCtory configuration
    :return: None or the return value of the cycle function
    """
    rpi = RevPiModIO(
        autorefresh=True,
        replace_io_file=replace_io_file,
        debug=debug,
        procimg=procimg,
        configrsc=configrsc,
    )
    rpi.handlesignalend()
    return rpi.cycleloop(func, cycletime)

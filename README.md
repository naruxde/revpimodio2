# RevPiModIO

### Python3 programming for RevolutionPi of Kunbus GmbH.

The module provides all devices and IOs from the piCtory configuration in Python3. It allows direct
access to the values via their assigned name. Read and write actions on the process image are
managed by the module itself without the programmer having to worry about offsets and addresses.
For the gateway modules such as ModbusTCP or Profinet, own 'inputs' and 'outputs' can be defined
over a specific address range. These IOs can be accessed directly from the values using Python3.

#### [RevolutionPi Hardware](https://revolution.kunbus.com)
The hardware configuration is done via a web page, which is located on the PiCore module. The
program is called “piCtory”.

All inputs and outputs can be assigned symbolic names to facilitate their handling and programming.
If this configuration is created and activated, the data of the input, output and gateway modules
are exchanged via a 4096-byte process image.

#### [Our RevPiModIO module](https://revpimodio.org/)

If you use our module in Python3, it uses the piCtory configuration to create all the inputs and
outputs with their symbolic names as objects. The programmer can address these directly via the
symbolic names and access the values of the inputs and outputs – both reading and writing!

```
import revpimodio2
rpi = revpimodio2.RevPiModIO(autorefresh=True)

# If input t_on is high, set output h_on high
if rpi.io.t_on.value:
    rpi.io.h_on.value = True

# Clean up and sync process image
rpi.exit()
```

In addition, it provides the developer with many useful functions that can be used to develop
cyclic or event-based programs.

If you know the .add_event_detect(...) function of the GPIO module from the Raspberry Pi, you
can also achieve this behavior with the Revolution Pi:

```
import revpimodio2
rpi = revpimodio2.RevPiModIO(autorefresh=True)

def event_detect(ioname, iovalue):
    """Event function."""

    # Set actual input value to output 'h_on'
    rpi.io.h_on.value = iovalue

    print(ioname, iovalue)

# Bind event function to input 't_on'
rpi.io.t_on.reg_event(event_detect)

rpi.mainloop()
```

Even with hardware changes, but constant names of the inputs and outputs, the actual Python3
source code does not need to be changed!

#### How it works:

```
                         |-----------------------------------------------------|
                         |                                                     |
                         |                  Python program                     |
                         |                                                     |
--------------------     |     ----------------          --------------------  |
|                  |     |     |              |          |                  |  |
|  RevPi hardware  |  <----->  |  RevPiModIO  |  <---->  | Your source code |  |
|                  |     |     |              |          |                  |  |
--------------------     |     ----------------          --------------------  |
                         |                                                     |
                         |-----------------------------------------------------|
```

#### Summary

With this module we want to spare all Python developers a lot of work. All communication with the
process image is optimally performed inside the module. Changes to the inputs and outputs are also
evaluated along with the additional functions of the module give the developer many tools along
the way.

More examples: (https://revpimodio.org/en/blogs/examples/)

Provided under the [LGPLv3](LICENSE.txt) license

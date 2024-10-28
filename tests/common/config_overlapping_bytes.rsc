{
  "App": {
    "name": "PiCtory",
    "version": "2.1.2",
    "saveTS": "20231031130813",
    "language": "en",
    "layout": {
      "north": {
        "size": 70,
        "initClosed": false,
        "initHidden": false
      },
      "south": {
        "size": 257,
        "initClosed": false,
        "initHidden": false,
        "children": {
          "layout1": {
            "east": {
              "size": 500,
              "initClosed": false,
              "initHidden": false
            }
          }
        }
      },
      "east": {
        "size": 70,
        "initClosed": true,
        "initHidden": false,
        "children": {}
      },
      "west": {
        "size": 200,
        "initClosed": false,
        "initHidden": false,
        "children": {
          "layout1": {}
        }
      }
    }
  },
  "Summary": {
    "inpTotal": 77,
    "outTotal": 26
  },
  "Devices": [
    {
      "GUID": "8012178a-c632-ac37-6d81-98aae223e268",
      "id": "device_RevPiConnect4_20230409_1_0_001",
      "type": "BASE",
      "productType": "136",
      "position": "0",
      "name": "RevPi Connect 4",
      "bmk": "RevPi Connect 4",
      "inpVariant": 0,
      "outVariant": 0,
      "comment": "This is a RevPi Connect 4 Device",
      "offset": 0,
      "inp": {
        "0": [
          "RevPiStatus",
          "0",
          "8",
          "0",
          true,
          "0000",
          "",
          ""
        ],
        "1": [
          "RevPiIOCycle",
          "0",
          "8",
          "1",
          true,
          "0001",
          "",
          ""
        ],
        "2": [
          "RS485ErrorCnt",
          "0",
          "16",
          "2",
          false,
          "0002",
          "",
          ""
        ],
        "3": [
          "Core_Temperature",
          "0",
          "8",
          "4",
          false,
          "0003",
          "",
          ""
        ],
        "4": [
          "Core_Frequency",
          "0",
          "8",
          "5",
          false,
          "0004",
          "",
          ""
        ]
      },
      "out": {
        "0": [
          "RevPiOutput",
          "0",
          "8",
          "6",
          true,
          "0005",
          "",
          ""
        ],
        "1": [
          "RS485ErrorLimit1",
          "10",
          "16",
          "7",
          false,
          "0006",
          "",
          ""
        ],
        "2": [
          "RS485ErrorLimit2",
          "1000",
          "16",
          "9",
          false,
          "0007",
          "",
          ""
        ],
        "3": [
          "RevPiLED",
          "0",
          "16",
          "11",
          true,
          "0008",
          "",
          ""
        ]
      },
      "mem": {},
      "extend": {}
    },
    {
      "GUID": "fa804e6e-8e80-0ca5-3b96-4ec06bf99ed0",
      "id": "device_RevPiRO_20231018_1_0_001",
      "type": "LEFT_RIGHT",
      "productType": "137",
      "position": "32",
      "name": "RevPi RO",
      "bmk": "RevPi RO",
      "inpVariant": 0,
      "outVariant": 0,
      "comment": "",
      "offset": 13,
      "inp": {
        "0": [
          "Status",
          "0",
          "8",
          "0",
          false,
          "0000",
          "",
          ""
        ]
      },
      "out": {
        "0": [
          "RelayOutput_1",
          "0",
          "1",
          "1",
          true,
          "0001",
          "",
          "0"
        ],
        "1": [
          "RelayOutput_2",
          "0",
          "1",
          "1",
          true,
          "0002",
          "",
          "1"
        ],
        "2": [
          "RelayOutput_3",
          "0",
          "1",
          "1",
          true,
          "0003",
          "",
          "2"
        ],
        "3": [
          "RelayOutput_4",
          "0",
          "1",
          "1",
          true,
          "0004",
          "",
          "3"
        ]
      },
      "mem": {
        "0": [
          "RelayCycleWarningThreshold_1",
          "0",
          "32",
          "2",
          false,
          "0005",
          "",
          ""
        ],
        "1": [
          "RelayCycleWarningThreshold_2",
          "0",
          "32",
          "6",
          false,
          "0006",
          "",
          ""
        ],
        "2": [
          "RelayCycleWarningThreshold_3",
          "0",
          "32",
          "10",
          false,
          "0007",
          "",
          ""
        ],
        "3": [
          "RelayCycleWarningThreshold_4",
          "0",
          "32",
          "13",
          false,
          "0008",
          "",
          ""
        ]
      },
      "extend": {}
    }
  ],
  "Connections": []
}
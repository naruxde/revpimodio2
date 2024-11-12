{
  "App": {
    "name": "PiCtory",
    "version": "2.1.2",
    "saveTS": "20231031173852",
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
    "outTotal": 26.5
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
      "GUID": "4e91f8c6-df1c-90be-0d4d-82a6bb3275dc",
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
        ],
        "4": [
          "RelayOutputPadding",
          "0",
          "8",
          "1",
          true,
          "0009",
          "",
          ""
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
          "14",
          false,
          "0008",
          "",
          ""
        ]
      },
      "extend": {}
    },
    {
      "GUID": "8ee305fb-cb81-7dd0-f60b-d7988da4922e",
      "id": "device_RevPiDI_20160818_1_0_001",
      "type": "LEFT_RIGHT",
      "productType": "97",
      "position": "33",
      "name": "RevPi DI",
      "bmk": "RevPi DI",
      "inpVariant": 0,
      "outVariant": 0,
      "comment": "",
      "offset": 31.5,
      "inp": {
        "0": [
          "I_1",
          "0",
          "1",
          "0",
          true,
          "0000",
          "",
          "0"
        ],
        "1": [
          "I_2",
          "0",
          "1",
          "0",
          true,
          "0001",
          "",
          "1"
        ],
        "2": [
          "I_3",
          "0",
          "1",
          "0",
          true,
          "0002",
          "",
          "2"
        ],
        "3": [
          "I_4",
          "0",
          "1",
          "0",
          true,
          "0003",
          "",
          "3"
        ],
        "4": [
          "I_5",
          "0",
          "1",
          "0",
          true,
          "0004",
          "",
          "4"
        ],
        "5": [
          "I_6",
          "0",
          "1",
          "0",
          true,
          "0005",
          "",
          "5"
        ],
        "6": [
          "I_7",
          "0",
          "1",
          "0",
          true,
          "0006",
          "",
          "6"
        ],
        "7": [
          "I_8",
          "0",
          "1",
          "0",
          true,
          "0007",
          "",
          "7"
        ],
        "8": [
          "I_9",
          "0",
          "1",
          "0",
          true,
          "0008",
          "",
          "8"
        ],
        "9": [
          "I_10",
          "0",
          "1",
          "0",
          true,
          "0009",
          "",
          "9"
        ],
        "10": [
          "I_11",
          "0",
          "1",
          "0",
          true,
          "0010",
          "",
          "10"
        ],
        "11": [
          "I_12",
          "0",
          "1",
          "0",
          true,
          "0011",
          "",
          "11"
        ],
        "12": [
          "I_13",
          "0",
          "1",
          "0",
          true,
          "0012",
          "",
          "12"
        ],
        "13": [
          "I_14",
          "0",
          "1",
          "0",
          true,
          "0013",
          "",
          "13"
        ],
        "14": [
          "I_15",
          "0",
          "1",
          "0",
          true,
          "0014",
          "",
          "14"
        ],
        "15": [
          "I_16",
          "0",
          "1",
          "0",
          true,
          "0015",
          "",
          "15"
        ],
        "16": [
          "Status_i03",
          "0",
          "16",
          "4",
          false,
          "0016",
          "",
          ""
        ],
        "17": [
          "Counter_1",
          "0",
          "32",
          "6",
          false,
          "0017",
          "",
          ""
        ],
        "18": [
          "Counter_2",
          "0",
          "32",
          "10",
          false,
          "0018",
          "",
          ""
        ],
        "19": [
          "Counter_3",
          "0",
          "32",
          "14",
          false,
          "0019",
          "",
          ""
        ],
        "20": [
          "Counter_4",
          "0",
          "32",
          "18",
          false,
          "0020",
          "",
          ""
        ],
        "21": [
          "Counter_5",
          "0",
          "32",
          "22",
          false,
          "0021",
          "",
          ""
        ],
        "22": [
          "Counter_6",
          "0",
          "32",
          "26",
          false,
          "0022",
          "",
          ""
        ],
        "23": [
          "Counter_7",
          "0",
          "32",
          "30",
          false,
          "0023",
          "",
          ""
        ],
        "24": [
          "Counter_8",
          "0",
          "32",
          "34",
          false,
          "0024",
          "",
          ""
        ],
        "25": [
          "Counter_9",
          "0",
          "32",
          "38",
          false,
          "0025",
          "",
          ""
        ],
        "26": [
          "Counter_10",
          "0",
          "32",
          "42",
          false,
          "0026",
          "",
          ""
        ],
        "27": [
          "Counter_11",
          "0",
          "32",
          "46",
          false,
          "0027",
          "",
          ""
        ],
        "28": [
          "Counter_12",
          "0",
          "32",
          "50",
          false,
          "0028",
          "",
          ""
        ],
        "29": [
          "Counter_13",
          "0",
          "32",
          "54",
          false,
          "0029",
          "",
          ""
        ],
        "30": [
          "Counter_14",
          "0",
          "32",
          "58",
          false,
          "0030",
          "",
          ""
        ],
        "31": [
          "Counter_15",
          "0",
          "32",
          "62",
          false,
          "0031",
          "",
          ""
        ],
        "32": [
          "Counter_16",
          "0",
          "32",
          "66",
          false,
          "0032",
          "",
          ""
        ],
        "33": [
          "Output_Status",
          "0",
          "16",
          "2",
          false,
          "0050",
          "",
          ""
        ]
      },
      "out": {
        "0": [
          "Output",
          "0",
          "16",
          "70",
          false,
          "0051",
          "",
          ""
        ],
        "1": [
          "PWM_1",
          "0",
          "8",
          "72",
          false,
          "0052",
          "",
          ""
        ],
        "2": [
          "PWM_2",
          "0",
          "8",
          "73",
          false,
          "0053",
          "",
          ""
        ],
        "3": [
          "PWM_3",
          "0",
          "8",
          "74",
          false,
          "0054",
          "",
          ""
        ],
        "4": [
          "PWM_4",
          "0",
          "8",
          "75",
          false,
          "0055",
          "",
          ""
        ],
        "5": [
          "PWM_5",
          "0",
          "8",
          "76",
          false,
          "0056",
          "",
          ""
        ],
        "6": [
          "PWM_6",
          "0",
          "8",
          "77",
          false,
          "0057",
          "",
          ""
        ],
        "7": [
          "PWM_7",
          "0",
          "8",
          "78",
          false,
          "0058",
          "",
          ""
        ],
        "8": [
          "PWM_8",
          "0",
          "8",
          "79",
          false,
          "0059",
          "",
          ""
        ],
        "9": [
          "PWM_9",
          "0",
          "8",
          "80",
          false,
          "0060",
          "",
          ""
        ],
        "10": [
          "PWM_10",
          "0",
          "8",
          "81",
          false,
          "0061",
          "",
          ""
        ],
        "11": [
          "PWM_11",
          "0",
          "8",
          "82",
          false,
          "0062",
          "",
          ""
        ],
        "12": [
          "PWM_12",
          "0",
          "8",
          "83",
          false,
          "0063",
          "",
          ""
        ],
        "13": [
          "PWM_13",
          "0",
          "8",
          "84",
          false,
          "0064",
          "",
          ""
        ],
        "14": [
          "PWM_14",
          "0",
          "8",
          "85",
          false,
          "0065",
          "",
          ""
        ],
        "15": [
          "PWM_15",
          "0",
          "8",
          "86",
          false,
          "0066",
          "",
          ""
        ],
        "16": [
          "PWM_16",
          "0",
          "8",
          "87",
          false,
          "0067",
          "",
          ""
        ]
      },
      "mem": {
        "0": [
          "InputMode_1",
          "0",
          "8",
          "88",
          false,
          "0033",
          "",
          ""
        ],
        "1": [
          "InputMode_2",
          "0",
          "8",
          "89",
          false,
          "0034",
          "",
          ""
        ],
        "2": [
          "InputMode_3",
          "0",
          "8",
          "90",
          false,
          "0035",
          "",
          ""
        ],
        "3": [
          "InputMode_4",
          "0",
          "8",
          "91",
          false,
          "0036",
          "",
          ""
        ],
        "4": [
          "InputMode_5",
          "0",
          "8",
          "92",
          false,
          "0037",
          "",
          ""
        ],
        "5": [
          "InputMode_6",
          "0",
          "8",
          "93",
          false,
          "0038",
          "",
          ""
        ],
        "6": [
          "InputMode_7",
          "0",
          "8",
          "94",
          false,
          "0039",
          "",
          ""
        ],
        "7": [
          "InputMode_8",
          "0",
          "8",
          "95",
          false,
          "0040",
          "",
          ""
        ],
        "8": [
          "InputMode_9",
          "0",
          "8",
          "96",
          false,
          "0041",
          "",
          ""
        ],
        "9": [
          "InputMode_10",
          "0",
          "8",
          "97",
          false,
          "0042",
          "",
          ""
        ],
        "10": [
          "InputMode_11",
          "0",
          "8",
          "98",
          false,
          "0043",
          "",
          ""
        ],
        "11": [
          "InputMode_12",
          "0",
          "8",
          "99",
          false,
          "0044",
          "",
          ""
        ],
        "12": [
          "InputMode_13",
          "0",
          "8",
          "100",
          false,
          "0045",
          "",
          ""
        ],
        "13": [
          "InputMode_14",
          "0",
          "8",
          "101",
          false,
          "0046",
          "",
          ""
        ],
        "14": [
          "InputMode_15",
          "0",
          "8",
          "102",
          false,
          "0047",
          "",
          ""
        ],
        "15": [
          "InputMode_16",
          "0",
          "8",
          "103",
          false,
          "0048",
          "",
          ""
        ],
        "16": [
          "InputDebounce",
          "0",
          "16",
          "104",
          false,
          "0049",
          "",
          ""
        ],
        "17": [
          "OutputPushPull",
          "0",
          "16",
          "106",
          false,
          "0068",
          "",
          ""
        ],
        "18": [
          "OutputOpenLoadDetect",
          "0",
          "16",
          "108",
          false,
          "0069",
          "",
          ""
        ],
        "19": [
          "OutputPWMActive",
          "0",
          "16",
          "110",
          false,
          "0070",
          "",
          ""
        ],
        "20": [
          "OutputPWMFrequency",
          "1",
          "8",
          "112",
          false,
          "0071",
          "",
          ""
        ]
      },
      "extend": {}
    }
  ],
  "Connections": []
}
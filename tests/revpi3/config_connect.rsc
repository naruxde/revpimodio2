{
  "App": {
    "name": "PiCtory",
    "version": "1.3.10",
    "saveTS": "20180731225026",
    "language": "en",
    "layout": {
      "north": {
        "size": 70,
        "initClosed": false,
        "initHidden": false
      },
      "south": {
        "size": 420,
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
    "inpTotal": 38,
    "outTotal": 37
  },
  "Devices": [
    {
      "GUID": "6ad3c1a4-6870-3bf1-6d55-b9d991ba9dc0",
      "id": "device_RevPiConnect_20171023_1_0_001",
      "type": "BASE",
      "productType": "105",
      "position": "0",
      "name": "RevPi Connect V1.0",
      "bmk": "RevPi Connect V1.0",
      "inpVariant": 0,
      "outVariant": 0,
      "comment": "This is a RevPi Connect",
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
          "RevPiLED",
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
        ]
      },
      "mem": {},
      "extend": {}
    },
    {
      "GUID": "437fb6d7-6ef6-8fc8-0bf2-f618576e1aca",
      "id": "device_RevPiConBT_20180425_1_0_001",
      "type": "RIGHT",
      "productType": "111",
      "position": "32",
      "name": "Connect Bluetooth",
      "bmk": "Connect Bluetooth",
      "inpVariant": 0,
      "outVariant": 0,
      "comment": "",
      "offset": 11,
      "inp": {},
      "out": {},
      "mem": {},
      "extend": {}
    },
    {
      "GUID": "2e9cd04b-b7e6-715a-4925-82ffbf0ff45e",
      "id": "device_Virtual01_20160818_1_0_001",
      "type": "VIRTUAL",
      "productType": "32768",
      "position": "64",
      "name": "Virtual Device 32 Byte",
      "bmk": "Virtual Device 32 Byte",
      "inpVariant": 0,
      "outVariant": 0,
      "comment": "Virtual Device to reserve space in process image for user applications",
      "offset": 11,
      "inp": {
        "0": [
          "Input_1",
          "0",
          "8",
          "0",
          false,
          "0000",
          "",
          ""
        ],
        "1": [
          "Input_2",
          "0",
          "8",
          "1",
          false,
          "0001",
          "",
          ""
        ],
        "2": [
          "Input_3",
          "0",
          "8",
          "2",
          false,
          "0002",
          "",
          ""
        ],
        "3": [
          "Input_4",
          "0",
          "8",
          "3",
          false,
          "0003",
          "",
          ""
        ],
        "4": [
          "Input_5",
          "0",
          "8",
          "4",
          false,
          "0004",
          "",
          ""
        ],
        "5": [
          "Input_6",
          "0",
          "8",
          "5",
          false,
          "0005",
          "",
          ""
        ],
        "6": [
          "Input_7",
          "0",
          "8",
          "6",
          false,
          "0006",
          "",
          ""
        ],
        "7": [
          "Input_8",
          "0",
          "8",
          "7",
          false,
          "0007",
          "",
          ""
        ],
        "8": [
          "Input_9",
          "0",
          "8",
          "8",
          false,
          "0008",
          "",
          ""
        ],
        "9": [
          "Input_10",
          "0",
          "8",
          "9",
          false,
          "0009",
          "",
          ""
        ],
        "10": [
          "Input_11",
          "0",
          "8",
          "10",
          false,
          "0010",
          "",
          ""
        ],
        "11": [
          "Input_12",
          "0",
          "8",
          "11",
          false,
          "0011",
          "",
          ""
        ],
        "12": [
          "Input_13",
          "0",
          "8",
          "12",
          false,
          "0012",
          "",
          ""
        ],
        "13": [
          "Input_14",
          "0",
          "8",
          "13",
          false,
          "0013",
          "",
          ""
        ],
        "14": [
          "Input_15",
          "0",
          "8",
          "14",
          false,
          "0014",
          "",
          ""
        ],
        "15": [
          "Input_16",
          "0",
          "8",
          "15",
          false,
          "0015",
          "",
          ""
        ],
        "16": [
          "Input_17",
          "0",
          "8",
          "16",
          false,
          "0016",
          "",
          ""
        ],
        "17": [
          "Input_18",
          "0",
          "8",
          "17",
          false,
          "0017",
          "",
          ""
        ],
        "18": [
          "Input_19",
          "0",
          "8",
          "18",
          false,
          "0018",
          "",
          ""
        ],
        "19": [
          "Input_20",
          "0",
          "8",
          "19",
          false,
          "0019",
          "",
          ""
        ],
        "20": [
          "Input_21",
          "0",
          "8",
          "20",
          false,
          "0020",
          "",
          ""
        ],
        "21": [
          "Input_22",
          "0",
          "8",
          "21",
          false,
          "0021",
          "",
          ""
        ],
        "22": [
          "Input_23",
          "0",
          "8",
          "22",
          false,
          "0022",
          "",
          ""
        ],
        "23": [
          "Input_24",
          "0",
          "8",
          "23",
          false,
          "0023",
          "",
          ""
        ],
        "24": [
          "Input_25",
          "0",
          "8",
          "24",
          false,
          "0024",
          "",
          ""
        ],
        "25": [
          "Input_26",
          "0",
          "8",
          "25",
          false,
          "0025",
          "",
          ""
        ],
        "26": [
          "Input_27",
          "0",
          "8",
          "26",
          false,
          "0026",
          "",
          ""
        ],
        "27": [
          "Input_28",
          "0",
          "8",
          "27",
          false,
          "0027",
          "",
          ""
        ],
        "28": [
          "Input_29",
          "0",
          "8",
          "28",
          false,
          "0028",
          "",
          ""
        ],
        "29": [
          "Input_30",
          "0",
          "8",
          "29",
          false,
          "0029",
          "",
          ""
        ],
        "30": [
          "Input_31",
          "0",
          "8",
          "30",
          false,
          "0030",
          "",
          ""
        ],
        "31": [
          "Input_32",
          "0",
          "8",
          "31",
          false,
          "0031",
          "",
          ""
        ]
      },
      "out": {
        "0": [
          "Output_1",
          "0",
          "8",
          "32",
          false,
          "0032",
          "",
          ""
        ],
        "1": [
          "Output_2",
          "0",
          "8",
          "33",
          false,
          "0033",
          "",
          ""
        ],
        "2": [
          "Output_3",
          "0",
          "8",
          "34",
          false,
          "0034",
          "",
          ""
        ],
        "3": [
          "Output_4",
          "0",
          "8",
          "35",
          false,
          "0035",
          "",
          ""
        ],
        "4": [
          "Output_5",
          "0",
          "8",
          "36",
          false,
          "0036",
          "",
          ""
        ],
        "5": [
          "Output_6",
          "0",
          "8",
          "37",
          false,
          "0037",
          "",
          ""
        ],
        "6": [
          "Output_7",
          "0",
          "8",
          "38",
          false,
          "0038",
          "",
          ""
        ],
        "7": [
          "Output_8",
          "0",
          "8",
          "39",
          false,
          "0039",
          "",
          ""
        ],
        "8": [
          "Output_9",
          "0",
          "8",
          "40",
          false,
          "0040",
          "",
          ""
        ],
        "9": [
          "Output_10",
          "0",
          "8",
          "41",
          false,
          "0041",
          "",
          ""
        ],
        "10": [
          "Output_11",
          "0",
          "8",
          "42",
          false,
          "0042",
          "",
          ""
        ],
        "11": [
          "Output_12",
          "0",
          "8",
          "43",
          false,
          "0043",
          "",
          ""
        ],
        "12": [
          "Output_13",
          "0",
          "8",
          "44",
          false,
          "0044",
          "",
          ""
        ],
        "13": [
          "Output_14",
          "0",
          "8",
          "45",
          false,
          "0045",
          "",
          ""
        ],
        "14": [
          "Output_15",
          "0",
          "8",
          "46",
          false,
          "0046",
          "",
          ""
        ],
        "15": [
          "Output_16",
          "0",
          "8",
          "47",
          false,
          "0047",
          "",
          ""
        ],
        "16": [
          "Output_17",
          "0",
          "8",
          "48",
          false,
          "0048",
          "",
          ""
        ],
        "17": [
          "Output_18",
          "0",
          "8",
          "49",
          false,
          "0049",
          "",
          ""
        ],
        "18": [
          "Output_19",
          "0",
          "8",
          "50",
          false,
          "0050",
          "",
          ""
        ],
        "19": [
          "Output_20",
          "0",
          "8",
          "51",
          false,
          "0051",
          "",
          ""
        ],
        "20": [
          "Output_21",
          "0",
          "8",
          "52",
          false,
          "0052",
          "",
          ""
        ],
        "21": [
          "Output_22",
          "0",
          "8",
          "53",
          false,
          "0053",
          "",
          ""
        ],
        "22": [
          "Output_23",
          "0",
          "8",
          "54",
          false,
          "0054",
          "",
          ""
        ],
        "23": [
          "Output_24",
          "0",
          "8",
          "55",
          false,
          "0055",
          "",
          ""
        ],
        "24": [
          "Output_25",
          "0",
          "8",
          "56",
          false,
          "0056",
          "",
          ""
        ],
        "25": [
          "Output_26",
          "0",
          "8",
          "57",
          false,
          "0057",
          "",
          ""
        ],
        "26": [
          "Output_27",
          "0",
          "8",
          "58",
          false,
          "0058",
          "",
          ""
        ],
        "27": [
          "Output_28",
          "0",
          "8",
          "59",
          false,
          "0059",
          "",
          ""
        ],
        "28": [
          "Output_29",
          "0",
          "8",
          "60",
          false,
          "0060",
          "",
          ""
        ],
        "29": [
          "Output_30",
          "0",
          "8",
          "61",
          false,
          "0061",
          "",
          ""
        ],
        "30": [
          "Output_31",
          "0",
          "8",
          "62",
          false,
          "0062",
          "",
          ""
        ],
        "31": [
          "Output_32",
          "0",
          "8",
          "63",
          false,
          "0063",
          "",
          ""
        ]
      },
      "mem": {},
      "extend": {}
    }
  ],
  "Connections": []
}
